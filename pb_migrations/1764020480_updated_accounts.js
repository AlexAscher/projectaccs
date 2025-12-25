/// <reference path="../pb_data/types.d.ts" />
migrate((app) => {
  const collection = app.findCollectionByNameOrId("pbc_2324088501")

  // remove field
  collection.fields.removeById("relation_category")

  // remove field
  collection.fields.removeById("relation_subcategory")

  return app.save(collection)
}, (app) => {
  const collection = app.findCollectionByNameOrId("pbc_2324088501")

  // add field
  collection.fields.addAt(5, new Field({
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

  // add field
  collection.fields.addAt(6, new Field({
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

  return app.save(collection)
})
