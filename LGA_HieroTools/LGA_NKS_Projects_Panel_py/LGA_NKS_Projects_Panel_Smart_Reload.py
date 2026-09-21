"""
____________________________________________________________________

  LGA_NKS_Projects_Panel_Smart_Reload v2.25 | Lega

  Script para recarga inteligente del panel Projects
  Destruye el panel actual, crea uno nuevo y lo dockea automáticamente
  usando el método nativo de Hiero wm.showWindow().

  v2.25: Recarga el estilo compartido antes del preview para que Reload Panel
         aplique switches o tokens nuevos sin reiniciar Nuke.
  v2.24: Recarga las ventanas privadas junto al panel, incluido
         ProjectMediaPreview; sin ese modulo, Drop media conservaba la clase
         anterior despues de Reload Panel.
  v2.23: Recarga tambien LGA_NKS_TimelineMemory. No estaba en la lista y un
         reimport dejaba corriendo la version vieja del modulo.
  v2.22: Migrado al logger compartido del Projects Panel y removidos prints directos de análisis y resultado
  v2.21: Mejorada lógica de versiones: búsqueda en anteúltimo bloque y priorización de sufijos (_Mac)
____________________________________________________________________

"""

import hiero.ui
import hiero.core
import sys
import os
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore
from LGA_NKS_Projects_Panel_py.LGA_NKS_ProjectsPanel_Logging import (
    DEBUG,
    DEBUG_CONSOLE,
    DEBUG_LOG,
    debug_print,
)

# Variable global para compartir estado entre funciones
_initial_docked_state = False


def log_panel_count(wm, context=""):
    """Función helper para loguear consistentemente el conteo de panels"""
    target_object_name = "com.lega.ProjectsPanel"
    projects_count = len([w for w in wm.windows() if w.objectName() == target_object_name])

    debug_print(f"🔢 PANEL COUNT {context}: {projects_count} panel(es) Projects")

    if projects_count > 0:
        for i, window in enumerate(wm.windows()):
            if window.objectName() == target_object_name:
                visible = window.isVisible()
                debug_print(f"   [{i}] '{window.windowTitle()}' - Visible: {visible}")

    return projects_count


def dock_panel_with_hiero_show_window(panel):
    """Dockea el panel usando el método nativo de Hiero wm.showWindow()"""
    wm = hiero.ui.windowManager()

    debug_print("🎯 Usando método nativo de Hiero: wm.showWindow()")

    try:
        result = wm.showWindow(panel)
        debug_print(f"✓ wm.showWindow() ejecutado, retornó: {result}")
        debug_print("✅ Panel dockeado exitosamente con método nativo de Hiero")
        return True
    except Exception as e:
        debug_print(f"✗ Error en wm.showWindow(): {e}")
        return False


def analyze_panel_docking(panel):
    """Analiza el estado de docking de un panel (versión simplificada)"""
    debug_print(f"\n{'='*50}")
    debug_print(f"ANALISIS DE DOCKING: {panel.objectName()}")
    debug_print(f"{'='*50}")

    # Información básica
    debug_print(f"Titulo: {panel.windowTitle()}")
    debug_print(f"Visible: {panel.isVisible()}")
    debug_print(f"Geometry: {panel.geometry()}")

    # Verificar jerarquía de parents
    has_stacked_widget = False
    current = panel
    depth = 0
    while current and depth < 10:
        if isinstance(current, QtWidgets.QStackedWidget):
            has_stacked_widget = True
            debug_print(f"Tiene QStackedWidget en profundidad {depth}")
            debug_print(f"  Count: {current.count()}")
            debug_print(f"  Current Index: {current.currentIndex()}")

            # Encontrar el índice de nuestro panel
            panel_index = -1
            for i in range(current.count()):
                widget = current.widget(i)
                if widget == panel:
                    panel_index = i
                    break
            debug_print(f"  Nuestro panel esta en indice: {panel_index}")

            # Ver otros panels en el mismo contenedor
            debug_print("  Panels en este contenedor:")
            for i in range(current.count()):
                widget = current.widget(i)
                name = getattr(widget, 'objectName', lambda: 'N/A')()
                title = getattr(widget, 'windowTitle', lambda: 'N/A')()
                current_marker = " <- CURRENT" if i == current.currentIndex() else ""
                our_panel_marker = " <- NUESTRO PANEL" if widget == panel else ""
                debug_print(f"    [{i}] {name}: '{title}'{current_marker}{our_panel_marker}")

            break
        current = current.parent()
        depth += 1

    if not has_stacked_widget:
        debug_print("No tiene QStackedWidget - no esta dockeado")

    debug_print(f"{'='*50} FIN ANALISIS {'='*50}")
    return has_stacked_widget


