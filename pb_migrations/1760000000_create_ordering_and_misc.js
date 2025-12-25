/// <reference path="../pb_data/types.d.ts" />
migrate((app) => {
  // --- orders collection ---
  let orders = null
  try { orders = app.findCollectionByNameOrId("orders") } catch(e) { orders = null }
  if (!orders) {
    orders = new Collection({
      "createRule": null,
      "deleteRule": null,
      "fields": [
        { "autogeneratePattern":"[a-z0-9]{15}", "hidden":false, "id":"text_ord_id", "max":15, "min":15, "name":"id", "pattern":"^[a-z0-9]+$", "presentable":false, "primaryKey":true, "required":true, "system":true, "type":"text" },
        { "hidden":false, "id":"autodate_ord_created", "name":"created", "onCreate":true, "onUpdate":false, "presentable":false, "system":false, "type":"autodate" },
        { "hidden":false, "id":"autodate_ord_updated", "name":"updated", "onCreate":true, "onUpdate":true, "presentable":false, "system":false, "type":"autodate" },
        { "cascadeDelete":false, "collectionId":"_pb_users_auth_", "hidden":false, "id":"relation_orders_user", "maxSelect":1, "minSelect":0, "name":"user", "presentable":false, "required":false, "system":false, "type":"relation" },
        { "cascadeDelete":false, "collectionId":"pbc_3458397677", "hidden":false, "id":"relation_orders_bot_user", "maxSelect":1, "minSelect":0, "name":"bot_user", "presentable":false, "required":false, "system":false, "type":"relation" },
        { "hidden":false, "id":"number_total_amount", "name":"total_amount", "presentable":false, "required":false, "system":false, "type":"number", "options": { "min": 0 } },
        { "hidden":false, "id":"text_currency", "name":"currency", "presentable":false, "required":false, "system":false, "type":"text" },
        { "hidden":false, "id":"text_status", "name":"status", "presentable":false, "required":false, "system":false, "type":"text" },
        { "hidden":false, "id":"autodate_reserve_expires_at", "name":"reserve_expires_at", "presentable":false, "required":false, "system":false, "type":"date" },
        { "hidden":false, "id":"text_order_number", "name":"order_number", "presentable":false, "required":false, "system":false, "type":"text" },
        { "hidden":false, "id":"editor_order_meta", "name":"metadata", "presentable":false, "required":false, "system":false, "type":"editor" }
      ],
      "id": "pbc_1760000001",
      "indexes": [],
      "listRule": null,
      "name": "orders",
      "system": false,
      "type": "base",
      "updateRule": null,
      "viewRule": null
    })

    app.save(orders)
  }

  // --- order_items collection ---
  let orderItems = null
  try { orderItems = app.findCollectionByNameOrId("order_items") } catch(e) { orderItems = null }
  if (!orderItems) {
    orderItems = new Collection({
      "createRule": null,
      "deleteRule": null,
      "fields": [
        { "autogeneratePattern":"[a-z0-9]{15}", "hidden":false, "id":"text_oi_id", "max":15, "min":15, "name":"id", "pattern":"^[a-z0-9]+$", "presentable":false, "primaryKey":true, "required":true, "system":true, "type":"text" },
        { "hidden":false, "id":"autodate_oi_created", "name":"created", "onCreate":true, "onUpdate":false, "presentable":false, "system":false, "type":"autodate" },
        { "hidden":false, "id":"autodate_oi_updated", "name":"updated", "onCreate":true, "onUpdate":true, "presentable":false, "system":false, "type":"autodate" },
        { "cascadeDelete":false, "collectionId":"pbc_1760000001", "hidden":false, "id":"relation_oi_order", "maxSelect":1, "minSelect":0, "name":"order", "presentable":false, "required":true, "system":false, "type":"relation" },
        { "cascadeDelete":false, "collectionId":"pbc_4092854851", "hidden":false, "id":"relation_oi_product", "maxSelect":1, "minSelect":0, "name":"product", "presentable":false, "required":false, "system":false, "type":"relation" },
        { "hidden":false, "id":"number_unit_price", "name":"unit_price", "presentable":false, "required":false, "system":false, "type":"number", "options": { "min": 0 } },
        { "hidden":false, "id":"number_quantity", "name":"quantity", "presentable":false, "required":false, "system":false, "type":"number", "options": { "min": 1 } },
        { "cascadeDelete":false, "collectionId":"pbc_2324088501", "hidden":false, "id":"relation_oi_account", "maxSelect":1, "minSelect":0, "name":"account", "presentable":false, "required":false, "system":false, "type":"relation" },
        { "hidden":false, "id":"editor_oi_meta", "name":"metadata", "presentable":false, "required":false, "system":false, "type":"editor" }
      ],
      "id": "pbc_1760000002",
      "indexes": [],
      "listRule": null,
      "name": "order_items",
      "system": false,
      "type": "base",
      "updateRule": null,
      "viewRule": null
    })

    app.save(orderItems)
  }

  // --- carts collection ---
  let carts = null
  try { carts = app.findCollectionByNameOrId("carts") } catch(e) { carts = null }
  if (!carts) {
    carts = new Collection({
      "createRule": null,
      "deleteRule": null,
      "fields": [
        { "autogeneratePattern":"[a-z0-9]{15}", "hidden":false, "id":"text_cart_id", "max":15, "min":15, "name":"id", "pattern":"^[a-z0-9]+$", "presentable":false, "primaryKey":true, "required":true, "system":true, "type":"text" },
        { "hidden":false, "id":"autodate_cart_created", "name":"created", "onCreate":true, "onUpdate":false, "presentable":false, "system":false, "type":"autodate" },
        { "hidden":false, "id":"autodate_cart_updated", "name":"updated", "onCreate":true, "onUpdate":true, "presentable":false, "system":false, "type":"autodate" },
        { "cascadeDelete":false, "collectionId":"_pb_users_auth_", "hidden":false, "id":"relation_cart_user", "maxSelect":1, "minSelect":0, "name":"user", "presentable":false, "required":false, "system":false, "type":"relation" },
        { "hidden":false, "id":"editor_cart_payload", "name":"cart_payload", "presentable":false, "required":false, "system":false, "type":"editor" }
      ],
      "id": "pbc_1760000003",
      "indexes": [],
      "listRule": null,
      "name": "carts",
      "system": false,
      "type": "base",
      "updateRule": null,
      "viewRule": null
    })

    app.save(carts)
  }

  // --- cart_items collection ---
  let cartItems = null
  try { cartItems = app.findCollectionByNameOrId("cart_items") } catch(e) { cartItems = null }
  if (!cartItems) {
    cartItems = new Collection({
      "createRule": null,
      "deleteRule": null,
      "fields": [
        { "autogeneratePattern":"[a-z0-9]{15}", "hidden":false, "id":"text_ci_id", "max":15, "min":15, "name":"id", "pattern":"^[a-z0-9]+$", "presentable":false, "primaryKey":true, "required":true, "system":true, "type":"text" },
        { "hidden":false, "id":"autodate_ci_created", "name":"created", "onCreate":true, "onUpdate":false, "presentable":false, "system":false, "type":"autodate" },
        { "hidden":false, "id":"autodate_ci_updated", "name":"updated", "onCreate":true, "onUpdate":true, "presentable":false, "system":false, "type":"autodate" },
        { "cascadeDelete":false, "collectionId":"pbc_1760000003", "hidden":false, "id":"relation_ci_cart", "maxSelect":1, "minSelect":0, "name":"cart", "presentable":false, "required":true, "system":false, "type":"relation" },
        { "cascadeDelete":false, "collectionId":"pbc_4092854851", "hidden":false, "id":"relation_ci_product", "maxSelect":1, "minSelect":0, "name":"product", "presentable":false, "required":true, "system":false, "type":"relation" },
        { "hidden":false, "id":"number_ci_quantity", "name":"quantity", "presentable":false, "required":false, "system":false, "type":"number", "options": { "min": 1 } }
      ],
      "id": "pbc_1760000004",
      "indexes": [],
      "listRule": null,
      "name": "cart_items",
      "system": false,
      "type": "base",
      "updateRule": null,
      "viewRule": null
    })

    app.save(cartItems)
  }

  // --- files collection ---
  let files = null
  try { files = app.findCollectionByNameOrId("files") } catch(e) { files = null }
  if (!files) {
    files = new Collection({
      "createRule": null,
      "deleteRule": null,
      "fields": [
        { "autogeneratePattern":"[a-z0-9]{15}", "hidden":false, "id":"text_file_id", "max":15, "min":15, "name":"id", "pattern":"^[a-z0-9]+$", "presentable":false, "primaryKey":true, "required":true, "system":true, "type":"text" },
        { "hidden":false, "id":"autodate_file_created", "name":"created", "onCreate":true, "onUpdate":false, "presentable":false, "system":false, "type":"autodate" },
        { "hidden":false, "id":"autodate_file_updated", "name":"updated", "onCreate":true, "onUpdate":true, "presentable":false, "system":false, "type":"autodate" },
        { "cascadeDelete":false, "collectionId":"pbc_1760000001", "hidden":false, "id":"relation_file_order", "maxSelect":1, "minSelect":0, "name":"order", "presentable":false, "required":false, "system":false, "type":"relation" },
        { "cascadeDelete":false, "collectionId":"pbc_1760000002", "hidden":false, "id":"relation_file_order_item", "maxSelect":1, "minSelect":0, "name":"order_item", "presentable":false, "required":false, "system":false, "type":"relation" },
        { "hidden":false, "id":"file_file", "maxSelect":1, "maxSize":0, "mimeTypes":[], "name":"file", "presentable":false, "protected":false, "required":false, "system":false, "thumbs":null, "type":"file" },
        { "hidden":false, "id":"text_filename", "name":"filename", "presentable":false, "required":false, "system":false, "type":"text" }
      ],
      "id": "pbc_1760000005",
      "indexes": [],
      "listRule": null,
      "name": "files",
      "system": false,
      "type": "base",
      "updateRule": null,
      "viewRule": null
    })

    app.save(files)
  }

  // --- audit_logs collection ---
  let audit = null
  try { audit = app.findCollectionByNameOrId("audit_logs") } catch(e) { audit = null }
  if (!audit) {
    audit = new Collection({
      "createRule": null,
      "deleteRule": null,
      "fields": [
        { "autogeneratePattern":"[a-z0-9]{15}", "hidden":false, "id":"text_audit_id", "max":15, "min":15, "name":"id", "pattern":"^[a-z0-9]+$", "presentable":false, "primaryKey":true, "required":true, "system":true, "type":"text" },
        { "hidden":false, "id":"autodate_audit_created", "name":"created", "onCreate":true, "onUpdate":false, "presentable":false, "system":false, "type":"autodate" },
        { "hidden":false, "id":"text_entity_type", "name":"entity_type", "presentable":false, "required":false, "system":false, "type":"text" },
        { "hidden":false, "id":"text_entity_id", "name":"entity_id", "presentable":false, "required":false, "system":false, "type":"text" },
        { "hidden":false, "id":"text_action", "name":"action", "presentable":false, "required":false, "system":false, "type":"text" },
        { "hidden":false, "id":"editor_payload", "name":"payload", "presentable":false, "required":false, "system":false, "type":"editor" }
      ],
      "id": "pbc_1760000006",
      "indexes": [],
      "listRule": null,
      "name": "audit_logs",
      "system": false,
      "type": "base",
      "updateRule": null,
      "viewRule": null
    })

    app.save(audit)
  }

  // --- update bot_users: add user_ref relation to users (unique enforced via index) ---
  let botUsers = null
  try { botUsers = app.findCollectionByNameOrId("bot_users") } catch(e) { botUsers = null }
  if (botUsers) {
    // add relation field if not exists
    const exists = botUsers.schema?.fields?.some?.(f => f.name === 'user_ref')
    try {
      if (!exists) {
        botUsers.fields.addAt(2, new Field({
          "cascadeDelete": false,
          "collectionId": "_pb_users_auth_",
          "hidden": false,
          "id": "relation_bot_user_user_ref",
          "maxSelect": 1,
          "minSelect": 0,
          "name": "user_ref",
          "presentable": false,
          "required": false,
          "system": false,
          "type": "relation"
        }))
      }
    } catch(e) {
      // ignore if add fails due to already existing id
    }

    // add unique index on user_ref (wrap in try/catch because existing data may violate uniqueness)
    try {
      botUsers.indexes = botUsers.indexes || []
      botUsers.indexes.push("CREATE UNIQUE INDEX `idx_botUsers_user_ref` ON `bot_users` (user_ref)")
      try {
        app.save(botUsers)
      } catch(e) {
        // if saving (creating index) fails (e.g. UNIQUE constraint), remove index entry and continue
        try { botUsers.indexes = (botUsers.indexes||[]).filter(i => !i.includes('idx_botUsers_user_ref')) } catch(_) {}
        try { app.save(botUsers) } catch(_) {}
      }
    } catch(e) {
      // ignore index creation errors
    }
  }

  return
}, (app) => {
  // rollback: delete created collections and remove bot_users additions
  let _orders = null
  try { _orders = app.findCollectionByNameOrId("pbc_1760000001") } catch(e) { _orders = null }
  if (_orders) app.delete(_orders)

  let _orderItems = null
  try { _orderItems = app.findCollectionByNameOrId("pbc_1760000002") } catch(e) { _orderItems = null }
  if (_orderItems) app.delete(_orderItems)

  let _carts = null
  try { _carts = app.findCollectionByNameOrId("pbc_1760000003") } catch(e) { _carts = null }
  if (_carts) app.delete(_carts)

  let _cartItems = null
  try { _cartItems = app.findCollectionByNameOrId("pbc_1760000004") } catch(e) { _cartItems = null }
  if (_cartItems) app.delete(_cartItems)

  let _files = null
  try { _files = app.findCollectionByNameOrId("pbc_1760000005") } catch(e) { _files = null }
  if (_files) app.delete(_files)

  let _audit = null
  try { _audit = app.findCollectionByNameOrId("pbc_1760000006") } catch(e) { _audit = null }
  if (_audit) app.delete(_audit)

  let _botUsers = null
  try { _botUsers = app.findCollectionByNameOrId("bot_users") } catch(e) { _botUsers = null }
  if (_botUsers) {
    try { _botUsers.fields.removeById("relation_bot_user_user_ref") } catch(e) {}
    try { _botUsers.indexes = (_botUsers.indexes||[]).filter(i => !i.includes('idx_botUsers_user_ref')) } catch(e) {}
    app.save(_botUsers)
  }

  return
})
