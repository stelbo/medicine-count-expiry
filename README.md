# Medicine Count & Expiry

Track your medicine inventory and expiry dates directly in Home Assistant.

## Features

- 📋 Track medicines with name, expiry date, quantity, and location
- 🚨 Automatic alerts for expired and expiring-soon medicines
- 🤖 Optional Claude AI label scanning and verification
- 🔍 Search and filter your inventory by name, location, or status
- 📊 Home Assistant sensor entities for automations
- 🃏 Lovelace dashboard card with add/delete/search UI
- 📬 Daily digest notifications summarising your inventory

## Quick Setup

1. Install via [HACS](https://hacs.xyz)
2. Restart Home Assistant
3. Go to **Settings → Devices & Services → Add Integration → Medicine Count & Expiry**
4. Follow the 4-step config flow (API key, notifications, storage, defaults)
5. Add the **Medicine Count & Expiry** card to your Lovelace dashboard

## Lovelace Card

The card is automatically registered on startup. Add it to a dashboard via the card picker
or include it manually in YAML:

```yaml
type: custom:medicine-count-card
title: My Medicine Cabinet
```

## AI Features (optional)

Get an [Anthropic Claude API key](https://console.anthropic.com) and enter it during setup to
enable:
- Automatic medicine label scanning from images
- AI verification of medicine name and expiry date
- Normalisation of non-standard expiry date formats

## Sensors Created

| Sensor | Description |
|---|---|
| `sensor.medicine_total_count` | Total medicines tracked |
| `sensor.medicine_expired_count` | Number of expired medicines |
| `sensor.medicine_expiring_soon_count` | Expiring within warning threshold |

## Documentation

Full documentation is in the [docs/](docs/) folder:
- [Installation](docs/INSTALLATION.md)
- [Configuration](docs/CONFIGURATION.md)
- [Usage](docs/USAGE.md)
