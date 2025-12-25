/// <reference path="../pb_data/types.d.ts" />
migrate((app) => {
  const collection = app.findCollectionByNameOrId("pbc_2354486458")

  // update collection data
  unmarshal({
    "listRule": "@request.auth.email = \"simple@gmail.com\"",
    "viewRule": "@request.auth.email = \"simple@gmail.com\""
  }, collection)

  return app.save(collection)
}, (app) => {
  const collection = app.findCollectionByNameOrId("pbc_2354486458")

  // update collection data
  unmarshal({
    "listRule": "@request.auth.id != null",
    "viewRule": "@request.auth.id != null"
  }, collection)

  return app.save(collection)
})
