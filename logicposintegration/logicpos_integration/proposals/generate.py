from collections import defaultdict
from datetime import date
import frappe
from fpdf import FPDF, Align, FontFace, TextStyle
import os

root_dir = os.path.join(frappe.get_app_path('logicposintegration', 'logicpos_integration', 'proposals'))
asset_dir = os.path.join(root_dir, 'assets')

datas = {
	"q.track": {
		"footer_description": "iPQ02.04-01 - Logicpulse - Gestão de Filas - Q.track", 
		"last_page": 16,
	},
	"q.track.survey": {
		"footer_description": "iPQ02.04-02 - Logicpulse - Avaliação de Satisfação - Q.track / survey.track",
		"last_page": 23,
	}
}


class PDF(FPDF):
	def __init__(self, client_name="", footer_description="", article=""):
		super().__init__()
		self.client_name = client_name
		self.footer_description = footer_description
		self.article = article

	def _omit_header_footer(self) -> bool:
		if self.page_no() == 1:
			return True
		# Última página fixa por artigo em `datas` (ex.: q.track → 16), como a capa.
		meta = datas.get(self.article) or {}
		last = meta.get("last_page")
		if last is not None and self.page_no() == last:
			return True
		return False

	def header(self): 
		if self._omit_header_footer():
			return
		
		self.set_fill_color(254, 251, 250)
		self.set_text_color(64, 64, 64) 
		self.set_font("helvetica", style="B", size=9) 
		self.set_draw_color(27, 151, 211) # border color
		self.ln(10)
		self.cell(80, 5, self.client_name, border=1, align=Align.L, fill=True)  
		self.ln(15)

	def footer(self):
		if self._omit_header_footer():
			return
		self.set_y(-13)
		self.set_font("helvetica", style="I", size=8) 
		self.set_text_color(64, 64, 64)
		self.cell(70, 8, self.footer_description, border=0, align=Align.L) 
		self.cell(0, 10, f"{self.page_no()}", align=Align.R)

	def write_html(self, text: str, *args, **kwargs):
		kwargs.setdefault("li_prefix_color", "#000000")
		return super().write_html(text, *args, **kwargs)

@frappe.whitelist()
def generate_proposal(article: str, client: str, currency: str, items=None) -> str:
	try:
		items = frappe.parse_json(items)
		if items is None:
			items = []
		elif not isinstance(items, list):
			frappe.throw(frappe._("O argumento items tem de ser uma lista."))

		doc = PDF(
			client_name=client,
			footer_description=datas.get(article).get("footer_description"),
			article=article,
		)
		doc.set_page_background(get_cover(article, 'capa.png'))
		doc.add_page()  
		doc.set_page_background(get_cover(article, 'background_image.jpg'))
		doc.add_page()  
		add_fonts(doc) 
		
		fill_document(doc, article, client, currency, items)

		file_name = f"ppt_{article}_{currency.lower()}_{client.lower()}.pdf" 
		public_file_path = frappe.utils.get_site_path("public", "files", file_name) 
		doc.output(public_file_path) 
		# port = frappe.conf.webserver_port or 8080 
		url_base = frappe.utils.get_url()

		# if f":{port}" not in url_base:
		# 	url_base += f":{port}"
		# full_path = url_base + '/files/' + file_name
		full_path = url_base.rstrip("/") + "/files/" + file_name
		return full_path
	except Exception as err:
		frappe.log_error(frappe.get_traceback(), "Error")
		frappe.throw(f"Erro ao gerar proposta: {str(err)}")


def _proposal_item_group(item: dict) -> str:
	g = item.get("item_group") or item.get("group") or item.get("category")
	if g:
		return str(g).strip()
	return "Outros"


def _proposal_line_total(item: dict) -> float:
	amt = item.get("amount")
	if amt is not None and str(amt).strip() != "":
		return float(amt)
	rate = float(item.get("rate") or item.get("price_list_rate") or 0)
	qty = float(item.get("qty") or 0)
	return rate * qty


def _proposal_is_oferta(item: dict) -> bool:
	if item.get("oferta") or item.get("is_offer"):
		return True
	total = _proposal_line_total(item)
	if total != 0:
		return False
	rate = float(item.get("rate") or item.get("price_list_rate") or 0)
	return rate == 0


