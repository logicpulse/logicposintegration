function set_customer_contact_html(frm, html) {
	const field = frm.get_field("customer_contact");
	if (!field) {
		return;
	}
	field.html(html || "");
}

function contact_row(icon, label, value_html) {
	return `<div class="lp-task-contact-row">
		<span class="lp-task-contact-icon">${frappe.utils.icon(icon, "sm")}</span>
		<span class="lp-task-contact-label">${frappe.utils.escape_html(label)}</span>
		<span class="lp-task-contact-value">${value_html}</span>
	</div>`;
}

function wrap_contact_field(inner, extra_class = "") {
	return `<div class="form-group lp-task-contact ${extra_class}">
		<div class="clearfix">
			<label class="control-label">${__("Contacto")}</label>
		</div>
		<div class="control-input-wrapper">
			<div class="control-value like-disabled-input">${inner}</div>
		</div>
	</div>`;
}

function render_customer_contact(frm, contact, warn) {
	if (!contact) {
		const customer_link = frappe.utils.get_form_link(
			"Customer",
			frm.doc.customer_id,
			true,
			frappe.utils.escape_html(frm.doc.customer_id)
		);
		const message = __(
			"Este cliente não tem contacto. Defina um contacto em {0}.",
			[customer_link]
		);
		set_customer_contact_html(
			frm,
			wrap_contact_field(
				`<div class="lp-task-contact-missing">
					${frappe.utils.icon("es-line-alert-triangle", "sm")}
					<span>${message}</span>
				</div>`,
				"is-missing"
			)
		);
		if (warn) {
			frappe.msgprint({
				title: __("Contacto em falta"),
				indicator: "orange",
				message,
			});
		}
		return;
	}

	const rows = [];
	const display_name = frappe.utils.escape_html(contact.full_name || contact.name);
	rows.push(
		contact_row(
			"es-line-people",
			__("Nome"),
			frappe.utils.get_form_link("Contact", contact.name, true, display_name)
		)
	);

	const phone = contact.phone || contact.mobile_no;
	if (phone) {
		const safe_phone = frappe.utils.escape_html(phone);
		rows.push(
			contact_row(
				"es-line-call",
				__("Telefone"),
				`<a href="tel:${encodeURIComponent(phone)}">${safe_phone}</a>`
			)
		);
	}
	if (contact.phone && contact.mobile_no && contact.mobile_no !== contact.phone) {
		const safe_mobile = frappe.utils.escape_html(contact.mobile_no);
		rows.push(
			contact_row(
				"es-line-call",
				__("Telemóvel"),
				`<a href="tel:${encodeURIComponent(contact.mobile_no)}">${safe_mobile}</a>`
			)
		);
	}
	if (contact.email) {
		const email = frappe.utils.escape_html(contact.email);
		rows.push(
			contact_row(
				"es-line-email",
				__("Email"),
				`<a href="mailto:${encodeURIComponent(contact.email)}">${email}</a>`
			)
		);
	}

	set_customer_contact_html(frm, wrap_contact_field(rows.join("")));
}

function load_customer_contact(frm, { warn = false } = {}) {
	if (!frm.doc.customer_id || frm.doc.project) {
		set_customer_contact_html(frm, "");
		return;
	}

	frm._lp_contact_req = (frm._lp_contact_req || 0) + 1;
	const req = frm._lp_contact_req;

	frappe
		.xcall(
			"logicposintegration.logicpos_integration.task_contact.get_customer_primary_contact",
			{ customer: frm.doc.customer_id }
		)
		.then((contact) => {
			if (req !== frm._lp_contact_req) {
				return;
			}
			render_customer_contact(frm, contact, warn);
		});
}

frappe.ui.form.on("Task", {
	refresh(frm) {
		frm._lp_prev_status_cached = frm.doc.status;
		load_customer_contact(frm, { warn: false });
	},
	customer_id(frm) {
		load_customer_contact(frm, { warn: true });
	},
	project(frm) {
		load_customer_contact(frm, { warn: false });
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
