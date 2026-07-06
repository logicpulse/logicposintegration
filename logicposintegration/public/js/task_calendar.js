function ensure_task_calendar_styles() {
	if ($("#task-calendar-avatar-style").length) {
		return;
	}

	frappe.dom.set_style(
		`
		.fc-event .task-calendar-event {
			display: flex;
			flex-direction: row;
			align-items: center;
			width: 100%;
			min-width: 0;
			overflow: hidden;
			gap: 4px;
		}
		.fc-event .task-calendar-event .fc-event-title {
			flex: 1 1 auto;
			min-width: 0;
			overflow: hidden;
			text-overflow: ellipsis;
			white-space: nowrap;
			text-align: left;
		}
		.fc-event .task-calendar-avatars {
			flex: 0 0 auto;
			display: inline-flex;
			align-items: center;
			margin-left: auto;
		}
		.fc-event .task-calendar-avatars .avatar-group {
			margin-left: 0;
		}
		.fc-event .task-calendar-avatars .avatar {
			width: 16px;
			height: 16px;
		}
		.fc-event .task-calendar-avatars .avatar-frame {
			width: 16px;
			height: 16px;
			font-size: 9px;
			line-height: 16px;
		}
	`,
		"task-calendar-avatar-style"
	);
}

function get_task_assignees(event) {
	const props = event.extendedProps || {};
	if (props.assignees?.length) {
		return props.assignees;
	}

	const assign = props._assign;
	if (!assign) {
		return [];
	}

	try {
		return JSON.parse(assign);
	} catch (e) {
		return [];
	}
}

function escape_attr(value) {
	return frappe.utils.escape_html(value || "").replace(/"/g, "&quot;");
}

function build_task_event_content(arg) {
	ensure_task_calendar_styles();

	const raw_title = arg.event.title || "";
	const title = frappe.utils.escape_html(raw_title);
	const title_attr = escape_attr(raw_title);
	const assignees = get_task_assignees(arg.event);

	let avatars_html = "";
	if (assignees.length) {
		avatars_html = frappe
			.avatar_group(assignees, 3, { overlap: true, css_class: "avatar-xs" })
			.prop("outerHTML");
	}

	return {
		html: `
			<div class="fc-event-main-frame task-calendar-event">
				<div class="fc-event-title fc-sticky" title="${title_attr}">${title}</div>
				${
					avatars_html
						? `<div class="task-calendar-avatars">${avatars_html}</div>`
						: ""
				}
			</div>
		`,
	};
}

$.extend(frappe.views.calendar["Task"], {
	fields: ["exp_start_date", "exp_end_date", "subject", "name", "_assign"],
	get_events_method: "logicposintegration.utils.task_calendar.get_task_calendar_events",
	options: {
		eventContent(arg) {
			return build_task_event_content(arg);
		},
	},
});
