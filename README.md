# Heatman – Home Assistant integration

Custom Home Assistant integration for [Heatman](https://github.com/mzperxp/heatman) heating control.

## Installation

- **HACS** (recommended): Add this repo as a custom repository, then install "Heatman".
- **Manual**: Copy the `heatman` folder from `custom_components/` into your Home Assistant `custom_components/` directory.

## Configuration

Configure via **Settings → Devices & services → Integrations → Add integration → Heatman**. You will need your Heatman server URL and a user account (USER or ADMIN).

## Development

This repo is intended to be used as a git submodule of the main Heatman repo so the full API implementation is available when developing. See the parent repo's [integrations/README.md](https://github.com/mzperxp/heatman/blob/master/integrations/README.md).
