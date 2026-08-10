from __future__ import annotations

import frappe
from frappe import _
from frappe.model.document import Document


class SatisfactionSurveyTemplate(Document):
	def validate(self) -> None:
		self._validate_questions()
		self._validate_single_default()

	def _validate_questions(self) -> None:
		if not self.questions:
			frappe.throw(_("O modelo precisa de pelo menos uma pergunta."))
		for row in self.questions:
			if row.question_type == "Scale":
				scale_min: int = int(row.scale_min or 0)
				scale_max: int = int(row.scale_max or 10)
				if scale_min >= scale_max:
					frappe.throw(_("Scale min deve ser menor que scale max."))
				row.scale_min = scale_min
				row.scale_max = scale_max
			if row.question_type == "Choice" and not (row.options or "").strip():
				frappe.throw(_("Perguntas Choice precisam de opções (uma por linha)."))

	def _validate_single_default(self) -> None:
		if not self.is_default or not self.is_active:
			return
		others: list[str] = frappe.get_all(
			"Satisfaction Survey Template",
			filters={"is_default": 1, "is_active": 1, "name": ("!=", self.name)},
			pluck="name",
		)
		if others:
			frappe.throw(_("Já existe um modelo default ativo: {0}").format(others[0]))
