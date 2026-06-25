frappe.ui.form.on("Purchase Order", { 
	supplier(frm) {
		sync_supplier_to_pos(frm);
	},
	refresh(frm) {
		if (frm.doc.docstatus === 1 && frm.doc.status !== "Closed") {
			frm.add_custom_button(__("Actualizar Stock"), () => {
				update_stock(frm);
			});
		}
	},
});

/**
 * Verifica se o ID do fornecedor no POS é válido
 * @param {string} supplier_id_at_pos - ID do fornecedor no POS
 * @returns {boolean} - true se o ID é válido, false caso contrário
 */
function is_valid_supplier_id_at_pos(supplier_id_at_pos) {
	return supplier_id_at_pos &&
		typeof supplier_id_at_pos === "string" &&
		/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(supplier_id_at_pos)
}

function sync_supplier_to_pos(frm) {
	frappe.call({
		method: "logicposintegration.logicpos_integration.customers.sync_supplier_to_pos",
		args: { 
			supplier: frm.doc.supplier,
			company: frm.doc.company,
		},
		freeze: true,
		freeze_message: __("A sincronizar fornecedor com o POS"),
		callback(r) {
			const result = r.message;
			if (!result) {
				return;
			}

			if (result.success) {
				frm.doc.supplier_id_at_pos = result.pos_id;
				frm.refresh_field('supplier_id_at_pos'); 

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
}

function update_stock(frm) {
	if (frm.doc.status === "Closed") {
		frappe.msgprint({
			title: __("POS"),
			message: __("O stock desta encomenda já foi actualizado no POS"),
			indicator: "orange",
		});
		return;
	}

	if (!is_valid_supplier_id_at_pos(frm.doc.supplier_id_at_pos)) {
		frappe.msgprint({
			title: __("POS"),
			message: __("Fornecedor não sincronizado com o POS"),
			indicator: "orange",
		});
		return;
	}

	frappe.call({
		method: "logicposintegration.logicpos_integration.articles.update_stock",
		args: {
			purchase_order: frm.doc.name,
			supplier_id: frm.doc.supplier_id_at_pos,
			company: frm.doc.company,
			date: frm.doc.transaction_date,
			document_number: frm.doc.name,
			external_document: frm.doc.bill_no || null,
			items: frm.doc.items.map((item) => ({
				item_code: item.item_code,
				qty: item.qty,
				rate: item.rate,
			})),
		},
		freeze: true,
		freeze_message: __("A actualizar stock no POS"),
		callback(r) {
			const result = r.message;
			if (result?.success) {
				frappe.show_alert({
					message: __("Stock actualizado no POS"),
					indicator: "green",
				});
				frm.reload_doc();
			}
		},
		error(r) {
			frappe.msgprint({
				title: __("POS"),
				message: r?.message || __("Erro ao actualizar stock no POS"),
				indicator: "red",
			});
		},
	});
}