import frappe


def execute() -> None:
	"""Cria modelo default de inquérito se ainda não existir nenhum."""
	if frappe.db.exists("Satisfaction Survey Template", {"is_active": 1}):
		return

	doc = frappe.get_doc(
		{
			"doctype": "Satisfaction Survey Template",
			"title": "Inquérito de Satisfação (Default)",
			"is_active": 1,
			"is_default": 1,
			"description": "Modelo padrão enviado ao concluir projetos ou tarefas de grupo.",
			"questions": [
				{
					"question": "Qual o assunto relacionado com este trabalho?",
					"question_type": "Choice",
					"options": (
						"Informação\nAquisição\nAssistência Técnica\nHardware\nSoftware\nOutros"
					),
					"is_mandatory": 1,
				},
				{
					"question": (
						"Numa escala de 0 a 10, sentiu que o assunto ficou resolvido?"
					),
					"question_type": "Scale",
					"scale_min": 0,
					"scale_max": 10,
					"is_mandatory": 1,
				},
				{
					"question": (
						"Numa escala de 0 a 10, como avalia o tempo de resolução?"
					),
					"question_type": "Scale",
					"scale_min": 0,
					"scale_max": 10,
					"is_mandatory": 1,
				},
				{
					"question": "Comentários ou sugestões",
					"question_type": "Text",
					"is_mandatory": 0,
				},
			],
		}
	)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
