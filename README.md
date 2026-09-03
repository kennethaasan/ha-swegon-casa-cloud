# Swegon CASA Cloud for Home Assistant

An experimental Home Assistant custom integration for selected Swegon CASA
Genius ventilation units connected to the Swegon CASA mobile cloud.

The integration exposes:

- a bounded ventilation-mode selector with language-neutral service values
  (`travelling`, `away`, `home`, `home_plus`, and `boost`) and translated
  English/Norwegian labels;
- the configured summer-mode setting and current summer boost level;
- the current ventilation control source; and
- a binary sensor showing when summer cooling is actively affecting the unit.

Every mode write is allow-listed and read back from the unit before Home
Assistant reports success. Transient modes such as startup and automatic
control are read-only.

## Language support

The config flow, entity names, ventilation modes, summer-mode states, and
control-source states are available in English and Norwegian Bokmål. Home
Assistant displays the selected language, while scripts and automations use the
stable lowercase values documented above.

Version 0.5.0 changes the former English select values (`Home`, `Home +`,
`Boost`, and so on) to their language-neutral equivalents. Update automations
that call `select.select_option` when upgrading from 0.4.x.

## Status and compatibility

This is community software, is not affiliated with Swegon, and uses cloud
interfaces used by the Swegon CASA mobile app. Those interfaces are not part of
the documented Swegon Public API and may change without notice.

It has been tested with:

- Swegon CASA R5 800W
- ventilation-unit software 4.3.1000
- Home Assistant OS

Other CASA Genius models may work but have not yet been verified.

## Installation

### HACS custom repository

1. Open HACS in Home Assistant.
2. Add `https://github.com/kennethaasan/ha-swegon-casa-cloud` as a custom
   integration repository.
3. Install **Swegon CASA Cloud** and restart Home Assistant.
4. Open **Settings → Devices & services → Add integration** and search for
   **Swegon CASA Cloud**.

### Manual installation

Copy `custom_components/swegon_casa_cloud` into Home Assistant's
`custom_components` directory, restart Home Assistant, and add the integration
from the UI.

## Authentication

Setup currently requires a mobile-app API key and a refresh token for your own
Swegon CASA account. This repository deliberately contains neither credentials
nor instructions for extracting vendor secrets. Swegon does not currently
publish a supported consumer authorization flow for these mobile endpoints.

Do not post API keys, refresh tokens, unit identifiers, MQTT connection details,
or diagnostic downloads containing them in an issue.

Swegon's documented, read-only telemetry and alarm API is available separately
at <https://swegoncasa.com/public/swagger-ui/index.html>.

## API references

[`docs/swegon-casa-api.openapi.yaml`](docs/swegon-casa-api.openapi.yaml)
records the published public REST API and the mobile REST routes observed by
this integration. The MQTT transport is documented separately using the
latest stable AsyncAPI specification in
[`docs/swegon-casa-mqtt.asyncapi.yaml`](docs/swegon-casa-mqtt.asyncapi.yaml).
The MQTT document describes the proprietary binary protocol and dynamic AWS
IoT authorizer handshake; it contains no credentials or household identifiers.
Because MQTT payloads are binary rather than JSON, the companion
[`docs/swegon-casa-mqtt-decoding.md`](docs/swegon-casa-mqtt-decoding.md) gives
the byte layout, varint rules, and safe reading examples.

## Safety

Ventilation is building equipment. Keep the physical control panel and official
CASA app available. This integration only writes the operating-mode control
value and does not change commissioning values, airflow calibration, fan limits,
heater settings, or alarm configuration.

Automations should:

- impose a maximum Boost duration;
- avoid overriding Away or Travelling modes;
- stop automatic control when telemetry is stale or an alarm is active; and
- respect later changes made from the panel or official app.

The companion blueprint repository provides a bounded example:
<https://github.com/kennethaasan/ha-alpstuga-swegon-blueprints>.

## Privacy

The integration has no analytics and sends data only to Home Assistant and the
Swegon services needed to operate the configured unit. Home Assistant stores the
submitted credentials in its private config-entry storage.

## Support

Use GitHub issues for reproducible bugs and feature requests. Redact all account,
home, unit, topic, and token information before attaching logs.

## License

Apache-2.0. See [LICENSE](LICENSE).
