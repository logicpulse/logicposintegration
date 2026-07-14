from erpnext.templates.pages.order import get_context as erpnext_get_context

from logicposintegration.utils.portal_comments import add_portal_comments_to_context


def get_context(context):
	erpnext_get_context(context)
	add_portal_comments_to_context(context)
	return context
