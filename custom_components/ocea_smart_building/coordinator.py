"""DataUpdateCoordinator for Ocea Smart Building."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
)
from homeassistant.const import UnitOfEnergy, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util, slugify

from .api import OceaApiClient, OceaAuthError, OceaApiError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

# API fluide -> (data key, statistics unit, display name, has leak estimate)
STATS_FLUIDES = {
    "EauFroide": ("eau_froide", UnitOfVolume.CUBIC_METERS, "Eau froide", True),
    "EauChaude": ("eau_chaude", UnitOfVolume.CUBIC_METERS, "Eau chaude", True),
    "Cetc": ("cetc", UnitOfEnergy.KILO_WATT_HOUR, "Chauffage", False),
}

BACKFILL_DAYS = 365


class OceaDataUpdateCoordinator(DataUpdateCoordinator[dict[str, float]]):
    """Manage fetching Ocea water consumption data."""

    def __init__(
        self, hass: HomeAssistant, client: OceaApiClient, local_id: str
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client
        self.local_id = local_id

    async def _async_update_data(self) -> dict[str, float]:
        """Fetch data from Ocea API (runs sync client in executor)."""
        _LOGGER.debug("Ocea coordinator: starting data fetch")
        try:
            raw_data = await self.hass.async_add_executor_job(
                self.client.get_consumptions
            )
        except OceaAuthError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except OceaApiError as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error: {err}") from err

        result: dict[str, float] = {}
        for item in raw_data:
            fluide = item.get("fluide", "")
            valeur_str = item.get("valeur", "0")
            # Ocea uses comma as decimal separator
            valeur = float(valeur_str.replace(",", "."))

            if fluide == "EauFroide":
                result["eau_froide"] = valeur
            elif fluide == "EauChaude":
                result["eau_chaude"] = valeur
            else:
                result[fluide.lower()] = valeur

        try:
            await self._async_update_daily(result)
        except (OceaAuthError, OceaApiError) as err:
            _LOGGER.warning("Daily statistics update failed: %s", err)

        _LOGGER.debug("Ocea consumption data updated: %s", result)
        return result

    async def _async_update_daily(self, result: dict[str, float]) -> None:
        """Push daily values as long-term statistics and extract leak estimates."""
        today = dt_util.start_of_local_day()
        tz = dt_util.get_default_time_zone()

        for fluide, (key, unit, name, has_leak) in STATS_FLUIDES.items():
            if key not in result:
                continue  # this dwelling has no such meter

            statistic_id = f"{DOMAIN}:{slugify(self.local_id)}_{key}"
            last = await get_instance(self.hass).async_add_executor_job(
                get_last_statistics, self.hass, 1, statistic_id, True, {"sum"}
            )
            if last:
                last_row = last[statistic_id][0]
                last_start = dt_util.as_local(
                    dt_util.utc_from_timestamp(last_row["start"])
                )
                running_sum = float(last_row["sum"] or 0)
                stats_from = last_start + timedelta(days=1)
            else:
                running_sum = 0.0
                stats_from = today - timedelta(days=BACKFILL_DAYS)

            # Fetch at least the last few days so the leak estimate stays fresh
            fetch_from = min(stats_from, today - timedelta(days=3))
            data = await self.hass.async_add_executor_job(
                self.client.get_daily_consumptions,
                fluide,
                fetch_from.isoformat(),
                dt_util.now().isoformat(),
            )

            stats: list[StatisticData] = []
            latest_leak: float | None = None
            for item in data.get("consommations") or []:
                # Ocea dates each reading at publication day; the value is
                # the consumption of the PREVIOUS day — shift back one day.
                day = datetime.fromisoformat(item["date"]).replace(
                    tzinfo=tz
                ) - timedelta(days=1)
                if has_leak and item.get("fuiteEstimee") is not None:
                    latest_leak = float(item["fuiteEstimee"])
                # Skip already-recorded days; shifted days are always complete
                if day < stats_from or day >= today:
                    continue
                valeur = float(item["valeur"])
                running_sum += valeur
                stats.append(
                    StatisticData(start=day, state=valeur, sum=running_sum)
                )

            if stats:
                async_add_external_statistics(
                    self.hass,
                    StatisticMetaData(
                        has_mean=False,
                        has_sum=True,
                        name=f"Ocea {name}",
                        source=DOMAIN,
                        statistic_id=statistic_id,
                        unit_of_measurement=unit,
                    ),
                    stats,
                )
                _LOGGER.debug(
                    "Pushed %d daily statistics for %s", len(stats), statistic_id
                )

            if has_leak and latest_leak is not None:
                result[f"fuite_{key}"] = latest_leak
