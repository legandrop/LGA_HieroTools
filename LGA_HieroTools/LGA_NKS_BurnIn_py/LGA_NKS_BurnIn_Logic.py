"""
____________________________________________________________________

  LGA_NKS_BurnIn_Logic v1.13 | Lega

  Logica viva del soft effect LGA_BurnIn. Las expresiones [python ...]
  de los Text2 internos del gizmo llaman a bi_text() y bi_ok() en cada
  evaluacion del timeline, asi que todo aca tiene que ser rapido y no
  tirar nunca una excepcion (un error devuelve texto vacio / ok=1.0 y
  se loguea una sola vez).

  La config se resuelve en LGA_NKS_BurnIn_Config y se cachea por
  proyecto; el modulo de registro invalida el cache en los eventos de
  load/save de proyecto.

  v1.13: Registro de tiempos [Perf]: cabecera de sesion, contadores del
         render en _frame_state (calculo separado en _compute_state) y
         resumen cada ~2 s que escribe el vigia del registro.
  v1.12: Fondos sin BlinkScript: el estado por frame suma "shapes"
         (paneles y franjas Band, las de los costados recortadas entre
         arriba y abajo) y shape_msg()/shape_geo() dan el mensaje en la
         fuente LGA Shapes y la caja de cada Text2 de fondo.
  v1.11: TC en rojo si no coincide con el del clip de aPlate en ese
         frame (_plate_tc_frames, items de aPlate cacheados 3 s). Sin
         timecode en la metadata o sin aPlate en el frame, no compara.
  v1.10: Performance. Un estado por frame (_frame_state): toda la
         metadata en UNA lectura del Input, textos medidos y geometria
         calculados una vez, y cada expresion del gizmo (cajas de los
         Text2, params del kernel, mensajes y colores) lee de ese estado.
         Antes cada una pedia su metadata y rehacia el layout. La config
         ya no mira el disco en cada llamada (mtime cada 2 s).
  v1.09: Mascara del viewer: el layout se calcula dentro del area visible
         (mask_inset_px, knob bi_mask_aspect) y el aspect entra en la
         firma del cache de geometria.
  v1.08: Panel con mapa. field_geo() calcula en render la geometria de
         cada campo (x, y, w, h) desde el mapa del knob bi_layout
         (LGA_NKS_BurnIn_Layout.compute): los paneles del kernel y las
         cajas de los Text2 leen lo mismo. Bandas del modo Band
         (field_geo('_band', t/b/l/r)). Campos nuevos: track (por API,
         el del clip de arriba bajo el frame), date (fecha de
         modificacion del archivo, input/mtime) y codec (compresion EXR
         con nivel DWA, o el codec de la media). Labels opcionales
         (bi_labels). Tamano de letra global (bi_size, fraccion del alto
         del formato). Cache de geometria por (efecto, frame, estado).
  v1.07: panel_geo('w') por API (texto vacio: sin stream) devuelve el
         ultimo ancho medido en render para ese campo (_last_width), asi
         el pivote de rotacion y el ancla 3x3 del panel tienen ancho.
  v1.06: _font_path() valida que el path de getFonts exista antes de
         usarlo (getFonts puede traer paths relativos rotos si el ":"
         de la unidad partio NUKE_FONT_PATH; medido) y cae al TTF del
         repo.
  v1.05: panel_geo() suma el comp 'cx' (centro horizontal del panel):
         es el pivote de la rotacion por campo, compartido entre el
         kernel (bind de ax) y el texto (apply_rotation del Blink).
  v1.04: 8 campos (agrega custom1/custom2, texto libre del usuario) y
         tamano POR CAMPO (bi_<f>_size en %): _font_px(parent, field) mide
         con el px efectivo (scale global x size del campo). PANEL_ANCHOR
         cubre los custom (center).
  v1.03: El ancho del panel se mide con las metricas AFM de Nuke
         (plugins/fonts/UtopiaRegular.afm), no con QFontMetrics: en NKS
         Qt sustituye "Utopia" por otra fuente mas ancha e inflaba el
         panel. Digitos normalizados solo en frame/tc (a '0'); el resto
         se mide exacto. Colorspace con cache TTL (un cambio manual no
         dispara evento; sin TTL nunca se refrescaba).
  v1.02: panel_geo(): geometria de los paneles medida del texto real
         (QFontMetrics, digitos normalizados a 8) con anclas por campo.
         Fix medido en NKS: hiero/project llega vacio en el stream del
         timeline; el nombre del proyecto ahora cae a la secuencia
         activa o al unico proyecto abierto.
  v1.01: Frame y TC como campos separados, campo colorspace (por API
         con cache) y registro de llamadas en el log para diagnostico.
  v1.00: Version inicial. Campos res (rojo condicional, solo EXR),
         fps (rojo condicional), frametc y clip.
____________________________________________________________________
"""

import os
import sys
import time

import LGA_NKS_BurnIn_Config as bi_config
import LGA_NKS_BurnIn_Layout as bi_layout

DEBUG = False  # Consola apagada por default; el .log se escribe siempre.

