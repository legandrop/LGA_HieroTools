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

`os.path.islink()`, `Path.is_symlink()` y `DirEntry.is_symlink()` dan **False**
para un junction de Windows (`mklink /J`), que es justo lo que se usa para "linkear" carpetas
de un shot. La pregunta correcta es el atributo del `lstat`:

    st = os.lstat(path)
    stat.S_ISLNK(st.st_mode) or (st.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)

`is_symlink()` sigue dando False para un junction tambien en Python 3.12: lo que 3.12 agrega es
`Path.is_junction()`, una pregunta aparte. El atributo del `lstat` cubre los dos casos en
cualquier version.

## Mover no es borrar, pero pierde igual

Dos caminos de perdida que no pasaban por ningun `rmtree`, en el transcode de Import Shots:

- **Un move que falla a mitad.** Si mover los EXR a `Originals/` se cortaba en el tercero de
  cinco (antivirus, indexador, NAS), el restore borraba todo `*.exr` de `item_path`, incluidos
  los originales que todavia no se habian movido. Regla: un restore solo borra un archivo si su
  copia a salvo existe del otro lado con el mismo nombre. Y el move de cada EXR es `os.rename`
  (atomico) o, entre discos, copiar + verificar tamano + recien ahi borrar: nunca queda una
  copia parcial como unica version, y nunca se pisa un destino existente.
- **Validar contra lo que hay, no contra que haya algo.** El overwrite borraba los convertidos
  si `Originals/<plate>` tenia ALGUN EXR. Si un borrado anterior quedo a medias, eso puede ser 1
  de 5. Regla: antes de borrar un convertido, su original con el mismo nombre tiene que estar.

## Donde se aplica

- `LGA_import_shots_transcode.py` (v1.02): `Originals/<plate>` y `_tc_temp_src`. Ver la
  seccion "Borrado honesto y enlaces" de `LGA_import_shots_transcode.md`, que explica por que
  el borrado posterior al exito informa en vez de levantar excepcion.
- `LGA_NKS_CreateV000.py` (v1.21): reemplazo de una v000 existente. La carpeta tiene que ser
  exactamente `<shot>/<task>/4_publish/<shot>_<task>_v000`: nombre completo y tres niveles
  bajo el shot. El resultado va al log sin depender de `DEBUG`.
- `LGA_import_shots_rename.py` (v1.02): la copia del modo test (`<padre>/renamned/<plate>`),
  que vive al lado del plate real. Guardas completas; si algo no cierra, el panel lo muestra
  como error del rename.
- `LGA_NKS_Flow_Push.py` (v4.16) y `LGA_NKS_Flow_Push_connector.py` (v1.13): carpetas
  propias (`ReviewPic_Cache` y un `mkdtemp`). Solo contabilidad honesta, y el cache no se toca
  si es un enlace.

La regla general de las apps LGA vive en `Doc_Borrado_Seguro.md` de `LGA_Base_QT_C_Py`.
