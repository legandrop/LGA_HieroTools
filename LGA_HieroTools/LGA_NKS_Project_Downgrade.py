"""
____________________________________________________________________

  LGA_NKS_Project_Downgrade v1.01 | Lega

  Crea una copia de proyectos Hiero/NKS 16.1 o 17 compatible con 16.0.
  Conserva el XML original salvo la version del formato; no reconstruye
  el timeline. Las annotations nuevas requieren descarte explicito.

  v1.01: Inspeccion y nombre con siguiente version para el Projects Panel.
  v1.00: Conversion segura de formato 12 a 11, sin sobrescrituras.
____________________________________________________________________
"""

import argparse
import logging
import os
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
from xml.parsers import expat

DEBUG = False


def suggest_project_name(source):
    """Incrementa el ultimo bloque de version; sin version, agrega _NKS16."""
    stem = Path(source).stem
    matches = list(re.finditer(r'(?:^|_)([vV]?)(\d+)(?=_|$)', stem))
    if not matches:
        return stem + '_NKS16.hrox'
    match = matches[-1]
    start, end = match.span(2)
    number = match.group(2)
    return stem[:start] + str(int(number) + 1).zfill(len(number)) + stem[end:] + '.hrox'


def _read_project(source):
    source = Path(source).expanduser().resolve(strict=True)
    if source.suffix.lower() != '.hrox' or not source.is_file():
        raise ValueError('El origen debe ser un archivo .hrox.')
    data = source.read_bytes()
    if b'<!ENTITY' in data:
        raise ValueError('El proyecto contiene declaraciones XML de entidades.')
    root = ET.fromstring(data)
    if root.tag != 'hieroXML' or not any(c.tag == 'Project' for c in root):
        raise ValueError('El XML no es un proyecto Hiero/Nuke Studio completo.')
    return source, data, root


def inspect_project(source):
    """Lee el formato real y las annotations sin escribir una copia ni abrir el host."""
    logger = _logger()
    try:
        path, _data, root = _read_project(source)
        info = dict(version=int(root.get('version', '0')),
                    release=root.get('release', ''),
                    annotations=sum(1 for _node in root.iter('Annotation')))
        logger.info('Inspeccion: %s; formato=%s; release=%s; annotations=%s',
                    path, info['version'], info['release'], info['annotations'])
        return info
    except Exception:
        logger.exception('No se pudo inspeccionar el proyecto.')
        raise


def _logger():
    log_dir = Path(__file__).resolve().parent / 'logs'
    log_dir.mkdir(exist_ok=True)
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
    logger.propagate = False
    handler = logging.FileHandler(log_dir / 'DebugPy_LGA_NKS_Project_Downgrade.log',
                                  mode='w', encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logger.addHandler(handler)
    if DEBUG:
        logger.addHandler(logging.StreamHandler())
    return logger


def _annotation_ranges(data):
    """Expat mide offsets de bytes: evita reserializar CDATA, efectos y presets."""
    parser = expat.ParserCreate()
    stack = []
    ranges = []

    def start(name, attributes):
        stack.append((name, parser.CurrentByteIndex))

    def end(name):
        tag, begin = stack.pop()
        if tag == 'Annotation':
            opening_end = data.index(b'>', begin) + 1
            if data[begin:opening_end].rstrip().endswith(b'/>'):
                finish = opening_end
            else:
                finish = data.index(b'>', parser.CurrentByteIndex) + 1
            ranges.append((begin, finish))

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.Parse(data, True)
    return ranges


def convert_project(source, destination=None, *, drop_annotations=False):
    """Devuelve la ruta de una copia nueva; nunca abre ni guarda en el host.

    Para proyectos grandes, llamar fuera del hilo de UI. La funcion no
    toca Hiero/Qt. No convierte efectos o plugins exclusivos de versiones nuevas.
    """
    logger = _logger()
    try:
        source, data, root = _read_project(source)
        destination = (Path(destination).expanduser().absolute() if destination
                       else source.with_name(source.stem + '_NKS16.hrox'))
        logger.info('Origen: %s; destino: %s; descartar annotations: %s',
                    source, destination, drop_annotations)
        if destination.suffix.lower() != '.hrox':
            raise ValueError('El destino debe tener extension .hrox.')
        if destination.resolve() == source or os.path.lexists(destination):
            raise FileExistsError('El destino ya existe o es el original; no se sobrescribe.')
        if root.get('version') != '12':
            raise ValueError('Se admite solamente formato hrox 12 (NKS/Hiero 16.1 y 17).')
        release = root.get('release', '')
        if not re.fullmatch(r'(?:16\.1|17\.0)v\d+', release):
            raise ValueError('Version de origen no verificada: %s.' % release)
        annotations = sum(1 for node in root.iter('Annotation'))
        if annotations and not drop_annotations:
            raise ValueError('Hay %d annotations nuevas que NKS 16 no conserva. '
                             'Use drop_annotations=True / --drop-annotations '
                             'solo si acepta descartarlas en la copia.' % annotations)
        if annotations:
            ranges = _annotation_ranges(data)
            if len(ranges) != annotations:
                raise ValueError('No se pudieron delimitar las annotations de forma segura.')
            for begin, end in sorted(ranges, reverse=True):
                data = data[:begin] + data[end:]
            logger.warning('Se descartan %d annotations en la copia; el original las conserva.',
                           annotations)
        match = re.search(br'<hieroXML\b[^>]*>', data)
        if not match:
            raise ValueError('No se encontro la cabecera hieroXML.')
        header, count = re.subn(br'(\bversion\s*=\s*[\x22\x27])12([\x22\x27])',
                               lambda m: m[1] + b'11' + m[2], match.group())
        if count != 1:
            raise ValueError('La version del formato en la cabecera no es unica.')
        result = data[:match.start()] + header + data[match.end():]
        parsed = ET.fromstring(result)
        if parsed.get('version') != '11' or (annotations and list(parsed.iter('Annotation'))):
            raise ValueError('Fallo la verificacion del XML convertido.')
        # x protege tambien frente a otro proceso que cree el destino tras el chequeo.
        created = False
        try:
            with destination.open('xb') as handle:
                created = True
                handle.write(result)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            if created:
                destination.unlink()
            raise
        logger.info('Copia escrita: %d bytes; formato 12 -> 11.', len(result))
        return destination
    except Exception:
        logger.exception('La conversion no se completo.')
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description='Crea una copia .hrox para NKS/Hiero 16.0.')
    parser.add_argument('source', help='Proyecto .hrox de NKS/Hiero 16.1 o 17')
    parser.add_argument('-o', '--output', help='Destino nuevo; por defecto <origen>_NKS16.hrox')
    parser.add_argument('--drop-annotations', action='store_true',
                        help='Acepta descartar las annotations nuevas solo en la copia')
    args = parser.parse_args(argv)
    try:
        path = convert_project(args.source, args.output,
                               drop_annotations=args.drop_annotations)
    except (OSError, ValueError, ET.ParseError, expat.ExpatError) as error:
        print('No se pudo convertir: %s' % error, file=sys.stderr)
        return 1
    print('Copia compatible con NKS 16: %s' % path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
