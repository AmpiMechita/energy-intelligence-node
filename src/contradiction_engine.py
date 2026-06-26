#!/usr/bin/env python3
"""
Contradiction Engine  ─  Deterministic physical-limits checker
==============================================================
El "cerebro" del Energy Intelligence Node: audita las afirmaciones (claims)
de tecnologías de energía renovable contra LÍMITES FÍSICOS FUNDAMENTALES y
techos prácticos conocidos, para detectar greenwashing y exageraciones.

Diseño:
    - 100% determinista: mismas reglas → mismo veredicto. Auditable y explicable.
    - Sin LLM, sin APIs externas, sin dependencias. Corre en cualquier laptop.
      (Una capa opcional con LLM puede añadirse después para casos sutiles.)
    - Alta PRECISIÓN sobre recall: preferimos NO acusar antes que acusar mal.
      Una herramienta anti-greenwashing pierde toda credibilidad si exagera.

Veredictos:
    "claimed"  → no se detectó violación (no significa "verdadero").
    "disputed" → supera un techo PRÁCTICO conocido; requiere verificación.
    "debunked" → viola una LEY FÍSICA fundamental; físicamente imposible.

Fuentes de los límites (ver comentarios en PHYSICAL_LIMITS):
    - Límite de Shockley–Queisser (~33.7% celda solar de unión simple)
    - Límite de Betz (59.3% extracción de energía eólica)
    - 1ra/2da ley de la termodinámica (eficiencia <= 100%)
    - Techos prácticos demostrados por química de batería / electrólisis
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# ───────────────────────── MODELO DE LÍMITE ──────────────────────────

@dataclass(frozen=True)
class PhysicalLimit:
    """Un límite físico o techo práctico aplicable a una métrica."""

    metric_name: str  # ej: "efficiency", "energy_density"
    max_value: float  # valor máximo permitido (en la unidad indicada)
    unit: str  # ej: "%", "Wh/kg"
    hard: bool  # True = ley física (debunked) · False = techo práctico (disputed)
    law: str  # nombre de la ley / principio
    explanation: str  # explicación legible para humanos
    applies_to: frozenset = field(default_factory=frozenset)  # tecnologías; vacío = todas

# ───────────────────────── BASE DE CONOCIMIENTO ──────────────────────
# Cada límite está documentado con su fundamento científico. Los umbrales
# son CONSERVADORES a propósito para minimizar falsos positivos.

PHYSICAL_LIMITS: list[PhysicalLimit] = [
    # ── LEYES UNIVERSALES (aplican a cualquier tecnología) ──
    PhysicalLimit(
        metric_name="efficiency",
        max_value=100.0,
        unit="%",
        hard=True,
        law="1ra ley de la termodinámica (conservación de energía)",
        explanation=(
            "Una eficiencia de conversión superior al 100% es físicamente "
            "imposible: implicaría crear energía de la nada."
        ),
    ),
    # ── ENERGÍA SOLAR ──
    # Límite de Shockley–Queisser: una celda fotovoltaica de UNIÓN SIMPLE
    # bajo espectro AM1.5 no puede superar ~33.7% (máximo a ~1.34 eV).
    # Las celdas tándem/multiunión SÍ pueden superarlo, pero deben declararse
    # como tales; un claim de unión simple por encima de 33.7% es imposible.
    PhysicalLimit(
        metric_name="efficiency",
        max_value=33.7,
        unit="%",
        hard=True,
        law="Límite de Shockley–Queisser",
        explanation=(
            "Una celda solar de unión simple no puede superar ~33.7% de "
            "eficiencia bajo luz solar no concentrada. Si la tecnología es "
            "tándem o multiunión, debe declararse explícitamente."
        ),
        applies_to=frozenset({"perovskite-solar"}),
    ),
    # ── ENERGÍA EÓLICA ──
    # Límite de Betz: una turbina no puede extraer más del 59.3% (16/27) de
    # la energía cinética del viento que la atraviesa.
    PhysicalLimit(
        metric_name="efficiency",
        max_value=59.3,
        unit="%",
        hard=True,
        law="Límite de Betz",
        explanation=(
            "Ninguna turbina eólica puede extraer más del 59.3% (16/27) de la "
            "energía cinética del viento. Valores mayores violan la mecánica "
            "de fluidos del flujo libre."
        ),
        applies_to=frozenset({"wind"}),
    ),
    # ── HIDRÓGENO VERDE / ELECTRÓLISIS ──
    # Techo práctico: la eficiencia de electrólisis del agua (base HHV) rara
    # vez supera ~83% en sistemas reales. No es imposible acercarse, pero un
    # claim por encima de 83% requiere verificación (techo práctico).
    PhysicalLimit(
        metric_name="efficiency",
        max_value=83.0,
        unit="%",
        hard=False,
        law="Techo práctico de electrólisis (base HHV)",
        explanation=(
            "La eficiencia de electrólisis del agua en sistemas reales rara "
            "vez supera ~83% (base HHV). Un valor mayor debe verificarse "
            "(¿celda vs. sistema?, ¿base HHV o LHV?)."
        ),
        applies_to=frozenset({"green-hydrogen"}),
    ),
    # ── BATERÍAS (techos prácticos · solo 'disputed', nunca 'debunked') ──
    # Las densidades teóricas pueden ser muy altas; lo que marcamos es la
    # superación de niveles DEMOSTRADOS A NIVEL CELDA, que es donde ocurre
    # el greenwashing (confundir teórico con celda comercial).
    PhysicalLimit(
        metric_name="energy_density",
        max_value=160.0,
        unit="Wh/kg",
        hard=False,
        law="Techo práctico Na-ion (nivel celda)",
        explanation=(
            "Las baterías de sodio-ion demostradas rondan 120–160 Wh/kg a "
            "nivel celda. Un valor mayor debe verificarse."
        ),
        applies_to=frozenset({"sodium-ion"}),
    ),
    PhysicalLimit(
        metric_name="energy_density",
        max_value=70.0,
        unit="Wh/kg",
        hard=False,
        law="Techo práctico de baterías de flujo (nivel celda)",
        explanation=(
            "Las baterías de flujo (p. ej. vanadio) tienen densidades "
            "energéticas bajas (~15–70 Wh/kg). Un valor mayor es atípico y "
            "debe verificarse."
        ),
        applies_to=frozenset({"flow-battery"}),
    ),
    PhysicalLimit(
        metric_name="energy_density",
        max_value=500.0,
        unit="Wh/kg",
        hard=False,
        law="Techo práctico de estado sólido (nivel celda)",
        explanation=(
            "Las baterías de estado sólido demostradas a nivel celda no "
            "superan ~500 Wh/kg. Valores mayores suelen confundir densidad "
            "teórica del material con la de la celda completa."
        ),
        applies_to=frozenset({"solid-state-battery"}),
    ),
    PhysicalLimit(
        metric_name="energy_density",
        max_value=1000.0,
        unit="Wh/kg",
        hard=False,
        law="Techo práctico electroquímico (nivel celda)",
        explanation=(
            "Ninguna química recargable demostrada hoy alcanza >1000 Wh/kg a "
            "nivel celda completa. Probable confusión teórico vs. celda."
        ),
        applies_to=frozenset(),  # aplica a cualquier tecnología de batería
    ),
]

# ───────────────────────── LÓGICA DE EVALUACIÓN ──────────────────────

@dataclass
class Violation:
    """Una violación detectada de un límite."""

    metric_name: str
    value: float
    unit: str
    limit: float
    hard: bool
    law: str
    explanation: str

    def as_text(self) -> str:
        kind = "VIOLACIÓN FÍSICA" if self.hard else "Supera techo práctico"
        return (
            f"[{kind}] {self.metric_name}={self.value}{self.unit} excede "
            f"{self.limit}{self.unit} · {self.law}: {self.explanation}"
        )

def _limit_applies(limit: PhysicalLimit, technology: str) -> bool:
    """El límite aplica si es universal (applies_to vacío) o incluye la tech."""
    return not limit.applies_to or technology in limit.applies_to

def check_metric(
    technology: str, metric_name: str, value: Optional[float], unit: str = ""
) -> list[Violation]:
    """Evalúa una sola métrica contra todos los límites aplicables."""
    if value is None or metric_name == "":
        return []
    violations: list[Violation] = []
    for lim in PHYSICAL_LIMITS:
        if lim.metric_name != metric_name:
            continue
        if not _limit_applies(lim, technology):
            continue
        # Comparación de unidad: si ambas existen y difieren, no comparamos.
        if unit and lim.unit and unit.lower() != lim.unit.lower():
            continue
        if value > lim.max_value:
            violations.append(
                Violation(
                    metric_name=metric_name,
                    value=value,
                    unit=unit or lim.unit,
                    limit=lim.max_value,
                    hard=lim.hard,
                    law=lim.law,
                    explanation=lim.explanation,
                )
            )
    return violations

def evaluate_claim(technology: str, metrics: list[dict]) -> dict:
    """Evalúa un claim (con 0+ métricas) y devuelve un veredicto.

    Args:
        technology: tecnología clasificada (ej. "perovskite-solar").
        metrics: lista de dicts {metric_name, metric_value, metric_unit}.

    Returns:
        {
          "status": "claimed" | "disputed" | "debunked",
          "flag_reason": str,   # vacío si claimed
          "flag_law": str,      # ley/principio principal violado
          "violations": [ ...as_text... ],
        }
    """
    all_violations: list[Violation] = []
    for m in metrics or []:
        all_violations.extend(
            check_metric(
                technology,
                m.get("metric_name", ""),
                m.get("metric_value"),
                m.get("metric_unit", ""),
            )
        )

    if not all_violations:
        return {"status": "claimed", "flag_reason": "", "flag_law": "", "violations": []}

    # Un solo "hard" basta para debunked. Si no hay hard pero sí soft → disputed.
    hard = [v for v in all_violations if v.hard]
    chosen = hard if hard else all_violations
    status = "debunked" if hard else "disputed"
    primary = chosen[0]
    reason = " | ".join(v.as_text() for v in chosen)
    return {
        "status": status,
        "flag_reason": reason,
        "flag_law": primary.law,
        "violations": [v.as_text() for v in all_violations],
    }

# ───────────────────────── CLI DE PRUEBA ─────────────────────────────

if __name__ == "__main__":
    # Ejemplos demostrativos del motor.
    examples = [
        ("perovskite-solar", [{"metric_name": "efficiency", "metric_value": 41.0, "metric_unit": "%"}]),
        ("perovskite-solar", [{"metric_name": "efficiency", "metric_value": 25.0, "metric_unit": "%"}]),
        ("wind", [{"metric_name": "efficiency", "metric_value": 65.0, "metric_unit": "%"}]),
        ("green-hydrogen", [{"metric_name": "efficiency", "metric_value": 95.0, "metric_unit": "%"}]),
        ("solid-state-battery", [{"metric_name": "energy_density", "metric_value": 650.0, "metric_unit": "Wh/kg"}]),
        ("other", [{"metric_name": "efficiency", "metric_value": 120.0, "metric_unit": "%"}]),
    ]
    for tech, mets in examples:
        verdict = evaluate_claim(tech, mets)
        print()
        print(f"[{tech}] {mets[0]['metric_value']}{mets[0]['metric_unit']} "
              f"-> {verdict['status'].upper()}")
        if verdict["flag_reason"]:
            print(f"   {verdict['flag_reason']}")
