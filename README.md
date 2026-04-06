# Medicine Count & Expiry

Track your medicine inventory and expiry dates directly in Home Assistant.

## Features

- 📋 Track medicines with name, expiry date, quantity, and location
- 🚨 Automatic alerts for expired and expiring-soon medicines
- 🤖 AI-powered label scanning with confidence scores (requires Claude API key)
- 🎨 Colour-coded confidence indicators (green / blue / orange / red)
- 🔍 Search and filter your inventory by name, location, or status
- 📊 Home Assistant sensor entities for automations
- 🃏 Lovelace dashboard card with camera scanning support
- 📬 Daily digest notifications summarising your inventory
- 📋 Slovak package leaflet generation (auto-cached for offline use)
- ✅ Transparent AI extraction metadata (source, timestamp, confidence)

## Quick Setup

1. Install via [HACS](https://hacs.xyz)
2. Restart Home Assistant
3. Go to **Settings → Devices & Services → Add Integration → Medicine Count & Expiry**
4. Follow the 4-step config flow (Claude API key, notifications, storage, defaults)
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
- Per-field confidence scores displayed directly on each medicine card
- Slovak package leaflet summaries (cached for offline access)

### Multi-Step Scanning Workflow

Adding a medicine via the card camera uses a guided 4-step process:

1. **Scan label** – photograph the front of the box; Claude extracts the medicine name and description
2. **Scan / enter expiry** – photograph or manually type the expiry date
3. **Add details** – set location, quantity, and unit
4. **Generate leaflet** *(optional)* – create a Slovak package leaflet summary

### AI Confidence Levels

Each scanned medicine shows the extraction confidence as a colour-coded badge:

| Badge | Confidence | Meaning |
|---|---|---|
| 🟢 **≥ 95%** | Excellent | High-quality scan, data is reliable |
| 🔵 **85 – 94%** | Good | Solid extraction, minor uncertainty |
| 🟠 **75 – 84%** | Fair | Acceptable but worth a manual check |
| 🔴 **< 75%** | Low | Poor image or ambiguous label – verify manually |

Click a medicine in the card to see the full AI extraction details (source, timestamp, per-field confidence).

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
