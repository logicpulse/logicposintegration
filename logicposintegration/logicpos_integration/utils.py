import frappe
import base64
import json as _json
from datetime import datetime, timezone

_POS_TOKEN_CACHE_KEY = "logicpos_sign_in_token"
_POS_TOKEN_DEFAULT_TTL = 3300  # fallback de 55 min se não conseguir ler o exp do JWT

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

    if not company:
        company = get_user_company()
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


def _pos_url(company: str | None, path: str) -> str:
    """Junta a raiz configurada na empresa com um path, sem barras duplicadas."""
    root = get_pos_base_url(company).rstrip("/")
    p = path if path.startswith("/") else f"/{path}"
    return f"{root}{p}"


def get_user_company():
    user = frappe.session.user

    if user == "Guest":
        frappe.throw("Utilizador não autenticado")

    return _get_company_for_user(user)


def _get_company_for_user(user: str) -> str:
    companies = frappe.get_all(
        "User Permission",
        filters={
            "user": user,
            "allow": "Company"
        },
        pluck="for_value"
    )

    if not companies:
        frappe.throw("Utilizador não tem empresa associada")

    return companies[0]

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
            headers=get_pos_auth_headers(with_content_type=False),
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

@frappe.whitelist()
def login_to_pos(company: str | None = None, user: str | None = None, force: bool | int = False):
    target_user = user or frappe.session.user
    if target_user == "Guest":
        frappe.throw("Utilizador não autenticado")

    if target_user != frappe.session.user and not frappe.has_permission("User", ptype="write"):
        frappe.throw("Sem permissão para testar a conexão POS deste utilizador")

    if not company:
        company = _get_company_for_user(target_user)

    if not frappe.utils.cint(force) and get_pos_token(target_user):
        return {"success": True, "message": "Login no POS já realizado (token em cache)"}

    clear_pos_token(target_user)
    _do_login(target_user, company)
    return {"success": True, "message": "Login no POS realizado com sucesso"}


def _decode_jwt_exp(token: str) -> int | None:
    """Extrai o claim 'exp' (Unix timestamp) do payload do JWT sem verificar assinatura."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        # base64url → base64 padrão (padding obrigatório)
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = _json.loads(base64.urlsafe_b64decode(payload_b64))
        return int(payload["exp"]) if "exp" in payload else None
    except Exception:
        return None


def _ttl_from_jwt(token: str) -> int:
    """Calcula o TTL em segundos até à expiração do JWT (com 60s de margem)."""
    exp = _decode_jwt_exp(token)
    if exp is None:
        return _POS_TOKEN_DEFAULT_TTL
    now = int(datetime.now(timezone.utc).timestamp())
    return max(exp - now - 60, 60)


def _save_pos_token(user: str, token: str) -> None:
    ttl = _ttl_from_jwt(token)
    frappe.cache().set_value(f"{_POS_TOKEN_CACHE_KEY}:{user}", token, expires_in_sec=ttl)


def get_pos_token(user: str | None = None):
    """Devolve a resposta de autenticação POS guardada em cache.
    Retorna None se o token não existir ou já tiver expirado (Redis TTL).
    """
    if not user:
        user = frappe.session.user
    return frappe.cache().get_value(f"{_POS_TOKEN_CACHE_KEY}:{user}")


def clear_pos_token(user: str | None = None) -> None:
    if not user:
        user = frappe.session.user
    frappe.cache().delete_value(f"{_POS_TOKEN_CACHE_KEY}:{user}")


def get_pos_auth_headers(
    user: str | None = None, 
    with_content_type: bool = True, 
    with_accept: bool = True
) -> dict:
    """
    Retorna o dicionário de headers para chamadas ao POS, incluindo o Bearer token.
    Lança exceção se o token não estiver disponível ou expirado.
    """
    token = get_pos_token(user)
    if not token:
        frappe.throw("Token POS expirado ou não disponível. Faça login no POS novamente.")

    headers = {
        "Authorization": f"Bearer {token}"
    }
    if with_content_type:
        headers["Content-Type"] = "application/json"
    if with_accept:
        headers["Accept"] = "application/json"
    return headers


def pos_request(method: str, endpoint: str, company: str | None = None, **kwargs):
    """Wrapper para chamadas ao POS com re-login automático em caso de 401.

    Uso:
        response = pos_request("GET", "/customers/123", company=frm.doc.company)
        response = pos_request("POST", "/orders", company=..., json={...})
    """
    requests = _get_requests()
    url = _pos_url(company, endpoint)
    timeout = kwargs.pop("timeout", 15)

    def _do_request():
        return requests.request(
            method,
            url,
            headers=get_pos_auth_headers(),
            timeout=timeout,
            **kwargs,
        )

    response = _do_request()

    if response.status_code == 401:
        user = frappe.session.user
        clear_pos_token(user)
        _do_login(user, company)
        response = _do_request()

    return response

def _extract_pos_token(response) -> str:
    """Extrai o JWT da resposta 200 de /auth/sign-in (JSON string)."""
    try:
        data = response.json()
        if isinstance(data, str):
            return data.strip()
    except Exception:
        pass

    return (response.text or "").strip().strip('"')


def _format_pos_login_error(response) -> str:
    """Formata a resposta de erro do POS (400, etc.)."""
    try:
        data = response.json()
    except Exception:
        preview = (response.text or "")[:400]
        return preview or f"HTTP {response.status_code}"

    if not isinstance(data, dict):
        return str(data)

    parts: list[str] = []
    if data.get("title"):
        parts.append(data["title"])
    if data.get("detail"):
        parts.append(data["detail"])

    for err in data.get("errors") or []:
        if not isinstance(err, dict):
            continue
        name = err.get("name") or ""
        reason = err.get("reason") or ""
        if name and reason:
            parts.append(f"{name}: {reason}")
        elif reason:
            parts.append(reason)
        elif name:
            parts.append(name)

    return " — ".join(parts) if parts else f"HTTP {response.status_code}"


def _do_login(user: str, company: str | None = None) -> None:
    """Login silencioso ao POS (sem whitelist). Guarda o novo token em cache."""
    user_doc = frappe.get_doc("User", user)

    if not user_doc.pos_email:
        frappe.throw("Email POS não configurado para o utilizador")

    if not user_doc.pin:
        frappe.throw("PIN não configurado para o utilizador")

    requests = _get_requests()
    login_url = _pos_url(company, "/auth/sign-in")
    response = requests.post(
        login_url,
        json={
            "login": user_doc.pos_email,
            "password": user_doc.pin,
        },
        timeout=10,
    )

    if response.status_code != 200:
        body_preview = (response.text or "")[:800]
        frappe.log_error(
            title="Falha no login ao POS",
            message=f"URL: {login_url}\nHTTP {response.status_code}\n{body_preview}",
        )
        if response.status_code == 404:
            frappe.throw(
                "O POS devolveu 404 em /auth/sign-in. Confirme na empresa o campo Base URL "
                "(inclua o prefixo da API se existir, ex.: …/api) e a porta; o pedido foi registado nos erros com a URL exata."
            )
        frappe.throw(f"Erro ao fazer login no POS: {_format_pos_login_error(response)}")

    token = _extract_pos_token(response)
    if not token:
        frappe.throw("O POS não devolveu token após login")

    _save_pos_token(user, token)


def _success(message: str):
    return {"success": True, "message": message}

def _error(message: str):
    return {"success": False, "message": message}