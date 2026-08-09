# Ocea Smart Building - Home Assistant Integration

[![hacs][hacs-badge]][hacs-url]
[![release][release-badge]][release-url]
![downloads][downloads-badge]

Home Assistant integration to monitor cold and hot water consumption from [Ocea Smart Building](https://espace-resident.ocea-sb.com) resident portal.

## Features

- **Cold water** and **hot water** consumption in m³
- **Heating** energy (Cetc) in kWh
- **Estimated leak** sensors (cold/hot water, from Ocea's `fuiteEstimee`)
- **Daily long-term statistics** (`ocea_smart_building:*` series, 365-day backfill,
  automatic catch-up after outages) — usable directly in the **Energy dashboard**
- Automatic Azure AD B2C authentication (no headless browser needed)
- Automatic token refresh
- UI-based configuration

> **Note on dates:** Ocea publishes each daily reading on day *J*, but the value is
> the consumption of day *J−1*. The integration shifts statistics back one day so
> consumption is credited to the day it actually happened.

## Installation

### Via HACS (recommended)

1. HACS → Integrations → ⋮ → Custom repositories
2. Add the repository URL, category **Integration**
3. Search for "Ocea Smart Building" → Install
4. Restart Home Assistant

### Manual

Copy `custom_components/ocea_smart_building/` into `config/custom_components/` and restart Home Assistant.

## Configuration

Settings → Devices & Services → Add Integration → "Ocea Smart Building"

- **Email**: your Ocea resident portal email
- **Password**: your Ocea password

Your dwelling is automatically detected from your Ocea account.

## Energy dashboard

In Settings → Dashboards → Energy → Water consumption, pick the **statistics series**
(`Ocea Eau froide` / `Ocea Eau chaude`) rather than the live sensors: the daily series
credit consumption to the right day, while the live sensors jump at poll time.

## Troubleshooting

```yaml
logger:
  logs:
    custom_components.ocea_smart_building: debug
```

<!-- Badge references -->
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[hacs-url]: https://github.com/hacs/integration
[release-badge]: https://img.shields.io/github/v/release/cyberv92/ha_ocea_smart_building
[release-url]: https://github.com/cyberv92/ha_ocea_smart_building/releases
[downloads-badge]: https://img.shields.io/github/downloads/cyberv92/ha_ocea_smart_building/total
