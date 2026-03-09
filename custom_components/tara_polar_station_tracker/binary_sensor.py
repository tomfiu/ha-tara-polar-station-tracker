"""Binary sensor platform for Tara Polar Station Tracker."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TaraPolarStationCoordinator


@dataclass(frozen=True, kw_only=True)
class TaraBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describe a Tara binary sensor entity."""

    value_fn: Callable[[dict[str, Any]], bool | None]


BINARY_SENSOR_DESCRIPTIONS: tuple[TaraBinarySensorEntityDescription, ...] = (
    TaraBinarySensorEntityDescription(
        key="in_arctic_circle",
        name="In Arctic Circle",
        icon="mdi:snowflake",
        value_fn=lambda data: data.get("in_arctic_circle"),
    ),
    TaraBinarySensorEntityDescription(
        key="in_polar_day",
        name="In Polar Day",
        icon="mdi:white-balance-sunny",
        value_fn=lambda data: data.get("in_polar_day"),
    ),
    TaraBinarySensorEntityDescription(
        key="in_polar_night",
        name="In Polar Night",
        icon="mdi:weather-night",
        value_fn=lambda data: data.get("in_polar_night"),
    ),
    TaraBinarySensorEntityDescription(
        key="stationary",
        name="Stationary",
        icon="mdi:anchor",
        value_fn=lambda data: data.get("stationary"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensor entities."""
    coordinator: TaraPolarStationCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        TaraBinarySensor(coordinator, description, entry)
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class TaraBinarySensor(
    CoordinatorEntity[TaraPolarStationCoordinator], BinarySensorEntity
):
    """Representation of a Tara Polar Station binary sensor."""

    entity_description: TaraBinarySensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TaraPolarStationCoordinator,
        description: TaraBinarySensorEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Tara Ocean Foundation",
            model="Polar Station",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def is_on(self) -> bool | None:
        """Return the binary sensor state."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
