frappe.ui.form.on("Project", {
	refresh(frm) {
		frm._lp_prev_status_cached = frm.doc.status;
	},
	before_save(frm) {
		frm._lp_prev_status = frm._lp_prev_status_cached;
	},
	after_save(frm) {
		const prev = frm._lp_prev_status;
		frm._lp_prev_status_cached = frm.doc.status;
		if (frm.doc.status === "Completed" && prev && prev !== "Completed") {
			frappe.logicpos.offer_satisfaction_survey("Project", frm.doc.name);
		}
	},
	// ERPNext "Actions → Set Project Status" chama frm.events.set_status (não after_save).
	// Substituímos o handler para oferecer o inquérito após concluir.
	set_status(frm, status) {
		frappe.confirm(
			__("Set Project and all Tasks to status {0}?", [__(status).bold()]),
			() => {
				frappe
					.xcall("erpnext.projects.doctype.project.project.set_project_status", {
						project: frm.doc.name,
						status: status,
					})
					.then(() => frm.reload_doc())
					.then(() => {
						if (status === "Completed") {
							frappe.logicpos.offer_satisfaction_survey("Project", frm.doc.name);
						}
					});
			}
		);
	},
});
