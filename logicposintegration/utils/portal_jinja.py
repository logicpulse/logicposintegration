STATUS_COLORS = {
	"Open": "orange",
	"Working": "blue",
	"Pending Review": "yellow",
	"Overdue": "red",
	"Completed": "green",
	"Cancelled": "grey",
	"Template": "purple",
}

PRIORITY_COLORS = {
	"Low": "grey",
	"Medium": "blue",
	"High": "orange",
	"Urgent": "red",
}


def get_portal_status_colors():
	return STATUS_COLORS


def get_portal_priority_colors():
	return PRIORITY_COLORS


def update_portal_project_context(context):
	if context.get("route") != "projects" and context.get("path") != "projects":
		return

	context.status_colors = STATUS_COLORS
	context.priority_colors = PRIORITY_COLORS
