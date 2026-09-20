# -*- coding: utf-8 -*-
"""
____________________________________________________________________

  LGA_NKS_ClientVendorAccess v1.00 | Lega

  Preflight fail-closed de acceso vendor para Create Shot en contexto client.
  No importa Hiero ni Qt y no realiza escrituras.

  v1.00: Validación cruzada de vendors, Group, HumanUser.groups,
         sg_vendor_group y Project.users.
____________________________________________________________________
"""

import json

from LGA_NKS_Shared.LGA_NKS_Flow_NamingUtils import (
    INTERNAL_VENDOR_TOKEN,
    is_internal_vendor_token,
    normalize_vendor_token,
)

PROJECT_SETTINGS_FIELD = "sg_pipesync_project_settings_json"
PROJECT_ACCESS_FIELD = "sg_pipesync_vendor_access_json"
HUMAN_VENDOR_GROUP_FIELD = "sg_vendor_group"


class VendorAccessError(ValueError):
    pass


def _json_object(value, label):
    try:
        parsed = json.loads(value or "{}") if isinstance(value, str) else (value or {})
    except (TypeError, ValueError) as exc:
        raise VendorAccessError("Invalid JSON in {0}.".format(label)) from exc
    if not isinstance(parsed, dict):
        raise VendorAccessError("{0} does not contain a JSON object.".format(label))
    return parsed


def _ref(entity_type, entity_id):
    return {"type": entity_type, "id": int(entity_id)}


def _has_ref(items, entity_id):
    return any(int(item.get("id") or 0) == int(entity_id) for item in (items or []))


def resolve_client_vendor_access(sg, project_id, vendor_tokens):
    """Resuelve todo el acceso vendor o aborta sin modificar Flow.

    SUP devuelve un plan interno vacío. Un vendor externo exige un único token,
    Group mapeado, usuarios no vacíos y doble membresía consistente.
    """
    normalized = [normalize_vendor_token(item) for item in (vendor_tokens or []) if normalize_vendor_token(item)]
    if len(normalized) > 1:
        raise VendorAccessError("Create Shot requires exactly one external vendor.")
    token = normalized[0] if normalized else ""

    project = sg.find_one(
        "Project", [["id", "is", int(project_id)]],
        ["id", "users", PROJECT_SETTINGS_FIELD, PROJECT_ACCESS_FIELD],
    )
    if not project:
        raise VendorAccessError("The project was not found in Flow.")
    settings = _json_object(project.get(PROJECT_SETTINGS_FIELD), PROJECT_SETTINGS_FIELD)
    raw_vendors = settings.get("vendors") or []
    if not isinstance(raw_vendors, list):
        raise VendorAccessError("Project vendors[] is not a list.")
    configured = [normalize_vendor_token(item) for item in raw_vendors]
    if INTERNAL_VENDOR_TOKEN in configured:
        raise VendorAccessError("SUP is reserved for internal naming and conflicts with vendors[].")
    if not token:
        return {"kind": "none", "vendor": None, "group": None, "users": [], "project_users_to_add": []}
    if is_internal_vendor_token(token):
        return {"kind": "internal", "vendor": token, "group": None, "users": [], "project_users_to_add": []}
    if token not in configured:
        raise VendorAccessError("Vendor '{0}' is not configured for the project.".format(token))

    access = _json_object(project.get(PROJECT_ACCESS_FIELD), PROJECT_ACCESS_FIELD)
    raw_ids = access.get("vendor_group_ids") or {}
    if not isinstance(raw_ids, dict):
        raise VendorAccessError("vendor_group_ids is not an object.")
    try:
        group_ids = {
            normalize_vendor_token(key): int(value or 0)
            for key, value in raw_ids.items()
        }
    except (TypeError, ValueError) as exc:
        raise VendorAccessError("vendor_group_ids contains an invalid Group id.") from exc
    group_id = group_ids.get(token, 0)
    if group_id <= 0:
        raise VendorAccessError("Vendor '{0}' has no mapped Group.".format(token))
    group = sg.find_one("Group", [["id", "is", group_id]], ["id", "code", "users"])
    if not group:
        raise VendorAccessError("The Group for vendor '{0}' does not exist.".format(token))
    users = sg.find(
        "HumanUser", [[HUMAN_VENDOR_GROUP_FIELD, "is", _ref("Group", group_id)]],
        ["id", "name", HUMAN_VENDOR_GROUP_FIELD, "groups"],
    ) or []
    if not users:
        raise VendorAccessError("The Group for vendor '{0}' has no users.".format(token))
    for user in users:
        vendor_group = user.get(HUMAN_VENDOR_GROUP_FIELD) or {}
        if int(vendor_group.get("id") or 0) != group_id or not _has_ref(user.get("groups"), group_id):
            raise VendorAccessError("User '{0}' is missing one of the required vendor memberships.".format(user.get("name") or user.get("id")))
    current_ids = {int(item.get("id") or 0) for item in (project.get("users") or [])}
    missing = [_ref("HumanUser", user["id"]) for user in users if int(user["id"]) not in current_ids]
    return {
        "kind": "external", "vendor": token,
        "group": _ref("Group", group_id),
        "users": [_ref("HumanUser", user["id"]) for user in users],
        "project_users_to_add": missing,
    }


def shot_vendor_fields(plan):
    return {"sg_vendor_groups": [plan["group"]]} if plan and plan.get("kind") == "external" else {}


def task_vendor_fields(plan):
    return {"task_assignees": list(plan["users"])} if plan and plan.get("kind") == "external" else {}


def resolve_selected_reviewers(sg, reviewers_config, reviewer_names):
    """Resolver estricto para el preflight Client: todo seleccionado debe existir una vez."""
    result = []
    for key, selected in (reviewers_config or {}).items():
        if not selected:
            continue
        name = reviewer_names.get(key)
        if not name:
            raise VendorAccessError("Selected reviewer '{0}' is not configured.".format(key))
        users = sg.find("HumanUser", [["name", "is", name]], ["id", "name"]) or []
        if len(users) != 1:
            raise VendorAccessError("Reviewer '{0}' could not be resolved uniquely in Flow.".format(name))
        result.append(_ref("HumanUser", users[0]["id"]))
    return result


def add_project_users(sg, project_id, plan):
    """Agrega únicamente candidatos prevalidos mediante el modo aditivo de Flow."""
    missing = list((plan or {}).get("project_users_to_add") or [])
    if not missing:
        return []
    sg.update(
        "Project", int(project_id), {"users": missing},
        multi_entity_update_modes={"users": "add"},
    )
    return missing
