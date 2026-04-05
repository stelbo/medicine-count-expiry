"""Constants for the Medicine Count & Expiry integration."""

DOMAIN = "medicine_count_expiry"
PLATFORMS = ["sensor"]

# Config keys
CONF_CLAUDE_API_KEY = "claude_api_key"
CONF_EXPIRY_WARNING_DAYS = "expiry_warning_days"
CONF_NOTIFICATION_SERVICE = "notification_service"
CONF_DAILY_DIGEST = "daily_digest"
CONF_LOCATIONS = "locations"

# Defaults
DEFAULT_EXPIRY_WARNING_DAYS = 30
DEFAULT_LOCATIONS = ["bathroom", "kitchen", "bedroom", "first_aid_kit"]
DEFAULT_DAILY_DIGEST = False

# Database
DB_FILE = "medicine_count_expiry.db"

# Medicine status
STATUS_EXPIRED = "expired"
STATUS_EXPIRING_SOON = "expiring_soon"
STATUS_GOOD = "good"
STATUS_UNKNOWN = "unknown"

# Events
EVENT_MEDICINE_ADDED = f"{DOMAIN}_medicine_added"
EVENT_MEDICINE_UPDATED = f"{DOMAIN}_medicine_updated"
EVENT_MEDICINE_DELETED = f"{DOMAIN}_medicine_deleted"
EVENT_MEDICINE_EXPIRING = f"{DOMAIN}_medicine_expiring"

# Services
SERVICE_ADD_MEDICINE = "add_medicine"
SERVICE_UPDATE_MEDICINE = "update_medicine"
SERVICE_DELETE_MEDICINE = "delete_medicine"
SERVICE_SCAN_IMAGE = "scan_image"
SERVICE_SEARCH_MEDICINES = "search_medicines"
SERVICE_SEND_DIGEST = "send_digest"

# Attributes
ATTR_MEDICINE_ID = "medicine_id"
ATTR_MEDICINE_NAME = "medicine_name"
ATTR_EXPIRY_DATE = "expiry_date"
ATTR_DESCRIPTION = "description"
ATTR_QUANTITY = "quantity"
ATTR_LOCATION = "location"
ATTR_IMAGE_URL = "image_url"
ATTR_AI_VERIFIED = "ai_verified"
ATTR_CONFIDENCE_SCORE = "confidence_score"
ATTR_ADDED_DATE = "added_date"
ATTR_UPDATED_DATE = "updated_date"
ATTR_STATUS = "status"

# Claude model
CLAUDE_MODEL = "claude-3-5-sonnet-20241022"
CLAUDE_MAX_TOKENS = 1024
