import json

import frappe
from frappe.desk.calendar import get_events


@frappe.whitelist()
def get_task_calendar_events(doctype, start, end, field_map, filters=None, fields=None):
	events = get_events(doctype, start, end, field_map, filters, fields)
	if doctype != "Task" or not events:
		return events

	names = [event["name"] for event in events]
	todo_assignments = frappe.get_all(
		"ToDo",
		filters={
			"reference_type": "Task",
			"reference_name": ["in", names],
			"status": ("not in", ["Cancelled", "Closed"]),
			"allocated_to": ("is", "set"),
		},
		fields=["reference_name", "allocated_to"],
	)

	todo_map: dict[str, list[str]] = {}
	for row in todo_assignments:
		todo_map.setdefault(row.reference_name, []).append(row.allocated_to)

	for event in events:
		assignees: list[str] = []
		if event.get("_assign"):
			try:
				assignees = json.loads(event["_assign"])
			except (json.JSONDecodeError, TypeError):
				assignees = []

		if not assignees:
			assignees = todo_map.get(event["name"], [])

		event["assignees"] = assignees

	return events
