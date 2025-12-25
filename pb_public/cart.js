/**
 * Cart Manager - управление корзиной с резервированием через PocketBase
 * Поддерживает: выбор количества на карточке, резерв через API, освобождение при уменьшении/удалении, таймеры истечения
 */
console.log('%c[cart.js] FILE LOADED', 'color: lime; font-size: 16px; font-weight: bold');

const CART_STORAGE_KEY = 'projectaccs_cart';
const PB_BASE = 'http://127.0.0.1:8090';
const API_BASE = 'http://127.0.0.1:5000';
const SHOP_BOT_URL = 'https://t.me/alexcrypto1422_bot';

// Глобальная функция для перезагрузки каталога (будет определена в index.html)
window.reloadCatalog = window.reloadCatalog || function() {
  console.warn('reloadCatalog not defined yet');
};

class CartManager {
  constructor() {
    console.info('CartManager.constructor — init');
    this.cart = [];
    this.cartId = null;
    this.userId = null;    // ID записи bot_user в PocketBase
    this.telegramId = null; // Telegram user_id
    this.timers = new Map();
    this.isAddingToCart = false;
    this.isClearingCart = false;
    this.isUpdatingQuantity = false;

    this.load();
    this.setupEventListeners();
    this.updateUI();

    // периодически проверяем просроченные резервы
    this.expiryTimer = setInterval(() => this.checkExpiredReservations(), 1000);
  }

  // Форматирование названия товара с дополнительными полями
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

  // Получить ID текущего пользователя из authManager
  getCurrentUserId() {
    // Пробуем получить из authManager (auth.js)
    if (window.authManager && window.authManager.currentUser) {
      console.debug('Got user from authManager:', window.authManager.currentUser.id);
      return window.authManager.currentUser.id;
    }
    // Fallback на localStorage (auth.js сохраняет как 'user_id')
    const savedUserId = localStorage.getItem('user_id');
    if (savedUserId) {
      console.debug('Got user from localStorage:', savedUserId);
      return savedUserId;
    }

    console.warn('No user_id found in authManager or localStorage');
    return null;
  }

  load() {
    try {
      const saved = localStorage.getItem(CART_STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        this.cart = parsed.items || [];
        this.cartId = parsed.cartId || null;
        this.userId = parsed.userId || null;
        this.telegramId = parsed.telegramId || null;
        console.debug('Cart loaded from storage', { items: this.cart.length, cartId: this.cartId, userId: this.userId });
      }
    } catch (e) {
      console.error('Failed to load cart:', e);
      this.cart = [];
    }
  }

