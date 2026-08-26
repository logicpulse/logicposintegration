from __future__ import annotations

import json

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from logicposintegration.overrides.quotation import update_child_qty_rate

CUSTOMER_NAME = "_Test Qtn Discount Customer"
ITEM_CODE = "_Test Qtn Discount Item"
COMPANY = "Logicpulse PT"
PRICE_LIST = "PVR-PT"


class TestQuotationUpdateItemsDiscount(FrappeTestCase):
	def setUp(self) -> None:
		frappe.set_user("Administrator")
		self._cleanup()
		self._ensure_fixtures()

	def tearDown(self) -> None:
		frappe.set_user("Administrator")
		self._cleanup()

	def test_update_discount_recalculates_rate_and_amount(self) -> None:
		quotation = self._make_submitted_quotation(qty=2, price_list_rate=1000, discount_percentage=10)
		item = quotation.items[0]
		self.assertEqual(flt(item.rate, 2), 900.0)

		update_child_qty_rate(
			"Quotation",
			json.dumps(
				[
					{
						"item_code": item.item_code,
						"qty": item.qty,
						"rate": item.rate,
						"docname": item.name,
						"discount_percentage": 25,
						"price_list_rate": item.price_list_rate,
					}
				]
			),
			quotation.name,
		)

		quotation.reload()
		updated = quotation.items[0]
		self.assertEqual(flt(updated.discount_percentage, 2), 25.0)
		self.assertEqual(flt(updated.rate, 2), 750.0)
		self.assertEqual(flt(updated.discount_amount, 2), 250.0)
		self.assertEqual(flt(updated.amount, 2), 1500.0)
		self.assertEqual(flt(quotation.net_total, 2), 1500.0)

	def test_clearing_discount_restores_list_price(self) -> None:
		quotation = self._make_submitted_quotation(qty=1, price_list_rate=400, discount_percentage=20)
		item = quotation.items[0]

		update_child_qty_rate(
			"Quotation",
			json.dumps(
				[
					{
						"item_code": item.item_code,
						"qty": item.qty,
						"rate": item.rate,
						"docname": item.name,
						"discount_percentage": 0,
						"price_list_rate": item.price_list_rate,
					}
				]
			),
			quotation.name,
		)

		quotation.reload()
		updated = quotation.items[0]
		self.assertEqual(flt(updated.discount_percentage, 2), 0.0)
		self.assertEqual(flt(updated.rate, 2), 400.0)
		self.assertEqual(flt(updated.amount, 2), 400.0)

	def test_invalid_discount_is_rejected(self) -> None:
		quotation = self._make_submitted_quotation(qty=1, price_list_rate=100, discount_percentage=0)
		item = quotation.items[0]
		payload = json.dumps(
			[
				{
					"item_code": item.item_code,
					"qty": item.qty,
					"rate": item.rate,
					"docname": item.name,
					"discount_percentage": 150,
					"price_list_rate": item.price_list_rate,
				}
			]
		)

		self.assertRaises(
			frappe.ValidationError,
			update_child_qty_rate,
			"Quotation",
			payload,
			quotation.name,
		)

		quotation.reload()
		self.assertEqual(flt(quotation.items[0].discount_percentage, 2), 0.0)
		self.assertEqual(flt(quotation.items[0].rate, 2), 100.0)

	def test_qty_update_without_discount_change_still_works(self) -> None:
		quotation = self._make_submitted_quotation(qty=2, price_list_rate=100, discount_percentage=10)
		item = quotation.items[0]

		update_child_qty_rate(
			"Quotation",
			json.dumps(
				[
					{
						"item_code": item.item_code,
						"qty": 5,
						"rate": item.rate,
						"docname": item.name,
						"discount_percentage": item.discount_percentage,
						"price_list_rate": item.price_list_rate,
					}
				]
			),
			quotation.name,
		)

		quotation.reload()
		updated = quotation.items[0]
		self.assertEqual(flt(updated.qty, 2), 5.0)
		self.assertEqual(flt(updated.discount_percentage, 2), 10.0)
		self.assertEqual(flt(updated.rate, 2), 90.0)
		self.assertEqual(flt(updated.amount, 2), 450.0)

	def _ensure_fixtures(self) -> None:
		if not frappe.db.exists("Item", ITEM_CODE):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": ITEM_CODE,
					"item_name": ITEM_CODE,
					"item_group": "All Item Groups",
					"stock_uom": "Unit",
					"is_stock_item": 0,
					"is_sales_item": 1,
				}
			).insert(ignore_permissions=True)

		if not frappe.db.exists("Customer", CUSTOMER_NAME):
			customer = frappe.get_doc(
				{
					"doctype": "Customer",
					"customer_name": CUSTOMER_NAME,
					"customer_type": "Company",
					"customer_group": "Commercial",
					"default_currency": "EUR",
					"tax_id": "PT999999991",
				}
			)
			customer.flags.ignore_mandatory = True
			customer.insert(ignore_permissions=True)

		if not frappe.db.exists(
			"Item Price",
			{"item_code": ITEM_CODE, "price_list": PRICE_LIST},
		):
			frappe.get_doc(
				{
					"doctype": "Item Price",
					"item_code": ITEM_CODE,
					"price_list": PRICE_LIST,
					"price_list_rate": 1000,
					"currency": "EUR",
				}
			).insert(ignore_permissions=True)

	def _make_submitted_quotation(
		self,
		qty: float,
		price_list_rate: float,
		discount_percentage: float,
	) -> frappe.Document:
		rate = flt(price_list_rate * (1.0 - discount_percentage / 100.0))
		quotation = frappe.get_doc(
			{
				"doctype": "Quotation",
				"quotation_to": "Customer",
				"party_name": CUSTOMER_NAME,
				"company": COMPANY,
				"currency": "EUR",
				"conversion_rate": 1,
				"selling_price_list": PRICE_LIST,
				"price_list_currency": "EUR",
				"plc_conversion_rate": 1,
				"order_type": "Sales",
				"ignore_pricing_rule": 1,
				"items": [
					{
						"item_code": ITEM_CODE,
						"qty": qty,
						"uom": "Unit",
						"price_list_rate": price_list_rate,
						"discount_percentage": discount_percentage,
						"rate": rate,
					}
				],
			}
		)
		quotation.insert(ignore_permissions=True)
		quotation.submit()
		quotation.reload()
		return quotation

	def _cleanup(self) -> None:
		for name in frappe.get_all(
			"Quotation",
			filters={"party_name": CUSTOMER_NAME},
			pluck="name",
		):
			doc = frappe.get_doc("Quotation", name)
			if doc.docstatus == 1:
				doc.cancel()
			frappe.delete_doc("Quotation", name, force=1, ignore_permissions=True)
