"""Two-stage template-based counterfactual explanation text."""

from __future__ import annotations

from typing import Any

CONSTANTS: dict[str, Any] = {
    "DEFAULT_PILLAR_KEYS": ["P1", "P2", "P3", "P4"],
}


def generate_explanation(
    county: str,
    interventions: dict[str, float],
    pillar_shifts: dict[str, float],
    uplift_final_year: float,
    final_year: int,
    pillar_label_keys: dict[str, str],
) -> str:
    """Generate a two-stage explanation from intervention and pillar shift magnitudes."""
    sorted_interventions = sorted(interventions.items(), key=lambda item: abs(float(item[1])), reverse=True)
    top_interventions = sorted_interventions[:2] if sorted_interventions else [("intervention", 0.0)]
    if len(top_interventions) == 1:
        top_interventions.append(("secondary_intervention", 0.0))

    ranked_pillars = sorted(pillar_shifts.items(), key=lambda item: abs(float(item[1])), reverse=True)
    if not ranked_pillars:
        ranked_pillars = [(key, 0.0) for key in CONSTANTS["DEFAULT_PILLAR_KEYS"]]
    primary = ranked_pillars[0]
    secondary = ranked_pillars[1] if len(ranked_pillars) > 1 else ranked_pillars[0]

    primary_label = pillar_label_keys.get(primary[0], primary[0]).replace("_", " ").title()
    secondary_label = pillar_label_keys.get(secondary[0], secondary[0]).replace("_", " ").title()

    return (
        "Stage 1 - What your intervention changed (raw -> pillar): "
        f"Adjusting {top_interventions[0][0]} by {float(top_interventions[0][1]):+.0%} and "
        f"{top_interventions[1][0]} by {float(top_interventions[1][1]):+.0%} primarily shifted "
        f"{primary_label} ({float(primary[1]):+.2f} pillar units), with a secondary change in "
        f"{secondary_label} ({float(secondary[1]):+.2f} pillar units).\n\n"
        "Stage 2 - What the model predicted (pillar -> score): "
        f"The STGNN translated these pillar shifts into an estimated {float(uplift_final_year):+.1f}-point "
        f"sustainability uplift for {county} by {int(final_year)}."
    )

