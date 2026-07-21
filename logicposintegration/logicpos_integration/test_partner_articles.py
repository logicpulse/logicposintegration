import frappe
from frappe.tests.utils import FrappeTestCase
from unittest.mock import patch


class TestPartnerArticles(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		if not frappe.db.exists("Price List", "PVR-PT"):
			frappe.get_doc(
				{
					"doctype": "Price List",
					"price_list_name": "PVR-PT",
					"selling": 1,
					"currency": "EUR",
					"enabled": 1,
				}
			).insert(ignore_permissions=True)

		if not frappe.db.exists("Item", "_Test Partner Article"):
			frappe.get_doc(
				{
					"doctype": "Item",
					"item_code": "_Test Partner Article",
					"item_name": "_Test Partner Article",
					"item_group": "All Item Groups",
					"stock_uom": "Unit",
					"is_stock_item": 0,
				}
			).insert(ignore_permissions=True)

		if not frappe.db.exists(
			"Item Price",
			{"item_code": "_Test Partner Article", "price_list": "PVR-PT"},
		):
			frappe.get_doc(
				{
					"doctype": "Item Price",
					"item_code": "_Test Partner Article",
					"price_list": "PVR-PT",
					"price_list_rate": 12.5,
					"currency": "EUR",
				}
			).insert(ignore_permissions=True)

	def _ensure_partner_user(self, account_manager="Administrator"):
		email = "partner_articles_test@example.com"
		self.partner_user = email
		if not frappe.db.exists("User", email):
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": "Partner",
					"send_welcome_email": 0,
					"user_type": "Website User",
				}
			)
			user.insert(ignore_permissions=True)
			user.add_roles("Customer")

		customer_name = "_Test Partner Customer"
		if not frappe.db.exists("Customer", customer_name):
			cust = frappe.get_doc(
				{
					"doctype": "Customer",
					"customer_name": customer_name,
					"customer_type": "Company",
					"account_manager": account_manager or None,
					"default_currency": "EUR",
					"tax_id": "PT999999990",
				}
			)
			cust.flags.ignore_mandatory = True
			cust.insert(ignore_permissions=True)
		else:
			frappe.db.set_value(
				"Customer",
				customer_name,
				"account_manager",
				account_manager or "",
			)

		cust = frappe.get_doc("Customer", customer_name)
		if not any(p.user == email for p in cust.get("portal_users") or []):
			cust.append("portal_users", {"user": email})
			cust.flags.ignore_mandatory = True
			cust.save(ignore_permissions=True)

	def test_get_partner_articles_returns_pvr_pt_only(self):
		from logicposintegration.logicpos_integration.partner_articles import (
			get_partner_articles,
		)

		result = get_partner_articles(search="_Test Partner Article", page=1, page_size=24)
		codes = [i["item_code"] for i in result["items"]]
		self.assertIn("_Test Partner Article", codes)
		row = next(i for i in result["items"] if i["item_code"] == "_Test Partner Article")
		self.assertEqual(float(row["price_list_rate"]), 12.5)
		self.assertEqual(result["page"], 1)

	def test_request_partner_quote_rejects_guest_price_tampering(self):
		from logicposintegration.logicpos_integration.partner_articles import (
			request_partner_quote,
		)

		self._ensure_partner_user()
		frappe.set_user(self.partner_user)

		with patch(
			"logicposintegration.logicpos_integration.partner_articles.frappe.sendmail"
		) as sendmail:
			result = request_partner_quote(
				items=[{"item_code": "_Test Partner Article", "qty": 2, "rate": 0.01}],
				notes="Pedido teste",
			)
			self.assertTrue(result["ok"])
			self.assertTrue(sendmail.called)
			_args, kwargs = sendmail.call_args
			html = kwargs.get("message") or ""
			self.assertIn("_Test Partner Article", html)
			self.assertNotIn("0.01", html)
			self.assertIn("Pedido teste", html)

	def test_request_partner_quote_fails_without_recipient(self):
		import logicposintegration.logicpos_integration.partner_articles as mod
		from logicposintegration.logicpos_integration.partner_articles import (
			request_partner_quote,
		)

		self._ensure_partner_user(account_manager=None)
		frappe.set_user(self.partner_user)
		original = mod.PARTNER_QUOTE_FALLBACK_EMAIL
		mod.PARTNER_QUOTE_FALLBACK_EMAIL = ""
		try:
			with self.assertRaises(frappe.ValidationError):
				request_partner_quote(
					items=[{"item_code": "_Test Partner Article", "qty": 1}]
				)
		finally:
			mod.PARTNER_QUOTE_FALLBACK_EMAIL = original
