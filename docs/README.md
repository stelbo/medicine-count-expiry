# Medicine Count & Expiry

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2023.1%2B-blue.svg)](https://www.home-assistant.io)

A [Home Assistant](https://www.home-assistant.io) custom integration (HACS) for tracking your medicine inventory and expiry dates.

## Features

- 📋 **Inventory tracking** – store medicine name, expiry date, quantity, location, and description
- 🚨 **Expiry alerts** – automated notifications for expired and expiring-soon medicines
- 🤖 **AI-powered scanning** – label scanning with per-field confidence scores via Anthropic's Claude
- 🎨 **Colour-coded confidence badges** – green / blue / orange / red indicators on every scanned medicine
- ✅ **Transparent AI metadata** – extraction source, timestamp, and per-field confidence always visible
- 📋 **Slovak package leaflets** – auto-generated summaries cached for offline use
- 🔍 **Search & filter** – find medicines by name, location, or status
- 📊 **HA sensor entities** – three sensor entities exposing total, expired, and expiring-soon counts
- 🌐 **REST API** – full CRUD JSON API for external integrations
- 🃏 **Lovelace card** – custom dashboard card with summary, list, add form, and camera scan

## Quick Start

See [INSTALLATION.md](INSTALLATION.md) for full installation instructions.

1. Add this repository to HACS as a custom repository
2. Install **Medicine Count & Expiry**
3. Restart Home Assistant
4. Go to **Settings → Devices & Services → Add Integration** and search for *Medicine Count & Expiry*
5. *(Optional)* Enter your [Anthropic Claude API key](https://console.anthropic.com) to enable AI scanning

## AI-Powered Medicine Scanning

When a Claude API key is configured the card guides you through a 4-step scanning workflow:

| Step | Action | What Claude does |
|---|---|---|
| 1 | Photograph the label | Extracts medicine name and description |
| 2 | Photograph / type the expiry date | Normalises any date format to YYYY-MM-DD |
| 3 | Add details | Set location, quantity, and unit |
| 4 | Generate leaflet *(optional)* | Creates a Slovak package leaflet summary |

### Confidence Levels

Each medicine card shows a colour-coded confidence badge for AI-extracted data:

| Colour | Range | Meaning |
|---|---|---|
| 🟢 Green | ≥ 95% | Excellent – data is highly reliable |
| 🔵 Blue | 85 – 94% | Good – minor uncertainty |
| 🟠 Orange | 75 – 84% | Fair – worth a manual check |
| 🔴 Red | < 75% | Low – verify the data manually |

Click any medicine in the card to see the full AI extraction details (source, timestamp, per-field confidence).

### Slovak Package Leaflets

When you opt into leaflet generation (step 4), Claude produces a concise Slovak-language summary covering:

- **Použitie** – what the medicine is used for
- **Dávkovanie** – typical adult dosage
- **Vedľajšie účinky** – common side effects
- **Varovania** – main warnings and contraindications
- **Skladovanie** – storage conditions
- **Interakcie** – important drug interactions

Leaflets are cached locally so they remain available without an internet connection.

## Documentation

| Document | Description |
|---|---|
| [INSTALLATION.md](INSTALLATION.md) | Step-by-step installation guide |
| [CONFIGURATION.md](CONFIGURATION.md) | All configuration options |
| [USAGE.md](USAGE.md) | How to use the integration |

## Sensors

| Entity | Description |
|---|---|
| `sensor.medicine_total_count` | Total number of tracked medicines |
| `sensor.medicine_expired_count` | Number of expired medicines |
| `sensor.medicine_expiring_soon_count` | Number of medicines expiring within the warning window |

## Lovelace Card

Add the resource to your dashboard and use `type: custom:medicine-count-card`.

## Contributing

Pull requests are welcome. Please open an issue to discuss significant changes first.

## License

MIT
