from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from logicposintegration.templates.pages.projects import portal_user_can_access_project

USER_EMAIL = "portal_project_access@example.com"
CUSTOMER_NAME = "_Test Portal Project Access Cust"
OTHER_CUSTOMER_NAME = "_Test Portal Project Access Other"
PROJECT_PREFIX = "_Test Portal Project Access"


class TestPortalProjectAccess(FrappeTestCase):
	def setUp(self) -> None:
		frappe.set_user("Administrator")
		self._cleanup()
		self.user = self._ensure_user()
		self.customer = self._ensure_customer(CUSTOMER_NAME, with_portal_user=True)
		self.other_customer = self._ensure_customer(OTHER_CUSTOMER_NAME, with_portal_user=False)

	def tearDown(self) -> None:
		frappe.set_user("Administrator")
		self._cleanup()

	def _cleanup(self) -> None:
		for name in frappe.get_all(
			"Project",
			filters={"project_name": ("like", f"{PROJECT_PREFIX}%")},
			pluck="name",
		):
			frappe.delete_doc("Project", name, force=1, ignore_permissions=True)

		for customer_name in (CUSTOMER_NAME, OTHER_CUSTOMER_NAME):
			if frappe.db.exists("Customer", customer_name):
				frappe.delete_doc("Customer", customer_name, force=1, ignore_permissions=True)

		if frappe.db.exists("User", USER_EMAIL):
			frappe.delete_doc("User", USER_EMAIL, force=1, ignore_permissions=True)

	def _ensure_user(self) -> str:
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": USER_EMAIL,
				"first_name": "Portal",
				"last_name": "Project Access",
				"send_welcome_email": 0,
				"user_type": "Website User",
			}
		)
		user.insert(ignore_permissions=True)
		user.add_roles("Customer")
		return USER_EMAIL

	def _ensure_customer(self, customer_name: str, *, with_portal_user: bool) -> str:
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
		if with_portal_user:
			doc.append("portal_users", {"user": USER_EMAIL})
			doc.flags.ignore_mandatory = True
			doc.save(ignore_permissions=True)
		return doc.name

	def _make_project(self, suffix: str, customer: str, *, add_project_user: bool = False) -> str:
		doc = frappe.get_doc(
			{
				"doctype": "Project",
				"project_name": f"{PROJECT_PREFIX} {suffix}",
				"customer": customer,
				"status": "Open",
			}
		)
		if add_project_user:
			doc.append("users", {"user": USER_EMAIL})
		doc.insert(ignore_permissions=True)
		return doc.name

	def test_denies_guest(self) -> None:
		project = self._make_project("Guest", self.customer)
		self.assertFalse(portal_user_can_access_project(project, "Guest"))

	def test_allows_project_user(self) -> None:
		project = self._make_project("ProjectUser", self.other_customer, add_project_user=True)
		self.assertTrue(portal_user_can_access_project(project, USER_EMAIL))

	def test_allows_portal_user_of_customer(self) -> None:
		project = self._make_project("PortalUser", self.customer)
		self.assertTrue(portal_user_can_access_project(project, USER_EMAIL))

	def test_denies_unrelated_customer_project(self) -> None:
		project = self._make_project("OtherCust", self.other_customer)
		self.assertFalse(portal_user_can_access_project(project, USER_EMAIL))
