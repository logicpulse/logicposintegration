from __future__ import annotations

import json
from pathlib import Path

import frappe


def execute() -> None:
	"""Importa Number Cards e Dashboard Charts do dashboard de Satisfaction Survey."""
	module_path = Path(frappe.get_app_path("logicposintegration")) / "logicpos_integration"
	frappe.flags.in_import = True
	try:
		_import_standard_records(module_path / "number_card", "Number Card")
		_import_standard_records(module_path / "dashboard_chart", "Dashboard Chart")
	finally:
		frappe.flags.in_import = False
	frappe.clear_cache()


def _import_standard_records(folder: Path, doctype: str) -> None:
	if not folder.exists():
		return
	for json_path in sorted(folder.glob("*/*.json")):
		data: dict = json.loads(json_path.read_text(encoding="utf-8"))
		name: str | None = data.get("name")
		if not name:
			continue
		if frappe.db.exists(doctype, name):
			doc = frappe.get_doc(doctype, name)
			for key, value in data.items():
				if key in (
					"doctype",
					"name",
					"modified",
					"modified_by",
					"creation",
					"owner",
					"roles",
					"y_axis",
				):
					continue
				doc.set(key, value)
			if doctype == "Dashboard Chart":
				doc.set("roles", [])
				for role in data.get("roles") or []:
					doc.append("roles", role)
			doc.flags.ignore_validate = True
			doc.save(ignore_permissions=True)
		else:
			doc = frappe.get_doc(data)
			doc.flags.ignore_validate = True
			doc.insert(ignore_permissions=True)
