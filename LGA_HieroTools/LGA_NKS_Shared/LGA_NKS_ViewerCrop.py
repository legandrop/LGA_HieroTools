"""
____________________________________________________________________

  LGA_NKS_ViewerCrop v1.00 | Lega

  Recorta los bordes negros de una captura del viewer de Hiero.

  Review Pic y Snapshot capturan el viewer ENTERO (viewer.image()) y
  le sacan solo el negro que lo rodea, en cualquier lado: arriba y
  abajo cuando la imagen es mas ancha que el viewer, a los costados
  cuando es mas alta, o de un solo lado cuando la imagen esta corrida
  o con zoom. Antes recortaban centrado al aspect ratio de la
  secuencia, que cortaba imagen si el viewer tenia zoom o paneo, y
  dejaba negro si la imagen no estaba centrada.

  Un borde es una fila o columna ENTERA cuyos canales no pasan de
  BLACK_THRESHOLD (0-255). Se mira el canal mas alto de cada pixel,
  no la luminancia: un azul muy oscuro no se confunde con negro. Las
  filas y columnas se leen como bytes con slices de Python, asi que
  una captura de 2000x800 se recorre en milisegundos.

  Si toda la captura es negra (o casi), se devuelve sin recortar.

  Cada recorte deja su log en logs/DebugPy_LGA_NKS_ViewerCrop.log con
  el tamaño de la captura, el rectangulo resultante y el valor maximo
  de cada borde recortado, para ajustar el umbral si hiciera falta.

  v1.00: Version inicial.
____________________________________________________________________
"""

import os
import time

DEBUG = False

# Valor maximo de canal (0-255) que todavia cuenta como fondo negro del viewer.
BLACK_THRESHOLD = 6

_HIEROTOOLS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_PATH = os.path.join(_HIEROTOOLS_DIR, "logs", "DebugPy_LGA_NKS_ViewerCrop.log")

_LOG_LINES = []


def debug_print(*message):
    """Acumula para el .log y, si DEBUG, ademas escribe en la consola."""
    linea = " ".join(str(m) for m in message)
    _LOG_LINES.append(linea)
    if DEBUG:
        print(linea)


def _volcar_log():
    """Escribe el log de la corrida, pisando el anterior. Nunca rompe la tool."""
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("Fecha: {0}\n".format(time.strftime("%Y-%m-%d %H:%M:%S")))
            handle.write("\n".join(_LOG_LINES) + "\n")
    except Exception:
        pass
    del _LOG_LINES[:]


def find_content_rect(data, width, height, stride, threshold=BLACK_THRESHOLD):
    """Rectangulo (x, y, ancho, alto) sin bordes negros, en pixeles RGB888.

    `data` son los bytes de una imagen RGB888 (3 bytes por pixel, filas de
    `stride` bytes). Devuelve None si no hay ningun pixel por encima del umbral.
    Puro, sin Qt, para poder probarlo sin Hiero.
    """
    row_bytes = width * 3

    def row_is_black(y):
        start = y * stride
        return max(data[start:start + row_bytes]) <= threshold

    top = 0
    while top < height and row_is_black(top):
        top += 1
    if top == height:
        return None
    bottom = height - 1
    while bottom > top and row_is_black(bottom):
        bottom -= 1

    # Las columnas se miran solo dentro de la franja de filas con contenido.
    band_start = top * stride
    band_end = bottom * stride + row_bytes

    def column_is_black(x):
        offset = band_start + x * 3
        for channel in range(3):
            if max(data[offset + channel:band_end:stride]) > threshold:
                return False
        return True

    left = 0
    while left < width and column_is_black(left):
        left += 1
    right = width - 1
    while right > left and column_is_black(right):
        right -= 1
    return left, top, right - left + 1, bottom - top + 1


def _rgb888_bytes(qimage):
    """(bytes, ancho, alto, stride) de `qimage` convertida a RGB888."""
    from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtGui

    image = qimage.convertToFormat(QtGui.QImage.Format_RGB888)
    stride = image.bytesPerLine()
    data = bytes(image.constBits())[: stride * image.height()]
    return data, image.width(), image.height(), stride


def crop_black_borders(qimage, threshold=BLACK_THRESHOLD):
    """Devuelve `qimage` sin los bordes negros que la rodean.

    Si no hay bordes, devuelve la misma imagen. Si todo es negro, la devuelve
    sin recortar. Nunca levanta excepcion: ante un error, devuelve la original.
    """
    try:
        data, width, height, stride = _rgb888_bytes(qimage)
        debug_print("Captura:", width, "x", height, "| umbral:", threshold)
        rect = find_content_rect(data, width, height, stride, threshold)
        if rect is None:
            debug_print("Toda la captura es negra: no se recorta.")
            return qimage
        x, y, w, h = rect
        debug_print(
            "Recorte: x={0} y={1} w={2} h={3} | bordes izq={0} arr={1} der={4} aba={5}".format(
                x, y, w, h, width - x - w, height - y - h
            )
        )
        if (x, y, w, h) == (0, 0, width, height):
            debug_print("Sin bordes negros.")
            return qimage
        from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtCore

        return qimage.copy(QtCore.QRect(x, y, w, h))
    except Exception as error:
        debug_print("Error recortando bordes, se usa la captura entera:", error)
        return qimage
    finally:
        _volcar_log()
