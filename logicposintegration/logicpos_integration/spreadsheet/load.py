import frappe 
import re
from erpnext.selling.doctype.catalogo.catalogo import (convert_list_to_model, get_values)
from logicposintegration.logicpos_integration.articles import update_article
from logicposintegration.logicpos_integration.utils import(_error, _success, get_user_company)

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
		"cell_range": "E:P"
	},
	{
		"ref": "q",
		"sheet_name": "Gestão de Filas de Espera",
		"cell_range": "E:P"
	},
	{
		"ref": "fleet",
		"sheet_name": "Gestão de Frotas",
		"cell_range": "E:P"
	},
	{
		"ref": "pos",
		"sheet_name": "POS",
		"cell_range": "E:P"
	},
	{
		"ref": "library",
		"sheet_name": "Gestão de Bibliotecas",
		"cell_range": "D:P"
	},
	{
		"ref": "factory",
		"sheet_name": "Gestão industrial",
		"cell_range": "D:P"
	}
]

@frappe.whitelist()
def sync_datas():
	results = []
	for data in datas:
		try:
			sheet_values = get_values(spreadsheet_id, data["sheet_name"], data["cell_range"])
			list_values = convert_list_to_model(sheet_values) 
			list_values_filtered = filter_valid_refs(list_values)
			items = get_items_by_ref(data["ref"])
			updated = sync_items(items, list_values_filtered)
			results.append(f"{data['ref']}: {updated} items atualizados") 

		except Exception as e:
			frappe.log_error(frappe.get_traceback(), f"Erro Synchronização {data['ref']}")
			return _error(f"Erro ao carregar dados da planilha {data['ref']}")
	
	return _success(" | ".join(results))

@frappe.whitelist()
def sync_single_sheet_data(ref: str): 
	data = get_sheet_config(ref) 
	if not data:
		return _error("Referência inválida") 
	
	try:
		sheet_values = get_values(spreadsheet_id, data["sheet_name"], data["cell_range"])
		list_values = convert_list_to_model(sheet_values) 
		list_values_filtered = filter_valid_refs(list_values)
		items = get_items_by_ref(data["ref"])
		updated = sync_items(items, list_values_filtered)
		return _success(f"Items atualizados: {updated}") 

	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Erro Synchronização")
		frappe.throw("Erro ao carregar dados da planilha")
          
@frappe.whitelist()
def sync_single_item(item_code: str, ref: str):
	data = get_sheet_config(ref) 
	if not data:
		return _error("Referência inválida") 
	
	try:
		# company_name = get_user_company()
		sheet_values = get_values(spreadsheet_id, data["sheet_name"], data["cell_range"])
		list_values = convert_list_to_model(sheet_values)  
		value = next((lv for lv in list_values if getattr(lv, "Ref", None) == item_code), None)
		if not value:
			return _error("Item não encontrado na planilha")
		
		item = frappe.db.get_value(
					"Item", 
					item_code, 
					["standard_rate", "valuation_rate", "pvp_ao", "pvp_mz"], 
					as_dict=True
				)
		
		if not item:
			return _error("Item não encontrado no LogicERP")
		
		new_values = parse_values(value)
             
		if item.standard_rate == new_values["standard_rate"] and \
		   item.valuation_rate == new_values["valuation_rate"] and \
		   item.pvp_ao == new_values["pvp_ao"] and \
		   item.pvp_mz == new_values["pvp_mz"]:
			return _success("Nenhuma alteração necessária")
            
		frappe.db.set_value(
			"Item",
			item_code,
			new_values,
			update_modified=False
		) 
            
		# testes update no POS
		update_article(item_code, new_values)
		# fim testes
            
		return _success(f"Item {item_code} atualizado com sucesso")

	except Exception as e:
		frappe.log_error(e.traceback, "Erro Synchronização")
		frappe.throw("Erro ao carregar dados da planilha")
# -------------------------
# Helpers principais
# -------------------------
def get_sheet_config(ref: str):
    return next((d for d in datas if d["ref"] == ref), None)

def get_items_by_ref(ref: str):
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

def sync_items(items, list_values):
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

        new_values = parse_values(lv)

        if not has_changes(item, new_values):
            continue

        frappe.db.set_value(
            "Item",
            item_code,
            new_values,
            update_modified=False
        )
        
        update_article(item_code, new_values)

        updated += 1

    return updated

# -------------------------
# Normalização e validação
# -------------------------

def filter_valid_refs(list_values):
    invalid = {"", "*", "#"}
    return [
        lv for lv in list_values
        if getattr(lv, "Ref", None) not in invalid
    ]

def parse_values(lv): # to do: trocar os valores de pvr <> pvp
    return {
        "standard_rate": normalize_decimal(parse_money(lv.PVP_PT)),
        "valuation_rate": normalize_decimal(parse_money(lv.PVR_PT)),
        "pvp_ao": normalize_decimal(parse_money(lv.PVP_AO)),
        "pvp_mz": normalize_decimal(parse_money(lv.PVP_MZ)),
    }

def has_changes(item, values):
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