def count_projects_panels():
    """Cuenta y analiza todos los paneles Projects existentes"""
    wm = hiero.ui.windowManager()
    target_object_name = "com.lega.ProjectsPanel"

    projects_panels = []
    for window in wm.windows():
        if window.objectName() == target_object_name:
            projects_panels.append(window)

    debug_print(f"\nPANELS PROJECTS ENCONTRADOS: {len(projects_panels)}")
    for i, panel in enumerate(projects_panels):
        debug_print(f"  Panel {i}: {panel.windowTitle()} - Visible: {panel.isVisible()}")

        # Verificar si está dockeado
        is_docked = False
        current = panel
        depth = 0
        while current and depth < 10:
            if isinstance(current, QtWidgets.QStackedWidget):
                is_docked = True
                debug_print(f"    Dockeado en QStackedWidget (profundidad {depth})")
                break
            current = current.parent()
            depth += 1

        if not is_docked:
            debug_print("    No dockeado")

    return projects_panels


def smart_reload_panel():
    """Recarga el panel Projects usando el método nativo de Hiero wm.showWindow()"""
    wm = hiero.ui.windowManager()
    target_object_name = "com.lega.ProjectsPanel"

    debug_print("=" * 60)
    debug_print("INICIANDO SMART RELOAD DEL PANEL PROJECTS")
    debug_print("=" * 60)

    log_panel_count(wm, "[INICIO]")

    # 0. CONTAR PANELS INICIALES
    debug_print("🔍 CONTANDO PANELS ANTES DEL RELOAD:")
    initial_panels = count_projects_panels()

    # 1. Buscar panel existente
    existing_panel = None
    for window in wm.windows():
        if window.objectName() == target_object_name:
            existing_panel = window
            break

    if not existing_panel:
        debug_print("✗ ERROR: Panel Projects no encontrado")
        return

    debug_print(f"✓ Panel existente encontrado: '{existing_panel.windowTitle()}'")

    # 1.5. ANALIZAR ESTADO INICIAL (como en simple dock)
    debug_print("\n" + "="*30 + " ESTADO INICIAL " + "="*30)
    global _initial_docked_state
    _initial_docked_state = analyze_panel_docking(existing_panel)

    # 2. DESTRUIR PANEL CON MÉTODO SIMPLE QUE FUNCIONA
    debug_print("\n--- PASO 2: Destruyendo panel con método simple ---")

    try:
        log_panel_count(wm, "[ANTES DE DESTRUIR]")

        # Estrategia que funciona: hide() + deleteLater() (como en Destruir_Simple.py)
        debug_print("🔨 Destruyendo panel...")
        existing_panel.hide()
        existing_panel.deleteLater()
        debug_print("✓ Comando de destrucción enviado")

        log_panel_count(wm, "[DESPUÉS DE deleteLater()]")

        # Verificar después de 100ms y crear nuevo panel
        QtCore.QTimer.singleShot(100, lambda: create_new_panel_after_destruction(wm))

    except Exception as e:
        debug_print(f"✗ ERROR destruyendo panel: {e}")
        return

