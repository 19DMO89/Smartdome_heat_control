"""Config Flow für Smartdome Heat Control."""
from __future__ import annotations

import uuid
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_AWAY_ENABLED,
    CONF_BOOST_DELTA,
    CONF_MAIN_SENSOR,
    CONF_MAIN_THERMOSTAT,
    CONF_MORNING_BOOST_END,
    CONF_MORNING_BOOST_START,
    CONF_ROOM_WINDOW_SENSOR,
    CONF_NIGHT_START,
    CONF_ROOMS,
    CONF_ROOM_AWAY_TEMPERATURE,
    CONF_ROOM_DAY_START,
    CONF_ROOM_ENABLED,
    CONF_ROOM_LABEL,
    CONF_ROOM_NIGHT_START,
    CONF_ROOM_SENSOR,
    CONF_ROOM_TARGET_DAY,
    CONF_ROOM_TARGET_NIGHT,
    CONF_ROOM_THERMOSTAT,
    CONF_TOLERANCE,
    CONF_VACATION_ENABLED,
    CONF_VACATION_TEMPERATURE,
    DEFAULT_AWAY_ENABLED,
    DEFAULT_BOOST_DELTA,
    DEFAULT_MORNING_BOOST_END,
    DEFAULT_MORNING_BOOST_START,
    DEFAULT_NIGHT_START,
    DEFAULT_ROOM_AWAY_TEMPERATURE,
    DEFAULT_TARGET_DAY,
    DEFAULT_TARGET_NIGHT,
    DEFAULT_TOLERANCE,
    DEFAULT_VACATION_ENABLED,
    DEFAULT_VACATION_TEMPERATURE,
    DOMAIN,
)
from .helpers import async_discover_rooms


def _temperature_sensor_selector() -> selector.EntitySelector:
    return selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain="sensor",
            device_class="temperature",
            multiple=False,
        )
    )


def _climate_selector() -> selector.EntitySelector:
    return selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain="climate",
            multiple=False,
        )
    )
    
def _window_sensor_selector() -> selector.EntitySelector:
    return selector.EntitySelector(
        selector.EntitySelectorConfig(
            domain="binary_sensor",
            multiple=False,
        )
    )

def _temp_number_selector(
    minimum: float,
    maximum: float,
    step: float,
) -> selector.NumberSelector:
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=minimum,
            max=maximum,
            step=step,
            unit_of_measurement="°C",
            mode="box",
        )
    )


class SmartdomeHeatControlConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._discovered_rooms: dict[str, dict[str, Any]] = {}

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        if user_input is not None:
            self._data.update(user_input)
            self._discovered_rooms = await async_discover_rooms(self.hass)

            for room_id, room_data in self._discovered_rooms.items():
                if isinstance(room_data, dict):
                    room_data.setdefault(
                        CONF_ROOM_AWAY_TEMPERATURE,
                        DEFAULT_ROOM_AWAY_TEMPERATURE,
                    )

            return await self.async_step_rooms()

        schema = vol.Schema(
            {
                vol.Required(CONF_MAIN_THERMOSTAT): _climate_selector(),
                vol.Optional(CONF_MAIN_SENSOR): _temperature_sensor_selector(),
                vol.Optional(
                    CONF_BOOST_DELTA,
                    default=DEFAULT_BOOST_DELTA,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.5,
                        max=5.0,
                        step=0.5,
                        unit_of_measurement="°C",
                        mode="slider",
                    )
                ),
                
                vol.Optional(
                    CONF_TOLERANCE,
                    default=DEFAULT_TOLERANCE,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.1,
                        max=2.0,
                        step=0.1,
                        unit_of_measurement="°C",
                        mode="slider",
                    )
                ),
                vol.Optional(
                    CONF_NIGHT_START,
                    default=DEFAULT_NIGHT_START,
                ): selector.TimeSelector(),
                vol.Optional(
                    CONF_MORNING_BOOST_START,
                    default=DEFAULT_MORNING_BOOST_START,
                ): selector.TimeSelector(),
                vol.Optional(
                    CONF_MORNING_BOOST_END,
                    default=DEFAULT_MORNING_BOOST_END,
                ): selector.TimeSelector(),
                vol.Optional(
                    CONF_VACATION_ENABLED,
                    default=DEFAULT_VACATION_ENABLED,
                ): bool,
                vol.Optional(
                    CONF_VACATION_TEMPERATURE,
                    default=DEFAULT_VACATION_TEMPERATURE,
                ): _temp_number_selector(5.0, 20.0, 0.5),
                vol.Optional(
                    CONF_AWAY_ENABLED,
                    default=DEFAULT_AWAY_ENABLED,
                ): bool,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema)

    async def async_step_rooms(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        if user_input is not None:
            self._data[CONF_ROOMS] = self._discovered_rooms
            return self.async_create_entry(
                title="Smartdome Heat Control",
                data=self._data,
            )

        room_names = ", ".join(
            room.get(CONF_ROOM_LABEL, room_id)
            for room_id, room in self._discovered_rooms.items()
        ) or "Keine gefunden"

        return self.async_show_form(
            step_id="rooms",
            data_schema=vol.Schema({vol.Required("confirm", default=True): bool}),
            description_placeholders={
                "room_count": str(len(self._discovered_rooms)),
                "room_names": room_names,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "SmartdomeOptionsFlow":
        return SmartdomeOptionsFlow(config_entry)


class SmartdomeOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry
        self._rooms: dict[str, dict[str, Any]] = dict(
            config_entry.data.get(CONF_ROOMS, {})
        )
        self._edit_room_id: str | None = None

        for room_id, room_data in self._rooms.items():
            if isinstance(room_data, dict):
                room_data.setdefault(
                    CONF_ROOM_AWAY_TEMPERATURE,
                    DEFAULT_ROOM_AWAY_TEMPERATURE,
                )

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        if user_input is not None:
            action = user_input.get("action")

            if action == "global":
                return await self.async_step_global()
            if action == "rooms":
                return await self.async_step_rooms_list()
            if action == "discover":
                return await self.async_step_discover()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required("action", default="rooms"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                {"value": "global", "label": "⚙️ Globale Einstellungen"},
                                {"value": "rooms", "label": "🏠 Räume verwalten"},
                                {"value": "discover", "label": "🔎 Räume neu erkennen"},
                            ],
                            mode="list",
                        )
                    ),
                }
            ),
        )

    async def async_step_global(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        data = self._entry.data

        if user_input is not None:
            new_data = {**data, **user_input, CONF_ROOMS: self._rooms}
            self.hass.config_entries.async_update_entry(self._entry, data=new_data)
            return self.async_create_entry(title="", data={})

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_MAIN_THERMOSTAT,
                    default=data.get(CONF_MAIN_THERMOSTAT),
                ): _climate_selector(),
                vol.Optional(
                    CONF_MAIN_SENSOR,
                    default=data.get(CONF_MAIN_SENSOR, ""),
                ): _temperature_sensor_selector(),
                vol.Optional(
                    CONF_BOOST_DELTA,
                    default=data.get(CONF_BOOST_DELTA, DEFAULT_BOOST_DELTA),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.5,
                        max=5.0,
                        step=0.5,
                        unit_of_measurement="°C",
                        mode="slider",
                    )
                ),
                vol.Optional(
                    CONF_TOLERANCE,
                    default=data.get(CONF_TOLERANCE, DEFAULT_TOLERANCE),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.1,
                        max=2.0,
                        step=0.1,
                        unit_of_measurement="°C",
                        mode="slider",
                    )
                ),
                vol.Optional(
                    CONF_NIGHT_START,
                    default=data.get(CONF_NIGHT_START, DEFAULT_NIGHT_START),
                ): selector.TimeSelector(),
                vol.Optional(
                    CONF_MORNING_BOOST_START,
                    default=data.get(
                        CONF_MORNING_BOOST_START,
                        DEFAULT_MORNING_BOOST_START,
                    ),
                ): selector.TimeSelector(),
                vol.Optional(
                    CONF_MORNING_BOOST_END,
                    default=data.get(
                        CONF_MORNING_BOOST_END,
                        DEFAULT_MORNING_BOOST_END,
                    ),
                ): selector.TimeSelector(),
                vol.Optional(
                    CONF_VACATION_ENABLED,
                    default=data.get(
                        CONF_VACATION_ENABLED,
                        DEFAULT_VACATION_ENABLED,
                    ),
                ): bool,
                vol.Optional(
                    CONF_VACATION_TEMPERATURE,
                    default=data.get(
                        CONF_VACATION_TEMPERATURE,
                        DEFAULT_VACATION_TEMPERATURE,
                    ),
                ): _temp_number_selector(5.0, 20.0, 0.5),
                vol.Optional(
                    CONF_AWAY_ENABLED,
                    default=data.get(
                        CONF_AWAY_ENABLED,
                        DEFAULT_AWAY_ENABLED,
                    ),
                ): bool,
            }
        )

        return self.async_show_form(step_id="global", data_schema=schema)

    async def async_step_rooms_list(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        if user_input is not None:
            action = user_input.get("room_action")

            if action == "__add__":
                return await self.async_step_add_room()

            if action in self._rooms:
                self._edit_room_id = action
                return await self.async_step_edit_room()

        room_options = [
            {"value": room_id, "label": f"✏️ {room.get(CONF_ROOM_LABEL, room_id)}"}
            for room_id, room in self._rooms.items()
        ]
        room_options.append({"value": "__add__", "label": "➕ Neuen Raum hinzufügen"})

        return self.async_show_form(
            step_id="rooms_list",
            data_schema=vol.Schema(
                {
                    vol.Required("room_action"): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=room_options, mode="list")
                    )
                }
            ),
        )

    async def async_step_edit_room(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        room_id = self._edit_room_id
        if room_id is None or room_id not in self._rooms:
            return await self.async_step_rooms_list()

        room = self._rooms[room_id]

        if user_input is not None:
            if user_input.get("delete_room"):
                del self._rooms[room_id]
            else:
                self._rooms[room_id] = {
                    **room,
                    CONF_ROOM_LABEL: user_input[CONF_ROOM_LABEL],
                    CONF_ROOM_THERMOSTAT: user_input.get(CONF_ROOM_THERMOSTAT),
                    CONF_ROOM_SENSOR: user_input.get(CONF_ROOM_SENSOR),
                    CONF_ROOM_TARGET_DAY: user_input.get(
                        CONF_ROOM_TARGET_DAY,
                        DEFAULT_TARGET_DAY,
                    ),
                    CONF_ROOM_TARGET_NIGHT: user_input.get(
                        CONF_ROOM_TARGET_NIGHT,
                        DEFAULT_TARGET_NIGHT,
                    ),
                    CONF_ROOM_AWAY_TEMPERATURE: user_input.get(
                        CONF_ROOM_AWAY_TEMPERATURE,
                        DEFAULT_ROOM_AWAY_TEMPERATURE,
                    ),
                    CONF_ROOM_DAY_START: user_input.get(CONF_ROOM_DAY_START, ""),
                    CONF_ROOM_NIGHT_START: user_input.get(CONF_ROOM_NIGHT_START, ""),
                    CONF_ROOM_ENABLED: user_input.get(CONF_ROOM_ENABLED, True),
                    CONF_ROOM_WINDOW_SENSOR: user_input.get(CONF_ROOM_WINDOW_SENSOR),
                }

            new_data = {**self._entry.data, CONF_ROOMS: self._rooms}
            self.hass.config_entries.async_update_entry(self._entry, data=new_data)
            return self.async_create_entry(title="", data={})

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_ROOM_LABEL,
                    default=room.get(CONF_ROOM_LABEL, ""),
                ): str,
                vol.Optional(
                    CONF_ROOM_THERMOSTAT,
                    default=room.get(CONF_ROOM_THERMOSTAT, ""),
                ): _climate_selector(),
                vol.Optional(
                    CONF_ROOM_SENSOR,
                    default=room.get(CONF_ROOM_SENSOR, ""),
                ): _temperature_sensor_selector(),
                vol.Optional(
                    CONF_ROOM_TARGET_DAY,
                    default=room.get(CONF_ROOM_TARGET_DAY, DEFAULT_TARGET_DAY),
                ): _temp_number_selector(5.0, 30.0, 0.5),
                vol.Optional(
                    CONF_ROOM_TARGET_NIGHT,
                    default=room.get(CONF_ROOM_TARGET_NIGHT, DEFAULT_TARGET_NIGHT),
                ): _temp_number_selector(5.0, 30.0, 0.5),
                vol.Optional(
                    CONF_ROOM_AWAY_TEMPERATURE,
                    default=room.get(
                        CONF_ROOM_AWAY_TEMPERATURE,
                        DEFAULT_ROOM_AWAY_TEMPERATURE,
                    ),
                ): _temp_number_selector(5.0, 30.0, 0.5),
                vol.Optional(
                    CONF_ROOM_DAY_START,
                    default=room.get(CONF_ROOM_DAY_START, ""),
                ): selector.TimeSelector(),
                vol.Optional(
                    CONF_ROOM_NIGHT_START,
                    default=room.get(CONF_ROOM_NIGHT_START, ""),
                ): selector.TimeSelector(),
                vol.Optional(
                    CONF_ROOM_ENABLED,
                    default=room.get(CONF_ROOM_ENABLED, True),
                ): bool,
                vol.Optional("delete_room", default=False): bool,
                vol.Optional(
                    CONF_ROOM_WINDOW_SENSOR,
                    default=room.get(CONF_ROOM_WINDOW_SENSOR, ""),
                ): _window_sensor_selector(),
            }
        )

        return self.async_show_form(step_id="edit_room", data_schema=schema)

    async def async_step_add_room(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        if user_input is not None:
            new_room_id = f"room_{uuid.uuid4().hex[:8]}"
            self._rooms[new_room_id] = {
                CONF_ROOM_LABEL: user_input[CONF_ROOM_LABEL],
                CONF_ROOM_THERMOSTAT: user_input.get(CONF_ROOM_THERMOSTAT),
                CONF_ROOM_SENSOR: user_input.get(CONF_ROOM_SENSOR),
                CONF_ROOM_TARGET_DAY: user_input.get(
                    CONF_ROOM_TARGET_DAY,
                    DEFAULT_TARGET_DAY,
                ),
                CONF_ROOM_TARGET_NIGHT: user_input.get(
                    CONF_ROOM_TARGET_NIGHT,
                    DEFAULT_TARGET_NIGHT,
                ),
                CONF_ROOM_AWAY_TEMPERATURE: user_input.get(
                    CONF_ROOM_AWAY_TEMPERATURE,
                    DEFAULT_ROOM_AWAY_TEMPERATURE,
                ),
                CONF_ROOM_DAY_START: user_input.get(CONF_ROOM_DAY_START, ""),
                CONF_ROOM_NIGHT_START: user_input.get(CONF_ROOM_NIGHT_START, ""),
                CONF_ROOM_ENABLED: user_input.get(CONF_ROOM_ENABLED, True),
                CONF_ROOM_WINDOW_SENSOR: user_input.get(CONF_ROOM_WINDOW_SENSOR),
            }

            new_data = {**self._entry.data, CONF_ROOMS: self._rooms}
            self.hass.config_entries.async_update_entry(self._entry, data=new_data)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="add_room",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ROOM_LABEL): str,
                    vol.Optional(CONF_ROOM_THERMOSTAT): _climate_selector(),
                    vol.Optional(CONF_ROOM_SENSOR): _temperature_sensor_selector(),
                    vol.Optional(
                        CONF_ROOM_TARGET_DAY,
                        default=DEFAULT_TARGET_DAY,
                    ): _temp_number_selector(5.0, 30.0, 0.5),
                    vol.Optional(
                        CONF_ROOM_TARGET_NIGHT,
                        default=DEFAULT_TARGET_NIGHT,
                    ): _temp_number_selector(5.0, 30.0, 0.5),
                    vol.Optional(
                        CONF_ROOM_AWAY_TEMPERATURE,
                        default=DEFAULT_ROOM_AWAY_TEMPERATURE,
                    ): _temp_number_selector(5.0, 30.0, 0.5),
                    vol.Optional(CONF_ROOM_DAY_START, default=""): selector.TimeSelector(),
                    vol.Optional(CONF_ROOM_NIGHT_START, default=""): selector.TimeSelector(),
                    vol.Optional(CONF_ROOM_ENABLED, default=True): bool,
                    vol.Optional(CONF_ROOM_WINDOW_SENSOR): _window_sensor_selector(),
                }
            ),
        )

    async def async_step_discover(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        discovered = await async_discover_rooms(self.hass)

        for room_id, room_data in discovered.items():
            if room_id not in self._rooms:
                if isinstance(room_data, dict):
                    room_data.setdefault(
                        CONF_ROOM_AWAY_TEMPERATURE,
                        DEFAULT_ROOM_AWAY_TEMPERATURE,
                    )
                self._rooms[room_id] = room_data

        new_data = {**self._entry.data, CONF_ROOMS: self._rooms}
        self.hass.config_entries.async_update_entry(self._entry, data=new_data)

        return self.async_create_entry(title="", data={})
