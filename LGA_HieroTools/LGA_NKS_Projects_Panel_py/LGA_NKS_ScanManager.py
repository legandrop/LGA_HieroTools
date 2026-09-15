# -*- coding: utf-8 -*-

"""
____________________________________________________________________

  LGA_NKS_ScanManager v1.02 | Lega

  Gestor de escaneo para el panel de proyectos LGA.

  v1.02: Solo se aplica el escaneo mas reciente: los anteriores se descartan.
         Si el escaneo termina mientras un switch de secuencia tiene congelado
         el repintado de la ventana principal, el resultado se aplica recien
         cuando se descongela. Rearmar la lista congelada la dejaba sin dibujar
         hasta que NKS perdia y recuperaba el foco. Asi el toggle Studio/Client
         puede largar el escaneo en paralelo con el switch.
  v1.01: Los carteles de aviso pasan al helper LGA_NKS_MessageBox con el estilo del pack.
____________________________________________________________________

"""

import hiero.ui
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtCore
from LGA_NKS_Shared.LGA_NKS_MessageBox import show_warning

# Cada cuanto se reintenta aplicar un escaneo que termino con la UI congelada.
FROZEN_UI_RETRY_MS = 50


def _main_window_frozen():
    """True si un switch de secuencia tiene apagado el repintado de la ventana principal."""
    try:
        return not hiero.ui.mainWindow().updatesEnabled()
    except Exception:
        return False

# Importar funciones necesarias del módulo principal
# Estas serán importadas desde el archivo principal cuando se importe este módulo
ScanWorker = None
debug_print = None
print_debug_messages = None


def initialize_scan_dependencies(scan_worker_class, debug_func, print_debug_func):
    """Inicializar las dependencias externas necesarias para el scan manager"""
    global ScanWorker, debug_print, print_debug_messages
    ScanWorker = scan_worker_class
    debug_print = debug_func
    print_debug_messages = print_debug_func


class ScanManager:
    """Clase para manejar las operaciones de escaneo"""

    @staticmethod
    def start_scan(panel):
        """Iniciar el proceso de escaneo"""
        debug_print("🚀 Iniciando escaneo desde botón refresh...")
        panel.refresh_button.setEnabled(False)

        # Numero de escaneo: si se largan varios seguidos, solo se aplica el ultimo.
        panel._scan_generation = getattr(panel, "_scan_generation", 0) + 1
        generation = panel._scan_generation

        debug_print(f"👷 Creando ScanWorker #{generation}...")
        worker = ScanWorker()
        worker.signals.scan_finished.connect(
            lambda proyectos, abiertos: ScanManager.on_scan_finished(panel, proyectos, abiertos, generation)
        )
        worker.signals.error.connect(lambda error: ScanManager.on_scan_error(panel, error))
        worker.signals.debug_output.connect(lambda: print_debug_messages())
        debug_print("🏃 Ejecutando ScanWorker en thread pool...")
        QtCore.QThreadPool.globalInstance().start(worker)
        debug_print("✅ ScanWorker enviado a thread pool")

    @staticmethod
    def on_scan_finished(panel, proyectos_encontrados, proyectos_abiertos, generation=None):
        """Callback cuando el escaneo se completa exitosamente"""
        latest = getattr(panel, "_scan_generation", None)
        if generation is not None and latest is not None and generation != latest:
            # Hay un escaneo mas nuevo en camino: aplicar este rearma la lista dos
            # veces seguidas, que es lo que dejaba items huerfanos.
            debug_print(f"⏭️ Escaneo #{generation} descartado: hay uno mas nuevo (#{latest})")
            return
        if _main_window_frozen():
            # El switch procesa eventos adentro, asi que este timer puede volver
            # a dispararse congelado: se re-agenda hasta que se descongele.
            debug_print("⏸️ Escaneo listo con la UI congelada por un switch: display diferido")
            QtCore.QTimer.singleShot(
                FROZEN_UI_RETRY_MS,
                lambda: ScanManager.on_scan_finished(
                    panel, proyectos_encontrados, proyectos_abiertos, generation
                ),
            )
            return
        debug_print("🎉 Escaneo completado exitosamente!")
        debug_print(f"   📊 Proyectos encontrados: {len(proyectos_encontrados)}")
        debug_print(f"   📂 Grupos de proyectos abiertos: {len(proyectos_abiertos)}")

        panel.proyectos_encontrados = proyectos_encontrados
        panel.proyectos_abiertos = proyectos_abiertos

        # Obtener información de proyectos con versiones más nuevas
        debug_print("🔍 Buscando proyectos con versiones más nuevas...")
        from LGA_Projects_Panel_ScanProjects import get_projects_with_newer_versions
        proyectos_con_version_nueva = get_projects_with_newer_versions()
        panel.proyectos_con_version_nueva = proyectos_con_version_nueva
        debug_print(f"   📈 Proyectos con versiones nuevas: {len(proyectos_con_version_nueva)}")

        panel.refresh_button.setEnabled(True)

        debug_print("🔄 Llamando a update_projects_display...")
        panel.update_projects_display()

    @staticmethod
    def on_scan_error(panel, error_msg):
        """Callback cuando ocurre un error durante el escaneo"""
        debug_print(f"❌ ERROR durante el escaneo: {error_msg}")
        panel.refresh_button.setEnabled(True)
        show_warning(panel, "Error de Escaneo", error_msg)
