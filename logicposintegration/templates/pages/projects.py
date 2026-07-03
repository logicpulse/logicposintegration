import json

import frappe
from frappe.utils import add_days, formatdate, getdate, today

from erpnext.templates.pages.projects import get_context as erpnext_get_context

from logicposintegration.utils.portal_jinja import PRIORITY_COLORS, STATUS_COLORS

DEFAULT_GANTT_COLOR = "#02A8E5"

GANTT_STATUS_OPTIONS = [
	"Open",
	"Working",
	"Pending Review",
	"Overdue",
	"Completed",
	"Cancelled",
	"Template",
]

GANTT_PRIORITY_OPTIONS = ["Low", "Medium", "High", "Urgent"]


def get_gantt_i18n():
	return {
		"status": frappe._("Status"),
		"priority": frappe._("Priority"),
		"progress": frappe._("Progress"),
		"assignment": frappe._("Assignment"),
		"open_task": frappe._("Open task"),
		"no_tasks_gantt": frappe._("No tasks available for Gantt view"),
		"status_labels": {option: frappe._(option) for option in GANTT_STATUS_OPTIONS},
		"priority_labels": {option: frappe._(option) for option in GANTT_PRIORITY_OPTIONS},
	}


def get_context(context):
	erpnext_get_context(context)
	context.doc.tasks = get_portal_tasks(
		context.doc.name,
		search=frappe.form_dict.get("search"),
	)
	context.status_colors = STATUS_COLORS
	context.priority_colors = PRIORITY_COLORS
	context.gantt_tasks = json.dumps(get_gantt_tasks(context.doc.name))
	context.gantt_i18n = json.dumps(get_gantt_i18n(), default=str)
	context.kanban_columns = get_kanban_columns(context.doc.name)
	return context


def get_portal_tasks(project, start=0, search=None, item_status=None):
	filters = {"project": project}
	if search:
		filters["subject"] = ("like", f"%{search}%")

	tasks = frappe.get_all(
		"Task",
		filters=filters,
		fields=[
			"name",
			"subject",
			"status",
			"priority",
			"modified",
			"_assign",
			"exp_end_date",
			"is_group",
			"parent_task",
		],
		limit_start=start,
		limit_page_length=100,
	)

	for task in tasks:
		if task.is_group:
			child_tasks = list(filter(lambda x: x.parent_task == task.name, tasks))
			if child_tasks:
				task.children = child_tasks

	return list(filter(lambda x: not x.parent_task, tasks))


def get_kanban_columns(project):
	statuses = [
		"Open",
		"Working",
		"Pending Review",
		"Overdue",
		"Completed",
	]

	tasks = frappe.get_all(
		"Task",
		filters={"project": project, "status": ("in", statuses)},
		fields=["name", "subject", "status", "exp_end_date", "progress", "priority", "color"],
		order_by="modified desc",
		limit=500,
	)

	columns = []
	for status in statuses:
		columns.append(
			{
				"status": status,
				"label": frappe._(status),
				"tasks": [task for task in tasks if task.status == status],
			}
		)

	return columns


def get_task_assignees(task):
	assignees = []
	if not task.get("_assign"):
		return assignees

	for user in json.loads(task._assign):
		details = frappe.db.get_value("User", user, ["full_name", "user_image"], as_dict=True)
		full_name = (details.full_name if details else None) or user
		assignees.append(
			{
				"user": user,
				"full_name": full_name,
				"user_image": details.user_image if details else None,
				"abbr": frappe.utils.get_abbr(full_name),
			}
		)

	return assignees


def get_gantt_color(color):
	if color and isinstance(color, str) and color.startswith("#") and len(color) >= 4:
		return color
	return DEFAULT_GANTT_COLOR


def get_gantt_tasks(project):
	project_doc = frappe.get_doc("Project", project)
	default_start = project_doc.expected_start_date or project_doc.actual_start_date or today()
	default_end = project_doc.expected_end_date or project_doc.actual_end_date or add_days(default_start, 7)

	tasks = frappe.get_all(
		"Task",
		filters={"project": project, "status": ("!=", "Cancelled")},
		fields=[
			"name",
			"subject",
			"status",
			"priority",
			"color",
			"exp_start_date",
			"exp_end_date",
			"progress",
			"depends_on_tasks",
			"_assign",
		],
		order_by="exp_start_date asc, creation asc",
		limit=500,
	)

	gantt_tasks = []
	for task in tasks:
		start = task.exp_start_date or default_start
		end = task.exp_end_date or default_end
		if end < start:
			end = add_days(start, 1)

		color = get_gantt_color(task.color)
		assignees = get_task_assignees(task)

		gantt_tasks.append(
			{
				"id": task.name,
				"name": task.subject or task.name,
				"start": formatdate(getdate(start), "yyyy-mm-dd"),
				"end": formatdate(getdate(end), "yyyy-mm-dd"),
				"progress": task.progress or 0,
				"dependencies": task.depends_on_tasks or "",
				"color": color,
				"custom_class": f"color-{color.lstrip('#')}",
				"status": task.status,
				"priority": task.priority or "",
				"assignees": assignees,
			}
		)

	return gantt_tasks
