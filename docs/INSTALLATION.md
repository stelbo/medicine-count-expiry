# Installation Guide

## Prerequisites

- Home Assistant 2023.1 or later
- [HACS](https://hacs.xyz) installed

## Method 1 – HACS (Recommended)

1. Open HACS in your Home Assistant sidebar.
2. Click **Integrations**.
3. Click the three-dot menu (⋮) in the top right and choose **Custom repositories**.
4. Enter `https://github.com/stelbo/medicine-count-expiry` and select category **Integration**.
5. Click **Add**.
6. Search for **Medicine Count & Expiry** and click **Download**.
7. Restart Home Assistant.

### Add the Lovelace card resource

1. In HACS, go to **Frontend**.
2. Add the same custom repository if not already present.
3. Install **Medicine Count & Expiry Card**.
4. Go to **Settings → Dashboards → Resources** and add:
   - URL: `/hacsfiles/medicine-count-card/medicine-count-card.js`
   - Type: `JavaScript module`

## Method 2 – Manual Installation

1. Download the latest release ZIP from the [Releases page](https://github.com/stelbo/medicine-count-expiry/releases).
2. Copy the `custom_components/medicine_count_expiry` folder into your HA `config/custom_components/` directory.
3. Copy the `www/medicine-count-card/` folder into `config/www/medicine-count-card/`.
4. Add the Lovelace resource (see above, using URL `/local/medicine-count-card/medicine-count-card.js`).
5. Restart Home Assistant.

## Setup the Integration

1. Go to **Settings → Devices & Services**.
2. Click **+ Add Integration**.
3. Search for **Medicine Count & Expiry**.
4. Follow the configuration wizard (see [CONFIGURATION.md](CONFIGURATION.md)).
