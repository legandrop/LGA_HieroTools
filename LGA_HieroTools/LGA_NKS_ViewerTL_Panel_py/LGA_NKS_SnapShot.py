"""
____________________________________________________________________

  LGA_NKS_SnapShot v0.64 | Lega

  Crea un snapshot de la imagen actual del viewer y lo copia al portapapeles

  v0.64: Se captura el viewer entero y solo se recorta el negro que lo rodea,
         de cualquier lado (LGA_NKS_ViewerCrop), en vez de recortar centrado
         al aspect ratio de la secuencia.
  v0.63: Shift+Click abre el snapshot en FrameRev (ver LGA_NKS_FrameRev) en vez
         del ShareX ImageEditor LGA que viajaba en el pack. La captura le llega
         por un PNG temporal que FrameRev borra al leerlo, y queda ademas en el
         portapapeles como con el click normal.
  v0.62: Shift+Click abre el snapshot en ShareX ImageEditor LGA sin crear archivos.
  v0.61: Se tiene en cuenta el pixel aspect ratio (PAR) del formato. El crop ahora se
         hace contra el DISPLAY aspect (storage * PAR) en lugar del storage aspect,
         porque viewer.image() ya entrega la imagen con el PAR aplicado. Antes, en
         timelines con PAR != 1, se recortaban los lados de la imagen.
____________________________________________________________________
"""

import hiero.core
import hiero.ui
import os
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets

DEBUG = False
SaveToFile = False


def debug_print(*message):
    if DEBUG:
        print(*message)


def open_in_image_editor(qimage):
    """Abre la captura en FrameRev como captura sin archivo propio.

    Pasa por un PNG temporal que FrameRev borra apenas lo lee (ver
    LGA_NKS_FrameRev.open_capture): no queda nada en disco, y Save en FrameRev
    pregunta donde guardar. Si FrameRev falta o es viejo, avisa con un cartel.
    """
    from LGA_NKS_Shared import LGA_NKS_FrameRev

    # La captura queda tambien en el portapapeles, como con el click normal: si
    # FrameRev falta, el usuario no la pierde.
    app = QtWidgets.QApplication.instance()
    if app:
        app.clipboard().setImage(qimage)

    error = LGA_NKS_FrameRev.open_capture(qimage)
    if error:
        LGA_NKS_FrameRev.warn_user(error)
        return False
    return True


def main(open_in_editor=False):
    output_path = r"T:\Borrame\snapshot.jpg"

    viewer = hiero.ui.currentViewer()
    if not viewer:
        raise Exception("No active viewer")

    qimage = viewer.image()
    if qimage is None or qimage.isNull():
        raise Exception("viewer.image() devolvió None o imagen nula")

    # Se captura el viewer entero y solo se le saca el negro que lo rodea, de
    # cualquier lado (ver LGA_NKS_ViewerCrop).
    from LGA_NKS_Shared.LGA_NKS_ViewerCrop import crop_black_borders

    qimage_cropped = crop_black_borders(qimage)

    debug_print(
        "Snapshot size (cropped):", qimage_cropped.width(), "×", qimage_cropped.height()
    )

    if SaveToFile:
        debug_print("Ruta de salida:", output_path)

        output_dir = os.path.dirname(output_path)
        if not os.path.isdir(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        ok = qimage_cropped.save(output_path, "JPEG")
        debug_print("qimage.save result:", ok)

        if ok and os.path.exists(output_path):
            debug_print("✅ Archivo creado:", output_path)
        else:
            debug_print("❌ No se pudo crear el archivo.")

    if open_in_editor:
        if open_in_image_editor(qimage_cropped):
            debug_print("Imagen abierta en FrameRev.")
        return

    # Copiar al portapapeles
    app = QtWidgets.QApplication.instance()
    if not app:
        app = QtWidgets.QApplication([])

    clipboard = app.clipboard()
    clipboard.setImage(qimage_cropped)

    debug_print("✅ Imagen (cropeada) copiada al portapapeles.")


# --- Main Execution ---
if __name__ == "__main__":
    # Necesario para ejecucion standalone fuera de Nuke
    main()
