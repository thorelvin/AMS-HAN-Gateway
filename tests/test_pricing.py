import sys
from datetime import datetime
from pathlib import Path
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ams_han_reflex_app.domain.pricing import (
    PRICE_REQUEST_HEADERS,
    PriceDayResult,
    PriceProvider,
)


class _BackgroundAwarePriceProvider(PriceProvider):
    def __init__(self) -> None:
        super().__init__()
        self.started: list[tuple[str, str]] = []

    def _start_background_fetch(self, area: str, dt: datetime) -> None:
        self.started.append((area, self._day_key(dt)))


class PricingTest(unittest.TestCase):
    def test_quote_for_hour_returns_non_blocking_background_fallback_on_empty_cache(self):
        provider = _BackgroundAwarePriceProvider()
        target = datetime(2026, 4, 21, 10, 30)

        quote = provider.quote_for_hour("NO3", target)

        self.assertTrue(quote.fallback_used)
        self.assertIn("loading in the background", quote.warning_text)
        self.assertEqual(provider.started, [("NO3", "2026-04-21")])

    def test_quote_for_hour_uses_cached_day_once_available(self):
        provider = _BackgroundAwarePriceProvider()
        target = datetime(2026, 4, 21, 10, 30)
        provider._cache[("NO3", "2026-04-21")] = PriceDayResult(
            entries=[
                {
                    "time_start": "2026-04-21T10:00:00+02:00",
                    "NOK_per_kWh": 0.834,
                }
            ]
        )

        quote = provider.quote_for_hour("NO3", target)

        self.assertFalse(quote.fallback_used)
        self.assertAlmostEqual(quote.nok_per_kwh, 0.834)
        self.assertEqual(provider.started, [])

    def test_fetch_day_sends_explicit_request_headers(self):
        provider = PriceProvider()
        target = datetime(2026, 4, 21, 10, 30)
        observed_headers: dict[str, str | None] = {}

        class _Response:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'[{"time_start":"2026-04-21T10:00:00+02:00","NOK_per_kWh":0.834}]'

        def fake_urlopen(request, timeout):
            observed_headers["User-Agent"] = request.get_header("User-agent")
            observed_headers["Accept"] = request.get_header("Accept")
            self.assertEqual(timeout, 6)
            return _Response()

        with patch("ams_han_reflex_app.domain.pricing.urlopen", side_effect=fake_urlopen):
            result = provider._fetch_day("NO3", target)

        self.assertEqual(result.warning_text, "")
        self.assertEqual(len(result.entries), 1)
        self.assertEqual(observed_headers["User-Agent"], PRICE_REQUEST_HEADERS["User-Agent"])
        self.assertEqual(observed_headers["Accept"], PRICE_REQUEST_HEADERS["Accept"])


if __name__ == "__main__":
    unittest.main()