_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
_LOG_PATH = os.path.join(_LOG_DIR, "DebugPy_LGA_NKS_BurnIn.log")
_MAX_LOGGED_ERRORS = 20

_log_started = False
_logged_error_keys = set()

# Cache de config: {project_name: config_dict}. Se invalida entero cuando
# cambia el mtime del BurnIn.json o cuando el registro avisa un evento de
# proyecto (load/save/close).
_config_cache = {}
_config_file_mtime = None


# ── Debug con archivo (convencion del pack) ───────────────────────────────────


def _log(message):
    """Escribe SIEMPRE al .log (pisado por sesion); consola solo si DEBUG."""
    global _log_started
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        mode = "a" if _log_started else "w"
        with open(_LOG_PATH, mode, newline="\n", encoding="utf-8") as f:
            f.write("[{}] {}\n".format(time.strftime("%H:%M:%S"), message))
        _log_started = True
    except Exception:
        pass
    if DEBUG:
        print("[LGA_BurnIn] {}".format(message))


def _log_error_once(key, message):
    """Loguea un error una sola vez por key para no inundar el log por frame."""
    if key in _logged_error_keys or len(_logged_error_keys) >= _MAX_LOGGED_ERRORS:
        return
    _logged_error_keys.add(key)
    _log("ERROR {}: {}".format(key, message))


# ── Registro de tiempos ([Perf]) ──────────────────────────────────────────────
#
# Existe para diagnosticar maquinas donde el efecto anda lento (un usuario con
# una RTX 3080 tenia todo trabado). Siempre prendido y barato: el render solo
# suma contadores en _frame_state y el resumen lo escribe el vigia del
# registro (LGA_NKS_BurnIn.py) cada ~2 s, nunca una linea por frame. El vigia
# tambien anota cuando el hilo principal estuvo trabado y cual fue la ultima
# actividad del efecto (perf_mark). Formato de las lineas: Docu_LGA_BurnIn.md.

_perf = {
    "calls": 0,
    "states": 0,
    "state_ms": 0.0,
    "state_max": 0.0,
    "since": time.time(),
    "last": "",
}


def perf_log(message):
    _log("[Perf] " + message)


def perf_mark(what):
    """Anota la ultima actividad del efecto; se nombra si el hilo se traba."""
    _perf["last"] = "{} ({})".format(what, time.strftime("%H:%M:%S"))


def perf_last():
    return _perf["last"] or "ninguna"


def perf_flush():
    """Resumen del render desde el ultimo resumen (solo si hubo render)."""
    if not _perf["calls"]:
        _perf["since"] = time.time()
        return
    dt = time.time() - _perf["since"]
    perf_log(
        "render {:.1f} s: {} expresiones, {} estados calculados "
        "({:.1f} ms en total, el peor {:.1f} ms)".format(
            dt, _perf["calls"], _perf["states"], _perf["state_ms"], _perf["state_max"]
        )
    )
    _perf.update(calls=0, states=0, state_ms=0.0, state_max=0.0, since=time.time())


def perf_header():
    """Primera linea de la sesion: con que se corre (para comparar maquinas)."""
    try:
        import nuke

        host = nuke.NUKE_VERSION_STRING
    except Exception:
        host = "?"
    version = "?"
    try:
        vpath = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "VERSION")
        with open(vpath, encoding="utf-8") as f:
            version = f.read().strip()
    except Exception:
        pass
    import platform

    perf_log(
        "sesion: NKS {}, HieroTools {}, {} {}, {} nucleos, pid {}".format(
            host, version, platform.system(), platform.release(), os.cpu_count(), os.getpid()
        )
    )


# ── Config cacheada ───────────────────────────────────────────────────────────


def invalidate_cache():
    """Vacia los caches. Lo llama el registro en eventos de proyecto."""
    _config_cache.clear()
    _colorspace_cache.clear()
    _measure_cache.clear()
    _geo_cache.clear()
    _track_cache.clear()
    _logged_error_keys.clear()
    _log("Cache de config invalidado")


def _file_mtime():
    try:
        return os.path.getmtime(bi_config.get_settings_path())
    except OSError:
        return None


# El mtime del BurnIn.json se mira a lo sumo cada _MTIME_EVERY segundos: es una
# llamada al disco y get_config se usaba en cada evaluacion del color de res/fps.
_MTIME_EVERY = 2.0
_mtime_checked_at = [0.0]


def _read_project_tag_json(project_name):
    """JSON del tag LGA_BurnIn_Settings del proyecto, via el modulo de tag."""
    try:
        import LGA_NKS_BurnIn_ProjectTag as bi_tag

        return bi_tag.read_config_json(bi_tag.find_project(project_name))
    except ImportError:
        return None
    except Exception as exc:
        _log_error_once("tag:" + str(project_name), str(exc))
        return None


