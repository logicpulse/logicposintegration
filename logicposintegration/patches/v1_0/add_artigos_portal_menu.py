import frappe


def execute():
	"""Artigos fica no sidebar via hooks.portal_menu_items.

	Garante que não há entrada duplicada em Portal Settings (ex.: de patches antigos).
	"""
	ps = frappe.get_single("Portal Settings")
	before = len(ps.menu)
	ps.set(
		"menu",
		[row for row in ps.menu if (row.route or "").rstrip("/") != "/artigos"],
	)
	if len(ps.menu) != before:
		ps.save(ignore_permissions=True)
		frappe.db.commit()

	frappe.cache.delete_keys("portal_menu_items")