def _format_pt_amount(value: float, decimals: int = 2) -> str:
	n = float(value)
	neg = n < 0
	a = abs(n)
	whole = int(a)
	frac = int(round((a - whole) * (10**decimals))) % (10**decimals)
	w = f"{whole:,}".replace(",", ".")
	num = f"{w},{frac:0{decimals}d}"
	return f"-{num}" if neg else num


def _format_money_proposal(value: float, currency: str) -> str:
	return f"{_format_pt_amount(value)} {currency}"


def _ordered_item_groups(items: list):
	groups = defaultdict(list)
	order = []
	for raw in items or []:
		item = raw if isinstance(raw, dict) else dict(raw)
		g = _proposal_item_group(item)
		if g not in groups:
			order.append(g)
		groups[g].append(item)
	return [(name, groups[name]) for name in order]


def add_grouped_prices_table(doc: FPDF, currency: str, items: list):
	# items = items or []
	doc.set_draw_color(0, 0, 0)
	col_widths = (78, 20, 16, 36, 40)
	header_ff = FontFace(
		family="calibri",
		emphasis="BOLD",
		color=(255, 255, 255),
		fill_color=(70, 70, 70),
	)
	group_ff = FontFace(family="calibri", emphasis="BOLD", fill_color=(220, 220, 220))
	subtotal_ff = FontFace(family="calibri", emphasis="BOLD")
	total_ff = FontFace(
		family="calibri",
		emphasis="BOLD",
		color=(255, 255, 255),
		fill_color=(70, 70, 70),
	)
	row_ff = FontFace(family="calibri")

	with doc.table(
		col_widths=col_widths,
		text_align=(Align.L, Align.C, Align.R, Align.R, Align.R),
		line_height=6,
		first_row_as_headings=False,
	) as table:
		hrow = table.row()
		hrow.cell("DESCRIÇÃO", style=header_ff)
		hrow.cell("IMAGEM", style=header_ff)
		hrow.cell("QT.", style=header_ff)
		hrow.cell("PREÇO UNIT.", style=header_ff)
		hrow.cell("PREÇO TOTAL", style=header_ff)

		if not items:
			erow = table.row()
			erow.cell("Sem itens nesta proposta.", colspan=5, style=row_ff, align=Align.C)
			return

		grand_total = 0.0
		for _group_name, group_items in _ordered_item_groups(items):
			grow = table.row()
			grow.cell(_group_name, colspan=5, style=group_ff, align=Align.L)

			group_sub = 0.0
			for item in group_items:
				desc = item.get("item_name") or ""
				image = item.get("image") or ""
				qty = float(item.get("qty") or 0)
				rate = float(item.get("rate") or 0)
				line = _proposal_line_total(item)
				oferta = _proposal_is_oferta(item)

				if not oferta:
					group_sub += line
					grand_total += line

				irow = table.row(min_height= 25 if image else None)
				irow.cell(str(desc), style=row_ff)
				if image:
					irow.cell(img=image, align=Align.C)
				else:
					irow.cell("N/D", align=Align.C)
				irow.cell(_format_pt_amount(qty), style=row_ff)
				irow.cell(_format_money_proposal(rate, currency), style=row_ff)
				irow.cell("OFERTA" if oferta else _format_money_proposal(line, currency), style=row_ff)

			srow = table.row()
			srow.cell("Sub-Total", colspan=4, style=subtotal_ff, align=Align.L)
			srow.cell(_format_money_proposal(group_sub, currency), style=subtotal_ff)

		trow = table.row()
		trow.cell("TOTAL", colspan=4, style=total_ff, align=Align.L)
		trow.cell(_format_money_proposal(grand_total, currency), style=total_ff)


def get_cover(article: str, filename: str) -> str:
	try:
		cover_image_path = os.path.join(root_dir, 'assets', article, filename)

		if not os.path.exists(cover_image_path):
			frappe.throw(f"Capa não encontrada!!!")

		return cover_image_path 
	except Exception as err:
		frappe.log_error(frappe.get_traceback(), "Cover Access Error")
		frappe.throw(f"Erro ao acessar a capa: {str(err)}")

