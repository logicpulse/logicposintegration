import frappe
from logicposintegration.logicpos_integration.utils import (
    _get_requests, 
    get_pos_base_url
)

@frappe.whitelist()
def get_article_by_code(code):
    requests = _get_requests()

    if not code:
        return {
            "found": False,
            "reason": "Código não informado"
        } 

    try:
        response = requests.get(
            f"{get_pos_base_url()}/articles/code/{code}",
            timeout=10
        )

        # 👉 CASO DE NEGÓCIO: NÃO ENCONTRADO
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

        # erro técnico REAL
        frappe.throw("Erro de comunicação com o POS")
