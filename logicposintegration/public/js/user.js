frappe.ui.form.on("User", {
	test_connection(frm) {
		if (frm.is_new()) {
			frappe.msgprint(__("Guarde o utilizador antes de testar a conexão."));
			return;
		}

		if (frm.is_dirty()) {
			frappe.msgprint(__("Guarde as alterações (Email / Pin) antes de testar a conexão."));
			return;
		}

		frappe.call({
			method: "logicposintegration.logicpos_integration.utils.login_to_pos",
			args: {
				user: frm.doc.name,
				force: 1,
			},
			freeze: true,
			freeze_message: __("A testar conexão com o POS..."),
			callback(r) {
				if (r.message?.success) {
					frappe.show_alert({
						message: r.message.message,
						indicator: "green",
					});
				}else{
					frappe.msgprint(r.message.message);
				}
			},
		});
	},
});
