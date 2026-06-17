frappe.ui.form.on("Purchase Order", {
	async after_save(frm) {
		if (!frm.doc.supplier || !frm.doc.company) {
			return;
		}

		// const erp_supplier = await frappe.db.get_doc('Supplier', frm.doc.supplier);
		// console.log("after_save", frm.doc.supplier_id_at_pos);

		if (
			frm.doc.supplier_id_at_pos &&
			typeof frm.doc.supplier_id_at_pos === "string" &&
			/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(frm.doc.supplier_id_at_pos)
		) {
			return;
		}

		// console.log("sync_supplier_to_pos", frm.doc.name, frm.doc.supplier, frm.doc.company);

		frappe.call({
			method: "logicposintegration.logicpos_integration.customers.sync_supplier_to_pos",
			args: {
				purchase_order: frm.doc.name,
				supplier: frm.doc.supplier,
				company: frm.doc.company,
			},
			callback(r) {
				const result = r.message;
				if (!result) {
					return;
				}

				if (result.success) {
					if (result.created) {
						frappe.show_alert({
							message: __("Fornecedor sincronizado com o POS"),
							indicator: "green",
						});
					} else {
						console.log("Fornecedor já existe no POS");
					}
					return;
				}

				if (result.message) {
					frappe.msgprint({
						title: __("POS"),
						message: result.message,
						indicator: "orange",
					});
				}
			},
			error(r) {
				frappe.msgprint({
					title: __("POS"),
					message: r?.message || __("Erro ao sincronizar fornecedor com o POS"),
					indicator: "red",
				});
			},
		});
	},
});
