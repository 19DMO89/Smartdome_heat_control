"""Konstanten für Smartdome Heat Control."""

DOMAIN = "smartdome_heat_control"

DATA_CONTROLLER = "controller"
DATA_ENABLED = "enabled"

PLATFORMS: list[str] = ["switch", "number"]

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
CONF_ROOM_WINDOW_SENSOR = "window_sensor"

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

#Uralub und weg
CONF_VACATION_ENABLED = "vacation_enabled"
CONF_VACATION_TEMPERATURE = "vacation_temperature"
CONF_AWAY_ENABLED = "away_enabled"
CONF_ROOM_AWAY_TEMPERATURE = "away_temperature"
CONF_WINDOW_OPEN_DELAY = "window_open_delay"
CONF_WINDOW_CLOSE_DELAY = "window_close_delay"

DEFAULT_WINDOW_OPEN_DELAY = 120
DEFAULT_WINDOW_CLOSE_DELAY = 60



# Defaults
DEFAULT_ENABLED = True
DEFAULT_BOOST_DELTA = 2.0
DEFAULT_TOLERANCE = 0.5
DEFAULT_NIGHT_START = "22:00"
DEFAULT_MORNING_BOOST_START = "05:00"
DEFAULT_MORNING_BOOST_END = "05:30"
DEFAULT_TARGET_DAY = 21.0
DEFAULT_TARGET_NIGHT = 18.0
DEFAULT_VACATION_ENABLED = False
DEFAULT_VACATION_TEMPERATURE = 14.0
DEFAULT_AWAY_ENABLED = False
DEFAULT_ROOM_AWAY_TEMPERATURE = 17.0
