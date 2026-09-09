"""
____________________________________________________________________

  LGA_NKS_Clip_DisableCG v1.00 | Lega

  Habilita o deshabilita el clip en el track _cg_ (solo contexto client).
  Wrapper de LGA_NKS_Clip_DisableEXR con track_name=_cg_.

  Pasa explícitamente `enable_rev_fallback=False` porque el flujo de fallback
  al track de review (compRev / similares) es exclusivo del botón ON OFF
  _comp_, igual que en el wrapper de roto.

  El nombre del track sale de LGA_NKS_TaskScope y no de LGA_NKS_GetClip:
  TaskScope no importa hiero, así que el fallback literal deja de ser el
  camino normal fuera de NKS.

  v1.00: Versión inicial.
____________________________________________________________________

"""

import sys
from pathlib import Path

# Nombre del track de la task CG, desde el modulo compartido de scope.
utils_path = Path(__file__).parent.parent / "LGA_NKS_Shared"
if utils_path.exists() and str(utils_path) not in sys.path:
    sys.path.insert(0, str(utils_path))
try:
    from LGA_NKS_TaskScope import exr_track_for_task

    TRACK_cg_EXR = exr_track_for_task("cg")
except Exception:
    TRACK_cg_EXR = "_cg_"

# Importar main de DisableEXR (mismo directorio)
panel_py_path = Path(__file__).parent
if str(panel_py_path) not in sys.path:
    sys.path.insert(0, str(panel_py_path))
from LGA_NKS_Clip_DisableEXR import main as disable_main


def main():
    disable_main(track_name=TRACK_cg_EXR, enable_rev_fallback=False)


if __name__ == "__main__":
    main()
