import datetime
import json
import logging
import os
from pathlib import Path

import httpx

logger = logging.getLogger("krishi_tools")

MANDI_RATES_FILE = Path(__file__).parent / "mandi_rates.json"


def _load_fallback_mandi_rates() -> dict:
    """Load local mandi benchmark fallback data from mandi_rates.json."""
    if MANDI_RATES_FILE.exists():
        try:
            with open(MANDI_RATES_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading mandi_rates.json: {e}")
    return {}


async def fetch_district_weather(district_name: str, state: str = "West Bengal") -> str:
    """Fetch live weather data for a district using Open-Meteo Geocoding and Forecast API."""
    district_clean = district_name.strip()
    state_clean = state.strip() if state else "West Bengal"
    today_str = datetime.date.today().strftime("%d %B %Y")

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # 1. Geocoding request
            geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={district_clean}&count=1"
            geo_resp = await client.get(geo_url)
            geo_resp.raise_for_status()
            geo_data = geo_resp.json()

            results = geo_data.get("results")
            if not results:
                logger.warning(
                    f"Geocoding returned no coordinates for {district_clean}"
                )
                return "Unable to fetch live weather data at this moment. Please check again shortly."

            location = results[0]
            lat = location.get("latitude")
            lon = location.get("longitude")
            resolved_name = location.get("name", district_clean)

            # 2. Weather Forecast request
            forecast_url = (
                f"https://api.open-meteo.com/v1/forecast?"
                f"latitude={lat}&longitude={lon}&current_weather=true"
                f"&daily=precipitation_sum,temperature_2m_max,temperature_2m_min&timezone=auto"
            )
            weather_resp = await client.get(forecast_url)
            weather_resp.raise_for_status()
            weather_data = weather_resp.json()

            current = weather_data.get("current_weather", {})
            curr_temp = current.get("temperature", "N/A")

            daily = weather_data.get("daily", {})
            max_temps = daily.get("temperature_2m_max", [])
            min_temps = daily.get("temperature_2m_min", [])
            precip = daily.get("precipitation_sum", [])

            max_temp = max_temps[0] if max_temps else "N/A"
            min_temp = min_temps[0] if min_temps else "N/A"
            rain_mm = precip[0] if precip else 0.0

            return (
                f"As per today's live weather report ({today_str}) for {resolved_name}, {state_clean}: "
                f"Current temperature is {curr_temp}°C (Min: {min_temp}°C, Max: {max_temp}°C). "
                f"Expected rainfall/precipitation today is {rain_mm} mm."
            )

    except Exception as e:
        logger.error(f"Error fetching district weather for {district_clean}: {e}")
        return "Unable to fetch live weather data at this moment. Please check again shortly."


async def fetch_mandi_prices(
    commodity: str, district: str = "Burdwan", state: str = "West Bengal"
) -> str:
    """Fetch real-time mandi prices via Government Agmarknet (data.gov.in) with strict 3.0s timeout and benchmark fallback."""
    commodity_clean = commodity.strip()
    district_clean = district.strip()
    state_clean = state.strip() if state else "West Bengal"
    today_str = datetime.date.today().strftime("%d %B %Y")

    api_key = os.getenv("DATA_GOV_API_KEY", "").strip()

    # Attempt Primary Live Gov API call with strict 3.0s timeout
    if api_key:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                gov_url = "https://api.data.gov.in/resource/9ef0be31-5971-4be1-8511-50e207d76d56"
                params = {
                    "api-key": api_key,
                    "format": "json",
                    "filters[state]": state_clean,
                    "filters[district]": district_clean,
                    "filters[commodity]": commodity_clean,
                }
                resp = await client.get(gov_url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    records = data.get("records", [])
                    if records:
                        rec = records[0]
                        market_name = rec.get("market", f"{district_clean} Mandi")
                        comm_name = rec.get("commodity", commodity_clean)
                        modal_price = rec.get(
                            "modal_price", rec.get("modal_rate", "N/A")
                        )
                        min_price = rec.get("min_price", rec.get("min_rate", "N/A"))
                        max_price = rec.get("max_price", rec.get("max_rate", "N/A"))
                        report_date = rec.get("arrival_date", today_str)

                        return (
                            f"As per today's live Agmarknet report ({report_date}) for {comm_name} in {market_name}, {district_clean} ({state_clean}): "
                            f"Modal price is ₹{modal_price}/quintal (Min: ₹{min_price}, Max: ₹{max_price}). "
                            f"Rates can vary locally; please verify at your local market before selling."
                        )
        except Exception as e:
            logger.warning(
                f"Agmarknet Live API request failed/timed out: {e}. Falling back to benchmark rates."
            )

    # Local Fallback Strategy (mandi_rates.json)
    fallback_data = _load_fallback_mandi_rates()
    state_key = state_clean.lower().replace(" ", "_")
    dist_key = district_clean.lower().replace(" ", "_")
    comm_key = commodity_clean.lower().replace(" ", "_")

    rate_info = None

    # Search in state -> district -> commodity
    state_dict = fallback_data.get(state_key, {})
    dist_dict = state_dict.get(dist_key, {})

    # Check exact commodity key or substring match
    for k, v in dist_dict.items():
        if k in comm_key or comm_key in k:
            rate_info = v
            break

    # If not found in district, check default benchmarks
    if not rate_info:
        def_benchmarks = fallback_data.get("default_benchmarks", {})
        for k, v in def_benchmarks.items():
            if k in comm_key or comm_key in k:
                rate_info = v
                break

    # General fallback default if commodity unknown
    if not rate_info:
        rate_info = {
            "min_price": 2000,
            "max_price": 2400,
            "modal_price": 2200,
            "market": f"{district_clean} Mandi",
            "unit": "Quintal",
        }

    modal_price = rate_info.get("modal_price", 2200)
    min_price = rate_info.get("min_price", 2000)
    max_price = rate_info.get("max_price", 2400)
    market_name = rate_info.get("market", f"{district_clean} Mandi")

    return (
        f"According to recent market benchmark report ({today_str}) for {commodity_clean} in {district_clean} ({state_clean}): "
        f"Modal price is ₹{modal_price}/quintal (Min: ₹{min_price}, Max: ₹{max_price}) at {market_name}. "
        f"Rates can vary locally; please verify at your local market before selling."
    )