  save() {
    console.log('%c[save] START', 'color: magenta; font-weight: bold', { itemsCount: this.cart.length, cartId: this.cartId });

    try {
      const dataToSave = {
        items: this.cart,
        cartId: this.cartId,
        userId: this.userId,
        telegramId: this.telegramId
      };

      console.log('[save] Saving to localStorage:', dataToSave);
      localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(dataToSave));
      console.log('[save] ✓ Saved to localStorage');

      // Синхронизируем cart_payload в PocketBase
      console.log('[save] Calling syncCartPayload()...');
      this.syncCartPayload();
    } catch (e) {
      console.error('%c[save] ✗ Failed to save cart', 'color: red; font-weight: bold', e);
    }
  }

  async syncCartPayload() {
    console.log('%c[syncCartPayload] START', 'color: cyan; font-weight: bold');

    if (!this.cartId) {
      console.warn('[syncCartPayload] No cartId, skipping sync');
      return;
    }

    try {
      const payload = {
        items: this.cart.map(item => ({
          productId: item.productId,
          productTitle: item.productTitle,
          productPrice: item.productPrice,
          quantity: item.quantity,
          accountIds: item.accountIds || [],
          typeOfWarm: item.typeOfWarm || '',
          regionForFilter: item.regionForFilter || ''
        }))
      };

      console.log('[syncCartPayload] Payload to sync:', payload);
      console.log('[syncCartPayload] Current cart state:', this.cart);
      console.log('[syncCartPayload] Cart ID:', this.cartId);

      const url = `${PB_BASE}/api/collections/carts/records/${this.cartId}`;
      const body = { cart_payload: JSON.stringify(payload) };

      console.log('[syncCartPayload] PATCH URL:', url);
      console.log('[syncCartPayload] PATCH body:', body);

      const resp = await fetch(url, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });

      console.log('[syncCartPayload] Response status:', resp.status, resp.statusText);

      if (!resp.ok) {
        const errorText = await resp.text();
        console.error('[syncCartPayload] Response not OK:', errorText);
        throw new Error(`PATCH failed: ${resp.status} ${errorText}`);
      }

      const responseData = await resp.json();
      console.log('%c[syncCartPayload] ✓ Cart payload synced to PocketBase', 'color: lime; font-weight: bold', responseData);
    } catch (e) {
      console.error('%c[syncCartPayload] ✗ Failed to sync cart payload', 'color: red; font-weight: bold', e);
    }
  }

  setupEventListeners() {
    const cartBtn = document.getElementById('cartBtn');
    const cartPage = document.getElementById('cartPage');
    const cartBackBtn = document.getElementById('cartBackBtn');
    const emptyCartBackBtn = document.getElementById('emptyCartBackBtn');
    const clearCartBtn = document.getElementById('clearCartBtn');

    // Секции, которые нужно скрывать при открытии корзины
    const mainSections = document.querySelectorAll('.hero, .categories, .features, .cta');

    if (!cartBtn) console.warn('cartBtn not found on page');
    if (!cartPage) console.warn('cartPage not found on page');

    // Открытие корзины — скрыть каталог, показать корзину
    if (cartBtn) {
      cartBtn.addEventListener('click', () => {
        console.debug('cartBtn click — opening cart page', { cartId: this.cartId, itemsCount: this.getTotalItems() });
        mainSections.forEach(s => s.style.display = 'none');
        document.getElementById('profilePage')?.style && (document.getElementById('profilePage').style.display = 'none');
        cartPage.style.display = 'block';
        this.renderCart();
        window.scrollTo({ top: 0, behavior: 'smooth' });
      });
    }

    // Назад к каталогу
    const goBackToCatalog = () => {
      cartPage.style.display = 'none';
      mainSections.forEach(s => s.style.display = '');
      window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    if (cartBackBtn) cartBackBtn.addEventListener('click', goBackToCatalog);
    if (emptyCartBackBtn) emptyCartBackBtn.addEventListener('click', goBackToCatalog);
    if (clearCartBtn) {
      clearCartBtn.addEventListener('click', () => {
        // Блокируем кнопку если уже идёт очистка
        if (this.isClearingCart) {
          console.warn('[clearCartBtn] Already clearing cart, ignoring click');
          return;
        }

        // Визуально блокируем кнопку
        clearCartBtn.disabled = true;
        clearCartBtn.style.opacity = '0.5';

        this.clearCart()
          .finally(() => {
            // Разблокируем кнопку после завершения
            clearCartBtn.disabled = false;
            clearCartBtn.style.opacity = '';
          });
      });
    }

    // Делегирование событий для карточек: -, +, ввод числа и добавление в корзину
    document.addEventListener('click', (e) => {
      const dec = e.target.closest('.product-decrease');
      const inc = e.target.closest('.product-increase');
      const addBtn = e.target.closest('.add-to-cart');

      if (dec) {
        const pid = dec.dataset.productId;
        const input = document.querySelector(`.product-qty-input[data-product-id='${pid}']`);
        if (!input) return;
        let val = parseInt(input.value || '1');
        val = Math.max(1, val - 1);
        input.value = val;
        return;
      }

      if (inc) {
        const pid = inc.dataset.productId;
        const input = document.querySelector(`.product-qty-input[data-product-id='${pid}']`);
        if (!input) return;
        const max = parseInt(input.max || '999') || 999;
        let val = parseInt(input.value || '1');
        val = Math.min(max, val + 1);
        input.value = val;
        return;
      }

      if (addBtn) {
        // Блокируем кнопку если уже идёт добавление
        if (this.isAddingToCart) {
          console.warn('[click handler] Already adding to cart, ignoring click');
          return;
        }

        const btn = addBtn;
        const productId = btn.dataset.productId;
        const productTitle = btn.dataset.productTitle;
        const productPrice = parseFloat(btn.dataset.productPrice || '0');
        const typeOfWarm = btn.dataset.typeOfWarm || '';
        const regionForFilter = btn.dataset.regionForFilter || '';

        console.log('%c[click handler] ═══ BUTTON CLICKED ═══', 'color: yellow; font-size: 14px; font-weight: bold');
        console.log('[click handler] Product ID:', productId);
        console.log('[click handler] Product Title:', productTitle);

        // Ищем input через productId, а не через parentElement (т.к. после reloadCatalog структура обновляется)
        const input = document.querySelector(`.product-qty-input[data-product-id='${productId}']`);
        console.log('[click handler] Found input:', input);
        console.log('[click handler] Input.max attribute:', input?.getAttribute('max'));
        console.log('[click handler] Input.max property:', input?.max);
        console.log('[click handler] Input.value:', input?.value);

        // ВАЖНО: Читаем max из инпута В МОМЕНТ КЛИКА, после возможной перезагрузки каталога
        const maxQuantity = input ? parseInt(input.getAttribute('max') || '999') : 999;
        const quantity = input ? Math.max(1, Math.min(parseInt(input.value || '1'), maxQuantity)) : 1;

        // Проверяем есть ли этот товар уже в корзине
        const existingInCart = this.cart.find(i => i.productId === productId);
        console.log('[click handler] Existing in cart:', existingInCart ? {
          quantity: existingInCart.quantity,
          maxQuantity: existingInCart.maxQuantity,
          accountIds: existingInCart.accountIds?.length || 0
        } : 'NO');

        console.log('%c[click handler] CALCULATED VALUES:', 'color: cyan; font-weight: bold');
        console.log('[click handler] maxQuantity (from catalog):', maxQuantity);
        console.log('[click handler] quantity (to add):', quantity);
        console.log('[click handler] cart state:', this.cart.map(i => ({
          id: i.productId,
          title: i.productTitle,
          qty: i.quantity,
          max: i.maxQuantity
        })));

        console.debug('Add to cart clicked', { productId, productTitle, quantity, maxQuantity, cartId: this.cartId, inputMax: input?.max });

        // Визуально блокируем кнопку
        btn.disabled = true;
        btn.style.opacity = '0.5';
        btn.style.cursor = 'not-allowed';

        this.addToCart(productId, productTitle, productPrice, quantity, maxQuantity, typeOfWarm, regionForFilter)
          .catch(err => {
            // addToCart already logs and shows notifications, but avoid unhandled rejection
            console.error('addToCart failed', err);
          })
          .finally(() => {
            // Разблокируем кнопку после завершения
            btn.disabled = false;
            btn.style.opacity = '';
            btn.style.cursor = '';
          });
      }
    });

    // ручной ввод количества на карточке — нормализовать значение
    document.addEventListener('input', (e) => {
      const ip = e.target.closest && e.target.closest('.product-qty-input');
      if (!ip) return;
      let val = parseInt(ip.value || '1');
      const min = parseInt(ip.min || '1') || 1;
      const max = parseInt(ip.max || '999') || 999;
      if (isNaN(val) || val < min) val = min;
      if (val > max) val = max;
      ip.value = val;
    });
  }

  async ensureCartRecord() {
    const currentUserId = this.getCurrentUserId();

    // Если есть cartId, но userId не совпадает с текущим пользователем — сбросить корзину
    if (this.cartId && currentUserId && this.userId !== currentUserId) {
      console.warn('Cart user mismatch, creating new cart', { stored: this.userId, current: currentUserId });
      this.cartId = null;
      this.cart = [];
    }

    // Если есть cartId, но userId пустой, а пользователь авторизован — создать новую корзину
    if (this.cartId && !this.userId && currentUserId) {
      console.warn('Cart has no user_bot but user is logged in, creating new cart');
      this.cartId = null;
      this.cart = [];
    }

    if (this.cartId) return this.cartId;
    console.debug('No valid cartId present, creating cart record...');
    return await this.createCartRecord();
  }

  // Постить запрос на резерв N аккаунтов для продукта
  async addToCart(productId, productTitle, productPrice, quantity = 1, maxQuantity = 999, typeOfWarm = '', regionForFilter = '') {
    if (this.isAddingToCart) {
      console.warn('[addToCart] Already adding to cart, skipping duplicate call');
      return;
    }

    this.isAddingToCart = true;
    console.log('%c[addToCart] START', 'color: yellow; font-weight: bold', { productId, productTitle, quantity, maxQuantity, typeOfWarm, regionForFilter });

    try {
      await this.ensureCartRecord();
      console.log('[addToCart] Cart record ensured:', this.cartId);

      // Получаем user_id для резервирования
      const userId = this.getCurrentUserId();
      console.log('[addToCart] User ID:', userId);

      console.debug('reserve request', {
        endpoint: `${API_BASE}/api/cart/reserve`,
        cart_id: this.cartId,
        product_id: productId,
        quantity,
        user_id: userId,
        maxQuantity
      });

      const resp = await fetch(`${API_BASE}/api/cart/reserve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          cart_id: this.cartId,
          product_id: productId,
          quantity,
          user_id: userId  // передаём user_id на бэкенд
        })
      });

      if (!resp.ok) {
        // try to log body for debugging
        const bodyText = await resp.text().catch(() => '');
        console.error('Reserve endpoint returned not-ok', resp.status, bodyText);
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.error || err.message || `Ошибка резервирования (${resp.status})`);
      }

      const data = await resp.json();
      console.log('%c[addToCart] Reserve response received', 'color: lime', data);

      let existing = this.cart.find(i => i.productId === productId);
      console.log('%c[addToCart] ═══ BEFORE UPDATE ═══', 'color: magenta; font-size: 14px; font-weight: bold');
      console.log('[addToCart] Existing item in cart:', existing ? {
        productId: existing.productId,
        quantity: existing.quantity,
        maxQuantity: existing.maxQuantity,
        accountIds: existing.accountIds?.length || 0
      } : 'NONE');
      console.log('[addToCart] maxQuantity from click handler:', maxQuantity);
      console.log('[addToCart] Quantity to add (from API response):', data.quantity);

      if (existing) {
        const oldQty = existing.quantity;
        const oldMaxQty = existing.maxQuantity;

        existing.quantity = (existing.quantity || 0) + data.quantity;
        existing.reservation_id = data.reservation_id;
        existing.expiresAt = data.expires_at;
        existing.accountIds = (existing.accountIds || []).concat(data.reserved_account_ids || []);

        // ВАЖНО: maxQuantity должен быть ТЕКУЩИМ остатком + то что УЖЕ в корзине
        // Если было в корзине 5, а доступно в каталоге ещё 10, то maxQuantity = 15
        existing.maxQuantity = maxQuantity + oldQty;

        console.log('%c[addToCart] ═══ AFTER UPDATE (EXISTING) ═══', 'color: lime; font-size: 14px; font-weight: bold');
        console.log('[addToCart] OLD values:', {
          oldQty,
          oldMaxQty
        });
        console.log('[addToCart] NEW values:', {
          newQty: existing.quantity,
          newMaxQty: existing.maxQuantity,
          calculation: `${maxQuantity} (catalog) + ${oldQty} (old in cart) = ${existing.maxQuantity}`,
          accountIdsCount: existing.accountIds.length
        });
      } else {
        const newItem = {
          productId, productTitle, productPrice,
          quantity: data.quantity,
          reservation_id: data.reservation_id,
          expiresAt: data.expires_at,
          accountIds: data.reserved_account_ids || [],
          maxQuantity, // сохраняем максимальное количество из карточки
          typeOfWarm,
          regionForFilter
        };
        this.cart.push(newItem);

        console.log('%c[addToCart] ═══ AFTER UPDATE (NEW ITEM) ═══', 'color: lime; font-size: 14px; font-weight: bold');
        console.log('[addToCart] Added new item to cart:', {
          productId: newItem.productId,
          quantity: newItem.quantity,
          maxQuantity: newItem.maxQuantity,
          accountIdsCount: newItem.accountIds.length
        });
      }

      console.log('%c[addToCart] ═══ FULL CART STATE ═══', 'color: orange; font-size: 14px; font-weight: bold');
      console.log('[addToCart] Cart items:', this.cart.map(i => ({
        id: i.productId,
        title: i.productTitle,
        qty: i.quantity,
        max: i.maxQuantity,
        accounts: i.accountIds?.length || 0
      })));

      console.log('[addToCart] Calling save()...');
      this.save();
      console.log('[addToCart] Calling updateUI()...');
      this.updateUI();
      this.startItemTimer(this.cart.find(i => i.productId === productId));
      this.showNotification(`✓ ${productTitle} добавлен в корзину (x${quantity})`);

      // Мгновенно уменьшаем счётчик в каталоге
      this.updateProductStockBadge(productId, -quantity);

      // Ждём подтверждения, что изменения записаны в базу
      console.log('%c[addToCart] Waiting for database changes to persist...', 'color: orange; font-weight: bold');

      // Делаем запрос для проверки, что аккаунты действительно зарезервированы
      const checkReservation = async () => {
        try {
          // Проверяем конкретные аккаунты из ответа API
          if (data.reserved_account_ids && data.reserved_account_ids.length > 0) {
            const accountChecks = data.reserved_account_ids.map(async (accountId) => {
              const response = await fetch(`${PB_BASE}/api/collections/accounts/records/${accountId}`, {
                method: 'GET',
                headers: {
                  'Cache-Control': 'no-cache, no-store, must-revalidate',
                  'Pragma': 'no-cache',
                  'Expires': '0'
                }
              });
              const account = await response.json();
              return account.reservation_id === data.reservation_id;
            });

            const results = await Promise.all(accountChecks);
            return results.every(result => result === true);
          }

          // Fallback: проверка по reservation_id
          const checkResponse = await fetch(`${PB_BASE}/api/collections/accounts/records?filter=reservation_id="${data.reservation_id}"&perPage=1`, {
            method: 'GET',
            headers: {
              'Cache-Control': 'no-cache, no-store, must-revalidate',
              'Pragma': 'no-cache',
              'Expires': '0'
            }
          });
          const checkData = await checkResponse.json();
          return checkData.items.length > 0;
        } catch (e) {
          console.warn('[addToCart] Failed to check reservation:', e);
          return false;
        }
      };

      // Ждём подтверждения резервирования
      let attempts = 0;
      const maxAttempts = 10;
      while (attempts < maxAttempts) {
        const isReserved = await checkReservation();
        if (isReserved) {
          console.log('%c[addToCart] ✓ Reservation confirmed in database', 'color: lime; font-weight: bold');
          break;
        }
        attempts++;
        console.log(`[addToCart] Waiting for reservation to be written... attempt ${attempts}/${maxAttempts}`);
        await new Promise(resolve => setTimeout(resolve, 100));
      }

      if (attempts >= maxAttempts) {
        console.warn('[addToCart] ⚠️ Reservation not confirmed, but proceeding with catalog reload');
      }

      setTimeout(() => {
        console.log('%c[addToCart setTimeout] Executing reload callback', 'color: orange; font-weight: bold');

        const reloadWithRetry = (attempt = 1, maxAttempts = 3) => {
          console.log(`[reloadWithRetry] Attempt ${attempt}/${maxAttempts}`);

          if (window.reloadCatalog && typeof window.reloadCatalog === 'function') {
            console.log('%c[setTimeout] Calling window.reloadCatalog()...', 'color: lime; font-weight: bold');
            try {
              window.reloadCatalog();
              console.log('%c[setTimeout] window.reloadCatalog() completed', 'color: lime; font-weight: bold');

              // Если это не последняя попытка, планируем следующую через 200ms
              if (attempt < maxAttempts) {
                setTimeout(() => reloadWithRetry(attempt + 1, maxAttempts), 200);
              }
            } catch (err) {
              console.error('[setTimeout] Error calling reloadCatalog:', err);
            }
          } else {
            console.error('%c[setTimeout] reloadCatalog is NOT a function!', 'color: red; font-weight: bold', { type: typeof window.reloadCatalog, value: window.reloadCatalog });
          }
        };

        reloadWithRetry();
      }, 1000);

      console.log('[addToCart] END, returning data');
      return data;
    } catch (e) {
      console.error('reserve error', e, { endpoint: `${API_BASE}/api/cart/reserve`, cart_id: this.cartId, product_id: productId, quantity });
      this.showNotification(`✗ Ошибка резервирования: ${e.message}`, 'error');
      throw e;
    } finally {
      this.isAddingToCart = false;
    }
  }

  // Изменить количество в корзине — при увеличении делаем новый резерв, при уменьшении освобождаем конкретные аккаунты
  async updateQuantity(productId, newQuantity) {
    if (this.isUpdatingQuantity) {
      console.warn('[updateQuantity] Already updating quantity, skipping duplicate call');
      return;
    }

    this.isUpdatingQuantity = true;
    const item = this.cart.find(i => i.productId === productId);
    if (!item) {
      this.isUpdatingQuantity = false;
      return;
    }

    const oldQuantity = item.quantity || 0;

    // Ограничиваем максимумом
    const maxQty = item.maxQuantity || 999;
    if (newQuantity > maxQty) {
      this.showNotification(`Максимум ${maxQty} шт. в наличии`, 'warning');
      newQuantity = maxQty;
    }

    if (newQuantity <= 0) return await this.removeFromCart(productId);

    if (newQuantity > (item.quantity || 0)) {
      const diff = newQuantity - (item.quantity || 0);
      // reserve diff
      try {
        const resp = await fetch(`${API_BASE}/api/cart/reserve`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ cart_id: this.cartId, product_id: productId, quantity: diff })
        });
        if (!resp.ok) throw new Error('reserve failed');
        const r = await resp.json();
        item.quantity = newQuantity;
        item.accountIds = (item.accountIds || []).concat(r.reserved_account_ids || []);
        item.expiresAt = r.expires_at;
        item.reservation_id = r.reservation_id;

        // Уменьшаем счётчик в каталоге
        this.updateProductStockBadge(productId, -diff);
      } catch (e) {
        this.showNotification('✗ Не удалось добавить количество', 'error');
        console.error(e);
        return;
      }
    } else if (newQuantity < (item.quantity || 0)) {
      const diff = oldQuantity - newQuantity;
      const toRelease = item.accountIds ? item.accountIds.slice(newQuantity) : [];
      if (toRelease.length) {
        try {
          await fetch(`${API_BASE}/api/cart/release-accounts`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ account_ids: toRelease }) });
        } catch (e) { console.warn('release accounts failed', e); }
        item.accountIds = (item.accountIds || []).slice(0, newQuantity);
      }
      item.quantity = newQuantity;

      // Увеличиваем счётчик в каталоге
      this.updateProductStockBadge(productId, diff);
    }

    this.save();
    this.updateUI();
    this.renderCart();
    this.isUpdatingQuantity = false;
  }

  async removeFromCart(productId) {
    const item = this.cart.find(i => i.productId === productId);
    if (!item) return;

    const releasedQuantity = item.quantity || 0;

    // release reserved accounts if there are any
    if (item.accountIds && item.accountIds.length) {
      try {
        await fetch(`${API_BASE}/api/cart/release-accounts`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ account_ids: item.accountIds }) });
        console.log(`Released ${item.accountIds.length} accounts for product ${productId}`);
      } catch (e) { console.warn('release on remove failed', e); }
    }

    this.cart = this.cart.filter(i => i.productId !== productId);
    this.save();
    this.updateUI();
    this.renderCart();

    // Мгновенно увеличиваем счётчик в каталоге
    this.updateProductStockBadge(productId, releasedQuantity);

    // Обновляем каталог — освобождённые аккаунты снова доступны
    setTimeout(() => {
      if (window.reloadCatalog && typeof window.reloadCatalog === 'function') {
        console.debug('Reloading catalog after remove...');
        window.reloadCatalog();
      }
    }, 300);
  }

  async clearCart() {
    if (this.isClearingCart) {
      console.warn('[clearCart] Already clearing cart, skipping duplicate call');
      return;
    }

    this.isClearingCart = true;
    console.log('%c[clearCart] START', 'color: orange; font-weight: bold');

    try {
      // Освобождаем зарезервированные аккаунты
      for (const item of this.cart) {
      if (item.accountIds && item.accountIds.length) {
        try {
          await fetch(`${API_BASE}/api/cart/release-accounts`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ account_ids: item.accountIds }) });
          console.log(`Released ${item.accountIds.length} accounts for product ${item.productId}`);
        } catch (e) { console.warn('release while clearing failed', e); }
      }
    }

    // Удаляем ВСЕ cart_items для текущего пользователя (через все его корзины)
    const userId = this.getCurrentUserId();
    if (userId) {
      try {
        const pb = new PocketBase(API_BASE);

        // Сначала получаем все корзины этого пользователя
        const userCarts = await pb.collection('carts').getFullList({
          filter: `user_bot="${userId}"`
        });

        console.log(`Found ${userCarts.length} carts for user ${userId}`);

        // Для каждой корзины удаляем все cart_items
        let totalDeleted = 0;
        for (const cart of userCarts) {
          const cartItems = await pb.collection('cart_items').getFullList({
            filter: `cart="${cart.id}"`
          });

          for (const ci of cartItems) {
            await pb.collection('cart_items').delete(ci.id);
            console.log(`Deleted cart_item ${ci.id} from cart ${cart.id}`);
            totalDeleted++;
          }
        }

        console.log(`✅ Cleared ${totalDeleted} cart_items for user ${userId} (across ${userCarts.length} carts)`);
      } catch (e) {
        console.warn('Failed to clear cart_items:', e);
      }
    }

      // Запоминаем товары для восстановления счётчиков
      const itemsToRestore = this.cart.map(item => ({
        productId: item.productId,
        quantity: item.quantity || 0
      }));

      this.cart = [];
      this.save();
      this.updateUI();
      this.renderCart();

      // Мгновенно увеличиваем счётчики всех товаров
      itemsToRestore.forEach(({ productId, quantity }) => {
        this.updateProductStockBadge(productId, quantity);
      });

      // Обновляем каталог — освобождённые аккаунты снова доступны
      setTimeout(() => {
        if (window.reloadCatalog && typeof window.reloadCatalog === 'function') {
          console.debug('Reloading catalog after clear...');
          window.reloadCatalog();
        }
      }, 300);

      console.log('%c[clearCart] END', 'color: lime; font-weight: bold');
    } finally {
      this.isClearingCart = false;
    }
  }

  getTotalItems() { return this.cart.reduce((sum, i) => sum + (i.quantity || 0), 0); }
  getTotalPrice() { return this.cart.reduce((sum, i) => sum + ((i.productPrice || 0) * (i.quantity || 0)), 0); }

  updateUI() {
    const cartCount = document.getElementById('cartCount');
    if (cartCount) {
      const total = this.getTotalItems();
      cartCount.textContent = total;
      cartCount.style.display = total > 0 ? 'flex' : 'none';
    }
  }

  renderCart() {
    const body = document.getElementById('cartPageBody');
    const footer = document.getElementById('cartPageFooter');
    const totalEl = document.getElementById('cartTotalAmount');
    const countEl = document.getElementById('cartItemsCount');

    if (!body) return;

    if (!this.cart.length) {
      body.innerHTML = `
        <div class="empty-cart">
          <i class="lucide-shopping-cart"></i>
          <p>Корзина пуста</p>
          <button class="btn-outline" id="emptyCartBackBtn">Перейти в каталог</button>
        </div>`;
      if (footer) footer.style.display = 'none';
      // Re-attach event listener for dynamically created button
      const btn = document.getElementById('emptyCartBackBtn');
      if (btn) {
        btn.addEventListener('click', () => {
          document.getElementById('cartPage').style.display = 'none';
          document.querySelectorAll('.hero, .categories, .features, .cta').forEach(s => s.style.display = '');
        });
      }
      return;
    }

    body.innerHTML = `
      <div class="cart-items-list">
        ${this.cart.map(item => {
          // Получаем максимум из сохранённого значения или 999 как fallback
          const maxQty = item.maxQuantity || 999;

          // Диагностика: проверяем наличие метаданных
          if (!item.typeOfWarm || !item.regionForFilter) {
            console.warn('[renderCart] Cart item missing metadata:', {
              productId: item.productId,
              productTitle: item.productTitle,
              hasTypeOfWarm: Boolean(item.typeOfWarm),
              hasRegionForFilter: Boolean(item.regionForFilter),
              itemSnapshot: item
            });
          }

          return `
          <div class="cart-item" data-product-id="${item.productId}">
            <div class="cart-item-info">
              <h4>${this.composeProductDisplay(item.productTitle, item.typeOfWarm, item.regionForFilter)}</h4>
              <p class="cart-item-price">${item.productPrice} USDT за шт.</p>
              <p class="cart-item-timer">
                <i class="lucide-clock"></i> Резерв истекает: <span data-timer-product="${item.productId}">--:--</span>
              </p>
            </div>
            <div class="quantity-selector">
              <button class="qty-btn" onclick="cartManager.updateQuantity('${item.productId}', ${Math.max(1, item.quantity - 1)})" ${item.quantity <= 1 ? 'disabled' : ''}>−</button>
              <input class="qty-input" type="number" value="${item.quantity}" min="1" max="${maxQty}"
                     onchange="cartManager.updateQuantity('${item.productId}', Math.min(parseInt(this.value)||1, ${maxQty}))" />
              <button class="qty-btn" onclick="cartManager.updateQuantity('${item.productId}', ${item.quantity + 1})" ${item.quantity >= maxQty ? 'disabled' : ''}>+</button>
            </div>
            <div class="cart-item-total">
              <span class="item-total-price">${(item.productPrice * item.quantity).toFixed(2)} USDT</span>
              <button class="remove-btn" onclick="cartManager.removeFromCart('${item.productId}')">
                <i class="lucide-trash-2"></i>
              </button>
            </div>
          </div>
        `}).join('')}
      </div>`;

    if (footer) footer.style.display = 'flex';
    if (totalEl) totalEl.textContent = `${this.getTotalPrice().toFixed(2)} USDT`;
    if (countEl) countEl.textContent = this.getTotalItems();

    // старт таймеров подсчёта на каждый item
    for (const it of this.cart) if (it.expiresAt) this.startItemTimer(it);

    if (typeof lucide !== 'undefined') lucide.createIcons();
  }

  showNotification(msg, type = 'success') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = msg;
    notification.style.cssText = `position: fixed; top: 80px; right: 20px; background: ${type === 'error' ? '#ef4444' : type === 'warning' ? '#f59e0b' : '#10b981'}; color: white; padding: 10px 16px; border-radius: 8px; z-index: 9999;`;
    document.body.appendChild(notification);
    setTimeout(() => { notification.style.opacity = '0'; setTimeout(() => notification.remove(), 300); }, 3000);
  }

  /**
   * Обновляет счётчик товара в каталоге
   * @param {string} productId - ID продукта
   * @param {number} deltaQuantity - изменение количества (отрицательное для уменьшения)
   */
  updateProductStockBadge(productId, deltaQuantity) {
    try {
      const stockBadge = document.querySelector(`[data-stock-badge="${productId}"]`);
      if (!stockBadge) {
        console.debug('[updateProductStockBadge] Badge not found for:', productId);
        return;
      }

      const currentText = stockBadge.textContent.trim();
      const match = currentText.match(/^(\d+)\s*шт\.$/);

      if (!match) {
        console.debug('[updateProductStockBadge] Could not parse:', currentText);
        return;
      }

      const currentStock = parseInt(match[1]);
      const newStock = Math.max(0, currentStock + deltaQuantity);

      console.log(`[updateProductStockBadge] ${productId}: ${currentStock} → ${newStock} (Δ${deltaQuantity})`);

      if (newStock > 0) {
        stockBadge.textContent = `${newStock} шт.`;
        stockBadge.classList.remove('out-of-stock');
        stockBadge.classList.add('in-stock');

        const productCard = stockBadge.closest('.product-card');
        if (productCard) {
          const addBtn = productCard.querySelector('.add-to-cart');
          const qtyInput = productCard.querySelector('.product-qty-input');
          const qtyBtns = productCard.querySelectorAll('.qty-btn');

          if (addBtn) addBtn.disabled = false;
          if (qtyInput) {
            qtyInput.disabled = false;
            qtyInput.max = newStock;
            qtyInput.setAttribute('max', newStock);
          }
          qtyBtns.forEach(btn => btn.disabled = false);
        }
      } else {
        stockBadge.textContent = 'Нет в наличии';
        stockBadge.classList.remove('in-stock');
        stockBadge.classList.add('out-of-stock');

        const productCard = stockBadge.closest('.product-card');
        if (productCard) {
          const addBtn = productCard.querySelector('.add-to-cart');
          const qtyInput = productCard.querySelector('.product-qty-input');
          const qtyBtns = productCard.querySelectorAll('.qty-btn');

          if (addBtn) addBtn.disabled = true;
          if (qtyInput) {
            qtyInput.disabled = true;
            qtyInput.max = 0;
          }
          qtyBtns.forEach(btn => btn.disabled = true);
        }
      }

      const qtyInput = document.querySelector(`.product-qty-input[data-product-id='${productId}']`);
      if (qtyInput) {
        qtyInput.max = newStock;
        qtyInput.setAttribute('max', newStock);
        if (parseInt(qtyInput.value) > newStock) {
          qtyInput.value = Math.max(1, newStock);
        }
      }

    } catch (error) {
      console.error('[updateProductStockBadge] Error:', error);
    }
  }

  async checkout() {
    if (!this.cart.length) { this.showNotification('Корзина пуста', 'warning'); return; }

    // Показываем индикатор загрузки
    this.showNotification('Создание заказа...', 'info');

    try {
      // Получаем user_id для создания заказа
      const userId = this.getCurrentUserId();
      if (!userId) {
        this.showNotification('Необходимо авторизоваться', 'error');
        return;
      }

      // Собираем данные корзины
      const cartData = {
        cart_id: this.cartId,
        user_id: userId,
        items: this.cart.map(item => ({
          product_id: item.productId,
          product_title: item.productTitle,
          product_price: item.productPrice,
          quantity: item.quantity,
          account_ids: item.accountIds || [],
          type_of_warm: item.typeOfWarm || '',
          region_for_filter: item.regionForFilter || ''
        })),
        total_amount: this.getTotalPrice()
      };

      console.log('Отправка данных заказа:', cartData);

      // Отправляем запрос на создание заказа и платежа
      const response = await fetch(`${API_BASE}/api/orders/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cartData)
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Неизвестная ошибка' }));
        throw new Error(errorData.error || `Ошибка сервера: ${response.status}`);
      }

      const orderData = await response.json();
      console.log('Заказ создан:', orderData);

      const orderId = orderData.order_id;

      // Сохраняем информацию о заказе в localStorage для отслеживания
      localStorage.setItem(`order_${orderId}`, JSON.stringify({
        order_id: orderId,
        cart_data: cartData,
        created_at: new Date().toISOString()
      }));

      // Запускаем поллинг статуса платежа
      this.startPaymentPolling(orderId);

      // Очищаем корзину после успешного создания заказа
      this.cart = [];
      this.save();
      this.updateUI();

      // Закрываем страницу корзины и возвращаемся в каталог
      const cartPage = document.getElementById('cartPage');
      const mainSections = document.querySelectorAll('.hero, .categories, .features, .cta');
      if (cartPage) cartPage.style.display = 'none';
      mainSections.forEach(s => s.style.display = '');

      if (orderData.payment_url) {
        // Старый сценарий (если backend вернул прямую ссылку на оплату)
        this.showPaymentModal(orderData);
      } else {
        // Новый сценарий — бот отправит ссылку
        this.showBotPaymentInstructions(orderData);
      }

    } catch (error) {
      console.error('Ошибка при создании заказа:', error);
      this.showNotification(`Ошибка создания заказа: ${error.message}`, 'error');
    }
  }

  showPaymentModal(orderData) {
    // Создаем модальное окно для оплаты
    const modal = document.createElement('div');
    modal.className = 'payment-modal-overlay';
    modal.innerHTML = `
      <div class="payment-modal">
        <div class="payment-modal-header">
          <h3>Оплата заказа #${orderData.order_id}</h3>
          <button class="payment-modal-close">&times;</button>
        </div>
        <div class="payment-modal-body">
          <div class="payment-info">
            <div class="payment-amount">
              <span class="label">Сумма к оплате:</span>
              <span class="amount">${orderData.amount} ${orderData.currency}</span>
            </div>
            <div class="payment-description">
              <span class="label">Описание:</span>
              <span class="description">${orderData.description}</span>
            </div>
          </div>
          <div class="payment-actions">
            <a href="${orderData.payment_url}" target="_blank" class="btn-payment">
              <i class="lucide-credit-card"></i> Оплатить через Crypto Bot
            </a>
            <button class="btn-secondary" id="copyPaymentLink">
              <i class="lucide-copy"></i> Скопировать ссылку
            </button>
          </div>
          <div class="payment-notice">
            <i class="lucide-info"></i>
            <p>После оплаты товары будут автоматически доставлены в Telegram бот</p>
          </div>
        </div>
      </div>
    `;

    document.body.appendChild(modal);

    // Обработчики событий
    modal.querySelector('.payment-modal-close').addEventListener('click', () => {
      modal.remove();
    });

    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        modal.remove();
      }
    });
    // Копирование ссылки
    modal.querySelector('#copyPaymentLink').addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(orderData.payment_url);
        this.showNotification('Ссылка скопирована', 'success');
      } catch (err) {
        // Fallback для старых браузеров
        const textArea = document.createElement('textarea');
        textArea.value = orderData.payment_url;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
        this.showNotification('Ссылка скопирована', 'success');
      }
    });
  }

  showBotPaymentInstructions(orderData) {
    // Удаляем все предыдущие модалки оплаты перед показом новой
    document.querySelectorAll('.payment-modal-overlay').forEach(oldModal => {
      oldModal.remove();
      console.debug('Removed old payment modal');
    });

    console.log('✓ Showing payment instructions for order:', orderData.order_id);

    const modal = document.createElement('div');
    modal.className = 'payment-modal-overlay';
    modal.innerHTML = `
      <div class="payment-modal">
        <div class="payment-modal-header">
          <h3>Заказ #${orderData.order_id}</h3>
          <button class="payment-modal-close">&times;</button>
        </div>
        <div class="payment-modal-body">
          <div class="payment-info">
            <p style="font-size: 16px; font-weight: 600; margin-bottom: 16px; color: #1f2937;">
              ✅ Заказ создан! Подтвердите покупку в Telegram-боте
            </p>
            <div class="payment-amount">
              <span class="label">Сумма к оплате:</span>
              <span class="amount">${orderData.amount} ${orderData.currency}</span>
            </div>
          </div>
          <div class="payment-actions">
            <a href="${SHOP_BOT_URL}" target="_blank" class="btn-payment">
              <i class="lucide-send"></i> Открыть Telegram-бота для оплаты
            </a>
          </div>
          <div class="payment-notice">
            <i class="lucide-info"></i>
            <p><strong>Откройте бот</strong> — ссылка на оплату уже отправлена в Telegram</p>
            <p>После оплаты бот автоматически отправит TXT с аккаунтами</p>
          </div>
        </div>
      </div>
    `;

    // ВАЖНО: Добавляем модалку напрямую в body, а не в какой-то контейнер
    document.body.appendChild(modal);

    const closeBtn = modal.querySelector('.payment-modal-close');
    closeBtn.addEventListener('click', () => {
      console.log('Modal closed by user');
      modal.remove();
    });

    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        console.log('Modal closed by overlay click');
        modal.remove();
      }
    });

    // Инициализируем иконки Lucide после добавления модалки
    if (typeof lucide !== 'undefined') {
      lucide.createIcons();
    }

    console.log('✓ Payment modal displayed');
  }

  /**
   * Запускает периодическую проверку статуса платежа
   * @param {string} orderId - ID заказа
   */
  startPaymentPolling(orderId) {
    const CHECK_INTERVAL = 10000; // 10 секунд
    const MAX_CHECKS = 36; // 6 минут максимум (36 × 10 сек)
    const RESERVATION_TIMEOUT = 62000; // 62 секунды (чуть больше минуты для надёжности)
    let checksCount = 0;

    console.log(`[PAYMENT POLL] Starting payment status polling for order ${orderId}`);

    // Запускаем таймер для отмены заказа и освобождения резерва при истечении
    // ВАЖНО: Это локальный таймер только для ЭТОГО пользователя, у других не перезагрузится
    const reservationTimer = setTimeout(async () => {
      console.log(`[PAYMENT POLL] ⏰ Reservation timeout reached for order ${orderId}`);

      try {
        // Отменяем заказ на бэкенде, освобождая резерв
        const cancelResponse = await fetch(`${API_BASE}/api/orders/${orderId}/cancel`, {
          method: 'POST'
        });

        if (cancelResponse.ok) {
          const cancelData = await cancelResponse.json();
          console.log(`[PAYMENT POLL] ✅ Order ${orderId} cancelled, released ${cancelData.released_accounts} accounts`);
        } else {
          console.warn(`[PAYMENT POLL] Failed to cancel order ${orderId}:`, cancelResponse.status);
        }
      } catch (cancelError) {
        console.error(`[PAYMENT POLL] Error cancelling order:`, cancelError);
      }

      // Перезагружаем каталог ТОЛЬКО у текущего пользователя для восстановления количества товаров
      if (window.reloadCatalog && typeof window.reloadCatalog === 'function') {
        window.reloadCatalog();
        console.log(`[PAYMENT POLL] ✓ My catalog reloaded after reservation expiration`);
      }
    }, RESERVATION_TIMEOUT);

    const pollInterval = setInterval(async () => {
      checksCount++;
      console.log(`[PAYMENT POLL] Check #${checksCount}/${MAX_CHECKS} for order ${orderId}`);

      try {
        const response = await fetch(`${API_BASE}/api/orders/${orderId}/payment-status`);

        if (!response.ok) {
          console.error(`[PAYMENT POLL] Failed to check status: ${response.status}`);
          return;
        }

        const statusData = await response.json();
        console.log(`[PAYMENT POLL] Status:`, statusData);

        // Если оплачен - показываем уведомление и останавливаем поллинг
        if (statusData.payment_status === 'paid' || statusData.order_status === 'paid') {
          clearInterval(pollInterval);
          clearTimeout(reservationTimer); // Отменяем таймер резервации
          console.log(`[PAYMENT POLL] ✅ Payment confirmed for order ${orderId}`);

          this.showNotification('✅ Оплата получена! Товары будут доставлены в Telegram', 'success');

          // Закрываем модалку оплаты, если она открыта
          const modal = document.querySelector('.payment-modal-overlay');
          if (modal) modal.remove();

          // Перезагружаем каталог для обновления доступного количества
          if (window.reloadCatalog && typeof window.reloadCatalog === 'function') {
            setTimeout(() => window.reloadCatalog(), 1000);
          }

          return;
        }

        // Проверяем, истекла ли резервация (1 минута с момента создания)
        const orderInfo = JSON.parse(localStorage.getItem(`order_${orderId}`) || '{}');
        if (orderInfo.created_at) {
          const createdTime = new Date(orderInfo.created_at);
          const now = new Date();
          const elapsed = (now - createdTime) / 1000; // секунды

          if (elapsed > 60 && statusData.payment_status !== 'paid') {
            clearInterval(pollInterval);
            console.log(`[PAYMENT POLL] ⏰ Reservation expired for order ${orderId}`);

            // Модалка будет закрыта или покажет сообщение об истечении
            // Бот уже обновил своё сообщение через update_message_on_reservation_expired
            // Таймер уже запланирован выше для перезагрузки каталога
            return;
          }
        }

        // Останавливаем после максимального количества проверок
        if (checksCount >= MAX_CHECKS) {
          clearInterval(pollInterval);
          clearTimeout(reservationTimer);
          console.log(`[PAYMENT POLL] ⏱️ Max checks reached for order ${orderId}`);
        }

      } catch (error) {
        console.error(`[PAYMENT POLL] Error checking status:`, error);
      }
    }, CHECK_INTERVAL);

    // Сохраняем интервалы для возможности остановки
    this.paymentPollInterval = pollInterval;
    this.reservationTimer = reservationTimer;
  }

  async createCartRecord() {
    try {
      // Получаем ID пользователя из authManager
      const botUserId = this.getCurrentUserId();

      if (!botUserId) {
        console.warn('No authenticated user, cart will be anonymous');
      }

      // Для carts используем поле user_bot (relation на bot_users)
      const cartData = {
        cart_payload: JSON.stringify({ items: [] })
      };

      // Добавляем user_bot только если есть авторизованный пользователь
      if (botUserId) {
        cartData.user_bot = botUserId;
      }

      console.debug('Creating cart record with data:', cartData);

      const resp = await fetch(`${PB_BASE}/api/collections/carts/records`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cartData)
      });

      if (!resp.ok) {
        const t = await resp.text().catch(() => '');
        console.warn('Could not create cart record:', t);
        return null;
      }

      const data = await resp.json();
      this.cartId = data.id;
      this.userId = botUserId;

      // Сохраняем telegram_id если доступен
      if (window.authManager && window.authManager.currentUser) {
        this.telegramId = window.authManager.currentUser.user_id;
      }

      this.save();
      console.log('✓ Created cart record:', this.cartId, 'for user:', this.userId);
      return this.cartId;
    } catch (e) {
      console.error('Create cart failed', e);
      return null;
    }
  }

  startItemTimer(item) {
    if (!item || !item.expiresAt) return;
    const id = item.productId;
    if (this.timers.get(id)) clearInterval(this.timers.get(id));
    const tick = () => {
      const now = new Date(); const exp = new Date(item.expiresAt); const remaining = exp - now;
      const timerEl = document.querySelector(`[data-timer-product="${id}"]`);
      if (remaining <= 0) { this.removeFromCart(id); this.showNotification('Время резервирования истекло. Товар удалён.', 'warning'); return; }
      if (timerEl) { const m = Math.floor(remaining / 60000); const s = Math.floor((remaining % 60000) / 1000); timerEl.textContent = `${m}:${s.toString().padStart(2,'0')}`; }
    };
    tick(); this.timers.set(id, setInterval(tick, 1000));
  }

  async checkExpiredReservations() {
    const now = new Date();
    for (const it of [...this.cart]) { if (it.expiresAt && new Date(it.expiresAt) <= now) await this.removeFromCart(it.productId); }
  }
}

