#!/usr/bin/env python3
"""
Energy Intelligence Node  ─  Single-file data ingestion + REST API
===================================================================
Rastrea claims físicos de tecnologías de energía renovable de nueva generación.

Fuentes:  ArXiv (papers) · USPTO PatentsView (patentes) · Climate Tech PR
Storage:  SQLite
API:      FastAPI

Uso:
    pip install fastapi uvicorn requests beautifulsoup4 lxml
    python energy_intel_node.py              # crea DB + lanza API en :8000
    python energy_intel_node.py --scrape     # modo CLI: solo ingesta, sin API

Arquitectura (todo en este archivo, < 500 líneas):
    ┌─────────────┐   ┌──────────────┐   ┌──────────────────┐
    │  ArXiv API  │   │ USPTO PV API │   │  Climate Tech PR │
    └──────┬──────┘   └──────┬───────┘   └────────┬─────────┘
           │                 │                     │
           └──────────┬──────┴─────────────────────┘
                      ▼
              ┌───────────────┐
              │  IngestPipeline│  ← dedup + normaliza
              └───────┬───────┘
                      ▼
              ┌───────────────┐
              │   SQLite DB   │  tabla: claims
              └───────┬───────┘
                      ▼
              ┌───────────────┐
              │   FastAPI      │  GET/POST /claims, /stats, /scrape
              └───────────────┘
"""

import argparse, hashlib, json, re, sqlite3, time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup

# ──────────────────────────── CONFIG ─────────────────────────────

DB_PATH       = "energy_intel.db"
ARXIV_API     = "https://export.arxiv.org/api/query"
USPTO_PV_API  = "https://api.patentsview.org/patents/query"
CLIMATE_FEEDS = [
    "https://cleantechnica.com/feed/",
    "https://renewablesnow.com/feed/",
]
SCRAPE_DELAY  = 2.0   # segundos entre requests (educado)
MAX_RESULTS   = 25    # por fuente por corrida

