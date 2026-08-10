from __future__ import annotations

import json
from typing import Any

import frappe


SIDEBAR_ITEMS: list[dict[str, Any]] = [
	{
		"type": "Link",
		"label": "Inquérito de Satisfação",
		"link_type": "DocType",
		"link_to": "Satisfaction Survey",
		"icon": "review",
		"child": 0,
		"collapsible": 1,
		"indent": 0,
		"keep_closed": 0,
		"show_arrow": 0,
	},
	{
		"type": "Link",
		"label": "Modelo de Inquérito",
		"link_type": "DocType",
		"link_to": "Satisfaction Survey Template",
		"icon": "file-text",
		"child": 0,
		"collapsible": 1,
		"indent": 0,
		"keep_closed": 0,
		"show_arrow": 0,
	},
]


def execute() -> None:
	_add_projects_sidebar_links()
	_add_projects_workspace_card()
	frappe.clear_cache()


def _add_projects_sidebar_links() -> None:
	if not frappe.db.exists("Workspace Sidebar", "Projects"):
		return

	sidebar = frappe.get_doc("Workspace Sidebar", "Projects")
	existing = {(row.link_type, row.link_to) for row in sidebar.items if row.link_to}

	changed = False
	for item in SIDEBAR_ITEMS:
		key = (item["link_type"], item["link_to"])
		if key in existing:
			continue
		sidebar.append("items", item)
		changed = True

	if changed:
		# Evitar exportar o Workspace standard do ERPNext em developer_mode
		frappe.flags.in_import = True
		try:
			sidebar.flags.ignore_links = True
			sidebar.save(ignore_permissions=True)
		finally:
			frappe.flags.in_import = False


def _add_projects_workspace_card() -> None:
	if not frappe.db.exists("Workspace", "Projects"):
		return

	ws = frappe.get_doc("Workspace", "Projects")
	existing_labels = {row.label for row in ws.links}

	changed = False
	if "Inquéritos" not in existing_labels:
		ws.append(
			"links",
			{"type": "Card Break", "label": "Inquéritos", "hidden": 0, "link_count": 2},
		)
		changed = True

	desired_links = [
		{
			"type": "Link",
			"label": "Inquérito de Satisfação",
			"link_type": "DocType",
			"link_to": "Satisfaction Survey",
			"hidden": 0,
			"onboard": 0,
			"is_query_report": 0,
		},
		{
			"type": "Link",
			"label": "Modelo de Inquérito de Satisfação",
			"link_type": "DocType",
			"link_to": "Satisfaction Survey Template",
			"hidden": 0,
			"onboard": 0,
			"is_query_report": 0,
		},
	]
	existing_link_tos = {
		(row.link_type, row.link_to) for row in ws.links if row.type == "Link"
	}
	for link in desired_links:
		key = (link["link_type"], link["link_to"])
		if key in existing_link_tos:
			continue
		ws.append("links", link)
		changed = True

	# Ensure card appears in workspace content JSON
	try:
		content: list[dict[str, Any]] = json.loads(ws.content or "[]")
	except json.JSONDecodeError:
		content = []

	has_card = any(
		block.get("type") == "card"
		and (block.get("data") or {}).get("card_name") == "Inquéritos"
		for block in content
	)
	if not has_card:
		content.append(
			{
				"id": "lp_sat_card",
				"type": "card",
				"data": {"card_name": "Inquéritos", "col": 4},
			}
		)
		ws.content = json.dumps(content)
		changed = True

	# Shortcut on Projects home
	existing_shortcuts = {(s.type, s.link_to) for s in ws.shortcuts}
	if ("DocType", "Satisfaction Survey") not in existing_shortcuts:
		ws.append(
			"shortcuts",
			{
				"type": "DocType",
				"link_to": "Satisfaction Survey",
				"label": "Inquéritos",
				"doc_view": "List",
				"color": "Blue",
			},
		)
		changed = True

	if changed:
		# Evitar exportar o Workspace standard do ERPNext em developer_mode
		frappe.flags.in_import = True
		try:
			ws.flags.ignore_links = True
			ws.save(ignore_permissions=True)
		finally:
			frappe.flags.in_import = False
