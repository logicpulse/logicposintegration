from datetime import date
import frappe 
from fpdf import FPDF, Align, FontFace, TextStyle
import os

root_dir = os.path.join(frappe.get_app_path('logicposintegration', 'logicpos_integration', 'proposals'))
asset_dir = os.path.join(root_dir, 'assets')

datas = {
	"q.track": {
		"footer_description": "iPQ02.04-01 - Logicpulse - Gestão de Filas - Q.track",
		"p1": "sistema avançado com interface Web para efetuar a gestão de filas de atendimento ao público"
	}
}

class PDF(FPDF):
	def __init__(self, client_name="", footer_description=""):
		super().__init__()
		self.client_name = client_name
		self.footer_description = footer_description

	def header(self): 
		if self.page_no() == 1:
			return
		
		self.set_fill_color(254, 251, 250)
		self.set_text_color(64, 64, 64) 
		self.set_font("helvetica", style="B", size=9) 
		self.set_draw_color(27, 151, 211) # border color
		self.ln(10)
		self.cell(80, 5, self.client_name, border=1, align=Align.L, fill=True)  
		self.ln(15)

	def footer(self):
		if self.page_no() == 1:
			return
		self.set_y(-13)
		self.set_font("helvetica", style="I", size=8) 
		self.set_text_color(64, 64, 64)
		self.cell(70, 8, self.footer_description, border=0, align=Align.L) 
		self.cell(0, 10, f"          {self.page_no()}", align=Align.R)

@frappe.whitelist()
def generate_proposal(article: str, client: str, currency: str) -> str:
	try:
		doc = PDF(
            client_name=client,
            footer_description=datas.get(article).get("footer_description")
        )
		doc.set_page_background(get_cover(article, 'capa.png'))
		doc.add_page()  
		doc.set_page_background(get_cover(article, 'background_image.jpg'))
		doc.add_page()  
		add_fonts(doc) 
		
		fill_document(doc, article, client, currency)

		file_name = f"ppt_{article}_{currency.lower()}_{client.lower()}.pdf" 
		public_file_path = frappe.utils.get_site_path("public", "files", file_name) 
		doc.output(public_file_path) 
		port = frappe.conf.webserver_port or 8080 
		url_base = frappe.utils.get_url()

		if f":{port}" not in url_base:
			url_base += f":{port}"
		full_path = url_base + '/files/' + file_name
		
		return full_path
	except Exception as err:
		frappe.log_error(frappe.get_traceback(), "Error")
		frappe.throw(f"Erro ao gerar proposta: {str(err)}")

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

def fill_document(doc: FPDF, article: str, client: str, currency: str):
	if article == "q.track":
		fill_q_track(doc, article, client, currency)

