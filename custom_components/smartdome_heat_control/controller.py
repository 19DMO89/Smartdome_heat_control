"""Smart Heating Controller – Kernlogik mit 0.5°C Hysterese."""
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
    CONF_NIGHT_START,
    CONF_ROOMS,
    CONF_TOLERANCE,
    DEFAULT_BOOST_DELTA,
    DEFAULT_MORNING_BOOST_END,
    DEFAULT_NIGHT_START,
    DEFAULT_TARGET_DAY,
    DEFAULT_TARGET_NIGHT,
    DEFAULT_TOLERANCE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

class SmartHeatingController:
    """Kernlogik: Einzelraum-Steuerung mit 0.5 Grad Hysterese."""

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        self.hass = hass
        self.config = config
        self._unsub: list = []

    async def async_start(self) -> None:
        """Listener und Zeitsteuerung registrieren."""
        self._unsubscribe_all()

        active_rooms = self._active_rooms()
        sensors = [r["sensor"] for r in active_rooms.values() if r.get("sensor")]
        
        if sensors:
            self._unsub.append(
                async_track_state_change_event(self.hass, sensors, self._on_temp_change)
            )

        # Minütlicher Check für Zeitplan-Wechsel
        self._unsub.append(
            async_track_time_change(self.hass, self._on_minute_tick, second=0)
        )

        _LOGGER.info("Smart Heating Controller gestartet (Hysterese: 0.5°C)")

    async def async_stop(self) -> None:
        self._unsubscribe_all()

    def update_config(self, config: dict[str, Any]) -> None:
        self.config = config
        self.hass.async_create_task(self.async_start())

    def _unsubscribe_all(self) -> None:
        for unsub in self._unsub:
            unsub()
        self._unsub.clear()

    # ── Zeit-Logik ────────────────────────────────────────────────────────────

    def _is_night_for_room(self, room: dict) -> bool:
        """Prüft, ob für einen Raum gerade Nachtzeit ist."""
        now = datetime.now().strftime("%H:%M")
        ns = str(room.get("night_start", self.config.get(CONF_NIGHT_START, DEFAULT_NIGHT_START)))[:5]
        ds = str(room.get("day_start", self.config.get(CONF_MORNING_BOOST_END, DEFAULT_MORNING_BOOST_END)))[:5]
        
        if ns > ds: # Nacht über Mitternacht
            return now >= ns or now < ds
        return ns <= now < ds

    def _target_for_room(self, room: dict) -> float:
        """Zieltemperatur basierend auf Zeitplan."""
        if self._is_night_for_room(room):
            return float(room.get("target_night", DEFAULT_TARGET_NIGHT))
        return float(room.get("target_day", DEFAULT_TARGET_DAY))

    # ── Kern-Logik (Evaluate) ──────────────────────────────────────────────────

    def _evaluate(self) -> None:
        rooms = self._active_rooms()
        if not rooms:
            return

        boost_delta = 2.0  # +2 Grad Erhöhung
        hysterese = 0.5    # 0.5 Grad Puffer
        
        needs_heat = {}

        for rid, room in rooms.items():
            temp = self._room_temp(room)
            target = self._target_for_room(room)
            
            if temp is None:
                needs_heat[rid] = False
                continue

            # Hysterese-Logik: Prüfen ob das Thermostat gerade heizt
            t_id = room.get("thermostat")
            state = self.hass.states.get(t_id) if t_id else None
            is_heating = False
            if state:
                current_set = state.attributes.get(ATTR_TEMPERATURE, 0)
                if current_set > target:
                    is_heating = True

            if is_heating:
                # Heizen bis Ziel exakt erreicht ist
                needs_heat[rid] = temp < target
            else:
                # Einschalten erst bei Ziel - 0.5 Grad
                needs_heat[rid] = temp < (target - hysterese)

        # ── Hauptthermostat Logik ──
        any_cold = any(needs_heat.values())
        main_id = self.config.get(CONF_MAIN_THERMOSTAT)
        main_state = self.hass.states.get(main_id) if main_id else None
        
        if any_cold and main_state:
            # BEDARF: Aktuelle Temperatur am Kessel +2 Grad
            main_current_temp = main_state.attributes.get("current_temperature")
            if main_current_temp is not None:
                final_main = float(main_current_temp) + boost_delta
            else:
                final_main = 24.0 # Fallback
        else:
            # KEIN BEDARF: Rücksprung auf 22 Grad Standby
            final_main = 22.0

        self._main_set_temp_if_new(final_main)

        # ── Einzel-Thermostate setzen ──
        for rid, room in rooms.items():
            t_id = room.get("thermostat")
            if not t_id:
                continue

            target = self._target_for_room(room)
            new_val = (target + boost_delta) if needs_heat[rid] else target
            
            self._set_temp_if_new(t_id, new_val)

    # ── Hilfsfunktionen ───────────────────────────────────────────────────────

    def _active_rooms(self) -> dict:
        return {k: v for k, v in self.config.get(CONF_ROOMS, {}).items() if v.get("enabled", True)}

    def _room_temp(self, room: dict) -> float | None:
        sensor = room.get("sensor")
        if not sensor: return None
        state = self.hass.states.get(sensor)
        if not state or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN): return None
        try: return float(state.state)
        except ValueError: return None

    def _set_temp_if_new(self, entity_id: str, temp: float) -> None:
        """Sende nur Befehle, wenn der Wert sich wirklich ändert."""
        state = self.hass.states.get(entity_id)
        if state:
            current = state.attributes.get(ATTR_TEMPERATURE)
            # KORREKTUR DER ZEILE 174:
            if current is not None and abs(float(current) - float(temp))  None:
        main = self.config.get(CONF_MAIN_THERMOSTAT)
        if main: self._set_temp_if_new(main, temp)

    # ── Event-Handler ─────────────────────────────────────────────────────────

    @callback
    def _on_temp_change(self, event) -> None:
        self._evaluate()

    @callback
    def _on_minute_tick(self, now) -> None:
        self._evaluate()
