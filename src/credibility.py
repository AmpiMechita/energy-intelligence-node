#!/usr/bin/env python3
"""
Credibility Scoring - Score de credibilidad determinista (0-100)
Convierte el veredicto del Contradiction Engine + senales de la fuente en un
score de credibilidad explicable, por afirmacion y por grupo.

El score NO mide "verdad", mide CREDIBILIDAD basada en:
  - El veredicto fisico (debunked/disputed/claimed) -> factor dominante.
  - El tipo de fuente (paper revisado > patente > nota de prensa).
  - Si reporta metricas cuantitativas verificables vs. afirmaciones vagas.
"""

from __future__ import annotations

SOURCE_WEIGHTS = {
    "paper": 15,
    "patent": 5,
    "press_release": -15,
    "": 0,
}

BAND_HIGH = 70
BAND_MEDIUM = 40

def _band(score: float) -> str:
    if score >= BAND_HIGH:
        return "high"
    if score >= BAND_MEDIUM:
        return "medium"
    return "low"

def _fmt(factors: list) -> list:
    return [{"factor": f, "delta": d, "reason": r} for f, d, r in factors]

def score_claim(claim: dict) -> dict:
    """Calcula el score de credibilidad (0-100) de una sola afirmacion."""
    factors = [("baseline", 60, "Punto de partida neutral")]
    score = 60
    status = claim.get("status", "claimed")

    if status == "debunked":
        factors.append(("verdict", -45, "DEBUNKED: viola una ley fisica fundamental"))
        return {"score": 15, "band": _band(15), "factors": _fmt(factors)}

    if status == "disputed":
        score -= 25
        factors.append(("verdict", -25, "DISPUTED: supera un techo practico conocido"))

    st = claim.get("source_type", "") or ""
    w = SOURCE_WEIGHTS.get(st, 0)
    if w:
        score += w
        factors.append(("source_type", w, f"Fuente de tipo '{st}'"))

    metrics = claim.get("checked_metrics") or []
    if isinstance(metrics, (list, tuple)) and len(metrics) > 0:
        score += 10
        factors.append(("metrics", 10, "Reporta metricas cuantitativas verificables"))
    else:
        score -= 10
        factors.append(("metrics", -10, "Sin metricas cuantitativas (afirmacion vaga)"))

    score = max(0, min(100, score))
    return {"score": score, "band": _band(score), "factors": _fmt(factors)}

def score_group(claims: list) -> dict:
    """Agrega el score de credibilidad de un grupo de afirmaciones."""
    if not claims:
        return {"count": 0, "avg_score": None, "band": None,
                "by_verdict": {}, "by_band": {}}
    scored = [score_claim(c) for c in claims]
    avg = round(sum(s["score"] for s in scored) / len(scored), 1)
    by_verdict: dict = {}
    by_band: dict = {}
    for c, s in zip(claims, scored):
        v = c.get("status", "claimed")
        by_verdict[v] = by_verdict.get(v, 0) + 1
        by_band[s["band"]] = by_band.get(s["band"], 0) + 1
    return {"count": len(claims), "avg_score": avg, "band": _band(avg),
            "by_verdict": by_verdict, "by_band": by_band}
