# Configuration

## Integration Options

Configure via **Settings → Devices & Services → Medicine Count & Expiry → Configure**.

| Option | Key | Default | Description |
|---|---|---|---|
| Claude API Key | `claude_api_key` | *(empty)* | Anthropic API key for AI label scanning & verification. Optional. |
| Expiry Warning Days | `expiry_warning_days` | `30` | Days before expiry to trigger "expiring soon" alerts. Range 1–365. |
| Notification Service | `notification_service` | *(empty)* | HA notify service name (e.g. `mobile_app_my_phone`). |
| Enable Daily Digest | `daily_digest` | `false` | Send a daily summary notification. |

## Obtaining a Claude API Key

1. Sign up at [console.anthropic.com](https://console.anthropic.com).
2. Create an API key in the API Keys section.
3. Paste it into the integration configuration. The key is stored locally in your HA `config/.storage/` directory.

> **Note:** The Claude API key is optional. Without it, AI-based label scanning and verification will be unavailable, but all other features work normally.

## Notification Service

To find your notification service name:
1. Go to **Developer Tools → Services**.
2. Search for `notify` to see all available services.
3. Copy the service name (without the `notify.` prefix, e.g. `mobile_app_my_phone`).

## Lovelace Card Configuration

```yaml
type: custom:medicine-count-card
```

No additional configuration is required. The card auto-discovers data from the integration API.
