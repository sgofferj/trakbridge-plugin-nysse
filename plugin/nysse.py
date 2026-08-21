# nysse.py from https://github.com/sgofferj/trakbridge-plugin-nysse.git
#
# Copyright Stefan Gofferje
#
# Licensed under the Gnu General Public License Version 3 or higher (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at https://www.gnu.org/licenses/gpl-3.0.en.html

"""
Nysse (Tampere regional transport) Plugin for TrakBridge
"""

import asyncio
import fnmatch
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, cast

import aiohttp
from plugins.base_plugin import (
    BaseGPSPlugin,
    PluginConfigField,
)
from services.logging_service import get_module_logger

logger = get_module_logger(__name__)

NYSSE_API_URL = "https://data.itsfactory.fi/journeys/api/1"

COT_TYPE_BUS = "a-f-G-E-V-C-M"


class NyssePlugin(BaseGPSPlugin):  # type: ignore[misc]
    """Nysse real-time bus tracking integration"""

    PLUGIN_NAME = "nysse"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._stop_cache: Dict[str, Dict[str, str]] = {}

    @classmethod
    def get_plugin_name(cls) -> str:
        return cls.PLUGIN_NAME

    @property
    def plugin_name(self) -> str:
        return self.PLUGIN_NAME

    @property
    def plugin_metadata(self) -> Dict[str, Any]:
        return {
            "display_name": "Nysse Plugin",
            "description": "Real-time bus tracking for Nysse "
            "(Tampere regional transport)",
            "icon": "fas fa-bus",
            "category": "custom",
            "min_poll_interval": 1,
            "hide_cot_type": True,
            "config_fields": [
                PluginConfigField(
                    name="nysse_line_filter",
                    label="Line Filter",
                    field_type="text",
                    required=False,
                    help_text=(
                        "Comma-separated list of bus line numbers to show "
                        "(e.g., 60,64,3A). Wildcards are supported "
                        "(e.g., 6*). Leave empty for all lines."
                    ),
                ),
            ],
            "help_sections": [
                {
                    "title": "Overview",
                    "content": [
                        "This plugin polls the Nysse (Tampere regional transport) "
                        "real-time vehicle activity API and generates CoT events "
                        "for buses.",
                        "Use the line filter to restrict output to specific bus "
                        "lines. Wildcards (fnmatch style) are supported.",
                    ],
                }
            ],
        }

    def _get_line_filter(self) -> str:
        config = self.get_decrypted_config()
        return cast(str, config.get("nysse_line_filter", "")).strip()

    def _matches_filter(self, line_ref: str, line_filter: str) -> bool:
        """Check if a line matches the configured filter (supports wildcards)."""
        if not line_filter:
            return True
        for pattern in line_filter.split(","):
            pattern = pattern.strip()
            if pattern and fnmatch.fnmatch(line_ref, pattern):
                return True
        return False

    async def _get_stop_info(
        self, session: aiohttp.ClientSession, stop_ref: str
    ) -> Dict[str, str]:
        """
        Fetch stop information (name, municipality) from the Nysse API or cache.
        """
        if stop_ref in self._stop_cache:
            return self._stop_cache[stop_ref]

        url = (
            stop_ref
            if stop_ref.startswith("http")
            else f"{NYSSE_API_URL}/stop-points/{stop_ref}"
        )

        try:
            timeout = aiohttp.ClientTimeout(total=10)
            headers = {"User-Agent": "trakbridge-plugin-nysse"}
            async with session.get(url, headers=headers, timeout=timeout) as response:
                response.raise_for_status()
                data = await response.json(content_type=None)
                if data and isinstance(data.get("body"), list) and data["body"]:
                    stop_data = data["body"][0]
                    name = stop_data.get("name", "Unknown")
                    municipality = stop_data.get("municipality", {}).get(
                        "name", "Unknown"
                    )
                    self._stop_cache[stop_ref] = {
                        "name": name,
                        "city": municipality,
                    }
                    return self._stop_cache[stop_ref]
        except (
            aiohttp.ClientError,
            asyncio.TimeoutError,
            ValueError,
            TypeError,
            AttributeError,
        ) as exc:
            logger.error(f"Nysse: Error fetching stop info for {stop_ref}: {exc}")

        return {"name": "Unknown", "city": "Unknown"}

    async def _process_vehicle(
        self,
        session: aiohttp.ClientSession,
        mvj: Dict[str, Any],
        line_filter: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Process a single monitored vehicle journey from the API response.
        """
        v_ref = mvj.get("vehicleRef")
        l_ref = mvj.get("lineRef")
        loc = mvj.get("vehicleLocation", {})
        lat = loc.get("latitude")
        lon = loc.get("longitude")

        if lat is None or lon is None or v_ref is None or l_ref is None:
            return None

        if not self._matches_filter(l_ref, line_filter):
            return None

        onward_calls = mvj.get("onwardCalls", [])
        ns_name, ns_city, ns_time = "Unknown", "Unknown", "--:--"

        if onward_calls:
            next_call = onward_calls[0]
            if ns_ref := next_call.get("stopPointRef"):
                s_info = await self._get_stop_info(session, ns_ref)
                ns_name, ns_city = s_info["name"], s_info["city"]

            exp_dep = next_call.get("expectedDepartureTime")
            if exp_dep and "T" in exp_dep:
                ns_time = exp_dep.split("T")[1][:5]

        d_name, d_city = "Unknown", "Unknown"
        if ds_name := mvj.get("destinationShortName"):
            d_info = await self._get_stop_info(session, ds_name)
            d_name, d_city = d_info["name"], d_info["city"]

        try:
            speed = float(mvj.get("speed", 0.0)) / 3.6
            bearing = float(mvj.get("bearing", 0.0))
        except (ValueError, TypeError) as exc:
            logger.error(f"Nysse: Error processing vehicle {v_ref}: {exc}")
            return None

        remarks = (
            f"Vehicle: {v_ref}\n"
            f"Line: {l_ref}\n"
            f"Dest: {d_city} {d_name}\n"
            f"Next stop: {ns_city} {ns_name} {ns_time}\n"
            "#NYSSE"
        )

        return {
            "uid": f"nysse-{v_ref}",
            "cot_type": COT_TYPE_BUS,
            "lat": float(lat),
            "lon": float(lon),
            "hae": 0,
            "name": f"NYSSE {l_ref}",
            "speed": speed,
            "course": bearing,
            "description": remarks,
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        }

    async def fetch_locations(
        self, session: aiohttp.ClientSession
    ) -> List[Dict[str, Any]]:
        line_filter = self._get_line_filter()

        try:
            url = (
                f"{NYSSE_API_URL}/vehicle-activity"
                f"?exclude-fields=recordedAtTime&lineRef={line_filter}"
            )
            timeout = aiohttp.ClientTimeout(total=10)
            headers = {"User-Agent": "trakbridge-plugin-nysse"}
            async with session.get(url, headers=headers, timeout=timeout) as response:
                response.raise_for_status()
                data = await response.json(content_type=None)
        except (
            aiohttp.ClientError,
            asyncio.TimeoutError,
            ValueError,
            TypeError,
            AttributeError,
        ) as exc:
            logger.error(f"Nysse: Error polling vehicle activity: {exc}")
            return []

        locations: List[Dict[str, Any]] = []
        if data and isinstance(data.get("body"), list):
            for activity in data["body"]:
                mvj = activity.get("monitoredVehicleJourney")
                if not mvj:
                    continue
                try:
                    location = await self._process_vehicle(session, mvj, line_filter)
                except (
                    aiohttp.ClientError,
                    asyncio.TimeoutError,
                    ValueError,
                    TypeError,
                    AttributeError,
                ) as exc:
                    logger.error(f"Nysse: Error processing vehicle: {exc}")
                    continue
                if location:
                    locations.append(location)

        return locations

    def validate_config(self) -> bool:
        return True

    async def test_connection(self) -> Dict[str, Any]:
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            headers = {"User-Agent": "trakbridge-plugin-nysse"}
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{NYSSE_API_URL}/vehicle-activity",
                    headers=headers,
                    timeout=timeout,
                ) as response:
                    response.raise_for_status()
            return {"success": True, "message": "Nysse API reachable"}
        except Exception as e:  # pylint: disable=broad-exception-caught
            return {"success": False, "message": f"Nysse API error: {e}"}
