# Borrado seguro en HieroTools

Un borrado programatico (`shutil.rmtree`, `os.remove`) no pasa por la papelera. En este pack
se borra material de shots reales, asi que todo borrado recursivo lleva guardas duras,
independientes de la logica de negocio que decide SI borrar.

## Las guardas

- **Ruta absoluta.** Una relativa se resuelve contra el directorio actual del proceso.
  Ojo con `T:` en Windows: sin barra es relativa a la unidad.
- **Nunca la raiz de una unidad**, ni como destino ni como carpeta madre.
- **Contencion canonica**: se compara `normcase(realpath(...))`, no textos. Un enlace que
  apunta afuera cae afuera.
- **Cada tramo del camino, sin resolver**: si un tramo intermedio es un junction que apunta a
  otro lugar ADENTRO del mismo arbol, la contencion canonica lo da por bueno. Se recorre la
  ruta tramo a tramo preguntando si es enlace.
- **Escanear el arbol entero antes de tocar el disco**: si aparece un enlace a cualquier
  nivel, no se borra nada. Chequear solo el primer nivel no alcanza.
- **Contabilidad honesta**: nada de `ignore_errors=True`. Los fallos se juntan con `onerror`,
  un archivo de solo lectura se destraba y se reintenta, y el log nombra lo que quedo. Nunca
  "eliminado" sin verificar que la carpeta ya no esta.

## Lo que costo aprender: `islink()` miente con los junctions

`os.path.islink()`, `Path.is_symlink()` (hasta 3.12) y `DirEntry.is_symlink()` dan **False**
para un junction de Windows (`mklink /J`), que es justo lo que se usa para "linkear" carpetas
de un shot. La pregunta correcta es el atributo del `lstat`:

    st = os.lstat(path)
    stat.S_ISLNK(st.st_mode) or (st.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)

## Donde se aplica

- `LGA_import_shots_transcode.py` (v1.02): `Originals/<plate>` y `_tc_temp_src`. Ver la
  seccion "Borrado honesto y enlaces" de `LGA_import_shots_transcode.md`, que explica por que
  el borrado posterior al exito informa en vez de levantar excepcion.
- `LGA_NKS_CreateV000.py` (v1.21): reemplazo de una v000 existente. La carpeta tiene que ser
  exactamente `<shot>/<task>/4_publish/<shot>_<task>_v000`: nombre completo y tres niveles
  bajo el shot. El resultado va al log sin depender de `DEBUG`.

La regla general de las apps LGA vive en `Doc_Borrado_Seguro.md` de `LGA_Base_QT_C_Py`.
