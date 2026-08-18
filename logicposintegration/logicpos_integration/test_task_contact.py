from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from logicposintegration.logicpos_integration.task_contact import get_customer_primary_contact

CUSTOMER_PREFIX = "_Test Task Contact Cust"


class TestTaskCustomerContact(FrappeTestCase):
	def setUp(self) -> None:
		frappe.set_user("Administrator")
		self._cleanup()

	def tearDown(self) -> None:
		frappe.set_user("Administrator")
		self._cleanup()

	def _cleanup(self) -> None:
		for name in frappe.get_all(
			"Customer",
			filters={"customer_name": ("like", f"{CUSTOMER_PREFIX}%")},
			pluck="name",
		):
			for contact in frappe.get_all(
				"Contact",
				filters=[
					["Dynamic Link", "link_doctype", "=", "Customer"],
					["Dynamic Link", "link_name", "=", name],
				],
				pluck="name",
			):
				frappe.delete_doc("Contact", contact, force=1, ignore_permissions=True)
			frappe.delete_doc("Customer", name, force=1, ignore_permissions=True)

	def _make_customer(self, suffix: str) -> str:
		customer_name = f"{CUSTOMER_PREFIX} {suffix}"
		doc = frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": customer_name,
				"customer_type": "Company",
				"territory": "All Territories",
			}
		)
		doc.flags.ignore_mandatory = True
		doc.insert(ignore_permissions=True)
		return doc.name

	def _make_contact(
		self,
		customer: str,
		first_name: str,
		*,
		email: str | None = None,
		phone: str | None = None,
		mobile: str | None = None,
		is_primary: int = 0,
	) -> str:
		payload: dict = {
			"doctype": "Contact",
			"first_name": first_name,
			"is_primary_contact": is_primary,
			"links": [{"link_doctype": "Customer", "link_name": customer}],
		}
		if email:
			payload["email_ids"] = [{"email_id": email, "is_primary": 1}]
		phone_nos: list[dict] = []
		if phone:
			phone_nos.append({"phone": phone, "is_primary_phone": 1})
		if mobile:
			phone_nos.append({"phone": mobile, "is_primary_mobile_no": 1})
		if phone_nos:
			payload["phone_nos"] = phone_nos
		contact = frappe.get_doc(payload)
		contact.insert(ignore_permissions=True)
		return contact.name

	def test_returns_none_when_customer_empty(self) -> None:
		self.assertIsNone(get_customer_primary_contact(""))

	def test_returns_none_when_customer_has_no_contact(self) -> None:
		customer = self._make_customer("Sem Contacto")
		self.assertIsNone(get_customer_primary_contact(customer))

	def test_returns_primary_contact_with_name_phone_and_email(self) -> None:
		customer = self._make_customer("Com Primario")
		self._make_contact(customer, "Outro", email="outro.taskcontact@example.com")
		primary = self._make_contact(
			customer,
			"Ana",
			email="ana.taskcontact@example.com",
			phone="210000001",
			mobile="910000001",
			is_primary=1,
		)
		frappe.db.set_value("Customer", customer, "customer_primary_contact", primary)

		details = get_customer_primary_contact(customer)
		self.assertIsNotNone(details)
		assert details is not None
		self.assertEqual(details["name"], primary)
		self.assertEqual(details["full_name"], "Ana")
		self.assertEqual(details["email"], "ana.taskcontact@example.com")
		self.assertEqual(details["phone"], "210000001")
		self.assertEqual(details["mobile_no"], "910000001")

	def test_falls_back_to_first_contact_when_no_primary(self) -> None:
		customer = self._make_customer("Sem Primario")
		first = self._make_contact(
			customer,
			"Bruno",
			email="bruno.taskcontact@example.com",
			phone="210000002",
		)
		self._make_contact(
			customer,
			"Carla",
			email="carla.taskcontact@example.com",
		)

		details = get_customer_primary_contact(customer)
		self.assertIsNotNone(details)
		assert details is not None
		self.assertEqual(details["name"], first)
		self.assertEqual(details["full_name"], "Bruno")
		self.assertEqual(details["email"], "bruno.taskcontact@example.com")
		self.assertEqual(details["phone"], "210000002")
