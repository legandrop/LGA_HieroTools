# Create NK v000

Crea el comp v000 desde un template del proyecto. El aPlate es obligatorio.
El escaneo y la escritura corren en workers; los diálogos, en el hilo principal.

Si faltan secuencias EXR denoised para los plates del shot que tienen slots
en el template (a–f), aparece una sola confirmación con todos los faltantes.
El cartel destaca `Missing denoised`, los Reads afectados y `original template
paths` para identificar el problema y la consecuencia de continuar de un vistazo.
`Cancel` termina sin escribir. `Continue` permite elegir el rango y crear el
script conservando los tríos Read/Anchor/Stamp y las rutas originales de esos
denoised, incluso el nombre del shot de origen y los placeholders del template.
Los rangos de esos Reads también se conservan. El aviso final identifica cuáles
quedaron pendientes; sus rutas se deben corregir cuando estén los renders.

Los denoised encontrados se actualizan normalmente. Los slots de plates que
el shot no tiene se eliminan junto con sus denoised. Las columnas extra con
medios existentes se clonan como antes. La conservación no inventa rutas ni
renders para columnas que el template no contempla.

Si el destino existe, se solicita además autorización para sobrescribirlo y se
guarda la copia `.nk~`. Esta confirmación es independiente de los denoised.

## Nombre del shot y vendor

El shot es el nombre de su **carpeta**: `PROJA_503_010`, o `PROJB_1013_0800_VEN`
en los proyectos que llevan vendor al final. El vendor es opcional y no se
consulta la lista de vendors de PipeSync: con la carpeta alcanza, y así la tool
no depende de que el vendor esté cargado.

Lo que sí importa es **dónde** se lee el nombre. El cuarto bloque solo se puede
decidir por estructura cuando el nombre está completo y delimitado (la carpeta,
un segmento entre barras). Suelto en el texto no: `PROJA_010_020_comp` y
`PROJB_010_020_VEN` tienen la misma forma. Por eso el shot de origen del
template se busca como carpeta en sus rutas (`.../<seq>/<shot>/...`), tomando la
más repetida y descartando el shot del nombre del template (`PROJA_000_000`).
Hasta la v1.14 se buscaba como token suelto de cuatro bloques, y en un proyecto
sin vendor eso devolvía `PROJA_089_010_aPla`: el shot más el arranque de
`_aPlate`.

Si el template no tiene ninguna ruta con la carpeta del shot, se buscan nombres
sueltos con la misma cantidad de bloques que el shot destino.

## Qué tiene que traer el template

Un **slot** es un trío Read → Anchor → Stamp cuyo Read lleva el nombre del slot
en su **label**: `aPlate` … `fPlate`, `aDenoised` … `fDenoised`, `cbPlate`,
`rfPlate`, `ccPlate`, `lgPlate`. La tool reconoce el slot por el label, no por
el nombre del archivo: un Read sin label no existe para ella.

El único slot obligatorio es `aPlate`. El template trae los demás si quiere:
un proyecto de un solo plate puede tener solo `aPlate` y `aDenoised`. Hasta la
v1.15 se exigían los 16 y la corrida abortaba con la lista de los que faltaban.

- **El Read de un slot puede estar vacío.** Alcanza con el label. Nuke no
  escribe los knobs que quedaron en su default, así que un Read recién creado
  se guarda sin `file` ni rango; la tool los agrega. Hasta la v1.15 solo
  reemplazaba knobs existentes: el Read quedaba vacío y el log decía `SET`
  igual. El log ahora marca `[el Read venia sin file]`.
- **Un plate del shot sin slot en el template se clona** del último slot de
  letra que sirva de molde (`f`, `e`, … `b`), plate desde plate y denoised
  desde denoised. Con un solo slot `b` de cada tipo alcanza para clonar todos
  los demás.
- **El slot `a` nunca sirve de molde.** Su trío lleva líneas `set`/`push` y su
  Stamp está cableado al resto del comp, fuera de la columna de input: una
  copia quedaría colgando en el medio del graph. Si el shot trae un plate que
  el template no contempla y no hay otro slot del que copiar, ese plate no se
  agrega y el cartel final lo avisa por nombre.
- **Las columnas se ubican según el propio template.** La primera va en la x
  del Read `aPlate`, el paso es la distancia `aPlate` → `aDenoised`
  (`COLUMN_STEP` si no hay `aDenoised`) y el backdrop `input` conserva el
  margen que tenía a la derecha de su último slot. Hasta la v1.15 eran
  coordenadas fijas medidas sobre un template: en otro armado en otra zona
  del node graph, los plates caían fuera de su backdrop.