def get_config(project_name):
    """Config efectiva para un proyecto, cacheada."""
    global _config_file_mtime
    now = time.time()
    if now - _mtime_checked_at[0] >= _MTIME_EVERY:
        _mtime_checked_at[0] = now
        mtime = _file_mtime()
        if mtime != _config_file_mtime:
            _config_file_mtime = mtime
            _config_cache.clear()

    key = project_name or ""
    cfg = _config_cache.get(key)
    if cfg is not None:
        return cfg

    user_data, error = bi_config.load_user_file()
    if error:
        _log_error_once("config_file", error)
    tag_json = _read_project_tag_json(project_name) if project_name else None
    cfg, warnings = bi_config.resolve(user_data, project_name, tag_json)
    for warning in warnings:
        _log_error_once("config_warn:" + warning[:40], warning)
    _config_cache[key] = cfg
    _log(
        "Config resuelta para '{}' (tag del proyecto: {})".format(
            key, "si" if tag_json else "no"
        )
    )
    return cfg


# ── Acceso a metadata del stream ──────────────────────────────────────────────


def _meta(parent, key, frame=None):
    """Una key de metadata del input del gizmo (el stream visible)."""
    try:
        input_node = parent.node("Input1")
        if input_node is None:
            return None
        if frame is None:
            return input_node.metadata(key)
        return input_node.metadata(key, frame)
    except Exception as exc:
        _log_error_once("meta:" + key, str(exc))
        return None


def _project_name(parent, meta=None):
    """Nombre del proyecto del clip visible.

    MEDIDO en NKS 16: la key hiero/project llega VACIA en el stream del
    gizmo en el timeline (aunque el preset del BurnIn nativo la liste),
    asi que hay cadena de fallbacks: metadata -> secuencia activa ->
    unico proyecto de usuario abierto.
    """
    name = meta.get("hiero/project") if meta is not None else _meta(parent, "hiero/project")
    if name:
        return name
    try:
        import hiero.ui

        seq = hiero.ui.activeSequence()
        if seq is not None:
            return seq.project().name()
    except Exception:
        pass
    try:
        import hiero.core

        projs = hiero.core.projects()
        if len(projs) == 1:
            return projs[0].name()
    except Exception:
        pass
    return None


# El colorspace no viaja en la metadata del stream del timeline, asi que se
# resuelve por API: se ubica el clip por nombre y se le pregunta su transform.
# Cache con TTL: NO se puede cachear indefinido porque cambiar el colorspace
# de un clip a mano no dispara ningun evento de proyecto (medido: con cache
# permanente el burn-in nunca se actualizaba). Se guarda (valor, timestamp)
# por clip.
_colorspace_cache = {}
_COLORSPACE_TTL = 3.0


def _clip_colorspace(parent, clip_name):
    if not clip_name:
        return ""
    now = time.time()
    cached = _colorspace_cache.get(clip_name)
    if cached is not None and (now - cached[1]) < _COLORSPACE_TTL:
        return cached[0]
    proj_name = _project_name(parent)
    value = ""
    try:
        import hiero.core

        for proj in hiero.core.projects():
            if proj_name and proj.name() != proj_name:
                continue
            for clip in hiero.core.findItemsInProject(proj, "Clips"):
                if clip.name() == clip_name:
                    value = str(clip.sourceMediaColourTransform() or "")
                    break
            break
    except Exception as exc:
        _log_error_once("cspace:" + str(clip_name), str(exc))
    _colorspace_cache[clip_name] = (value, now)
    return value


def _target_res(parent, cfg):
    """Resolucion objetivo: explicita de config, o el formato del timeline."""
    explicit = bi_config.parse_res(cfg.get("res_target"))
    if explicit:
        return explicit
    try:
        return (int(parent.width()), int(parent.height()))
    except Exception as exc:
        _log_error_once("target_res", str(exc))
        return None


def _labeled(parent, label, value):
    """'Label: valor' con los labels prendidos (bi_labels), o el valor solo."""
    if not value:
        return ""
    try:
        on = bool(parent["bi_labels"].value())
    except Exception:
        on = True
    return "{}: {}".format(label, value) if on else str(value)


def _clip_codec(parent, frame=None, meta=None):
    """Compresion EXR (con el nivel si es DWA) o el codec de la media.

    MEDIDO en NKS 17: un EXR trae exr/compressionName ('DWAA') y
    exr/dwaCompressionLevel ('60'). Para el resto se busca la primera key
    de metadata que nombre un codec (cada reader usa su prefijo).
    """
    if meta is None:
        meta = _frame_meta(parent, frame)
    name = meta.get("exr/compressionName")
    if name:
        name = str(name)
        if name.upper().startswith("DWA"):
            level = meta.get("exr/dwaCompressionLevel")
            if level:
                try:
                    level = "%g" % float(level)
                except (TypeError, ValueError):
                    pass
                return "{} {}".format(name, level)
        return name
    for key in sorted(meta):
        low = key.lower()
        if low.endswith(("codec_name", "/codec", "compressor")):
            value = str(meta[key] or "").strip()
            if value:
                return value
    return ""


# El track no viaja en la metadata del stream (hiero/track llega vacio; medido
# en NKS 17), asi que se busca por API: el track item de la secuencia activa
# cuya fuente es el clip visible y que cubre el frame. Cache con TTL corto,
# como el colorspace: clip -> [(nombre del track, in, out)], de arriba abajo.
_track_cache = {}
_TRACK_TTL = 3.0


