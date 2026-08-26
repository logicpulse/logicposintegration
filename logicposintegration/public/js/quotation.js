frappe.provide("logicposintegration.quotation");

const COMPANY_PARTY_CURRENCY = {
	"Logicpulse PT": "EUR",
	"Logicpulse AO": "AOA",
};

logicposintegration.quotation.set_party_name_query = function (frm) {
	if (frm.doc.quotation_to !== "Customer") {
		return;
	}

	const currency = COMPANY_PARTY_CURRENCY[frm.doc.company];
	if (!currency) {
		frm.set_query("party_name");
		return;
	}

	frm.set_query("party_name", () => ({
		filters: { default_currency: currency },
	}));
};

logicposintegration.quotation.validate_party_currency = function (frm) {
	if (frm.doc.quotation_to !== "Customer" || !frm.doc.party_name) {
		return;
	}

	const expected = COMPANY_PARTY_CURRENCY[frm.doc.company];
	if (!expected) {
		return;
	}

	frappe.db.get_value("Customer", frm.doc.party_name, "default_currency", (r) => {
		const customer_currency = r?.message?.default_currency;
		if (customer_currency && customer_currency !== expected) {
			frm.set_value("party_name", "");
			frm.set_value("customer_name", "");
		}
	});
};

logicposintegration.quotation.parse_proposal_version = function (version) {
	if (version == null || String(version).trim() === "") {
		return null;
	}

	let s = String(version).trim().replace(/\s/g, "");
	if (s.includes(",") && s.includes(".")) {
		return null;
	}

	s = s.replace(",", ".");
	const v = parseFloat(s);
	return isNaN(v) ? null : v;
};

logicposintegration.quotation.validate_proposal_version = function (version) {
	const v = logicposintegration.quotation.parse_proposal_version(version);
	if (v == null || v < 1.0 || v > 10.9) {
		frappe.msgprint(__('A versão deve estar entre 1,0 e 10,9.'));
		return false;
	}
	return true;
};

logicposintegration.quotation.get_update_item_discount_fields = function () {
	const child_meta = frappe.get_meta("Quotation Item");
	const get_precision = (fieldname) =>
		child_meta.fields.find((field) => field.fieldname === fieldname)?.precision;

	return {
		discount_percentage: {
			fieldtype: "Percent",
			fieldname: "discount_percentage",
			label: __("Discount (%)"),
			in_list_view: 1,
			columns: 1,
			default: 0,
			precision: get_precision("discount_percentage"),
			onchange() {
				const grid =
					this.grid || this.layout?.grid || cur_dialog?.fields_dict?.trans_items?.grid;
				logicposintegration.quotation.apply_discount_to_update_row(this.doc, grid);
			},
		},
		hidden: [
			{ fieldtype: "Currency", fieldname: "price_list_rate", hidden: 1 },
			{ fieldtype: "Currency", fieldname: "rate_with_margin", hidden: 1 },
			{ fieldtype: "Currency", fieldname: "discount_amount", hidden: 1 },
		],
	};
};

logicposintegration.quotation.apply_discount_to_update_row = function (row, grid) {
	if (!row) {
		return;
	}
	const base = flt(row.rate_with_margin) || flt(row.price_list_rate);
	const percent = flt(row.discount_percentage);
	if (base) {
		row.discount_amount = flt((base * percent) / 100);
		row.rate = flt(base * (1 - percent / 100));
	}
	grid?.refresh();
};

logicposintegration.quotation.populate_discount_on_rows = function (rows, frm) {
	const items_by_name = Object.fromEntries((frm.doc.items || []).map((item) => [item.name, item]));
	(rows || []).forEach((row) => {
		const item = items_by_name[row.docname];
		if (!item) {
			return;
		}
		row.discount_percentage = item.discount_percentage;
		row.discount_amount = item.discount_amount;
		row.price_list_rate = item.price_list_rate;
		row.rate_with_margin = item.rate_with_margin;
	});
};

