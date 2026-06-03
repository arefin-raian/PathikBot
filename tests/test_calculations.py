"""Comprehensive tests for petrol/mobil threshold tracking."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.calculations import (
    _refill_status, calc_carry_forward,
    get_petrol_status, get_mobil_status,
    PETROL_THRESHOLD_KM, MOBIL_THRESHOLD_KM
)


class TestRefillStatus:

    def test_no_entries(self):
        result = _refill_status([], 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        assert result['distance_since'] == 0
        assert result['is_due'] is False
        assert result['effective_threshold'] == PETROL_THRESHOLD_KM

    def test_no_refill_ever(self):
        entries = [
            {'date': '2026-06-01', 'total_km': 50, 'petrol_liters': 0},
            {'date': '2026-06-02', 'total_km': 100, 'petrol_liters': 0},
        ]
        result = _refill_status(entries, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        assert result['distance_since'] == 150
        assert result['is_due'] is False

    def test_no_refill_ever_exceeds_threshold(self):
        entries = [{'date': '2026-01-01', 'total_km': 500, 'petrol_liters': 0}]
        result = _refill_status(entries, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        assert result['distance_since'] == 500
        assert result['is_due'] is True

    def test_refill_includes_own_km(self):
        """Refill entry's own total_km must count toward distance_since."""
        entries = [
            {'date': '2026-06-01', 'total_km': 50, 'petrol_liters': 5, 'petrol_overflow': 0},
            {'date': '2026-06-02', 'total_km': 60, 'petrol_liters': 0},
            {'date': '2026-06-03', 'total_km': 55, 'petrol_liters': 0},
            {'date': '2026-06-04', 'total_km': 65, 'petrol_liters': 0},
            {'date': '2026-06-05', 'total_km': 58, 'petrol_liters': 0},
            {'date': '2026-06-06', 'total_km': 62, 'petrol_liters': 0},
            {'date': '2026-06-07', 'total_km': 52, 'petrol_liters': 0},
        ]
        result = _refill_status(entries, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        # 50 + 60 + 55 + 65 + 58 + 62 + 52 = 402
        assert result['distance_since'] == 402, (
            f"Expected 402 (including refill entry's 50 km), got {result['distance_since']}"
        )
        assert result['is_due'] is False

    def test_user_scenario_494_exceeds_480(self):
        """Exact user scenario: refill June 1, 402 km by June 7, +92 on June 8 = 494 > 480."""
        entries = [
            {'date': '2026-06-01', 'total_km': 50, 'petrol_liters': 5, 'petrol_overflow': 0},
            {'date': '2026-06-02', 'total_km': 60, 'petrol_liters': 0},
            {'date': '2026-06-03', 'total_km': 55, 'petrol_liters': 0},
            {'date': '2026-06-04', 'total_km': 65, 'petrol_liters': 0},
            {'date': '2026-06-05', 'total_km': 58, 'petrol_liters': 0},
            {'date': '2026-06-06', 'total_km': 62, 'petrol_liters': 0},
            {'date': '2026-06-07', 'total_km': 52, 'petrol_liters': 0},
        ]
        result = _refill_status(entries, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        # Simulate adding the new entry's 92 km (as done in handle_odo_confirm)
        distance_since = result['distance_since'] + 92
        is_due = distance_since >= result['effective_threshold']
        assert distance_since == 494, f"Expected 494, got {distance_since}"
        assert is_due is True, (
            f"Reminder should trigger: 494 >= {result['effective_threshold']}"
        )

    def test_refill_at_last_entry_includes_own_km(self):
        """When the last entry IS the refill, include its km."""
        entries = [
            {'date': '2026-06-01', 'total_km': 50, 'petrol_liters': 0},
            {'date': '2026-06-02', 'total_km': 100, 'petrol_liters': 5, 'petrol_overflow': 0},
        ]
        result = _refill_status(entries, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        assert result['distance_since'] == 100, (
            f"Expected 100 (last refill entry's own km), got {result['distance_since']}"
        )

    def test_multiple_refills_uses_last(self):
        entries = [
            {'date': '2026-06-01', 'total_km': 50, 'petrol_liters': 5, 'petrol_overflow': 0},
            {'date': '2026-06-02', 'total_km': 100, 'petrol_liters': 0},
            {'date': '2026-06-05', 'total_km': 70, 'petrol_liters': 4, 'petrol_overflow': 0},
            {'date': '2026-06-06', 'total_km': 80, 'petrol_liters': 0},
        ]
        result = _refill_status(entries, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        # Last refill is June 5: distance = 70 (refill) + 80 = 150
        assert result['distance_since'] == 150, (
            f"Expected 150, got {result['distance_since']}"
        )

    def test_threshold_exactly_met(self):
        entries = [
            {'date': '2026-06-01', 'total_km': 480, 'petrol_liters': 5, 'petrol_overflow': 0},
        ]
        result = _refill_status(entries, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        assert result['distance_since'] == 480
        assert result['is_due'] is True

    def test_carry_forward_reduces_effective_threshold(self):
        """14 km carry-forward → effective threshold = 480 - 14 = 466."""
        entries = [
            {'date': '2026-06-01', 'total_km': 50, 'petrol_liters': 5, 'petrol_overflow': 14},
            {'date': '2026-06-02', 'total_km': 300, 'petrol_liters': 0},
        ]
        result = _refill_status(entries, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        assert result['carry_forward'] == 14
        assert result['effective_threshold'] == 466  # 480 - 14
        assert result['distance_since'] == 350  # 50 + 300
        assert result['is_due'] is False  # 350 < 466

    def test_carry_forward_triggers_reminder_sooner(self):
        entries = [
            {'date': '2026-06-01', 'total_km': 50, 'petrol_liters': 5, 'petrol_overflow': 14},
            {'date': '2026-06-02', 'total_km': 420, 'petrol_liters': 0},
        ]
        result = _refill_status(entries, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        assert result['effective_threshold'] == 466
        assert result['distance_since'] == 470  # 50 + 420
        assert result['is_due'] is True  # 470 >= 466

    def test_mobil_threshold(self):
        entries = [
            {'date': '2026-06-01', 'total_km': 600, 'mobil_liters': 2, 'mobil_overflow': 0},
            {'date': '2026-06-02', 'total_km': 500, 'mobil_liters': 0},
        ]
        result = get_mobil_status(entries)
        assert result['effective_threshold'] == MOBIL_THRESHOLD_KM  # 1000
        assert result['distance_since'] == 1100  # 600 + 500
        assert result['is_due'] is True  # 1100 >= 1000

    def test_petrol_threshold(self):
        entries = [
            {'date': '2026-06-01', 'total_km': 300, 'petrol_liters': 5, 'petrol_overflow': 0},
            {'date': '2026-06-02', 'total_km': 200, 'petrol_liters': 0},
        ]
        result = get_petrol_status(entries)
        assert result['distance_since'] == 500
        assert result['is_due'] is True  # 500 >= 480

    def test_no_overflow_when_below_threshold(self):
        existing = [
            {'date': '2026-06-01', 'total_km': 50, 'petrol_liters': 5, 'petrol_overflow': 0},
            {'date': '2026-06-02', 'total_km': 100, 'petrol_liters': 0},
        ]
        overflow = calc_carry_forward(
            existing, 50, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM
        )
        # distance_since = 50 (new) + 50 (refill) + 100 = 200 < 480
        assert overflow == 0

    def test_carry_forward_user_scenario(self):
        """User scenario: 494 km → overflow = 494 - 480 = 14."""
        existing = [
            {'date': '2026-06-01', 'total_km': 50, 'petrol_liters': 5, 'petrol_overflow': 0},
            {'date': '2026-06-02', 'total_km': 60, 'petrol_liters': 0},
            {'date': '2026-06-03', 'total_km': 55, 'petrol_liters': 0},
            {'date': '2026-06-04', 'total_km': 65, 'petrol_liters': 0},
            {'date': '2026-06-05', 'total_km': 58, 'petrol_liters': 0},
            {'date': '2026-06-06', 'total_km': 62, 'petrol_liters': 0},
            {'date': '2026-06-07', 'total_km': 52, 'petrol_liters': 0},
        ]
        overflow = calc_carry_forward(
            existing, 92, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM
        )
        # distance_since = 92 (new) + 50 (refill) + 60 + 55 + 65 + 58 + 62 + 52 = 494
        # overflow = max(0, 494 - 480) = 14
        assert overflow == 14, f"Expected 14, got {overflow}"

    def test_carry_forward_with_prev_overflow(self):
        existing = [
            {'date': '2026-06-01', 'total_km': 50, 'petrol_liters': 5, 'petrol_overflow': 10},
            {'date': '2026-06-02', 'total_km': 200, 'petrol_liters': 0},
        ]
        overflow = calc_carry_forward(
            existing, 300, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM
        )
        # distance_since = 300 + 50 + 200 = 550
        # effective_threshold = 480 - 10 = 470
        # overflow = max(0, 550 - 470) = 80
        assert overflow == 80, f"Expected 80, got {overflow}"

    def test_distance_since_key_present(self):
        """Ensure response dict has all expected keys."""
        result = _refill_status([], 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        expected_keys = {'distance_since', 'is_due', 'effective_threshold', 'effective_remaining', 'carry_forward'}
        assert set(result.keys()) == expected_keys, f"Missing keys: {expected_keys - set(result.keys())}"
