frappe.provide("logicposintegration.pos_stock");

const POS_STOCK_METHOD =
	"logicposintegration.logicpos_integration.articles.get_on_hand_total_for_article";

logicposintegration.pos_stock._timeouts = {};
logicposintegration.pos_stock._cache = {};
logicposintegration.pos_stock._preview_hold_until = null;
logicposintegration.pos_stock._preview_hide_timeout = null;
logicposintegration.pos_stock._link_preview_hooked = false;

logicposintegration.pos_stock.CONFIGS = {
	Quotation: { child_doctype: "Quotation Item", draft_only: true },
	"Sales Order": { child_doctype: "Sales Order Item", draft_only: true },
};

logicposintegration.pos_stock.get_config = function (frm_or_doctype) {
	const doctype =
		typeof frm_or_doctype === "string" ? frm_or_doctype : frm_or_doctype?.doctype;
	return logicposintegration.pos_stock.CONFIGS[doctype];
};

logicposintegration.pos_stock.get_active_frm = function () {
	if (!cur_frm) {
		return null;
	}
	return logicposintegration.pos_stock.get_config(cur_frm) ? cur_frm : null;
};

logicposintegration.pos_stock.get_child_doctype = function (frm) {
	return logicposintegration.pos_stock.get_config(frm)?.child_doctype;
};

logicposintegration.pos_stock.should_auto_refresh = function (frm) {
	const config = logicposintegration.pos_stock.get_config(frm);
	if (!config) {
		return false;
	}
	return config.draft_only ? frm.doc.docstatus === 0 : frm.doc.docstatus !== 2;
};

logicposintegration.pos_stock.get_pos_stock_cache_key = function (frm, row) {
	return `${frm?.doc?.name || "new"}:${row.name}:${row.item_code}`;
};

logicposintegration.pos_stock.get_row = function (doc, frm) {
	const child_doctype =
		logicposintegration.pos_stock.get_child_doctype(frm) || doc.doctype;
	return locals[child_doctype]?.[doc.name] || doc;
};

logicposintegration.pos_stock.get_row_stock_state = function (doc, frm) {
	frm = frm || logicposintegration.pos_stock.get_active_frm();
	const row = logicposintegration.pos_stock.get_row(doc, frm);

	if (frm && row?.name && row?.item_code) {
		const cache_key = logicposintegration.pos_stock.get_pos_stock_cache_key(frm, row);
		if (logicposintegration.pos_stock._cache[cache_key]) {
			return logicposintegration.pos_stock._cache[cache_key];
		}
	}

	return {
		loading: !!row.__pos_on_hand_loading,
		found: row.__pos_on_hand_found,
		total: row.__pos_on_hand_total,
		reason: row.__pos_on_hand_reason,
	};
};

logicposintegration.pos_stock.set_row_stock_state = function (row, state, frm) {
	row.__pos_on_hand_loading = state.loading;
	row.__pos_on_hand_found = state.found;
	row.__pos_on_hand_total = state.total;
	row.__pos_on_hand_reason = state.reason;

	frm = frm || logicposintegration.pos_stock.get_active_frm();
	if (frm && row?.name && row?.item_code) {
		const cache_key = logicposintegration.pos_stock.get_pos_stock_cache_key(frm, row);
		logicposintegration.pos_stock._cache[cache_key] = { ...state };
	}
};

logicposintegration.pos_stock.parse_pos_stock_total = function (data) {
	if (data == null || typeof data !== "object") {
		return null;
	}
	if ("quantity" in data) {
		return flt(data.quantity);
	}
	return null;
};

logicposintegration.pos_stock.get_stock_indicator_color = function (doc, frm) {
	if (!doc.item_code) {
		return "";
	}

	frm = frm || logicposintegration.pos_stock.get_active_frm();
	const state = logicposintegration.pos_stock.get_row_stock_state(doc, frm);

	if (state.loading) {
		return "yellow";
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
		return flt(doc.qty) <= flt(state.total) ? "green" : "blue";
	}
	return !doc.qty && frm?.doc?.has_unit_price_items ? "orange" : "";
};

