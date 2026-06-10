frappe.provide("logicposintegration.quotation");

const COMPANY_PARTY_CURRENCY = {
	"Logicpulse PT": "EUR",
	"Logicpulse AO": "AOA",
};

const POS_STOCK_METHOD =
	"logicposintegration.logicpos_integration.articles.get_on_hand_total_for_article";

logicposintegration.quotation._pos_stock_timeouts = {};
logicposintegration.quotation._pos_stock_cache = {};

logicposintegration.quotation.get_quotation_frm = function () {
	return cur_frm?.doctype === "Quotation" ? cur_frm : null;
};

logicposintegration.quotation.get_pos_stock_cache_key = function (frm, row) {
	return `${frm?.doc?.name || "new"}:${row.name}:${row.item_code}`;
};

logicposintegration.quotation.get_row_stock_state = function (doc, frm) {
	const row = locals["Quotation Item"]?.[doc.name] || doc;
	frm = frm || logicposintegration.quotation.get_quotation_frm();

	if (frm && row?.name && row?.item_code) {
		const cache_key = logicposintegration.quotation.get_pos_stock_cache_key(frm, row);
		if (logicposintegration.quotation._pos_stock_cache[cache_key]) {
			return logicposintegration.quotation._pos_stock_cache[cache_key];
		}
	}

	return {
		loading: !!row.__pos_on_hand_loading,
		found: row.__pos_on_hand_found,
		total: row.__pos_on_hand_total,
		reason: row.__pos_on_hand_reason,
	};
};

logicposintegration.quotation.set_row_stock_state = function (row, state, frm) {
	row.__pos_on_hand_loading = state.loading;
	row.__pos_on_hand_found = state.found;
	row.__pos_on_hand_total = state.total;
	row.__pos_on_hand_reason = state.reason;

	frm = frm || logicposintegration.quotation.get_quotation_frm();
	if (frm && row?.name && row?.item_code) {
		const cache_key = logicposintegration.quotation.get_pos_stock_cache_key(frm, row);
		logicposintegration.quotation._pos_stock_cache[cache_key] = { ...state };
	}
};

logicposintegration.quotation.parse_pos_stock_total = function (data) {
	if (data == null || typeof data !== "object") {
		return null;
	}
	if ("quantity" in data) {
		return flt(data.quantity);
	}
	return null;
};

logicposintegration.quotation.get_stock_indicator_color = function (doc) {
	if (!doc.item_code) {
		return "";
	}

	const frm = logicposintegration.quotation.get_quotation_frm();
	const state = logicposintegration.quotation.get_row_stock_state(doc);

	if (state.loading) {
		return "blue";
	}

	if (state.found === false) {
		return "red";
	}

	if (state.found === true) {
		if (!doc.qty) {
			return frm?.doc?.has_unit_price_items ? "orange" : "";
		}
		if (state.total == null) {
			return "";
		}
		return flt(doc.qty) <= flt(state.total) ? "green" : "yellow";
	}

	return !doc.qty && frm?.doc?.has_unit_price_items ? "orange" : "";
};

logicposintegration.quotation.get_stock_preview_fields = function (doc) {
	if (!doc.item_code) {
		return [];
	}

	const state = logicposintegration.quotation.get_row_stock_state(doc);

	if (state.loading) {
		return [{ label: __("Stock POS"), value: __("A consultar stock no POS...") }];
	}
	if (state.found === false) {
		return [
			{
				label: __("Stock POS"),
				value: state.reason || __("Artigo não encontrado no POS"),
			},
		];
	}
	if (state.found == null) {
		return [{ label: __("Stock POS"), value: __("A consultar stock no POS...") }];
	}
	if (state.found === true && state.total == null) {
		return [{ label: __("Stock POS"), value: __("Stock POS indisponível") }];
	}

	const fields = [{ label: __("Stock POS"), value: String(flt(state.total)) }];
	if (doc.qty) {
		fields.push({ label: __("Pedido"), value: String(flt(doc.qty)) });
		const shortage = flt(doc.qty) - flt(state.total);
		if (shortage > 0) {
			fields.push({ label: __("Em falta"), value: String(shortage) });
		}
	}
	return fields;
};

logicposintegration.quotation.get_stock_preview_html = function (doc) {
	return logicposintegration.quotation
		.get_stock_preview_fields(doc)
		.map(
			(field) => `
			<div class="preview-field"> 
				<div class="preview-label text-muted">${__(field.label)}: ${frappe.utils.escape_html(field.value)}</div> 
			</div>
		`
		)
		.join("");
};

