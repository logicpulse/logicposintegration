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

frappe.ui.form.on("Quotation", {
	setup(frm) {
		logicposintegration.quotation.set_party_name_query(frm);
	},

	refresh(frm) {
		logicposintegration.quotation.set_party_name_query(frm);
	},

	company(frm) {
		logicposintegration.quotation.set_party_name_query(frm);
		logicposintegration.quotation.validate_party_currency(frm);
	},

	quotation_to(frm) {
		logicposintegration.quotation.set_party_name_query(frm);
	},
});