def force_cleanup_old_panels(wm):
    """Fuerza la limpieza completa de panels Projects existentes"""
    debug_print("🧹 Realizando limpieza forzada de panels Projects existentes...")

    target_object_name = "com.lega.ProjectsPanel"
    old_panels = []

    # Encontrar todos los panels Projects existentes
    for window in wm.windows():
        if window.objectName() == target_object_name:
            old_panels.append(window)

    debug_print(f"Encontrados {len(old_panels)} panel(es) Projects para limpiar")

    # Procesar cada panel con múltiples estrategias
    for i, panel in enumerate(old_panels):
        debug_print(f"  Limpiando panel {i+1}: {panel.windowTitle()} - Visible: {panel.isVisible()} - ID: {id(panel)}")

        try:
            # Estrategia 1: Remover del WindowManager
            if hasattr(wm, 'removeWindow'):
                try:
                    wm.removeWindow(panel)
                    debug_print("    ✓ Removido del WindowManager")
                except Exception as e:
                    debug_print(f"    ⚠️ Error removiendo del WindowManager: {e}")

            # Estrategia 2: Ocultar y desconectar
            panel.hide()
            panel.setParent(None)
            panel.setVisible(False)
            debug_print("    ✓ Ocultado y desconectado")

            # Estrategia 3: Destruir completamente
            panel.destroy()
            debug_print("    ✓ Destruido completamente")

        except Exception as e:
            debug_print(f"    ⚠️ Error limpiando panel: {e}")

    # Verificación final con espera
    QtCore.QTimer.singleShot(50, lambda: verify_cleanup_complete(wm))

def verify_cleanup_complete(wm):
    """Verifica que la limpieza se completó correctamente"""
    target_object_name = "com.lega.ProjectsPanel"
    remaining = len([w for w in wm.windows() if w.objectName() == target_object_name])
    debug_print(f"Panels Projects restantes después de limpieza: {remaining}")
    log_panel_count(wm, "[DESPUÉS DE LIMPIEZA FORZADA - VERIFICACIÓN]")

    if remaining == 0:
        debug_print("✅ Limpieza completa exitosa - no quedan panels Projects")
    else:
        debug_print(f"⚠️ Limpieza incompleta - quedan {remaining} panel(s) Projects")


def create_new_panel_after_destruction(wm, attempt=1, max_attempts=5):
    """Crea el nuevo panel después de la destrucción (con verificación robusta)"""
    debug_print(f"\n--- PASO 3: Verificando destrucción (intento {attempt}/{max_attempts}) ---")

    log_panel_count(wm, f"[VERIFICACIÓN INTENTO {attempt}]")

    # Verificar destrucción del panel anterior
    target_object_name = "com.lega.ProjectsPanel"
    projects_count = len([w for w in wm.windows() if w.objectName() == target_object_name])
    debug_print(f"Panels Projects restantes: {projects_count}")

    if projects_count == 0:
        debug_print("✓ No hay panels Projects restantes (destrucción exitosa)")
        create_new_panel_anyway(wm)
    else:
        debug_print(f"⚠️  Todavía hay {projects_count} panel(es) Projects existente(s)")

        if attempt >= max_attempts:
            debug_print("❌ MÁXIMO INTENTOS ALCANZADO - Procediendo con limpieza forzada")
            log_panel_count(wm, "[ANTES DE LIMPIEZA FORZADA]")
            force_cleanup_old_panels(wm)
            log_panel_count(wm, "[DESPUÉS DE LIMPIEZA FORZADA]")
            create_new_panel_anyway(wm)
        else:
            debug_print(f"⏳ Esperando más tiempo para destrucción completa... ({attempt}/{max_attempts})")
            QtCore.QTimer.singleShot(200, lambda: create_new_panel_after_destruction(wm, attempt + 1, max_attempts))

