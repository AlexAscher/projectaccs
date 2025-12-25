/// <reference path="../pb_data/types.d.ts" />
migrate((app) => {
  const collection = app.findCollectionByNameOrId("pbc_997979991")

  // add field
  collection.fields.addAt(4, new Field({
    "autogeneratePattern": "",
    "hidden": false,
    "id": "text2918445923",
    "max": 0,
    "min": 0,
    "name": "data",
    "pattern": "",
    "presentable": false,
    "primaryKey": false,
    "required": false,
    "system": false,
    "type": "text"
  }))

  // add field
  collection.fields.addAt(5, new Field({
    "cascadeDelete": false,
    "collectionId": "pbc_4092854851",
    "hidden": false,
    "id": "relation3544843437",
    "maxSelect": 1,
    "minSelect": 0,
    "name": "product",
    "presentable": false,
    "required": false,
    "system": false,
    "type": "relation"
  }))

  return app.save(collection)
}, (app) => {
  const collection = app.findCollectionByNameOrId("pbc_997979991")

  // remove field
  collection.fields.removeById("text2918445923")

  // remove field
  collection.fields.removeById("relation3544843437")

  return app.save(collection)
})
