#!/usr/bin/env python3
"""Demo: auditoria en vivo de afirmaciones de energia renovable (para captura)."""

from energy_intel_node import annotate_claim
from report import generate_report

claims = [
    {
        "source_type": "press_release",
        "title": "SolarCo panel: 47% efficiency",
        "claim_text": "Our single-junction solar panel reaches 47% efficiency",
        "technology": "perovskite-solar"
    },
    {
        "source_type": "press_release",
        "title": "WindMax turbine: 68% efficiency",
        "claim_text": "new turbine captures 68% efficiency of wind energy",
        "technology": "wind"
    },
    {
        "source_type": "patent",
        "title": "Solid-state battery: 950 Wh/kg",
        "claim_text": "cell delivers an energy density of 950 Wh/kg",
        "technology": "solid-state-battery"
    },
    {
        "source_type": "press_release",
        "title": "GreenH2 electrolyzer: 92%",
        "claim_text": "electrolysis efficiency of 92% achieved",
        "technology": "green-hydrogen"
    },
    {
        "source_type": "paper",
        "title": "Perovskite tandem: 24.5% efficiency",
        "claim_text": "certified 24.5% efficiency tandem cell",
        "technology": "perovskite-solar"
    },
]

for c in claims:
    annotate_claim(c)

print(generate_report("Renewable-energy claims - live physics audit", claims))
