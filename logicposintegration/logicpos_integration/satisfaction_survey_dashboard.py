from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import flt


def _normalized_scale_score(
	answer_scale: int | float | None,
	scale_min: int | float | None,
	scale_max: int | float | None,
) -> float | None:
	if answer_scale is None:
		return None
	low: float = float(scale_min if scale_min is not None else 0)
	high: float = float(scale_max if scale_max is not None else 10)
	if high <= low:
		return None
	return (float(answer_scale) - low) / (high - low) * 10.0


def compute_average_scale(rows: list[dict[str, Any]]) -> float:
	scores: list[float] = []
	for row in rows:
		normalized = _normalized_scale_score(
			row.get("answer_scale"),
			row.get("scale_min"),
			row.get("scale_max"),
		)
		if normalized is not None:
			scores.append(normalized)
	if not scores:
		return 0.0
	return flt(sum(scores) / len(scores), 1)


def compute_response_rate(sent_count: int, submitted_count: int) -> float:
	total: int = int(sent_count) + int(submitted_count)
	if total <= 0:
		return 0.0
	return flt(float(submitted_count) / float(total) * 100.0, 1)


def _ensure_survey_read() -> None:
	frappe.has_permission("Satisfaction Survey", ptype="read", throw=True)


@frappe.whitelist()
def get_survey_response_rate(filters: list | str | None = None) -> dict[str, Any]:
	_ensure_survey_read()
	sent_count: int = frappe.db.count("Satisfaction Survey", {"status": "Sent"})
	submitted_count: int = frappe.db.count("Satisfaction Survey", {"status": "Submitted"})
	return {
		"value": compute_response_rate(sent_count, submitted_count),
		"fieldtype": "Percent",
		"route": ["List", "Satisfaction Survey", "List"],
		"route_options": {"status": ["in", ["Sent", "Submitted"]]},
	}


@frappe.whitelist()
def get_survey_average_score(filters: list | str | None = None) -> dict[str, Any]:
	_ensure_survey_read()
	rows: list[dict[str, Any]] = frappe.db.sql(
		"""
		select a.answer_scale, a.scale_min, a.scale_max
		from `tabSatisfaction Survey Answer` a
		inner join `tabSatisfaction Survey` s on s.name = a.parent
		where s.status = 'Submitted'
			and a.question_type = 'Scale'
			and a.answer_scale is not null
		""",
		as_dict=True,
	)
	return {
		"value": compute_average_scale(rows),
		"fieldtype": "Float",
		"precision": 1,
		"route": ["List", "Satisfaction Survey", "List"],
		"route_options": {"status": "Submitted"},
	}
