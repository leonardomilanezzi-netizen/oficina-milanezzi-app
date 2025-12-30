import os
import json
import re
import traceback
from flask import Flask, request, send_file
from flask_cors import CORS
import google.generativeai as genai
from fpdf import FPDF
from datetime import datetime

app = Flask(__name__)
CORS(app)

[cite_start]# [cite: 4-9] Dados Padronizados Milanezzi
EMPRESA = {
    "nome": "AUTO MECANICA MILANEZZI",
    "proprietario": "FAUSTO MILANEZZI 29382323813",
    "cnpj": "17.865.934/0001-99",
    "fone": "(15) 3355-0707",
    "email": "automecanicamilanezzi@gmail.com",
    "endereco": "RUA MANOEL CIRIACO RAMOS NOGUEIRA, 1316-JD. BELA VISTA - ANGATUBA-SP"
}

# Configuração Segura via Variável de Ambiente
API_KEY = os.getenv("GEMINI_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)
else:
    print("ALERTA: Variável GEMINI_API_KEY não configurada no Render!")

model = genai.GenerativeModel('gemini-1.5-flash')

# Funções Auxiliares de Limpeza e Segurança
def limpar_valor(valor):
    if isinstance(valor, (int, float)): return float(valor)
    texto = str(valor).replace('R$', '').replace('.', '').replace(',', '.').strip()
    try:
        return float(re.findall(r"[-+]?\d*\.\d+|\d+", texto)[0])
    except:
        return 0.0

def s(t):
    """Trata acentos para evitar Erro 500 no FPDF"""
    return str(t).encode('latin-1', 'replace').decode('latin-1')

@app.route('/')
def home():
    return "Servidor Milanezzi Online e Configurado!"

@app.route('/gerar-pdf', methods=['POST'])
def gerar_pdf():
    try:
        dados_requisicao = request.json
        texto_usuario = dados_requisicao.get('texto', '')

        prompt = (
            f"Extraia os dados desta Ordem de Serviço: '{texto_usuario}'. "
            "Retorne APENAS um JSON puro (sem markdown) neste formato exato: "
            "{{'cliente': '', 'veiculo': '', 'placa': '', 'km': '', 'chassi': '', "
            "'produtos': [{{'qtd': 0, 'desc': '', 'unit': 0.0}}], "
            "'servicos': [{{'desc': '', 'valor': 0.0}}]}}"
        )
        
        response = model.generate_content(prompt)
        json_limpo = re.sub(r'```json|```', '', response.text).strip()
        data = json.loads(json_limpo)

        # --- PROCESSAMENTO DE REGRAS E MATEMÁTICA (PYTHON) ---
        # 1. Placa em Maiúsculo
        placa_formatada = str(data.get('placa', '')).upper()

        # 2. Produtos com descrição capitalizada e cálculo rigoroso
        total_produtos = 0
        for p in data.get('produtos', []):
            p['desc'] = str(p.get('desc', '')).strip().capitalize()
            p['qtd'] = limpar_valor(p.get('qtd', 0))
            p['unit'] = limpar_valor(p.get('unit', 0))
            p['total_item'] = p['qtd'] * p['unit']
            total_produtos += p['total_item']

        # 3. Serviços com descrição capitalizada e cálculo rigoroso
        total_servicos = 0
        for serv in data.get('servicos', []):
            serv['desc'] = str(serv.get('desc', '')).strip().capitalize()
            serv['valor'] = limpar_valor(serv.get('valor', 0))
            total_servicos += serv['valor']

        total_geral = total_produtos + total_servicos #

        # --- CONSTRUÇÃO DO PDF ---
        pdf = FPDF()
        pdf.add_page()
        
        # [cite_start]Cabeçalho Esquerda (Logo e Empresa) [cite: 4-9]
        if os.path.exists("logo.png"):
            pdf.image("logo.png", 10, 8, 33)
            pdf.set_x(45)
        
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 6, s(EMPRESA["nome"]), ln=True)
        pdf.set_font("Arial", size=9)
        x_off = 45 if os.path.exists("logo.png") else 10
        pdf.set_x(x_off)
        pdf.cell(0, 5, s(EMPRESA["proprietario"]), ln=True)
        pdf.set_x(x_off)
        pdf.cell(0, 5, s(f"CNPJ: {EMPRESA['cnpj']}"), ln=True)
        pdf.set_x(x_off)
        pdf.cell(0, 5, s(f"{EMPRESA['fone']} | {EMPRESA['email']}"), ln=True)
        
        # [cite_start]Cabeçalho Direita (Título sem 'Número' e Data) [cite: 10, 11]
        pdf.set_font("Arial", 'B', 11)
        pdf.text(145, 15, s("Ordem de servico")) # Removido "Numero"
        pdf.set_font("Arial", size=9)
        pdf.text(145, 20, s(f"Entrada: {datetime.now().strftime('%d/%m/%Y')}"))

        pdf.set_x(x_off)
        pdf.multi_cell(0, 5, s(EMPRESA["endereco"]))
        pdf.ln(5)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)

        # [cite_start]Dados do Veículo [cite: 1, 2, 12, 13]
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 6, s(f"Cliente: {data.get('cliente', '').upper()}"), ln=True)
        pdf.set_font("Arial", size=10)
        pdf.cell(0, 6, s(f"Veiculo: {data.get('veiculo', '')}  |  Placa: {placa_formatada}"), ln=True)
        pdf.cell(0, 6, s(f"Km: {data.get('km', '')}  |  Chassi: {data.get('chassi', '')}"), ln=True)
        pdf.ln(5)

        # Tabela de Produtos
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 8, s("Produtos"), ln=True)
        pdf.set_fill_color(245, 245, 245)
        pdf.cell(15, 8, "Qtd", 1, 0, 'C', True)
        pdf.cell(100, 8, s("Descricao"), 1, 0, 'L', True)
        pdf.cell(35, 8, "Valor Unit.", 1, 0, 'C', True)
        pdf.cell(40, 8, "Valor Total", 1, 1, 'C', True)

        pdf.set_font("Arial", size=9)
        for p in data.get('produtos', []):
            pdf.cell(15, 7, str(int(p['qtd'])), 1, 0, 'C')
            pdf.cell(100, 7, s(p['desc']), 1)
            pdf.cell(35, 7, f"R$ {p['unit']:.2f}", 1, 0, 'R')
            pdf.cell(40, 7, f"R$ {p['total_item']:.2f}", 1, 1, 'R')
        
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(190, 8, s(f"Total De Produtos: R$ {total_produtos:.2f}"), ln=True, align='R') #

        # Tabela de Serviços
        pdf.ln(5)
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 8, s("Servicos"), ln=True)
        pdf.cell(150, 8, s("Descricao"), 1, 0, 'L', True)
        pdf.cell(40, 8, "Valor Total", 1, 1, 'C', True)
        
        pdf.set_font("Arial", size=9)
        for srv in data.get('servicos', []):
            pdf.cell(150, 7, s(srv['desc']), 1)
            pdf.cell(40, 7, f"R$ {srv['valor']:.2f}", 1, 1, 'R')
            
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(190, 8, s(f"Total De Servicos: R$ {total_servicos:.2f}"), ln=True, align='R') #

        # Resumo Final e Total Geral
        pdf.ln(5)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(190, 12, s(f"TOTAL: R$ {total_geral:.2f}"), border=1, ln=True, align='R')

        path = os.path.join(os.getcwd(), "Orcamento_Milanezzi_Final.pdf")
        pdf.output(path)
        return send_file(path, as_attachment=True)

    except Exception as e:
        print(f"ERRO NO SERVIDOR:\n{traceback.format_exc()}")
        return f"Erro técnico: {str(e)}", 500

if __name__ == '__main__':
    # Configuração para nuvem (Render)
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