def _clip_track(parent, frame=None, clip_name=None):
    if not clip_name:
        return ""
    now = time.time()
    cached = _track_cache.get(clip_name)
    if cached is None or (now - cached[1]) >= _TRACK_TTL:
        spans = []
        try:
            import hiero.ui

            seq = hiero.ui.activeSequence()
            tracks = list(seq.videoTracks()) if seq is not None else []
            for track in reversed(tracks):
                for item in track.items():
                    try:
                        if item.source().name() == clip_name:
                            spans.append(
                                (track.name(), item.timelineIn(), item.timelineOut())
                            )
                    except Exception:
                        continue
        except Exception as exc:
            _log_error_once("track:" + str(clip_name), str(exc))
        cached = (spans, now)
        _track_cache[clip_name] = cached
    spans = cached[0]
    if not spans:
        return ""
    if frame is not None:
        for name, tin, tout in spans:
            if tin <= frame <= tout:
                return name
    return spans[0][0]


# TC contra aPlate: el TC del clip visible se pinta rojo si no coincide con el
# del clip del track aPlate en el mismo frame (un comp renderizado con otro
# rango que el plate). Los items de aPlate se cachean con TTL corto, como el
# track: (in, out, frame de media del in, velocidad).
REF_TRACK = "aplate"
_plate_cache = {"t": 0.0, "spans": None}


def _tc_to_frames(tc, fps):
    """'HH:MM:SS:FF' (o con ';') a frames. None si no se puede."""
    try:
        parts = [int(p) for p in str(tc).replace(";", ":").split(":")]
        if len(parts) != 4 or not fps:
            return None
        base = int(round(float(fps)))
        h, m, s, f = parts
        return ((h * 60 + m) * 60 + s) * base + f
    except (TypeError, ValueError):
        return None


def _plate_spans():
    now = time.time()
    if _plate_cache["spans"] is not None and (now - _plate_cache["t"]) < _TRACK_TTL:
        return _plate_cache["spans"]
    spans = []
    try:
        import hiero.ui

        seq = hiero.ui.activeSequence()
        for track in (seq.videoTracks() if seq is not None else []):
            if track.name().lower() != REF_TRACK:
                continue
            for item in track.items():
                try:
                    src = item.source()
                    start = int(src.timecodeStart()) + int(item.sourceIn())
                    spans.append((item.timelineIn(), item.timelineOut(), start,
                                  float(item.playbackSpeed() or 1.0)))
                except Exception:
                    continue
    except Exception as exc:
        _log_error_once("plate_spans", str(exc))
    _plate_cache["spans"] = spans
    _plate_cache["t"] = now
    return spans


def _plate_tc_frames(frame):
    """Frame de TC del clip de aPlate en el frame de la secuencia, o None."""
    if frame is None:
        return None
    for tin, tout, start, speed in _plate_spans():
        if tin <= frame <= tout:
            return start + int(round((frame - tin) * speed))
    return None


# ── Textos de los campos ──────────────────────────────────────────────────────


def _text_from(field, parent, frame, meta):
    """Texto de un campo. meta: dict de metadata del frame (una sola lectura
    por frame, ver _frame_meta) o None para leer key por key."""

    def m(key):
        if meta is not None:
            return meta.get(key)
        return _meta(parent, key, frame)

    if field == "clip":
        return str(m("hiero/clip") or "")
    if field == "res":
        try:
            w, h = m("input/width"), m("input/height")
            if w is None or h is None:
                return ""
            return "{}x{}".format(int(float(w)), int(float(h)))
        except (TypeError, ValueError):
            return ""
    if field == "fps":
        try:
            v = m("input/frame_rate")
            return "{} fps".format("%g" % float(v)) if v is not None else ""
        except (TypeError, ValueError):
            return ""
    if field == "frame":
        return _labeled(parent, "Frame", m("input/frame"))
    if field == "tc":
        return _labeled(parent, "TC", m("input/timecode"))
    if field == "cspace":
        return _clip_colorspace(parent, m("hiero/clip"))
    if field == "track":
        return _labeled(parent, "Track", _clip_track(parent, frame, m("hiero/clip")))
    if field == "date":
        return str(m("input/mtime") or "").split(" ")[0]
    if field == "codec":
        return _clip_codec(parent, frame, meta)
    if field in ("custom1", "custom2"):
        # Texto libre que escribe el usuario en el knob del campo.
        try:
            return str(parent["bi_%s_text" % field].value() or "")
        except Exception:
            return ""
    if field == "frametc":
        # Compatibilidad con instancias viejas del gizmo (campo unificado).
        return "Frame: {}        TC: {}".format(m("input/frame") or "", m("input/timecode") or "")
    return ""


