"""Config Flow für Smart Heating Controller.

Schritt 1: Hauptthermostat + globale Einstellungen
Schritt 2: Automatisch erkannte Räume bestätigen / anpassen
Schritt 3 (Options): Räume nachträglich verwalten, Einstellungen ändern
"""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_BOOST_DELTA,
    CONF_MAIN_THERMOSTAT,
    CONF_MORNING_BOOST_END,
    CONF_MORNING_BOOST_START,
    CONF_NIGHT_START,
    CONF_ROOMS,
    CONF_TOLERANCE,
    DEFAULT_BOOST_DELTA,
    DEFAULT_MORNING_BOOST_END,
    DEFAULT_MORNING_BOOST_START,
    DEFAULT_NIGHT_START,
    DEFAULT_TOLERANCE,
    DOMAIN,
)
from .helpers import async_discover_rooms


class SmartHeatingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config Flow: Schritt-für-Schritt Einrichtung."""

    VERSION = 1

    def __init__(self):
        self._data: dict = {}
        self._discovered_rooms: dict = {}

    async def async_step_user(self, user_input=None):
        """Schritt 1: Hauptthermostat & globale Parameter."""
        errors = {}

        if user_input is not None:
            self._data.update(user_input)
            # Weiter zu Schritt 2: Räume entdecken
            self._discovered_rooms = await async_discover_rooms(self.hass)
            return await self.async_step_rooms()

        schema = vol.Schema({
            vol.Required(CONF_MAIN_THERMOSTAT): selector.selector({
                "entity": {"domain": "climate"}
            }),
            vol.Optional(CONF_BOOST_DELTA, default=DEFAULT_BOOST_DELTA): selector.selector({
                "number": {"min": 0.5, "max": 5.0, "step": 0.5, "unit_of_measurement": "°C", "mode": "slider"}
            }),
            vol.Optional(CONF_TOLERANCE, default=DEFAULT_TOLERANCE): selector.selector({
                "number": {"min": 0.1, "max": 2.0, "step": 0.1, "unit_of_measurement": "°C", "mode": "slider"}
            }),
            vol.Optional(CONF_NIGHT_START, default=DEFAULT_NIGHT_START): selector.selector({
                "time": {}
            }),
            vol.Optional(CONF_MORNING_BOOST_START, default=DEFAULT_MORNING_BOOST_START): selector.selector({
                "time": {}
            }),
            vol.Optional(CONF_MORNING_BOOST_END, default=DEFAULT_MORNING_BOOST_END): selector.selector({
                "time": {}
            }),
        })

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            description_placeholders={
                "title": "Smart Heating einrichten",
            },
            errors=errors,
        )

    async def async_step_rooms(self, user_input=None):
        """Schritt 2: Erkannte Räume bestätigen."""
        if user_input is not None:
            # Räume übernehmen und Entry erstellen
            self._data[CONF_ROOMS] = self._discovered_rooms
            return self.async_create_entry(
                title="Smart Heating",
                data=self._data,
            )

        discovered = self._discovered_rooms
        room_count = len(discovered)
        room_names = ", ".join(r["label"] for r in discovered.values()) or "Keine"

        schema = vol.Schema({
            vol.Optional("confirm", default=True): selector.selector({
                "boolean": {}
            }),
        })

        return self.async_show_form(
            step_id="rooms",
            data_schema=schema,
            description_placeholders={
                "room_count": str(room_count),
                "room_names": room_names,
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SmartHeatingOptionsFlow(config_entry)


class SmartHeatingOptionsFlow(config_entries.OptionsFlow):
    """Options Flow: Nachträgliche Konfiguration über Einstellungen → Integration."""

    def __init__(self, config_entry):
        self._entry = config_entry
        self._rooms: dict = dict(config_entry.data.get(CONF_ROOMS, {}))
        self._edit_room_id: str | None = None

    async def async_step_init(self, user_input=None):
        """Hauptmenü des Options Flow."""
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
            data_schema=vol.Schema({
                vol.Required("action", default="rooms"): selector.selector({
                    "select": {
                        "options": [
                            {"value": "global",   "label": "⚙️  Globale Einstellungen"},
                            {"value": "rooms",    "label": "🏠 Räume verwalten"},
                            {"value": "discover", "label": "🔍 Räume neu erkennen"},
                        ],
                        "mode": "list",
                    }
                }),
            }),
        )

    async def async_step_global(self, user_input=None):
        """Globale Einstellungen ändern."""
        data = self._entry.data

        if user_input is not None:
            new_data = {**data, **user_input, CONF_ROOMS: self._rooms}
            self.hass.config_entries.async_update_entry(self._entry, data=new_data)
            return self.async_create_entry(title="", data={})

        schema = vol.Schema({
            vol.Required(CONF_MAIN_THERMOSTAT,
                         default=data.get(CONF_MAIN_THERMOSTAT, "")): selector.selector({
                "entity": {"domain": "climate"}
            }),
            vol.Optional(CONF_BOOST_DELTA,
                         default=data.get(CONF_BOOST_DELTA, DEFAULT_BOOST_DELTA)): selector.selector({
                "number": {"min": 0.5, "max": 5.0, "step": 0.5, "unit_of_measurement": "°C", "mode": "slider"}
            }),
            vol.Optional(CONF_TOLERANCE,
                         default=data.get(CONF_TOLERANCE, DEFAULT_TOLERANCE)): selector.selector({
                "number": {"min": 0.1, "max": 2.0, "step": 0.1, "unit_of_measurement": "°C", "mode": "slider"}
            }),
            vol.Optional(CONF_NIGHT_START,
                         default=data.get(CONF_NIGHT_START, DEFAULT_NIGHT_START)): selector.selector({
                "time": {}
            }),
            vol.Optional(CONF_MORNING_BOOST_START,
                         default=data.get(CONF_MORNING_BOOST_START, DEFAULT_MORNING_BOOST_START)): selector.selector({
                "time": {}
            }),
            vol.Optional(CONF_MORNING_BOOST_END,
                         default=data.get(CONF_MORNING_BOOST_END, DEFAULT_MORNING_BOOST_END)): selector.selector({
                "time": {}
            }),
        })

        return self.async_show_form(step_id="global", data_schema=schema)

    async def async_step_rooms_list(self, user_input=None):
        """Raumübersicht – Raum auswählen oder neuen hinzufügen."""
        if user_input is not None:
            action = user_input.get("room_action", "")
            if action == "__add__":
                return await self.async_step_add_room()
            elif action == "__rediscover__":
                return await self.async_step_discover()
            elif action in self._rooms:
                self._edit_room_id = action
                return await self.async_step_edit_room()

        room_options = [
            {"value": room_id, "label": f"✏️  {room['label']}"}
            for room_id, room in self._rooms.items()
        ]
        room_options.append({"value": "__add__",       "label": "➕ Neuen Raum hinzufügen"})
        room_options.append({"value": "__rediscover__","label": "🔍 Räume neu erkennen"})

        return self.async_show_form(
            step_id="rooms_list",
            data_schema=vol.Schema({
                vol.Required("room_action"): selector.selector({
                    "select": {"options": room_options, "mode": "list"}
                }),
            }),
            description_placeholders={"room_count": str(len(self._rooms))},
        )

    async def async_step_edit_room(self, user_input=None):
        """Einen bestehenden Raum bearbeiten."""
        room_id = self._edit_room_id
        room    = self._rooms.get(room_id, {})

        if user_input is not None:
            if user_input.get("delete_room"):
                del self._rooms[room_id]
            else:
                self._rooms[room_id] = {**room, **user_input}
            new_data = {**self._entry.data, CONF_ROOMS: self._rooms}
            self.hass.config_entries.async_update_entry(self._entry, data=new_data)
            return self.async_create_entry(title="", data={})

        schema = vol.Schema({
            vol.Required("label", default=room.get("label", "")): str,
            vol.Optional("thermostat", default=room.get("thermostat", "")): selector.selector({
                "entity": {"domain": "climate", "multiple": False}
            }),
            vol.Optional("sensor", default=room.get("sensor", "")): selector.selector({
                "entity": {"device_class": "temperature", "multiple": False}
            }),
            vol.Optional("target_day", default=room.get("target_day", 21.0)): selector.selector({
                "number": {"min": 15.0, "max": 27.0, "step": 0.5, "unit_of_measurement": "°C", "mode": "slider"}
            }),
            vol.Optional("target_night", default=room.get("target_night", 18.0)): selector.selector({
                "number": {"min": 12.0, "max": 22.0, "step": 0.5, "unit_of_measurement": "°C", "mode": "slider"}
            }),
            vol.Optional("enabled", default=room.get("enabled", True)): selector.selector({
                "boolean": {}
            }),
            vol.Optional("delete_room", default=False): selector.selector({
                "boolean": {}
            }),
        })

        return self.async_show_form(
            step_id="edit_room",
            data_schema=schema,
            description_placeholders={"room_name": room.get("label", room_id)},
        )

    async def async_step_add_room(self, user_input=None):
        """Neuen Raum manuell hinzufügen."""
        if user_input is not None:
            import uuid
            room_id = f"room_{uuid.uuid4().hex[:8]}"
            self._rooms[room_id] = {
                "label":        user_input.get("label", "Neuer Raum"),
                "area_id":      user_input.get("area_id", ""),
                "thermostat":   user_input.get("thermostat", ""),
                "sensor":       user_input.get("sensor", ""),
                "target_day":   user_input.get("target_day", 21.0),
                "target_night": user_input.get("target_night", 18.0),
                "enabled":      True,
            }
            new_data = {**self._entry.data, CONF_ROOMS: self._rooms}
            self.hass.config_entries.async_update_entry(self._entry, data=new_data)
            return self.async_create_entry(title="", data={})

        # Areas für Dropdown anbieten
        from homeassistant.helpers.area_registry import async_get as async_get_area_registry
        area_registry = async_get_area_registry(self.hass)
        area_options = [{"value": "", "label": "— keine Area —"}] + [
            {"value": a.id, "label": a.name}
            for a in area_registry.async_list_areas()
        ]

        schema = vol.Schema({
            vol.Required("label"): str,
            vol.Optional("area_id", default=""): selector.selector({
                "select": {"options": area_options}
            }),
            vol.Optional("thermostat", default=""): selector.selector({
                "entity": {"domain": "climate"}
            }),
            vol.Optional("sensor", default=""): selector.selector({
                "entity": {"device_class": "temperature"}
            }),
            vol.Optional("target_day", default=21.0): selector.selector({
                "number": {"min": 15.0, "max": 27.0, "step": 0.5, "unit_of_measurement": "°C", "mode": "slider"}
            }),
            vol.Optional("target_night", default=18.0): selector.selector({
                "number": {"min": 12.0, "max": 22.0, "step": 0.5, "unit_of_measurement": "°C", "mode": "slider"}
            }),
        })

        return self.async_show_form(step_id="add_room", data_schema=schema)

    async def async_step_discover(self, user_input=None):
        """Räume automatisch neu erkennen und bestehende ergänzen."""
        if user_input is not None:
            if user_input.get("confirm"):
                # Neu erkannte Räume zu bestehenden hinzufügen (nicht überschreiben)
                for room_id, room in self._new_rooms.items():
                    if room_id not in self._rooms:
                        self._rooms[room_id] = room
                new_data = {**self._entry.data, CONF_ROOMS: self._rooms}
                self.hass.config_entries.async_update_entry(self._entry, data=new_data)
            return self.async_create_entry(title="", data={})

        self._new_rooms = await async_discover_rooms(self.hass)
        new_count = sum(1 for rid in self._new_rooms if rid not in self._rooms)
        new_names = ", ".join(
            r["label"] for rid, r in self._new_rooms.items()
            if rid not in self._rooms
        ) or "Keine neuen"

        schema = vol.Schema({
            vol.Optional("confirm", default=True): selector.selector({"boolean": {}}),
        })

        return self.async_show_form(
            step_id="discover",
            data_schema=schema,
            description_placeholders={
                "new_count": str(new_count),
                "new_names": new_names,
            },
      )