logicposintegration.quotation.refresh_pos_stock_row = function (frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!row?.item_code) {
		return;
	}
	logicposintegration.quotation.set_row_stock_state(
		row,
		{
			loading: true,
			found: null,
			total: null,
			reason: null,
		},
		frm
	);
	logicposintegration.quotation.refresh_grid_item_code_indicators(frm);

	const timeout_key = `${frm.doc.name || "new"}:${cdn}`;
	clearTimeout(logicposintegration.quotation._pos_stock_timeouts[timeout_key]);
	logicposintegration.quotation._pos_stock_timeouts[timeout_key] = setTimeout(() => {
		frappe.call({
			method: POS_STOCK_METHOD,
			args: {
				code: row.item_code,
				company: frm.doc.company,
			},
			callback(r) {
				const message = r.message || {};
				if (!message.found) {
					logicposintegration.quotation.set_row_stock_state(
						row,
						{
							loading: false,
							found: false,
							total: null,
							reason: message.reason,
						},
						frm
					);
				} else {
					const stock_data = message.data || message;
					let total = logicposintegration.quotation.parse_pos_stock_total(stock_data);
					if (total == null && stock_data && typeof stock_data === "object") {
						total = 0;
					}
					logicposintegration.quotation.set_row_stock_state(
						row,
						{
							loading: false,
							found: true,
							total,
							reason: null,
						},
						frm
					);
				}
				logicposintegration.quotation.refresh_grid_item_code_indicators(frm);
			},
			error() {
				logicposintegration.quotation.set_row_stock_state(
					row,
					{
						loading: false,
						found: false,
						total: null,
						reason: __("Erro de comunicação com o POS"),
					},
					frm
				);
				logicposintegration.quotation.refresh_grid_item_code_indicators(frm);
			},
		});
	}, 300);
};

logicposintegration.quotation.clear_pos_stock_cache = function (frm) {
	const prefix = `${frm.doc.name || "new"}:`;
	Object.keys(logicposintegration.quotation._pos_stock_cache).forEach((key) => {
		if (key.startsWith(prefix)) {
			delete logicposintegration.quotation._pos_stock_cache[key];
		}
	});

	(frm.doc.items || []).forEach((row) => {
		logicposintegration.quotation.set_row_stock_state(
			row,
			{
				loading: false,
				found: null,
				total: null,
				reason: null,
			},
			frm
		);
	});
};

logicposintegration.quotation.refresh_all_pos_stock = function (frm, force = false) {
	(frm.doc.items || []).forEach((row) => {
		if (!row.item_code) {
			return;
		}
		const state = logicposintegration.quotation.get_row_stock_state(row);
		if (force || (state.found == null && !state.loading)) {
			logicposintegration.quotation.refresh_pos_stock_row(frm, row.doctype, row.name);
		}
	});
};

logicposintegration.quotation.format_item_code = function (value, df, doc) {
	if (!value) {
		return "";
	}

	const color = logicposintegration.quotation.get_stock_indicator_color(doc);
	const label = frappe.utils.escape_html(value);
	const escaped_name = encodeURIComponent(value);
	const color_class = color ? `indicator ${color}` : "";

	return `
		<a class="${color_class}"
			href="/desk/${frappe.router.slug(df.options)}/${escaped_name}"
			data-doctype="${df.options}"
			data-name="${frappe.utils.escape_html(value)}"
			data-logicpos-row="${frappe.utils.escape_html(doc.name)}">
			${label}
		</a>
	`;
};

logicposintegration.quotation.refresh_grid_item_code_indicators = function (frm) {
	const grid = frm?.fields_dict?.items?.grid;
	if (!grid?.grid_rows?.length) {
		return;
	}

	const df = frappe.meta.docfield_map["Quotation Item"]["item_code"];
	if (!df) {
		return;
	}

	grid.grid_rows.forEach((grid_row) => {
		if (!grid_row.doc?.item_code) {
			return;
		}

		const column = grid_row.columns?.item_code;
		if (!column?.static_area) {
			return;
		}

		const html = logicposintegration.quotation.format_item_code(
			grid_row.doc.item_code,
			df,
			grid_row.doc
		);
		column.static_area.html(html);
	});
};