def _ok_from(field, parent, meta, frame=None):
    """1.0 si res/fps coinciden con el objetivo del proyecto (o el TC con el
    de aPlate), 0.0 si no."""
    if field == "tc":
        mine = _tc_to_frames(meta.get("input/timecode"), meta.get("input/frame_rate"))
        ref = _plate_tc_frames(frame)
        if mine is None or ref is None:
            return 1.0
        return 0.0 if mine != ref else 1.0
    cfg = get_config(_project_name(parent, meta))
    if field == "res":
        filename = str(meta.get("input/filename") or "")
        ext = os.path.splitext(filename)[1].lstrip(".").lower()
        exts = [str(e).lstrip(".").lower() for e in cfg.get("compare_res_exts", [])]
        if ext not in exts:
            return 1.0
        try:
            clip = (int(float(meta["input/width"])), int(float(meta["input/height"])))
        except (KeyError, TypeError, ValueError):
            return 1.0
        target = _target_res(parent, cfg)
        return 0.0 if target is not None and clip != target else 1.0
    if field == "fps":
        try:
            clip = float(meta["input/frame_rate"])
        except (KeyError, TypeError, ValueError):
            return 1.0
        target = bi_config.parse_fps(cfg.get("fps_target"))
        if target is None:
            try:
                v = meta.get("hiero/sequence/frame_rate")
                target = float(v) if v is not None else None
            except (TypeError, ValueError):
                target = None
        if target is not None and abs(clip - target) >= 0.001:
            return 0.0
    return 1.0


# ── API para las expresiones del gizmo ────────────────────────────────────────
#
# PERFORMANCE (medido en NKS 17, 2026-11-14): las ~150 expresiones [python] del
# gizmo se evaluan en el HILO PRINCIPAL, varias veces por frame, y una
# referencia TCL a un knob con [python] vuelve a correr el python (no hay
# cache de Nuke en el medio). Por eso TODO sale de _frame_state(): un estado
# por (efecto, frame, knobs) calculado una vez, y cada llamada siguiente es
# una busqueda en un dict (~10 us). La version anterior pedia metadata del
# input en cada llamada solo para armar la clave del cache (~100-250 us x
# 150 llamadas por frame).


def bi_text(field, parent, frame=None):
    """Texto de un campo. La llama la expresion del message de cada Text2."""
    try:
        st = _frame_state(parent, frame)
        if st is not None and field in st["texts"]:
            return st["texts"][field]
        return _text_from(field, parent, frame, None)
    except Exception as exc:
        _log_error_once("text:" + str(field), str(exc))
        return ""


def bi_ok(field, parent, frame=None):
    """1.0 si el campo esta OK, 0.0 si hay mismatch (pinta rojo).

    La llaman las expresiones de color de Text_Res / Text_Fps. El parametro
    frame hace que la expresion dependa del frame (sin el, Nuke la evalua una
    sola vez). Ante cualquier duda devuelve 1.0: un burn-in roto no grita rojo.
    """
    try:
        st = _frame_state(parent, frame)
        if st is None:
            return 1.0
        oks = st["oks"]
        if field not in oks:
            oks[field] = _ok_from(field, parent, st["meta"], frame)
        return oks[field]
    except Exception as exc:
        _log_error_once("ok:" + str(field), str(exc))
        return 1.0


# ── Medicion del texto ────────────────────────────────────────────────────────
#
# El panel de cada campo ABRAZA a su texto. La fuente del burn-in es Inter (la
# del pack). Para que el ancho medido coincida con lo que Nuke RENDERIZA se mide
# con QFontMetrics cargando EL MISMO archivo TTF que Nuke usa: se le pregunta a
# nuke.getFonts() el path de (family, style) y se carga ESE en Qt. El peso
# (Regular/SemiBold/Bold) cambia el TTF y por lo tanto las metricas. Para
# frame/tc los digitos se normalizan a '0' (ancho estable por frame). Todo
# cacheado. VERIFICADO en NKS (sonda 29-08): render Inter + paneles abrazan.

_measure_cache = {}
_qt_family_cache = {}  # (family, style) -> familia que informa Qt (carga 1 vez)

# El TTF del repo, fallback cuando no hay `nuke` (banco) o la fuente no esta en
# getFonts. LGA_NKS_Shared/fonts/ tiene los tres pesos de Inter.
_FONT_DIR_REPO = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "LGA_NKS_Shared", "fonts")
)
_INTER_REPO_TTF = {
    "Regular": "Inter-400.ttf",
    "SemiBold": "Inter-600.ttf",
    "Bold": "Inter-700.ttf",
}
_WEIGHT_BY_INDEX = ["Regular", "SemiBold", "Bold"]
_DEFAULT_STYLE = "SemiBold"


def _weight_style(parent):
    """Estilo de Inter del knob bi_weight (Enumeration: value() da el LABEL,
    que ES el estilo: Regular/SemiBold/Bold). Default SemiBold."""
    try:
        style = str(parent["bi_weight"].value())
        if style in _WEIGHT_BY_INDEX:
            return style
    except Exception:
        pass
    return _DEFAULT_STYLE


