from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase


class TestSatisfactionSurveyAPI(FrappeTestCase):
	def setUp(self) -> None:
		frappe.set_user("Administrator")
		self._cleanup()

	def tearDown(self) -> None:
		frappe.set_user("Administrator")
		self._cleanup()

	def _cleanup(self) -> None:
		for name in frappe.get_all(
			"Satisfaction Survey",
			filters={"context_label": ("like", "_Test Sat%")},
			pluck="name",
		):
			frappe.delete_doc("Satisfaction Survey", name, force=1, ignore_permissions=True)
		for name in frappe.get_all(
			"Satisfaction Survey Template",
			filters={"title": ("like", "_Test Sat%")},
			pluck="name",
		):
			frappe.delete_doc(
				"Satisfaction Survey Template", name, force=1, ignore_permissions=True
			)
		for subject in ("_Test Sat Orphan Task", "_Test Sat Group Task"):
			for name in frappe.get_all("Task", filters={"subject": subject}, pluck="name"):
				frappe.db.set_value("Task", name, "project", None)
				frappe.delete_doc("Task", name, force=1, ignore_permissions=True)
		for name in frappe.get_all(
			"Project", filters={"project_name": "_Test Sat Project"}, pluck="name"
		):
			frappe.delete_doc("Project", name, force=1, ignore_permissions=True)
		for doctype, name in (
			("Customer", "_Test Sat Customer"),
			("Customer", "_Test Sat Contact Customer"),
			("Contact", "_Test Sat Contact"),
			("User", "sat.portal@example.com"),
		):
			if frappe.db.exists(doctype, name):
				frappe.delete_doc(doctype, name, force=1, ignore_permissions=True)

	def _ensure_template(
		self, title: str, *, is_default: int = 0, is_active: int = 1
	) -> str:
		existing = frappe.db.get_value(
			"Satisfaction Survey Template", {"title": title}, "name"
		)
		if existing:
			doc = frappe.get_doc("Satisfaction Survey Template", existing)
			doc.is_default = is_default
			doc.is_active = is_active
			doc.save(ignore_permissions=True)
			return doc.name

		doc = frappe.get_doc(
			{
				"doctype": "Satisfaction Survey Template",
				"title": title,
				"is_active": is_active,
				"is_default": is_default,
				"questions": [
					{
						"question": "Assunto?",
						"question_type": "Choice",
						"options": "Hardware\nSoftware\nOutros",
						"is_mandatory": 1,
					},
					{
						"question": "Resolvido?",
						"question_type": "Scale",
						"scale_min": 0,
						"scale_max": 10,
						"is_mandatory": 1,
					},
					{
						"question": "Comentários",
						"question_type": "Text",
						"is_mandatory": 0,
					},
				],
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name

	def _ensure_customer_with_portal(self) -> str:
		email = "sat.portal@example.com"
		if not frappe.db.exists("User", email):
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": email,
					"first_name": "Sat",
					"last_name": "Portal",
					"send_welcome_email": 0,
					"user_type": "Website User",
				}
			)
			user.insert(ignore_permissions=True)
			user.add_roles("Customer")

		customer_name = "_Test Sat Customer"
		if not frappe.db.exists("Customer", customer_name):
			cust = frappe.get_doc(
				{
					"doctype": "Customer",
					"customer_name": customer_name,
					"customer_type": "Company",
					"territory": "All Territories",
				}
			)
			cust.flags.ignore_mandatory = True
			cust.insert(ignore_permissions=True)
		else:
			cust = frappe.get_doc("Customer", customer_name)

		if not any(p.user == email for p in cust.get("portal_users") or []):
			cust.append("portal_users", {"user": email})
			cust.flags.ignore_mandatory = True
			cust.save(ignore_permissions=True)
		return customer_name

	def _ensure_customer_with_contact_only(self) -> str:
		customer_name = "_Test Sat Contact Customer"
		if frappe.db.exists("Customer", customer_name):
			cust = frappe.get_doc("Customer", customer_name)
			cust.set("portal_users", [])
			cust.flags.ignore_mandatory = True
			cust.save(ignore_permissions=True)
		else:
			cust = frappe.get_doc(
				{
					"doctype": "Customer",
					"customer_name": customer_name,
					"customer_type": "Company",
					"territory": "All Territories",
				}
			)
			cust.flags.ignore_mandatory = True
			cust.insert(ignore_permissions=True)

		contact_name = "_Test Sat Contact"
		if frappe.db.exists("Contact", contact_name):
			frappe.delete_doc("Contact", contact_name, force=1, ignore_permissions=True)
		contact = frappe.get_doc(
			{
				"doctype": "Contact",
				"first_name": "Sat",
				"last_name": "Contact",
				"email_ids": [{"email_id": "sat.contact@example.com", "is_primary": 1}],
				"links": [{"link_doctype": "Customer", "link_name": customer_name}],
			}
		)
		contact.insert(ignore_permissions=True)
		frappe.db.set_value(
			"Customer", customer_name, "customer_primary_contact", contact.name
		)
		return customer_name

	def _ensure_completed_project(self, customer: str) -> str:
		project_name = "_Test Sat Project"
		existing = frappe.db.get_value("Project", {"project_name": project_name}, "name")
		if existing:
			frappe.db.set_value(
				"Project",
				existing,
				{"customer": customer, "status": "Completed"},
			)
			return existing
		doc = frappe.get_doc(
			{
				"doctype": "Project",
				"project_name": project_name,
				"customer": customer,
				"status": "Completed",
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name

	def _ensure_orphan_group_task(self, *, status: str = "Completed") -> str:
		from frappe.utils import add_days, today

		subject = "_Test Sat Orphan Task"
		existing = frappe.db.get_value("Task", {"subject": subject}, "name")
		if existing:
			frappe.db.set_value(
				"Task",
				existing,
				{
					"is_group": 1,
					"status": status,
					"project": "",
					"customer_id": "",
				},
			)
			return existing
		doc = frappe.get_doc(
			{
				"doctype": "Task",
				"subject": subject,
				"is_group": 1,
				"status": status,
				"exp_start_date": today(),
				"exp_end_date": add_days(today(), 7),
			}
		)
		doc.insert(ignore_permissions=True)
		return doc.name

	def test_get_default_template_prefers_is_default(self) -> None:
		from logicposintegration.logicpos_integration.satisfaction_survey import (
			get_default_survey_template,
		)

		other = self._ensure_template("_Test Sat Template Other", is_default=0)
		default = self._ensure_template("_Test Sat Template Default", is_default=1)
		self.assertEqual(get_default_survey_template(), default)
		self.assertNotEqual(get_default_survey_template(), other)

	def test_get_default_template_ambiguous_raises(self) -> None:
		from logicposintegration.logicpos_integration.satisfaction_survey import (
			get_default_survey_template,
		)

		self._ensure_template("_Test Sat Template A", is_default=0)
		self._ensure_template("_Test Sat Template B", is_default=0)
		with self.assertRaises(frappe.ValidationError):
			get_default_survey_template()

	def test_resolve_recipients_portal_user_first(self) -> None:
		from logicposintegration.logicpos_integration.satisfaction_survey import (
			resolve_survey_recipients,
		)

		customer = self._ensure_customer_with_portal()
		recipients = resolve_survey_recipients(customer)
		self.assertTrue(recipients)
		self.assertEqual(recipients[0]["email"], "sat.portal@example.com")
		self.assertEqual(recipients[0]["source"], "portal_user")

	def test_resolve_recipients_falls_back_to_contact(self) -> None:
		from logicposintegration.logicpos_integration.satisfaction_survey import (
			resolve_survey_recipients,
		)

		customer = self._ensure_customer_with_contact_only()
		recipients = resolve_survey_recipients(customer)
		self.assertTrue(recipients)
		self.assertEqual(recipients[0]["email"], "sat.contact@example.com")
		self.assertEqual(recipients[0]["source"], "contact")

	def test_eligible_project_completed_without_existing_survey(self) -> None:
		from logicposintegration.logicpos_integration.satisfaction_survey import (
			is_survey_eligible,
		)

		customer = self._ensure_customer_with_portal()
		project = self._ensure_completed_project(customer)
		result = is_survey_eligible("Project", project)
		self.assertTrue(result["eligible"])
		self.assertEqual(result["customer"], customer)

	def test_not_eligible_when_project_survey_exists(self) -> None:
		from logicposintegration.logicpos_integration.satisfaction_survey import (
			create_and_send_satisfaction_survey,
			is_survey_eligible,
		)

		self._ensure_template("_Test Sat Template Default", is_default=1)
		customer = self._ensure_customer_with_portal()
		project = self._ensure_completed_project(customer)
		with patch("frappe.sendmail"):
			create_and_send_satisfaction_survey(
				"Project", project, "sat.portal@example.com", "sat.portal@example.com"
			)
		result = is_survey_eligible("Project", project)
		self.assertFalse(result["eligible"])

	def test_eligible_orphan_group_task(self) -> None:
		from logicposintegration.logicpos_integration.satisfaction_survey import (
			is_survey_eligible,
		)

		task = self._ensure_orphan_group_task(status="Completed")
		result = is_survey_eligible("Task", task)
		self.assertTrue(result["eligible"])
		self.assertEqual(result["task"], task)
		self.assertFalse(result["project"])

	def test_group_task_with_project_not_eligible_if_project_survey_exists(self) -> None:
		from logicposintegration.logicpos_integration.satisfaction_survey import (
			create_and_send_satisfaction_survey,
			is_survey_eligible,
		)

		self._ensure_template("_Test Sat Template Default", is_default=1)
		customer = self._ensure_customer_with_portal()
		project = self._ensure_completed_project(customer)
		with patch("frappe.sendmail"):
			create_and_send_satisfaction_survey(
				"Project", project, "sat.portal@example.com"
			)

		from frappe.utils import add_days, today

		subject = "_Test Sat Group Task"
		task_name = frappe.db.get_value("Task", {"subject": subject}, "name")
		if task_name:
			frappe.db.set_value(
				"Task",
				task_name,
				{"project": project, "is_group": 1, "status": "Completed"},
			)
		else:
			task_name = (
				frappe.get_doc(
					{
						"doctype": "Task",
						"subject": subject,
						"project": project,
						"is_group": 1,
						"status": "Completed",
						"exp_start_date": today(),
						"exp_end_date": add_days(today(), 7),
					}
				)
				.insert(ignore_permissions=True)
				.name
			)

		result = is_survey_eligible("Task", task_name)
		self.assertFalse(result["eligible"])

	def test_create_and_send_creates_sent_survey_with_snapshot(self) -> None:
		from logicposintegration.logicpos_integration.satisfaction_survey import (
			create_and_send_satisfaction_survey,
		)

		self._ensure_template("_Test Sat Template Default", is_default=1)
		customer = self._ensure_customer_with_portal()
		project = self._ensure_completed_project(customer)
		with patch("frappe.sendmail") as sendmail:
			name = create_and_send_satisfaction_survey(
				"Project", project, "sat.portal@example.com", "sat.portal@example.com"
			)
			self.assertTrue(sendmail.called)

		doc = frappe.get_doc("Satisfaction Survey", name)
		self.assertEqual(doc.status, "Sent")
		self.assertTrue(doc.access_token)
		self.assertEqual(len(doc.answers), 3)
		self.assertEqual(doc.answers[0].question_type, "Choice")

	def test_create_and_send_rejects_duplicate_project(self) -> None:
		from logicposintegration.logicpos_integration.satisfaction_survey import (
			create_and_send_satisfaction_survey,
		)

		self._ensure_template("_Test Sat Template Default", is_default=1)
		customer = self._ensure_customer_with_portal()
		project = self._ensure_completed_project(customer)
		with patch("frappe.sendmail"):
			create_and_send_satisfaction_survey(
				"Project", project, "sat.portal@example.com"
			)
			with self.assertRaises(frappe.ValidationError):
				create_and_send_satisfaction_survey(
					"Project", project, "sat.portal@example.com"
				)

	def test_submit_marks_submitted_and_rejects_second(self) -> None:
		from logicposintegration.logicpos_integration.satisfaction_survey import (
			create_and_send_satisfaction_survey,
			submit_satisfaction_survey,
		)

		self._ensure_template("_Test Sat Template Default", is_default=1)
		customer = self._ensure_customer_with_portal()
		project = self._ensure_completed_project(customer)
		with patch("frappe.sendmail"):
			name = create_and_send_satisfaction_survey(
				"Project", project, "sat.portal@example.com"
			)
		token = frappe.db.get_value("Satisfaction Survey", name, "access_token")
		answers = [
			{"idx": 1, "answer_choice": "Hardware"},
			{"idx": 2, "answer_scale": 8},
			{"idx": 3, "answer_text": "Bom trabalho"},
		]
		submit_satisfaction_survey(token, answers)
		doc = frappe.get_doc("Satisfaction Survey", name)
		self.assertEqual(doc.status, "Submitted")
		self.assertEqual(doc.answers[0].answer_choice, "Hardware")
		self.assertEqual(doc.answers[1].answer_scale, 8)
		with self.assertRaises(frappe.ValidationError):
			submit_satisfaction_survey(token, answers)

	def test_submit_validates_mandatory_answers(self) -> None:
		from logicposintegration.logicpos_integration.satisfaction_survey import (
			create_and_send_satisfaction_survey,
			submit_satisfaction_survey,
		)

		self._ensure_template("_Test Sat Template Default", is_default=1)
		customer = self._ensure_customer_with_portal()
		project = self._ensure_completed_project(customer)
		with patch("frappe.sendmail"):
			name = create_and_send_satisfaction_survey(
				"Project", project, "sat.portal@example.com"
			)
		token = frappe.db.get_value("Satisfaction Survey", name, "access_token")
		with self.assertRaises(frappe.ValidationError):
			submit_satisfaction_survey(
				token,
				[{"idx": 1, "answer_choice": ""}, {"idx": 2, "answer_scale": None}],
			)
