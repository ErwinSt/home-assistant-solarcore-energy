import importlib.util
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "solarcore_energy"
    / "util.py"
)
spec = importlib.util.spec_from_file_location("util", MODULE_PATH)
util = importlib.util.module_from_spec(spec)
spec.loader.exec_module(util)
parse_value = util.parse_value


def test_parse_power_kw():
    assert parse_value("0.5kW") == 500.0


def test_parse_energy_wh():
    assert parse_value("500Wh") == 0.5


def test_parse_temperature():
    assert parse_value("42°C") == 42.0


def test_parse_invalid():
    assert parse_value("N/A") is None
