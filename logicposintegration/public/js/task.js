frappe.ui.form.on("Task", {
	refresh(frm) {
		frm._lp_prev_status_cached = frm.doc.status;
	},
	before_save(frm) {
		frm._lp_prev_status = frm._lp_prev_status_cached;
	},
	after_save(frm) {
		const prev = frm._lp_prev_status;
		frm._lp_prev_status_cached = frm.doc.status;
		if (
			frm.doc.is_group &&
			frm.doc.status === "Completed" &&
			prev &&
			prev !== "Completed"
		) {
			frappe.logicpos.offer_satisfaction_survey("Task", frm.doc.name);
		}
	},
});
