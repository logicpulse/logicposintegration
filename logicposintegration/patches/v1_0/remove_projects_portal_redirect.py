import frappe


def execute():
	"""Remove broken projects→project redirect and clear stale website redirect cache."""
	frappe.cache.delete_value("website_redirects")
	frappe.clear_document_cache("Website Settings", "Website Settings")

	for name in frappe.get_all(
		"Website Route Redirect",
		filters={"source": "projects", "target": "project"},
		pluck="name",
	):
		frappe.delete_doc("Website Route Redirect", name, ignore_permissions=True)

	frappe.db.commit()
