/**
 * PocketBase клиент для авторизации и работы с данными
 */

const POCKETBASE_URL = 'http://127.0.0.1:8090';
const API_BASE_URL = 'http://127.0.0.1:5000';

class AuthManager {
  constructor() {
    this.currentUser = null;
    this.sessionToken = null;
    this.debugEnabled = true;
  }

  /**
   * Проверить наличие токена авторизации в URL
   */
  checkAuthToken() {
    this.logDebug('checkAuthToken', 'Checking auth token in URL');
    const urlParams = new URLSearchParams(window.location.search);
    const authToken = urlParams.get('auth');

    if (authToken) {
      this.logInfo('checkAuthToken', 'Auth token found in URL');
      this.authenticateWithToken(authToken);
    } else {
      this.logDebug('checkAuthToken', 'No auth token, checking saved session');
      this.checkSavedSession();
    }
  }

  /**
   * Авторизация по токену из ссылки
   */
  async authenticateWithToken(authToken) {
    try {
      this.logInfo('authenticateWithToken', 'Authenticating via magic link');
      // Шаг 6: Валидация токена и получение данных пользователя
      const response = await fetch(
        `${POCKETBASE_URL}/api/collections/bot_users/records?filter=auth_link="${authToken}"`,
        {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        this.logError('authenticateWithToken', 'Auth token validation failed', response.status);
        throw new Error('Invalid auth token');
      }

      const data = await response.json();
      this.logDebug('authenticateWithToken', 'Auth token lookup result', data);
      const user = data.items?.[0];

      if (!user) {
        this.logWarn('authenticateWithToken', 'Auth token did not resolve to user');
        this.showError('Неверная или устаревшая ссылка авторизации');
        return;
      }

      // Шаг 7: Создание сессии
      await this.createSession(user);

      // Удаляем токен из URL
      window.history.replaceState({}, document.title, window.location.pathname);

      this.showSuccess('Вы успешно авторизованы!');
      this.logInfo('authenticateWithToken', 'User authorized via magic link', { userId: user.id });

    } catch (error) {
      this.logError('authenticateWithToken', 'Authentication error', error);
      this.showError('Ошибка авторизации. Попробуйте получить новую ссылку в боте.');
    }
  }

  /**
   * Создание сессии и сохранение в localStorage
   */
  async createSession(user) {
    this.currentUser = user;
    this.sessionToken = user.session_token;
    this.logInfo('createSession', 'Session created for user', {
      recordId: user.id,
      telegramId: user.user_id,
      username: user.username
    });

    // Сохраняем сессию в localStorage (user.id - это PocketBase ID записи)
    localStorage.setItem('session_token', user.session_token);
    localStorage.setItem('user_id', user.id);  // PocketBase ID записи
    localStorage.setItem('telegram_id', user.user_id);  // Telegram user ID

    // Обновляем UI
    this.updateUI();

    // Логируем активность
    await this.logActivity('Вход в систему');
  }

  /**
   * Проверка сохраненной сессии
   */
  async checkSavedSession() {
    const sessionToken = localStorage.getItem('session_token');
    const userId = localStorage.getItem('user_id');

    this.logDebug('checkSavedSession', 'Evaluating saved credentials', {
      hasToken: Boolean(sessionToken),
      tokenPreview: sessionToken ? sessionToken.substring(0, 10) + '...' : null,
      userId
    });

    if (!sessionToken || !userId) {
      this.showLoginPrompt();
      return;
    }

    try {
      // Проверяем валидность сессии (userId - это PocketBase ID записи)
      const response = await fetch(
        `${POCKETBASE_URL}/api/collections/bot_users/records/${userId}`,
        {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        this.logWarn('checkSavedSession', 'Stored session invalid or expired', response.status);
        throw new Error('Session expired');
      }

      const user = await response.json();
      this.logDebug('checkSavedSession', 'Loaded user from session', user);

      if (user.session_token !== sessionToken) {
        this.logWarn('checkSavedSession', 'Session token mismatch detected');
        throw new Error('Session invalid');
      }

      this.currentUser = user;
      this.sessionToken = sessionToken;
      this.updateUI();

    } catch (error) {
      this.logError('checkSavedSession', 'Session validation failed', error);
      this.logout();
    }
  }

  /**
   * Обновление UI после авторизации
   */
  updateUI() {
    if (!this.currentUser) {
      this.logWarn('updateUI', 'Tried to update UI without user');
      return;
    }

    this.logDebug('updateUI', 'Applying user data to profile', {
      recordId: this.currentUser.id,
      telegramId: this.currentUser.user_id,
      username: this.currentUser.username
    });

    // Обновляем профиль
    const usernameEl = document.getElementById('userUsername');
    const telegramIdEl = document.getElementById('userTelegramId');

    if (usernameEl) {
      usernameEl.textContent = `@${this.currentUser.username || 'пользователь'}`;
      this.logDebug('updateUI', 'Username rendered', usernameEl.textContent);
    } else {
      this.logWarn('updateUI', 'Element userUsername not found in DOM');
    }

    if (telegramIdEl) {
      telegramIdEl.textContent = this.currentUser.user_id;
      this.logDebug('updateUI', 'Telegram ID rendered', telegramIdEl.textContent);
    } else {
      this.logWarn('updateUI', 'Element userTelegramId not found in DOM');
    }

    // Показываем кнопку профиля
    const profileBtn = document.getElementById('profileBtn');
    if (profileBtn) {
      profileBtn.style.display = 'flex';
      this.logDebug('updateUI', 'Profile button shown');
    } else {
      this.logWarn('updateUI', 'Profile button element missing');
    }

    this.logInfo('updateUI', 'Base profile info rendered');
  }

  /**
   * Загрузка данных пользователя (заказы, активность)
   * ОТКЛЮЧЕНО: orders и audit_logs используются только в Telegram-боте
   */
  async loadUserData() {
    if (!this.currentUser) {
      this.logWarn('loadUserData', 'Cannot load data without authenticated user');
      this.showLoginPrompt();
      return;
    }

    const ordersList = document.getElementById('ordersList');
    const activityList = document.getElementById('activityList');

    if (ordersList) {
      ordersList.innerHTML = '<p class="loading">Загрузка заказов...</p>';
      this.logDebug('loadUserData', 'Orders list placeholder rendered');
    }

    if (activityList) {
      activityList.innerHTML = '<p class="loading">Загрузка активности...</p>';
      this.logDebug('loadUserData', 'Activity list placeholder rendered');
    }

    try {
      const history = await this.fetchProfileHistory();
      const orders = Array.isArray(history.orders) ? history.orders : [];
      const activity = Array.isArray(history.activity) ? history.activity : [];
      this.renderOrders(orders);
      this.renderActivity(activity);
      this.logInfo('loadUserData', 'History loaded via API proxy', {
        orders: orders.length,
        activity: activity.length
      });
    } catch (apiError) {
      this.logError('loadUserData', 'History API failed, falling back to direct PocketBase requests', apiError);
      try {
        await Promise.all([
          this.loadOrders(),
          this.loadActivity()
        ]);
        this.logInfo('loadUserData', 'Fallback orders and activity requests finished');
      } catch (fallbackError) {
        this.logError('loadUserData', 'Failed to load profile data even after fallback', fallbackError);
      }
    }
  }

  async fetchProfileHistory() {
    const sessionToken = this.sessionToken || localStorage.getItem('session_token');
    const userId = this.currentUser?.id || localStorage.getItem('user_id');

    if (!sessionToken) {
      this.logWarn('fetchProfileHistory', 'Session token missing, cannot hit proxy API');
      throw new Error('Missing session token');
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/profile/history`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Token': sessionToken
        },
        body: JSON.stringify({
          session_token: sessionToken,
          user_id: userId
        })
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`History API responded with ${response.status}: ${errorText}`);
      }

      const payload = await response.json();
      const payloadData = payload || {};
      const ordersArray = Array.isArray(payloadData.orders) ? payloadData.orders : [];
      const activityArray = Array.isArray(payloadData.activity) ? payloadData.activity : [];
      const metaObject = payloadData && typeof payloadData.meta === 'object' ? payloadData.meta : {};
      const ordersCount = ordersArray.length;
      const activityCount = activityArray.length;
      this.logDebug('fetchProfileHistory', 'Proxy API responded', {
        orders: ordersCount,
        activity: activityCount
      });
      return {
        orders: ordersArray,
        activity: activityArray,
        meta: metaObject
      };
    } catch (error) {
      this.logError('fetchProfileHistory', 'Proxy API call failed', error);
      throw error;
    }
  }

  /**
   * Загрузка истории заказов
   */
  async loadOrders() {
    const ordersList = document.getElementById('ordersList');
    if (!this.currentUser) {
      this.logWarn('loadOrders', 'No authenticated user available');
      return;
    }
    if (!ordersList) {
      this.logWarn('loadOrders', 'ordersList element missing in DOM');
      return;
    }

    try {
      const filter = encodeURIComponent(`user_bot="${this.currentUser.id}"`);
      const url = `${POCKETBASE_URL}/api/collections/orders/records?filter=${filter}&sort=-created&perPage=20`;
      this.logDebug('loadOrders', 'Fetching orders from PocketBase', { url, user: this.currentUser.id });

      const response = await fetch(url, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!response.ok) {
        this.logWarn('loadOrders', 'Orders request failed', response.status);
        throw new Error(`Orders response ${response.status}`);
      }

      const data = await response.json();
      this.logInfo('loadOrders', 'Orders fetched successfully', {
        count: data?.items?.length || 0,
        totalPages: data?.totalPages,
        page: data?.page
      });
      this.renderOrders(data.items || []);
    } catch (error) {
      this.logError('loadOrders', 'Error loading orders', error);
      ordersList.innerHTML = '<p class="muted-text">Не удалось загрузить заказы. Попробуйте позже.</p>';
    }
  }

  /**
   * Отображение заказов в UI
   */
  renderOrders(orders) {
    const ordersList = document.getElementById('ordersList');
    if (!ordersList) return;

     this.logDebug('renderOrders', 'Rendering orders collection', {
       count: orders.length,
       sample: orders.slice(0, 2)
     });

    if (orders.length === 0) {
      this.logInfo('renderOrders', 'No orders to display for user');
      ordersList.innerHTML = '<p class="muted-text">У вас пока нет заказов. Начните покупки в <a href="#" onclick="authManager.showCatalog(); return false;">каталоге</a>!</p>';
      return;
    }

    orders.forEach(order => {
      this.logDebug('renderOrders', 'Order snapshot', {
        id: order.id,
        publicId: order.order_id || order.order_number,
        status: order.status,
        total: order.total_amount,
        created: order.created
      });
    });

    ordersList.innerHTML = orders.map(order => {
      const orderNumber = order.order_id || order.order_number || ('#' + (order.id || '').substring(0, 8).toUpperCase());
      const status = (order.status || 'pending').toLowerCase();
      const statusClass = this.getOrderStatusClass(status);
      const statusText = this.getOrderStatusText(status);
      const createdAt = order.delivered_at || order.paid_at || order.created || order.created_at;
      const itemsText = this.buildOrderItemsText(order);
      const totalAmount = this.formatAmount(order.total_amount);
      const canDownload = ['completed', 'delivered', 'paid'].includes(status);

      return `
        <div class="order-card">
          <div class="order-header">
            <span class="order-number">${orderNumber}</span>
            <span class="order-status ${statusClass}">${statusText}</span>
          </div>
          <p class="order-date">${this.formatDate(createdAt)}</p>
          <p class="order-items">${itemsText}</p>
          <p class="order-total">${totalAmount} USDT</p>
          ${canDownload ? `<button class="btn-outline small" onclick="authManager.downloadOrder('${order.id}')">Скачать повторно</button>` : ''}
        </div>
      `;
    }).join('');

        this.logInfo('renderOrders', 'Orders rendered to DOM');
  }

  composeProductDisplay(title, typeOfWarm, regionForFilter) {
    const parts = [];
    if (title && typeof title === 'string' && title.trim()) {
      parts.push(title.trim());
    }
    if (typeOfWarm && typeof typeOfWarm === 'string' && typeOfWarm.trim()) {
      parts.push(typeOfWarm.trim());
    }
    if (regionForFilter && typeof regionForFilter === 'string' && regionForFilter.trim()) {
      parts.push(regionForFilter.trim());
    }
    if (!parts.length) {
      return 'Товар';
    }
    return parts.join(' ');
  }

  buildOrderItemsText(order) {
    const inlineItems = Array.isArray(order.items) ? order.items : [];
    if (inlineItems.length) {
      this.logDebug('buildOrderItemsText', 'Using embedded items array', inlineItems);
      const parts = inlineItems.map(item => {
        const title = item.display_name || item.product_title || item.product_id || item.title || 'Товар';
        const label = this.composeProductDisplay(
          title,
          item.type_of_warm || item.type || '',
          item.region_for_filter || item.region || ''
        );
        const quantity = item.quantity || 0;
        return quantity ? `${quantity}× ${label}` : label;
      });
      return parts.join(', ');
    }

    const expandedItems = order.expand?.order_items;
    if (Array.isArray(expandedItems) && expandedItems.length) {
      this.logDebug('buildOrderItemsText', 'Using expanded order_items relation', expandedItems);
      const parts = expandedItems.map(item => {
        const product = item.expand?.product;
        const label = this.composeProductDisplay(
          product?.title || product?.display_name || item.display_name || item.product || 'Товар',
          product?.type_of_warm || item.type_of_warm || '',
          product?.region_for_filter || item.region_for_filter || ''
        );
        return `${item.quantity || 1}× ${label}`;
      });
      return parts.join(', ');
    }

    this.logWarn('buildOrderItemsText', 'Order without items payload', order);
    return 'Нет позиций';
  }

  formatAmount(value) {
    const amount = parseFloat(value || 0);
    if (Number.isNaN(amount)) {
      this.logWarn('formatAmount', 'Amount is not a number', value);
      return '0.00';
    }
    return amount.toFixed(2);
  }

  /**
   * Загрузка истории активности
   */
  async loadActivity() {
    const activityList = document.getElementById('activityList');
    if (!this.currentUser) {
      this.logWarn('loadActivity', 'No authenticated user, aborting');
      return;
    }
    if (!activityList) {
      this.logWarn('loadActivity', 'activityList element missing in DOM');
      return;
    }

    try {
      this.logDebug('loadActivity', 'Fetching user activity');
      let activities = await this.fetchUserActivity();

      if (!activities.length) {
        this.logWarn('loadActivity', 'Primary user_activity collection empty, falling back to audit_logs');
        activities = await this.fetchAuditLogActivity();
      }

      if (!activities.length) {
        activities = [
          {
            created: this.currentUser.last_activity || new Date().toISOString(),
            text: 'Последняя активность'
          }
        ];
        this.logWarn('loadActivity', 'Both sources empty, using synthetic fallback event', activities[0]);
      }

      this.renderActivity(activities);
      this.logInfo('loadActivity', 'Activity rendered', { count: activities.length });
    } catch (error) {
      this.logError('loadActivity', 'Failed to load activity history', error);
      activityList.innerHTML = '<p class="muted-text">Не удалось загрузить активность. Попробуйте позже.</p>';
    }
  }

  /**
   * Отображение истории активности в UI
   */
  renderActivity(activities) {
    const activityList = document.getElementById('activityList');
    if (!activityList) return;

    const eventsToRender = (activities || []).slice(0, 5);

    if (!eventsToRender.length) {
      this.logInfo('renderActivity', 'Activity list empty, showing placeholder');
      activityList.innerHTML = '<p class="muted-text">История активности пуста</p>';
      return;
    }

    this.logDebug('renderActivity', 'Rendering activity events', eventsToRender);
    activityList.innerHTML = eventsToRender.map(activity => `
      <div class="activity-item">
        <span class="activity-date">${this.formatDate(activity.created)}</span>
        <span class="activity-text">${activity.text}</span>
      </div>
    `).join('');
  }

  async fetchUserActivity() {
    try {
      const filter = encodeURIComponent(`user_bot="${this.currentUser.id}"`);
      const url = `${POCKETBASE_URL}/api/collections/user_activity/records?filter=${filter}&sort=-created&perPage=20`;
      this.logDebug('fetchUserActivity', 'Requesting user_activity collection', { url });
      const response = await fetch(url, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!response.ok) {
        this.logWarn('fetchUserActivity', 'user_activity request failed', response.status);
        return [];
      }

      const data = await response.json();
      const items = data.items || [];
      this.logInfo('fetchUserActivity', 'Fetched user_activity entries', { count: items.length });
      return items.map(entry => this.normalizeActivityEntry(entry, 'user_activity'));
    } catch (error) {
      this.logWarn('fetchUserActivity', 'Primary activity fetch failed, will fallback', error);
      return [];
    }
  }

  async fetchAuditLogActivity() {
    try {
      const filter = encodeURIComponent(`entity_type="bot_user" && entity_id="${this.currentUser.id}"`);
      const url = `${POCKETBASE_URL}/api/collections/audit_logs/records?filter=${filter}&sort=-created&perPage=20`;
      this.logDebug('fetchAuditLogActivity', 'Requesting audit_logs', { url });
      const response = await fetch(url, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!response.ok) {
        this.logWarn('fetchAuditLogActivity', 'audit_logs request failed', response.status);
        return [];
      }

      const data = await response.json();
      const items = data.items || [];
      this.logInfo('fetchAuditLogActivity', 'Fetched audit log entries', { count: items.length });
      return items.map(entry => this.normalizeActivityEntry(entry, 'audit_logs'));
    } catch (error) {
      this.logWarn('fetchAuditLogActivity', 'Audit log fetch failed', error);
      return [];
    }
  }

  normalizeActivityEntry(entry, source = 'user_activity') {
    const created = entry.created || entry.updated || new Date().toISOString();

    if (source === 'user_activity' && entry.event_type) {
      const label = this.getActivityEventLabel(entry.event_type);
      const detail = typeof entry.details === 'string'
        ? entry.details
        : entry.details && typeof entry.details === 'object'
          ? entry.details.description || JSON.stringify(entry.details)
          : '';
      const text = detail ? `${label}: ${detail}` : label;
      const normalized = { created, text };
      this.logDebug('normalizeActivityEntry', 'Normalized user_activity event', normalized);
      return normalized;
    }

    const actionText = entry.action || entry.details || entry.event_type || 'Активность';
    const normalized = { created, text: actionText };
    this.logDebug('normalizeActivityEntry', 'Normalized audit_log event', normalized);
    return normalized;
  }

  getActivityEventLabel(eventType) {
    const map = {
      'command_start': 'Запуск бота',
      'command_menu': 'Главное меню',
      'catalog_opened': 'Открытие каталога',
      'invoice_created': 'Создан счёт',
      'order_paid': 'Оплата получена',
      'order_delivered': 'Доставка выполнена'
    };
    return map[eventType] || 'Активность';
  }

  /**
   * Логирование активности пользователя
   */
  async logActivity(action) {
    if (!this.currentUser) {
      this.logWarn('logActivity', 'Cannot log activity without current user');
      return;
    }

    try {
      this.logDebug('logActivity', 'Recording audit log action', action);
      await fetch(
        `${POCKETBASE_URL}/api/collections/audit_logs/records`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            entity_type: 'bot_user',
            entity_id: this.currentUser.id,
            action: action,
            payload: {},
          }),
        }
      );

      // Обновляем last_activity в bot_users
      await fetch(
        `${POCKETBASE_URL}/api/collections/bot_users/records/${this.currentUser.id}`,
        {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            last_activity: new Date().toISOString(),
          }),
        }
      );

      this.logInfo('logActivity', 'Audit log recorded and last_activity updated');
    } catch (error) {
      this.logError('logActivity', 'Failed to log activity', error);
    }
  }

  /**
   * Выход из системы
   */
  logout() {
    this.currentUser = null;
    this.sessionToken = null;
    localStorage.removeItem('session_token');
    localStorage.removeItem('user_id');
    localStorage.removeItem('telegram_id');

    this.logInfo('logout', 'User logged out, local storage cleared');
    this.showLoginPrompt();
  }

  /**
   * Показать приглашение войти через бота
   */
  showLoginPrompt() {
    const profileBtn = document.getElementById('profileBtn');
    if (profileBtn) {
      profileBtn.style.display = 'none';
      this.logDebug('showLoginPrompt', 'Profile button hidden, prompting login');
    } else {
      this.logWarn('showLoginPrompt', 'Profile button not found while showing login prompt');
    }
  }

  /**
   * Вспомогательные методы
   */
  formatDate(dateString) {
    if (!dateString) return '—';
    const date = new Date(dateString);
    if (isNaN(date.getTime())) {
      this.logWarn('formatDate', 'Unable to parse date', dateString);
      return '—';
    }
    return date.toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  getOrderStatusClass(status) {
    const normalized = (status || 'pending').toLowerCase();
    const statusMap = {
      'completed': 'completed',
      'delivered': 'delivered',
      'paid': 'completed',
      'pending': 'pending',
      'awaiting_invoice': 'pending',
      'awaiting_payment': 'pending',
      'processing': 'processing',
      'in_progress': 'processing',
      'cancelled': 'cancelled',
      'failed': 'failed',
      'error': 'failed'
    };
    return statusMap[normalized] || 'pending';
  }

  getOrderStatusText(status) {
    const normalized = (status || 'pending').toLowerCase();
    const statusMap = {
      'completed': 'Завершён',
      'delivered': 'Доставлен',
      'paid': 'Оплачен',
      'pending': 'Ожидает оплаты',
      'awaiting_invoice': 'Ждёт счёт',
      'awaiting_payment': 'Ждёт оплату',
      'processing': 'В обработке',
      'in_progress': 'В обработке',
      'cancelled': 'Отменён',
      'failed': 'Ошибка',
      'error': 'Ошибка'
    };
    return statusMap[normalized] || 'Неизвестно';
  }

  logDebug(scope, message, payload) {
    if (!this.debugEnabled) return;
    const prefix = `[Auth:${scope}]`;
    if (typeof payload === 'undefined') {
      console.log(prefix, message);
    } else {
      console.log(prefix, message, payload);
    }
  }

  logInfo(scope, message, payload) {
    const prefix = `[Auth:${scope}]`;
    if (typeof payload === 'undefined') {
      console.info(prefix, message);
    } else {
      console.info(prefix, message, payload);
    }
  }

  logWarn(scope, message, payload) {
    const prefix = `[Auth:${scope}]`;
    if (typeof payload === 'undefined') {
      console.warn(prefix, message);
    } else {
      console.warn(prefix, message, payload);
    }
  }

  logError(scope, message, payload) {
    const prefix = `[Auth:${scope}]`;
    if (typeof payload === 'undefined') {
      console.error(prefix, message);
    } else {
      console.error(prefix, message, payload);
    }
  }

  showCatalog() {
    // Скрываем профиль и показываем главную страницу
    const profilePage = document.getElementById('profilePage');
    const mainContent = document.querySelectorAll('.hero, .categories, .features, .cta');

    if (profilePage) {
      profilePage.style.display = 'none';
      this.logDebug('showCatalog', 'Profile page hidden');
    } else {
      this.logWarn('showCatalog', 'Profile page element missing');
    }

    mainContent.forEach(el => el.style.display = 'block');
    this.logInfo('showCatalog', 'Main sections displayed for catalog view');
    window.scrollTo(0, 0);
  }

  showProfile() {
    // Скрываем главную страницу и показываем профиль
    const profilePage = document.getElementById('profilePage');
    const mainContent = document.querySelectorAll('.hero, .categories, .features, .cta');

    mainContent.forEach(el => el.style.display = 'none');
    this.logDebug('showProfile', 'Main sections hidden');

    if (profilePage) {
      profilePage.style.display = 'block';
      this.logInfo('showProfile', 'Profile page displayed');
    } else {
      this.logWarn('showProfile', 'Profile page element missing');
    }

    // Перезагружаем данные профиля
    this.loadUserData();
    window.scrollTo(0, 0);
  }

  showSuccess(message) {
    // Можно добавить toast-уведомление
    this.logInfo('toast', 'Success message', message);
  }

  showError(message) {
    // Можно добавить toast-уведомление
    this.logError('toast', 'Error message', message);
    alert(message);
  }

  async downloadOrder(orderId) {
    this.logInfo('downloadOrder', 'Download requested', orderId);

    try {
      // Получаем детали заказа из PocketBase
      const response = await fetch(
        `${POCKETBASE_URL}/api/collections/orders/records/${orderId}`,
        {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );

      if (!response.ok) {
        throw new Error('Не удалось загрузить данные заказа');
      }

      const order = await response.json();
      this.logDebug('downloadOrder', 'Order data loaded', order);
      this.logDebug('downloadOrder', 'Order.items full structure', JSON.stringify(order.items, null, 2));

      // Проверяем статус заказа
      if (!['completed', 'delivered', 'paid'].includes(order.status)) {
        this.showError('Заказ еще не оплачен или не обработан');
        return;
      }

      // Собираем все account_ids из всех items
      const items = Array.isArray(order.items) ? order.items : [];
      const allAccountIds = items.flatMap(item => item.account_ids || []);

      this.logDebug('downloadOrder', 'Items and accounts', {
        itemsCount: items.length,
        accountIdsCount: allAccountIds.length,
        items: items,
        allAccountIds: allAccountIds
      });

      if (allAccountIds.length === 0) {
        this.showError('В заказе нет привязанных аккаунтов');
        return;
      }

      // Загружаем данные всех аккаунтов из sold_accounts
      // Важно: account_ids в order.items - это ID из коллекции sold_accounts, НЕ из accounts
      const accountPromises = allAccountIds.map(async (soldAccountId) => {
        try {
          // Пробуем загрузить напрямую из sold_accounts по ID записи
          const soldResp = await fetch(
            `${POCKETBASE_URL}/api/collections/sold_accounts/records/${soldAccountId}`,
            {
              method: 'GET',
              headers: { 'Content-Type': 'application/json' },
            }
          );

          if (soldResp.ok) {
            const soldAccount = await soldResp.json();
            this.logDebug('downloadOrder', 'Found sold_account by ID', { soldAccountId });

            // sold_accounts хранит данные аккаунта в поле 'data'
            if (soldAccount.data) {
              return {
                id: soldAccountId,
                data: soldAccount.data
              };
            } else {
              this.logWarn('downloadOrder', 'sold_account exists but no data field', { soldAccountId, soldAccount });
            }
          } else {
            this.logDebug('downloadOrder', 'sold_account not found by ID, trying accounts fallback', { soldAccountId, status: soldResp.status });
          }

          // Fallback: пробуем найти в accounts (для незавершенных заказов)
          const accResp = await fetch(
            `${POCKETBASE_URL}/api/collections/accounts/records/${soldAccountId}`,
            {
              method: 'GET',
              headers: { 'Content-Type': 'application/json' },
            }
          );

          if (accResp.ok) {
            const account = await accResp.json();
            this.logDebug('downloadOrder', 'Found account in accounts collection', { soldAccountId });
            return account;
          } else {
            this.logWarn('downloadOrder', 'Account not found anywhere', { soldAccountId });
          }

          return null;
        } catch (e) {
          this.logError('downloadOrder', 'Failed to load account', { soldAccountId, error: e.message });
          return null;
        }
      });

      const accounts = (await Promise.all(accountPromises)).filter(a => a !== null);

      this.logDebug('downloadOrder', 'Accounts loaded', {
        count: accounts.length,
        accounts: accounts.map(a => ({
          id: a.id,
          data: a.data || a.data,
          hasData: !!a.data
        }))
      });

      if (accounts.length === 0) {
        this.showError('Не удалось загрузить данные аккаунтов');
        return;
      }

      // Группируем товары по категориям (по product_title + type_of_warm + region_for_filter)
      const categorizedItems = new Map();

      items.forEach((item) => {
        const itemAccountIds = item.account_ids || [];
        const itemAccounts = accounts.filter(acc => itemAccountIds.includes(acc.id));

        if (itemAccounts.length > 0) {
          // Создаём ключ категории (полное название товара)
          const categoryKey = this.composeProductDisplay(
            item.product_title || 'Товар',
            item.type_of_warm || '',
            item.region_for_filter || ''
          );

          if (!categorizedItems.has(categoryKey)) {
            categorizedItems.set(categoryKey, []);
          }

          categorizedItems.get(categoryKey).push({
            accounts: itemAccounts,
            item: item
          });
        }
      });

      this.logDebug('downloadOrder', 'Categorized items', {
        categoriesCount: categorizedItems.size,
        categories: Array.from(categorizedItems.keys())
      });

      // Если только одна категория - скачиваем TXT
      if (categorizedItems.size === 1) {
        const [categoryName, categoryData] = Array.from(categorizedItems.entries())[0];
        const accountsText = this.buildAccountsText(categoryName, categoryData);

        if (!accountsText.trim()) {
          this.showError('Нет данных для скачивания');
          return;
        }

        // Создаём безопасное имя файла
        const safeFileName = categoryName.replace(/[^a-zA-Z0-9а-яА-Я\s]/g, '_').replace(/\s+/g, '_');

        // Скачиваем TXT файл
        const blob = new Blob([accountsText], { type: 'text/plain;charset=utf-8' });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `${safeFileName}_order_${order.order_id || order.id}.txt`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);

        this.showSuccess('Файл с аккаунтами загружен');
        this.logInfo('downloadOrder', 'Single TXT file downloaded');

      } else {
        // Несколько категорий - создаём ZIP архив
        this.logInfo('downloadOrder', 'Creating ZIP archive with multiple categories');

        // Подключаем JSZip динамически
        if (typeof JSZip === 'undefined') {
          await this.loadJSZip();
        }

        const zip = new JSZip();

        // Добавляем файл для каждой категории
        categorizedItems.forEach((categoryData, categoryName) => {
          const accountsText = this.buildAccountsText(categoryName, categoryData);
          const safeFileName = categoryName.replace(/[^a-zA-Z0-9а-яА-Я\s]/g, '_').replace(/\s+/g, '_');
          zip.file(`${safeFileName}.txt`, accountsText);
        });

        // Генерируем ZIP
        const zipBlob = await zip.generateAsync({ type: 'blob' });
        const url = window.URL.createObjectURL(zipBlob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `order_${order.order_id || order.id}_accounts.zip`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);

        this.showSuccess(`ZIP архив с ${categorizedItems.size} категориями загружен`);
        this.logInfo('downloadOrder', 'ZIP archive downloaded', { categoriesCount: categorizedItems.size });
      }

    } catch (error) {
      this.logError('downloadOrder', 'Download failed', error);
      this.showError(`Ошибка скачивания: ${error.message}`);
    }
  }

  /**
   * Формирует текст с аккаунтами для категории
   */
  buildAccountsText(categoryName, categoryData) {
    // Создаём заголовок с названием категории
    let text = `${categoryName}\n`;
    text += `${'='.repeat(categoryName.length)}\n\n`;
    text += `ВНИМАНИЕ: Входите в аккаунт только через прокси страны, аккаунт которой вы купили.\n`;
    text += `Формат: логин:пароль:почта\n\n`;

    categoryData.forEach(({ accounts }) => {
      accounts.forEach((acc) => {
        const accountData = acc.data || 'N/A:N/A:N/A';
        text += `${accountData}\n`;
      });
    });

    text += `\n`;
    return text;
  }

  /**
   * Динамическая загрузка библиотеки JSZip
   */
  async loadJSZip() {
    return new Promise((resolve, reject) => {
      if (typeof JSZip !== 'undefined') {
        resolve();
        return;
      }

      const script = document.createElement('script');
      script.src = 'https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js';
      script.onload = () => {
        this.logInfo('loadJSZip', 'JSZip loaded successfully');
        resolve();
      };
      script.onerror = () => {
        this.logError('loadJSZip', 'Failed to load JSZip');
        reject(new Error('Failed to load JSZip library'));
      };
      document.head.appendChild(script);
    });
  }
}

// Создаем глобальный экземпляр менеджера авторизации
const authManager = new AuthManager();
window.authManager = authManager; // Делаем доступным глобально

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
  authManager.logInfo('bootstrap', 'DOM loaded, initializing auth flow');
  authManager.checkAuthToken();
});
