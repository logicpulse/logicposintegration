from __future__ import annotations

import secrets

import frappe
from frappe import _
from frappe.model.document import Document


class SatisfactionSurvey(Document):
	def before_insert(self) -> None:
		if not self.access_token:
			self.access_token = secrets.token_urlsafe(32)

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
