"""Helper-Funktionen für Smartdome Heat Control."""
from __future__ import annotations

from typing import Any

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.area_registry import async_get as async_get_area_registry
from homeassistant.helpers.device_registry import DeviceEntry, async_get as async_get_device_registry
from homeassistant.helpers.entity_registry import EntityEntry, async_get as async_get_entity_registry

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


def _is_state_available(state: State | None) -> bool:
    """Prüfen, ob ein HA-State verfügbar ist."""
    return state is not None and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN)


def _safe_float(value: Any) -> float | None:
    """Wert robust als float parsen."""
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _entity_area(
    entity: EntityEntry,
    area_id: str,
    device_registry,
) -> bool:
    """Prüfen, ob eine Entity direkt oder über ihr Device zu einer Area gehört."""
    if entity.area_id == area_id:
        return True

    if entity.device_id:
        device: DeviceEntry | None = device_registry.async_get(entity.device_id)
        if device and device.area_id == area_id:
            return True

    return False


def _available_entities(
    hass: HomeAssistant,
    entities: list[EntityEntry],
) -> list[EntityEntry]:
    """Nur verfügbare Entities zurückgeben."""
    result: list[EntityEntry] = []
    for entity in entities:
        state = hass.states.get(entity.entity_id)
        if _is_state_available(state):
            result.append(entity)
    return result


def _best_entity(
    hass: HomeAssistant,
    entities: list[EntityEntry],
    domain: str,
    prefer_available: bool = True,
) -> str | None:
    """Beste Entity eines bestimmten Domains finden."""
    candidates = [
        entity
        for entity in entities
        if entity.domain == domain and not entity.disabled_by
    ]
    if not candidates:
        return None

    if prefer_available:
        available = _available_entities(hass, candidates)
        if available:
            return available[0].entity_id

    return candidates[0].entity_id


def _sensor_score(hass: HomeAssistant, entity: EntityEntry) -> tuple[int, int]:
    """Sensor bewerten.

    Höherer Score = besserer Kandidat.
    Score 1: device_class=temperature
    Score 2: state ist numerisch
    Score 3: entity_id enthält 'temp' oder 'temperature'
    """
    score = 0
    state = hass.states.get(entity.entity_id)

    if state and state.attributes.get("device_class") == "temperature":
        score += 100

    if state and _safe_float(state.state) is not None:
        score += 10

    entity_id_lower = entity.entity_id.lower()
    if "temperature" in entity_id_lower:
        score += 3
    elif "temp" in entity_id_lower:
        score += 2

    # Zweites Sortierkriterium für stabile Reihenfolge
    return score, -len(entity.entity_id)


def _best_sensor(
    hass: HomeAssistant,
    entities: list[EntityEntry],
) -> str | None:
    """Besten Temperatursensor in einer Area finden."""
    candidates = [
        entity
        for entity in entities
        if entity.domain == SENSOR_DOMAIN and not entity.disabled_by
    ]
    if not candidates:
        return None

    available_candidates = _available_entities(hass, candidates)
    pool = available_candidates or candidates

    best = sorted(
        pool,
        key=lambda entity: _sensor_score(hass, entity),
        reverse=True,
    )

    top = best[0]
    top_state = hass.states.get(top.entity_id)

    # Falls selbst der "beste" Kandidat keinen brauchbaren Wert liefert,
    # lieber None zurückgeben.
    if top_state is None:
        return None

    if top_state.attributes.get("device_class") == "temperature":
        return top.entity_id

    if _safe_float(top_state.state) is not None:
        return top.entity_id

    return None


async def async_discover_rooms(hass: HomeAssistant) -> dict[str, dict[str, Any]]:
    """HA-Areas analysieren und passende Räume automatisch erzeugen.

    Ergebnisformat:
    {
        area_id: {
            "label": str,
            "area_id": str,
            "thermostat": str,
            "sensor": str,
            "target_day": float,
            "target_night": float,
            "enabled": bool,
        }
    }
    """
    area_registry = async_get_area_registry(hass)
    entity_registry = async_get_entity_registry(hass)
    device_registry = async_get_device_registry(hass)

    rooms: dict[str, dict[str, Any]] = {}

    for area in area_registry.async_list_areas():
        area_id = area.id
        area_name = area.name

        area_entities = [
            entity
            for entity in entity_registry.entities.values()
            if _entity_area(entity, area_id, device_registry)
        ]

        thermostat = _best_entity(
            hass,
            area_entities,
            domain=CLIMATE_DOMAIN,
            prefer_available=True,
        )
        sensor = _best_sensor(hass, area_entities)

        # Nur sinnvolle Räume übernehmen
        if thermostat or sensor:
            rooms[area_id] = {
                CONF_ROOM_LABEL: area_name,
                CONF_ROOM_AREA_ID: area_id,
                CONF_ROOM_THERMOSTAT: thermostat or "",
                CONF_ROOM_SENSOR: sensor or "",
                CONF_ROOM_TARGET_DAY: float(DEFAULT_TARGET_DAY),
                CONF_ROOM_TARGET_NIGHT: float(DEFAULT_TARGET_NIGHT),
                CONF_ROOM_ENABLED: True,
            }

    return rooms


async def async_get_all_thermostats(hass: HomeAssistant) -> list[str]:
    """Alle climate.* Entities zurückgeben."""
    return sorted(
        entity_id
        for entity_id in hass.states.async_entity_ids(CLIMATE_DOMAIN)
    )


async def async_get_all_sensors(hass: HomeAssistant) -> list[str]:
    """Alle brauchbaren Temperatursensoren zurückgeben."""
    result: list[str] = []

    for entity_id in hass.states.async_entity_ids(SENSOR_DOMAIN):
        state = hass.states.get(entity_id)
        if state is None:
            continue

        device_class = state.attributes.get("device_class")
        if device_class == "temperature":
            result.append(entity_id)
            continue

        entity_id_lower = entity_id.lower()
        if (
            entity_id_lower.startswith("sensor.")
            and ("temp" in entity_id_lower or "temperature" in entity_id_lower)
            and _safe_float(state.state) is not None
        ):
            result.append(entity_id)

    return sorted(set(result))


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Zwei Dicts rekursiv zusammenführen.

    `override` überschreibt Werte in `base`.
    """
    for key, value in override.items():
        if (
            key in base
            and isinstance(base[key], dict)
            and isinstance(value, dict)
        ):
            deep_merge(base[key], value)
        else:
            base[key] = value

    return base
