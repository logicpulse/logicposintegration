(() => {
	const STATUS_COLORS = {
		Open: "orange",
		Working: "blue",
		"Pending Review": "yellow",
		Overdue: "red",
		Completed: "green",
		Cancelled: "grey",
		Template: "purple",
	};

	const PRIORITY_COLORS = {
		Low: "grey",
		Medium: "blue",
		High: "orange",
		Urgent: "red",
	};

	function format_gantt_date(value) {
		if (!value) {
			return "";
		}

		let date_str;
		if (typeof value === "string") {
			date_str = value.split(" ")[0];
		} else if (value instanceof Date) {
			date_str = moment(value).format("YYYY-MM-DD");
		} else {
			try {
				date_str = moment(value).format("YYYY-MM-DD");
			} catch (e) {
				return String(value);
			}
		}

		if (frappe.datetime && frappe.datetime.str_to_user) {
			return frappe.datetime.str_to_user(date_str, false, true);
		}

		return date_str;
	}

	function build_status_pill(status) {
		if (!status) {
			return '<span class="text-muted">—</span>';
		}
		const color_key = STATUS_COLORS[status] || "grey";
		return (
			`<span class="portal-status-pill portal-status-${color_key}">` +
			frappe.utils.escape_html(__(status)) +
			"</span>"
		);
	}

	function build_priority_pill(priority) {
		if (!priority) {
			return '<span class="text-muted">—</span>';
		}
		const color_key = PRIORITY_COLORS[priority] || "grey";
		return (
			`<span class="portal-priority-pill portal-priority-${color_key}">` +
			frappe.utils.escape_html(__(priority)) +
			"</span>"
		);
	}

	function build_assignee_avatars(assign_json) {
		if (!assign_json) {
			return '<span class="text-muted">—</span>';
		}

		let assign_list = [];
		try {
			assign_list = typeof assign_json === "string" ? JSON.parse(assign_json) : assign_json;
		} catch (e) {
			return '<span class="text-muted">—</span>';
		}

		if (!assign_list || !assign_list.length) {
			return '<span class="text-muted">—</span>';
		}

		return (
			'<div class="portal-gantt-popup-assignees">' +
			assign_list
				.map((user) => {
					const info = frappe.user_info(user);
					const title = frappe.utils.escape_html(info.fullname || user);
					if (info.image) {
						return (
							`<span class="avatar avatar-small portal-avatar" title="${title}">` +
							`<span class="avatar-frame" style="background-image: url('${frappe.utils.escape_html(
								info.image
							)}')"></span></span>`
						);
					}
					const abbr = frappe.utils.escape_html(
						(info.abbr || frappe.get_abbr(info.fullname || user)).slice(0, 2).toUpperCase()
					);
					return (
						`<span class="avatar avatar-small portal-avatar" title="${title}">` +
						`<div class="standard-image">${abbr}</div></span>`
					);
				})
				.join("") +
			"</div>"
		);
	}

	function style_gantt_popup() {
		const popup = document.querySelector(".gantt-modern .popup-wrapper, .gantt-container .popup-wrapper");
		if (!popup) {
			return;
		}

		popup.style.setProperty("background", "#fff", "important");
		popup.style.setProperty("color", "#0f172a", "important");
		popup.style.setProperty("border", "1px solid #e2e8f0", "important");
		popup.style.setProperty("border-radius", "12px", "important");
		popup.style.setProperty("box-shadow", "0 12px 32px rgba(15, 23, 42, 0.12)", "important");
		popup.style.setProperty("padding", "0", "important");

		const pointer = popup.querySelector(".pointer");
		if (pointer) {
			pointer.style.display = "none";
		}
	}

	frappe.listview_settings["Task"] = frappe.listview_settings["Task"] || {};

	frappe.listview_settings["Task"].gantt_custom_popup_html = function (ganttobj, task) {
		const title = task.subject || ganttobj.name || ganttobj.id;
		const progress = ganttobj.progress != null ? ganttobj.progress + "%" : "—";
		const task_url = "/app/task/" + encodeURIComponent(ganttobj.id);

		setTimeout(style_gantt_popup, 0);

		return (
			'<div class="portal-gantt-popup">' +
			'<div class="portal-gantt-popup-header">' +
			'<div class="portal-gantt-popup-title">' +
			frappe.utils.escape_html(title) +
			"</div>" +
			'<div class="portal-gantt-popup-dates">' +
			frappe.utils.escape_html(format_gantt_date(ganttobj._start)) +
			" → " +
			frappe.utils.escape_html(format_gantt_date(ganttobj._end)) +
			"</div></div>" +
			'<div class="portal-gantt-popup-body">' +
			'<div class="portal-gantt-popup-row"><span class="portal-gantt-popup-label">' +
			__("Status") +
			'</span><span class="portal-gantt-popup-value">' +
			build_status_pill(task.status) +
			"</span></div>" +
			'<div class="portal-gantt-popup-row"><span class="portal-gantt-popup-label">' +
			__("Priority") +
			'</span><span class="portal-gantt-popup-value">' +
			build_priority_pill(task.priority) +
			"</span></div>" +
			'<div class="portal-gantt-popup-row"><span class="portal-gantt-popup-label">' +
			__("Progress") +
			'</span><span class="portal-gantt-popup-value">' +
			frappe.utils.escape_html(String(progress)) +
			"</span></div>" +
			'<div class="portal-gantt-popup-row"><span class="portal-gantt-popup-label">' +
			__("Assignment") +
			'</span><span class="portal-gantt-popup-value">' +
			build_assignee_avatars(task._assign) +
			"</span></div></div>" +
			'<div class="portal-gantt-popup-actions">' +
			'<a href="' +
			task_url +
			'">' +
			__("Open task") +
			" →</a>" +
			"</div></div>"
		);
	};
})();
