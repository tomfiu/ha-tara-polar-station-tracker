"""Sensor platform for Tara Polar Station Tracker."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import DEGREE, UnitOfLength, UnitOfSpeed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TaraPolarStationCoordinator


@dataclass(frozen=True, kw_only=True)
class TaraSensorEntityDescription(SensorEntityDescription):
    """Describe a Tara sensor entity."""

    value_fn: Callable[[dict[str, Any]], Any]
    extra_attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


SENSOR_DESCRIPTIONS: tuple[TaraSensorEntityDescription, ...] = (
    TaraSensorEntityDescription(
        key="latitude",
        name="Latitude",
        native_unit_of_measurement=DEGREE,
        suggested_display_precision=4,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:latitude",
        value_fn=lambda data: data.get("latitude"),
    ),
    TaraSensorEntityDescription(
        key="longitude",
        name="Longitude",
        native_unit_of_measurement=DEGREE,
        suggested_display_precision=4,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:longitude",
        value_fn=lambda data: data.get("longitude"),
    ),
    TaraSensorEntityDescription(
        key="speed",
        name="Speed",
        native_unit_of_measurement=UnitOfSpeed.KNOTS,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:speedometer",
        value_fn=lambda data: data.get("speed"),
    ),
    TaraSensorEntityDescription(
        key="course",
        name="Course",
        native_unit_of_measurement=DEGREE,
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:compass",
        value_fn=lambda data: data.get("course"),
    ),
    TaraSensorEntityDescription(
        key="last_report",
        name="Last Report",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:clock-outline",
        value_fn=lambda data: data.get("timestamp"),
    ),
    TaraSensorEntityDescription(
        key="distance_from_home",
        name="Distance from Home",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:map-marker-distance",
        value_fn=lambda data: data.get("distance_from_home"),
    ),
    TaraSensorEntityDescription(
        key="distance_to_north_pole",
        name="Distance to North Pole",
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:earth",
        value_fn=lambda data: data.get("distance_to_north_pole"),
    ),
    TaraSensorEntityDescription(
        key="bearing_from_home",
        name="Bearing from Home",
        native_unit_of_measurement=DEGREE,
        suggested_display_precision=0,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:compass-rose",
        value_fn=lambda data: data.get("bearing_from_home"),
        extra_attrs_fn=lambda data: {
            "compass_direction": data.get("bearing_compass"),
        },
    ),
    TaraSensorEntityDescription(
        key="days_since_departure",
        name="Days Since Departure",
        native_unit_of_measurement="d",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:calendar-clock",
        value_fn=lambda data: data.get("days_since_departure"),
    ),
    TaraSensorEntityDescription(
        key="solar_elevation",
        name="Solar Elevation",
        native_unit_of_measurement=DEGREE,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:weather-sunny",
        value_fn=lambda data: data.get("solar_elevation"),
    ),
    TaraSensorEntityDescription(
        key="mission_phase",
        name="Mission Phase",
        icon="mdi:sail-boat",
        value_fn=lambda data: data.get("mission_phase"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities."""
    coordinator: TaraPolarStationCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        TaraSensor(coordinator, description, entry)
        for description in SENSOR_DESCRIPTIONS
    )


class TaraSensor(
    CoordinatorEntity[TaraPolarStationCoordinator], SensorEntity
):
    """Representation of a Tara Polar Station sensor."""

    entity_description: TaraSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TaraPolarStationCoordinator,
        description: TaraSensorEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
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
    def native_value(self) -> Any:
        """Return the sensor value."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        if (
            self.coordinator.data is None
            or self.entity_description.extra_attrs_fn is None
        ):
            return None
        return self.entity_description.extra_attrs_fn(self.coordinator.data)