def _font_path(family, style):
    """Path del TTF que Nuke usa para (family, style); si no, el TTF del repo.

    Usa `nuke` SOLO si ya esta importado (en NKS): un `import nuke` en un
    python suelto dispara el chequeo de licencia y cuelga el banco.
    """
    nuke = sys.modules.get("nuke")
    if nuke is not None:
        try:
            for f in nuke.getFonts():
                if len(f) >= 3 and str(f[0]) == family and str(f[1]) == style:
                    p = str(f[2])
                    # getFonts puede traer un path RELATIVO roto (el ":" de la
                    # unidad parte NUKE_FONT_PATH; medido): usarlo solo si
                    # existe de verdad, si no caer al TTF del repo.
                    if os.path.isfile(p):
                        return p
                    break
        except Exception:
            pass
    fname = _INTER_REPO_TTF.get(style)
    if fname:
        p = os.path.join(_FONT_DIR_REPO, fname)
        if os.path.exists(p):
            return p
    return None


def _qt_family(family, style):
    """Familia que Qt asigna al TTF de (family, style). Cacheada. '' si falla."""
    key = (family, style)
    if key in _qt_family_cache:
        return _qt_family_cache[key]
    fam = ""
    path = _font_path(family, style)
    if path:
        try:
            from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtGui

            fid = QtGui.QFontDatabase.addApplicationFont(path)
            if fid != -1:
                fams = list(QtGui.QFontDatabase.applicationFontFamilies(fid))
                fam = fams[0] if fams else ""
        except Exception as exc:
            _log_error_once("qtfont:" + family + style, str(exc))
    _qt_family_cache[key] = fam
    return fam


# Solo frame y tc cambian de contenido por frame: para que su panel no
# "respire" se mide con los digitos normalizados a '0'. El resto de los
# campos se miden exactos: no cambian por frame.
_DIGIT_FIELDS = ("frame", "tc")


def _digit_template(text):
    """Normaliza digitos a '0' para medir un ancho estable en frame/tc."""
    return "".join("0" if ch.isdigit() else ch for ch in str(text))


def _size_fraction(parent):
    """Fraccion del alto del formato que mide la letra (bi_size S/M/L)."""
    try:
        idx = int(parent["bi_size"].getValue())
    except Exception:
        idx = 1
    idx = max(0, min(len(bi_layout.SIZE_FRACTIONS) - 1, idx))
    return bi_layout.SIZE_FRACTIONS[idx][1]


def _font_px(parent, field=None, fmt_h=None):
    """Tamano en px del texto de Text2: fraccion de bi_size x alto del
    formato. Debe coincidir con el global_font_scale del Text2 (SIZE_EXPR del
    generador del gizmo)."""
    if fmt_h is None:
        try:
            fmt_h = float(parent.height())
        except Exception:
            fmt_h = 2160.0
    return max(8, int(round(_size_fraction(parent) * float(fmt_h))))


def _measure_text(text, px, style):
    """Ancho en px del texto en Inter <style> a <px>, con QFontMetrics del TTF real."""
    key = (text, px, style)
    cached = _measure_cache.get(key)
    if cached is not None:
        return cached
    width = None
    fam = _qt_family("Inter", style)
    try:
        from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtGui

        ft = QtGui.QFont()
        if fam:
            ft.setFamily(fam)
        ft.setPixelSize(max(1, int(round(px))))
        width = float(QtGui.QFontMetricsF(ft).horizontalAdvance(text))
    except Exception as exc:
        _log_error_once("measure", str(exc))
    if not width:
        # Sin Qt/fuente: estimacion gruesa (0.5 em promedio por caracter).
        width = px * 0.5 * len(text)
    if len(_measure_cache) > 4000:
        _measure_cache.clear()
    _measure_cache[key] = width
    return width


# ── Estado por frame: textos + geometria desde el mapa ────────────────────────
#
# Lo leen TODAS las expresiones del gizmo (cajas y mensajes de los Text2, los
# paneles y las franjas) para los once campos. Se calcula una vez
# por (efecto, frame, formato, knobs que lo afectan) y las llamadas siguientes
# son un dict lookup. Los textos de frame/tc se miden con los digitos
# normalizados, asi que el layout no "respira" de un frame a otro.

_geo_cache = {}
_GEO_CACHE_MAX = 300

# Knobs que cambian textos o geometria (el radio entra en el mensaje de los
# fondos). Colores y opacidades llegan al render por expresiones TCL directas.
_SIG_KNOBS = ("bi_weight", "bi_size", "bi_text_pad", "bi_labels", "bi_bg_mode",
              "bi_custom1_text", "bi_custom2_text", "bi_mask_aspect",
              "bi_bg_radius")



def layout_text(node):
    """JSON crudo del knob bi_layout. OJO: value() de un String_Knob evalua
    los corchetes como TCL y con un JSON devuelve 'missing close-bracket'
    (medido): siempre getText()."""
    try:
        return str(node["bi_layout"].getText() or "")
    except Exception:
        return ""


def _knob_sig(parent):
    sig = []
    for name in _SIG_KNOBS:
        try:
            k = parent[name]
            sig.append(k.getText() if name.endswith("_text") else k.value())
        except Exception:
            sig.append(None)
    return tuple(sig)


def _frame_meta(parent, frame):
    """Toda la metadata del input en UNA lectura (dict). {} sin stream."""
    try:
        inp = parent.node("Input1")
        if inp is None:
            return {}
        if frame is None:
            return dict(inp.metadata() or {})
        return dict(inp.metadata(time=frame) or {})
    except Exception as exc:
        _log_error_once("meta_dict", str(exc))
        return {}