def add_fonts(doc: FPDF):
	fonts_dir = os.path.join(root_dir, 'fonts')
	calibri_bold = os.path.join(fonts_dir, 'calibri-bold.ttf')
	calibri_bold_italic = os.path.join(fonts_dir, 'calibri-bold-italic.ttf')
	calibri_italic = os.path.join(fonts_dir, 'calibri-italic.ttf')
	calibri_regular = os.path.join(fonts_dir, 'calibri-regular.ttf') 
	doc.add_font("calibri", style="b", fname=calibri_bold)
	doc.add_font("calibri", style="bi", fname=calibri_bold_italic)
	doc.add_font("calibri", style="i", fname=calibri_italic)
	doc.add_font("calibri", style="", fname=calibri_regular)
	doc.set_font(family="calibri", style="", size=11)

def fill_document(doc: FPDF, article: str, client: str, currency: str, items: list):
	if article == "q.track":
		fill_q_track(doc, article, client, currency, items)
	elif article == "q.track.survey":
		fill_q_track_survey(doc, article, client, currency, items)

def fill_q_track(doc: FPDF, article: str, client: str, currency: str, items: list):
	info_section(doc, article, client, "5.png")
	subtitle(doc, "INDÍCE")
	# paragraph(doc)

	TABLE_DATA = (
		("1.", "APRESENTAÇÃO", "4"),
		("2.", "Q.TRACK", "5"),
		("2.1", "Descrição do Sistema", "6"),
		("2.1.1.", "Aplicações do Q.track", "7"),
		("2.1.2.", "QInfoScreen", "8"),
		("2.1.3.", "QComposer", "9"),
		("2.1.4.", "QKiosk", "9"),
		("2.1.5.", "QUser", "10"),
		("2.1.6.", "QWebAdmin", "11"),
		("3.", "PREÇOS E CONDIÇÕES", "12"),
		("3.1.", "Preços", "12"),
		("3.2.", "Condições", "13"),
		("4.", "REFERÊNCIAS", "14"),
		("", "", ""),
	)

	doc.set_font(style="", size=11)
	with doc.table(col_widths=(10, 83, 7), text_align=("LEFT", "LEFT", "RIGHT")) as table:
		for data_row in TABLE_DATA:
			row = table.row() 
			for datum in data_row:
				row.cell(datum, style=FontFace(emphasis="ITALICS"), border=0)
	
	# paragraph(doc)
	doc.image(get_image(article, "Picture2.png"), w=188.72, h=115.32)

	change_title(doc, "1.	APRESENTAÇÃO")
	doc.write_html("""
		<p style="line-height:1.7; text-align: justify;">A <strong>Logicpulse</strong> prop&otilde;e um <strong>sistema avan&ccedil;ado com interface Web para efetuar a gest&atilde;o de filas de atendimento ao p&uacute;blico</strong>. <br />Este sistema permite gerir um n&uacute;mero de servi&ccedil;os limitado pelo terminal apresentado, tornando o atendimento mais eficaz e eficiente, ajudando a reduzir o tempo de espera dos utentes aumentando assim a satisfa&ccedil;&atilde;o dos mesmos, com indica&ccedil;&atilde;o de tempo de previs&atilde;o de atendimento. <br />O <strong><font color="#1b97d3">Q</font>.track</strong> permite o <strong>ativar</strong> e <strong>desativar</strong> balc&otilde;es de atendimento atrav&eacute;s da aplica&ccedil;&atilde;o central, toda a gest&atilde;o e intera&ccedil;&atilde;o do software &eacute; feita atrav&eacute;s de um browser (Internet Explorer, Mozilla Firefox, Google Chrome) n&atilde;o necessitando de ser instalado em cada computador nos balc&otilde;es de atendimento.<br />Desta forma, possibilita manter um controlo eficaz e eficiente sobre o fluxo de atendimento, servi&ccedil;os mais requisitados assim como, relat&oacute;rios da rapidez do atendimento de cada colaborador, sendo uma ferramenta que promove a produtividade dos colaboradores destacados nos servi&ccedil;os de atendimento ao p&uacute;blico.</p>
	""")
	doc.write_html("""
		<p style="text-align: justify;"><strong><em><u>As VANTAGENS do sistema são:</u></em></strong></p>
			<ul style="line-height:1.7;">
				<li style="text-align: justify;">• Aviso automático de entrada de novas senhas;</li>
				<li style="text-align: justify;">• Atualização automática do número de senhas por atender;</li>
				<li style="text-align: justify;">• Relatórios em tempo real dos serviços de atendimento;</li>
				<li style="text-align: justify;">• Definição de regras de prioridade de atendimento;</li>
				<li style="text-align: justify;">• Produção de relatórios sobre vários parâmetros (ex. tempo de utilização);</li>
			</ul>
		<p> </p>
	""")
	doc.image(get_image(article, "19.jpg"), w=188.72, h=80.32)
	doc.image(get_image(article, "18.png"), w=188.72, h=20.32)
 
	change_title(doc, "2.	Q.TRACK")
	doc.write_html("""
		<p style="line-height: 1.7; text-align: justify;">O <strong><font color="#1b97d3">Q</font>.track</strong> é uma solução pensada e dimensionada para efetuar a gestão de atendimento em qualquer tipo de local, com qualquer tipo de requisitos.<br /> Apresentamos um breve resumo do sucesso da aplicação na área da gestão de filas, esta baseia-se em vários projetos implementados com sucesso no terreno, e dos quais destacamos, o projeto no Centro Hospitalar de Coimbra, unidade dos Covões. <br />Este projeto consiste num sistema de gestão de consultas totalmente integrado com o software de gestão SONHO. Nesta instalação, o utente identifica-se na receção do serviço e confirma a sua consulta, esta informação é adicionada ao sistema do médico que está a realizar as consultas, possibilitando ao médico aceder a informação em tempo real dos utentes em espera e realizar a chamada automática dos utentes (pelo seu nome) através do ecrã instalado na sala de espera.</p>
		<p style="text-align: justify;"><strong>O sistema inclui:</strong></p>
		<ul style="line-height: 1.7;">
			<li style="text-align: justify;">• Quiosque dispensador de senhas;</li>
			<li style="text-align: justify;">• Ecrã LCD (opcional);</li>
			<li style="text-align: justify;">• Pc Box (opcional);</li>
			<li style="text-align: justify;">• SOFTWARE de Gestão de Filas “<strong><font color="#1b97d3">Q</font>.track</strong>” multiposto;</li>
			<li style="text-align: justify;">• INSTALAÇÃO no local;</li>
			<li style="text-align: justify;">• FORMAÇÃO a utilizadores</li>
		</ul>
		<p> </p>
	""")

	doc.image(get_image(article, "Picture5.png"), w=188.72, h=100.32)
	change_title(doc, "2.1.	Descrição do Sistema")
	doc.write_html("""
		<p style="line-height: 1.7; text-align: justify;">A solução <strong><font color="#1b97d3">Q</font>.track</strong> é uma ferramenta modular e de baixo custo que lhe permite gerir as filas de espera/atendimento de 1 ou mais locais com múltiplos serviços, fornecendo dados em tempo real através da web de forma a poderem ser tomadas decisões por parte dos gestores sobre o funcionamento do atendimento dos seus serviços.</p> 
		<p></p>
	""")
	paragraph(doc)
	doc.image(get_image(article, "28.jpg"), w=188.72, h=100.32)
	doc.image(get_image(article, "27.png"), w=188.72, h=50.32)
	doc.write_html("""
		<p style="line-height: 1.7; text-align: justify;">Toda a solução foi pensada de forma a se adaptar a diferentes necessidades de configuração dos serviços e de diferentes tipos de hardware utilizado, podendo ser utilizado com dispensadores de senhas multimédia ou simples dispensadores de botão, podendo mostrar a informação das filas em ecrãs multimédia com publicidade associada (e Corporate TV) ou então com simples painéis de chamada numéricos. Desta forma conseguimos satisfazer desde o simples atendimento numa empresa até grandes serviços de atendimentos públicos.</p>
	""")
	doc.write_html("""
		<p><strong>As principais caraterísticas do <font color="#1b97d3">Q</font>.track</strong> <strong>são: </strong></p>
		<ul style="line-height: 1.7;">
			<li>• Melhoria da imagem da sua organização</li>
			<li>• Aumento da satisfação dos clientes</li>
			<li>• Redução do tempo de espera</li>
			<li>• Mais qualidade no serviço prestado aos clientes</li>
			<li>• Melhor aproveitamento dos recursos humanos</li>
			<li>• Maior produtividade e eficácia dos recursos humanos</li>
			<li>• Reencaminhamento de utentes entre serviços através de prioridades de atendimento por serviço</li>
			<li>• Possibilidade de funcionamento de todo o sistema via web</li>
			<li>• Conhecimento de todos os indicadores de atendimento via web</li>
			<li>• Inserção de publicidade sobre produtos ou serviços aproveitando o tempo de espera dos clients</li>
		</ul>
		<p> </p>
	""")

	subtitle(doc, "2.1.1.	Aplicações do Q.track")

	doc.write_html("""
		<p style="line-height: 1.7; text-align: justify;">Como o sistema <strong><font color="#1b97d3">Q</font>.track</strong> assenta numa arquitetura distribuída, existem diversas aplicações que podem funcionar de forma autónoma, no entanto é possível utilizar todas as aplicações da solução <strong><font color="#1b97d3">Q</font>.track</strong> através de interfaces web utilizando a nova tecnologia XAML Browser Application (XBAP).<br/>
		Apresentamos de seguida o diagrama com as principais aplicações do sistema, seguida de uma pequena explicação.</p>
	""")

	doc.image(get_image(article, "Picture6.png"), w=188.72, h=80.32)
	doc.add_page()
	subtitle(doc, "2.1.2.	QInfoScreen")
	doc.write_html("""
		<p style="line-height: 1.7; text-align: justify;">A aplicação que informa os utentes do estado do(s) serviço(s) e chamar o próximo utente a ser atendido. Para além disso permite mostrar mensagens que o administrador entender, podendo por um espaço temporal nas mensagens.</p>
	""")
	paragraph(doc, 10)
	doc.image(get_image(article, "37.jpg"), w=188.72, h=100.32)
	doc.image(get_image(article, "36.png"), w=188.72, h=40.32)
	doc.add_page()
	subtitle(doc, "2.1.3.	QComposer")
	doc.write_html("""
		<p style="line-height: 1.7; text-align: justify;">A aplicação <strong>QComposer</strong> possibilita ao gestor/administrador do <strong><font color="#1b97d3">Q</font>.track</strong> a geração dinâmica dos conteúdos que são mostrados no display de chamada.<br /> Esta composição dos conteúdos é efetuada através de simples “drag and drop” e possibilita a inclusão de texto, vídeos, slideshow de imagens, Apresentação PowerPoint, conteúdos RSS, TV, streaming de vídeo, etc.</p>
	""")
	paragraph(doc, 10)
	subtitle(doc, "2.1.4.	QKiosk")
	doc.write_html("""
		<p style="line-height: 1.7; text-align: justify;">Permite ao utente tirar uma senha de espera. Esta aplicação só irá disponibilizar os serviços que se encontrem activos, ou seja, os serviços que estão a ser atendidos no momento.</p>
	""")
	paragraph(doc, 10)
	doc.image(get_image(article, "39.jpg"), w=188.72, h=100.32)
	doc.image(get_image(article, "38.png"), w=188.72, h=40.32)
	doc.add_page()
	subtitle(doc, "2.1.5.	QUser")
	doc.write_html(""" 
		<p style="line-height: 1.7; text-align: justify;">A aplicação <strong>QUser</strong> permite aos funcionários de atendimento:</p>
		<ul style="line-height: 1.7;>
			<li style="text-align: justify;">Escolher o balcão a ativar;</li>
			<li style="text-align: justify;">Ativar os serviços que o utilizador pretender;</li>
			<li style="text-align: justify;">Chamar os utentes;</li>
			<li style="text-align: justify;">Escolher o tipo de processamento do utente a ser chamado através do tempo de espera do utente, da fila de espera, e do tempo de atendimento do serviço. Para além destes modos de seleção, poderá ser ativada a prioridades dos serviços;</li>
			<li style="text-align: justify;">Disponibiliza a média de atendimentos do utilizador que está a atender, o número de pessoas atendidas, o próximo utente a ser chamado, e mostrar as últimas 18 sessões que o utilizador iniciou mostrando os utentes atendidos em cada uma dessas sessões através de um gráfico.</li>
		</ul>
	""")
	paragraph(doc, 10)
	doc.cell(70)
	doc.image(get_image(article, "41.png"), h=120.32)
	doc.add_page()
	subtitle(doc, "2.1.6.	QWebAdmin")
	doc.write_html("""
		<p style="line-height: 1.7; text-align: justify;">Toda a gestão da aplicação é efetuada no <strong>QWebAdmin</strong> através de um browser Web, possibilitando ao administrador/gestor efetuar a configuração dos postos de atendimento e consultar alguns relatórios de atendimento em qualquer parte do mundo. Esta aplicação tem como principais caraterísticas:</p>
		<ul style="line-height: 1.7;">
			<li style="text-align: justify;">Dashboard com dados estatísticos em tempo real;</li>
			<li style="text-align: justify;">Adicionar/Editar/Desativar serviços;</li>
			<li style="text-align: justify;">Associar um posto de atendimento a um serviço;</li>
			<li style="text-align: justify;">Adicionar/Editar/desativar postos de atendimento + Departamentos;</li>
			<li style="text-align: justify;">Adicionar/Editar/desativar utilizadores;</li>
			<li style="text-align: justify;">Adicionar/Editar mensagens para o QInfoscreen;</li>
			<li style="text-align: justify;">Gestão de todos os conteúdos mutimédia e templates do QInfoscreen + QKiosk;</li>
			<li style="text-align: justify;">Consulta e geração de relatórios (atendimento por utilizador e afluência ao serviço)</li>
		</ul>
	""")
	paragraph(doc, 10)
	doc.image(get_image(article, "43.png"), w=188.72, h=100.32)
	doc.image(get_image(article, "42.png"), w=188.72, h=40.32)

	change_title(doc, "3.	PREÇOS E CONDIÇÕES")
	subtitle(doc, "3.1.	Preços")
	add_grouped_prices_table(doc, currency, items)
	paragraph(doc, 5)
	doc.set_font(style="U", size=10)
	doc.write_html("""
		<p style="text-align: center;"><u>NOTA: Aos valores apresentados acresce os impostos em vigor à data da faturação.</u></p>
	""")
	doc.add_page()
	subtitle(doc, "3.2.	Condições")
	doc.set_font(style="", size=11)
	doc.write_html("""
		<p style="line-height: 1.7; text-align: justify;"><strong><em><u>Serviços incluídos</u></em></strong></p>
		<ul style="line-height: 1.7;">
			<li style="text-align: justify;">Montagem e fixação do Hardware;</li>
			<li style="text-align: justify;">Todas as ligações (rede elétrica, Ethernet, etc.) deverão estar nos locais de instalação;</li>
		</ul>
		<p style="line-height: 1.0; text-align: justify;">(Nota: distâncias de cablagem superiores a 2 metros serão orçamentadas em separado.)</p>
		<ul style="line-height: 1.7;">
			<li style="text-align: justify;">Instalação de softwares no servidor e de 1 posto de trabalho (no caso de licença adicional) + Instalação da aplicação <strong><font color="#1b97d3">Q</font>.track</strong> nos Postos de atendimento (nº de instalação dependendo da versão da licença);</li>
			<li style="text-align: justify;">Formação a 1 “master-user” e utilizadores (todas as formações num único dia).</li>
		</ul>
		<p><strong><em><u>Exclusões à proposta</u></em></strong></p>
		<p style="line-height: 1.7; text-align: justify;">Não estão incluídos trabalhos de construção civil para instalação dos equipamentos nem cablagem necessária. <br />Esta proposta não inclui deslocações adicionais que sejam necessárias por impossibilidade de acesso ou avaria dos equipamentos já existentes que impossibilite a conclusão da instalação, e que vão para além do que incluído nesta proposta. Se existir uma deslocação adicional será cobrada com base numa taxa de <strong>1 USD</strong>/ km.</p>
		<p><strong><em><u>Garantia</u></em></strong></p>
		<p style="line-height: 1.7; text-align: justify;">Todos os equipamentos têm uma garantia de 12 meses contra defeito de fabrico e montagem. <br />São disponibilizadas atualizações do software grátis durante um período de 12 meses.</p>
		<p><strong><em><u>Prazo de entrega</u></em></strong></p>
		<p style="line-height: 1.7; text-align: justify;">No máximo 6 semanas, incluindo tempo de transporte e instalação, após a receção da encomenda devidamente clara e específica, assinatura do respetivo contrato de fornecimento e pagamento dos 50% da adjudicação.</p>
		<p><strong><em><u>Condições de Pagamento de Aquisição</u></em></strong></p>
		<p style="line-height: 1.7; text-align: justify;"><strong>50%</strong> Com a adjudicação + <strong>50%</strong> com a entrega do equipamento.</p>
		<p><strong><em><u>Validade da proposta</u></em></strong></p>
		<p  style="line-height: 1.7; text-align: justify;">30 Dias</p>
	""") 
	change_title(doc, "4.	AS NOSSAS SOLUÇÕES")
	doc.write_html("""
		<p style="line-height: 1.7; text-align: justify;">A LogicPulse desenvolve e promove Soluções, facultando aos seus clientes competências em várias tecnologias. O nosso Portfolio de Soluções permitirá rentabilizar e credibilizar o seu negócio.
        <br/>Abaixo apresentamos-lhe algumas das nossas soluções:</p>
	""")
	paragraph(doc, 6)
	solution_figures = (
		"q.track.png",
		"acess.track.png",
		"fleet.track.png",
		"frota.track.png",
		"pos.png",
	)
	for i, fig in enumerate(solution_figures):
		doc.image(get_image(article, fig), w=188.72)
		if i < len(solution_figures) - 1:
			paragraph(doc, 4)
	doc.write_html("""
		<p style="line-height: 1.7; text-align: justify;">Nós temos o "Saber Fazer ". Desenvolvemos Soluções á medida e Especializámo-nos em tecnologia.</p>
	""") 
	change_title(doc, "5.	REFERÊNCIAS")
	doc.write_html("""
		<p style="line-height: 1.7; text-align: justify;">Apresentamos de seguida algumas das empresas onde temos instaladas soluções LogicPulse, estas referências podem confirmar a qualidade dos nossos sistemas:</p>
	""")
	paragraph(doc, 6)
	doc.image(get_image(article, "parceiros.png"), w=188.72, h=180.32)
	doc.set_page_background(get_cover(article, '125.png'))
	doc.add_page()

