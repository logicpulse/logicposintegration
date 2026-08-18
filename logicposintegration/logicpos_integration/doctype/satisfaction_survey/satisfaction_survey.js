frappe.ui.form.on("Satisfaction Survey", {
	refresh(frm) {
		frm.disable_save();
		frm.set_read_only();
	},
});