# ──────────────────────── DATABASE LAYER ─────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS claims (
    id            TEXT PRIMARY KEY,          -- hash(source_url + title + date)
    source_type   TEXT NOT NULL,             -- paper | patent | press_release
    source_url    TEXT NOT NULL,
    title         TEXT NOT NULL,
    authors       TEXT DEFAULT '',
    date_pub      TEXT NOT NULL,             -- ISO-8601
    technology    TEXT NOT NULL,             -- ej: solid-state-battery, perovskite-solar
    metric_name   TEXT DEFAULT '',           -- ej: energy_density, efficiency
    metric_value  REAL,
    metric_unit   TEXT DEFAULT '',           -- ej: Wh/kg, %
    claim_text    TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'claimed',  -- claimed | disputed | debunked
    raw_json      TEXT DEFAULT '{}',
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tech   ON claims(technology);
CREATE INDEX IF NOT EXISTS idx_status ON claims(status);
CREATE INDEX IF NOT EXISTS idx_date   ON claims(date_pub);
"""

@contextmanager
def db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with db_conn() as c:
        c.executescript(SCHEMA)

def claim_id(url: str, title: str, date: str) -> str:
    raw = f"{url}|{title}|{date}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]

def upsert_claim(conn, claim: dict) -> bool:
    """Inserta claim si no existe (dedup por id). Devuelve True si nuevo."""
    cid = claim_id(claim["source_url"], claim["title"], claim["date_pub"])
    existing = conn.execute("SELECT 1 FROM claims WHERE id=?", (cid,)).fetchone()
    if existing:
        return False
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        INSERT INTO claims (id,source_type,source_url,title,authors,date_pub,
            technology,metric_name,metric_value,metric_unit,claim_text,
            status,raw_json,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (cid, claim["source_type"], claim["source_url"], claim["title"],
          claim.get("authors",""), claim["date_pub"], claim["technology"],
          claim.get("metric_name",""), claim.get("metric_value"),
          claim.get("metric_unit",""), claim["claim_text"],
          claim.get("status","claimed"), json.dumps(claim.get("raw",{})),
          now, now))
    return True

# ──────────────────── EXTRACTION HELPERS ─────────────────────────

TECH_KEYWORDS = {
    "solid-state-battery":  r"solid.?state.?batter|ssb|sulfide.?electrolyte",
    "perovskite-solar":     r"perovskite.?solar|psk.?pv|perovskite.?photovol",
    "sodium-ion":           r"sodium.?ion.?batter|na.?ion",
    "green-hydrogen":       r"green.?hydrogen|electrolysis|pem.?electroly",
    "flow-battery":         r"flow.?batter|redox.?flow|vanadium.?flow",
    "thermophotovoltaic":   r"thermophotovoltaic|tpv|thermo.?pv",
    "fusion":               r"fusion.?energy|inertial.?confinement|magnetic.?fusion",
    "agrivoltaics":         r"agrivoltaic|dual.?use.?solar|crop.?solar",
}

METRIC_PATTERNS = [
    # (regex, metric_name, unit, value_group_idx)
    (r"(\d+(?:\.\d+)?)\s*Wh/kg",              "energy_density",  "Wh/kg", 1),
    (r"(\d+(?:\.\d+)?)\s*Wh/L",               "volumetric_density","Wh/L",1),
    (r"(\d+(?:\.\d+)?)\s*%\s*(?:efficiency|PCE|power conversion)",
                                                "efficiency",      "%",      1),
    (r"(\d+(?:\.\d+)?)\s*mW/cm[²2]",          "power_density",   "mW/cm²", 1),
    (r"(\d+(?:\.\d+)?)\s*kW/kg",              "specific_power",  "kW/kg",  1),
    (r"(\d+(?:\.\d+)?)\s*\$/kWh",             "cost",            "$/kWh",  1),
    (r"(\d+(?:\.\d+)?)\s*hours?.*cycling",     "cycle_life",      "hours",  1),
    (r"(\d+(?:\.\d+)?)\s*cycles",             "cycle_life",      "cycles", 1),
]

def classify_technology(text: str) -> str:
    low = text.lower()
    for tech, pat in TECH_KEYWORDS.items():
        if re.search(pat, low):
            return tech
    return "other"

def extract_metrics(text: str) -> dict:
    """Extrae la primera métrica reconocida del texto."""
    for pat, name, unit, gidx in METRIC_PATTERNS:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return {"metric_name": name, "metric_value": float(m.group(gidx)),
                    "metric_unit": unit}
    return {}

# ──────────────────── SCRAPERS ───────────────────────────────────

def scrape_arxiv(query: str = "all:renewable energy AND cat:physics*",
                 max_results: int = MAX_RESULTS) -> list[dict]:
    """ArXiv API (Atom XML) → lista de claims normalizados."""
    claims = []
    params = {"search_query": query, "start": 0, "max_results": max_results,
              "sortBy": "submittedDate", "sortOrder": "descending"}
    try:
        r = requests.get(ARXIV_API, params=params, timeout=30)
        r.raise_for_status()
    except Exception as e:
        print(f"[ArXiv] Error: {e}")
        return claims

    soup = BeautifulSoup(r.text, "lxml-xml")
    for entry in soup.find_all("entry"):
        title_t = entry.find("title")
        summ_t  = entry.find("summary")
        id_t    = entry.find("id")
        pub_t   = entry.find("published")
        if not title_t or not id_t:
            continue
        title = title_t.get_text(strip=True).replace("\n"," ")
        abstract = summ_t.get_text(strip=True).replace("\n"," ") if summ_t else ""
        url = id_t.get_text(strip=True)
        published = pub_t.get_text(strip=True)[:10] if pub_t else ""
        author_names = entry.find_all("name")
        authors = ", ".join(a.get_text() for a in author_names[:5])
        tech = classify_technology(f"{title} {abstract}")
        meta = extract_metrics(f"{title} {abstract}")
        claims.append({
            "source_type": "paper",
            "source_url": url,
            "title": title,
            "authors": authors,
            "date_pub": published,
            "technology": tech,
            **meta,
            "claim_text": abstract[:500],
            "raw": {"abstract_len": len(abstract)},
        })
    print(f"[ArXiv] {len(claims)} papers")
    return claims

def scrape_uspto(terms: list[str] = None, max_results: int = MAX_RESULTS) -> list[dict]:
    """USPTO PatentsView API → claims de patentes."""
    if terms is None:
        terms = ["solid state battery", "perovskite solar cell",
                 "sodium ion battery", "green hydrogen electrolysis"]
    claims = []
    for term in terms:
        body = {
            "q": {"_and": [
                {"_text_any": {"patent_title": term}},
                {"_gte": {"patent_date": "2023-01-01"}}
            ]},
            "f": ["patent_number","patent_title","patent_date",
                  "inventor_first_name","inventor_last_name","patent_abstract"],
            "s": [{"patent_date":"desc"}],
            "o": {"per_page": min(max_results, 25)}
        }
        try:
            r = requests.post(USPTO_PV_API, json=body, timeout=30)
            r.raise_for_status()
        except Exception as e:
            print(f"[USPTO] Error '{term}': {e}")
            continue
        try:
            patents = r.json().get("patents") or []
        except Exception:
            patents = []
        for p in patents:
            title = p.get("patent_title","")
            abstract = p.get("patent_abstract","") or ""
            invs = p.get("inventors") or []
            authors = ", ".join(
                f"{i.get('inventor_first_name','')} {i.get('inventor_last_name','')}".strip()
                for i in invs[:5])
            url = f"https://patents.google.com/patent/US{p.get('patent_number','')}"
            tech = classify_technology(f"{title} {abstract}")
            meta = extract_metrics(f"{title} {abstract}")
            claims.append({
                "source_type": "patent",
                "source_url": url,
                "title": title,
                "authors": authors,
                "date_pub": p.get("patent_date","")[:10],
                "technology": tech,
                **meta,
                "claim_text": abstract[:500],
                "raw": {"patent_number": p.get("patent_number","")},
            })
        time.sleep(SCRAPE_DELAY)
    print(f"[USPTO] {len(claims)} patents")
    return claims

def scrape_climate_pr(feeds: list[str] = None) -> list[dict]:
    """RSS feeds de Climate Tech → press releases."""
    feeds = feeds or CLIMATE_FEEDS
    claims = []
    for feed_url in feeds:
        try:
            r = requests.get(feed_url, timeout=20,
                             headers={"User-Agent":"EnergyIntelBot/1.0"})
            r.raise_for_status()
        except Exception as e:
            print(f"[PR] Error {feed_url}: {e}")
            continue
        soup = BeautifulSoup(r.text, "lxml-xml")
        for item in soup.find_all("item")[:MAX_RESULTS]:
            title_tag = item.find("title")
            link_tag  = item.find("link")
            date_tag  = item.find("pubDate") or item.find("dc:date")
            desc_tag  = item.find("description") or item.find("content:encoded")
            title = title_tag.get_text(strip=True) if title_tag else ""
            link  = link_tag.get_text(strip=True) if link_tag else feed_url
            raw_date = date_tag.get_text(strip=True) if date_tag else ""
            desc  = desc_tag.get_text(strip=True)[:500] if desc_tag else title
            try:
                date_pub = datetime.strptime(raw_date[:25],
                             "%a, %d %b %Y %H:%M:%S").strftime("%Y-%m-%d")
            except Exception:
                date_pub = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            tech = classify_technology(f"{title} {desc}")
            if tech == "other":
                continue  # filtrar ruido
            meta = extract_metrics(f"{title} {desc}")
            claims.append({
                "source_type": "press_release",
                "source_url": link,
                "title": title,
                "authors": "",
                "date_pub": date_pub,
                "technology": tech,
                **meta,
                "claim_text": desc[:500],
                "raw": {"feed": feed_url},
            })
        time.sleep(SCRAPE_DELAY)
    print(f"[PR] {len(claims)} releases")
    return claims

# ──────────────────── INGEST PIPELINE ────────────────────────────

def run_ingest():
    """Ejecuta todos los scrapers y hace upsert en la DB."""
    init_db()
    new = 0
    with db_conn() as conn:
        for scraper in [scrape_arxiv, scrape_uspto, scrape_climate_pr]:
            for claim in scraper():
                if upsert_claim(conn, claim):
                    new += 1
    print(f"\n✓ Ingesta completa: {new} claims nuevos")
    return new

# ──────────────────── REST API ───────────────────────────────────

def create_app():
    from fastapi import FastAPI, Query, HTTPException
    from pydantic import BaseModel as PydModel

    app = FastAPI(title="Energy Intelligence Node",
                  version="1.0.0",
                  description="API para consultar claims de energías renovables")

    # ── Pydantic models ──
    class ClaimOut(PydModel):
        id: str; source_type: str; source_url: str; title: str
        authors: str = ""; date_pub: str; technology: str
        metric_name: str = ""; metric_value: Optional[float]=None
        metric_unit: str = ""; claim_text: str; status: str
        created_at: str; updated_at: str

    class ClaimIn(PydModel):
        source_type: str; source_url: str; title: str; authors: str = ""
        date_pub: str; technology: str; metric_name: str = ""
        metric_value: Optional[float]=None; metric_unit: str = ""
        claim_text: str; status: str = "claimed"

    class StatusPatch(PydModel):
        status: str  # claimed | disputed | debunked

    class StatsOut(PydModel):
        total_claims: int; by_source: dict; by_status: dict
        by_technology: dict

    # ── Helpers ──
    def row_to_dict(row):
        d = dict(row)
        d["metric_value"] = float(d["metric_value"]) if d["metric_value"] else None
        return d

    # ── Endpoints ──
    @app.get("/claims", response_model=list[ClaimOut])
    def list_claims(
        technology: Optional[str] = Query(None, description="Filtrar por tecnología"),
        status: Optional[str] = Query(None, description="claimed|disputed|debunked"),
        source_type: Optional[str] = Query(None, description="paper|patent|press_release"),
        metric_name: Optional[str] = Query(None, description="ej: energy_density"),
        limit: int = Query(50, ge=1, le=200),
        offset: int = Query(0, ge=0),
    ):
        """Consultar claims con filtros opcionales."""
        conds, params = [], []
        if technology:  conds.append("technology=?");  params.append(technology)
        if status:      conds.append("status=?");      params.append(status)
        if source_type: conds.append("source_type=?"); params.append(source_type)
        if metric_name: conds.append("metric_name=?"); params.append(metric_name)
        where = ("WHERE " + " AND ".join(conds)) if conds else ""
        with db_conn() as conn:
            rows = conn.execute(
                f"SELECT * FROM claims {where} ORDER BY date_pub DESC LIMIT ? OFFSET ?",
                params + [limit, offset]).fetchall()
        return [row_to_dict(r) for r in rows]

    @app.get("/claims/{claim_id}", response_model=ClaimOut)
    def get_claim(claim_id: str):
        with db_conn() as conn:
            row = conn.execute("SELECT * FROM claims WHERE id=?", (claim_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Claim no encontrado")
        return row_to_dict(row)

    @app.post("/claims", response_model=ClaimOut, status_code=201)
    def add_claim(body: ClaimIn):
        with db_conn() as conn:
            claim = body.model_dump()
            cid = claim_id(claim["source_url"], claim["title"], claim["date_pub"])
            if conn.execute("SELECT 1 FROM claims WHERE id=?", (cid,)).fetchone():
                raise HTTPException(409, "Claim ya existe")
            now = datetime.now(timezone.utc).isoformat()
            conn.execute("""
                INSERT INTO claims (id,source_type,source_url,title,authors,date_pub,
                    technology,metric_name,metric_value,metric_unit,claim_text,
                    status,raw_json,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (cid, claim["source_type"], claim["source_url"], claim["title"],
                  claim.get("authors",""), claim["date_pub"], claim["technology"],
                  claim.get("metric_name",""), claim.get("metric_value"),
                  claim.get("metric_unit",""), claim["claim_text"],
                  claim.get("status","claimed"), "{}", now, now))
            row = conn.execute("SELECT * FROM claims WHERE id=?", (cid,)).fetchone()
        return row_to_dict(row)

    @app.patch("/claims/{claim_id}", response_model=ClaimOut)
    def update_status(claim_id: str, body: StatusPatch):
        if body.status not in ("claimed","disputed","debunked"):
            raise HTTPException(400, "status debe ser claimed|disputed|debunked")
        with db_conn() as conn:
            if not conn.execute("SELECT 1 FROM claims WHERE id=?", (claim_id,)).fetchone():
                raise HTTPException(404, "Claim no encontrado")
            now = datetime.now(timezone.utc).isoformat()
            conn.execute("UPDATE claims SET status=?, updated_at=? WHERE id=?",
                         (body.status, now, claim_id))
            row = conn.execute("SELECT * FROM claims WHERE id=?", (claim_id,)).fetchone()
        return row_to_dict(row)

    @app.get("/stats", response_model=StatsOut)
    def stats():
        with db_conn() as conn:
            total = conn.execute("SELECT COUNT(*) c FROM claims").fetchone()["c"]
            by_source = dict(conn.execute(
                "SELECT source_type, COUNT(*) c FROM claims GROUP BY source_type").fetchall())
            by_status = dict(conn.execute(
                "SELECT status, COUNT(*) c FROM claims GROUP BY status").fetchall())
            by_tech = dict(conn.execute(
                "SELECT technology, COUNT(*) c FROM claims GROUP BY technology "
                "ORDER BY c DESC LIMIT 20").fetchall())
        return {"total_claims": total, "by_source": by_source,
                "by_status": by_status, "by_technology": by_tech}

    @app.post("/scrape")
    def trigger_scrape():
        """Dispara ingesta asíncrona (en prod usar Celery/background task)."""
        new = run_ingest()
        return {"new_claims": new, "status": "ok"}

    @app.get("/technologies")
    def list_technologies():
        with db_conn() as conn:
            rows = conn.execute(
                "SELECT technology, COUNT(*) c FROM claims GROUP BY technology "
                "ORDER BY c DESC").fetchall()
        return [{"technology": r["technology"], "count": r["c"]} for r in rows]

    return app

# ──────────────────── MAIN ───────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Energy Intelligence Node")
    parser.add_argument("--scrape", action="store_true",
                        help="Solo ejecutar ingesta (sin API)")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--db", default=DB_PATH, help="Ruta a SQLite DB")
    args = parser.parse_args()

    DB_PATH = args.db
    init_db()

    if args.scrape:
        run_ingest()
    else:
        import uvicorn
        app = create_app()
        print(f"\n⚡ Energy Intelligence Node → http://{args.host}:{args.port}")
        print(f"   Docs: http://{args.host}:{args.port}/docs")
        print(f"   DB:   {DB_PATH}\n")
        uvicorn.run(app, host=args.host, port=args.port)
