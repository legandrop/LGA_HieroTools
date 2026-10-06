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

No sirve cualquier `.nk` guardado desde un shot. La tool exige que el template
tenga un Read por cada slot, identificado por su **label**: `aPlate` …
`fPlate`, `aDenoised` … `fDenoised`, `cbPlate`, `rfPlate`, `ccPlate` y
`lgPlate`. Cada uno es un trío Read → Anchor → Stamp, y los slots que no son
del shot de origen llevan `file PLACEHOLDER`. Si falta alguno, la corrida
termina con `El template no tiene estos Reads esperados` y la lista: un
template con los Reads sin label cae ahí aunque tenga el aPlate y el denoised
bien conectados.
