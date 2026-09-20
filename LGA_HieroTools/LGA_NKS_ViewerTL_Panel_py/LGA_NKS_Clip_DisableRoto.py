"""
____________________________________________________________________

  LGA_NKS_Clip_DisableRoto v1.11 | Lega

  Habilita o deshabilita el clip en el track _roto_.
  Wrapper de LGA_NKS_Clip_DisableEXR con track_name=TRACK_roto_EXR.

  Pasa explícitamente `enable_rev_fallback=False` porque el flujo de fallback al track
  de review (compRev / similares) es exclusivo del botón TL | ON/OFF _comp_.

  v1.11: Movido de Review al ViewerTL Panel con su toggle contextual de Studio.
  v1.10: Pasa `enable_rev_fallback=False` para mantener el comportamiento original (sin
         fallback al track REV). Necesario porque el default del script genérico es True.
  v1.00: Versión inicial
____________________________________________________________________

"""

import sys
from pathlib import Path

# Importar TRACK_roto_EXR del módulo central
utils_path = Path(__file__).parent.parent / "LGA_NKS_Shared"
if utils_path.exists():
    sys.path.insert(0, str(utils_path))
    from LGA_NKS_Shared.LGA_NKS_GetClip import TRACK_roto_EXR
else:
    TRACK_roto_EXR = "_roto_"

# Importar main de DisableEXR (mismo directorio)
panel_py_path = Path(__file__).parent
if str(panel_py_path) not in sys.path:
    sys.path.insert(0, str(panel_py_path))
from LGA_NKS_Clip_DisableEXR import main as disable_main


def main():
    disable_main(track_name=TRACK_roto_EXR, enable_rev_fallback=False)


if __name__ == "__main__":
    main()
