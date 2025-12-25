/// <reference path="../pb_data/types.d.ts" />
migrate((app) => {
  const collection = app.findCollectionByNameOrId("pbc_946965560")

  // update collection data
  unmarshal({
    "name": "regions"
  }, collection)

  return app.save(collection)
}, (app) => {
  const collection = app.findCollectionByNameOrId("pbc_946965560")

  // update collection data
  unmarshal({
    "name": "region"
  }, collection)

  return app.save(collection)
})
