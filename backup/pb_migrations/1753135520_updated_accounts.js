/// <reference path="../pb_data/types.d.ts" />
migrate((app) => {
  const collection = app.findCollectionByNameOrId("pbc_2324088501")

  // remove field
  collection.fields.removeById("relation232563784")

  // remove field
  collection.fields.removeById("relation961728715")

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
  const collection = app.findCollectionByNameOrId("pbc_2324088501")

  // add field
  collection.fields.addAt(5, new Field({
    "cascadeDelete": false,
    "collectionId": "pbc_2354486458",
    "hidden": false,
    "id": "relation232563784",
    "maxSelect": 1,
    "minSelect": 0,
    "name": "subcategory",
    "presentable": false,
    "required": false,
    "system": false,
    "type": "relation"
  }))

  // add field
  collection.fields.addAt(6, new Field({
    "cascadeDelete": false,
    "collectionId": "pbc_3292755704",
    "hidden": false,
    "id": "relation961728715",
    "maxSelect": 1,
    "minSelect": 0,
    "name": "platform",
    "presentable": false,
    "required": false,
    "system": false,
    "type": "relation"
  }))

  // remove field
  collection.fields.removeById("relation3544843437")

  return app.save(collection)
})
