from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.query_builder import Order
from frappe.query_builder.functions import Count
from frappe.utils.user import is_website_user

from erpnext.projects.doctype.task.task import Task


class CustomTask(Task):
	def has_webform_permission(self) -> bool:
		"""Portal: Project User, Portal User do Customer do projeto, ou customer_id."""
		return portal_user_can_access_task(self)

	def validate(self) -> None:
		super().validate()
		_block_portal_task_mutation()

	def before_insert(self) -> None:
		_block_portal_task_mutation()

	def on_trash(self) -> None:
		_block_portal_task_mutation()
		super().on_trash()


def _block_portal_task_mutation() -> None:
	"""Website users may view and comment, but not create/edit/delete Tasks."""
	if frappe.session.user in ("Administrator", "Guest"):
		return
	if not is_website_user():
		return
	frappe.throw(_("Portal users can only view and comment on tasks."), frappe.PermissionError)


def portal_user_customers(user: str | None = None) -> list[str]:
	user = user or frappe.session.user
	if not user or user == "Guest":
		return []
	return frappe.db.get_all(
		"Portal User",
		filters={"user": user, "parenttype": "Customer"},
		pluck="parent",
	)


def _is_portal_user_of_customer(customer: str | None, user: str) -> bool:
	if not customer:
		return False
	return bool(
		frappe.db.exists(
			"Portal User",
			{"parent": customer, "parenttype": "Customer", "user": user},
		)
	)


def portal_user_can_access_task(doc: Any, user: str | None = None) -> bool:
	"""Portal: Project User, Portal User do Customer do projeto, ou customer_id da Task."""
	user = user or frappe.session.user
	if not user or user == "Guest":
		return False
	if user == "Administrator":
		return True

	project = getattr(doc, "project", None) or None
	if project:
		if frappe.db.exists("Project User", {"parent": project, "user": user}):
			return True
		project_customer = frappe.db.get_value("Project", project, "customer")
		if _is_portal_user_of_customer(project_customer, user):
			return True

	customer_id = getattr(doc, "customer_id", None) or None
	return _is_portal_user_of_customer(customer_id, user)


def has_website_permission(doc: Any, ptype: str, user: str, verbose: bool = False) -> bool:
	"""Portal: só leitura (ver detalhes). Escrita/criação/eliminação ficam bloqueadas."""
	if ptype not in ("read", "select"):
		return False
	return portal_user_can_access_task(doc, user)


def get_task_list(
	doctype: str,
	txt: str | None,
	filters: list | dict | None,
	limit_start: int,
	limit_page_length: int = 20,
	order_by: str = "modified desc",
) -> list:
	"""Lista portal de Tasks filtrada por customer_id (Portal User → Customer)."""
	customers = portal_user_customers()

	if is_website_user() and frappe.session.user != "Guest" and not customers:
		return []

	task = frappe.qb.DocType("Task")
	query = frappe.qb.from_(task).select(
		task.name,
		task.subject,
		task.status,
		task.priority,
		task.project,
		task.customer_id,
		task.exp_end_date,
		task.modified,
		task.progress,
	)

	if is_website_user() and frappe.session.user != "Guest":
		query = query.where(task.customer_id.isin(customers))
		if frappe.form_dict.get("without_project"):
			query = query.where((task.project.isnull()) | (task.project == ""))

	if txt:
		like = f"%{txt}%"
		query = query.where((task.name.like(like)) | (task.subject.like(like)))

	query = query.orderby(task.modified, order=Order.desc)
	query = query.limit(limit_page_length).offset(limit_start)

	return query.run(as_dict=True)


def get_list_context(context: Any = None) -> dict:
	return {
		"show_sidebar": True,
		"show_search": True,
		"no_breadcrumbs": True,
		"title": _("Tasks"),
		"get_list": get_task_list,
		"row_template": "templates/includes/portal/portal_task_row.html",
		"list_template": "templates/includes/portal/portal_task_list.html",
	}


def count_orphan_tasks_for_portal_user() -> int:
	customers = portal_user_customers()
	if not customers:
		return 0

	task = frappe.qb.DocType("Task")
	return (
		frappe.qb.from_(task)
		.select(Count(task.name))
		.where(task.customer_id.isin(customers))
		.where((task.project.isnull()) | (task.project == ""))
	).run()[0][0]
