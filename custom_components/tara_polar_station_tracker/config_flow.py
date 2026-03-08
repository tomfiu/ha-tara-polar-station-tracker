"""Config flow for Tara Polar Station Tracker."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    AISSTREAM_WS_URL,
    CONF_API_KEY,
    CONF_DEPARTURE_DATE,
    CONF_ENABLE_WEBCAM,
    CONF_HOME_LAT,
    CONF_HOME_LON,
    CONF_POLL_INTERVAL,
    DEFAULT_DEPARTURE_DATE,
    DEFAULT_ENABLE_WEBCAM,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    TARA_MMSI,
)

_LOGGER = logging.getLogger(__name__)


class TaraPolarStationConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tara Polar Station Tracker."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step — collect AISStream API key."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY]

            if await self._test_api_key(api_key):
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Tara Polar Station",
                    data={CONF_API_KEY: api_key},
                )
            errors["base"] = "invalid_api_key"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_API_KEY): str}
            ),
            errors=errors,
        )

    @staticmethod
    async def _test_api_key(api_key: str) -> bool:
        """Test if the API key is accepted by AISStream."""
        subscription = {
            "APIKey": api_key,
            "BoundingBoxes": [[[-90, -180], [90, 180]]],
            "FiltersShipMMSI": [TARA_MMSI],
            "FilterMessageTypes": ["PositionReport"],
        }

        session = aiohttp.ClientSession()
        try:
            async with asyncio.timeout(15):
                ws = await session.ws_connect(AISSTREAM_WS_URL)
                try:
                    await ws.send_json(subscription)
                    msg = await ws.receive(timeout=10)
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        if "error" in json.dumps(data).lower():
                            return False
                        return True
                    if msg.type == aiohttp.WSMsgType.CLOSE:
                        return False
                    return True
                finally:
                    await ws.close()
        except TimeoutError:
            # Timeout means the key was accepted but no data arrived yet
            return True
        except Exception:
            _LOGGER.debug("API key validation failed", exc_info=True)
            return False
        finally:
            await session.close()

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> TaraPolarStationOptionsFlow:
        """Get the options flow handler."""
        return TaraPolarStationOptionsFlow(config_entry)


class TaraPolarStationOptionsFlow(OptionsFlow):
    """Handle Tara Polar Station options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage integration options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self._config_entry.options

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_POLL_INTERVAL,
                        default=options.get(
                            CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
                        ),
                    ): vol.All(
                        vol.Coerce(int), vol.Range(min=5, max=60)
                    ),
                    vol.Optional(
                        CONF_HOME_LAT,
                        description={
                            "suggested_value": options.get(CONF_HOME_LAT)
                        },
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_HOME_LON,
                        description={
                            "suggested_value": options.get(CONF_HOME_LON)
                        },
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_DEPARTURE_DATE,
                        default=options.get(
                            CONF_DEPARTURE_DATE, DEFAULT_DEPARTURE_DATE
                        ),
                    ): str,
                    vol.Optional(
                        CONF_ENABLE_WEBCAM,
                        default=options.get(
                            CONF_ENABLE_WEBCAM, DEFAULT_ENABLE_WEBCAM
                        ),
                    ): bool,
                }
            ),
        )
