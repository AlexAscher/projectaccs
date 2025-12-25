/// <reference path="../pb_data/types.d.ts" />
migrate((app) => {
  const collection = app.findCollectionByNameOrId("pbc_2324088501")

  // add field
  collection.fields.addAt(11, new Field({
    "cascadeDelete": false,
    "collectionId": "pbc_1760000003",
    "hidden": false,
    "id": "relation1527135592",
    "maxSelect": 1,
    "minSelect": 0,
    "name": "reserved_cart",
    "presentable": false,
    "required": false,
    "system": false,
    "type": "relation"
  }))

  // add field
  collection.fields.addAt(12, new Field({
    "hidden": false,
    "id": "date2568376179",
    "max": "",
    "min": "",
    "name": "reserved_until",
    "presentable": false,
    "required": false,
    "system": false,
    "type": "date"
  }))

  return app.save(collection)
}, (app) => {
  const collection = app.findCollectionByNameOrId("pbc_2324088501")

  // remove field
  collection.fields.removeById("relation1527135592")

  // remove field
  collection.fields.removeById("date2568376179")

  return app.save(collection)
})
