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
    estimate_capacity,
)


class _BackgroundAwarePriceProvider(PriceProvider):
    def __init__(self) -> None:
        super().__init__()
        self.started: list[tuple[str, str]] = []

    def _start_background_fetch(self, area: str, dt: datetime) -> None:
        self.started.append((area, self._day_key(dt)))


class PricingTest(unittest.TestCase):
    def test_estimate_capacity_returns_visual_step_data(self):
        capacity = estimate_capacity(
            [
                {"day": "2026-04-01", "hour": "07", "avg_import_kw": 4.2},
                {"day": "2026-04-02", "hour": "08", "avg_import_kw": 3.3},
                {"day": "2026-04-03", "hour": "09", "avg_import_kw": 4.5},
                {"day": "2026-04-03", "hour": "10", "avg_import_kw": 2.2},
            ]
        )

        self.assertEqual(capacity.step_label, "2-5 kW")
        self.assertEqual(capacity.step_price_text, "~270 NOK/month")
        self.assertEqual(capacity.basis_kw_text, "4.00 kW basis")
        active_step = next(step for step in capacity.steps if step.status == "active")
        self.assertEqual(active_step.label, "2-5 kW")
        self.assertEqual(active_step.fill_percent, "66.7%")
        self.assertEqual(capacity.steps[-1].label, "0-2 kW")

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
