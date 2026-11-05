import pytest
from controller import DeterministicMatcher

def test_exact_voltage_and_connector_match():
    reqs = {"voltage_v": 12.0, "connector_type": "USB-C", "power_w": 45.0}
    part = {"voltage_v": 12.0, "connector_type": "usb-c", "max_power_w": 65.0}
    
    is_compat, passed, failed = DeterministicMatcher.is_compatible(reqs, part)
    assert is_compat is True
    assert len(failed) == 0

def test_voltage_mismatch_fails():
    reqs = {"voltage_v": 5.0, "connector_type": "Barrel_5.5mm", "power_w": 10.0}
    part = {"voltage_v": 12.0, "connector_type": "Barrel_5.5mm", "max_power_w": 20.0}
    
    is_compat, passed, failed = DeterministicMatcher.is_compatible(reqs, part)
    assert is_compat is False
    assert any("Voltage mismatch" in err for err in failed)

def test_insufficient_power_rating_fails():
    reqs = {"voltage_v": 24.0, "connector_type": "Terminal_Block", "power_w": 100.0}
    part = {"voltage_v": 24.0, "connector_type": "Terminal_Block", "max_power_w": 50.0}
    
    is_compat, passed, failed = DeterministicMatcher.is_compatible(reqs, part)
    assert is_compat is False
    assert any("Insufficient power" in err for err in failed)

def test_current_to_power_calculation():
    # 12V @ 2A = 24W required
    reqs = {"voltage_v": 12.0, "connector_type": "USB-C", "current_a": 2.0}
    part = {"voltage_v": 12.0, "connector_type": "USB-C", "max_power_w": 30.0}
    
    is_compat, passed, failed = DeterministicMatcher.is_compatible(reqs, part)
    assert is_compat is True