import re

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils.html_utils import clean_html
from frappe.website.utils import clear_cache

URLS_COMMENT_PATTERN = re.compile(
	r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
	re.IGNORECASE,
)
EMAIL_PATTERN = re.compile(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)", re.IGNORECASE)

PORTAL_COMMENT_DOCTYPES = {
	"Quotation",
	"Sales Order",
	"Sales Invoice",
	"Delivery Note",
	"Issue",
	"Purchase Order",
	"Purchase Invoice",
	"Supplier Quotation",
	"Material Request",
}


def can_comment_on(doctype: str, name: str) -> bool:
	if frappe.session.user == "Guest":
		return False
	if doctype not in PORTAL_COMMENT_DOCTYPES:
		return False
	if not frappe.db.exists(doctype, name):
		return False
	# Portal users usually lack desk DocPerm; website access is what matters.
	doc = frappe.get_doc(doctype, name)
	return bool(frappe.has_website_permission(doc, ptype="read"))


def get_portal_comments(doctype: str, name: str) -> list[dict]:
	if not can_comment_on(doctype, name):
		return []

	return frappe.get_all(
		"Comment",
		fields=["name", "creation", "owner", "comment_email", "comment_by", "content"],
		filters={
			"reference_doctype": doctype,
			"reference_name": name,
			"comment_type": "Comment",
		},
		order_by="creation desc",
		ignore_permissions=True,
	)


def add_portal_comments_to_context(context):
	doc = context.get("doc")
	if not doc:
		return

	context.enable_portal_comments = can_comment_on(doc.doctype, doc.name)
	if not context.enable_portal_comments:
		context.comment_list = []
		context.comment_count = 0
		return

	context.comment_list = get_portal_comments(doc.doctype, doc.name)
	context.comment_count = len(context.comment_list)
	context.reference_doctype = doc.doctype
	context.reference_name = doc.name
	context.guest_allowed = 0


@frappe.whitelist()
@rate_limit(key="reference_name", limit=20, seconds=60 * 60)
def add_portal_comment(comment, comment_email, comment_by, reference_doctype, reference_name, route=None):
	if frappe.session.user == "Guest":
		frappe.throw(_("Please login to post a comment."))

	if not can_comment_on(reference_doctype, reference_name):
		frappe.throw(_("Not Permitted"), frappe.PermissionError)

	comment = (comment or "").strip()
	if not comment:
		frappe.msgprint(_("The comment cannot be empty"))
		return False

	if URLS_COMMENT_PATTERN.search(comment) or EMAIL_PATTERN.search(comment):
		frappe.msgprint(_("Comments cannot have links or email addresses"))
		return False

	doc = frappe.get_doc(reference_doctype, reference_name)
	comment_doc = doc.add_comment(
		text=clean_html(comment),
		comment_email=comment_email or frappe.session.user,
		comment_by=comment_by or frappe.utils.get_fullname(),
	)
	comment_doc.db_set("published", 1)

	if route:
		clear_cache(route)

	template = frappe.get_template("templates/includes/comments/comment.html")
	return template.render({"comment": comment_doc.as_dict()})
