from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _
from frappe.utils import get_url, now_datetime, validate_email_address


def get_default_survey_template() -> str:
	defaults: list[str] = frappe.get_all(
		"Satisfaction Survey Template",
		filters={"is_active": 1, "is_default": 1},
		pluck="name",
		limit=2,
	)
	if len(defaults) == 1:
		return defaults[0]
	if len(defaults) > 1:
		frappe.throw(_("Existe mais do que um modelo de inquérito default ativo."))

	actives: list[str] = frappe.get_all(
		"Satisfaction Survey Template",
		filters={"is_active": 1},
		pluck="name",
		limit=2,
	)
	if len(actives) == 1:
		return actives[0]
	if not actives:
		frappe.throw(_("Não existe nenhum modelo de inquérito ativo."))
	frappe.throw(_("Vários modelos ativos sem default. Marque um como default."))


def resolve_survey_recipients(customer: str | None) -> list[dict[str, Any]]:
	if not customer:
		return []

	recipients: list[dict[str, Any]] = []
	seen: set[str] = set()

	portal_users = frappe.get_all(
		"Portal User",
		filters={"parent": customer, "parenttype": "Customer"},
		fields=["user"],
	)
	for row in portal_users:
		user: str = row.user
		email: str | None = frappe.db.get_value("User", user, "email")
		enabled: int = int(frappe.db.get_value("User", user, "enabled") or 0)
		if not email or not enabled:
			continue
		email_norm = email.strip().lower()
		if email_norm in seen:
			continue
		seen.add(email_norm)
		recipients.append(
			{"email": email.strip(), "user": user, "source": "portal_user"}
		)

	if recipients:
		return recipients

	contact: str | None = frappe.db.get_value(
		"Customer", customer, "customer_primary_contact"
	)
	if not contact:
		from frappe.contacts.doctype.contact.contact import get_default_contact

		contact = get_default_contact("Customer", customer)

	if contact:
		email = frappe.db.get_value("Contact", contact, "email_id")
		if email:
			recipients.append(
				{"email": email.strip(), "user": None, "source": "contact"}
			)

	return recipients


def survey_already_exists_for_project(project: str) -> bool:
	return bool(
		frappe.db.exists(
			{
				"doctype": "Satisfaction Survey",
				"project": project,
				"status": ("in", ["Sent", "Submitted"]),
			}
		)
	)


def survey_already_exists_for_orphan_task(task: str) -> bool:
	rows = frappe.get_all(
		"Satisfaction Survey",
		filters={"task": task, "status": ("in", ["Sent", "Submitted"])},
		fields=["name", "project"],
	)
	return any(not r.project for r in rows)


def _project_context(project_name: str) -> dict[str, Any]:
	project = frappe.db.get_value(
		"Project",
		project_name,
		["name", "project_name", "customer", "status"],
		as_dict=True,
	)
	if not project:
		frappe.throw(_("Project {0} não encontrado.").format(project_name))
	label = project.project_name or project.name
	return {
		"customer": project.customer,
		"project": project.name,
		"task": None,
		"context_label": label,
		"status": project.status,
	}


def _task_context(task_name: str) -> dict[str, Any]:
	task = frappe.db.get_value(
		"Task",
		task_name,
		["name", "subject", "project", "customer_id", "status", "is_group"],
		as_dict=True,
	)
	if not task:
		frappe.throw(_("Task {0} não encontrada.").format(task_name))

	customer: str | None = task.customer_id
	if not customer and task.project:
		customer = frappe.db.get_value("Project", task.project, "customer")

	return {
		"customer": customer,
		"project": task.project,
		"task": task.name,
		"context_label": task.subject or task.name,
		"status": task.status,
		"is_group": int(task.is_group or 0),
	}


@frappe.whitelist()
def is_survey_eligible(reference_doctype: str, reference_name: str) -> dict[str, Any]:
	result: dict[str, Any] = {
		"eligible": False,
		"reason": None,
		"customer": None,
		"project": None,
		"task": None,
		"context_label": None,
	}

	if reference_doctype == "Project":
		ctx = _project_context(reference_name)
		result.update(
			{
				"customer": ctx["customer"],
				"project": ctx["project"],
				"task": None,
				"context_label": ctx["context_label"],
			}
		)
		if ctx["status"] != "Completed":
			result["reason"] = _("O projeto ainda não está concluído.")
			return result
		if survey_already_exists_for_project(ctx["project"]):
			result["reason"] = _("Já existe um inquérito ativo para este projeto.")
			return result
		result["eligible"] = True
		return result

	if reference_doctype == "Task":
		ctx = _task_context(reference_name)
		result.update(
			{
				"customer": ctx["customer"],
				"project": ctx["project"],
				"task": ctx["task"],
				"context_label": ctx["context_label"],
			}
		)
		if not ctx["is_group"]:
			result["reason"] = _("Apenas tarefas de grupo podem gerar inquérito.")
			return result
		if ctx["status"] != "Completed":
			result["reason"] = _("A tarefa ainda não está concluída.")
			return result
		if ctx["project"]:
			if survey_already_exists_for_project(ctx["project"]):
				result["reason"] = _(
					"Já existe um inquérito ativo para o projeto desta tarefa."
				)
				return result
		elif survey_already_exists_for_orphan_task(ctx["task"]):
			result["reason"] = _("Já existe um inquérito ativo para esta tarefa.")
			return result
		result["eligible"] = True
		return result

	result["reason"] = _("Tipo de documento não suportado.")
	return result


