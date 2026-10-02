import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_DIR = os.path.dirname(CURRENT_DIR)
if SHARED_DIR not in sys.path:
    sys.path.insert(0, SHARED_DIR)

import LGA_NKS_ViewerCrop as crop  # noqa: E402


def _expect(condition, message):
    if not condition:
        raise AssertionError(message)


def _canvas(width, height, content, color=(90, 120, 60), background=(0, 0, 0), padding=2):
    """Bytes RGB888 de un viewer `width`x`height` con un rectangulo `content` pintado.

    `padding` imita el relleno de fin de fila de QImage (bytesPerLine multiplo de 4).
    """
    stride = width * 3 + padding
    row = bytearray(bytes(background) * width + b"\x00" * padding)
    data = bytearray(row * height)
    x0, y0, w, h = content
    for y in range(y0, y0 + h):
        for x in range(x0, x0 + w):
            start = y * stride + x * 3
            data[start:start + 3] = bytes(color)
    return bytes(data), stride


def test_letterbox_all_sides():
    # Imagen chica en el medio del viewer: negro en los cuatro lados.
    data, stride = _canvas(60, 30, (14, 7, 30, 15))
    _expect(crop.find_content_rect(data, 60, 30, stride) == (14, 7, 30, 15), "cuatro lados")


def test_black_only_on_right():
    # Imagen con zoom que llena el viewer salvo una franja a la derecha.
    data, stride = _canvas(60, 30, (0, 0, 52, 30))
    _expect(crop.find_content_rect(data, 60, 30, stride) == (0, 0, 52, 30), "solo derecha")


def test_no_borders():
    data, stride = _canvas(20, 10, (0, 0, 20, 10))
    _expect(crop.find_content_rect(data, 20, 10, stride) == (0, 0, 20, 10), "sin bordes")


def test_all_black_returns_none():
    data, stride = _canvas(20, 10, (0, 0, 0, 0))
    _expect(crop.find_content_rect(data, 20, 10, stride) is None, "todo negro")


def test_dark_content_is_not_border():
    # Contenido muy oscuro pero con un canal por encima del umbral: no es borde.
    data, stride = _canvas(20, 10, (3, 2, 10, 5), color=(0, 0, crop.BLACK_THRESHOLD + 1))
    _expect(crop.find_content_rect(data, 20, 10, stride) == (3, 2, 10, 5), "azul oscuro no es negro")


def test_near_black_background_is_border():
    data, stride = _canvas(20, 10, (5, 0, 10, 10), background=(crop.BLACK_THRESHOLD,) * 3)
    _expect(crop.find_content_rect(data, 20, 10, stride) == (5, 0, 10, 10), "fondo casi negro")


def test_black_pixels_inside_content_do_not_split():
    # Una columna negra DENTRO de la imagen no corta nada: solo cuentan los bordes.
    data, stride = _canvas(30, 10, (5, 2, 20, 6))
    data = bytearray(data)
    for y in range(2, 8):
        start = y * stride + 12 * 3
        data[start:start + 3] = b"\x00\x00\x00"
    _expect(crop.find_content_rect(bytes(data), 30, 10, stride) == (5, 2, 20, 6), "negro interno")


def run():
    test_letterbox_all_sides()
    test_black_only_on_right()
    test_no_borders()
    test_all_black_returns_none()
    test_dark_content_is_not_border()
    test_near_black_background_is_border()
    test_black_pixels_inside_content_do_not_split()


if __name__ == "__main__":
    run()
    print("test_viewer_crop: OK")
