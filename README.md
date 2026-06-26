# Energy Intelligence Node (EIN)

**Open-Source AI to Audit Climate Tech Claims and Fight Greenwashing.**

The transition to renewable energy is slowed by two things: physical
engineering bottlenecks, and corporate greenwashing. EIN is an open-source
intelligence pipeline that ingests scientific papers (ArXiv), patents (USPTO),
and technical press, extracts physical claims (e.g., "500 Wh/kg density",
"99% efficiency"), and automatically flags those that violate fundamental
physical laws or exceed known practical ceilings.

## Why This Matters (Energy Justice)

Global South governments and marginalized (MAPA) communities often lack the
technical capacity to audit whether a multi-million dollar green technology
actually works or if it is venture-capital marketing. EIN levels the playing
field by providing technology intelligence that runs locally on a standard
laptop, without relying on expensive proprietary APIs.

## How It Works

1. Ingestion - Automated scraping of ArXiv, USPTO PatentsView, and RSS feeds.
2. Extraction - Regex-based extraction of all physical metrics in a text
   (Wh/kg, percent, dollars/kWh, cycles, mW/cm2, kW/kg).
3. Contradiction Engine - A deterministic physical-limits checker
   (src/contradiction_engine.py) cross-references each metric against a
   knowledge base of fundamental laws and practical ceilings, assigning a
   verdict:
   - claimed   - no violation detected (not a guarantee of truth).
   - disputed  - exceeds a known practical ceiling; needs verification.
   - debunked  - violates a fundamental physical law; physically impossible.
4. Output - A queryable REST API (FastAPI) including a /contradictions endpoint
   that lists every flagged claim with a human-readable explanation and the
   physical law involved.

### Physical laws and ceilings currently encoded

| Domain | Rule | Type |
|--------|------|------|
| Any | Conversion efficiency <= 100% | Law (1st law of thermodynamics) |
| Single-junction PV | Efficiency <= 33.7% | Law (Shockley-Queisser) |
| Wind | Power extraction <= 59.3% | Law (Betz limit) |
| Green hydrogen | Electrolysis efficiency <= ~83% (HHV) | Practical ceiling |
| Solid-state / Na-ion / flow batteries | Demonstrated cell-level density | Practical ceiling |

The engine is transparent and auditable by design: every verdict cites the
exact law/threshold and an explanation. The knowledge base is easy to extend.

### Roadmap

- Optional LLM layer for subtle contradictions deterministic rules cannot catch
  (e.g., lab-vs-module efficiency drops). Designed to be optional so the core
  always runs offline.
- Additional regional scrapers (ANEEL Brazil, CREG Colombia).
- Localization of reports (Spanish, Portuguese, indigenous languages).

## Quickstart

Commands (run from the repository root):

    pip install -r requirements.txt
    python src/energy_intel_node.py            # API on :8000  ->  /docs
    python src/energy_intel_node.py --scrape   # ingestion only
    python src/contradiction_engine.py         # try the engine directly
    pytest tests/ -v                           # run the test suite (23 tests)

USPTO patents require a free PatentsView API key
(https://patentsview.org/apis/keyrequest). Export it as PATENTSVIEW_API_KEY.
Without it, patent scraping is skipped cleanly and the rest keeps working.

## Key API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET  | /claims | List claims (filter by technology, status, source). |
| GET  | /contradictions | List flagged claims (disputed / debunked). |
| POST | /claims | Add a claim (auto-evaluated by the engine). |
| POST | /scrape | Trigger ingestion from all sources. |
| POST | /recheck | Re-run the engine over stored claims. |
| GET  | /stats | Aggregate counts by source / status / technology. |

## Contributing

We are seeking collaborators, especially data scientists, energy researchers,
and open-source advocates from the Global South. See CONTRIBUTING.md.

## License

MIT License - see LICENSE.