@frappe.whitelist()
def get_survey_dialog_context(
	reference_doctype: str, reference_name: str
) -> dict[str, Any]:
	eligibility = is_survey_eligible(reference_doctype, reference_name)
	recipients = resolve_survey_recipients(eligibility.get("customer"))
	eligibility["recipients"] = recipients
	return eligibility


def _snapshot_answers_from_template(template_name: str) -> list[dict[str, Any]]:
	template = frappe.get_doc("Satisfaction Survey Template", template_name)
	rows: list[dict[str, Any]] = []
	for q in template.questions:
		rows.append(
			{
				"question": q.question,
				"question_type": q.question_type,
				"scale_min": q.scale_min,
				"scale_max": q.scale_max,
				"options": q.options,
				"is_mandatory": q.is_mandatory,
			}
		)
	return rows


def _send_survey_email(survey) -> None:
	link = get_url(f"/satisfacao/{survey.access_token}")
	subject = _("Inquérito de satisfação — {0}").format(survey.context_label)
	frappe.sendmail(
		recipients=[survey.recipient_email],
		subject=subject,
		template="satisfaction_survey",
		args={
			"context_label": survey.context_label or "",
			"link": link,
		},
		reference_doctype=survey.doctype,
		reference_name=survey.name,
		now=False
	)


@frappe.whitelist()
def create_and_send_satisfaction_survey(
	reference_doctype: str,
	reference_name: str,
	recipient_email: str,
	recipient_user: str | None = None,
) -> str:
	eligibility = is_survey_eligible(reference_doctype, reference_name)
	if not eligibility.get("eligible"):
		frappe.throw(eligibility.get("reason") or _("Inquérito não elegível."))

	email = validate_email_address(recipient_email, throw=True)
	template_name = get_default_survey_template()
	snapshot = _snapshot_answers_from_template(template_name)

	# is_mandatory is template-only; strip before insert into Answer child
	answer_rows: list[dict[str, Any]] = []
	for row in snapshot:
		answer_rows.append(
			{
				"question": row["question"],
				"question_type": row["question_type"],
				"scale_min": row.get("scale_min"),
				"scale_max": row.get("scale_max"),
				"options": row.get("options"),
			}
		)

	doc = frappe.get_doc(
		{
			"doctype": "Satisfaction Survey",
			"survey_template": template_name,
			"customer": eligibility.get("customer"),
			"project": eligibility.get("project"),
			"task": eligibility.get("task") if reference_doctype == "Task" else None,
			"context_label": eligibility.get("context_label"),
			"recipient_email": email,
			"recipient_user": recipient_user or None,
			"status": "Sent",
			"sent_on": now_datetime(),
			"answers": answer_rows,
		}
	)
	doc.flags.allow_survey_write = True
	doc.insert(ignore_permissions=True)
	_send_survey_email(doc)
	return doc.name


def _load_survey_by_token(token: str):
	name: str | None = frappe.db.get_value(
		"Satisfaction Survey", {"access_token": token}, "name"
	)
	if not name:
		frappe.throw(_("Inquérito inválido ou inexistente."), frappe.DoesNotExistError)
	return frappe.get_doc("Satisfaction Survey", name)


def _portal_customer_for_user() -> str | None:
	if frappe.session.user in ("Guest", "Administrator"):
		customers = frappe.db.get_all(
			"Portal User",
			filters={"user": frappe.session.user, "parenttype": "Customer"},
			pluck="parent",
		)
		# Administrator may have no portal user; allow None
		return customers[0] if customers else None
	customers = frappe.db.get_all(
		"Portal User",
		filters={"user": frappe.session.user, "parenttype": "Customer"},
		pluck="parent",
	)
	return customers[0] if customers else None


def _user_can_access_survey(survey) -> bool:
	if frappe.session.user == "Guest":
		return True  # token gate already applied by caller
	if "System Manager" in frappe.get_roles(frappe.session.user):
		return True
	customer = _portal_customer_for_user()
	return bool(customer and survey.customer == customer)