logicposintegration.pos_stock.get_stock_preview_fields = function (doc, frm) {
	if (!doc.item_code) {
		return [];
	}

	const state = logicposintegration.pos_stock.get_row_stock_state(doc, frm);

	if (state.loading || state.found == null) {
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
	if (state.total == null) {
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

logicposintegration.pos_stock.get_stock_preview_html = function (doc, frm) {
	return logicposintegration.pos_stock
		.get_stock_preview_fields(doc, frm)
		.map(
			(field) => `
			<div class="preview-field">
				<div class="preview-label text-muted">${__(field.label)}: ${frappe.utils.escape_html(field.value)}</div>
			</div>
		`
		)
		.join("");
};

logicposintegration.pos_stock.refresh_pos_stock_row = function (frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!row?.item_code) {
		return;
	}

	logicposintegration.pos_stock.set_row_stock_state(
		row,
		{ loading: true, found: null, total: null, reason: null },
		frm
	);
	logicposintegration.pos_stock.refresh_grid_item_code_indicators(frm);

	const timeout_key = `${frm.doc.name || "new"}:${cdn}`;
	clearTimeout(logicposintegration.pos_stock._timeouts[timeout_key]);
	logicposintegration.pos_stock._timeouts[timeout_key] = setTimeout(() => {
		frappe.call({
			method: POS_STOCK_METHOD,
			args: { code: row.item_code, company: frm.doc.company },
			callback(r) {
				const message = r.message || {};
				if (!message.found) {
					logicposintegration.pos_stock.set_row_stock_state(
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
					let total = logicposintegration.pos_stock.parse_pos_stock_total(stock_data);
					if (total == null && stock_data && typeof stock_data === "object") {
						total = 0;
					}
					logicposintegration.pos_stock.set_row_stock_state(
						row,
						{ loading: false, found: true, total, reason: null },
						frm
					);
				}
				logicposintegration.pos_stock.refresh_grid_item_code_indicators(frm);
				logicposintegration.pos_stock.refresh_open_item_preview(row);
			},
			error() {
				logicposintegration.pos_stock.set_row_stock_state(
					row,
					{
						loading: false,
						found: false,
						total: null,
						reason: __("Erro de comunicação com o POS"),
					},
					frm
				);
				logicposintegration.pos_stock.refresh_grid_item_code_indicators(frm);
				logicposintegration.pos_stock.refresh_open_item_preview(row);
			},
		});
	}, 300);
};

logicposintegration.pos_stock.clear_pos_stock_cache = function (frm) {
	const prefix = `${frm.doc.name || "new"}:`;
	Object.keys(logicposintegration.pos_stock._cache).forEach((key) => {
		if (key.startsWith(prefix)) {
			delete logicposintegration.pos_stock._cache[key];
		}
	});

	(frm.doc.items || []).forEach((row) => {
		logicposintegration.pos_stock.set_row_stock_state(
			row,
			{ loading: false, found: null, total: null, reason: null },
			frm
		);
	});
};

logicposintegration.pos_stock.refresh_all_pos_stock = function (frm, force = false) {
	(frm.doc.items || []).forEach((row) => {
		if (!row.item_code) {
			return;
		}
		const state = logicposintegration.pos_stock.get_row_stock_state(row, frm);
		if (force || (state.found == null && !state.loading)) {
			logicposintegration.pos_stock.refresh_pos_stock_row(frm, row.doctype, row.name);
		}
	});
};

logicposintegration.pos_stock.format_item_code = function (value, df, doc, frm) {
	if (!value) {
		return "";
	}

	const color = logicposintegration.pos_stock.get_stock_indicator_color(doc, frm);
	const label = frappe.utils.escape_html(value);
	const escaped_name = encodeURIComponent(value);
	const color_class = color ? `indicator ${color}` : "";
	const child_doctype = logicposintegration.pos_stock.get_child_doctype(frm) || doc.doctype;

	return `
		<a class="${color_class}"
			href="/desk/${frappe.router.slug(df.options)}/${escaped_name}"
			data-doctype="${df.options}"
			data-name="${frappe.utils.escape_html(value)}"
			data-logicpos-row="${frappe.utils.escape_html(doc.name)}"
			data-logicpos-child="${frappe.utils.escape_html(child_doctype)}">
			${label}
		</a>
	`;
};

logicposintegration.pos_stock.refresh_grid_item_code_indicators = function (frm) {
	const grid = frm?.fields_dict?.items?.grid;
	const child_doctype = logicposintegration.pos_stock.get_child_doctype(frm);
	if (!grid?.grid_rows?.length || !child_doctype) {
		return;
	}

	const df = frappe.meta.docfield_map[child_doctype]?.item_code;
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
		column.static_area.html(
			logicposintegration.pos_stock.format_item_code(
				grid_row.doc.item_code,
				df,
				grid_row.doc,
				frm
			)
		);
	});
};

logicposintegration.pos_stock.setup_grid_formatters = function () {
	Object.values(logicposintegration.pos_stock.CONFIGS).forEach(({ child_doctype }) => {
		const item_code_df = frappe.meta.docfield_map[child_doctype]?.item_code;
		if (!item_code_df) {
			return;
		}
		item_code_df.formatter = function (value, df, options, doc) {
			return logicposintegration.pos_stock.format_item_code(
				value,
				df,
				doc,
				logicposintegration.pos_stock.get_active_frm()
			);
		};
	});
};

logicposintegration.pos_stock.attach_formatter_to_grid = function (frm) {
	const grid = frm.fields_dict?.items?.grid;
	const child_doctype = logicposintegration.pos_stock.get_child_doctype(frm);
	const formatter = frappe.meta.docfield_map[child_doctype]?.item_code?.formatter;
	if (!grid || !formatter) {
		return;
	}
	(grid.docfields || []).forEach((df) => {
		if (df.fieldname === "item_code") {
			df.formatter = formatter;
		}
	});
};

logicposintegration.pos_stock.ensure_grid_hooks = function (frm) {
	const grid = frm.fields_dict?.items?.grid;
	if (!grid) {
		return;
	}

	logicposintegration.pos_stock.attach_formatter_to_grid(frm);

	if (!grid._logicpos_indicator_hook && typeof grid.refresh === "function") {
		grid._logicpos_indicator_hook = true;
		const original_refresh = grid.refresh.bind(grid);
		grid.refresh = function (...args) {
			const result = original_refresh(...args);
			logicposintegration.pos_stock.attach_formatter_to_grid(frm);
			setTimeout(() => {
				logicposintegration.pos_stock.refresh_grid_item_code_indicators(frm);
			}, 0);
			return result;
		};
	}

	const $wrapper = grid.wrapper || frm.$wrapper || $(frm.wrapper);
	if (!frm._logicpos_stock_focusout_hook && $wrapper?.on) {
		frm._logicpos_stock_focusout_hook = true;
		$wrapper.on("focusout.logicpos-stock", ".grid-row", () => {
			setTimeout(() => {
				logicposintegration.pos_stock.refresh_grid_item_code_indicators(frm);
			}, 0);
		});
	}

	logicposintegration.pos_stock.setup_item_code_preview_handlers(frm);
	logicposintegration.pos_stock.refresh_grid_item_code_indicators(frm);
};

logicposintegration.pos_stock.get_link_preview = function () {
	return frappe.app?.link_preview;
};

logicposintegration.pos_stock.find_row_from_preview_element = function ($element) {
	const row_name = $element.attr("data-logicpos-row");
	const child_doctype = $element.attr("data-logicpos-child");
	if (row_name && child_doctype) {
		return locals[child_doctype]?.[row_name];
	}
	for (const config of Object.values(logicposintegration.pos_stock.CONFIGS)) {
		const row = locals[config.child_doctype]?.[row_name];
		if (row) {
			return row;
		}
	}
	return null;
};

logicposintegration.pos_stock.setup_link_preview = function () {
	if (logicposintegration.pos_stock._link_preview_hooked) {
		return;
	}
	logicposintegration.pos_stock._link_preview_hooked = true;

	const LP = frappe.ui.LinkPreview.prototype;
	const PREVIEW_SHOW_DELAY_MS = 150;
	const PREVIEW_DATA_DELAY_MS = 50;

	const original_show_popover = LP.show_popover;
	LP.show_popover = function (e) {
		if (this.element?.attr("data-logicpos-row")) {
			logicposintegration.pos_stock._preview_hold_until = Date.now() + 500;
		}
		return original_show_popover.call(this, e);
	};

	const original_clear_all_popovers = LP.clear_all_popovers;
	LP.clear_all_popovers = function () {
		if (
			logicposintegration.pos_stock._preview_hold_until &&
			Date.now() < logicposintegration.pos_stock._preview_hold_until
		) {
			return;
		}
		return original_clear_all_popovers.call(this);
	};

	const original_setup_popover_control = LP.setup_popover_control;
	LP.setup_popover_control = function (e) {
		if (!this.element?.attr("data-logicpos-row")) {
			return original_setup_popover_control.call(this, e);
		}
		if (!(frappe.boot.link_preview_doctypes || []).includes(this.doctype)) {
			return;
		}

		clearTimeout(this.data_timeout);
		clearTimeout(this.popover_timeout);
		logicposintegration.pos_stock._preview_hold_until = Date.now() + 800;

		this.element.on("change", () => {
			this.new_popover = true;
		});

		if (!this.popover || this.new_popover) {
			this.data_timeout = setTimeout(() => this.create_popover(e), PREVIEW_DATA_DELAY_MS);
		} else {
			this.popover_timeout = setTimeout(() => {
				if (!this.element.is(":focus")) {
					this.show_popover(e);
				}
			}, PREVIEW_SHOW_DELAY_MS);
		}
	};

	const original_create_popover = LP.create_popover;
	LP.create_popover = function (e) {
		if (!this.element?.attr("data-logicpos-row")) {
			return original_create_popover.call(this, e);
		}

		this.new_popover = false;
		if (this.element.is(":focus")) {
			return;
		}

		this.get_preview_data().then((preview_data) => {
			if (!preview_data) {
				return;
			}
			if (this.popover_timeout) {
				clearTimeout(this.popover_timeout);
			}
			this.popover_timeout = setTimeout(() => {
				if (this.popover && this.popover.config) {
					this.popover.config.content = this.get_popover_html(preview_data);
				} else {
					this.init_preview_popover(preview_data);
				}
				this.show_popover(e);
			}, PREVIEW_SHOW_DELAY_MS);
		});
	};

	const original_get_content_html = LP.get_content_html;
	LP.get_content_html = function (preview_data) {
		let content_html = original_get_content_html.call(this, preview_data);

		if (this.doctype !== "Item" || !this.element) {
			return content_html;
		}

		const row = logicposintegration.pos_stock.find_row_from_preview_element(this.element);
		if (row) {
			const frm = logicposintegration.pos_stock.get_active_frm();
			const state = logicposintegration.pos_stock.get_row_stock_state(row, frm);
			if (state.found == null && !state.loading && frm) {
				logicposintegration.pos_stock.refresh_pos_stock_row(frm, row.doctype, row.name);
			}
			content_html += logicposintegration.pos_stock.get_stock_preview_html(row, frm);
		}

		return content_html;
	};
};

logicposintegration.pos_stock.trigger_item_preview = function ($link, e) {
	const lp = logicposintegration.pos_stock.get_link_preview();
	if (!lp || !$link?.length) {
		return;
	}

	clearTimeout(logicposintegration.pos_stock._preview_hide_timeout);
	logicposintegration.pos_stock._preview_hold_until = Date.now() + 800;
	lp.link_hovered = true;
	lp.element = $link;
	lp.is_link = true;
	lp.identify_doc();
	lp.popover = $link.data("bs.popover");

	if (lp.name && lp.doctype) {
		lp.setup_popover_control(e);
	}
};

logicposintegration.pos_stock.refresh_open_item_preview = function (row) {
	const $link = $("a[data-logicpos-row]").filter(function () {
		return $(this).attr("data-logicpos-row") === row.name;
	}).filter(":visible");
	if (!$link.length) {
		return;
	}

	const popover = $link.data("bs.popover");
	const $tip = popover?.tip ? $(popover.tip) : $();
	if (!$tip.length || !$tip.is(":visible")) {
		return;
	}

	const lp = logicposintegration.pos_stock.get_link_preview();
	if (!lp) {
		return;
	}

	lp.element = $link;
	lp.is_link = true;
	lp.doctype = "Item";
	lp.name = row.item_code;
	lp.href = $link.attr("href");

	lp.get_preview_data().then((preview_data) => {
		if (!preview_data) {
			return;
		}
		popover.config.content = lp.get_popover_html(preview_data);
		$link.popover("show");
	});
};

logicposintegration.pos_stock.setup_item_code_preview_handlers = function (frm) {
	const grid = frm.fields_dict?.items?.grid;
	const $wrapper = grid?.wrapper || frm.$wrapper || $(frm.wrapper);
	if (!$wrapper?.on || frm._logicpos_preview_hover_hook) {
		return;
	}

	frm._logicpos_preview_hover_hook = true;

	$wrapper.on(
		"mouseenter.logicpos-preview",
		'a[data-logicpos-row][data-doctype="Item"]',
		function (e) {
			logicposintegration.pos_stock.trigger_item_preview($(this), e);
		}
	);

	$wrapper.on(
		"mouseleave.logicpos-preview",
		'a[data-logicpos-row][data-doctype="Item"]',
		function () {
			const lp = logicposintegration.pos_stock.get_link_preview();
			clearTimeout(logicposintegration.pos_stock._preview_hide_timeout);
			logicposintegration.pos_stock._preview_hide_timeout = setTimeout(() => {
				if ($(".link-preview-popover:hover").length) {
					return;
				}
				if (lp) {
					lp.link_hovered = false;
					lp.clear_all_popovers();
				}
			}, 300);
		}
	);

	if (!logicposintegration.pos_stock._preview_popover_handlers) {
		logicposintegration.pos_stock._preview_popover_handlers = true;

		$(document.body).on("mouseenter.logicpos-preview", ".link-preview-popover", () => {
			clearTimeout(logicposintegration.pos_stock._preview_hide_timeout);
			const lp = logicposintegration.pos_stock.get_link_preview();
			if (lp) {
				lp.link_hovered = true;
			}
		});

		$(document.body).on("mouseleave.logicpos-preview", ".link-preview-popover", () => {
			const lp = logicposintegration.pos_stock.get_link_preview();
			clearTimeout(logicposintegration.pos_stock._preview_hide_timeout);
			logicposintegration.pos_stock._preview_hide_timeout = setTimeout(() => {
				if (lp) {
					lp.link_hovered = false;
					lp.clear_all_popovers();
				}
			}, 200);
		});
	}
};

logicposintegration.pos_stock.register = function (parent_doctype, child_doctype) {
	logicposintegration.pos_stock.CONFIGS[parent_doctype] = {
		child_doctype,
		draft_only: true,
	};

	frappe.ui.form.on(parent_doctype, {
		refresh(frm) {
			logicposintegration.pos_stock.ensure_grid_hooks(frm);
			if (logicposintegration.pos_stock.should_auto_refresh(frm)) {
				logicposintegration.pos_stock.refresh_all_pos_stock(frm);
			}
		},

		company(frm) {
			logicposintegration.pos_stock.clear_pos_stock_cache(frm);
			logicposintegration.pos_stock.refresh_all_pos_stock(frm, true);
		},
	});

	frappe.ui.form.on(child_doctype, {
		item_code(frm, cdt, cdn) {
			logicposintegration.pos_stock.refresh_pos_stock_row(frm, cdt, cdn);
		},

		qty(frm, cdt, cdn) {
			const row = locals[cdt][cdn];
			const state = logicposintegration.pos_stock.get_row_stock_state(row, frm);
			if (row?.item_code && state.found !== true) {
				logicposintegration.pos_stock.refresh_pos_stock_row(frm, cdt, cdn);
				return;
			}
			logicposintegration.pos_stock.refresh_grid_item_code_indicators(frm);
		},
	});
};

logicposintegration.pos_stock.setup_link_preview();
logicposintegration.pos_stock.setup_grid_formatters();
logicposintegration.pos_stock.register("Quotation", "Quotation Item");
logicposintegration.pos_stock.register("Sales Order", "Sales Order Item");
