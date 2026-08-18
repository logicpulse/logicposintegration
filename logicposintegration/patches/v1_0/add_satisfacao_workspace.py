from __future__ import annotations

import json
from pathlib import Path

import frappe


def execute() -> None:
	"""Garante o Workspace Desk 'Inquéritos de Satisfação' (filho de Projects)."""
	path = (
		Path(frappe.get_app_path("logicposintegration"))
		/ "logicpos_integration"
		/ "workspace"
		/ "inqueritos_de_satisfacao"
		/ "inqueritos_de_satisfacao.json"
	)
	data = json.loads(path.read_text(encoding="utf-8"))
	name: str = data["name"]

	if frappe.db.exists("Workspace", name):
		doc = frappe.get_doc("Workspace", name)
		for key, value in data.items():
			if key in (
				"links",
				"shortcuts",
				"charts",
				"number_cards",
				"quick_lists",
				"custom_blocks",
				"roles",
				"doctype",
				"name",
				"modified",
				"modified_by",
				"creation",
				"owner",
			):
				continue
			doc.set(key, value)
		doc.set("links", [])
		for link in data.get("links") or []:
			doc.append("links", link)
		doc.set("shortcuts", [])
		for sc in data.get("shortcuts") or []:
			doc.append("shortcuts", sc)
		doc.save(ignore_permissions=True)
	else:
		frappe.get_doc(data).insert(ignore_permissions=True)

	frappe.clear_cache()
