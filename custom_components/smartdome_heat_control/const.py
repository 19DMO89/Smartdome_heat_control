"""Konstanten für Smartdome Heat Control."""

DOMAIN = "smartdome_heat_control"

DATA_CONTROLLER = "controller"
DATA_ENABLED = "enabled"

PLATFORMS = ["switch"]

# Services
SERVICE_UPDATE_CONFIG = "update_config"
SERVICE_ADD_ROOM = "add_room"
SERVICE_REMOVE_ROOM = "remove_room"
SERVICE_RELOAD = "reload"

# Globale Config-Keys
CONF_MAIN_THERMOSTAT = "main_thermostat"
CONF_MAIN_SENSOR = "main_sensor"
CONF_BOOST_DELTA = "boost_delta"
CONF_TOLERANCE = "tolerance"
CONF_NIGHT_START = "night_start"
CONF_MORNING_BOOST_START = "morning_boost_start"
CONF_MORNING_BOOST_END = "morning_boost_end"
CONF_ROOMS = "rooms"

# Room-Keys
CONF_ROOM_LABEL = "label"
CONF_ROOM_AREA_ID = "area_id"
CONF_ROOM_THERMOSTAT = "thermostat"
CONF_ROOM_SENSOR = "sensor"
CONF_ROOM_TARGET_DAY = "target_day"
CONF_ROOM_TARGET_NIGHT = "target_night"
CONF_ROOM_DAY_START = "day_start"
CONF_ROOM_NIGHT_START = "night_start"
CONF_ROOM_ENABLED = "enabled"

# Defaults
DEFAULT_ENABLED = True
DEFAULT_BOOST_DELTA = 2.0
DEFAULT_TOLERANCE = 0.5
DEFAULT_NIGHT_START = "22:00"
DEFAULT_MORNING_BOOST_START = "05:00"
DEFAULT_MORNING_BOOST_END = "05:30"
DEFAULT_TARGET_DAY = 21.0
DEFAULT_TARGET_NIGHT = 18.0
