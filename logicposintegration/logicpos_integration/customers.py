import frappe
from logicposintegration.logicpos_integration.utils import (
    _get_requests,
    get_pos_base_url
)

@frappe.whitelist()
def get_customer_by_fiscal_number(fiscal_number):
    requests = _get_requests()

    if not fiscal_number:
        return {
            "found": False,
            "reason": "Fiscal Number não informado"
        } 

    try: 
        response = requests.get(
            f"{get_pos_base_url()}/customers/customer",
			params={"fiscalNumber": fiscal_number },
            timeout=10
        )

        # 👉 Caso de negócio: cliente não existe
        if response.status_code == 404:
            return {
                "found": False,
                "reason": "Cliente não encontrado no POS",
                "fiscal_number": fiscal_number
            }

        response.raise_for_status()

        return {
            "found": True,
            "data": response.json()
        }

    except requests.exceptions.RequestException as e:
        frappe.log_error(
            title="Erro técnico ao buscar cliente no POS",
            message=str(e)
        )

        frappe.throw("Erro de comunicação com o POS")