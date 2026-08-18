from __future__ import annotations

from typing import TypedDict

import frappe


class CustomerContactDetails(TypedDict):
	name: str
	full_name: str | None
	email: str | None
	phone: str | None
	mobile_no: str | None


def _contact_details(contact_name: str) -> CustomerContactDetails | None:
	details = frappe.db.get_value(
		"Contact",
		contact_name,
		["name", "full_name", "email_id", "phone", "mobile_no"],
		as_dict=True,
	)
	if not details:
		return None

	return {
		"name": details.name,
		"full_name": details.full_name,
		"email": details.email_id or None,
		"phone": details.phone or None,
		"mobile_no": details.mobile_no or None,
	}


def _first_linked_contact_name(customer: str) -> str | None:
	contacts: list[str] = frappe.get_all(
		"Contact",
		filters=[
			["Dynamic Link", "link_doctype", "=", "Customer"],
			["Dynamic Link", "link_name", "=", customer],
			["Dynamic Link", "parenttype", "=", "Contact"],
		],
		pluck="name",
		limit=1,
		order_by="is_primary_contact desc, creation asc",
	)
	return contacts[0] if contacts else None


@frappe.whitelist()
def get_customer_primary_contact(customer: str) -> CustomerContactDetails | None:
	"""Contacto primário do cliente, ou o primeiro ligado se não houver primário."""
	if not customer:
		return None

	frappe.get_cached_doc("Customer", customer).check_permission("read")

	primary: str | None = frappe.db.get_value(
		"Customer", customer, "customer_primary_contact"
	)
	if primary:
		details = _contact_details(primary)
		if details:
			return details

	contact_name = _first_linked_contact_name(customer)
	if not contact_name:
		return None

	return _contact_details(contact_name)