logicposintegration.quotation.inject_discount_fields = function (dialog_opts, frm) {
	const table = (dialog_opts.fields || []).find((field) => field.fieldname === "trans_items");
	if (!table?.fields || table.fields.some((field) => field.fieldname === "discount_percentage")) {
		return;
	}

	const defs = logicposintegration.quotation.get_update_item_discount_fields();
	const rate_idx = table.fields.findIndex((field) => field.fieldname === "rate");
	const insert_at = rate_idx >= 0 ? rate_idx + 1 : table.fields.length;
	table.fields.splice(insert_at, 0, defs.discount_percentage);
	table.fields.push(...defs.hidden);
	logicposintegration.quotation.populate_discount_on_rows(table.data, frm);
};

logicposintegration.quotation.patch_update_child_items = function () {
	if (erpnext.utils._logicpos_quotation_update_items_patched_v2) {
		return;
	}
	erpnext.utils._logicpos_quotation_update_items_patched_v2 = true;

	const original = erpnext.utils.update_child_items;
	erpnext.utils.update_child_items = function (opts) {
		if ((opts?.frm?.doctype || opts?.frm?.doc?.doctype) !== "Quotation") {
			return original.apply(this, arguments);
		}

		// cur_dialog só é definido em shown.bs.modal (depois do show()).
		// Injectar os campos no construtor garante que a grelha e o form da linha os vêem.
		const Dialog = frappe.ui.Dialog;
		frappe.ui.Dialog = class extends Dialog {
			constructor(dialog_opts) {
				logicposintegration.quotation.inject_discount_fields(dialog_opts, opts.frm);
				super(dialog_opts);
			}
		};

		try {
			return original.apply(this, arguments);
		} finally {
			frappe.ui.Dialog = Dialog;
		}
	};
};

logicposintegration.quotation.generate_proposal = function (frm, values) {
	console.log(values);
	// console.log(frm.doc);

	// frm.doc.customer_name
	// frm.doc.currency
	// frm.doc.items 

	const payload = {
		article: values.article,
		version: values.version.toString().replace(",", "."),
		client: frm.doc.customer_name,
		currency: frm.doc.currency,
		terms: frm.doc.terms,
		items: frm.doc.items.map((item) => { 
			return {
				item_code: item.item_code,
				item_name: item.item_name,
				item_group: item.item_group,
				stock_uom: item.uom,
				image: item.image,
				qty: item.qty,
				rate: item.rate,
				amount: item.amount,
			}	
		}),
	}

	console.log(payload);

	frappe.call({
		method: "logicposintegration.logicpos_integration.proposals.generate.generate_proposal",
		freeze: true,
		freeze_message: "A gerar a proposta comercial...",
		args: payload,
		callback: function (res) {
			if (res.message) {
				window.open(res.message, '_blank');
				frappe.msgprint(__('Proposta comercial gerada com sucesso!'));
			} else {
				frappe.msgprint(__('Erro ao gerar a proposta comercial.'));
			}
		},
	});
};

frappe.ui.form.on("Quotation", {
	setup(frm) {
		logicposintegration.quotation.set_party_name_query(frm);
		logicposintegration.quotation.patch_update_child_items();
	},

	refresh(frm) {
		logicposintegration.quotation.set_party_name_query(frm);
		logicposintegration.quotation.patch_update_child_items();

		frm.add_custom_button(__("Proposta"), () => {
			let dialog = new frappe.ui.Dialog({
				title: 'Proposta Comercial',
				fields: [
					{
						label: 'Artigo',
						fieldname: 'article',
						fieldtype: "Select",
						options: ["q.track", "q.track.survey", "time.track", "access.track", "fatory.track", "library.track", "fleet.track", "logicPOS", "others"].join("\n"),
						reqd: 1
					},
					{
						label: 'Versão',
						fieldname: 'version',
						fieldtype: 'Data',
						reqd: 1,
						default: '1.0',
						description: __('Valor entre 1.0 e 10.9 (use vírgula ou ponto)'),
					}
				],
				size: 'small',
				primary_action_label: 'Gerar',
				primary_action(values) {
					if (!logicposintegration.quotation.validate_proposal_version(values.version)) {
						return;
					}
					values.version = logicposintegration.quotation.parse_proposal_version(values.version);
					logicposintegration.quotation.generate_proposal(frm, values);
					dialog.hide();
				}
			});
			dialog.show();
		});
	},

	company(frm) {
		logicposintegration.quotation.set_party_name_query(frm);
		logicposintegration.quotation.validate_party_currency(frm);
	},

	quotation_to(frm) {
		logicposintegration.quotation.set_party_name_query(frm);
	},
});
