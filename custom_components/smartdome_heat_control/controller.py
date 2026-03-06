"""Smart Heating Controller – Kernlogik."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.const import ATTR_TEMPERATURE, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
)

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
    DEFAULT_TARGET_DAY,
    DEFAULT_TARGET_NIGHT,
    DEFAULT_TOLERANCE,
)

_LOGGER = logging.getLogger(__name__)


class SmartHeatingController:
    """Kernlogik: Temperaturüberwachung und Thermostatsteuerung."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        self.hass   = hass
        self.config = config
        self._unsub: list = []

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def async_start(self) -> None:
        """Listener und Zeitsteuerung registrieren."""
        self._unsubscribe_all()

        sensors = [
            room["sensor"]
            for room in self._active_rooms().values()
            if room.get("sensor")
        ]
        if sensors:
            self._unsub.append(
                async_track_state_change_event(self.hass, sensors, self._on_temp_change)
            )

        self._register_time(CONF_NIGHT_START,         DEFAULT_NIGHT_START,         self._on_night_start)
        self._register_time(CONF_MORNING_BOOST_START, DEFAULT_MORNING_BOOST_START, self._on_morning_boost)
        self._register_time(CONF_MORNING_BOOST_END,   DEFAULT_MORNING_BOOST_END,   self._on_day_start)

        _LOGGER.info(
            "Smart Heating gestartet. Räume: %s | Sensoren: %s",
            list(self._active_rooms().keys()), sensors,
        )

    async def async_stop(self) -> None:
        self._unsubscribe_all()

    def update_config(self, config: dict[str, Any]) -> None:
        self.config = config
        self.hass.async_create_task(self.async_start())

    def _unsubscribe_all(self) -> None:
        for unsub in self._unsub:
            unsub()
        self._unsub.clear()

    def _register_time(self, cfg_key: str, default: str, fn) -> None:
        t = self.config.get(cfg_key, default)
        try:
            h, m = map(int, t.split(":"))
        except (ValueError, AttributeError):
            _LOGGER.warning("Smart Heating: Ungültige Zeit für '%s': %s", cfg_key, t)
            return
        self._unsub.append(
            async_track_time_change(self.hass, fn, hour=h, minute=m, second=0)
        )

    # ── Hilfsfunktionen ───────────────────────────────────────────────────────

    def _active_rooms(self) -> dict:
        return {
            k: v for k, v in self.config.get(CONF_ROOMS, {}).items()
            if v.get("enabled", True)
        }

    def _room_temp(self, room: dict) -> float | None:
        sensor = room.get("sensor")
        if not sensor:
            return None
        state = self.hass.states.get(sensor)
        if not state or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        try:
            return float(state.state)
        except ValueError:
            return None

    def _is_night(self) -> bool:
        now = datetime.now().strftime("%H:%M")
        ns  = self.config.get(CONF_NIGHT_START,         DEFAULT_NIGHT_START)
        mb  = self.config.get(CONF_MORNING_BOOST_START, DEFAULT_MORNING_BOOST_START)
        return now >= ns or now < mb

    def _is_morning_boost(self) -> bool:
        now      = datetime.now().strftime("%H:%M")
        mb_start = self.config.get(CONF_MORNING_BOOST_START, DEFAULT_MORNING_BOOST_START)
        mb_end   = self.config.get(CONF_MORNING_BOOST_END,   DEFAULT_MORNING_BOOST_END)
        return mb_start <= now < mb_end

    def _target(self, room: dict) -> float:
        if self._is_night() and not self._is_morning_boost():
            return float(room.get("target_night", DEFAULT_TARGET_NIGHT))
        return float(room.get("target_day", DEFAULT_TARGET_DAY))

    def _set_temp(self, entity_id: str, temp: float) -> None:
        if not entity_id:
            return
        self.hass.async_create_task(
            self.hass.services.async_call(
                CLIMATE_DOMAIN,
                "set_temperature",
                {"entity_id": entity_id, ATTR_TEMPERATURE: round(temp, 1)},
            )
        )

    def _main_set_temp(self, temp: float) -> None:
        main = self.config.get(CONF_MAIN_THERMOSTAT, "")
        if main:
            self._set_temp(main, temp)

    # ── Kernlogik ─────────────────────────────────────────────────────────────

    def _evaluate(self) -> None:
        rooms   = self._active_rooms()
        boost   = float(self.config.get(CONF_BOOST_DELTA, DEFAULT_BOOST_DELTA))
        tol     = float(self.config.get(CONF_TOLERANCE,   DEFAULT_TOLERANCE))

        if not rooms:
            return

        needs_heat: dict[str, bool] = {}
        for key, room in rooms.items():
            temp   = self._room_temp(room)
            target = self._target(room)
            needs_heat[key] = temp is not None and temp < (target - tol)

        any_cold   = any(needs_heat.values())
        max_target = max(self._target(r) for r in rooms.values())

        if any_cold:
            self._main_set_temp(max_target + boost)
            for key, room in rooms.items():
                thermostat = room.get("thermostat", "")
                if not thermostat:
                    continue
                target = self._target(room)
                if needs_heat[key]:
                    self._set_temp(thermostat, target + boost)
                    _LOGGER.debug("Raum %s zu kalt, öffne Ventil auf %.1f°", key, target + boost)
                else:
                    temp      = self._room_temp(room) or target
                    throttled = max(temp - 1.0, target - 2.0)
                    self._set_temp(thermostat, throttled)
        else:
            self._main_set_temp(max_target)
            for room in rooms.values():
                if room.get("thermostat"):
                    self._set_temp(room["thermostat"], self._target(room))

    # ── Event-Handler ─────────────────────────────────────────────────────────

    @callback
    def _on_temp_change(self, event) -> None:
        self._evaluate()

    @callback
    def _on_night_start(self, now) -> None:
        rooms = self._active_rooms()
        if not rooms:
            return
        min_night = min(float(r.get("target_night", DEFAULT_TARGET_NIGHT)) for r in rooms.values())
        self._main_set_temp(min_night)
        for room in rooms.values():
            if room.get("thermostat"):
                self._set_temp(room["thermostat"], float(room.get("target_night", DEFAULT_TARGET_NIGHT)))
        _LOGGER.info("Smart Heating: Nachtmodus aktiviert")

    @callback
    def _on_morning_boost(self, now) -> None:
        rooms = self._active_rooms()
        if not rooms:
            return
        boost      = float(self.config.get(CONF_BOOST_DELTA, DEFAULT_BOOST_DELTA))
        max_target = max(float(r.get("target_day", DEFAULT_TARGET_DAY)) for r in rooms.values())
        self._main_set_temp(max_target + boost)
        for room in rooms.values():
            if room.get("thermostat"):
                self._set_temp(room["thermostat"], float(room.get("target_day", DEFAULT_TARGET_DAY)))
        _LOGGER.info("Smart Heating: Morgen-Boost aktiv")

    @callback
    def _on_day_start(self, now) -> None:
        rooms = self._active_rooms()
        if not rooms:
            return
        max_target = max(float(r.get("target_day", DEFAULT_TARGET_DAY)) for r in rooms.values())
        self._main_set_temp(max_target)
        for room in rooms.values():
            if room.get("thermostat"):
                self._set_temp(room["thermostat"], float(room.get("target_day", DEFAULT_TARGET_DAY)))
        _LOGGER.info("Smart Heating: Tagbetrieb aktiv")
