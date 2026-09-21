"""
____________________________________________________________________

  LGA_NKS_Flow_Reviewer_Config v1.01 | Lega

  Politica compartida de reviewers visibles en Create/Modify Shot.

  v1.01: Expone la clave canonica de Lega para el assignee fijo de SUP.
  v1.00: En Client solo se ofrece Lega; Studio conserva todos los
         reviewers del estudio.
____________________________________________________________________
"""

from typing import Dict, List, Optional

try:
    from LGA_NKS_TaskScope import BOTH, STUDIO_ONLY, resolve_mode
except ImportError:  # pragma: no cover - depende de como se arme el sys.path
    from LGA_NKS_Shared.LGA_NKS_TaskScope import BOTH, STUDIO_ONLY, resolve_mode


REVIEWERS: List[Dict[str, str]] = [
    {
        "key": "lega_pugliese",
        "label": "Lega",
        "flow_name": "Lega Pugliese",
        "contexts": BOTH,
    },
    {
        "key": "sebas_romano",
        "label": "Sebas",
        "flow_name": "Sebas Romano",
        "contexts": STUDIO_ONLY,
    },
    {
        "key": "juano",
        "label": "Juano",
        "flow_name": "Juan Olivares",
        "contexts": STUDIO_ONLY,
    },
    {
        "key": "charly_villafane",
        "label": "Charly",
        "flow_name": "Charly Villafañe",
        "contexts": STUDIO_ONLY,
    },
    {
        "key": "javi_bravo",
        "label": "Javi",
        "flow_name": "Javi Bravo",
        "contexts": STUDIO_ONLY,
    },
]

REVIEWER_KEY_TO_NAME = {
    reviewer["key"]: reviewer["flow_name"] for reviewer in REVIEWERS
}
INTERNAL_VENDOR_ASSIGNEE_KEY = "lega_pugliese"


def get_available_reviewers(mode: Optional[str] = None) -> List[Dict[str, str]]:
    """Reviewers que el dialogo ofrece en el contexto indicado."""
    active = resolve_mode(mode)
    return [
        reviewer
        for reviewer in REVIEWERS
        if active in reviewer.get("contexts", BOTH)
    ]


__all__ = [
    "INTERNAL_VENDOR_ASSIGNEE_KEY",
    "REVIEWERS",
    "REVIEWER_KEY_TO_NAME",
    "get_available_reviewers",
]
