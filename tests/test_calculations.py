"""Comprehensive tests for petrol/mobil threshold tracking."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.expense_calculations import (
    _refill_status, calc_carry_forward, calculate_fuel_since_refill,
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

    def test_negative_carry_when_below_threshold(self):
        """Refuelling before threshold = negative carry (km remaining)."""
        existing = [
            {'date': '2026-06-01', 'total_km': 50, 'petrol_liters': 5, 'petrol_overflow': 0},
            {'date': '2026-06-02', 'total_km': 100, 'petrol_liters': 0},
        ]
        carry = calc_carry_forward(
            existing, 50, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM
        )
        # distance_since = 50 (new) + 50 (refill) + 100 = 200 < 480
        # carry = 200 - 480 = -280 (280 km still remaining)
        assert carry == -280, f"Expected -280 (km remaining), got {carry}"

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


class TestCalculateFuelSinceRefill:

    def test_empty_entries(self):
        result = calculate_fuel_since_refill([], 'petrol_liters', PETROL_THRESHOLD_KM)
        assert result['distance_since_refill'] == 0
        assert result['liters_consumed'] == 0
        assert result['last_refill_liters'] == 0

    def test_no_refill_found(self):
        entries = [
            {'date': '2026-06-01', 'total_km': 50, 'petrol_liters': 0},
            {'date': '2026-06-02', 'total_km': 100, 'petrol_liters': 0},
        ]
        result = calculate_fuel_since_refill(entries, 'petrol_liters', PETROL_THRESHOLD_KM)
        assert result['distance_since_refill'] == 0
        assert result['liters_consumed'] == 0

    def test_user_scenario(self):
        """Tour 20: 10L petrol. Tours 20-24 total distance <480km."""
        entries = [
            {'date': '2026-06-20', 'total_km': 50, 'petrol_liters': 10},
            {'date': '2026-06-21', 'total_km': 100, 'petrol_liters': 0},
            {'date': '2026-06-22', 'total_km': 80, 'petrol_liters': 0},
            {'date': '2026-06-23', 'total_km': 90, 'petrol_liters': 0},
            {'date': '2026-06-24', 'total_km': 70, 'petrol_liters': 0},
        ]
        result = calculate_fuel_since_refill(entries, 'petrol_liters', PETROL_THRESHOLD_KM)
        # distance = 50+100+80+90+70 = 390
        # efficiency = 480/10 = 48 km/L
        # liters_consumed = 390/48 = 8.12 (rounded to 2 dp)
        assert result['distance_since_refill'] == 390
        assert result['liters_consumed'] == 8.12
        assert result['last_refill_liters'] == 10

    def test_refill_at_last_entry(self):
        """Refill IS the last tour."""
        entries = [
            {'date': '2026-06-01', 'total_km': 100, 'petrol_liters': 0},
            {'date': '2026-06-02', 'total_km': 50, 'petrol_liters': 5},
        ]
        result = calculate_fuel_since_refill(entries, 'petrol_liters', PETROL_THRESHOLD_KM)
        # distance = 50 (only the refill entry's own km)
        # efficiency = 480/5 = 96 km/L
        # liters_consumed = 50/96 = 0.52
        assert result['distance_since_refill'] == 50
        assert result['liters_consumed'] == 0.52
        assert result['last_refill_liters'] == 5

    def test_mobil_since_refill(self):
        entries = [
            {'date': '2026-06-01', 'total_km': 300, 'mobil_liters': 2},
            {'date': '2026-06-02', 'total_km': 500, 'mobil_liters': 0},
            {'date': '2026-06-03', 'total_km': 200, 'mobil_liters': 0},
        ]
        result = calculate_fuel_since_refill(entries, 'mobil_liters', MOBIL_THRESHOLD_KM)
        # distance = 300+500+200 = 1000
        # efficiency = 1000/2 = 500 km/L
        # liters_consumed = 1000/500 = 2.0
        assert result['distance_since_refill'] == 1000
        assert result['liters_consumed'] == 2.0
        assert result['last_refill_liters'] == 2


# ═══════════════════════════════════════════════════════════════════
# NEW: 50+ comprehensive petrol/mobil scenario tests
# ═══════════════════════════════════════════════════════════════════

class TestSignedCarryForward:
    """Tests for the signed carry-forward fix."""

    def test_refill_before_threshold_carries_remaining(self):
        """
        User scenario: 10L petrol, travel 400km (before 480 threshold),
        still has ~80km worth. Take another 10L.
        Carry should be -80 (80 km remaining from previous).
        """
        existing = [
            {'date': '2026-06-01', 'total_km': 50, 'petrol_liters': 5, 'petrol_overflow': 0},
            {'date': '2026-06-02', 'total_km': 100, 'petrol_liters': 0},
            {'date': '2026-06-03', 'total_km': 80, 'petrol_liters': 0},
            {'date': '2026-06-04', 'total_km': 90, 'petrol_liters': 0},
            {'date': '2026-06-05', 'total_km': 80, 'petrol_liters': 0},
        ]
        # distance_since = 50+100+80+90+80 = 400 from last refill
        carry = calc_carry_forward(existing, 0, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        assert carry == -80, f"Expected -80 (80 km remaining), got {carry}"

    def test_refill_before_threshold_effective_threshold_increases(self):
        """With -80 carry stored, effective threshold = 480 - (-80) = 560."""
        existing = [
            {'date': '2026-06-01', 'total_km': 50, 'petrol_liters': 5, 'petrol_overflow': -80},
            {'date': '2026-06-02', 'total_km': 100, 'petrol_liters': 0},
        ]
        status = _refill_status(existing, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        assert status['carry_forward'] == -80
        assert status['effective_threshold'] == 560  # 480 - (-80)

    def test_refill_before_threshold_reminder_not_due(self):
        """400 < 560, so reminder not due."""
        existing = [
            {'date': '2026-06-01', 'total_km': 50, 'petrol_liters': 5, 'petrol_overflow': -80},
            {'date': '2026-06-02', 'total_km': 100, 'petrol_liters': 0},
        ]
        status = _refill_status(existing, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        assert status['effective_threshold'] == 560
        assert status['distance_since'] == 150
        assert status['is_due'] is False

    def test_refill_before_threshold_reminder_due_at_higher_boundary(self):
        """With -80 carry, reminder should fire at 560km from that refill."""
        existing = [
            {'date': '2026-06-01', 'total_km': 50, 'petrol_liters': 5, 'petrol_overflow': -80},
            {'date': '2026-06-02', 'total_km': 200, 'petrol_liters': 0},
            {'date': '2026-06-03', 'total_km': 200, 'petrol_liters': 0},
            {'date': '2026-06-04', 'total_km': 120, 'petrol_liters': 0},
        ]
        status = _refill_status(existing, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        assert status['effective_threshold'] == 560
        assert status['distance_since'] == 570  # 50+200+200+120
        assert status['is_due'] is True

    def test_exact_threshold_zero_carry(self):
        """Exactly at threshold = zero carry."""
        existing = [
            {'date': '2026-06-01', 'total_km': 200, 'petrol_liters': 5, 'petrol_overflow': 0},
            {'date': '2026-06-02', 'total_km': 280, 'petrol_liters': 0},
        ]
        carry = calc_carry_forward(existing, 0, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        assert carry == 0  # 480 - 480

    def test_new_entry_km_added_to_distance(self):
        """new_entry_km parameter is included in distance calculation."""
        existing = [
            {'date': '2026-06-01', 'total_km': 50, 'petrol_liters': 5, 'petrol_overflow': 0},
            {'date': '2026-06-02', 'total_km': 100, 'petrol_liters': 0},
        ]
        carry_no_new = calc_carry_forward(existing, 0, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        carry_with_new = calc_carry_forward(existing, 30, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        assert carry_no_new == -330  # 150 - 480
        assert carry_with_new == -300  # 180 - 480

    def test_prev_remaining_and_current_excess(self):
        """Previous carry = -50 (50km left), now travel 500km → distance = 500, effective = 480-(-50)=530, carry = 500-530 = -30"""
        existing = [
            {'date': '2026-06-01', 'total_km': 50, 'petrol_liters': 5, 'petrol_overflow': -50},
            {'date': '2026-06-02', 'total_km': 200, 'petrol_liters': 0},
            {'date': '2026-06-03', 'total_km': 250, 'petrol_liters': 0},
        ]
        status = _refill_status(existing, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        assert status['effective_threshold'] == 530
        assert status['distance_since'] == 500
        assert status['is_due'] is False  # 500 < 530

    def test_prev_remaining_exceeded(self):
        """Previous carry = -50, travel 550km → distance=550 >= 530, due."""
        existing = [
            {'date': '2026-06-01', 'total_km': 50, 'petrol_liters': 5, 'petrol_overflow': -50},
            {'date': '2026-06-02', 'total_km': 200, 'petrol_liters': 0},
            {'date': '2026-06-03', 'total_km': 300, 'petrol_liters': 0},
        ]
        status = _refill_status(existing, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        assert status['effective_threshold'] == 530
        assert status['distance_since'] == 550
        assert status['is_due'] is True

    def test_carry_forward_with_prev_negative_carry(self):
        """Previous carry = -80, now refuel with 300 new km."""
        existing = [
            {'date': '2026-06-01', 'total_km': 50, 'petrol_liters': 5, 'petrol_overflow': -80},
            {'date': '2026-06-02', 'total_km': 100, 'petrol_liters': 0},
        ]
        carry = calc_carry_forward(existing, 300, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        # distance = 300 + 50 + 100 = 450, effective = 480 - (-80) = 560
        # carry = 450 - 560 = -110
        assert carry == -110

    def test_empty_entries_carry_forward_returns_zero(self):
        assert calc_carry_forward([], 0, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM) == 0

    def test_no_refill_ever_carry_forward_returns_zero(self):
        """No previous refill found → no carry to forward."""
        entries = [
            {'date': '2026-06-01', 'total_km': 100, 'petrol_liters': 0},
            {'date': '2026-06-02', 'total_km': 200, 'petrol_liters': 0},
        ]
        carry = calc_carry_forward(entries, 50, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        assert carry == 0  # no refill found

    def test_chained_refills_carry_stored_on_refill_entry(self):
        """Carry is stored on the refill entry itself; status reads it."""
        entries = [
            {'date': '2026-06-01', 'total_km': 100, 'petrol_liters': 5, 'petrol_overflow': -380},
            {'date': '2026-06-02', 'total_km': 100, 'petrol_liters': 0},
            {'date': '2026-06-03', 'total_km': 100, 'petrol_liters': 0},
            {'date': '2026-06-04', 'total_km': 100, 'petrol_liters': 5, 'petrol_overflow': -280},
        ]
        status = _refill_status(entries, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        assert status['distance_since'] == 100
        assert status['carry_forward'] == -280
        assert status['effective_threshold'] == 760  # 480 - (-280)

    def test_mobil_and_petrol_independent(self):
        """Petrol and mobil tracking don't interfere."""
        entries = [
            {'date': '2026-06-01', 'total_km': 300, 'petrol_liters': 5, 'petrol_overflow': 0, 'mobil_liters': 0, 'mobil_overflow': 0},
            {'date': '2026-06-02', 'total_km': 200, 'petrol_liters': 0, 'mobil_liters': 2, 'mobil_overflow': 0},
            {'date': '2026-06-03', 'total_km': 600, 'petrol_liters': 0, 'mobil_liters': 0, 'mobil_overflow': 0},
        ]
        p = get_petrol_status(entries)
        m = get_mobil_status(entries)
        # Petrol: last refill idx=0, distance sums from idx 0 = 300+200+600 = 1100
        assert p['distance_since'] == 1100
        assert p['carry_forward'] == 0
        assert p['is_due'] is True  # 1100 >= 480
        # Mobil: last refill idx=1, distance sums from idx 1 = 200+600 = 800
        assert m['distance_since'] == 800
        assert m['carry_forward'] == 0
        assert m['is_due'] is False  # 800 < 1000

    def test_missing_overflow_field_defaults_zero(self):
        """If overflow field missing, treat as 0."""
        entries = [
            {'date': '2026-06-01', 'total_km': 300, 'petrol_liters': 5},
            # no petrol_overflow key
        ]
        status = _refill_status(entries, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        assert status['carry_forward'] == 0
        assert status['effective_threshold'] == PETROL_THRESHOLD_KM

    def test_missing_liters_field_defaults_zero(self):
        entries = [
            {'date': '2026-06-01', 'total_km': 300},
        ]
        status = _refill_status(entries, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        assert status['distance_since'] == 300
        assert status['is_due'] is False

    def test_zero_km_entries(self):
        """Entries with 0 km don't affect tracking."""
        entries = [
            {'date': '2026-06-01', 'total_km': 0, 'petrol_liters': 5, 'petrol_overflow': 0},
            {'date': '2026-06-02', 'total_km': 0, 'petrol_liters': 0},
            {'date': '2026-06-03', 'total_km': 100, 'petrol_liters': 0},
        ]
        status = _refill_status(entries, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        assert status['distance_since'] == 100  # 0+0+100

    def test_unsorted_entries_sorted_by_date(self):
        entries = [
            {'date': '2026-06-05', 'total_km': 100, 'petrol_liters': 0},
            {'date': '2026-06-01', 'total_km': 50, 'petrol_liters': 5, 'petrol_overflow': 0},
            {'date': '2026-06-03', 'total_km': 60, 'petrol_liters': 0},
        ]
        status = _refill_status(entries, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        assert status['distance_since'] == 210  # 50+60+100

    def test_large_remaining_km_extends_threshold_significantly(self):
        """Refill at 100km (380km remaining). Threshold = 480 + 380 = 860."""
        entries = [
            {'date': '2026-06-01', 'total_km': 50, 'petrol_liters': 5, 'petrol_overflow': 0},
            {'date': '2026-06-02', 'total_km': 50, 'petrol_liters': 0},
        ]
        status = _refill_status(entries, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        assert status['effective_remaining'] == 380  # 480 - 100

    def test_carry_forward_does_not_use_max(self):
        """Verify the fix: old max(0, ...) would return 0, new returns -280."""
        existing = [
            {'date': '2026-06-01', 'total_km': 50, 'petrol_liters': 5, 'petrol_overflow': 0},
            {'date': '2026-06-02', 'total_km': 100, 'petrol_liters': 0},
        ]
        carry = calc_carry_forward(existing, 50, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        assert carry < 0  # must be negative to show remaining km
        assert carry == -280

    def test_both_refill_same_entry(self):
        """Petrol + mobil in same entry, both tracked independently."""
        entries = [
            {'date': '2026-06-01', 'total_km': 300, 'petrol_liters': 5, 'petrol_overflow': 0, 'mobil_liters': 2, 'mobil_overflow': 0},
            {'date': '2026-06-02', 'total_km': 200, 'petrol_liters': 0, 'mobil_liters': 0, 'mobil_overflow': 0},
        ]
        p = get_petrol_status(entries)
        m = get_mobil_status(entries)
        assert p['distance_since'] == 500
        assert m['distance_since'] == 500
        assert p['is_due'] is True
        assert m['is_due'] is False  # 500 < 1000

    def test_no_refill_ever_boundary_479(self):
        """479 km (just under 480) → not due."""
        entries = [{'date': '2026-06-01', 'total_km': 479, 'petrol_liters': 0}]
        status = _refill_status(entries, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        assert status['is_due'] is False

    def test_no_refill_ever_boundary_480(self):
        """480 km → due."""
        entries = [{'date': '2026-06-01', 'total_km': 480, 'petrol_liters': 0}]
        status = _refill_status(entries, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        assert status['is_due'] is True

    def test_no_refill_ever_very_large(self):
        entries = [{'date': '2026-06-01', 'total_km': 9999, 'petrol_liters': 0}]
        status = _refill_status(entries, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        assert status['distance_since'] == 9999
        assert status['is_due'] is True

    def test_carry_forward_chained_positive(self):
        """Multiple refills all exceeding threshold."""
        entries = [
            {'date': '2026-06-01', 'total_km': 100, 'petrol_liters': 5, 'petrol_overflow': 20},
            {'date': '2026-06-02', 'total_km': 200, 'petrol_liters': 0},
            {'date': '2026-06-03', 'total_km': 300, 'petrol_liters': 5, 'petrol_overflow': 0},
        ]
        # Last refill = June 3, stored petrol_overflow = 0
        # distance = 0 + 300 = 300, effective = 480 - 0 = 480
        carry = calc_carry_forward(entries, 0, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        assert carry == -180  # 300 - 480

    def test_carry_forward_chained_positive_to_negative(self):
        """Prev overflow 20 stored but last refill carries its own stored value."""
        entries = [
            {'date': '2026-06-01', 'total_km': 100, 'petrol_liters': 5, 'petrol_overflow': 20},
            {'date': '2026-06-02', 'total_km': 200, 'petrol_liters': 0},
            {'date': '2026-06-03', 'total_km': 180, 'petrol_liters': 5, 'petrol_overflow': 0},
        ]
        carry = calc_carry_forward(entries, 0, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        # Last refill = June 3, stored petrol_overflow = 0
        # distance = 180, effective = 480 - 0 = 480, carry = 180 - 480 = -300
        assert carry == -300

    def test_carry_forward_exactly_at_effective_threshold(self):
        existing = [
            {'date': '2026-06-01', 'total_km': 50, 'petrol_liters': 5, 'petrol_overflow': 20},
            {'date': '2026-06-02', 'total_km': 410, 'petrol_liters': 0},
        ]
        carry = calc_carry_forward(existing, 0, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        # distance = 460, effective = 480 - 20 = 460
        assert carry == 0

    def test_mobil_threshold_1000_remaining(self):
        """Mobil refill at 800km (200 remaining)."""
        entries = [
            {'date': '2026-06-01', 'total_km': 500, 'mobil_liters': 2, 'mobil_overflow': 0},
            {'date': '2026-06-02', 'total_km': 300, 'mobil_liters': 0},
        ]
        status = get_mobil_status(entries)
        assert status['distance_since'] == 800
        assert status['effective_remaining'] == 200
        assert status['is_due'] is False

    def test_mobil_threshold_1000_remaining_extends(self):
        """With -200 mobil carry, threshold = 1000 - (-200) = 1200."""
        entries = [
            {'date': '2026-06-01', 'total_km': 500, 'mobil_liters': 2, 'mobil_overflow': 0},
            {'date': '2026-06-02', 'total_km': 300, 'mobil_liters': 0},
        ]
        carry = calc_carry_forward(entries, 0, 'mobil_liters', 'mobil_overflow', MOBIL_THRESHOLD_KM)
        assert carry == -200  # 800 - 1000
        # New entries with carry = -200
        entries2 = [
            {'date': '2026-06-01', 'total_km': 500, 'mobil_liters': 2, 'mobil_overflow': -200},
            {'date': '2026-06-02', 'total_km': 400, 'mobil_liters': 0},
        ]
        status = get_mobil_status(entries2)
        assert status['effective_threshold'] == 1200
        assert status['distance_since'] == 900
        assert status['is_due'] is False

    def test_effective_remaining_correct_with_negative_carry(self):
        """effective_remaining = max(0, effective_threshold - distance_since)."""
        entries = [
            {'date': '2026-06-01', 'total_km': 50, 'petrol_liters': 5, 'petrol_overflow': -80},
            {'date': '2026-06-02', 'total_km': 100, 'petrol_liters': 0},
        ]
        status = _refill_status(entries, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        assert status['effective_threshold'] == 560  # 480 - (-80)
        assert status['distance_since'] == 150  # 50 + 100
        assert status['effective_remaining'] == 410  # max(0, 560 - 150)

    def test_mobil_carry_forward_negative(self):
        existing = [
            {'date': '2026-06-01', 'total_km': 400, 'mobil_liters': 2, 'mobil_overflow': 0},
        ]
        carry = calc_carry_forward(existing, 0, 'mobil_liters', 'mobil_overflow', MOBIL_THRESHOLD_KM)
        assert carry == -600  # 400 - 1000

    def test_mobil_carry_forward_positive(self):
        existing = [
            {'date': '2026-06-01', 'total_km': 1200, 'mobil_liters': 2, 'mobil_overflow': 0},
        ]
        carry = calc_carry_forward(existing, 0, 'mobil_liters', 'mobil_overflow', MOBIL_THRESHOLD_KM)
        assert carry == 200  # 1200 - 1000

    def test_fuel_efficiency_high_consumption(self):
        """10L → 480km, so 48 km/L. If travelled 480km, consumed 10L."""
        entries = [
            {'date': '2026-06-01', 'total_km': 480, 'petrol_liters': 10},
        ]
        result = calculate_fuel_since_refill(entries, 'petrol_liters', PETROL_THRESHOLD_KM)
        assert result['liters_consumed'] == 10.0

    def test_fuel_efficiency_low_consumption(self):
        """2L → 1000km = 500 km/L. T ravelled 200km → 0.4L consumed."""
        entries = [
            {'date': '2026-06-01', 'total_km': 200, 'mobil_liters': 2},
        ]
        result = calculate_fuel_since_refill(entries, 'mobil_liters', MOBIL_THRESHOLD_KM)
        assert result['liters_consumed'] == 0.4
        assert result['last_refill_liters'] == 2

    def test_fuel_efficiency_multiple_refills_last_used(self):
        entries = [
            {'date': '2026-06-01', 'total_km': 100, 'petrol_liters': 5},
            {'date': '2026-06-02', 'total_km': 200, 'petrol_liters': 0},
            {'date': '2026-06-05', 'total_km': 150, 'petrol_liters': 3},
            {'date': '2026-06-06', 'total_km': 100, 'petrol_liters': 0},
        ]
        result = calculate_fuel_since_refill(entries, 'petrol_liters', PETROL_THRESHOLD_KM)
        # Last refill = June 5, 3L. distance = 150 + 100 = 250
        # efficiency = 480/3 = 160 km/L
        # consumed = 250/160 = 1.56
        assert result['distance_since_refill'] == 250
        assert result['liters_consumed'] == 1.56
        assert result['last_refill_liters'] == 3

    def test_fuel_efficiency_zero_distance(self):
        entries = [
            {'date': '2026-06-01', 'total_km': 0, 'petrol_liters': 5},
        ]
        result = calculate_fuel_since_refill(entries, 'petrol_liters', PETROL_THRESHOLD_KM)
        assert result['distance_since_refill'] == 0
        assert result['liters_consumed'] == 0

    def test_carry_forward_petrol_only_not_mobil(self):
        """Petrol refill should not affect mobil carry_forward."""
        existing = [
            {'date': '2026-06-01', 'total_km': 100, 'petrol_liters': 5, 'petrol_overflow': 0, 'mobil_liters': 0, 'mobil_overflow': 0},
        ]
        petrol_carry = calc_carry_forward(existing, 0, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        mobil_carry = calc_carry_forward(existing, 0, 'mobil_liters', 'mobil_overflow', MOBIL_THRESHOLD_KM)
        assert petrol_carry == -380  # 100 - 480
        assert mobil_carry == 0  # no mobil refill found

    def test_carry_forward_with_meeting_entries_skipped_by_petrol(self):
        """Meeting entries have no petrol/mobil, but they have total_km=0 so don't affect distance."""
        existing = [
            {'date': '2026-06-01', 'total_km': 100, 'petrol_liters': 5, 'petrol_overflow': 0},
            {'date': '2026-06-02', 'total_km': 0, 'petrol_liters': 0, 'entry_type': 'MONTHLY_MEETING'},
            {'date': '2026-06-03', 'total_km': 100, 'petrol_liters': 0},
        ]
        status = _refill_status(existing, 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        assert status['distance_since'] == 200

    def test_is_due_field_type_bool(self):
        status = _refill_status([], 'petrol_liters', 'petrol_overflow', PETROL_THRESHOLD_KM)
        assert isinstance(status['is_due'], bool)

    def test_get_petrol_status_returns_dict(self):
        result = get_petrol_status([])
        assert isinstance(result, dict)

    def test_get_mobil_status_returns_dict(self):
        result = get_mobil_status([])
        assert isinstance(result, dict)
