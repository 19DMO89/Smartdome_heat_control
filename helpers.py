"""Helper-Funktionen: Automatische Erkennung von Räumen, Thermostaten und Sensoren."""
from __future__ import annotations

from typing import Any

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.area_registry import async_get as async_get_area_registry
from homeassistant.helpers.device_registry import async_get as async_get_device_registry
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry

from .const import (
    CONF_ROOM_AREA_ID,
    CONF_ROOM_ENABLED,
    CONF_ROOM_LABEL,
    CONF_ROOM_SENSOR,
    CONF_ROOM_TARGET_DAY,
    CONF_ROOM_TARGET_NIGHT,
    CONF_ROOM_THERMOSTAT,
    DEFAULT_TARGET_DAY,
    DEFAULT_TARGET_NIGHT,
)


async def async_discover_rooms(hass: HomeAssistant) -> dict[str, dict]:
    """
    Liest alle HA-Areas aus und findet automatisch passende
    Thermostate (climate.*) und Temperatursensoren pro Raum.

    Gibt ein Dict zurück: { area_id: { label, thermostat, sensor, ... } }
    """
    area_registry   = async_get_area_registry(hass)
    entity_registry = async_get_entity_registry(hass)
    device_registry = async_get_device_registry(hass)

    rooms: dict[str, dict] = {}

    for area in area_registry.async_list_areas():
        area_id   = area.id
        area_name = area.name

        # Alle Entities dieser Area sammeln
        area_entities = [
            e for e in entity_registry.entities.values()
            if _entity_area(e, area_id, device_registry)
        ]

        # Bestes Thermostat (climate.*) finden
        thermostat = _best_entity(
            hass, area_entities,
            domain=CLIMATE_DOMAIN,
            prefer_available=True,
        )

        # Besten Temperatursensor finden
        sensor = _best_sensor(hass, area_entities)

        # Nur Areas einbeziehen, die mindestens ein Thermostat ODER Sensor haben
        if thermostat or sensor:
            rooms[area_id] = {
                CONF_ROOM_LABEL:        area_name,
                CONF_ROOM_AREA_ID:      area_id,
                CONF_ROOM_THERMOSTAT:   thermostat or "",
                CONF_ROOM_SENSOR:       sensor or "",
                CONF_ROOM_TARGET_DAY:   DEFAULT_TARGET_DAY,
                CONF_ROOM_TARGET_NIGHT: DEFAULT_TARGET_NIGHT,
                CONF_ROOM_ENABLED:      True,
            }

    return rooms


def _entity_area(entity, area_id: str, device_registry) -> bool:
    """Prüft ob eine Entity direkt oder über ihr Gerät einer Area gehört."""
    if entity.area_id == area_id:
        return True
    if entity.device_id:
        device = device_registry.async_get(entity.device_id)
        if device and device.area_id == area_id:
            return True
    return False


def _best_entity(
    hass: HomeAssistant,
    entities: list,
    domain: str,
    prefer_available: bool = True,
) -> str | None:
    """Findet die beste (verfügbare) Entity eines bestimmten Domains."""
    candidates = [e for e in entities if e.domain == domain and not e.disabled_by]
    if not candidates:
        return None

    if prefer_available:
        available = [
            e for e in candidates
            if hass.states.get(e.entity_id) and
               hass.states.get(e.entity_id).state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)
        ]
        if available:
            return available[0].entity_id

    return candidates[0].entity_id


def _best_sensor(hass: HomeAssistant, entities: list) -> str | None:
    """
    Findet den besten Temperatursensor:
    Priorität: device_class=temperature → entity_id enthält 'temp' → erster sensor.*
    """
    sensor_entities = [
        e for e in entities
        if e.domain == SENSOR_DOMAIN and not e.disabled_by
    ]

    # 1. Prio: device_class = temperature
    for e in sensor_entities:
        state = hass.states.get(e.entity_id)
        if state and state.attributes.get("device_class") == "temperature":
            if state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                return e.entity_id

    # 2. Prio: entity_id enthält "temp"
    for e in sensor_entities:
        if "temp" in e.entity_id.lower():
            return e.entity_id

    return None


async def async_get_all_thermostats(hass: HomeAssistant) -> list[str]:
    """Alle climate.* Entities zurückgeben."""
    return sorted(
        k for k in hass.states.keys() if k.startswith("climate.")
    )


async def async_get_all_sensors(hass: HomeAssistant) -> list[str]:
    """Alle Temperatursensoren zurückgeben."""
    return sorted([
        entity_id for entity_id, state in hass.states.items()
        if state.attributes.get("device_class") == "temperature"
        or (entity_id.startswith("sensor.") and "temp" in entity_id.lower())
    ])


def deep_merge(base: dict, override: dict) -> dict:
    """Tiefes Zusammenführen zweier Dicts (in-place für base)."""
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            deep_merge(base[k], v)
        else:
            base[k] = v
    return base
