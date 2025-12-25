/// <reference path="../pb_data/types.d.ts" />
migrate((app) => {
  const collection = app.findCollectionByNameOrId("_pb_users_auth_")

  // update field
  collection.fields.addAt(2, new Field({
    "autogeneratePattern": "",
    "hidden": true,
    "id": "text2504183744",
    "max": 0,
    "min": 0,
    "name": "tokenKey",
    "pattern": "",
    "presentable": false,
    "primaryKey": false,
    "required": true,
    "system": true,
    "type": "text"
  }))

  return app.save(collection)
}, (app) => {
  const collection = app.findCollectionByNameOrId("_pb_users_auth_")

  // update field
  collection.fields.addAt(2, new Field({
    "autogeneratePattern": "[a-zA-Z0-9]{50}",
    "hidden": true,
    "id": "text2504183744",
    "max": 60,
    "min": 30,
    "name": "tokenKey",
    "pattern": "",
    "presentable": false,
    "primaryKey": false,
    "required": true,
    "system": true,
    "type": "text"
  }))

  return app.save(collection)
})
