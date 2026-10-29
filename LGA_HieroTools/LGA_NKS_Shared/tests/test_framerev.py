import json
import os
import sys
import tempfile

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_DIR = os.path.dirname(CURRENT_DIR)
if SHARED_DIR not in sys.path:
    sys.path.insert(0, SHARED_DIR)

import LGA_NKS_FrameRev as framerev  # noqa: E402


def _expect(condition, message):
    if not condition:
        raise AssertionError(message)


class _FakeImage:
    """Doble de QImage: solo lo que usa open_capture()."""

    def __init__(self, ok=True):
        self.ok = ok

    def save(self, path, fmt, quality=-1):
        if not self.ok:
            return False
        with open(path, "wb") as handle:
            handle.write(b"\x89PNG fake")
        return True


def _write_registry(folder, executable, version):
    path = os.path.join(folder, "FrameRev.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"executable": executable, "version": version, "name": "FrameRev"}, handle)
    return path


def _fake_exe(folder):
    path = os.path.join(folder, "FrameRev.exe")
    with open(path, "wb") as handle:
        handle.write(b"")
    return path


def test_registry_file_per_platform():
    win = framerev.registry_file("win32", {"APPDATA": r"C:\Users\x\AppData\Roaming"}, r"C:\Users\x")
    _expect(win.replace("\\", "/") == "C:/Users/x/AppData/Roaming/LGA/FrameRev.json", win)
    mac = framerev.registry_file("darwin", {}, "/Users/x")
    _expect(mac.replace("\\", "/") == "/Users/x/Library/Application Support/LGA/FrameRev.json", mac)


def test_parse_version():
    _expect(framerev.parse_version("0.265") == (0, 265), "0.265")
    _expect(framerev.parse_version("0.267") > framerev.MIN_VERSION, "0.267 alcanza")
    _expect(framerev.parse_version("0.263") < framerev.MIN_VERSION, "0.263 no alcanza")
    _expect(framerev.parse_version("abc") is None, "texto invalido")
    _expect(framerev.parse_version(None) is None, "None")


def test_find_framerev_cases(folder):
    exe = _fake_exe(folder)
    missing = os.path.join(folder, "no_existe.json")
    found, error = framerev.find_framerev(missing)
    _expect(found is None and "not installed" in error, "sin registro avisa que no esta instalado")

    corrupt = os.path.join(folder, "corrupt.json")
    with open(corrupt, "w", encoding="utf-8") as handle:
        handle.write("{no es json")
    found, error = framerev.find_framerev(corrupt)
    _expect(found is None and "not installed" in error, "registro roto se trata como no instalado")

    not_object = os.path.join(folder, "lista.json")
    with open(not_object, "w", encoding="utf-8") as handle:
        handle.write("[]")
    found, error = framerev.find_framerev(not_object)
    _expect(found is None and "not installed" in error, "un JSON que no es objeto no rompe")

    with_bom = os.path.join(folder, "bom.json")
    with open(with_bom, "w", encoding="utf-8-sig") as handle:
        json.dump({"executable": exe, "version": "0.267"}, handle)
    found, error = framerev.find_framerev(with_bom)
    _expect(found == exe and error is None, "un registro con BOM se lee bien")

    moved = _write_registry(folder, os.path.join(folder, "movido", "FrameRev.exe"), "0.267")
    found, error = framerev.find_framerev(moved)
    _expect(found is None and "registered" in error, "ejecutable inexistente avisa")

    old = _write_registry(folder, exe, "0.263")
    found, error = framerev.find_framerev(old)
    _expect(found is None and "0.265" in error and "0.263" in error, "version vieja nombra minima e instalada")

    ok = _write_registry(folder, exe, "0.267")
    found, error = framerev.find_framerev(ok)
    _expect(found == exe and error is None, "version suficiente devuelve el ejecutable")


def test_edit_image_command(folder):
    exe = _fake_exe(folder)
    registry = _write_registry(folder, exe, "0.265")
    image = os.path.join(folder, "SHOT_010_comp_v003_1001.jpg")
    launched = []
    original = framerev._launch
    framerev._launch = lambda command: launched.append(command)
    try:
        error = framerev.edit_image(image, json_path=registry)
    finally:
        framerev._launch = original
    _expect(error is None, "sin error")
    _expect(launched == [[exe, "--edit-image", os.path.abspath(image)]], repr(launched))


def test_edit_image_without_framerev_does_not_launch(folder):
    launched = []
    original = framerev._launch
    framerev._launch = lambda command: launched.append(command)
    try:
        error = framerev.edit_image(os.path.join(folder, "a.jpg"),
                                    json_path=os.path.join(folder, "no_existe.json"))
    finally:
        framerev._launch = original
    _expect(error and not launched, "sin FrameRev no se lanza nada y se devuelve el aviso")


def test_open_capture_temp_ownership(folder):
    exe = _fake_exe(folder)
    registry = _write_registry(folder, exe, "0.267")
    temp_dir = os.path.join(folder, "tmp")
    os.makedirs(temp_dir)

    # Lanzamiento OK: el temporal queda para FrameRev, que lo borra al leerlo.
    launched = []
    original = framerev._launch
    framerev._launch = lambda command: launched.append(command)
    try:
        error = framerev.open_capture(_FakeImage(), json_path=registry, temp_dir=temp_dir)
    finally:
        framerev._launch = original
    _expect(error is None, "sin error")
    command = launched[0]
    _expect(command[:2] == [exe, "--open-capture"], repr(command))
    _expect(command[3:] == ["--capture-app-name", framerev.CAPTURE_APP_NAME], repr(command))
    _expect(os.path.isfile(command[2]), "el temporal existe para que FrameRev lo lea")
    os.remove(command[2])

    # Lanzamiento fallido: el temporal se borra aca, no queda basura.
    original = framerev._launch
    framerev._launch = lambda command: "FrameRev could not be started"
    try:
        error = framerev.open_capture(_FakeImage(), json_path=registry, temp_dir=temp_dir)
    finally:
        framerev._launch = original
    _expect(error, "devuelve el error")
    _expect(os.listdir(temp_dir) == [], "no quedan temporales tras un fallo")

    # Imagen que no se puede escribir: aviso y sin temporales.
    error = framerev.open_capture(_FakeImage(ok=False), json_path=registry, temp_dir=temp_dir)
    _expect(error and os.listdir(temp_dir) == [], "fallo al escribir no deja temporales")

    # Sin FrameRev: ni siquiera se crea el temporal.
    error = framerev.open_capture(_FakeImage(), json_path=os.path.join(folder, "no.json"),
                                  temp_dir=temp_dir)
    _expect(error and os.listdir(temp_dir) == [], "sin FrameRev no se crea temporal")


def _window(hwnd, area=1000, visible=True, owned=False, tool=False, cloaked=False):
    return {"hwnd": hwnd, "visible": visible, "owned": owned, "tool": tool,
            "cloaked": cloaked, "area": area}


def test_pick_main_window():
    _expect(framerev.pick_main_window([]) is None, "sin ventanas")
    # El toast (tool), un dialogo (owned), una oculta y la encapada no cuentan.
    windows = [
        _window(1, area=50, tool=True),
        _window(2, area=900000, owned=True),
        _window(3, area=800000, visible=False),
        _window(4, area=700000, cloaked=True),
        _window(5, area=0),
    ]
    _expect(framerev.pick_main_window(windows) is None, "ninguna es la principal")
    windows.append(_window(6, area=400000))
    windows.append(_window(7, area=600000))
    _expect(framerev.pick_main_window(windows) == 7, "la mas grande de las validas")


def test_front_step():
    own, child, other = 100, 200, 300
    step = framerev.front_step
    _expect(step(child, own, child, True, None) == "done", "FrameRev ya al frente")
    _expect(step(own, own, child, False, None) == "exited", "FrameRev se cerro")
    _expect(step(other, own, child, True, 7) == "user_left", "el usuario esta en otra app")
    _expect(step(own, own, child, True, None) == "wait", "la ventana todavia no aparecio")
    _expect(step(own, own, child, True, 7) == "raise", "Hiero al frente y ventana lista")
    _expect(step(0, own, child, True, 7) == "wait", "sin ventana de frente no se fuerza nada")


def test_win32_enumeration():
    """Solo lectura: enumera ventanas reales para validar los tipos de ctypes."""
    if not sys.platform.startswith("win"):
        return
    api = framerev._win32()
    _expect(api is not None, "ctypes disponible en Windows")
    user32 = api[2]
    foreground_pid = framerev._window_pid(api, user32.GetForegroundWindow())
    _expect(isinstance(foreground_pid, int), "pid de la ventana del frente")
    if foreground_pid:
        windows = framerev._windows_of(api, foreground_pid)
        _expect(all(set(w) == {"hwnd", "visible", "owned", "tool", "cloaked", "area"}
                    for w in windows), "formato de cada ventana")
    _expect(framerev._windows_of(api, os.getpid()) == [], "este proceso no tiene ventanas")


def run():
    with tempfile.TemporaryDirectory() as folder:
        framerev.LOG_PATH = os.path.join(folder, "logs", "DebugPy_LGA_NKS_FrameRev.log")
        test_registry_file_per_platform()
        test_parse_version()
        test_pick_main_window()
        test_front_step()
        test_win32_enumeration()
        for test in (test_find_framerev_cases, test_edit_image_command,
                     test_edit_image_without_framerev_does_not_launch,
                     test_open_capture_temp_ownership):
            case_dir = os.path.join(folder, test.__name__)
            os.makedirs(case_dir)
            test(case_dir)
        _expect(os.path.isfile(framerev.LOG_PATH), "cada corrida deja su log")


if __name__ == "__main__":
    run()
    print("test_framerev: OK")
