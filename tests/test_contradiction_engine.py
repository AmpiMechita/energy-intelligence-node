"""Tests del motor de contradicción (límites físicos deterministas)."""
from contradiction_engine import check_metric, evaluate_claim

def test_efficiency_above_100_is_debunked_universal():
    v = evaluate_claim("other", [{"metric_name": "efficiency",
                                  "metric_value": 120.0, "metric_unit": "%"}])
    assert v["status"] == "debunked"
    assert "termodin" in v["flag_law"].lower()

def test_perovskite_single_junction_exceeds_shockley_queisser():
    v = evaluate_claim("perovskite-solar", [{"metric_name": "efficiency",
                                             "metric_value": 41.0, "metric_unit": "%"}])
    assert v["status"] == "debunked"
    assert "Shockley" in v["flag_law"]

def test_wind_turbine_exceeds_betz_limit():
    v = evaluate_claim("wind", [{"metric_name": "efficiency",
                                 "metric_value": 65.0, "metric_unit": "%"}])
    assert v["status"] == "debunked"
    assert "Betz" in v["flag_law"]

def test_green_hydrogen_above_practical_ceiling_is_disputed():
    v = evaluate_claim("green-hydrogen", [{"metric_name": "efficiency",
                                           "metric_value": 95.0, "metric_unit": "%"}])
    assert v["status"] == "disputed"

def test_solid_state_battery_high_density_is_disputed():
    v = evaluate_claim("solid-state-battery", [{"metric_name": "energy_density",
                                                "metric_value": 650.0, "metric_unit": "Wh/kg"}])
    assert v["status"] == "disputed"

def test_sodium_ion_high_density_is_disputed():
    v = evaluate_claim("sodium-ion", [{"metric_name": "energy_density",
                                       "metric_value": 250.0, "metric_unit": "Wh/kg"}])
    assert v["status"] == "disputed"

def test_perovskite_within_limits_is_claimed():
    v = evaluate_claim("perovskite-solar", [{"metric_name": "efficiency",
                                             "metric_value": 25.0, "metric_unit": "%"}])
    assert v["status"] == "claimed"
    assert v["flag_reason"] == ""

def test_realistic_battery_is_claimed():
    v = evaluate_claim("solid-state-battery", [{"metric_name": "energy_density",
                                                "metric_value": 300.0, "metric_unit": "Wh/kg"}])
    assert v["status"] == "claimed"

def test_no_metrics_is_claimed():
    assert evaluate_claim("other", [])["status"] == "claimed"

def test_unit_mismatch_does_not_flag():
    assert check_metric("perovskite-solar", "efficiency", 40.0, "Wh/kg") == []

def test_hard_violation_takes_priority_over_soft():
    metrics = [
        {"metric_name": "efficiency", "metric_value": 150.0, "metric_unit": "%"},
        {"metric_name": "energy_density", "metric_value": 600.0, "metric_unit": "Wh/kg"},
    ]
    v = evaluate_claim("solid-state-battery", metrics)
    assert v["status"] == "debunked"

def test_none_value_is_ignored():
    assert check_metric("perovskite-solar", "efficiency", None, "%") == []

def test_silicon_single_junction_also_bound_by_shockley_queisser():
    v = evaluate_claim("silicon-solar", [{"metric_name": "efficiency",
                                          "metric_value": 36.0, "metric_unit": "%"}])
    assert v["status"] == "debunked"
    assert "Shockley" in v["flag_law"]
