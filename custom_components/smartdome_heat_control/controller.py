"""Smart Heating Controller – Kernlogik mit Einzelraum-Zeitplänen."""
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
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

class SmartHeatingController:
    """Kernlogik: Einzelraum-Steuerung und Zeitpläne."""

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

        # Wir prüfen jede Minute, ob ein Raum den Modus (Tag/Nacht) wechseln muss
        self._unsub.append(
            async_track_time_change(self.hass, self._on_minute_tick, second=0)
        )

        _LOGGER.info("Smart Heating Controller gestartet (Einzelraum-Modus aktiv)")

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
        """Prüft, ob für einen spezifischen Raum gerade Nachtzeit ist."""
        now = datetime.now().strftime("%H:%M")
        
        # Raum-Zeiten laden (Fallback auf globale Defaults)
        ns = str(room.get("night_start", self.config.get(CONF_NIGHT_START, DEFAULT_NIGHT_START)))[:5]
        ds = str(room.get("day_start", self.config.get(CONF_MORNING_BOOST_END, DEFAULT_MORNING_BOOST_END)))[:5]
        
        if ns > ds:  # Nacht geht über Mitternacht (z.B. 22:00 bis 06:00)
            return now >= ns or now < ds
        return ns <= now < ds # Nacht liegt im selben Tag (z.B. 08:00 bis 16:00)

    def _target_for_room(self, room: dict) -> float:
        """Gibt die aktuell gültige Zieltemperatur für den Raum zurück."""
        if self._is_night_for_room(room):
            return float(room.get("target_night", DEFAULT_TARGET_NIGHT))
        return float(room.get("target_day", DEFAULT_TARGET_DAY))

    # ── Steuerung ─────────────────────────────────────────────────────────────

    def _evaluate(self) -> None:
        rooms = self._active_rooms()
        if not rooms:
            return

        boost = float(self.config.get(CONF_BOOST_DELTA, DEFAULT_BOOST_DELTA))
        tol   = float(self.config.get(CONF_TOLERANCE, DEFAULT_TOLERANCE))
        
        needs_heat = {}
        max_target = 0.0

        for rid, room in rooms.items():
            temp = self._room_temp(room)
            target = self._target_for_room(room)
            
            # Höchstes Ziel für Hauptthermostat finden
            if target > max_target:
                max_target = target
            
            # Bedarf ermitteln
            needs_heat[rid] = (temp is not None and temp < (target - tol))

        # Hauptthermostat setzen
        any_cold = any(needs_heat.values())
        final_main_temp = (max_target + boost) if any_cold else max_target
        self._main_set_temp(final_main_temp)

        # Einzel-Thermostate setzen
        for rid, room in rooms.items():
            thermostat = room.get("thermostat")
            if not thermostat:
                continue

            target = self._target_for_room(room)
            
            if needs_heat[rid]:
                # Raum braucht Wärme -> voll auf (Soll + Boost)
                self._set_temp(thermostat, target + boost)
            else:
                # Raum warm genug -> Exakt auf Zieltemperatur (Nachtabsenkung erzwingen)
                self._set_temp(thermostat, target)

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

    def _set_temp(self, entity_id: str, temp: float) -> None:
        self.hass.async_create_task(
            self.hass.services.async_call(
                CLIMATE_DOMAIN, "set_temperature",
                {"entity_id": entity_id, ATTR_TEMPERATURE: round(temp, 1)},
            )
        )

    def _main_set_temp(self, temp: float) -> None:
        main = self.config.get(CONF_MAIN_THERMOSTAT)
        if main: self._set_temp(main, temp)

    # ── Event-Handler ─────────────────────────────────────────────────────────

    @callback
    def _on_temp_change(self, event) -> None:
        self._evaluate()

    @callback
    def _on_minute_tick(self, now) -> None:
        """Prüft minütlich, ob ein Raum in den Nacht/Tag Modus gewechselt ist."""
        self._evaluate()
