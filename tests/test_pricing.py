import sys
from datetime import datetime
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ams_han_reflex_app.domain.pricing import PriceDayResult, PriceProvider


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


if __name__ == "__main__":
    unittest.main()
