from __future__ import annotations

import secrets

import frappe
from frappe import _
from frappe.model.document import Document


def _is_system_admin() -> bool:
	if frappe.session.user == "Administrator":
		return True
	return "System Manager" in frappe.get_roles(frappe.session.user)


class SatisfactionSurvey(Document):
	def before_insert(self) -> None:
		if not self.access_token:
			self.access_token = secrets.token_urlsafe(32)
		self._ensure_system_write()

	def before_save(self) -> None:
		if self.is_new():
			return
		self._ensure_system_write()

	def on_trash(self) -> None:
		if frappe.flags.in_test:
			return
		if not _is_system_admin():
			frappe.throw(_("Apenas o administrador pode remover um inquérito de satisfação."))

	def _ensure_system_write(self) -> None:
		"""Desk users (incluindo admin) não editam; só a API interna pode gravar."""
		if self.flags.allow_survey_write:
			return
		frappe.throw(_("Não é permitido editar um inquérito de satisfação."))

	def validate(self) -> None:
		self._validate_dedupe()

	def _validate_dedupe(self) -> None:
		if self.status not in ("Sent", "Submitted"):
			return
		if self.project:
			rows: list[str] = frappe.get_all(
				"Satisfaction Survey",
				filters={
					"project": self.project,
					"status": ("in", ["Sent", "Submitted"]),
					"name": ("!=", self.name or ""),
				},
				pluck="name",
				limit=1,
			)
			if rows:
				frappe.throw(
					_("Já existe um inquérito ativo para o projeto {0}.").format(self.project)
				)
			return
		if self.task:
			rows_task: list[dict] = frappe.get_all(
				"Satisfaction Survey",
				filters={
					"task": self.task,
					"status": ("in", ["Sent", "Submitted"]),
					"name": ("!=", self.name or ""),
				},
				fields=["name", "project"],
				limit=5,
			)
			for row in rows_task:
				if not row.project:
					frappe.throw(
						_("Já existe um inquérito ativo para a tarefa {0}.").format(self.task)
					)
