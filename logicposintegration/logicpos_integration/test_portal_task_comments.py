from __future__ import annotations

from typing import Any

import frappe
from frappe.tests.utils import FrappeTestCase

from logicposintegration.utils.portal_comments import (
	get_task_portal_comment_list,
	update_portal_task_comments_context,
)

USER_EMAIL = "portal_task_comments@example.com"
CUSTOMER_NAME = "_Test Portal Task Comments Cust"
PROJECT_PREFIX = "_Test Portal Task Comments Proj"
TASK_PREFIX = "_Test Portal Task Comments"


class TestPortalTaskComments(FrappeTestCase):
	def setUp(self) -> None:
		frappe.set_user("Administrator")
		self._cleanup()
		self.user = self._ensure_user()
		self.customer = self._ensure_customer()
		self.project = self._make_project()
		self.task = self._make_task()

	def tearDown(self) -> None:
		frappe.set_user("Administrator")
		self._cleanup()

	def _cleanup(self) -> None:
		for name in frappe.get_all(
			"Task",
			filters={"subject": ("like", f"{TASK_PREFIX}%")},
			pluck="name",
		):
			for comment in frappe.get_all(
				"Comment",
				filters={"reference_doctype": "Task", "reference_name": name},
				pluck="name",
			):
				frappe.delete_doc("Comment", comment, force=1, ignore_permissions=True)
			frappe.delete_doc("Task", name, force=1, ignore_permissions=True)

		for name in frappe.get_all(
			"Project",
			filters={"project_name": ("like", f"{PROJECT_PREFIX}%")},
			pluck="name",
		):
			frappe.delete_doc("Project", name, force=1, ignore_permissions=True)

		if frappe.db.exists("Customer", CUSTOMER_NAME):
			frappe.delete_doc("Customer", CUSTOMER_NAME, force=1, ignore_permissions=True)

		if frappe.db.exists("User", USER_EMAIL):
			frappe.delete_doc("User", USER_EMAIL, force=1, ignore_permissions=True)

	def _ensure_user(self) -> str:
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": USER_EMAIL,
				"first_name": "Portal",
				"last_name": "Comments",
				"send_welcome_email": 0,
				"user_type": "Website User",
			}
		)
		user.insert(ignore_permissions=True)
		user.add_roles("Customer")
		return USER_EMAIL

	def _ensure_customer(self) -> str:
		doc = frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": CUSTOMER_NAME,
				"customer_type": "Company",
				"territory": "All Territories",
			}
		)
		doc.flags.ignore_mandatory = True
		doc.insert(ignore_permissions=True)
		doc.append("portal_users", {"user": USER_EMAIL})
		doc.flags.ignore_mandatory = True
		doc.save(ignore_permissions=True)
		return doc.name

	def _make_project(self) -> str:
		doc = frappe.get_doc(
			{
				"doctype": "Project",
				"project_name": f"{PROJECT_PREFIX} 1",
				"customer": self.customer,
				"status": "Open",
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name

	def _make_task(self) -> Any:
		doc = frappe.get_doc(
			{
				"doctype": "Task",
				"subject": f"{TASK_PREFIX} 1",
				"status": "Open",
				"project": self.project,
				"exp_start_date": "2026-01-01",
				"exp_end_date": "2026-01-31",
			}
		)
		doc.flags.ignore_mandatory = True
		doc.insert(ignore_permissions=True)
		return doc

	def _add_comment(self, *, owner: str, content: str, published: int) -> str:
		comment = frappe.get_doc(
			{
				"doctype": "Comment",
				"comment_type": "Comment",
				"reference_doctype": "Task",
				"reference_name": self.task.name,
				"content": content,
				"comment_email": owner,
				"comment_by": owner,
				"published": published,
			}
		)
		comment.insert(ignore_permissions=True)
		frappe.db.set_value("Comment", comment.name, "owner", owner, update_modified=False)
		return comment.name

	def test_portal_user_sees_unpublished_desk_comments(self) -> None:
		desk = self._add_comment(owner="Administrator", content="desk note", published=0)
		own = self._add_comment(owner=USER_EMAIL, content="portal note", published=1)

		frappe.set_user(USER_EMAIL)
		names = {row.name for row in get_task_portal_comment_list(self.task.name)}
		self.assertIn(desk, names)
		self.assertIn(own, names)

	def test_guest_gets_empty_list(self) -> None:
		self._add_comment(owner="Administrator", content="desk note", published=0)
		frappe.set_user("Guest")
		self.assertEqual(get_task_portal_comment_list(self.task.name), [])

	def test_update_context_replaces_comment_list(self) -> None:
		desk = self._add_comment(owner="Administrator", content="desk note", published=0)
		frappe.set_user(USER_EMAIL)
		context = frappe._dict(
			{
				"reference_doctype": "Task",
				"reference_name": self.task.name,
				"comment_list": [],
			}
		)
		update_portal_task_comments_context(context)
		names = {row["name"] for row in context.comment_list}
		self.assertIn(desk, names)
