"""Device tracker platform for Tara Polar Station Tracker.

Exposes the station as a proper HA device tracker so it appears on the
built-in map card with a live position marker.
"""
from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker import SourceType
from homeassistant.components.device_tracker.config_entry import TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import TaraPolarStationCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Tara station device tracker."""
    coordinator: TaraPolarStationCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([TaraStationTracker(coordinator, entry)])


class TaraStationTracker(
    CoordinatorEntity[TaraPolarStationCoordinator], TrackerEntity
):
    """Device tracker that shows the Tara Polar Station on the HA map."""

    _attr_has_entity_name = True
    _attr_name = "Position"
    _attr_icon = "mdi:sail-boat"

    def __init__(
        self,
        coordinator: TaraPolarStationCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the tracker."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_position"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Tara Ocean Foundation",
            model="Polar Station",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def latitude(self) -> float | None:
        """Return current latitude."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("latitude")

    @property
    def longitude(self) -> float | None:
        """Return current longitude."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("longitude")

    @property
    def source_type(self) -> SourceType:
        """Return GPS as the position source."""
        return SourceType.GPS

    @property
    def location_accuracy(self) -> int:
        """Return GPS accuracy (AIS/satellite — report 0 m)."""
        return 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose track history so map cards can draw the drift path."""
        if self.coordinator.data is None:
            return {}
        return {
            "track_points": self.coordinator.data.get("track_history") or [],
        }