## Nodos de look: CDL, CLF y .cube

Los nodos OCIO del template (`OCIOCDLTransform`, `OCIOFileTransform`) se
apuntan a los archivos del shot en `<shot>/_input/Look_Files`. Cada nodo recibe
el tipo de archivo que le corresponde:

| Nodo del template | Recibe |
|---|---|
| `OCIOCDLTransform` | el `.cdl` del aPlate (`*aplate*.cdl` o `*_cdl`), de version mas alta |
| `OCIOFileTransform` cuyo `file` nombra un `.cube` | el `.cube` del shot |
| cualquier otro `OCIOFileTransform` | el `.clf` del shot |

**El tipo lo decide lo que el template ya trae en el `file` del nodo**: una ruta
o una expresion TCL que contenga `.cube` (por ejemplo la que busca `*.cube` en
`Look_Files`). Un `OCIOFileTransform` sin `file` no dice que formato espera y se
trata como `.clf`, que era lo unico que existia antes. **Si el LMT de un show es
un `.cube`, el template tiene que dejar el nodo con su `file` puesto** (alcanza
con la ruta de cualquier shot, que la tool reemplaza). Hasta la v1.16 un nodo
con `.cube` se pisaba con el `.clf` del shot, o quedaba intacto sin aviso si el
shot no tenia `.clf`.

**Que `.cube` se elige.** Es el LMT del proyecto, no de un plate (igual que el
`.clf`), asi que no se filtra por plate: entre varios gana el de version mas
alta (`_vNN` del nombre) y, si empatan o ninguno trae version, el ultimo por
orden alfabetico. Las mayusculas de la extension no importan.

**Reglas que no cambian:**

- Un `file` que apunta a un archivo concreto FUERA de `Look_Files` no se toca:
  lo puso alguien a mano y no es el look del shot. Pasa tambien con un `.cube`
  de ruta fija: queda como vino y el cartel final lo avisa como cualquier nodo
  de color no reconocido. Si algun show necesita lo contrario, es una decision
  de la regla, no un caso del `.cube`.
- Si el shot no trae el archivo, el nodo conserva la ruta del template y el
  cartel avisa. El aviso `No .cube LUT found` solo sale si el template tiene
  nodos de `.cube` (en el resto de los proyectos no tener `.cube` es lo normal),
  y el de `.clf` se omite cuando el template tiene solo nodos de `.cube`.

## Writes de video: el limit range sin handles

El EditRef del shot define la ventana del review, sin handles. Esa ventana se
aplica como limit range (`use_limit true`, `first`, `last`) a **todo Write cuya
salida es video**, sea cual sea su nombre. Hasta la v1.16 solo se tocaba el
Write llamado `WRITE_DNXHD`: en un show cuyo Write se llamaba `WRITE_REV` el
rango quedaba el del template, sin ningun aviso.

- **Que es "de video":** `file_type` en `mov`, `mov64` o `mxf`. Si el nodo no
  trae `file_type` -Nuke no guarda los knobs en su default, y ahi el formato
  sale de la extension- decide la extension del `file`: `.mov` o `.mxf`. Manda
  `file_type`: un Write con `file_type exr` y `file` terminado en `.mov` escribe
  EXR y no se toca. El `file` suele ser una expresion TCL; la extension es el
  texto literal del final. Si el final es otra expresion (`...]`) no se puede
  saber sin evaluarla, el Write no cuenta como video y el log lo dice
  (`extension indeterminada`).
- **Un show puede tener dos salidas de video** (reviews en DNxHD y entregas en
  otro `.mov`/`.mxf`): las dos van sin handles y las dos reciben el rango.
- **Los Write de imagen** (`.exr`, `.tif`, `.dpx`) no se tocan.
- **Write deshabilitado:** se ajusta igual. Sigue siendo parte del template y,
  si alguien lo prende despues, tiene que salir con el rango correcto y no con
  handles. El log lo marca `[deshabilitado]`.
- **Write dentro de un Group:** se ajusta igual. En un `.nk` los nodos internos
  de un Group van como chunks indentados a continuacion de la llave de cierre del
  Group, asi que el recorrido del texto los ve igual que a los de afuera; el log
  dice en que grupo estaba.
- **Sin ningun Write de video:** no es un error. El log lo registra
  (`WRITE de video: ninguno ...`) y el script se arma igual.
- **Sin duracion del EditRef** (no hay mov o no se pudo medir) no hay ventana
  que aplicar: los Write quedan como vinieron y el log lo dice. El cartel final
  ya avisa del EditRef.
