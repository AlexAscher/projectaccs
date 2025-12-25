/// <reference path="../pb_data/types.d.ts" />
migrate((app) => {
  const collection = app.findCollectionByNameOrId("pbc_2324088501")

  // remove field
  collection.fields.removeById("text961728715")

  // remove field
  collection.fields.removeById("text232563784")

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

  return app.save(collection)
}, (app) => {
  const collection = app.findCollectionByNameOrId("pbc_2324088501")

  // add field
  collection.fields.addAt(3, new Field({
    "autogeneratePattern": "",
    "hidden": false,
    "id": "text961728715",
    "max": 0,
    "min": 0,
    "name": "platform",
    "pattern": "",
    "presentable": false,
    "primaryKey": false,
    "required": false,
    "system": false,
    "type": "text"
  }))

  // add field
  collection.fields.addAt(4, new Field({
    "autogeneratePattern": "",
    "hidden": false,
    "id": "text232563784",
    "max": 0,
    "min": 0,
    "name": "subcategory",
    "pattern": "",
    "presentable": false,
    "primaryKey": false,
    "required": false,
    "system": false,
    "type": "text"
  }))

  // remove field
  collection.fields.removeById("relation232563784")

  // remove field
  collection.fields.removeById("relation961728715")

  return app.save(collection)
})
