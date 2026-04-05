# Medicine Count & Expiry

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2023.1%2B-blue.svg)](https://www.home-assistant.io)

A [Home Assistant](https://www.home-assistant.io) custom integration (HACS) for tracking your medicine inventory and expiry dates.

## Features

- 📋 **Inventory tracking** – store medicine name, expiry date, quantity, location, and description
- 🚨 **Expiry alerts** – automated notifications for expired and expiring-soon medicines
- 🤖 **Claude AI verification** – optional AI-powered label scanning and data verification via Anthropic's Claude
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
