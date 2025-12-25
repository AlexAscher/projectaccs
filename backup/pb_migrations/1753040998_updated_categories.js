/// <reference path="../pb_data/types.d.ts" />
migrate((app) => {
  const collection = app.findCollectionByNameOrId("pbc_3292755704")

  // update collection data
  unmarshal({
    "listRule": "",
    "viewRule": ""
  }, collection)

  return app.save(collection)
}, (app) => {
  const collection = app.findCollectionByNameOrId("pbc_3292755704")

  // update collection data
  unmarshal({
    "listRule": "@request.auth.id = \"ey136465lu4vd40\"\n\n",
    "viewRule": "@request.auth.id = \"ey136465lu4vd40\"\n"
  }, collection)

  return app.save(collection)
})
