/// <reference path="../pb_data/types.d.ts" />
migrate((app) => {
  const collection = app.findCollectionByNameOrId("pbc_946965560")

  // remove field
  collection.fields.removeById("number1361375778")

  return app.save(collection)
}, (app) => {
  const collection = app.findCollectionByNameOrId("pbc_946965560")

  // add field
  collection.fields.addAt(3, new Field({
    "hidden": false,
    "id": "number1361375778",
    "max": null,
    "min": null,
    "name": "sort",
    "onlyInt": false,
    "presentable": false,
    "required": false,
    "system": false,
    "type": "number"
  }))

  return app.save(collection)
})
