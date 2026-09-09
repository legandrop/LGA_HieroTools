# -*- coding: utf-8 -*-
"""
____________________________________________________________________

  LGA_NKS_TrackNames_Section v1.00 | Lega

  Seccion read-only del panel de Settings con los nombres de track que el
  pack espera para cada task del contexto activo.

  Es SOLO VISIBILIDAD, igual que los colores de proyecto: la convencion vive
  en el codigo (`LGA_NKS_TaskScope`) y no se edita desde la UI. Sirve para
  que un artista al que una tool "no le encuentra el clip" pueda ver, sin
  preguntarle a nadie, con que nombres se lo busca.

  Vive en su propio modulo y NO importa hiero, asi que el harness de capturas
  puede construir la seccion sin levantar NKS.

  v1.00: Version inicial.
____________________________________________________________________

"""

from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets

# Se importan atomos (Color/Metric) y no una hoja de Style a proposito: esta
# seccion son LABELS sueltos, y el modulo no tiene hoja para QLabel -DETAIL es
# para QTextEdit y PANEL es un fondo-. El linter de estilo marca esto con
# UI006; es el unico caso que la regla de "usar la hoja si existe" no cubre.
from LGA_NKS_Shared.LGA_UI_Style_HieroTools import (
    Color,
    Metric,
    apply_ui_font,
    semibold_css,
)


def _tasks_del_contexto():
    """Tasks del contexto activo con sus dos tracks y su carpeta.

    Devuelve una lista de tuplas (carpeta, track EXR, track review). Si la
    cadena de imports de contexto no esta disponible devuelve lista vacia y
    la seccion lo dice, en vez de inventar nombres.
    """
    try:
        from LGA_NKS_Shared.LGA_NKS_TaskScope import (
            active_track_tasks,
            exr_track_for_task,
            rev_track_for_task,
            task_folder_name,
        )
    except Exception:
        return []

    filas = []
    for task in active_track_tasks():
        filas.append(
            (
                task_folder_name(task),
                exr_track_for_task(task),
                rev_track_for_task(task),
            )
        )
    return filas


def _fila(carpeta, track_exr, track_rev):
    """Fila: nombre de la task y sus dos tracks (EXR y review)."""
    widget = QtWidgets.QWidget()
    layout = QtWidgets.QHBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(8)

    nombre = QtWidgets.QLabel(carpeta or "-")
    nombre.setFixedWidth(140)
    nombre.setStyleSheet("color: %s;" % Color.TEXT)

    # Los nombres de track son DATO, no decoracion: el de EXR va destacado y
    # el de review atenuado, que es el orden en que se los consulta.
    exr = QtWidgets.QLabel(track_exr or "-")
    exr.setStyleSheet("color: %s;" % Color.TEXT_STRONG)

    rev = QtWidgets.QLabel(track_rev or "-")
    rev.setStyleSheet("color: %s;" % Color.TEXT_DIM)

    layout.addWidget(nombre)
    layout.addWidget(exr)
    layout.addWidget(rev)
    layout.addStretch(1)
    return widget


def build_track_names_section(filas=None):
    """Arma la seccion completa y la devuelve como un QWidget.

    `filas` existe para el harness de capturas: si no se pasa, se resuelven
    del contexto activo.

    La fuente del pack se aplica SOLO a este contenedor. El resto de la vista
    de Settings todavia usa hexes a mano y la fuente del host; migrarla es
    otro trabajo y cambiarle el aspecto de prepo no es parte de este.
    """
    if filas is None:
        filas = _tasks_del_contexto()

    container = QtWidgets.QWidget()
    box = QtWidgets.QVBoxLayout(container)
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(4)

    titulo = QtWidgets.QLabel("Track names")
    titulo.setStyleSheet("color: %s; %s" % (Color.TEXT_STRONG, semibold_css()))
    box.addWidget(titulo)

    hint = QtWidgets.QLabel("Read-only. Defined in code, same for every project.")
    hint.setStyleSheet("color: %s;" % Color.TEXT_DIM)
    box.addWidget(hint)

    if not filas:
        vacio = QtWidgets.QLabel("Task scope unavailable.")
        vacio.setStyleSheet("color: %s;" % Color.TEXT_DIM)
        box.addWidget(vacio)
    else:
        for carpeta, track_exr, track_rev in filas:
            box.addWidget(_fila(carpeta, track_exr, track_rev))

    # La fuente va al final: medir antes de aplicarla usa la del host.
    apply_ui_font(container, size=Metric.FORM_PATH_FONT_SIZE)
    return container
