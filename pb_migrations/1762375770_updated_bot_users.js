/// <reference path="../pb_data/types.d.ts" />
migrate((app) => {
  const collection = app.findCollectionByNameOrId("pbc_3458397677")

  // remove field
  collection.fields.removeById("relation_bot_user_user_ref")

  return app.save(collection)
}, (app) => {
  const collection = app.findCollectionByNameOrId("pbc_3458397677")

  // add field
  collection.fields.addAt(2, new Field({
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

  return app.save(collection)
})