def _frame_state(parent, frame):
    """Estado del efecto en un frame: textos, rects, bandas, crops, oks.

    Sin stream (el Input no tiene metadata: un setValue, el onCreate, el
    panel) no se cachea: el render despues lo calcula con los textos reales.
    """
    try:
        fmt_w, fmt_h = float(parent.width()), float(parent.height())
        name = parent.fullName()
    except Exception:
        return None
    _perf["calls"] += 1
    text = layout_text(parent)
    sig = _knob_sig(parent)
    key = (name, frame, fmt_w, fmt_h, text, sig)
    hit = _geo_cache.get(key)
    if hit is not None:
        return hit

    t0 = time.perf_counter()
    try:
        return _compute_state(parent, frame, fmt_w, fmt_h, text, key)
    finally:
        ms = (time.perf_counter() - t0) * 1000.0
        _perf["states"] += 1
        _perf["state_ms"] += ms
        if ms > _perf["state_max"]:
            _perf["state_max"] = ms


def _compute_state(parent, frame, fmt_w, fmt_h, text, key):
    meta = _frame_meta(parent, frame)
    arr = bi_layout.active(bi_layout.parse(text))
    style = _weight_style(parent)
    fs = _font_px(parent, None, fmt_h)
    try:
        pad = float(parent["bi_text_pad"].value())
    except Exception:
        pad = 28.0
    try:
        mode = int(parent["bi_bg_mode"].getValue())
    except Exception:
        mode = 0
    texts, widths = {}, {}
    for f in bi_layout.visible_fields(arr):
        t = _text_from(f, parent, frame, meta)
        texts[f] = t
        if f in _DIGIT_FIELDS:
            t = _digit_template(t)
        if t:
            widths[f] = _measure_text(t, fs, style) + 2.0 * pad
    rects, bands = bi_layout.compute(
        arr, widths, fmt_w, fmt_h, fs, pad, mask_inset_px(parent, fmt_w, fmt_h)
    )
    bands = bands if mode == 1 else {"t": 0.0, "b": 0.0, "l": 0.0, "r": 0.0}
    state = {
        "texts": texts,
        "rects": rects,
        "bands": bands,
        "shapes": _shapes(rects, bands, fmt_w, fmt_h, parent),
        "line_h": bi_layout.line_height(fs, pad),
        "meta": meta,
        "oks": {},
    }
    if "input/width" in meta:
        if len(_geo_cache) > _GEO_CACHE_MAX:
            _geo_cache.clear()
        _geo_cache[key] = state
    return state


_RECT_INDEX = {"x": 0, "y": 1, "w": 2, "h": 3}


def field_geo(field, comp, parent, frame=None):
    """Geometria en px desde el mapa.

    - Un campo, caja del Text2: 'x', 'y', 'w', 'h' del panel SIN ROTAR, o
      'y2' (= y + h). Oculto o sin texto: 0.
    - '_band': grosor de la franja del modo Band en el borde comp ('t', 'b',
      'l', 'r'); 0 si el modo no es Band.
    """
    try:
        st = _frame_state(parent, frame)
        if st is None:
            return 0.0
        if field == "_band":
            return float(st["bands"].get(comp, 0.0))
        rect = st["rects"].get(field)
        if rect is None:
            return 0.0
        if comp == "y2":
            return float(rect[1] + rect[3])
        idx = _RECT_INDEX.get(comp)
        return float(rect[idx]) if idx is not None else 0.0
    except Exception as exc:
        _log_error_once("geo:" + str(field) + comp, str(exc))
        return 0.0


# ── Fondos con glifos (fuente LGA Shapes) ─────────────────────────────────────
#
# Cada fondo (panel de un campo o franja del modo Band) es UN Text2 que
# escribe con la fuente LGA Shapes del pack: tapa izquierda redondeada +
# bloques de relleno + tapa derecha. El glifo mide 1000 unidades de alto y el
# Text2 dibuja a 100 px por unidad de global_font_scale, asi que con
# scale = h / 100 el fondo mide h px de alto. Un Text2 compone todos sus
# glifos como una sola forma (superponer no suma opacidad) y los glifos se
# solapan para que no haya costuras. Reemplaza al BlinkScript (v1.12): no
# depende de la GPU. Mecanismo medido en Docu_SoftEffects_Aprendizajes.md.

_CAP_L = 0xE000   # + radio en % del alto (0..50)
_CAP_R = 0xE100
_BLOCKS = ((1000, 0xE200), (100, 0xE201), (10, 0xE202), (1, 0xE203))
_START_OFFSET = 0x10  # U+E210..E213: mismos bloques sin solape (primer bloque)
BAND_KEYS = ("band_t", "band_b", "band_l", "band_r")
_BLEED = 6.0
_GLYPH_DY = 2.0


