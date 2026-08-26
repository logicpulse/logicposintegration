from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _
from frappe.utils import flt
from erpnext.controllers.accounts_controller import (
	update_child_qty_rate as erpnext_update_child_qty_rate,
)

DISCOUNT_MIN = 0.0
DISCOUNT_MAX = 100.0


@frappe.whitelist()
def update_child_qty_rate(
	parent_doctype: str,
	trans_items: str,
	parent_doctype_name: str,
	child_docname: str = "items",
) -> Any:
	rows = _parse_trans_items(trans_items)
	if parent_doctype == "Quotation":
		rows = prepare_quotation_trans_items(rows)
		trans_items = json.dumps(rows)

	result = erpnext_update_child_qty_rate(
		parent_doctype, trans_items, parent_doctype_name, child_docname
	)

	if parent_doctype == "Quotation":
		_apply_discount_to_new_items(parent_doctype_name, rows)

	return result


def prepare_quotation_trans_items(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
	"""Recompute rate from discount % and persist it on existing quotation items."""
	children_by_name: dict[str, Any] = {}
	for row in rows:
		docname = row.get("docname")
		if docname:
			children_by_name[str(docname)] = frappe.get_doc("Quotation Item", docname)

	for row in rows:
		if not row.get("item_code"):
			continue
		child = children_by_name.get(str(row.get("docname") or ""))
		apply_discount_to_row(row, child)

	for row in rows:
		child = children_by_name.get(str(row.get("docname") or ""))
		if not child or not _has_discount_percentage(row):
			continue
		frappe.db.set_value(
			"Quotation Item",
			child.name,
			{
				"discount_percentage": flt(row["discount_percentage"]),
				"discount_amount": flt(row.get("discount_amount")),
			},
			update_modified=False,
		)

	return rows


def apply_discount_to_row(row: dict[str, Any], child: Any | None = None) -> dict[str, Any]:
	"""If discount % is present, validate it and recompute rate from the list price."""
	if not _has_discount_percentage(row):
		return row

	discount_percentage = flt(row.get("discount_percentage"))
	if discount_percentage < DISCOUNT_MIN or discount_percentage > DISCOUNT_MAX:
		frappe.throw(
			_("O desconto (%) tem de estar entre {0} e {1}.").format(DISCOUNT_MIN, DISCOUNT_MAX),
			title=_("Desconto inválido"),
		)

	row["discount_percentage"] = discount_percentage
	base_rate = _base_rate_for_discount(child, row)
	if not base_rate:
		return row

	row["discount_amount"] = flt(base_rate * discount_percentage / 100.0)
	row["rate"] = flt(base_rate * (1.0 - discount_percentage / 100.0))
	return row


def _parse_trans_items(trans_items: str | list[dict[str, Any]]) -> list[dict[str, Any]]:
	if isinstance(trans_items, str):
		parsed: Any = json.loads(trans_items)
		return list(parsed)
	return list(trans_items)


def _has_discount_percentage(row: dict[str, Any]) -> bool:
	return "discount_percentage" in row and row.get("discount_percentage") is not None


def _base_rate_for_discount(child: Any | None, row: dict[str, Any]) -> float:
	rate_with_margin = flt(row.get("rate_with_margin"))
	price_list_rate = flt(row.get("price_list_rate"))
	if child:
		rate_with_margin = rate_with_margin or flt(child.get("rate_with_margin"))
		price_list_rate = price_list_rate or flt(child.get("price_list_rate"))
	return rate_with_margin or price_list_rate


def _apply_discount_to_new_items(parent_name: str, rows: list[dict[str, Any]]) -> None:
	new_rows = [
		row
		for row in rows
		if row.get("item_code") and not row.get("docname") and _has_discount_percentage(row)
	]
	if not new_rows:
		return

	parent = frappe.get_doc("Quotation", parent_name)
	existing_names = {str(row.get("docname")) for row in rows if row.get("docname")}
	new_children = [item for item in parent.items if item.name not in existing_names]
	if len(new_children) < len(new_rows):
		return

	changed = False
	for row, child in zip(new_rows, new_children[-len(new_rows) :]):
		if child.item_code != row.get("item_code"):
			continue
		apply_discount_to_row(row, child)
		child.discount_percentage = flt(row.get("discount_percentage"))
		child.discount_amount = flt(row.get("discount_amount"))
		if row.get("rate") is not None:
			child.rate = flt(row["rate"])
		changed = True

	if not changed:
		return

	parent.flags.ignore_validate_update_after_submit = True
	parent.calculate_taxes_and_totals()
	parent.set_total_in_words()
	parent.save()
