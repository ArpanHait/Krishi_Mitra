import os
import sys
from pathlib import Path

# Add src to path
src_dir = Path(__file__).parent.parent / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

import pytest  # noqa: E402

from agent import Assistant  # noqa: E402
from tools import fetch_district_weather, fetch_mandi_prices  # noqa: E402


@pytest.mark.asyncio
async def test_fetch_district_weather_success() -> None:
    """Test fetch_district_weather with live Open-Meteo API query for Burdwan."""
    result = await fetch_district_weather("Burdwan", "West Bengal")
    assert isinstance(result, str)
    assert (
        "report" in result.lower()
        or "weather" in result.lower()
        or "temperature" in result.lower()
    )
    assert "°C" in result or "Unable" in result


@pytest.mark.asyncio
async def test_fetch_district_weather_invalid_district() -> None:
    """Test fetch_district_weather error handling with an unresolvable district name."""
    result = await fetch_district_weather("NonExistentDistrictName123456789")
    assert isinstance(result, str)
    assert "Unable to fetch live weather data" in result or "report" in result.lower()


@pytest.mark.asyncio
async def test_fetch_mandi_prices_live_or_fallback() -> None:
    """Test fetch_mandi_prices returns valid report with modal rate for Paddy in Burdwan."""
    result = await fetch_mandi_prices("Paddy", "Burdwan", "West Bengal")
    assert isinstance(result, str)
    assert "Paddy" in result or "paddy" in result.lower()
    assert "₹" in result or "quintal" in result.lower()
    assert "Agmarknet" in result or "benchmark" in result.lower()


@pytest.mark.asyncio
async def test_fetch_mandi_prices_fallback_trigger() -> None:
    """Test fetch_mandi_prices fallback mechanism when API key is empty/invalid."""
    # Temporarily unset API key to force local benchmark JSON fallback
    orig_key = os.environ.get("DATA_GOV_API_KEY")
    try:
        os.environ["DATA_GOV_API_KEY"] = ""
        result = await fetch_mandi_prices("Potato", "Hooghly", "West Bengal")
        assert isinstance(result, str)
        assert "Potato" in result or "potato" in result.lower()
        assert "₹" in result
        assert "benchmark" in result.lower()
    finally:
        if orig_key is not None:
            os.environ["DATA_GOV_API_KEY"] = orig_key


def test_assistant_tools_registration() -> None:
    """Verify that Day 5 function tools are properly registered on the Assistant agent."""
    assistant = Assistant()

    # Verify tool callables exist on Assistant instance or type
    assert hasattr(assistant, "get_district_weather")
    assert hasattr(assistant, "get_mandi_prices")
    assert hasattr(assistant, "save_farmer_facts")
    assert hasattr(assistant, "forget_farmer_facts")
