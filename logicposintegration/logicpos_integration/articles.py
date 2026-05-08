import frappe
from logicposintegration.logicpos_integration.utils import (
    _get_requests,
    get_pos_auth_headers, 
    get_pos_base_url, 
    get_user_company
) 

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