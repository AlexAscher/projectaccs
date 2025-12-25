/// <reference path="../pb_data/types.d.ts" />
migrate((app) => {
  const collection = app.findCollectionByNameOrId("pbc_1760000001")

  // update field
  collection.fields.addAt(3, new Field({
    "cascadeDelete": false,
    "collectionId": "pbc_3458397677",
    "hidden": false,
    "id": "relation_orders_bot_user",
    "maxSelect": 1,
    "minSelect": 0,
    "name": "user_bot",
    "presentable": false,
    "required": false,
    "system": false,
    "type": "relation"
  }))

  return app.save(collection)
}, (app) => {
  const collection = app.findCollectionByNameOrId("pbc_1760000001")

  // update field
  collection.fields.addAt(3, new Field({
    "cascadeDelete": false,
    "collectionId": "pbc_3458397677",
    "hidden": false,
    "id": "relation_orders_bot_user",
    "maxSelect": 1,
    "minSelect": 0,
    "name": "bot_user",
    "presentable": false,
    "required": false,
    "system": false,
    "type": "relation"
  }))

  return app.save(collection)
})