def fill_q_track_survey(doc: FPDF, article: str, client: str, currency: str, items: list):
	info_section(doc, article, client, "8.png")
	subtitle(doc, "INDÍCE")

def info_section(doc: FPDF, article: str, client: str, article_img_name: str):
	subtitle(doc, "INFO DOCUMENTO") 
	client_data = frappe.db.get_value(
		"Customer", 
		client, 
		["customer_name", "first_name", "last_name", "email_id", "mobile_no"], 
		as_dict=1
	)
	
	user = frappe.db.get_value(
		"User",
		{"name": frappe.session.user},
		["full_name", "email", "phone", "mobile_no"],
		as_dict=1
	)

	TABLE_DATA = (
		("Autores:", f"{user.full_name} ▪ {user.email} ▪ Tel: {user.mobile_no}"),
		("Destinatários:", f"{client_data.customer_name}"),
		("Contacto:", f"{client_data.first_name} {client_data.last_name} ▪ {client_data.email_id} ▪ Tel: {client_data.mobile_no}"),
		("Histórico:", ""),
		("", "")
	)
	
	doc.set_font(style="", size=11)
	with doc.table(col_widths=(25, 75), first_row_as_headings=False) as table:
		for data_row in TABLE_DATA:
			row = table.row()
			is_first = True
			for datum in data_row:
				if is_first:
					row.cell(datum, style=FontFace(emphasis="BOLD"), border="TOP")
				else:
					row.cell(datum, border="TOP")
				is_first = False
	
	TABLE_DATA = (
		("DATA:", "VERSÃO", "DESCRIÇÃO", "AUTORES"), 
		(f"{date.today()}", "00", "Criação do Documento", f"{user.full_name}")
	)

	doc.set_font(style="", size=9)
	with doc.table(col_widths=(20, 10, 40, 30), headings_style=FontFace(emphasis="BOLD", fill_color=(166, 166, 166))) as table:
		for data_row in TABLE_DATA:
			row = table.row()
			for datum in data_row:
				row.cell(datum)
	
	paragraph(doc) 
	doc.image(get_image(article, article_img_name), w=148.02, h=148.02)
	doc.add_page()

def get_image(article: str, img_name: str) -> str:
	path = os.path.join(asset_dir, article, img_name)
	if not os.path.exists(path):
		frappe.throw(f"Imagem não encontrada!!!")
	return path

def paragraph(doc: FPDF, h: int = 15):
	doc.ln(h)

def subtitle(doc: FPDF, text: str):
	doc.set_font(family="calibri", style="BI", size=14)
	doc.write(text=text)
	paragraph(doc, 10)
	doc.set_font(style="", size=11)

def title(doc: FPDF, text: str):
	doc.set_font(family="calibri", style="B", size=16)
	doc.write(text=text)

def change_title(doc: FPDF, new_title: str):
	doc.add_page()
	title(doc, new_title)
	paragraph(doc, 10)
	doc.set_font(style="", size=11)