from __future__ import annotations

from typing import Any

import frappe
from frappe.tests.utils import FrappeTestCase

from logicposintegration.overrides.task import (
	has_website_permission,
	portal_user_can_access_task,
)

USER_EMAIL = "portal_task_access@example.com"
CUSTOMER_NAME = "_Test Portal Task Access Cust"
OTHER_CUSTOMER_NAME = "_Test Portal Task Access Other"
PROJECT_PREFIX = "_Test Portal Task Access Proj"
TASK_PREFIX = "_Test Portal Task Access"


class TestPortalTaskAccess(FrappeTestCase):
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
			"Task",
			filters={"subject": ("like", f"{TASK_PREFIX}%")},
			pluck="name",
		):
			frappe.delete_doc("Task", name, force=1, ignore_permissions=True)

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
				"last_name": "Task Access",
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

	def _make_task(
		self,
		suffix: str,
		*,
		project: str | None = None,
		customer_id: str | None = None,
	) -> Any:
		payload: dict[str, Any] = {
			"doctype": "Task",
			"subject": f"{TASK_PREFIX} {suffix}",
			"status": "Open",
			"exp_start_date": "2026-01-01",
			"exp_end_date": "2026-01-31",
		}
		if project:
			payload["project"] = project
		if customer_id:
			payload["customer_id"] = customer_id
		doc = frappe.get_doc(payload)
		doc.flags.ignore_mandatory = True
		doc.insert(ignore_permissions=True)
		return doc

	def test_allows_via_project_customer_portal_user_without_task_customer_id(self) -> None:
		project = self._make_project("ViaProjectCust", self.customer)
		task = self._make_task("NoCustomerId", project=project)
		self.assertFalse(task.customer_id)
		self.assertTrue(portal_user_can_access_task(task, USER_EMAIL))

	def test_allows_via_task_customer_id(self) -> None:
		task = self._make_task("Orphan", customer_id=self.customer)
		self.assertTrue(portal_user_can_access_task(task, USER_EMAIL))

	def test_allows_via_project_user(self) -> None:
		project = self._make_project("ViaProjectUser", self.other_customer, add_project_user=True)
		task = self._make_task("ProjectUser", project=project)
		self.assertTrue(portal_user_can_access_task(task, USER_EMAIL))

	def test_denies_unrelated_project_task(self) -> None:
		project = self._make_project("Other", self.other_customer)
		task = self._make_task("Denied", project=project)
		self.assertFalse(portal_user_can_access_task(task, USER_EMAIL))

	def test_has_website_permission_read_via_project_customer(self) -> None:
		project = self._make_project("WebsitePerm", self.customer)
		task = self._make_task("WebsitePerm", project=project)
		frappe.set_user(USER_EMAIL)
		self.assertTrue(has_website_permission(task, "read", USER_EMAIL))
