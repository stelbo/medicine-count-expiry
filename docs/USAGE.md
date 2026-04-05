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
| Scan label | In the add form, click **📷 Scan Label** to upload a photo (requires Claude API key) |
| Delete medicine | Click **🗑** next to any medicine |
| Refresh | Click **⟳** to reload data |

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
