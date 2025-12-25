/// <reference path="../pb_data/types.d.ts" />
migrate((app) => {
  const collection = app.findCollectionByNameOrId("pbc_3292755704")

  // update collection data
  unmarshal({
    "listRule": "@request.auth.id != null\n",
    "viewRule": "@request.auth.id != null\n"
  }, collection)

  return app.save(collection)
}, (app) => {
  const collection = app.findCollectionByNameOrId("pbc_3292755704")

  // update collection data
  unmarshal({
    "listRule": "",
    "viewRule": null
  }, collection)

  return app.save(collection)
})
