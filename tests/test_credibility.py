"""Tests del scoring de credibilidad y del reporte de due-diligence."""
from credibility import score_claim, score_group
from report import generate_report

def test_debunked_claim_scores_very_low():
    c = {"status": "debunked", "source_type": "paper",
         "checked_metrics": [{"metric_name": "efficiency"}]}
    r = score_claim(c)
    assert r["score"] <= 20
    assert r["band"] == "low"

def test_solid_paper_with_metrics_scores_high():
    c = {"status": "claimed", "source_type": "paper",
         "checked_metrics": [{"metric_name": "efficiency"}]}
    r = score_claim(c)
    assert r["score"] >= 70
    assert r["band"] == "high"

def test_press_release_without_metrics_scores_lower():
    pr = score_claim({"status": "claimed", "source_type": "press_release",
                      "checked_metrics": []})
    paper = score_claim({"status": "claimed", "source_type": "paper",
                         "checked_metrics": [{"m": 1}]})
    assert pr["score"] < paper["score"]

def test_disputed_lowers_score():
    claimed = score_claim({"status": "claimed", "source_type": "patent",
                           "checked_metrics": [{"m": 1}]})
    disputed = score_claim({"status": "disputed", "source_type": "patent",
                            "checked_metrics": [{"m": 1}]})
    assert disputed["score"] < claimed["score"]

def test_factors_are_explained():
    r = score_claim({"status": "claimed", "source_type": "paper",
                     "checked_metrics": [{"m": 1}]})
    assert any(f["factor"] == "baseline" for f in r["factors"])
    assert all({"factor", "delta", "reason"} <= set(f) for f in r["factors"])

def test_score_is_clamped_0_100():
    r = score_claim({"status": "claimed", "source_type": "paper",
                     "checked_metrics": [{"m": 1}]})
    assert 0 <= r["score"] <= 100

def test_score_group_empty():
    g = score_group([])
    assert g["count"] == 0
    assert g["avg_score"] is None

def test_score_group_aggregates():
    claims = [
        {"status": "debunked", "source_type": "press_release", "checked_metrics": []},
        {"status": "claimed", "source_type": "paper", "checked_metrics": [{"m": 1}]},
    ]
    g = score_group(claims)
    assert g["count"] == 2
    assert g["by_verdict"]["debunked"] == 1
    assert 0 <= g["avg_score"] <= 100

def test_report_contains_sections_and_warning():
    claims = [
        {"status": "debunked", "source_type": "press_release",
         "title": "Solar 99% efficiency", "flag_reason": "viola Shockley",
         "checked_metrics": []},
    ]
    md = generate_report("perovskite-solar", claims)
    assert "Informe de Due-Diligence" in md
    assert "perovskite-solar" in md
    assert "Recomendacion" in md
    assert "PRECAUCION" in md

def test_report_empty_is_safe():
    md = generate_report("vacio", [])
    assert "Informe de Due-Diligence" in md
