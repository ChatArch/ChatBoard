"""Machine registry service for the ChatBoard Machines page."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

STATUS_ORDER = {"ok": 0, "warning": 1, "unknown": 2, "stale": 3, "offline": 4}
GROUP_TITLES = {
    "local": "Local",
    "public-cloud": "Public Cloud",
    "oray": "Local / Oray",
    "cube": "Cube Internal",
    "unknown": "Needs Review",
}


def machines_registry_path(root: Path) -> Path:
    return root / ".chatboard" / "machines.json"


def _load_registry(root: Path) -> dict[str, Any]:
    path = machines_registry_path(root)
    if not path.exists():
        return {
            "schema": "chatboard.machines.v1",
            "selected_framework": {
                "name": "Beszel",
                "url": "https://github.com/henrygd/beszel",
                "status": "selected-not-installed",
            },
            "machines": [],
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid machine registry JSON: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"machine registry must be an object: {path}")
    return data


def _machine_status(machine: dict[str, Any]) -> str:
    return str(machine.get("status") or "unknown")


def _machine_group(machine: dict[str, Any]) -> str:
    return str(machine.get("group") or machine.get("zone") or "unknown")


def _machine_title(machine: dict[str, Any]) -> str:
    return str(machine.get("title") or machine.get("id") or "Unknown machine")


def _sort_machine(machine: dict[str, Any]) -> tuple[int, str, str]:
    status = _machine_status(machine)
    group = _machine_group(machine)
    return (STATUS_ORDER.get(status, 9), group, _machine_title(machine).lower())


def _string_list(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    return [str(value)]


def _normalize_machine(machine: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(machine)
    for key in ("aliases", "roles", "evidence"):
        normalized[key] = _string_list(machine.get(key))
    if not isinstance(normalized.get("tools"), dict):
        normalized["tools"] = {}
    if not isinstance(normalized.get("status_detail"), dict):
        normalized["status_detail"] = {}
    return normalized


def list_machines(root: Path) -> dict[str, Any]:
    registry = _load_registry(root)
    raw_machines = registry.get("machines") or []
    if not isinstance(raw_machines, list):
        raise ValueError("machine registry field 'machines' must be a list")
    machines = [_normalize_machine(machine) for machine in raw_machines if isinstance(machine, dict)]
    machines.sort(key=_sort_machine)

    status_counts: dict[str, int] = {}
    group_counts: dict[str, int] = {}
    for machine in machines:
        status = _machine_status(machine)
        group = _machine_group(machine)
        status_counts[status] = status_counts.get(status, 0) + 1
        group_counts[group] = group_counts.get(group, 0) + 1

    groups = []
    for group in sorted(group_counts):
        groups.append({"key": group, "title": GROUP_TITLES.get(group, group.replace("-", " ").title()), "count": group_counts[group]})

    return {
        "root": str(root),
        "registry_path": str(machines_registry_path(root)),
        "selected_framework": registry.get("selected_framework") or {},
        "summary": {
            "total": len(machines),
            "status_counts": status_counts,
            "group_counts": group_counts,
            "last_updated": registry.get("last_updated"),
        },
        "groups": groups,
        "machines": machines,
    }


def get_machine(machine_id: str, root: Path) -> dict[str, Any] | None:
    data = list_machines(root)
    for machine in data["machines"]:
        if str(machine.get("id")) == machine_id:
            return {
                "root": data["root"],
                "registry_path": data["registry_path"],
                "selected_framework": data["selected_framework"],
                "machine": machine,
                "sections": machine_sections(machine, data["selected_framework"]),
            }
    return None


def machine_sections(machine: dict[str, Any], selected_framework: dict[str, Any]) -> list[dict[str, Any]]:
    tools_raw = machine.get("tools")
    status_raw = machine.get("status_detail")
    evidence_raw = machine.get("evidence")
    tools: dict[str, Any] = tools_raw if isinstance(tools_raw, dict) else {}
    status: dict[str, Any] = status_raw if isinstance(status_raw, dict) else {}
    evidence: list[Any] = evidence_raw if isinstance(evidence_raw, list) else []
    return [
        {
            "key": "overview",
            "title": "Overview",
            "kind": "kv",
            "data": [
                ["ID", machine.get("id")],
                ["Status", machine.get("status")],
                ["Zone", machine.get("zone") or machine.get("group")],
                ["Host", machine.get("host")],
                ["Port", machine.get("port")],
                ["SSH alias", machine.get("ssh_alias")],
                ["Aliases", ", ".join(machine.get("aliases") or [])],
                ["Roles", ", ".join(machine.get("roles") or [])],
                ["Notes", machine.get("notes")],
            ],
        },
        {
            "key": "status",
            "title": "Status",
            "kind": "kv",
            "data": [[key.replace("_", " ").title(), value] for key, value in status.items()] or [["Status", machine.get("summary")]],
        },
        {
            "key": "tools",
            "title": "Tools",
            "kind": "kv",
            "data": [
                ["Selected framework", selected_framework.get("name") or "Beszel"],
                ["Framework status", selected_framework.get("status") or "selected-not-installed"],
                ["Beszel", tools.get("beszel") or "not configured"],
                ["Cockpit", tools.get("cockpit") or "not configured"],
                ["Netdata", tools.get("netdata") or "not configured"],
                ["Uptime", tools.get("uptime") or "not configured"],
                ["Homepage", tools.get("homepage") or "not configured"],
            ],
        },
        {
            "key": "evidence",
            "title": "Evidence",
            "kind": "list",
            "data": evidence or ["No evidence path recorded yet."],
        },
    ]
