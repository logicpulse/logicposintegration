import frappe
from frappe import _

no_cache = 1


def get_context(context):
	context.no_cache = 1
	context.show_sidebar = frappe.session.user != "Guest"
	context.title = _("Inquérito de Satisfação")
	token = frappe.form_dict.get("token") or ""

	from logicposintegration.logicpos_integration.satisfaction_survey import (
		get_survey_for_portal,
	)

	try:
		survey = get_survey_for_portal(token=token)
		context.survey = survey
		context.error = None
	except Exception as e:
		context.survey = None
		context.error = str(e)

	context.metatags = {
		"title": _("Inquérito de Satisfação"),
		"description": _("Preencha o inquérito de satisfação"),
	}
	return context
