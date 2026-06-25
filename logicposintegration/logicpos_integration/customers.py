import frappe
from logicposintegration.logicpos_integration.utils import (
    _get_requests,
    get_pos_auth_headers,
    get_pos_base_url,
    get_pos_country_by_code,
    pos_request,
)

@frappe.whitelist()
def get_customer_by_fiscal_number(fiscal_number, company=None):
    requests = _get_requests()

    if not fiscal_number:
        return {
            "found": False,
            "reason": "Fiscal Number não informado"
        } 

    try: 
        response = requests.get(
            f"{get_pos_base_url(company)}/customers/customer",
			params={"fiscalNumber": fiscal_number },
            headers=get_pos_auth_headers(with_content_type=False),
            timeout=10
        )
 
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


def _get_pos_list(company: str | None, endpoint: str) -> list:
    try:
        response = pos_request(
            "GET",
            endpoint,
            company=company,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        frappe.log_error(
            title=f"Erro ao listar {endpoint} no POS",
            message=str(e),
        )
        raise


def _resolve_pos_entity_id(
    items: list,
    keywords: tuple[str, ...] = (),
) -> str | None:
    if not items:
        return None

    if keywords:
        for item in items:
            designation = (item.get("designation") or "").lower()
            code = (item.get("code") or "").lower()
            if any(keyword in designation or keyword in code for keyword in keywords):
                return item.get("id")

    return items[0].get("id")


@frappe.whitelist()
def get_customer_types(company=None):
    try:
        return {
            "found": True,
            "data": _get_pos_list(company, "/customers/types"),
        }
    except Exception as e:
        frappe.log_error(
            title="Erro técnico ao listar tipos de cliente no POS",
            message=str(e),
        )
        frappe.throw("Erro de comunicação com o POS")


def _resolve_customer_type_id(company: str | None = None, supplier: bool = False) -> str | None:
    customer_types = _get_pos_list(company, "/customers/types")
    keywords = ("empresa", "fornecedor", "supplier") if supplier else ()
    return _resolve_pos_entity_id(customer_types, keywords)


def _resolve_price_type_id(company: str | None = None) -> str | None:
    price_types = _get_pos_list(company, "/articles/pricetypes")
    return _resolve_pos_entity_id(
        price_types,
        ("vendedor", "compra", "wholesale", "grossista"),
    )


def _get_supplier_pos_payload(supplier_name: str, company: str | None = None) -> dict:
    supplier = frappe.db.get_value(
        "Supplier",
        supplier_name,
        [
            "supplier_name",
            "tax_id",
            "supplier_primary_address",
            "mobile_no",
            "email_id",
        ],
        as_dict=True,
    )
    if not supplier:
        frappe.throw(f"Fornecedor {supplier_name} não encontrado")

    fiscal_number = (supplier.tax_id or "").strip()
    if not fiscal_number:
        return {"error": "NIF do fornecedor não informado"}

    address_data = {}
    if supplier.supplier_primary_address:
        address_data = (
            frappe.db.get_value(
                "Address",
                supplier.supplier_primary_address,
                [
                    "address_line1",
                    "address_line2",
                    "city",
                    "state",
                    "pincode",
                    "country",
                    "phone",
                    "email_id",
                ],
                as_dict=True,
            )
            or {}
        )

    country_id = ""
    if address_data.get("country"):
        country_code = frappe.db.get_value("Company", company, "codigo")
        if country_code:
            pos_country = get_pos_country_by_code(country_code, company)
            if pos_country.get("found"):
                country_id = pos_country["data"].get("id", "")

    customer_type_id = _resolve_customer_type_id(company, supplier=True)
    if not customer_type_id:
        return {"error": "Tipo de cliente não encontrado no POS"}

    price_type_id = _resolve_price_type_id(company)
    if not price_type_id:
        return {"error": "Tipo de preço não encontrado no POS"}

    if not country_id:
        return {"error": "País do fornecedor não encontrado no POS"}

    address_parts = [
        part for part in (address_data.get("address_line1"), address_data.get("address_line2")) if part
    ]

    return {
        "customerTypeId": customer_type_id,
        "priceTypeId": price_type_id,
        "countryId": country_id,
        "name": supplier.supplier_name or supplier_name,
        "address": " - ".join(address_parts) or None,
        "locality": address_data.get("state"),
        "zipCode": address_data.get("pincode"),
        "city": address_data.get("city"),
        "phone": address_data.get("phone"),
        "mobilePhone": supplier.mobile_no,
        "email": supplier.email_id or address_data.get("email_id"),
        "fiscalNumber": fiscal_number,
        "discount": 0,
        "cardCredit": 0,
        "supplier": True,
        "notes": "Created by LogicERP",
    }


@frappe.whitelist()
def create_customer_in_pos(customer_data, company=None):
    if isinstance(customer_data, str):
        customer_data = frappe.parse_json(customer_data)

    if not customer_data:
        frappe.throw("Dados do cliente não informados")

    try:
        response = pos_request(
            "POST",
            "/customers",
            company=company,
            json=customer_data,
            timeout=15,
        )

        if response.status_code not in (200, 201):
            frappe.log_error(
                title="Erro POS - Criar cliente/fornecedor",
                message=f"Status: {response.status_code}\nResponse: {response.text}",
            )
            frappe.throw("Erro ao criar fornecedor no POS")

        return response.json()

    except frappe.exceptions.ValidationError:
        raise
    except Exception as e:
        frappe.log_error(
            title="Erro técnico ao criar cliente no POS",
            message=str(e),
        )
        frappe.throw("Erro de comunicação com o POS")


@frappe.whitelist()
def sync_supplier_to_pos(supplier, company=None):
    requests = _get_requests()

    if not supplier:
        return {"success": False, "message": "Fornecedor não informado"}

    fiscal_number = (frappe.db.get_value("Supplier", supplier, "tax_id") or "").strip()
    if not fiscal_number:
        return {"success": False, "message": "NIF do fornecedor não informado"}

    try:
        existing = get_customer_by_fiscal_number(fiscal_number, company)
        if existing.get("found"): 
            return {"success": True, "created": False, "pos_id": existing["data"].get("id")}

        payload = _get_supplier_pos_payload(supplier, company)
        if payload.get("error"):
            return {"success": False, "message": payload["error"]}

        created = create_customer_in_pos(payload, company) 

        return {
            "success": True,
            "created": True,
            "pos_id": created.get("id")
        }
    except requests.exceptions.RequestException as e:
        frappe.log_error(
            title="Erro de comunicação ao sincronizar fornecedor com o POS",
            message=str(e),
        )
        return {
            "success": False,
            "message": "Erro de comunicação com o POS. Verifique a ligação e o login no POS.",
        }
    except frappe.exceptions.ValidationError as e:
        return {"success": False, "message": str(e)}