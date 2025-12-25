/// <reference path="../pb_data/types.d.ts" />
migrate((app) => {
  // Update `accounts` collection: add structured fields for price, currency, category/subcategory relations and metadata
  let accounts = null
  try { accounts = app.findCollectionByNameOrId("accounts") } catch(e) { accounts = null }

  // add price (number)
  if (accounts) {
    try {
      accounts.fields.addAt(4, new Field({
        "hidden": false,
        "id": "number_price",
        "name": "price",
        "presentable": false,
        "required": false,
        "system": false,
        "type": "number",
        "options": { "min": 0 }
      }))
    } catch(e) {}

    // currency field removed — currency is stored on product/pricing level

    // add category relation
    try {
      accounts.fields.addAt(6, new Field({
        "cascadeDelete": false,
        "collectionId": "pbc_3292755704",
        "hidden": false,
        "id": "relation_category",
        "maxSelect": 1,
        "minSelect": 0,
        "name": "category",
        "presentable": false,
        "required": false,
        "system": false,
        "type": "relation"
      }))
    } catch(e) {}

    // add subcategory relation
    try {
      accounts.fields.addAt(7, new Field({
        "cascadeDelete": false,
        "collectionId": "pbc_2354486458",
        "hidden": false,
        "id": "relation_subcategory",
        "maxSelect": 1,
        "minSelect": 0,
        "name": "subcategory",
        "presentable": false,
        "required": false,
        "system": false,
        "type": "relation"
      }))
    } catch(e) {}

    // add metadata JSON (use editor type for arbitrary JSON/markup)
    try {
      accounts.fields.addAt(8, new Field({
        "hidden": false,
        "id": "editor_metadata",
        "name": "metadata",
        "presentable": false,
        "required": false,
        "system": false,
        "type": "editor"
      }))
    } catch(e) {}
  }

  // Update `products` collection: ensure price, currency, region, description
  let products = null
  try { products = app.findCollectionByNameOrId("products") } catch(e) { products = null }
  if (products) {
    try {
      products.fields.addAt(3, new Field({
        "hidden": false,
        "id": "text_sku",
        "name": "sku",
        "presentable": false,
        "required": false,
        "system": false,
        "type": "text"
      }))
    } catch(e) {}
    try {
      products.fields.addAt(4, new Field({
        "hidden": false,
        "id": "text_title",
        "name": "title",
        "presentable": false,
        "required": false,
        "system": false,
        "type": "text"
      }))
    } catch(e) {}
    try {
      products.fields.addAt(5, new Field({
        "hidden": false,
        "id": "editor_description",
        "name": "description",
        "presentable": false,
        "required": false,
        "system": false,
        "type": "editor"
      }))
    } catch(e) {}
    try {
      products.fields.addAt(6, new Field({
        "hidden": false,
        "id": "number_price",
        "name": "price",
        "presentable": false,
        "required": false,
        "system": false,
        "type": "number",
        "options": { "min": 0 }
      }))
    } catch(e) {}
  }

  // Update `sold_accounts`: add references to buyer, seller, account, sale_price
  let sold = null
  try { sold = app.findCollectionByNameOrId("sold_accounts") } catch(e) { sold = null }
  if (sold) {
    try {
      sold.fields.addAt(3, new Field({
        "cascadeDelete": false,
        "collectionId": "pbc_2324088501",
        "hidden": false,
        "id": "relation_account",
        "maxSelect": 1,
        "minSelect": 0,
        "name": "account",
        "presentable": false,
        "required": true,
        "system": false,
        "type": "relation"
      }))
    } catch(e) {}
    try {
      sold.fields.addAt(4, new Field({
        "cascadeDelete": false,
        "collectionId": "users",
        "hidden": false,
        "id": "relation_buyer",
        "maxSelect": 1,
        "minSelect": 0,
        "name": "buyer",
        "presentable": false,
        "required": false,
        "system": false,
        "type": "relation"
      }))
    } catch(e) {}
    try {
      sold.fields.addAt(5, new Field({
        "hidden": false,
        "id": "number_sale_price",
        "name": "sale_price",
        "presentable": false,
        "required": false,
        "system": false,
        "type": "number",
        "options": { "min": 0 }
      }))
    } catch(e) {}
  }

  // Update `bot_users`: remove wallet balance (migrate it out) and add roles
  let botUsers = null
  try { botUsers = app.findCollectionByNameOrId("bot_users") } catch(e) { botUsers = null }
  if (botUsers) {
    // remove legacy `balance` field if present
    try { botUsers.fields.removeById("number_balance") } catch(e) {}
    try {
      botUsers.fields.addAt(4, new Field({
        "hidden": false,
        "id": "text_role",
        "name": "role",
        "presentable": false,
        "required": false,
        "system": false,
        "type": "text"
      }))
    } catch(e) {}
  }

  // Update `users`: remove legacy `avatar` file field if present
  let users = null
  try { users = app.findCollectionByNameOrId("users") } catch(e) { users = null }
  if (users) {
    try {
      const af = users.schema?.fields?.find?.(f => f.name === 'avatar')
      if (af && af.id) try { users.fields.removeById(af.id) } catch(e) {}
    } catch(e) {}
  }

  // Create `payments` collection (if not exists create new collection object)
  const payments = new Collection({
    "createRule": null,
    "deleteRule": null,
    "fields": [
      {
        "autogeneratePattern": "[a-z0-9]{15}",
        "hidden": false,
        "id": "text3208210256",
        "max": 15,
        "min": 15,
        "name": "id",
        "pattern": "^[a-z0-9]+$",
        "presentable": false,
        "primaryKey": true,
        "required": true,
        "system": true,
        "type": "text"
      },
      {
        "hidden": false,
        "id": "autodate_created",
        "name": "created",
        "onCreate": true,
        "onUpdate": false,
        "presentable": false,
        "system": false,
        "type": "autodate"
      },
      {
        "hidden": false,
        "id": "autodate_updated",
        "name": "updated",
        "onCreate": true,
        "onUpdate": true,
        "presentable": false,
        "system": false,
        "type": "autodate"
      },
      {
        "hidden": false,
        "id": "text_invoice_id",
        "name": "invoice_id",
        "presentable": false,
        "required": true,
        "system": false,
        "type": "text"
      },
      {
        "cascadeDelete": false,
        "collectionId": "pbc_1760000001",
        "hidden": false,
        "id": "relation_order",
        "maxSelect": 1,
        "minSelect": 0,
        "name": "order",
        "presentable": false,
        "required": false,
        "system": false,
        "type": "relation"
      },
      {
        "cascadeDelete": false,
        "collectionId": "users",
        "hidden": false,
        "id": "relation_user",
        "maxSelect": 1,
        "minSelect": 0,
        "name": "user",
        "presentable": false,
        "required": true,
        "system": false,
        "type": "relation"
      },
      {
        "hidden": false,
        "id": "number_amount",
        "name": "amount",
        "presentable": false,
        "required": true,
        "system": false,
        "type": "number",
        "options": { "min": 0 }
      },
      {
        "hidden": false,
        "id": "text_currency",
        "name": "currency",
        "presentable": false,
        "required": true,
        "system": false,
        "type": "text"
      },
      {
        "hidden": false,
        "id": "text_provider",
        "name": "provider",
        "presentable": false,
        "required": false,
        "system": false,
        "type": "text"
      },
      {
        "hidden": false,
        "id": "text_provider_tx",
        "name": "provider_tx_id",
        "presentable": false,
        "required": false,
        "system": false,
        "type": "text"
      },
      {
        "hidden": false,
        "id": "text_status",
        "name": "status",
        "presentable": false,
        "required": false,
        "system": false,
        "type": "text"
      },
      {
        "hidden": false,
        "id": "autodate_expires",
        "name": "expires_at",
        "onCreate": false,
        "onUpdate": false,
        "presentable": false,
        "required": false,
        "system": false,
        "type": "date"
      },
      {
        "hidden": false,
        "id": "editor_metadata",
        "name": "metadata",
        "presentable": false,
        "required": false,
        "system": false,
        "type": "editor"
      }
    ],
    "id": "pbc_9999999999",
    "indexes": [
      "CREATE UNIQUE INDEX `idx_payments_invoice` ON `payments` (invoice_id)",
      "CREATE INDEX `idx_payments_provider_tx` ON `payments` (provider_tx_id)"
    ],
    "listRule": null,
    "name": "payments",
    "system": false,
    "type": "base",
    "updateRule": null,
    "viewRule": null
  })

  // save collections
  try { if (accounts) app.save(accounts) } catch(e) {}
  try { if (products) app.save(products) } catch(e) {}
  try { if (sold) app.save(sold) } catch(e) {}
  try { if (botUsers) app.save(botUsers) } catch(e) {}
  // only save payments if it does not exist (safe check)
  let paymentsExists = false
  try { paymentsExists = !!app.findCollectionByNameOrId("payments") } catch(e) { paymentsExists = false }
  if (!paymentsExists) {
    try { app.save(payments) } catch(e) {}
  }

  return
}, (app) => {
  // rollback: remove fields we added
  const accounts = app.findCollectionByNameOrId("accounts")
  if (accounts) {
    try { accounts.fields.removeById("number_price") } catch(e) {}
    try { accounts.fields.removeById("relation_category") } catch(e) {}
    try { accounts.fields.removeById("relation_subcategory") } catch(e) {}
    try { accounts.fields.removeById("editor_metadata") } catch(e) {}
    try { app.save(accounts) } catch(e) {}
  }

  const products = app.findCollectionByNameOrId("products")
  if (products) {
    try { products.fields.removeById("text_sku") } catch(e) {}
    try { products.fields.removeById("text_title") } catch(e) {}
    try { products.fields.removeById("editor_description") } catch(e) {}
    try { products.fields.removeById("number_price") } catch(e) {}
    try { app.save(products) } catch(e) {}
  }

  const sold = app.findCollectionByNameOrId("sold_accounts")
  if (sold) {
    try { sold.fields.removeById("relation_account") } catch(e) {}
    try { sold.fields.removeById("relation_buyer") } catch(e) {}
    try { sold.fields.removeById("number_sale_price") } catch(e) {}
    try { app.save(sold) } catch(e) {}
  }

  const botUsers = app.findCollectionByNameOrId("bot_users")
  if (botUsers) {
    try { botUsers.fields.removeById("number_balance") } catch(e) {}
    try { botUsers.fields.removeById("text_role") } catch(e) {}
    try { app.save(botUsers) } catch(e) {}
  }

  // delete payments collection if present
  const payments = app.findCollectionByNameOrId("pbc_9999999999")
  if (payments) app.delete(payments)

  return
})
