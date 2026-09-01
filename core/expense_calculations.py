DEFAULT_PETROL_PRICE = 140.7
DEFAULT_MOBIL_PRICE = 560.0
DEFAULT_DA_AMOUNT = 200

def calculate_km(odo_start, odo_end):
    """Calculate total kilometers."""
    return max(0, odo_end - odo_start)

def calculate_petrol_cost(liters, price_per_liter=None):
    """Calculate petrol cost."""
    if price_per_liter is None:
        price_per_liter = DEFAULT_PETROL_PRICE
    return round(liters * float(price_per_liter))

def calculate_mobil_cost(liters, price_per_liter=None):
    """Calculate mobil cost."""
    if price_per_liter is None:
        price_per_liter = DEFAULT_MOBIL_PRICE
    return round(liters * float(price_per_liter))

def calculate_total_entry_cost(entry_type, petrol_liters=0, mobil_liters=0, da_amount=None, transport_fee=0, petrol_price=None, mobil_price=None):
    """Calculate total cost for an entry based on its type."""
    if da_amount is None:
        da_amount = DEFAULT_DA_AMOUNT
    da_amount = int(da_amount)

    if entry_type == 'MONTHLY_MEETING':
        return int(transport_fee)
    elif entry_type == 'KHATA_MILANO':
        return da_amount + int(transport_fee)
    else:
        petrol_cost = calculate_petrol_cost(petrol_liters, petrol_price)
        mobil_cost = calculate_mobil_cost(mobil_liters, mobil_price)
        return petrol_cost + mobil_cost + da_amount

def calculate_summary(entries):
    """Calculate summary statistics for a list of entries (usually for a month)."""
    total_km = 0
    total_liters_petrol = 0
    total_liters_mobil = 0
    total_petrol_cost = 0
    total_mobil_cost = 0
    total_da = 0
    total_others = 0 # Transport fees
    
    tour_count = 0
    friday_tour_count = 0
    meeting_count = 0
    manager_tour_count = 0
    short_tour_count = 0 # < 50km
    
    for entry in entries:
        e_type = entry.get('entry_type', 'REGULAR')
        km = entry.get('total_km', 0)
        
        if e_type == 'MONTHLY_MEETING':
            meeting_count += 1
            total_others += entry.get('transport_fee', 0)
        elif e_type == 'KHATA_MILANO':
            meeting_count += 1
            total_others += entry.get('transport_fee', 0)
            total_da += entry.get('da_amount', 0)
        else:
            tour_count += 1
            total_km += km
            total_liters_petrol += entry.get('petrol_liters', 0)
            total_liters_mobil += entry.get('mobil_liters', 0)
            total_petrol_cost += entry.get('petrol_cost', 0)
            total_mobil_cost += entry.get('mobil_cost', 0)
            total_da += entry.get('da_amount', 0)
            
            # Friday check
            from datetime import datetime
            dt = datetime.strptime(entry['date'], '%Y-%m-%d')
            if dt.weekday() == 4: # Friday
                friday_tour_count += 1
            
            if entry.get('others_designation'):
                manager_tour_count += 1
            
            if km < 50:
                short_tour_count += 1
                
    net_tours = tour_count - friday_tour_count - meeting_count
    
    total_amount = total_petrol_cost + total_mobil_cost + total_da + total_others
    
    return {
        'total_tour': tour_count + meeting_count,
        'friday_tour': friday_tour_count,
        'meeting_count': meeting_count,
        'manager_tour': manager_tour_count,
        'short_tour': short_tour_count,
        'net_tours': net_tours if net_tours >= 0 else 0,
        'total_liters_petrol': total_liters_petrol,
        'total_liters_mobil': total_liters_mobil,
        'total_km': total_km,
        'total_petrol_cost': total_petrol_cost,
        'total_mobil_cost': total_mobil_cost,
        'total_da': total_da,
        'total_others': total_others,
        'grand_total': total_amount
    }


# ── Petrol / Mobil threshold tracking ─────────────────────

PETROL_THRESHOLD_KM = 480
MOBIL_THRESHOLD_KM = 1000

def _coerce_threshold(value, default: int) -> int:
    """Accept ints/floats/numeric strings; fall back to the default for anything
    unparseable or non-positive."""
    try:
        n = int(float(value))
        return n if n > 0 else default
    except (TypeError, ValueError):
        return default


def get_thresholds(prefs: dict | None) -> tuple[int, int]:
    """Return (petrol_threshold, mobil_threshold) with per-user overrides."""
    p = prefs or {}
    return (
        _coerce_threshold(p.get('petrol_threshold'), PETROL_THRESHOLD_KM),
        _coerce_threshold(p.get('mobil_threshold'),  MOBIL_THRESHOLD_KM),
    )