def create_new_panel_anyway(wm):
    """Reutiliza el panel automático creado por exec_module() en lugar de crear uno nuevo"""
    script_path = os.path.join(os.path.dirname(__file__), "..", "LGA_NKS_Projects_Panel.py")
    target_object_name = "com.lega.ProjectsPanel"

    log_panel_count(wm, "[INICIO CREATE_NEW_PANEL_ANYWAY]")

    try:
        debug_print(f"Cargando script desde: {script_path}")

        # Usar importlib para cargar el módulo del panel
        import importlib.util
        spec = importlib.util.spec_from_file_location("LGA_NKS_Projects_Panel", script_path)
        panel_module = importlib.util.module_from_spec(spec)

        log_panel_count(wm, "[DESPUÉS DE CREAR ESPEC]")

        # ACTIVAR auto-creación para que exec_module() cree el panel automáticamente
        panel_module.AUTO_CREATE_PANEL = True
        debug_print("✓ Activada auto-creación del panel (lo reutilizaremos)")

        # 🔄 RECARGAR MÓDULOS DEPENDIENTES ANTES DE EXEC_MODULE
        debug_print("🔄 Recargando módulos dependientes...")
        modules_to_reload = [
            # Va antes de los módulos que importan Style directamente: un
            # Reload Panel tiene que levantar tokens y hojas nuevas del preview.
            'LGA_NKS_Shared.LGA_UI_Style_HieroTools',
            # Estos módulos se importan directamente en el panel: recargarlos
            # antes garantiza que sus diálogos y logs salgan de esta pasada.
            'LGA_NKS_Projects_Panel_py.LGA_NKS_ProjectsPanel_Logging',
            'LGA_NKS_Projects_Panel_py.LGA_Projects_Panel_ScanProjects',
            # Antes que el switch y el panel, que lo importan: sin esto un
            # reimport sigue corriendo la version vieja de la memoria.
            'LGA_NKS_Projects_Panel_py.LGA_NKS_TimelineMemory',
            # El panel importa la clase directamente. Si no se recarga antes de
            # exec_module(), el siguiente Drop media abre el dialogo viejo.
            'LGA_NKS_Projects_Panel_py.LGA_NKS_ProjectMediaPreview',
            'LGA_NKS_Projects_Panel_py.LGA_NKS_TrackNames_Section',
            'LGA_NKS_Projects_Panel_py.LGA_NKS_ProjectItem',
            'LGA_NKS_Projects_Panel_py.LGA_NKS_ProjectHandler',
            'LGA_NKS_Projects_Panel_py.LGA_NKS_ScanManager',
            'LGA_NKS_Projects_Panel_py.LGA_NKS_Workers',
            'LGA_NKS_Projects_Panel_py.LGA_NKS_UIManager'
        ]

        for module_name in modules_to_reload:
            try:
                if module_name in sys.modules:
                    debug_print(f"  🔄 Recargando {module_name}")
                    importlib.reload(sys.modules[module_name])
                else:
                    debug_print(f"  ⚠️  Módulo {module_name} no estaba cargado")
            except Exception as e:
                debug_print(f"  ❌ Error recargando {module_name}: {e}")

        debug_print("✅ Recarga de módulos dependientes completada")

        spec.loader.exec_module(panel_module)

        log_panel_count(wm, "[DESPUÉS DE EXEC_MODULE]")
        debug_print("✓ Módulo cargado exitosamente - Panel automático creado")

        # ENCONTRAR TODOS los panels Projects y seleccionar el más nuevo
        projects_panels = []
        for window in wm.windows():
            if window.objectName() == target_object_name:
                projects_panels.append(window)

        debug_print(f"Encontrados {len(projects_panels)} panels Projects después de exec_module")

        # Seleccionar el panel más nuevo (último en la lista, que debería ser el creado por exec_module)
        if projects_panels:
            automatic_panel = projects_panels[-1]  # El último es el más nuevo
            debug_print(f"✓ Usando panel más nuevo: {automatic_panel.windowTitle()} - ID: {id(automatic_panel)}")

            # 🔄 RECARGAR COLORES en el nuevo panel para asegurar que use los valores actualizados del .ini
            debug_print("🔄 Recargando colores en el nuevo panel...")
            try:
                panel_module.load_project_colors()
                debug_print("✅ Colores recargados en el nuevo panel")
            except Exception as e:
                debug_print(f"⚠️ Error recargando colores: {e}")

        else:
            debug_print("❌ ERROR: No se encontraron panels Projects después de exec_module()")
            return

        if automatic_panel is None:
            debug_print("❌ ERROR: No se encontró el panel automático creado por exec_module()")
            return

        log_panel_count(wm, "[PANEL AUTOMÁTICO ENCONTRADO]")

        # USAR el panel automático - no crear uno nuevo
        debug_print("🎯 Reutilizando panel automático en lugar de crear uno nuevo")

        # 4. Dockear automáticamente con método nativo de Hiero
        debug_print("\n--- PASO 4: Dockeando panel automático ---")
        QtCore.QTimer.singleShot(300, lambda: finalize_docking(automatic_panel))

    except Exception as e:
        debug_print(f"✗ ERROR en create_new_panel_anyway: {e}")
        import traceback
        debug_print(f"Traceback completo:\n{traceback.format_exc()}")


