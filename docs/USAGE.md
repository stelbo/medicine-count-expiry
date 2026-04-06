# Usage Guide

## Dashboard Card

After adding the Lovelace resource and setting up the integration, add a card to your dashboard:

```yaml
type: custom:medicine-count-card
```

### Card Features

| Feature | How to use |
|---|---|
| Summary stats | Click a summary tile to filter the list by that status |
| Search | Type in the search box to filter by name, description, or location |
| Filter by status | Use the status dropdown (All / Good / Expiring Soon / Expired) |
| Filter by location | Use the location dropdown |
| Add medicine | Click **＋** to open the add form |
| Scan label | In the add form, click **📷 Scan Label** to start the multi-step scanning workflow (requires Claude API key) |
| Delete medicine | Click **🗑** next to any medicine |
| Refresh | Click **⟳** to reload data |
| View AI details | Click any medicine to see extraction source, timestamp, and per-field confidence |

## Multi-Step Scanning Workflow

When Claude AI is configured, the **📷 Scan Label** button guides you through four steps:

### Step 1 – Scan Label
Photograph the front of the medicine box. Claude extracts:
- Medicine name (e.g. *Paralen 500*)
- Description / dosage form (e.g. *500 mg tablets / paracetamol*)
- Per-field confidence scores

### Step 2 – Scan / Enter Expiry Date
Photograph the expiry date, or type it manually. Accepted formats include:
`MM/YYYY`, `MM-YYYY`, `MM/YY`, `DD/MM/YYYY`, and `YYYY-MM-DD`.
Claude normalises any format to `YYYY-MM-DD`.

### Step 3 – Add Details
Set the storage location, quantity, and unit (e.g. *tablets*, *ml*, *capsules*).

### Step 4 – Generate Leaflet *(optional)*
Generate a concise Slovak-language package leaflet summary.
The leaflet is cached locally and available offline after the first generation.

## AI Confidence Scores

Every medicine added via scanning displays a colour-coded confidence badge:

| Badge | Confidence | What to do |
|---|---|---|
| 🟢 ≥ 95% | Excellent | Data is highly reliable – no action needed |
| 🔵 85 – 94% | Good | Minor uncertainty – spot-check the label |
| 🟠 75 – 84% | Fair | Acceptable – verify name and expiry manually |
| 🔴 < 75% | Low | Poor scan – confirm all fields before saving |

Click the medicine in the card to open the detail view, which shows:
- **Extraction source** – *scanned*, *manual*, or *verified*
- **Extraction timestamp** – when Claude last processed the label
- **Per-field confidence** – separate scores for name, description, and expiry date

> **Tip:** Re-scan in good lighting to improve confidence on low-scoring medicines.

## Slovak Package Leaflets

For any medicine added with a Claude API key configured, you can generate a Slovak-language summary:

1. Open the medicine detail view
2. Click **📋 Generate Leaflet**
3. Wait a few seconds while Claude builds the summary
4. The leaflet is saved locally and shown immediately

The leaflet covers six sections: *Použitie* (use), *Dávkovanie* (dosage), *Vedľajšie účinky* (side effects),
*Varovania* (warnings), *Skladovanie* (storage), and *Interakcie* (interactions).

## HA Services

### `medicine_count_expiry.add_medicine`

```yaml
service: medicine_count_expiry.add_medicine
data:
  medicine_name: "Paracetamol 500mg"
  expiry_date: "2026-06-30"
  description: "Pain relief"
  quantity: 20
  location: "bathroom"
```

### `medicine_count_expiry.update_medicine`

```yaml
service: medicine_count_expiry.update_medicine
data:
  medicine_id: "your-medicine-uuid"
  quantity: 15
  location: "kitchen"
```

### `medicine_count_expiry.delete_medicine`

```yaml
service: medicine_count_expiry.delete_medicine
data:
  medicine_id: "your-medicine-uuid"
```

### `medicine_count_expiry.search_medicines`

Fires a `medicine_count_expiry_search_results` event with matching medicines.

```yaml
service: medicine_count_expiry.search_medicines
data:
  name: "aspirin"
  status: "expiring_soon"
```

### `medicine_count_expiry.send_digest`

Sends a summary notification immediately.

```yaml
service: medicine_count_expiry.send_digest
```

## REST API

All endpoints require HA authentication (use a Long-Lived Access Token).

| Method | URL | Description |
|---|---|---|
| `GET` | `/api/medicine_count_expiry/medicines` | List / search medicines |
| `POST` | `/api/medicine_count_expiry/medicines` | Add a medicine |
| `GET` | `/api/medicine_count_expiry/medicines/{id}` | Get a single medicine |
| `PUT` | `/api/medicine_count_expiry/medicines/{id}` | Update a medicine |
| `DELETE` | `/api/medicine_count_expiry/medicines/{id}` | Delete a medicine |
| `POST` | `/api/medicine_count_expiry/scan` | Scan an image (Claude required) |
| `GET` | `/api/medicine_count_expiry/summary` | Get inventory summary |

### Query parameters for GET `/medicines`

| Parameter | Description |
|---|---|
| `name` | Partial name match |
| `location` | Exact location match |
| `status` | `expired`, `expiring_soon`, or `good` |
| `expiry_before` | ISO date – only medicines expiring on or before this date |
| `expiry_after` | ISO date – only medicines expiring on or after this date |
| `ai_verified` | `true` or `false` |

## Automation Examples

### Alert when a medicine expires

```yaml
automation:
  - alias: "Medicine expired alert"
    trigger:
      - platform: numeric_state
        entity_id: sensor.medicine_expired_count
        above: 0
    action:
      - service: notify.mobile_app_my_phone
        data:
          title: "Medicine Expired!"
          message: "You have {{ states('sensor.medicine_expired_count') }} expired medicine(s)."
```

### Daily digest at 8 AM

```yaml
automation:
  - alias: "Medicine daily digest"
    trigger:
      - platform: time
        at: "08:00:00"
    action:
      - service: medicine_count_expiry.send_digest
```
