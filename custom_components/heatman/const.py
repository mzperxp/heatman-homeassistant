"""Constants for the Heatman integration."""

DOMAIN = "heatman"

CONF_BASE_URL = "base_url"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"

DEFAULT_SCAN_INTERVAL = 60  # seconds

API_PATH_LOGIN = "/api/auth/login"
API_PATH_TREE_WITH_STATE = "/api/locations/tree-with-state"
API_PATH_MANUAL_OVERRIDES = "/api/manual-overrides"
API_PATH_SCENES = "/api/scenes"
API_PATH_SCENE_RULES = "/api/scene-rules"
API_PATH_SYSTEM = "/api/system"

# Default duration for manual overrides created from Home Assistant (in minutes)
DEFAULT_OVERRIDE_DURATION_MINUTES = 240

# Default heating temp when creating a scene rule from HA (backend requires at least one temp)
DEFAULT_SCENE_RULE_HEATING_TEMP = 20.0