def finalize_docking(new_panel):
    """Dockea el panel y finaliza el smart reload con análisis final"""
    wm = hiero.ui.windowManager()
    log_panel_count(wm, "[INICIO FINALIZE_DOCKING]")

    debug_print("Ejecutando docking automático...")

    success = dock_panel_with_hiero_show_window(new_panel)

    log_panel_count(wm, "[DESPUÉS DE SHOW_WINDOW]")

    # ANALIZAR ESTADO FINAL (como en simple dock)
    debug_print("\n" + "="*30 + " ESTADO FINAL " + "="*30)
    final_docked = analyze_panel_docking(new_panel)

    # CONTAR PANELS FINALES
    debug_print("\n🔍 CONTANDO PANELS DESPUÉS DEL RELOAD:")
    final_panels = count_projects_panels()

    log_panel_count(wm, "[FINAL - ANTES DEL RESULTADO]")

    # RESULTADO DETALLADO
    debug_print("\n" + "="*30 + " RESULTADO DETALLADO " + "="*30)
    global _initial_docked_state
    # Recalcular panels iniciales ya que la variable no está disponible en este scope
    initial_panels_count = 1  # Empezamos con 1 panel inicialmente
    debug_print(f"Panels al inicio: {initial_panels_count}")
    debug_print(f"Panels al final: {len(final_panels)}")
    debug_print(f"Estaba dockeado inicialmente? {_initial_docked_state}")
    debug_print(f"Esta dockeado el nuevo panel? {final_docked}")
    debug_print(f"Docking exitoso? {success}")

    if len(final_panels) > initial_panels_count:
        debug_print("⚠️  ALERTA: Se crearon panels adicionales!")
    elif len(final_panels) < initial_panels_count:
        debug_print("✓ Panel viejo destruido correctamente")
    else:
        debug_print("ℹ️  Mismo número de panels (viejo no destruido aún)")

    if final_docked:
        debug_print("🎉 ÉXITO: Panel dockeado correctamente")
        log_panel_count(wm, "[ÉXITO - PANEL DOCKEADO]")

        # Verificar que el panel correcto está dockeado
        docked_panels = []
        for panel in final_panels:
            current = panel
            depth = 0
            while current and depth < 10:
                if isinstance(current, QtWidgets.QStackedWidget):
                    docked_panels.append(panel)
                    break
                current = current.parent()
                depth += 1

        if len(docked_panels) == 1:
            debug_print("✓ Solo un panel dockeado (correcto)")
        else:
            debug_print(f"⚠️  {len(docked_panels)} panels dockeados - posible problema")

        debug_print("\n" + "=" * 60)
        debug_print("🎉 SMART RELOAD COMPLETADO EXITOSAMENTE")
        debug_print("📍 Panel dockeado automáticamente en su posición original")
        debug_print("=" * 60)
    else:
        debug_print("❌ FRACASO: Panel no se dockeó")
        log_panel_count(wm, "[FRACASO - PANEL NO DOCKEADO]")
        if success:
            debug_print("⚠️  wm.showWindow() retornó éxito pero panel no está dockeado")
        # Fallback: intentar mostrar el panel de todas formas
        try:
            new_panel.show()
            debug_print("💡 Fallback: Panel mostrado sin docking completo")
        except:
            debug_print("✗ ERROR: Ni siquiera se pudo mostrar el panel")


def main():
    """Función principal para ser llamada desde el panel"""
    smart_reload_panel()


if __name__ == "__main__":
    main()
