# tests/unit/test_bot_logic.py
from bot import calculate_total_price

def test_calculate_total_price_ig_bulk():
    assert calculate_total_price("ig_0_us", 250) == 250.0    # $1
    assert calculate_total_price("ig_0_us", 100) == 120.0   # $1.20
    assert calculate_total_price("ig_0_us", 50) == 75.0     # $1.50

def test_calculate_total_price_snapchat():
    assert calculate_total_price("snap_0_us", 11) == 55.0   # $5
    assert calculate_total_price("snap_0_us", 6) == 42.0    # $7
    assert calculate_total_price("snap_0_us", 3) == 30.0    # $10