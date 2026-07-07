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
	},

	refresh(frm) {
		logicposintegration.quotation.set_party_name_query(frm);

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
