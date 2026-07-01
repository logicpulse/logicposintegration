frappe.ready(function () {
	var STATUS_COLORS = {
		Open: "orange",
		Working: "blue",
		"Pending Review": "yellow",
		Overdue: "red",
		Completed: "green",
		Cancelled: "grey",
		Template: "purple",
	};

	var PRIORITY_COLORS = {
		Low: "grey",
		Medium: "blue",
		High: "orange",
		Urgent: "red",
	};

	var gantt_tasks = [];
	var gantt_task_map = {};

	try {
		gantt_tasks = JSON.parse(document.getElementById("project-gantt-data").textContent || "[]");
		gantt_tasks.forEach(function (task) {
			gantt_task_map[String(task.id)] = task;
		});
	} catch (e) {
		gantt_tasks = [];
	}

	var project_gantt = null;
	var views = {
		list: "#tasks-list-view",
		gantt: "#tasks-gantt-view",
		kanban: "#tasks-kanban-view",
	};

	function show_view(view) {
		Object.keys(views).forEach(function (key) {
			$(views[key]).hide();
		});

		if (view === "gantt") {
			$(views.gantt).show();
			render_gantt();
		} else if (view === "kanban") {
			$(views.kanban).show();
		} else {
			$(views.list).show();
		}
	}

	$(".project-tasks-view-tab").on("click", function (e) {
		e.preventDefault();
		var view = $(this).data("view");
		$(".project-tasks-view-tab").removeClass("active");
		$(this).addClass("active");
		show_view(view);
	});

	$(".project-kanban-card").on("click", function () {
		var task = $(this).data("task");
		if (task) {
			window.location.href = "/tasks/" + encodeURIComponent(task);
		}
	});

	$(".portal-gantt-mode-btn").on("click", function () {
		var mode = $(this).data("mode");
		$(".portal-gantt-mode-btn").removeClass("active");
		$(this).addClass("active");
		if (project_gantt) {
			project_gantt.change_view_mode(mode);
		}
	});

	function get_task_meta(task) {
		var mapped = gantt_task_map[String(task.id)] || {};
		return {
			status: mapped.status || task.status || "",
			priority: mapped.priority || task.priority || "",
			progress: mapped.progress != null ? mapped.progress : task.progress,
			assignees: mapped.assignees || task.assignees || [],
		};
	}

	function build_status_pill(status) {
		if (!status) {
			return '<span class="text-muted">—</span>';
		}
		var color_key = STATUS_COLORS[status] || "grey";
		return (
			'<span class="portal-status-pill portal-status-' +
			color_key +
			'">' +
			frappe.utils.escape_html(__(status)) +
			"</span>"
		);
	}

	function build_priority_pill(priority) {
		if (!priority) {
			return '<span class="text-muted">—</span>';
		}
		var color_key = PRIORITY_COLORS[priority] || "grey";
		return (
			'<span class="portal-priority-pill portal-priority-' +
			color_key +
			'">' +
			frappe.utils.escape_html(__(priority)) +
			"</span>"
		);
	}

	function build_assignee_avatars(assignees) {
		if (!assignees || !assignees.length) {
			return '<span class="text-muted">—</span>';
		}

		return (
			'<div class="portal-gantt-popup-assignees">' +
			assignees
				.map(function (assignee) {
					var name = assignee.full_name || assignee;
					var title = frappe.utils.escape_html(name);
					if (typeof assignee === "string") {
						return (
							'<span class="avatar avatar-small portal-avatar" title="' +
							title +
							'"><div class="standard-image">' +
							frappe.utils.escape_html(name.slice(0, 2).toUpperCase()) +
							"</div></span>"
						);
					}
					if (assignee.user_image) {
						return (
							'<span class="avatar avatar-small portal-avatar" title="' +
							title +
							'"><img src="' +
							frappe.utils.escape_html(assignee.user_image) +
							'" alt=""></span>'
						);
					}
					return (
						'<span class="avatar avatar-small portal-avatar" title="' +
						title +
						'"><div class="standard-image">' +
						frappe.utils.escape_html(assignee.abbr || name.slice(0, 2).toUpperCase()) +
						"</div></span>"
					);
				})
				.join("") +
			"</div>"
		);
	}

	function build_gantt_popup(task) {
		var meta = get_task_meta(task);
		var progress = meta.progress != null ? meta.progress + "%" : "—";
		var task_url = "/tasks/" + encodeURIComponent(task.id);

		return (
			'<div class="portal-gantt-popup">' +
			'<div class="portal-gantt-popup-title">' +
			frappe.utils.escape_html(task.name) +
			"</div>" +
			'<div class="portal-gantt-popup-dates">' +
			frappe.utils.escape_html(format_gantt_date(task._start)) +
			" → " +
			frappe.utils.escape_html(format_gantt_date(task._end)) +
			"</div>" +
			'<div class="portal-gantt-popup-row"><span class="portal-gantt-popup-label">' +
			__("Status") +
			'</span><span class="portal-gantt-popup-value">' +
			build_status_pill(meta.status) +
			"</span></div>" +
			'<div class="portal-gantt-popup-row"><span class="portal-gantt-popup-label">' +
			__("Priority") +
			'</span><span class="portal-gantt-popup-value">' +
			build_priority_pill(meta.priority) +
			"</span></div>" +
			'<div class="portal-gantt-popup-row"><span class="portal-gantt-popup-label">' +
			__("Progress") +
			'</span><span class="portal-gantt-popup-value">' +
			frappe.utils.escape_html(String(progress)) +
			"</span></div>" +
			'<div class="portal-gantt-popup-row"><span class="portal-gantt-popup-label">' +
			__("Assignment") +
			'</span><span class="portal-gantt-popup-value">' +
			build_assignee_avatars(meta.assignees) +
			"</span></div>" +
			'<div class="portal-gantt-popup-actions">' +
			'<a href="' +
			task_url +
			'">' +
			__("Open task") +
			" →</a>" +
			"</div></div>"
		);
	}

	function render_gantt() {
		if (project_gantt) {
			return;
		}

		if (!gantt_tasks.length) {
			$("#project-gantt").html(
				'<p class="text-muted text-center py-5">' +
					(__("No tasks available for Gantt view") || "No tasks available for Gantt view") +
					"</p>"
			);
			return;
		}

		load_gantt_lib(function () {
			project_gantt = new Gantt("#project-gantt", gantt_tasks, {
				bar_height: 32,
				bar_corner_radius: 4,
				view_mode: "Week",
				on_click: function () {
					/* popup handled by custom_popup_html */
				},
				custom_popup_html: function (task) {
					return build_gantt_popup(task);
				},
			});
			apply_gantt_colors(gantt_tasks);
		});
	}

	function apply_gantt_colors(tasks) {
		var styles = tasks
			.filter(function (t) {
				return t.custom_class && t.color;
			})
			.map(function (t) {
				var class_name = t.custom_class;
				var bar_color = t.color;
				var progress_color = darken_color(bar_color, 0.25);
				return (
					".gantt .bar-wrapper." +
					class_name +
					" .bar { fill: " +
					bar_color +
					"; }" +
					".gantt .bar-wrapper." +
					class_name +
					" .bar-progress { fill: " +
					progress_color +
					"; }"
				);
			})
			.join("");

		if (styles) {
			$("#project-gantt-colors").remove();
			$('<style id="project-gantt-colors">' + styles + "</style>").prependTo("#tasks-gantt-view");
		}
	}

	function format_gantt_date(value) {
		if (!value) {
			return "";
		}
		if (typeof value === "string") {
			return value.split(" ")[0];
		}
		try {
			return value.toISOString().slice(0, 10);
		} catch (e) {
			return String(value);
		}
	}

	function darken_color(hex, amount) {
		if (!hex || hex.charAt(0) !== "#") {
			return "#0271a8";
		}
		var num = parseInt(hex.slice(1), 16);
		var r = Math.max(0, ((num >> 16) & 0xff) * (1 - amount));
		var g = Math.max(0, ((num >> 8) & 0xff) * (1 - amount));
		var b = Math.max(0, (num & 0xff) * (1 - amount));
		return (
			"#" +
			((1 << 24) + (Math.round(r) << 16) + (Math.round(g) << 8) + Math.round(b))
				.toString(16)
				.slice(1)
		);
	}

	function load_gantt_lib(callback) {
		if (window.Gantt) {
			callback();
			return;
		}

		var script = document.createElement("script");
		script.src = "/assets/frappe/node_modules/frappe-gantt/dist/frappe-gantt.min.js";
		script.onload = callback;
		document.head.appendChild(script);
	}

	$(".file-size").each(function () {
		$(this).text(frappe.form.formatters.FileSize($(this).text()));
	});
});