@frappe.whitelist(allow_guest=True)
def get_survey_for_portal(
	token: str | None = None, name: str | None = None
) -> dict[str, Any]:
	survey = None
	if token:
		survey = _load_survey_by_token(token)
	elif name:
		if frappe.session.user == "Guest":
			frappe.throw(_("Login necessário."), frappe.PermissionError)
		survey = frappe.get_doc("Satisfaction Survey", name)
		if not _user_can_access_survey(survey):
			frappe.throw(_("Sem permissão para este inquérito."), frappe.PermissionError)
	else:
		frappe.throw(_("Token ou nome do inquérito em falta."))

	if survey.status == "Cancelled":
		frappe.throw(_("Este inquérito foi cancelado."))

	questions: list[dict[str, Any]] = []
	for row in survey.answers:
		questions.append(
			{
				"idx": row.idx,
				"name": row.name,
				"question": row.question,
				"question_type": row.question_type,
				"scale_min": row.scale_min if row.scale_min is not None else 0,
				"scale_max": row.scale_max if row.scale_max is not None else 10,
				"options": [
					opt.strip()
					for opt in (row.options or "").split("\n")
					if opt.strip()
				],
				"answer_scale": row.answer_scale,
				"answer_text": row.answer_text,
				"answer_choice": row.answer_choice,
			}
		)

	return {
		"name": survey.name,
		"status": survey.status,
		"context_label": survey.context_label,
		"customer": survey.customer,
		"project": survey.project,
		"task": survey.task,
		"already_submitted": survey.status == "Submitted",
		"questions": questions,
		"access_token": survey.access_token,
	}


@frappe.whitelist()
def list_portal_surveys() -> list[dict[str, Any]]:
	if frappe.session.user == "Guest":
		frappe.throw(_("Login necessário."), frappe.PermissionError)

	customer = _portal_customer_for_user()
	if not customer:
		return []

	return frappe.get_all(
		"Satisfaction Survey",
		filters={
			"customer": customer,
			"status": ("in", ["Sent", "Submitted"]),
		},
		fields=[
			"name",
			"status",
			"context_label",
			"access_token",
			"project",
			"task",
			"sent_on",
			"submitted_on",
		],
		order_by="modified desc",
	)


def _parse_answers(answers: list | str) -> list[dict[str, Any]]:
	if isinstance(answers, str):
		answers = json.loads(answers)
	if not isinstance(answers, list):
		frappe.throw(_("Formato de respostas inválido."))
	return answers


def _choice_options(options_text: str | None) -> list[str]:
	return [opt.strip() for opt in (options_text or "").split("\n") if opt.strip()]


@frappe.whitelist(allow_guest=True)
def submit_satisfaction_survey(token: str, answers: list | str) -> str:
	survey = _load_survey_by_token(token)
	if survey.status == "Submitted":
		frappe.throw(_("Este inquérito já foi submetido."))
	if survey.status != "Sent":
		frappe.throw(_("Este inquérito não está disponível para preenchimento."))

	parsed = _parse_answers(answers)
	by_idx: dict[int, dict[str, Any]] = {}
	for item in parsed:
		idx = int(item.get("idx") or 0)
		if idx:
			by_idx[idx] = item

	# Load mandatory flags from template when available
	mandatory_by_idx: dict[int, int] = {}
	if survey.survey_template and frappe.db.exists(
		"Satisfaction Survey Template", survey.survey_template
	):
		template = frappe.get_doc("Satisfaction Survey Template", survey.survey_template)
		for tq in template.questions:
			mandatory_by_idx[tq.idx] = int(tq.is_mandatory or 0)

	for row in survey.answers:
		payload = by_idx.get(row.idx) or {}
		qtype = row.question_type
		is_mandatory = mandatory_by_idx.get(row.idx, 1)

		if qtype == "Scale":
			value = payload.get("answer_scale")
			if value is None or value == "":
				if is_mandatory:
					frappe.throw(_("Resposta obrigatória: {0}").format(row.question))
				continue
			value_int = int(value)
			scale_min = int(row.scale_min if row.scale_min is not None else 0)
			scale_max = int(row.scale_max if row.scale_max is not None else 10)
			if value_int < scale_min or value_int > scale_max:
				frappe.throw(
					_("Valor fora da escala ({0}–{1}) em: {2}").format(
						scale_min, scale_max, row.question
					)
				)
			row.answer_scale = value_int
		elif qtype == "Text":
			text = (payload.get("answer_text") or "").strip()
			if not text and is_mandatory:
				frappe.throw(_("Resposta obrigatória: {0}").format(row.question))
			row.answer_text = text
		elif qtype == "Choice":
			choice = (payload.get("answer_choice") or "").strip()
			if not choice and is_mandatory:
				frappe.throw(_("Resposta obrigatória: {0}").format(row.question))
			allowed = _choice_options(row.options)
			if choice and allowed and choice not in allowed:
				frappe.throw(_("Opção inválida em: {0}").format(row.question))
			row.answer_choice = choice

	survey.status = "Submitted"
	survey.submitted_on = now_datetime()
	if frappe.session.user and frappe.session.user != "Guest":
		survey.submitted_by = frappe.session.user
	survey.flags.allow_survey_write = True
	survey.save(ignore_permissions=True)
	return survey.name