def fill_q_track(doc: FPDF, article: str, client: str, currency: str):
	subtitle(doc, "INFO DOCUMENTO")
	# paragraph(doc)

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
	doc.image(get_image(article, "5.png"), w=148.02, h=148.02)
	doc.add_page()
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
		<p style="line-height:1.7; text-align: justify;">A <strong>Logicpulse</strong> prop&otilde;e um <strong>sistema avan&ccedil;ado com interface Web para efetuar a gest&atilde;o de filas de atendimento ao p&uacute;blico</strong>. <br />Este sistema permite gerir um n&uacute;mero de servi&ccedil;os limitado pelo terminal apresentado, tornando o atendimento mais eficaz e eficiente, ajudando a reduzir o tempo de espera dos utentes aumentando assim a satisfa&ccedil;&atilde;o dos mesmos, com indica&ccedil;&atilde;o de tempo de previs&atilde;o de atendimento. <br />O <strong><span style="color: #1b97d3;">Q</span>.track</strong> permite o <strong>ativar</strong> e <strong>desativar</strong> balc&otilde;es de atendimento atrav&eacute;s da aplica&ccedil;&atilde;o central, toda a gest&atilde;o e intera&ccedil;&atilde;o do software &eacute; feita atrav&eacute;s de um browser (Internet Explorer, Mozilla Firefox, Google Chrome) n&atilde;o necessitando de ser instalado em cada computador nos balc&otilde;es de atendimento.<br />Desta forma, possibilita manter um controlo eficaz e eficiente sobre o fluxo de atendimento, servi&ccedil;os mais requisitados assim como, relat&oacute;rios da rapidez do atendimento de cada colaborador, sendo uma ferramenta que promove a produtividade dos colaboradores destacados nos servi&ccedil;os de atendimento ao p&uacute;blico.</p>
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
		<p style="line-height: 1.7; text-align: justify;">O <strong><a href="#">Q</a>.track</strong> é uma solução pensada e dimensionada para efetuar a gestão de atendimento em qualquer tipo de local, com qualquer tipo de requisitos.<br /> Apresentamos um breve resumo do sucesso da aplicação na área da gestão de filas, esta baseia-se em vários projetos implementados com sucesso no terreno, e dos quais destacamos, o projeto no Centro Hospitalar de Coimbra, unidade dos Covões. <br />Este projeto consiste num sistema de gestão de consultas totalmente integrado com o software de gestão SONHO. Nesta instalação, o utente identifica-se na receção do serviço e confirma a sua consulta, esta informação é adicionada ao sistema do médico que está a realizar as consultas, possibilitando ao médico aceder a informação em tempo real dos utentes em espera e realizar a chamada automática dos utentes (pelo seu nome) através do ecrã instalado na sala de espera.</p>
		<p style="text-align: justify;"><strong>O sistema inclui:</strong></p>
		<ul style="line-height: 1.7;">
			<li style="text-align: justify;">• Quiosque dispensador de senhas;</li>
			<li style="text-align: justify;">• Ecrã LCD (opcional);</li>
			<li style="text-align: justify;">• Pc Box (opcional);</li>
			<li style="text-align: justify;">• SOFTWARE de Gestão de Filas “<strong><a href="#">Q</a>.track</strong>” multiposto;</li>
			<li style="text-align: justify;">• INSTALAÇÃO no local;</li>
			<li style="text-align: justify;">• FORMAÇÃO a utilizadores</li>
		</ul>
		<p> </p>
	""", tag_styles={
			"a": FontFace(color="#1b97d3")
		}
	)

	doc.image(get_image(article, "Picture5.png"), w=188.72, h=100.32)
	change_title(doc, "2.1.	Descrição do Sistema")
	doc.write_html("""
		<p style="line-height: 1.7; text-align: justify;">A solução <strong><a href="#">Q</a>.track</strong> é uma ferramenta modular e de baixo custo que lhe permite gerir as filas de espera/atendimento de 1 ou mais locais com múltiplos serviços, fornecendo dados em tempo real através da web de forma a poderem ser tomadas decisões por parte dos gestores sobre o funcionamento do atendimento dos seus serviços.</p> 
		<p></p>
	""", tag_styles={
			"a": FontFace(color="#1b97d3")
		}
	)
	paragraph(doc)
	doc.image(get_image(article, "28.jpg"), w=188.72, h=100.32)
	doc.image(get_image(article, "27.png"), w=188.72, h=50.32)
	doc.write_html("""
		<p style="line-height: 1.7; text-align: justify;">Toda a solução foi pensada de forma a se adaptar a diferentes necessidades de configuração dos serviços e de diferentes tipos de hardware utilizado, podendo ser utilizado com dispensadores de senhas multimédia ou simples dispensadores de botão, podendo mostrar a informação das filas em ecrãs multimédia com publicidade associada (e Corporate TV) ou então com simples painéis de chamada numéricos. Desta forma conseguimos satisfazer desde o simples atendimento numa empresa até grandes serviços de atendimentos públicos.</p>
	""")
	doc.write_html("""
		<p><strong>As principais caraterísticas do <a href="#">Q</a>.track</strong> <strong>são: </strong></p>
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
	""", tag_styles={
			"a": FontFace(color="#1b97d3")
		}
	)

	subtitle(doc, "2.1.1.	Aplicações do Q.track")

	doc.write_html("""
		<p style="line-height: 1.7; text-align: justify;">Como o sistema <strong><a href="#">Q</a>.track</strong> assenta numa arquitetura distribuída, existem diversas aplicações que podem funcionar de forma autónoma, no entanto é possível utilizar todas as aplicações da solução <strong><a href="#">Q</a>.track</strong> através de interfaces web utilizando a nova tecnologia XAML Browser Application (XBAP).<br/>
		Apresentamos de seguida o diagrama com as principais aplicações do sistema, seguida de uma pequena explicação.</p>
	""", tag_styles={
			"a": FontFace(color="#1b97d3")
		}
	)

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
		<p style="line-height: 1.7; text-align: justify;">A aplicação <strong>QComposer</strong> possibilita ao gestor/administrador do <strong><a href="#">Q</a>.track</strong> a geração dinâmica dos conteúdos que são mostrados no display de chamada.<br /> Esta composição dos conteúdos é efetuada através de simples “drag and drop” e possibilita a inclusão de texto, vídeos, slideshow de imagens, Apresentação PowerPoint, conteúdos RSS, TV, streaming de vídeo, etc.</p>
	""", tag_styles={
			"a": FontFace(color="#1b97d3")
		}
	)
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
			<li style="text-align: justify;">•	Escolher o balcão a ativar;</li>
			<li style="text-align: justify;">•	Ativar os serviços que o utilizador pretender;</li>
			<li style="text-align: justify;">•	Chamar os utentes;</li>
			<li style="text-align: justify;">•	Escolher o tipo de processamento do utente a ser chamado através do tempo de espera do utente, da fila de espera, e do tempo de atendimento do serviço. Para além destes modos de seleção, poderá ser ativada a prioridades dos serviços;</li>
			<li style="text-align: justify;">•	Disponibiliza a média de atendimentos do utilizador que está a atender, o número de pessoas atendidas, o próximo utente a ser chamado, e mostrar as últimas 18 sessões que o utilizador iniciou mostrando os utentes atendidos em cada uma dessas sessões através de um gráfico.</li>
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
			<li style="text-align: justify;">•	Dashboard com dados estatísticos em tempo real;</li>
			<li style="text-align: justify;">•	Adicionar/Editar/Desativar serviços;</li>
			<li style="text-align: justify;">•	Associar um posto de atendimento a um serviço;</li>
			<li style="text-align: justify;">•	Adicionar/Editar/desativar postos de atendimento + Departamentos;</li>
			<li style="text-align: justify;">•	Adicionar/Editar/desativar utilizadores;</li>
			<li style="text-align: justify;">•	Adicionar/Editar mensagens para o QInfoscreen;</li>
			<li style="text-align: justify;">•	Gestão de todos os conteúdos mutimédia e templates do QInfoscreen + QKiosk;</li>
			<li style="text-align: justify;">•	Consulta e geração de relatórios (atendimento por utilizador e afluência ao serviço)</li>
		</ul>
	""")
	paragraph(doc, 10)
	doc.image(get_image(article, "43.png"), w=188.72, h=100.32)
	doc.image(get_image(article, "42.png"), w=188.72, h=40.32)

	change_title(doc, "3.	PREÇOS E CONDIÇÕES")
	subtitle(doc, "3.1.	Preços")

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