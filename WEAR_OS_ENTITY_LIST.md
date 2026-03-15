# Wear OS: Why climate entities don't appear in "Select entity" / favorites

## If it worked before

If you could select a Heatman climate entity on the watch a week ago and now the list is empty (same HA, same integration codebase), possible explanations:

1. **Tile was configured earlier** – The entity_id was already saved in the tile (e.g. from a previous app version or from the first time you set it up). After you **deleted the tile and re-added it**, you have to choose an entity again, and the list is now empty because of (2).
2. **Companion app update** – A newer Wear build might subscribe only to `supportedDomains` for the entity list; an older build might have loaded climate entities for the thermostat picker differently.
3. **Integration changes** – Our integration may have changed (e.g. `hvac_action` set to `None` when there is no actuator, or removal of a custom `state`). Some clients might hide entities with `hvac_action == null` or invalid state. We can keep our entities “complete” (e.g. always set `hvac_action` to at least `idle` when there are no actuators) so they are less likely to be filtered out by any client.

There is **no way to configure the thermostat tile from the phone** with a full entity list; the docs require configuring it on the watch. So when the watch’s “Select entity” list is empty, the only fix on the app side is to have climate in `supportedDomains` (see below). On our side, we keep the integration correct (e.g. `hvac_action` = `None` when the location has no actuator). If a future client filters by “has hvac_action”, you could try setting `hvac_action` to `idle` when there is no actuator instead of `None` in `_derive_hvac_action` as a local experiment.

## Root cause (in Home Assistant Companion for Android)

The Wear OS app only **loads and keeps** entities whose **domain** is in a fixed list called `supportedDomains`. That list is defined in the **Wear** module:

**File:** `wear/src/main/kotlin/io/homeassistant/companion/android/home/HomePresenterImpl.kt`

```kotlin
companion object {
  val domainsWithNames = mapOf(
    "button" to commonR.string.buttons,
    "cover" to commonR.string.covers,
    "fan" to commonR.string.fans,
    "input_boolean" to commonR.string.input_booleans,
    "input_button" to commonR.string.input_buttons,
    "light" to commonR.string.lights,
    "lock" to commonR.string.locks,
    "switch" to commonR.string.switches,
    "script" to commonR.string.scripts,
    "scene" to commonR.string.scenes,
  )
  val supportedDomains = domainsWithNames.keys.toList()
}
```

**`climate` is not in this list.** So:

1. When the app calls `getEntities()` and then `updateEntityStates(entities)` in `MainViewModel`, it filters with `entities.filter { it.domain in supportedDomains }`. Climate entities are dropped.
2. The thermostat tile "Select entity" screen and favorites both use this same in-memory entity map. So climate entities never appear there.

The Heatman integration (and any other climate entities) are correct; the filtering happens entirely in the Companion app.

## Fix (in home-assistant/android repo)

Add **climate** to `domainsWithNames` (and a string resource for the display name, e.g. thermostats/climate) so that `supportedDomains` includes `"climate"`. Then:

- Climate entities will be loaded and stored.
- They will appear in the thermostat tile "Select entity" picker.
- They can be added as Wear favorites.

### Steps for a PR

1. In **HomePresenterImpl.kt** (Wear module), add to `domainsWithNames`:
   - `"climate" to commonR.string.thermostats` (or add a new string like `climate` / `thermostats` in the common module if it doesn’t exist).
2. Ensure the common module has a string resource for the climate domain (e.g. in `common/src/main/res/values/strings.xml` or the appropriate locale). If there is already a string for thermostats/climate used elsewhere in the app, reuse it.
3. After this change, `supportedDomains` will include `"climate"`, and the Wear app will load and show climate entities in the thermostat tile and in favorites.

### Reference

- MainViewModel: `updateEntityStates()` filters by `supportedDomains`; `entityUpdates()` only subscribes to `getSupportedEntities()` (same filter).
- SetThermostatTileView receives `entities: List<Entity>?` from the same UI state that is populated only with supported domains.
- Issue #2555 and PR #4959 (thermostat tile) did not add climate to `supportedDomains`, so the tile’s entity picker stays empty unless the app is updated.
