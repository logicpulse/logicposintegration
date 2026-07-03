import frappe
from frappe.utils import get_datetime, get_fullname
from logicposintegration.logicpos_integration.utils import (
    _format_pos_login_error,
    _get_requests,
    get_pos_auth_headers, 
    get_pos_base_url, 
    get_user_company
) 

POS_STOCK_COMMENT_MARKER = "actualizou o stock no POS"

@frappe.whitelist()
def get_article_by_code(code, company=None):
    requests = _get_requests()

    if not code:
        return {
            "found": False,
            "reason": "Código não informado"
        } 

    try:
        response = requests.get(
            f"{get_pos_base_url(company)}/articles/code/{code}",
            headers=get_pos_auth_headers(with_content_type=False),
            timeout=10
        )
 
        if response.status_code == 404:
            return {
                "found": False,
                "reason": "Artigo não encontrado no POS",
                "code": code
            }

        response.raise_for_status()

        return {
            "found": True,
            "data": response.json()
        }

    except requests.exceptions.RequestException as e:
        frappe.log_error(
            title="Erro técnico ao consumir API do POS",
            message=str(e)
        ) 
        frappe.throw("Erro de comunicação com o POS")

def update_article(code, new_data):
    requests = _get_requests() 

    article = get_article_by_code(code) 
    if not article.get("found"):
        frappe.log_error(
            "Artigo não encontrado no POS",
            f"Código: {code} | reason: {article.get('reason')}",
            "Item",
            code
        ) 
        return

    try:
        article_id = article.get("data").get("id")  
        company_name = get_user_company()
        company_default_currency = frappe.db.get_value("Company", company_name, "default_currency")
        
        payload = { 
            "id": article_id,
            "newPrice1": {
                "value": get_value_by_currency(company_default_currency, new_data)
            }
        }

        # frappe.log(f"🔄 Atualizando artigo no POS, Id: {article_id}, Dados: {payload}")

        response = requests.put(
            url=f"{get_pos_base_url()}/articles/{article_id}",
            json=payload,
			headers=get_pos_auth_headers(),
            timeout=15
        )

        response.raise_for_status()
        # frappe.log(f"✅ Resposta do POS: {response.json()}")
        frappe.log(f"✅ Artigo atualizado com sucesso no POS, Código: {code}")

    except requests.exceptions.RequestException as e:
        frappe.log(f"❌ Erro ao atualizar artigo no POS, Id: {article_id}, Erro: {str(e)}") 
        frappe.log_error(
            message=str(e),
            title=f"Erro ao atualizar artigo no POS ({article_id})"
        )

def get_value_by_currency(currency: str, values: dict) -> float | None:
	currency_map = {
		"MZN": "pvp_mz",
		"KZ": "pvp_ao",
        "AOA": "pvp_ao",
		"EUR": "standard_rate"
	}
	field = currency_map.get(currency.upper())
	if field:
		return values.get(field)
	return None

@frappe.whitelist()
def get_on_hand_total_for_article(code: str, company: str | None = None) -> dict:
    requests = _get_requests()

    if not code:
        return {
            "found": False,
            "reason": "Código não informado"
        } 

    if not company:
        company = get_user_company()

    try:
        response = requests.get(
            f"{get_pos_base_url(company)}/articles/stocks/total",
            headers=get_pos_auth_headers(with_content_type=False),
            params={"code": code},
            timeout=15
        )

        if response.status_code == 400:
            return {
                "found": False,
                "reason": _format_pos_login_error(response),
                "code": code,
            }

        if response.status_code == 404:
            return {
                "found": False,
                "reason": "Artigo não encontrado no POS",
                "code": code,
            }

        response.raise_for_status()

        return {
            "found": True,
            "data": response.json()
        }
    except requests.exceptions.RequestException as e:
        frappe.log_error(
            title="Erro técnico ao consumir API do POS",
            message=str(e)
        ) 
        frappe.throw("Erro de comunicação com o POS")

def _pos_stock_already_updated(purchase_order: str) -> bool:
    return bool(
        frappe.db.exists(
            "Comment",
            {
                "reference_doctype": "Purchase Order",
                "reference_name": purchase_order,
                "comment_type": "Comment",
                "content": ("like", f"%{POS_STOCK_COMMENT_MARKER}%"),
            },
        )
    )

def _finalize_purchase_order_after_pos_stock_sync(purchase_order: str) -> None:
    po = frappe.get_doc("Purchase Order", purchase_order)

    if po.docstatus != 1:
        frappe.throw("A encomenda deve estar submetida")

    user_display = get_fullname(frappe.session.user) or frappe.session.user
    po.add_comment("Comment", f"{user_display} {POS_STOCK_COMMENT_MARKER}")

    if po.status not in ("Cancelled", "Closed"):
        po.update_status("Closed")

def _build_stock_movement_item(item_code: str, qty: float, rate: float, company: str) -> dict:
    article = get_article_by_code(item_code, company)
    if not article.get("found"):
        frappe.throw(f"Artigo {item_code} não encontrado no POS")

    article_id = article.get("data", {}).get("id")
    if not article_id:
        frappe.throw(f"Artigo {item_code} sem ID no POS")

    return {
        "articleId": article_id,
        "quantity": float(qty),
        "price": float(rate),
    }

@frappe.whitelist()
def update_stock(
    supplier_id: str,
    company: str,
    items,
    purchase_order=None,
    date=None,
    document_number=None,
    external_document=None,
):
    requests = _get_requests()

    if not supplier_id or not company:
        frappe.throw("Parâmetros inválidos")

    if not purchase_order:
        frappe.throw("Encomenda de compra não informada")

    if _pos_stock_already_updated(purchase_order):
        frappe.throw("O stock desta encomenda já foi actualizado no POS")

    items = frappe.parse_json(items)
    if not items or not isinstance(items, list):
        frappe.throw("Itens não informados")

    movement_items = []
    for row in items:
        item_code = row.get("item_code")
        if not item_code:
            frappe.throw("Linha sem código de artigo")

        movement_items.append(
            _build_stock_movement_item(
                item_code,
                row.get("qty") or 0,
                row.get("rate") or 0,
                company,
            )
        )

    payload = {
        "supplierId": supplier_id,
        "date": get_datetime(date).isoformat() if date else get_datetime().isoformat(),
        "items": movement_items,
    }

    if document_number:
        payload["documentNumber"] = document_number
    if external_document:
        payload["externalDocument"] = external_document

    try:
        response = requests.post(
            f"{get_pos_base_url(company)}/articles/stocks/movements",
            headers=get_pos_auth_headers(),
            json=payload,
            timeout=30,
        )

        if response.status_code == 400:
            frappe.throw(_format_pos_login_error(response))

        response.raise_for_status()

        data = response.json() if response.content else None
        _finalize_purchase_order_after_pos_stock_sync(purchase_order)

        return {
            "success": True,
            "data": data,
        }
    except frappe.exceptions.ValidationError:
        raise
    except requests.exceptions.RequestException as e:
        frappe.log_error(
            title="Erro técnico ao consumir API do POS",
            message=str(e),
        )
        frappe.throw("Erro de comunicação com o POS")
