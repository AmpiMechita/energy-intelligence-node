#!/usr/bin/env python3
"""
Due-Diligence Report - Genera informes en Markdown a partir de claims.
Produce un informe que un inversor, banco o gobierno querria recibir antes de
financiar una tecnologia. Sin dependencias externas; 100% determinista.
"""

from __future__ import annotations

from datetime import datetime, timezone

try:
    from credibility import score_claim, score_group
except ImportError:  # pragma: no cover
    from .credibility import score_claim, score_group

NL = chr(10)

def _recommendation(agg: dict) -> str:
    if agg.get("count", 0) == 0:
        return "Sin datos suficientes para emitir una recomendacion."
    debunked = agg.get("by_verdict", {}).get("debunked", 0)
    disputed = agg.get("by_verdict", {}).get("disputed", 0)
    score = agg.get("avg_score") or 0
    if debunked:
        return (f"PRECAUCION ALTA: {debunked} afirmacion(es) violan leyes fisicas "
                "fundamentales (imposibles). Alto riesgo de greenwashing; exigir "
                "validacion independiente antes de cualquier inversion.")
    if score >= 70:
        return ("Credibilidad ALTA: no se detectaron banderas rojas fisicas. "
                f"({disputed} afirmacion(es) por verificar.)")
    if score >= 40:
        return (f"Credibilidad MEDIA: {disputed} afirmacion(es) superan techos "
                "practicos conocidos y requieren verificacion documental.")
    return "Credibilidad BAJA: revisar a fondo las afirmaciones antes de invertir."

def generate_report(title: str, claims: list) -> str:
    """Genera un informe de due-diligence en Markdown."""
    agg = score_group(claims)
    out = []
    out.append(f"# Informe de Due-Diligence Tecnico: {title}")
    out.append("")
    out.append(f"- Generado: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}")
    out.append(f"- Afirmaciones analizadas: {agg['count']}")
    if agg["avg_score"] is not None:
        out.append(f"- Credibilidad promedio: {agg['avg_score']}/100 "
                   f"({(agg['band'] or '').upper()})")
    out.append("")

    out.append("## Resumen de veredictos")
    if agg["by_verdict"]:
        for k, v in sorted(agg["by_verdict"].items()):
            out.append(f"- {k}: {v}")
    else:
        out.append("- (sin afirmaciones)")
    out.append("")

    out.append("## Detalle de afirmaciones")
    out.append("")
    out.append("| Score | Veredicto | Fuente | Titulo | Motivo |")
    out.append("|-------|-----------|--------|--------|--------|")
    for c in claims:
        s = score_claim(c)
        title_c = (c.get("title") or "")[:60].replace("|", "/")
        reason = (c.get("flag_reason") or "-")[:90].replace("|", "/")
        out.append(f"| {s['score']} | {c.get('status', '')} | "
                   f"{c.get('source_type', '')} | {title_c} | {reason} |")
    out.append("")

    out.append("## Recomendacion")
    out.append(_recommendation(agg))
    return NL.join(out)
