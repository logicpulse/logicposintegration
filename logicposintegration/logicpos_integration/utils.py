import frappe

def _get_requests():
	"""Import requests at runtime and raise a clear error if missing.
	This avoids failing module import when 'requests' is not installed in production.
	"""
	try:
		import requests
		return requests
	except Exception:
		frappe.log_error(
			title="Missing dependency 'requests'",
			message="The 'requests' library is not available in the Python environment.",
		)
		frappe.throw("Dependência ausente: biblioteca 'requests' não instalada no servidor. Instale-a e reinicie os workers.")

def _get_re():
	"""Import `re` at runtime. This is mostly defensive — `re` is stdlib but keeping parity with _get_requests.
	"""
	try:
		import re
		return re
	except Exception:
		frappe.log_error(
			title="Missing stdlib module 're'",
			message="The Python 're' module could not be imported.",
		)
		frappe.throw("Dependência ausente: módulo padrão 're' não disponível no servidor.")

def get_pos_base_url(company: str | None = None) -> str:
    # company_name = frappe.defaults.get_user_default("Company")

    if not company:
        frappe.throw("Empresa não informada")

    company = frappe.db.get_value(
        "Company",
        company,
        ["base_url", "port"],
        as_dict=True
    )

    if not company or not company.base_url:
        frappe.throw("Base URL não configurada na empresa")

    return (
        f"{company.base_url}:{company.port}"
        if company.port
        else company.base_url
    )

@frappe.whitelist()
def get_pos_country_by_code(code, company: str | None = None):
    requests = _get_requests()
    
    if not code:
        return {
            "found": False,
            "reason": "code não informado"
        } 

    try: 
        response = requests.get(
            f"{get_pos_base_url(company)}/countries/country",
			params={"code2": code },
            timeout=10
        )

        # 👉 Caso de negócio: pais não existe
        if response.status_code == 404:
            return {
                "found": False,
                "reason": "code não encontrado no POS",
                "code": code
            }

        response.raise_for_status()

        return {
            "found": True,
            "data": response.json()
        }

    except requests.exceptions.RequestException as e:
        frappe.log_error(
            title="Erro técnico ao buscar code no POS",
            message=str(e)
        )

        frappe.throw("Erro de comunicação com o POS")