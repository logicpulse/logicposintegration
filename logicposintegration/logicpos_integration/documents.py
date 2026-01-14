
import frappe
from logicposintegration.logicpos_integration.utils import (
    _get_re, 
    _get_requests, 
    get_pos_base_url
)

@frappe.whitelist()
def create_pos_document(doctype=None, docname=None, payload=None):
    requests = _get_requests()

    if not payload:
        frappe.throw("Payload não informado")

    try:

        frappe.log_error(title="Payload enviado ao POS", message=payload)
		
        response = requests.post(
            f"{get_pos_base_url()}/documents",
            data=payload,
			headers={
				"Content-Type": "application/json"
			},
            timeout=15
        )

        if response.status_code not in (200, 201):
            frappe.log_error(
                title="Erro POS - Create Document",
                message=f"""
                Status: {response.status_code}
                Response: {response.text}
                """
            )

            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.json() if response.text else None
            }

        data = response.json()

        pos_id = data.get("id")
        if not pos_id:
            frappe.throw("POS não retornou o ID do documento")

        # salvar no ERP se necessário
        if doctype and docname:
            doc = frappe.get_doc(doctype, docname)
            doc.pos_id = pos_id
            # doc.save(ignore_permissions=True)
            frappe.db.set_value(doctype, docname, "pos_id", pos_id, update_modified=False)

        return {
            "success": True,
            "pos_id": pos_id,
            "data": data
        }

    except requests.exceptions.Timeout:
        frappe.throw("Timeout ao comunicar com o POS")

    except requests.exceptions.RequestException as e:
        frappe.log_error(
            title="Erro técnico POS",
            message=str(e)
        )
        frappe.throw("Erro técnico ao comunicar com o POS")


@frappe.whitelist()
def generate_pdf_document(document_id: str | None = None): 
    requests = _get_requests()
    re = _get_re()
    url = f"{get_pos_base_url()}/documents/pdf"
  
    try:
        response = requests.get(
            url=url,
			params={
				"id": document_id
			},
            headers={
        		"Accept": "*/*"
    		},
            timeout=30,
			stream=True
        )

        response.raise_for_status()  # lança erro para 4xx/5xx

        content_type = response.headers.get("Content-Type", "")
        if "octet-stream" not in content_type:
            raise Exception(
                f"Resposta inesperada da API. Content-Type: {content_type}"
            )

        # Extrair nome do ficheiro
        disposition = response.headers.get("Content-Disposition", "")
        filename = "documento.pdf"

        match = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', disposition)
        if match:
            filename = requests.utils.unquote(match.group(1))

        # Enviar diretamente para o browser
        frappe.local.response.filename = filename
        frappe.local.response.filecontent = response.content
        frappe.local.response.type = "download"

    except requests.exceptions.Timeout:
        frappe.throw("Timeout ao comunicar com o POS")

    except requests.exceptions.RequestException as e:
        frappe.log_error(str(e), "Erro ao baixar PDF do POS")
        frappe.throw("Erro ao baixar PDF do POS")