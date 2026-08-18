import frappe


def execute() -> None:
	"""Portal Task web form: view + comments only (no edit/create/delete)."""
	if not frappe.db.exists("Web Form", "tasks"):
		return

	frappe.db.set_value(
		"Web Form",
		"tasks",
		{
			"allow_edit": 0,
			"allow_delete": 0,
			"allow_multiple": 0,
			"allow_comments": 1,
		},
		update_modified=False,
	)
	frappe.clear_document_cache("Web Form", "tasks")
	frappe.db.commit()
