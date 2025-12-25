/// <reference path="../pb_data/types.d.ts" />
migrate((app) => {
  // Update `accounts` collection: add structured fields for price, currency, category/subcategory relations and metadata
  const accounts = app.findCollectionByNameOrId("accounts")

  // add price (number)
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

  // add currency (text)
  accounts.fields.addAt(5, new Field({
    "hidden": false,
    "id": "text_currency",
    "name": "currency",
    "presentable": false,
    "required": false,
    "system": false,
    "type": "text"
  }))

  // add category relation
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

  // add subcategory relation
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

  // add metadata JSON (use editor type for arbitrary JSON/markup)
  accounts.fields.addAt(8, new Field({
    "hidden": false,
    "id": "editor_metadata",
    "name": "metadata",
    "presentable": false,
    "required": false,
    "system": false,
    "type": "editor"
  }))

  // Update `products` collection: ensure price, currency, region, description
  const products = app.findCollectionByNameOrId("products")
  products.fields.addAt(3, new Field({
    "hidden": false,
    "id": "text_sku",
    "name": "sku",
    "presentable": false,
    "required": false,
    "system": false,
    "type": "text"
  }))
  products.fields.addAt(4, new Field({
    "hidden": false,
    "id": "text_title",
    "name": "title",
    "presentable": false,
    "required": false,
    "system": false,
    "type": "text"
  }))
  products.fields.addAt(5, new Field({
    "hidden": false,
    "id": "editor_description",
    "name": "description",
    "presentable": false,
    "required": false,
    "system": false,
    "type": "editor"
  }))
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

  // Update `sold_accounts`: add references to buyer, seller, account, sale_price
  const sold = app.findCollectionByNameOrId("sold_accounts")
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

  // Update `bot_users`: add wallet balance and roles
  const botUsers = app.findCollectionByNameOrId("bot_users")
  botUsers.fields.addAt(3, new Field({
    "hidden": false,
    "id": "number_balance",
    "name": "balance",
    "presentable": false,
    "required": false,
    "system": false,
    "type": "number",
    "options": { "min": 0 }
  }))
  botUsers.fields.addAt(4, new Field({
    "hidden": false,
    "id": "text_role",
    "name": "role",
    "presentable": false,
    "required": false,
    "system": false,
    "type": "text"
  }))

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
      }
    ],
    "id": "pbc_9999999999",
    "indexes": [],
    "listRule": null,
    "name": "payments",
    "system": false,
    "type": "base",
    "updateRule": null,
    "viewRule": null
  })

  // save collections
  app.save(accounts)
  app.save(products)
  app.save(sold)
  app.save(botUsers)
  app.save(payments)

  return
}, (app) => {
  // rollback: remove fields we added
  const accounts = app.findCollectionByNameOrId("accounts")
  accounts.fields.removeById("number_price")
  accounts.fields.removeById("text_currency")
  accounts.fields.removeById("relation_category")
  accounts.fields.removeById("relation_subcategory")
  accounts.fields.removeById("editor_metadata")

  const products = app.findCollectionByNameOrId("products")
  products.fields.removeById("text_sku")
  products.fields.removeById("text_title")
  products.fields.removeById("editor_description")
  products.fields.removeById("number_price")

  const sold = app.findCollectionByNameOrId("sold_accounts")
  sold.fields.removeById("relation_account")
  sold.fields.removeById("relation_buyer")
  sold.fields.removeById("number_sale_price")

  const botUsers = app.findCollectionByNameOrId("bot_users")
  botUsers.fields.removeById("number_balance")
  botUsers.fields.removeById("text_role")

  // delete payments collection if present
  const payments = app.findCollectionByNameOrId("pbc_9999999999")
  if (payments) app.delete(payments)

  app.save(accounts)
  app.save(products)
  app.save(sold)
  app.save(botUsers)

  return
})
