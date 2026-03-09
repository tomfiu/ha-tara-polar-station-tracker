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
    CONF_DATA_SOURCE,
    CONF_DEPARTURE_DATE,
    CONF_ENABLE_WEBCAM,
    CONF_HOME_LAT,
    CONF_HOME_LON,
    CONF_POLL_INTERVAL,
    DATALASTIC_API_URL,
    DATA_SOURCES,
    DEFAULT_DATA_SOURCE,
    DEFAULT_DEPARTURE_DATE,
    DEFAULT_ENABLE_WEBCAM,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    SOURCE_AISSTREAM,
    SOURCE_DATALASTIC,
    TARA_MMSI,
)

_LOGGER = logging.getLogger(__name__)


class TaraPolarStationConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Tara Polar Station Tracker."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._selected_source: str = DEFAULT_DATA_SOURCE

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 1 — let the user choose a tracking data source."""
        if user_input is not None:
            self._selected_source = user_input[CONF_DATA_SOURCE]
            if self._selected_source == SOURCE_AISSTREAM:
                return await self.async_step_aisstream()
            if self._selected_source == SOURCE_DATALASTIC:
                return await self.async_step_datalastic()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_DATA_SOURCE, default=DEFAULT_DATA_SOURCE
                    ): vol.In(DATA_SOURCES),
                }
            ),
        )

    # ------------------------------------------------------------------
    # AISStream source
    # ------------------------------------------------------------------

    async def async_step_aisstream(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2a — collect AISStream API key and validate it."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            if await self._test_aisstream_key(api_key):
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Tara Polar Station",
                    data={
                        CONF_DATA_SOURCE: SOURCE_AISSTREAM,
                        CONF_API_KEY: api_key,
                    },
                )
            errors["base"] = "invalid_api_key"

        return self.async_show_form(
            step_id="aisstream",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    @staticmethod
    async def _test_aisstream_key(api_key: str) -> bool:
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
            _LOGGER.debug("AISStream key validation failed", exc_info=True)
            return False
        finally:
            await session.close()

    # ------------------------------------------------------------------
    # Datalastic source
    # ------------------------------------------------------------------

    async def async_step_datalastic(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Step 2b — collect Datalastic API key and validate it."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            if await self._test_datalastic_key(api_key):
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Tara Polar Station",
                    data={
                        CONF_DATA_SOURCE: SOURCE_DATALASTIC,
                        CONF_API_KEY: api_key,
                    },
                )
            errors["base"] = "invalid_api_key"

        return self.async_show_form(
            step_id="datalastic",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )

    @staticmethod
    async def _test_datalastic_key(api_key: str) -> bool:
        """Test if the API key is accepted by the Datalastic API."""
        url = f"{DATALASTIC_API_URL}?api-key={api_key}&mmsi={TARA_MMSI}"
        session = aiohttp.ClientSession()
        try:
            async with asyncio.timeout(15):
                async with session.get(url) as resp:
                    if resp.status == 401 or resp.status == 403:
                        return False
                    if resp.status == 200:
                        return True
                    # 404 / 422 can mean the vessel has no recent data but
                    # the key itself is valid — treat as accepted.
                    return resp.status not in (401, 403)
        except Exception:
            _LOGGER.debug("Datalastic key validation failed", exc_info=True)
            return False
        finally:
            await session.close()

    # ------------------------------------------------------------------
    # Options flow
    # ------------------------------------------------------------------

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