def _refill_status(entries, liters_field, overflow_field, threshold):
    """
    Compute distance since last refill and whether a refill is due.
    Returns dict with distance_since, is_due, effective_threshold,
    effective_remaining, carry_forward.
    """
    sorted_entries = sorted(entries, key=lambda e: e['date'])
    last_refill_idx = -1
    carry_forward = 0

    for i in range(len(sorted_entries) - 1, -1, -1):
        if sorted_entries[i].get(liters_field, 0) > 0:
            last_refill_idx = i
            carry_forward = sorted_entries[i].get(overflow_field, 0)
            break

    if last_refill_idx == -1:
        # No refill found — use total distance of ALL entries as baseline
        distance_since = sum(e.get('total_km', 0) for e in sorted_entries)
        is_due = distance_since >= threshold
        return {
            'distance_since': distance_since,
            'is_due': is_due,
            'effective_threshold': threshold,
            'effective_remaining': max(0, threshold - distance_since),
            'carry_forward': 0,
        }

    distance_since = 0
    for i in range(last_refill_idx, len(sorted_entries)):
        distance_since += sorted_entries[i].get('total_km', 0)

    effective_threshold = threshold - carry_forward
    is_due = distance_since >= effective_threshold

    return {
        'distance_since': distance_since,
        'is_due': is_due,
        'effective_threshold': effective_threshold,
        'effective_remaining': max(0, effective_threshold - distance_since),
        'carry_forward': carry_forward,
    }


def get_petrol_status(entries, threshold: int | None = None):
    """Get petrol refill tracking status based on stored entries."""
    return _refill_status(entries, 'petrol_liters', 'petrol_overflow',
                          threshold if threshold else PETROL_THRESHOLD_KM)


def get_mobil_status(entries, threshold: int | None = None):
    """Get mobil refill tracking status based on stored entries."""
    return _refill_status(entries, 'mobil_liters', 'mobil_overflow',
                          threshold if threshold else MOBIL_THRESHOLD_KM)


def calc_carry_forward(entries, new_entry_km, liters_field, overflow_field, threshold):
    """
    Calculate signed carry-forward when adding a new entry that includes a refill.
    Should be called BEFORE the entry is saved (entries = existing data only).

    Returns SIGNED value:
      - Negative: km remaining (refuelled before threshold — petrol still left)
      - Positive: excess km (exceeded threshold — next threshold reduced)
      - Zero:     exactly at threshold
    """
    sorted_entries = sorted(entries, key=lambda e: e['date'])
    if not sorted_entries:
        return 0

    last_refill_idx = -1
    prev_carry = 0

    for i in range(len(sorted_entries) - 1, -1, -1):
        if sorted_entries[i].get(liters_field, 0) > 0:
            last_refill_idx = i
            prev_carry = sorted_entries[i].get(overflow_field, 0)
            break

    if last_refill_idx == -1:
        return 0

    distance_since = new_entry_km
    for i in range(last_refill_idx, len(sorted_entries)):
        distance_since += sorted_entries[i].get('total_km', 0)

    effective_threshold = threshold - prev_carry
    return distance_since - effective_threshold


def calculate_fuel_since_refill(entries, liters_field, threshold_km):
    """
    Calculate fuel consumed from the last refill entry to the final entry.
    Used when an entry is marked as the last tour of the month.

    Returns:
        distance_since_refill: total km from last refill to end
        liters_consumed: proportional liters consumed based on efficiency
        last_refill_liters: liters of the last refill found
    """
    sorted_entries = sorted(entries, key=lambda e: e['date'])
    if not sorted_entries:
        return {'distance_since_refill': 0, 'liters_consumed': 0, 'last_refill_liters': 0}

    last_refill_idx = -1
    last_refill_liters = 0
    for i in range(len(sorted_entries) - 1, -1, -1):
        liters = sorted_entries[i].get(liters_field, 0)
        if liters > 0:
            last_refill_idx = i
            last_refill_liters = liters
            break

    if last_refill_idx == -1 or last_refill_liters == 0:
        return {'distance_since_refill': 0, 'liters_consumed': 0, 'last_refill_liters': 0}

    distance = 0
    for i in range(last_refill_idx, len(sorted_entries)):
        distance += sorted_entries[i].get('total_km', 0)

    efficiency = threshold_km / last_refill_liters
    liters_consumed = round(distance / efficiency, 2) if efficiency > 0 else 0

    return {
        'distance_since_refill': distance,
        'liters_consumed': liters_consumed,
        'last_refill_liters': last_refill_liters
    }
