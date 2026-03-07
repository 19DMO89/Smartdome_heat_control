"""Smart Heating Controller – Kernlogik."""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.const import ATTR_TEMPERATURE, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.util import dt as dt_util

from .const import (
    CONF_BOOST_DELTA,
    CONF_MAIN_SENSOR,
    CONF_MAIN_THERMOSTAT,
    CONF_MORNING_BOOST_END,
    CONF_MORNING_BOOST_START,
    CONF_NIGHT_START,
    CONF_ROOMS,
    CONF_ROOM_ENABLED,
    CONF_ROOM_SENSOR,
    CONF_ROOM_TARGET_DAY,
    CONF_ROOM_TARGET_NIGHT,
    CONF_ROOM_THERMOSTAT,
    CONF_TOLERANCE,
    DEFAULT_BOOST_DELTA,
    DEFAULT_MORNING_BOOST_END,
    DEFAULT_MORNING_BOOST_START,
    DEFAULT_NIGHT_START,
    DEFAULT_TARGET_DAY,
    DEFAULT_TARGET_NIGHT,
    DEFAULT_TOLERANCE,
)

_LOGGER = logging.getLogger(__name__)


class SmartHeatingController:
    """Kernlogik: Reagiert auf Sensorwerte und steuert Thermostate."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        self.hass = hass
        self.config = config
        self._enabled = True
        self._unsub: list[Callable] = []

    async def async_start(self) -> None:
        """Listener registrieren."""
        self._unsubscribe_all()

        if not self._enabled:
            return

        watch_entities: set[str] = set()

        main_t = self.config.get(CONF_MAIN_THERMOSTAT)
        main_s = self.config.get(CONF_MAIN_SENSOR)

        if main_t:
            watch_entities.add(main_t)

        if main_s:
            watch_entities.add(main_s)

        for room in self._active_rooms().values():
            if room.get(CONF_ROOM_SENSOR):
                watch_entities.add(room[CONF_ROOM_SENSOR])

            if room.get(CONF_ROOM_THERMOSTAT):
                watch_entities.add(room[CONF_ROOM_THERMOSTAT])

        if watch_entities:
            self._unsub.append(
                async_track_state_change_event(
                    self.hass,
                    list(watch_entities),
                    self._on_state_change,
                )
            )

        self._unsub.append(
            async_track_time_change(
                self.hass,
                self._on_minute_tick,
                second=0,
            )
        )

        _LOGGER.debug("SmartHeatingController gestartet")

        self._evaluate()

    async def async_stop(self) -> None:
        """Controller stoppen."""
        self._unsubscribe_all()

    def set_enabled(self, enabled: bool) -> None:
        """Controller aktivieren / deaktivieren."""
        self._enabled = enabled

        if not enabled:
            self._unsubscribe_all()
            _LOGGER.info("Smart Heating Controller deaktiviert")
            return

        _LOGGER.info("Smart Heating Controller aktiviert")
        self.hass.async_create_task(self.async_start())

    def update_config(self, config: dict[str, Any]) -> None:
        """Neue Konfiguration übernehmen."""
        self.config = config

        if self._enabled:
            self.hass.async_create_task(self.async_start())

    def _unsubscribe_all(self) -> None:
        """Alle Listener entfernen."""
        for unsub in self._unsub:
            try:
                unsub()
            except Exception:
                pass

        self._unsub.clear()

    def _active_rooms(self) -> dict[str, dict[str, Any]]:
        """Aktive Räume zurückgeben."""
        rooms = self.config.get(CONF_ROOMS, {})

        return {
            room_id: room
            for room_id, room in rooms.items()
            if room.get(CONF_ROOM_ENABLED, True)
        }

    def _safe_float(self, value: Any) -> float | None:
        """Float robust parsen."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _get_state_float(self, entity_id: str | None) -> float | None:
        """State als float lesen."""
        if not entity_id:
            return None

        state = self.hass.states.get(entity_id)

        if not state:
            return None

        if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None

        return self._safe_float(state.state)

    def _get_attr_float(self, entity_id: str, attr: str) -> float | None:
        """Attribut als float lesen."""
        state = self.hass.states.get(entity_id)

        if not state:
            return None

        return self._safe_float(state.attributes.get(attr))

    def _in_morning_boost_window(self) -> bool:
        """Morgen Boost aktiv?"""
        now = dt_util.now().strftime("%H:%M")

        start = self.config.get(CONF_MORNING_BOOST_START, DEFAULT_MORNING_BOOST_START)
        end = self.config.get(CONF_MORNING_BOOST_END, DEFAULT_MORNING_BOOST_END)

        if start <= end:
            return start <= now < end

        return now >= start or now < end

    def _is_night(self) -> bool:
        """Nachtbetrieb aktiv?"""
        now = dt_util.now().strftime("%H:%M")

        night = self.config.get(CONF_NIGHT_START, DEFAULT_NIGHT_START)
        boost = self.config.get(CONF_MORNING_BOOST_START, DEFAULT_MORNING_BOOST_START)

        if night > boost:
            return now >= night or now < boost

        return night <= now < boost

    def _room_temp(self, room: dict[str, Any]) -> float | None:
        """Raumtemperatur lesen."""
        return self._get_state_float(room.get(CONF_ROOM_SENSOR))

    def _base_target_for_room(self, room: dict[str, Any]) -> float:
        """Solltemperatur ohne Boost."""
        if self._is_night():
            return float(room.get(CONF_ROOM_TARGET_NIGHT, DEFAULT_TARGET_NIGHT))

        return float(room.get(CONF_ROOM_TARGET_DAY, DEFAULT_TARGET_DAY))

    def _main_reference_temp(self) -> float | None:
        """Temperatur für Hauptthermostat."""
        main_sensor = self.config.get(CONF_MAIN_SENSOR)

        if main_sensor:
            val = self._get_state_float(main_sensor)
            if val is not None:
                return val

        main_thermostat = self.config.get(CONF_MAIN_THERMOSTAT)

        if main_thermostat:
            return self._get_attr_float(main_thermostat, "current_temperature")

        return None

    def _set_temp_if_new(self, entity_id: str, temp: float) -> None:
        """Temperatur setzen wenn nötig."""
        current = self._get_attr_float(entity_id, ATTR_TEMPERATURE)

        if current is not None and abs(current - temp) < 0.1:
            return

        self.hass.async_create_task(
            self.hass.services.async_call(
                CLIMATE_DOMAIN,
                "set_temperature",
                {
                    "entity_id": entity_id,
                    ATTR_TEMPERATURE: round(temp, 1),
                },
                blocking=True,
            )
        )

    def _evaluate(self) -> None:
        """Heizbedarf berechnen."""
        if not self._enabled:
            return

        rooms = self._active_rooms()

        if not rooms:
            return

        boost_delta = self.config.get(CONF_BOOST_DELTA, DEFAULT_BOOST_DELTA)
        tolerance = self.config.get(CONF_TOLERANCE, DEFAULT_TOLERANCE)

        needs_heat: dict[str, bool] = {}

        for room_id, room in rooms.items():
            temp = self._room_temp(room)
            target = self._base_target_for_room(room)

            needs_heat[room_id] = (
                temp is not None and temp < (target - tolerance)
            )

        any_room_needs_heat = any(needs_heat.values())

        main_t = self.config.get(CONF_MAIN_THERMOSTAT)

        if main_t:
            base_target = max(
                self._base_target_for_room(room) for room in rooms.values()
            )

            main_temp = self._main_reference_temp()

            target = base_target

            if (
                any_room_needs_heat
                and main_temp is not None
                and main_temp < base_target - tolerance
                and self._in_morning_boost_window()
            ):
                target = base_target + boost_delta

            self._set_temp_if_new(main_t, target)

        for room_id, room in rooms.items():
            thermostat = room.get(CONF_ROOM_THERMOSTAT)

            if not thermostat:
                continue

            base = self._base_target_for_room(room)

            if needs_heat[room_id] and self._in_morning_boost_window():
                base += boost_delta

            self._set_temp_if_new(thermostat, base)

    @callback
    def _on_state_change(self, event: Event) -> None:
        """State Change Trigger."""
        self._evaluate()

    @callback
    def _on_minute_tick(self, now) -> None:
        """Minütlicher Check."""
        self._evaluate()