def shape_message(w, h, radius):
    """Texto en LGA Shapes que dibuja un rectangulo redondeado de w x h px con
    esquinas de radio `radius` px. '' si no hay rectangulo."""
    if w <= 0.5 or h <= 0.5:
        return ""
    r = max(0.0, min(float(radius), w * 0.5, h * 0.5))
    pct = int(round(r * 100.0 / h))
    pct = max(0, min(50, pct))
    # Un radio menor que el solape de los glifos (3 % del alto, 1,5 px a 50 px)
    # se ve recto: va como rectangulo sin tapas.
    if pct < 3:
        pct = 0
    total_u = int(round(w * 1000.0 / h))
    cap_u = int(round(10.0 * pct))
    inner = max(0, total_u - 2 * cap_u)
    blocks = []
    for size, code in _BLOCKS:
        n, inner = divmod(inner, size)
        blocks.extend([code] * n)
    if pct == 0:
        # Sin tapa izquierda: el primer bloque no se solapa hacia afuera.
        if blocks:
            blocks[0] += _START_OFFSET
        return "".join(chr(c) for c in blocks)
    return chr(_CAP_L + pct) + "".join(chr(c) for c in blocks) + chr(_CAP_R + pct)


def _shapes(rects, bands, fmt_w, fmt_h, parent):
    """key -> (x, y, w, h, radio) de cada fondo a dibujar.

    Paneles: el rect del campo (sin rotar; el giro lo pone el blob del Text2
    con el mismo pivote que el texto). Franjas: arriba y abajo de lado a
    lado; las de los costados SOLO entre esas dos, para que las esquinas no
    se pinten dos veces (dos Text2 superpuestos si suman opacidad)."""
    try:
        radius = float(parent["bi_bg_radius"].value())
    except Exception:
        radius = 0.0
    out = {}
    for f, rect in rects.items():
        out[f] = (float(rect[0]), float(rect[1]), float(rect[2]), float(rect[3]), radius)
    t, b = float(bands.get("t", 0.0)), float(bands.get("b", 0.0))
    l, r = float(bands.get("l", 0.0)), float(bands.get("r", 0.0))
    mid_h = max(0.0, fmt_h - t - b)
    # Las franjas pasan _BLEED px por afuera del cuadro por los bordes de la
    # imagen: medido en NKS 17, el Text2 dejaba ~1,5 px sin cubrir justo en
    # el borde derecho y en el de abajo. Lo de afuera no se ve.
    m = _BLEED
    if t > 0:
        out["band_t"] = (-m, fmt_h - t, fmt_w + 2 * m, t + m, 0.0)
    if b > 0:
        out["band_b"] = (-m, -m, fmt_w + 2 * m, b + m, 0.0)
    if l > 0 and mid_h > 0:
        out["band_l"] = (-m, b, l + m, mid_h, 0.0)
    if r > 0 and mid_h > 0:
        out["band_r"] = (fmt_w - r, b, r + m, mid_h, 0.0)
    return out


def shape_msg(key, parent, frame=None, rev=None):
    """Mensaje del Text2 de fondo `key` (campo o band_t/b/l/r). `rev` no se
    usa: pasar [value parent.bi_rev] hace que Nuke re-evalue el mensaje
    cuando nudge() lo incrementa."""
    try:
        st = _frame_state(parent, frame)
        if st is None:
            return ""
        shape = st["shapes"].get(key)
        if shape is None:
            return ""
        return shape_message(shape[2], shape[3], shape[4])
    except Exception as exc:
        _log_error_once("shape_msg:" + str(key), str(exc))
        return ""


def shape_geo(key, comp, parent, frame=None):
    """Caja del Text2 de fondo: 'x', 'y', 'y2' en px y 'scale' (alto / 100,
    para global_font_scale). Sin fondo: 0 (scale 0.01)."""
    try:
        st = _frame_state(parent, frame)
        shape = st["shapes"].get(key) if st is not None else None
        if shape is None:
            return 0.01 if comp == "scale" else 0.0
        x, y, w, h = shape[0], shape[1], shape[2], shape[3]
        if comp == "x":
            return x
        # Text2 apoya el glifo _GLYPH_DY px por encima del borde de abajo de
        # la caja (medido en NKS 17: igual con 50 y con 200 px de alto), asi
        # que la caja baja eso.
        if comp == "y":
            return y - _GLYPH_DY
        if comp == "y2":
            return y + h - _GLYPH_DY
        if comp == "scale":
            return max(0.01, h / 100.0)
        return 0.0
    except Exception as exc:
        _log_error_once("shape_geo:" + str(key) + comp, str(exc))
        return 0.01 if comp == "scale" else 0.0


def mask_inset_px(parent, fmt_w, fmt_h):
    """(ix, iy) de la mascara del viewer segun el knob bi_mask_aspect."""
    try:
        aspect = float(parent["bi_mask_aspect"].value())
    except Exception:
        aspect = 0.0
    return bi_layout.mask_inset(aspect, fmt_w, fmt_h)


def line_height_px(parent, fmt_h):
    """Alto del panel en px para un alto de formato (lo usa el pivote)."""
    try:
        pad = float(parent["bi_text_pad"].value())
    except Exception:
        pad = 28.0
    return bi_layout.line_height(_font_px(parent, None, fmt_h), pad)


_log("Modulo de logica cargado")