logicposintegration.quotation.setup_pos_stock_grid_formatter = function () {
	const item_code_df = frappe.meta.docfield_map["Quotation Item"]["item_code"];
	item_code_df.formatter = function (value, df, options, doc) {
		return logicposintegration.quotation.format_item_code(value, df, doc);
	};
};

logicposintegration.quotation.attach_formatter_to_grid = function (frm) {
	const grid = frm.fields_dict?.items?.grid;
	const formatter = frappe.meta.docfield_map["Quotation Item"]["item_code"]?.formatter;
	if (!grid || !formatter) {
		return;
	}

	(grid.docfields || []).forEach((df) => {
		if (df.fieldname === "item_code") {
			df.formatter = formatter;
		}
	});
};

logicposintegration.quotation.ensure_pos_stock_grid_hooks = function (frm) {
	const grid = frm.fields_dict?.items?.grid;
	if (!grid) {
		return;
	}

	logicposintegration.quotation.attach_formatter_to_grid(frm);

	if (!grid._logicpos_indicator_hook && typeof grid.refresh === "function") {
		grid._logicpos_indicator_hook = true;
		const original_refresh = grid.refresh.bind(grid);
		grid.refresh = function (...args) {
			const result = original_refresh(...args);
			logicposintegration.quotation.attach_formatter_to_grid(frm);
			setTimeout(() => {
				logicposintegration.quotation.refresh_grid_item_code_indicators(frm);
			}, 0);
			return result;
		};
	}

	const $wrapper = grid.wrapper || frm.$wrapper || $(frm.wrapper);
	if (!frm._logicpos_stock_focusout_hook && $wrapper?.on) {
		frm._logicpos_stock_focusout_hook = true;
		$wrapper.on("focusout.logicpos-stock", ".grid-row", () => {
			setTimeout(() => {
				logicposintegration.quotation.refresh_grid_item_code_indicators(frm);
			}, 0);
		});
	}

	logicposintegration.quotation.refresh_grid_item_code_indicators(frm);
};

logicposintegration.quotation.setup_pos_stock_link_preview = function () {
	if (logicposintegration.quotation._link_preview_hooked) {
		return;
	}
	logicposintegration.quotation._link_preview_hooked = true;

	const original_get_content_html = frappe.ui.LinkPreview.prototype.get_content_html;
	frappe.ui.LinkPreview.prototype.get_content_html = function (preview_data) {
		let content_html = original_get_content_html.call(this, preview_data);

		if (this.doctype !== "Item" || !this.element) {
			return content_html;
		}

		const row_name = this.element.attr("data-logicpos-row");
		const row = locals["Quotation Item"]?.[row_name];

		if (row) {
			const frm = logicposintegration.quotation.get_quotation_frm();
			const state = logicposintegration.quotation.get_row_stock_state(row, frm);
			if (state.found == null && !state.loading && frm) {
				logicposintegration.quotation.refresh_pos_stock_row(
					frm,
					row.doctype,
					row.name
				);
			}
			content_html += logicposintegration.quotation.get_stock_preview_html(row);
		}

		return content_html;
	};
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

logicposintegration.quotation.setup_pos_stock_link_preview();
logicposintegration.quotation.setup_pos_stock_grid_formatter();

frappe.ui.form.on("Quotation", {
	setup(frm) {
		logicposintegration.quotation.set_party_name_query(frm);
	},

	refresh(frm) {
		logicposintegration.quotation.set_party_name_query(frm);
		logicposintegration.quotation.ensure_pos_stock_grid_hooks(frm);
		if (frm.doc.docstatus === 0) {
			logicposintegration.quotation.refresh_all_pos_stock(frm);
		}
	},

	company(frm) {
		logicposintegration.quotation.set_party_name_query(frm);
		logicposintegration.quotation.validate_party_currency(frm);
		logicposintegration.quotation.clear_pos_stock_cache(frm);
		logicposintegration.quotation.refresh_all_pos_stock(frm, true);
	},

	quotation_to(frm) {
		logicposintegration.quotation.set_party_name_query(frm);
	},
});

frappe.ui.form.on("Quotation Item", {
	item_code(frm, cdt, cdn) {
		logicposintegration.quotation.refresh_pos_stock_row(frm, cdt, cdn);
	},

	qty(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		const state = logicposintegration.quotation.get_row_stock_state(row);
		if (row?.item_code && state.found !== true) {
			logicposintegration.quotation.refresh_pos_stock_row(frm, cdt, cdn);
			return;
		}
		logicposintegration.quotation.refresh_grid_item_code_indicators(frm);
	},
});
