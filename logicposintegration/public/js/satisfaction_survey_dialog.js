frappe.logicpos = frappe.logicpos || {};

frappe.logicpos.offer_satisfaction_survey = function (reference_doctype, reference_name) {
	frappe.call({
		method:
			"logicposintegration.logicpos_integration.satisfaction_survey.get_survey_dialog_context",
		args: { reference_doctype, reference_name },
		callback: function (r) {
			const ctx = r.message;
			if (!ctx || !ctx.eligible) {
				if (ctx && ctx.reason) {
					frappe.show_alert({ message: ctx.reason, indicator: "orange" });
				}
				return;
			}

			const emails = (ctx.recipients || []).map((x) => x.email).filter(Boolean);
			const default_email =
				(ctx.recipients && ctx.recipients[0] && ctx.recipients[0].email) || "";

			const fields = [
				{
					fieldtype: "HTML",
					options: `<p>${__("Contexto")}: <strong>${frappe.utils.escape_html(
						ctx.context_label || ""
					)}</strong></p>`,
				},
				{
					label: __("Email do cliente"),
					fieldname: "recipient_email",
					fieldtype: "Data",
					reqd: 1,
					default: default_email,
					options: "Email",
				},
			];

			if (emails.length) {
				fields.push({
					label: __("Sugestões"),
					fieldname: "email_suggestions",
					fieldtype: "Select",
					options: emails.join("\n"),
					default: default_email,
				});
			}

			const d = new frappe.ui.Dialog({
				title: __("Enviar inquérito de satisfação?"),
				fields: fields,
				primary_action_label: __("Enviar"),
				primary_action(values) {
					const email = values.recipient_email;
					const match = (ctx.recipients || []).find((x) => x.email === email);
					frappe.call({
						method:
							"logicposintegration.logicpos_integration.satisfaction_survey.create_and_send_satisfaction_survey",
						args: {
							reference_doctype,
							reference_name,
							recipient_email: email,
							recipient_user: match ? match.user : null,
						},
						freeze: true,
						callback: function () {
							frappe.show_alert({
								message: __("Inquérito enviado"),
								indicator: "green",
							});
							d.hide();
						},
					});
				},
				secondary_action_label: __("Não enviar"),
				secondary_action() {
					d.hide();
				},
			});

			if (d.fields_dict.email_suggestions) {
				d.fields_dict.email_suggestions.$input.on("change", function () {
					d.set_value("recipient_email", d.get_value("email_suggestions"));
				});
			}

			d.show();
		},
	});
};
