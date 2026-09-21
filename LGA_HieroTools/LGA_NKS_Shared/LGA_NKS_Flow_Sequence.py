"""
____________________________________________________________________

  LGA_NKS_Flow_Sequence v1.00 | Lega

  Preflight y creacion explicita de Sequences para Create Shot.

  v1.00: Detecta las Sequences faltantes sin escribir y, despues de la
         confirmacion de UI, crea unicamente las que siguen ausentes.
____________________________________________________________________
"""

from LGA_NKS_Shared.LGA_NKS_Flow_NamingUtils import (
    extract_sequence_name_from_path,
)


class SequencePreflightError(RuntimeError):
    """Error que impide validar o crear las Sequences antes de los Shots."""


def sequence_name_for_clip(clip_info, fallback_sequence_name):
    """Replica la prioridad de Create Shot: ruta del clip y luego UI."""
    return (
        extract_sequence_name_from_path((clip_info or {}).get("file_path"))
        or (fallback_sequence_name or "").strip()
    )


def find_missing_sequences(
    sg,
    clips_info,
    fallback_sequence_name,
    project_id_lookup,
):
    """Devuelve Sequences faltantes, sin realizar ninguna escritura en Flow."""
    if not sg:
        raise SequencePreflightError("Flow is not connected.")

    missing = []
    checked = set()
    for clip_info in clips_info or []:
        project_name = (clip_info.get("project_name") or "").strip()
        sequence_name = sequence_name_for_clip(
            clip_info, fallback_sequence_name
        )
        if not project_name:
            raise SequencePreflightError(
                "The Flow project could not be determined."
            )
        if not sequence_name:
            raise SequencePreflightError(
                "The Sequence name could not be determined."
            )

        project_id = project_id_lookup(project_name)
        if not project_id:
            raise SequencePreflightError(
                "Project '{0}' was not found in Flow.".format(project_name)
            )

        key = (project_id, sequence_name)
        if key in checked:
            continue
        checked.add(key)

        filters = [
            ["project", "is", {"type": "Project", "id": project_id}],
            ["code", "is", sequence_name],
        ]
        sequences = sg.find("Sequence", filters, ["id", "code"])
        if not sequences:
            missing.append(
                {
                    "project_id": project_id,
                    "project_name": project_name,
                    "sequence_name": sequence_name,
                }
            )

    return missing


def unapproved_missing_sequences(missing_sequences, approved_sequences):
    """Limita la autorizacion a los pares proyecto/nombre mostrados en UI."""
    approved_keys = {
        (item["project_id"], item["sequence_name"])
        for item in approved_sequences or []
    }
    return [
        item
        for item in missing_sequences or []
        if (item["project_id"], item["sequence_name"]) not in approved_keys
    ]


def create_missing_sequences(sg, missing_sequences):
    """Crea, tras confirmacion externa, las Sequences que aun no existen."""
    created = []
    for item in missing_sequences or []:
        project_ref = {"type": "Project", "id": item["project_id"]}
        filters = [
            ["project", "is", project_ref],
            ["code", "is", item["sequence_name"]],
        ]
        if sg.find("Sequence", filters, ["id", "code"]):
            continue

        try:
            sequence = sg.create(
                "Sequence",
                {
                    "project": project_ref,
                    "code": item["sequence_name"],
                },
            )
        except Exception as exc:
            # Otro proceso puede haberla creado entre la reconsulta y el create.
            # En ese caso se reutiliza la entidad existente en vez de duplicarla.
            existing = sg.find("Sequence", filters, ["id", "code"])
            if existing:
                continue
            raise SequencePreflightError(
                "Sequence '{0}' could not be created in project '{1}': {2}".format(
                    item["sequence_name"], item["project_name"], exc
                )
            )
        if not sequence:
            raise SequencePreflightError(
                "Sequence '{0}' could not be created in project '{1}'.".format(
                    item["sequence_name"], item["project_name"]
                )
            )
        created.append(sequence)

    return created
