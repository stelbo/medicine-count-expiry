"""Constants for the Medicine Count & Expiry integration."""

DOMAIN = "medicine_count_expiry"
PLATFORMS = ["sensor"]

# Config keys
CONF_CLAUDE_API_KEY = "claude_api_key"
CONF_EXPIRY_WARNING_DAYS = "expiry_warning_days"
CONF_NOTIFICATION_SERVICE = "notification_service"
CONF_DAILY_DIGEST = "daily_digest"
CONF_DIGEST_TIME = "digest_time"
CONF_LOCATIONS = "locations"
CONF_AUTO_CLEANUP = "auto_cleanup"
CONF_KEEP_DAYS = "keep_days"
CONF_DEFAULT_LOCATION = "default_location"
CONF_DEFAULT_UNIT = "default_unit"
CONF_ENABLE_CAMERA = "enable_camera"
CONF_CONFIDENCE_THRESHOLD = "confidence_threshold"

# Location presets
LOCATION_PRESETS = ["bathroom", "kitchen", "bedroom", "living room", "other"]

# Unit presets
UNIT_PRESETS = ["tablets", "pills", "ml", "mg", "capsules", "drops", "units"]

# Defaults
DEFAULT_EXPIRY_WARNING_DAYS = 30
DEFAULT_LOCATIONS = ["bathroom", "kitchen", "bedroom", "living room"]
DEFAULT_DAILY_DIGEST = False
DEFAULT_DIGEST_TIME = "08:00:00"
DEFAULT_AUTO_CLEANUP = False
DEFAULT_KEEP_DAYS = 90
DEFAULT_DEFAULT_LOCATION = "bathroom"
DEFAULT_DEFAULT_UNIT = "tablets"
DEFAULT_ENABLE_CAMERA = True
DEFAULT_CONFIDENCE_THRESHOLD = 70

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
CLAUDE_MODEL = "claude-sonnet-4-6"
CLAUDE_MAX_TOKENS = 1024

# Claude API retry configuration
CLAUDE_MAX_RETRIES = 3
CLAUDE_BASE_RETRY_DELAY = 1.0
CLAUDE_MAX_RETRY_DELAY = 30.0
