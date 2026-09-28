# Offline geography

ZIP coordinates/place names in `locations.json` are a subset of the US postal dataset obtained through pgeocode 0.5.0 on 2026-09-25. Source: [GeoNames postal data](https://download.geonames.org/export/zip/), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). They are approximate area centroids, not community addresses.

The named Rochester/Brighton entries are approximate city reference points for the demo. For other regions, supply a reviewed JSON lookup through `GEO_LOOKUP_FILE` with lowercase city/ZIP keys and `[latitude, longitude]` values. Community CSV/Sheets rows may supply `Latitude` and `Longitude` for more precise distance calculation.

The API never silently substitutes Rochester for an unresolved location and never downloads geography data in a request. Unknown locations are returned as warnings. The legacy pgeocode resolver in `src/geo.py` has optional online lookup only when explicitly enabled.
