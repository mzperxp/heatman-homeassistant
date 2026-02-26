# Heatman – Home Assistant integration

Custom Home Assistant integration for [Heatman](https://github.com/mzperxp/heatman) heating control.

## Installation

- **HACS** (recommended): Add this repo as a custom repository, then install "Heatman".
- **Manual**: Copy the `custom_components/heatman` folder into your Home Assistant `config/custom_components/` directory.

## Configuration

Configure via **Settings → Devices & services → Integrations → Add integration → Heatman**. You will need:

- **Server URL**: Base URL of your Heatman backend, **including port** if not 80 (e.g. `http://192.168.1.7:8080`). If you omit the port and the backend runs on 8080, setup will fail with a connection error.
- **Username** and **Password**: A Heatman user with at least USER role

The integration will validate credentials by calling the Heatman login API.

## Features

- **Config flow**: One-time setup with URL and credentials; duplicate servers are prevented.
- **Sensors per location**: For each Heatman location (room/zone), the integration creates:
  - **Temperature**: current measured temperature (°C)
  - **Setpoint**: current target temperature from the scheduler (°C)
- Data is polled every 60 seconds. Each location appears as a device with two sensors.

## History and statistics

The temperature and setpoint sensors use `state_class: measurement` and are recorded by Home Assistant’s **Recorder** by default, so history and statistics (e.g. in the entity card or **Settings → Dashboards → History**) should work.

If you use a custom **Recorder** `include` list in your configuration, add the `heatman` domain so these entities are recorded:

```yaml
recorder:
  include:
    domains:
      - heatman
      # ... your other domains
```

If history still doesn’t appear, check **Settings → System → Repairs** and the Recorder integration for errors, and ensure the entities show a numeric state (not “unknown”).

## Development

This repo is intended to be used as a git submodule of the main Heatman repo so the full API implementation is available when developing. See the parent repo's [integrations/README.md](https://github.com/mzperxp/heatman/blob/master/integrations/README.md).
