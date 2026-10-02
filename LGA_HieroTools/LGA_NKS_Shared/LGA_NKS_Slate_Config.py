"""
____________________________________________________________________

  LGA_NKS_Slate_Config v1.01 | Lega

  Fuente unica de los datos del slate que viajan por Flow: los codigos de
  los campos custom, las opciones de los selectores y el boton que dispara
  la submission note. La usan el Flow Review Panel, el push y su conector,
  y el boton Slate Frame del panel Flow | S3. No importa hiero ni Qt: el
  conector corre en el Python de PipeSync, fuera de NKS.

  Los cuatro campos existen SOLO en el sitio studio de Flow. Los crea
  bootstrap_slate_fields.py de PipeSync; detalle en docs/Docu_Slate_MXF.md.

  v1.01: Tooltip de Rev Dir en una linea corta, como el resto del panel.
  v1.00: Version inicial.
____________________________________________________________________
"""

# Campos de la Version que escribe el supervisor y lee la tool del editor.
# Son tres campos de texto y no un JSON en uno: se leen y se corrigen a mano
# en la web de Flow, y un JSON roto en un campo de texto no le avisa a nadie.
FIELD_SUBMISSION_NOTE = "sg_submission_note"
FIELD_SUBMITTING_FOR = "sg_submitting_for"
FIELD_MEDIA_COLOR = "sg_media_color"
VERSION_SUBMISSION_FIELDS = (
    FIELD_SUBMISSION_NOTE,
    FIELD_SUBMITTING_FOR,
    FIELD_MEDIA_COLOR,
)

# Campo File/Link del Shot con el frame del aPlate elegido para el slate. La
# API no crea campos custom de tipo imagen: se sube con
# sg.upload(..., field_name=FIELD_SLATE_FRAME) y se baja con download_attachment.
FIELD_SLATE_FRAME = "sg_slate_frame"

# Unico boton de estado que acepta Ctrl+Alt+Click para escribir la submission
# note. Es el label del boton, no el codigo de Flow.
SUBMISSION_BUTTON_LABEL = "Rev Dir"

# Estados de Task de la cola de entrega (pubsh -> check -> apr). Si la task ya
# esta en uno de estos, Ctrl+Alt+Click en Rev Dir ofrece guardar SOLO la nota:
# volver a Rev Dir sacaria al shot de la cola de entrega.
DELIVERY_QUEUE_CODES = ("pubsh", "check", "apr")

# Opciones del selector "Submitting For". El combo es editable: el supervisor
# puede escribir cualquier otro valor.
SUBMITTING_FOR_OPTIONS = ("WIP", "FINAL", "TEMP")

# Opciones cerradas del selector "Media Color".
MEDIA_COLOR_OPTIONS = (
    "Rec709 with show LUT",
    "Rec709 without show LUT",
)

# Contexto donde existen los campos. En client no hay submission note.
SLATE_CONTEXT_MODE = "studio"

# Textos de tooltip, aparte del widget para la futura version bilingue.
TOOLTIPS = {
    "rev_dir": "Ctrl+Alt+Click: Submission Note del slate de entrega",
    "slate_frame": (
        "Click: guardar el frame actual del viewer como imagen del slate de "
        "entrega del shot en Flow (campo Slate Frame). Solo en contexto studio."
    ),
}


def submission_values(note, submitting_for, media_color):
    """Arma el dict de campos de Version, sin espacios sobrantes."""
    return {
        FIELD_SUBMISSION_NOTE: (note or "").strip(),
        FIELD_SUBMITTING_FOR: (submitting_for or "").strip(),
        FIELD_MEDIA_COLOR: (media_color or "").strip(),
    }