// Добавляем стили модалки при загрузке страницы
function injectModalStyles() {
  if (document.querySelector('#payment-modal-styles')) return;

  const styles = document.createElement('style');
  styles.id = 'payment-modal-styles';
  styles.textContent = `
    .payment-modal-overlay {
      position: fixed !important;
      top: 0 !important;
      left: 0 !important;
      right: 0 !important;
      bottom: 0 !important;
      background: rgba(0, 0, 0, 0.8) !important;
      display: flex !important;
      align-items: center !important;
      justify-content: center !important;
      z-index: 10000 !important;
    }
    .payment-modal {
      background: white;
      border-radius: 12px;
      max-width: 500px;
      width: 90%;
      max-height: 90vh;
      overflow-y: auto;
      box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.3);
    }
    .payment-modal-header {
      padding: 20px 24px;
      border-bottom: 1px solid #e5e7eb;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .payment-modal-header h3 {
      margin: 0;
      font-size: 18px;
      font-weight: 600;
    }
    .payment-modal-close {
      background: none;
      border: none;
      font-size: 28px;
      cursor: pointer;
      color: #6b7280;
      width: 32px;
      height: 32px;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .payment-modal-body {
      padding: 24px;
    }
    .payment-info {
      margin-bottom: 24px;
    }
    .payment-amount, .payment-description {
      display: flex;
      justify-content: space-between;
      margin-bottom: 12px;
    }
    .payment-amount .amount {
      font-size: 24px;
      font-weight: 700;
      color: #059669;
    }
    .label {
      font-weight: 500;
      color: #374151;
    }
    .payment-actions {
      display: flex;
      gap: 12px;
      margin-bottom: 20px;
    }
    .btn-payment {
      flex: 1;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white !important;
      padding: 12px 20px;
      border-radius: 8px;
      text-decoration: none !important;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      font-weight: 600;
    }
    .payment-notice {
      background: #fef3c7;
      border: 1px solid #f59e0b;
      border-radius: 8px;
      padding: 12px;
    }
    .payment-notice p {
      margin: 4px 0;
      font-size: 14px;
      color: #92400e;
    }
  `;
  document.head.appendChild(styles);
  console.log('✓ Payment modal styles injected');
}

// Инициализация при загрузке страницы
let cartManager;
document.addEventListener('DOMContentLoaded', () => {
  // Инжектим стили модалки
  injectModalStyles();

  cartManager = new CartManager();

  // Обработчик кнопки оформления заказа
  const checkoutBtn = document.getElementById('checkoutBtn');
  if (checkoutBtn) {
    checkoutBtn.addEventListener('click', () => {
      cartManager.checkout();
    });
  }
});
