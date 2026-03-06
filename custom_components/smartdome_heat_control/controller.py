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
    """Kernlogik: Reagiert auf UI-Eingaben und Sensorwerte."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        self.hass = hass
        self.config = config
        self._unsub: list[Callable[[], None]] = []

    async def async_start(self) -> None:
        """Listener registrieren."""
        self._unsubscribe_all()

        rooms = self._active_rooms()
        watch_list: set[str] = set()

        main_thermostat = self._as_entity_id(self.config.get(CONF_MAIN_THERMOSTAT))
        main_sensor = self._as_entity_id(self.config.get(CONF_MAIN_SENSOR))

        if main_thermostat:
            watch_list.add(main_thermostat)
        if main_sensor:
            watch_list.add(main_sensor)

        for room in rooms.values():
            sensor = self._as_entity_id(room.get(CONF_ROOM_SENSOR))
            thermostat = self._as_entity_id(room.get(CONF_ROOM_THERMOSTAT))

            if sensor:
                watch_list.add(sensor)
            if thermostat:
                watch_list.add(thermostat)

        if watch_list:
            self._unsub.append(
                async_track_state_change_event(
                    self.hass,
                    list(watch_list),
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

        _LOGGER.debug(
            "SmartHeatingController gestartet, beobachtete Entities: %s",
            sorted(watch_list),
        )

        self._evaluate()

    async def async_stop(self) -> None:
        """Listener entfernen."""
        self._unsubscribe_all()

    def update_config(self, config: dict[str, Any]) -> None:
        """Konfiguration aktualisieren und Controller neu starten."""
        self.config = config
        self.hass.async_create_task(self.async_start())

    def _unsubscribe_all(self) -> None:
        """Alle Listener entfernen."""
        for unsub in self._unsub:
            try:
                unsub()
            except Exception:
                _LOGGER.exception("Fehler beim Entfernen eines Listeners")
        self._unsub.clear()

    def _as_entity_id(self, value: Any) -> str | None:
        """String-Entity-ID normalisieren."""
        return value if isinstance(value, str) and value else None

    def _active_rooms(self) -> dict[str, dict[str, Any]]:
        """Aktive Räume zurückgeben."""
        rooms = self.config.get(CONF_ROOMS, {})
        if not isinstance(rooms, dict):
            return {}

        result: dict[str, dict[str, Any]] = {}
        for room_id, room_cfg in rooms.items():
            if not isinstance(room_id, str) or not isinstance(room_cfg, dict):
                continue
            if room_cfg.get(CONF_ROOM_ENABLED, True):
                result[room_id] = room_cfg

        return result

    def _safe_float(self, value: Any) -> float | None:
        """Float robust parsen."""
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def _get_state_float(self, entity_id: str | None) -> float | None:
        """State-Wert einer Entity als float lesen."""
        if not entity_id:
            return None

        state = self.hass.states.get(entity_id)
        if state is None:
            return None

        if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None

        return self._safe_float(state.state)

    def _get_attr_float(self, entity_id: str | None, attr_name: str) -> float | None:
        """Attribut-Wert einer Entity als float lesen."""
        if not entity_id:
            return None

        state = self.hass.states.get(entity_id)
        if state is None:
            return None

        return self._safe_float(state.attributes.get(attr_name))

    def _in_morning_boost_window(self) -> bool:
        """Prüfen, ob wir im globalen Morgen-Boost-Fenster sind."""
        now = dt_util.now().strftime("%H:%M")
        start = str(
            self.config.get(CONF_MORNING_BOOST_START, DEFAULT_MORNING_BOOST_START)
        )[:5]
        end = str(
            self.config.get(CONF_MORNING_BOOST_END, DEFAULT_MORNING_BOOST_END)
        )[:5]

        if start <= end:
            return start <= now < end

        return now >= start or now < end

    def _is_night_for_room(self, room: dict[str, Any]) -> bool:
        """Prüfen, ob für den Raum Nachtbetrieb gilt."""
        now = dt_util.now().strftime("%H:%M")
        night_start = str(
            room.get(CONF_NIGHT_START, self.config.get(CONF_NIGHT_START, DEFAULT_NIGHT_START))
        )[:5]
        boost_start = str(
            self.config.get(CONF_MORNING_BOOST_START, DEFAULT_MORNING_BOOST_START)
        )[:5]

        # Nacht von z. B. 22:00 bis 05:00
        if night_start > boost_start:
            return now >= night_start or now < boost_start

        return night_start <= now < boost_start

    def _base_target_for_room(self, room: dict[str, Any]) -> float:
        """Basis-Zieltemperatur ohne Boost bestimmen."""
        if self._is_night_for_room(room):
            return float(room.get(CONF_ROOM_TARGET_NIGHT, DEFAULT_TARGET_NIGHT))
        return float(room.get(CONF_ROOM_TARGET_DAY, DEFAULT_TARGET_DAY))

    def _room_temp(self, room: dict[str, Any]) -> float | None:
        """Raumtemperatur über konfigurierten Sensor lesen."""
        sensor_id = self._as_entity_id(room.get(CONF_ROOM_SENSOR))
        temp = self._get_state_float(sensor_id)

        if temp is None and sensor_id:
            _LOGGER.debug("Kein gültiger Temperaturwert für Sensor %s", sensor_id)

        return temp

    def _main_reference_temp(self) -> float | None:
        """Referenztemperatur für das Hauptthermostat lesen.

        Priorität:
        1. explizit gewählter main_sensor
        2. current_temperature des Hauptthermostats
        """
        main_sensor = self._as_entity_id(self.config.get(CONF_MAIN_SENSOR))
        sensor_temp = self._get_state_float(main_sensor)
        if sensor_temp is not None:
            return sensor_temp

        main_thermostat = self._as_entity_id(self.config.get(CONF_MAIN_THERMOSTAT))
        return self._get_attr_float(main_thermostat, "current_temperature")

    def _main_base_target(self, rooms: dict[str, dict[str, Any]]) -> float:
        """Basis-Sollwert des Hauptthermostats.

        Nimmt den höchsten Basis-Sollwert aller aktiven Räume.
        """
        if not rooms:
            return float(DEFAULT_TARGET_DAY)

        return max(self._base_target_for_room(room) for room in rooms.values())

    def _set_temp_if_new(self, entity_id: str, temp: float) -> None:
        """Temperatur nur setzen, wenn sie sich relevant geändert hat."""
        current_target = self._get_attr_float(entity_id, ATTR_TEMPERATURE)
        if current_target is not None and abs(current_target - temp) < 0.1:
            return

        rounded_temp = round(float(temp), 1)
        _LOGGER.debug("Setze %s auf %.1f °C", entity_id, rounded_temp)

        self.hass.async_create_task(
            self.hass.services.async_call(
                CLIMATE_DOMAIN,
                "set_temperature",
                {
                    "entity_id": entity_id,
                    ATTR_TEMPERATURE: rounded_temp,
                },
                blocking=True,
            )
        )

    def _evaluate(self) -> None:
        """Alle Räume prüfen und Solltemperaturen aktualisieren."""
        rooms = self._active_rooms()
        if not rooms:
            _LOGGER.debug("Keine aktiven Räume konfiguriert")
            return

        boost_delta = self._safe_float(
            self.config.get(CONF_BOOST_DELTA, DEFAULT_BOOST_DELTA)
        )
        tolerance = self._safe_float(
            self.config.get(CONF_TOLERANCE, DEFAULT_TOLERANCE)
        )

        if boost_delta is None:
            boost_delta = float(DEFAULT_BOOST_DELTA)
        if tolerance is None:
            tolerance = float(DEFAULT_TOLERANCE)

        in_morning_boost = self._in_morning_boost_window()
        needs_heat: dict[str, bool] = {}

        for room_id, room in rooms.items():
            actual_temp = self._room_temp(room)
            base_target = self._base_target_for_room(room)

            room_needs_heat = (
                actual_temp is not None and actual_temp < (base_target - tolerance)
            )
            needs_heat[room_id] = room_needs_heat

            _LOGGER.debug(
                "Raum %s: ist=%s basis_soll=%.2f braucht_waerme=%s boostfenster=%s",
                room_id,
                f"{actual_temp:.2f}" if actual_temp is not None else "n/a",
                base_target,
                room_needs_heat,
                in_morning_boost,
            )

        any_room_needs_heat = any(needs_heat.values())

        # Hauptthermostat steuern
        main_thermostat = self._as_entity_id(self.config.get(CONF_MAIN_THERMOSTAT))
        if main_thermostat:
            main_base_target = self._main_base_target(rooms)
            main_reference_temp = self._main_reference_temp()

            main_target = main_base_target

            if (
                in_morning_boost
                and any_room_needs_heat
                and main_reference_temp is not None
                and main_reference_temp < (main_base_target - tolerance)
            ):
                main_target = main_base_target + boost_delta

            self._set_temp_if_new(main_thermostat, main_target)

        # Raumthermostate steuern
        for room_id, room in rooms.items():
            thermostat_id = self._as_entity_id(room.get(CONF_ROOM_THERMOSTAT))
            if not thermostat_id:
                continue

            room_base_target = self._base_target_for_room(room)
            room_target = room_base_target

            if in_morning_boost and needs_heat[room_id]:
                room_target = room_base_target + boost_delta

            self._set_temp_if_new(thermostat_id, room_target)

    @callback
    def _on_state_change(self, event: Event) -> None:
        """Bei State-Änderungen neu auswerten."""
        self._evaluate()

    @callback
    def _on_minute_tick(self, now) -> None:
        """Minütliche Zeit-basierte Auswertung."""
        self._evaluate()
