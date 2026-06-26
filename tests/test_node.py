"""Tests de extracción de métricas, clasificación y API REST."""
import energy_intel_node as ein

def test_extract_all_metrics_finds_multiple():
    text = "We achieved 500 Wh/kg and 95% efficiency over 1000 cycles"
    metrics = ein.extract_all_metrics(text)
    names = {m["metric_name"] for m in metrics}
    assert {"energy_density", "efficiency", "cycle_life"} <= names

def test_extract_metrics_backward_compatible_returns_first():
    text = "Density of 400 Wh/kg reported"
    m = ein.extract_metrics(text)
    assert m["metric_name"] == "energy_density"
    assert m["metric_value"] == 400.0

def test_extract_all_metrics_dedupes():
    text = "95% efficiency, again 95% efficiency"
    metrics = ein.extract_all_metrics(text)
    effs = [m for m in metrics if m["metric_name"] == "efficiency"]
    assert len(effs) == 1

def test_classify_perovskite():
    assert ein.classify_technology("a novel perovskite solar cell") == "perovskite-solar"

def test_classify_wind():
    assert ein.classify_technology("new offshore wind turbine design") == "wind"

def test_classify_unknown_is_other():
    assert ein.classify_technology("a paper about cats") == "other"

def test_annotate_claim_flags_impossible():
    claim = {
        "title": "Perovskite solar cell with 45% efficiency",
        "claim_text": "We report a record 45% efficiency single junction device",
        "technology": "perovskite-solar",
        "status": "claimed",
    }
    ein.annotate_claim(claim)
    assert claim["status"] == "debunked"
    assert claim["flag_law"]

def test_annotate_respects_manual_verdict():
    claim = {
        "title": "Perovskite cell 45% efficiency",
        "claim_text": "x",
        "technology": "perovskite-solar",
        "status": "disputed",
    }
    ein.annotate_claim(claim)
    assert claim["status"] == "disputed"

def _client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setattr(ein, "DB_PATH", str(tmp_path / "test.db"))
    ein.init_db()
    return TestClient(ein.create_app())

def test_api_flags_impossible_claim_on_post(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    payload = {
        "source_type": "paper", "source_url": "http://example.com/1",
        "title": "Perovskite cell 45% efficiency",
        "date_pub": "2026-01-01", "technology": "perovskite-solar",
        "claim_text": "We report 45% efficiency",
    }
    r = client.post("/claims", json=payload)
    assert r.status_code == 201
    assert r.json()["status"] == "debunked"
    assert r.json()["flag_law"]

def test_api_contradictions_endpoint(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.post("/claims", json={
        "source_type": "paper", "source_url": "http://example.com/2",
        "title": "Wind turbine 70% efficiency", "date_pub": "2026-01-01",
        "technology": "wind", "claim_text": "70% efficiency"})
    client.post("/claims", json={
        "source_type": "paper", "source_url": "http://example.com/3",
        "title": "Realistic perovskite 24% efficiency", "date_pub": "2026-01-01",
        "technology": "perovskite-solar", "claim_text": "24% efficiency"})
    flagged = client.get("/contradictions").json()
    assert len(flagged) == 1
    assert flagged[0]["status"] == "debunked"

def test_api_recheck(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    with ein.db_conn() as conn:
        ein.upsert_claim(conn, {
            "source_type": "paper", "source_url": "http://example.com/4",
            "title": "Solar 99% efficiency", "date_pub": "2026-01-01",
            "technology": "perovskite-solar",
            "claim_text": "99% efficiency single junction", "status": "claimed"})
    res = client.post("/recheck").json()
    assert res["newly_flagged"] == 1

def test_api_claim_score_endpoint(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    r = client.post("/claims", json={
        "source_type": "paper", "source_url": "http://example.com/s1",
        "title": "Perovskite 24% efficiency", "date_pub": "2026-01-01",
        "technology": "perovskite-solar", "claim_text": "24% efficiency"})
    cid = r.json()["id"]
    sc = client.get(f"/claims/{cid}/score").json()
    assert 0 <= sc["score"] <= 100
    assert sc["band"] in ("high", "medium", "low")
    assert isinstance(sc["factors"], list) and sc["factors"]

def test_api_report_endpoint(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.post("/claims", json={
        "source_type": "press_release", "source_url": "http://example.com/s2",
        "title": "Solar 99% efficiency", "date_pub": "2026-01-01",
        "technology": "perovskite-solar", "claim_text": "99% efficiency"})
    rep = client.get("/report", params={"technology": "perovskite-solar"}).json()
    assert rep["title"] == "perovskite-solar"
    assert rep["aggregate"]["count"] == 1
    assert "Informe de Due-Diligence" in rep["markdown"]


def test_extract_efficiency_word_before_value():
    m = ein.extract_all_metrics("The cell reached an efficiency of 25.3% under AM1.5")
    assert any(x["metric_name"] == "efficiency" and x["metric_value"] == 25.3 for x in m)

def test_extract_pce_phrasing():
    m = ein.extract_all_metrics("power conversion efficiency reached 24.1 %")
    assert any(x["metric_name"] == "efficiency" and x["metric_value"] == 24.1 for x in m)

def test_extract_energy_density_word_before():
    m = ein.extract_all_metrics("an energy density of 500 Wh/kg was achieved")
    assert any(x["metric_name"] == "energy_density" and x["metric_value"] == 500.0 for x in m)

def test_extract_energy_density_spaced_unit():
    m = ein.extract_all_metrics("delivering 480 Wh kg at cell level")
    assert any(x["metric_name"] == "energy_density" and x["metric_value"] == 480.0 for x in m)

def test_extract_cost_dollar_prefix():
    m = ein.extract_all_metrics("a projected cost of $80/kWh")
    assert any(x["metric_name"] == "cost" and x["metric_value"] == 80.0 for x in m)

def test_arxiv_queries_are_focused():
    assert any("perovskite" in q for q in ein.ARXIV_QUERIES)
    assert any("battery" in q for q in ein.ARXIV_QUERIES)

def test_classify_no_false_positive_nation():
    assert ein.classify_technology("the national grid policy reform") == "other"
    assert ein.classify_technology("a combination of several materials") == "other"

def test_classify_sodium_ion_still_works():
    assert ein.classify_technology("a new sodium-ion battery cathode") == "sodium-ion"
    assert ein.classify_technology("Na-ion cell with improved cycling") == "sodium-ion"

def test_classify_silicon_solar():
    assert ein.classify_technology("crystalline silicon solar module") == "silicon-solar"

def test_classify_lithium_ion():
    assert ein.classify_technology("a lithium-ion battery anode") == "lithium-ion"
    assert ein.classify_technology("lion populations in Africa") == "other"
