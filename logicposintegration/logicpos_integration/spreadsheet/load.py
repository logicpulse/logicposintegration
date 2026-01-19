# import json
from erpnext.selling.doctype.catalogo.catalogo import (convert_list_to_model, get_values)
import frappe 
import re

spreadsheet_id = "1Nm6YatjJrugBxM38yaXlIJgLHfVAMCnnMLw83lga5YQ"
datas = [
	{
		"ref": "access",
		"sheet_name": "Gestão de Acessos",
		"cell_range": "E:P"
	},
	{
		"ref": "time",
		"sheet_name": "Gestão de Assiduidade",
		"cell_range": "E:T"
	},
	{
		"ref": "q",
		"sheet_name": "Gestão de Filas de Espera",
		"cell_range": "E:T"
	},
	{
		"ref": "fleet",
		"sheet_name": "Gestão de Frotas",
		"cell_range": "E:T"
	},
	{
		"ref": "pos",
		"sheet_name": "POS",
		"cell_range": "E:T"
	},
	{
		"ref": "library",
		"sheet_name": "Gestão de Bibliotecas",
		"cell_range": "E:T"
	},
	{
		"ref": "factory",
		"sheet_name": "Gestão industrial",
		"cell_range": "E:T"
	}
]

@frappe.whitelist()
def get_datas():
	
	data = []
	try:
		for data in datas:
			ref = data.get("ref")
			sheet_name = data.get("sheet_name")
			cell_range = data.get("cell_range")

			values = get_values(spreadsheet_id, sheet_name, cell_range)
			data.append({
				"ref": ref,
				"values": values
			}) 

		return {
			"success": True,
			"data": data
		}
	except Exception as e:
		frappe.log_error(
			title="Erro técnico ao carregar dados da planilha",
			message=str(e)
		)

		return {
			"success": False,
			"message": "Erro ao carregar dados da planilha"
		}

@frappe.whitelist()
def get_single_sheet_data(ref: str): 
	data = _get_sheet_config(ref) 
	if not data:
		return _error("Referência inválida") 
	
	try:
		sheet_values = get_values(spreadsheet_id, data["sheet_name"], data["cell_range"])
		list_values = convert_list_to_model(sheet_values) 
		list_values_filtered = _filter_valid_refs(list_values)
		items = _get_items_by_ref(data["ref"])
		updated = _sync_items(items, list_values_filtered)
		return _success(f"Items atualizados: {updated}") 

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Erro Synchronização")
		frappe.throw("Erro ao carregar dados da planilha")
# -------------------------
# Helpers principais
# -------------------------
def _get_sheet_config(ref: str):
    return next((d for d in datas if d["ref"] == ref), None)

def _get_items_by_ref(ref: str):
    return frappe.db.get_all(
        "Item",
        fields=[
            "item_code",
            "standard_rate",
            "valuation_rate",
            "pvp_ao",
            "pvp_mz"
        ],
        filters={
            "item_group": ["like", f"%{ref}%"]
        },
        limit_page_length=0
    )

def _sync_items(items, list_values):
    list_map = {
        str(lv.Ref): lv
        for lv in list_values
        if getattr(lv, "Ref", None)
    }

    updated = 0

    for item in items:
        item_code = item["item_code"]
        lv = list_map.get(item_code)
        if not lv:
            continue

        new_values = _parse_values(lv)

        if not _has_changes(item, new_values):
            continue

        frappe.db.set_value(
            "Item",
            item_code,
            new_values,
            update_modified=False
        )

        updated += 1

    return updated
	
def safe_float(value):
    return value if value is not None else 0.0

# -------------------------
# Normalização e validação
# -------------------------

def _filter_valid_refs(list_values):
    invalid = {"", "*", "#"}
    return [
        lv for lv in list_values
        if getattr(lv, "Ref", None) not in invalid
    ]

def _parse_values(lv):
    return {
        "standard_rate": normalize_decimal(parse_money(lv.PVR_PT)),
        "valuation_rate": normalize_decimal(parse_money(lv.PVP_PT)),
        "pvp_ao": normalize_decimal(parse_money(lv.PVP_AO)),
        "pvp_mz": normalize_decimal(parse_money(lv.PVP_MZ)),
    }

def _has_changes(item, values):
    return any(
        is_different(values[field], item.get(field))
        for field in values
    )

# -------------------------
# Utilitários
# -------------------------
def is_different(a, b):
    return float(a or 0) != float(b or 0)

def normalize_decimal(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
    
def parse_money(value: str) -> float | None:
    if not value or not isinstance(value, str):
        return None
    
    # Remove símbolos monetários, espaços não-breaking e letras e Troca vírgula por ponto (decimal)
    cleaned = re.sub(r"[^\d,.-]", "", value).replace(",", ".")
      
    try:
        return float(cleaned)
    except ValueError:
        return None
    
def _success(message: str):
    return {"success": True, "message": message}

def _error(message: str):
    return {"success": False, "message": message}