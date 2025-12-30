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

# [cite_start] [cite: 4-9] Dados Oficiais Milanezzi
EMPRESA = {
    "nome": "AUTO MECANICA MILANEZZI",
    "proprietario": "FAUSTO MILANEZZI 29382323813",
    "cnpj": "17.865.934/0001-99",
    "fone": "(15) 3355-0707",
    "email": "automecanicamilanezzi@gmail.com",
    "endereco": "RUA MANOEL CIRIACO RAMOS NOGUEIRA, 1316-JD. BELA VISTA - ANGATUBA-SP"
}

# Configuração de Segurança: A chave deve estar no Environment do Render
API_KEY = os.getenv("GEMINI_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)
else:
    print("ERRO: Variável GEMINI_API_KEY não configurada no Render!")

# Usando 1.5-flash para maior estabilidade e cota gratuita
model = genai.GenerativeModel('gemini-2.5-flash')

def limpar_valor(valor):
    """Garante que preços como 'R$ 40,00' virem números decimais"""
    if isinstance(valor, (int, float)): return float(valor)
    texto = str(valor).replace('R$', '').replace('.', '').replace(',', '.').strip()
    try:
        numeros = re.findall(r"[-+]?\d*\.\d+|\d+", texto)
        return float(numeros[0]) if numeros else 0.0
    except:
        return 0.0

def s(t):
    """Trata acentos para evitar erro 500 no PDF"""
    return str(t).encode('latin-1', 'replace').decode('latin-1')

@app.route('/')
def home():
    return "Servidor Milanezzi Online e Protegido!"

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

        # --- PADRONIZAÇÃO RIGOROSA ---
        placa_maiuscula = str(data.get('placa', '')).upper() #

        # Processamento de Produtos
        total_produtos = 0
        for p in data.get('produtos', []):
            p['desc'] = str(p.get('desc', '')).strip().capitalize() #
            p['qtd'] = limpar_valor(p.get('qtd', 0))
            p['unit'] = limpar_valor(p.get('unit', 0))
            p['total_item'] = p['qtd'] * p['unit'] # Cálculo garantido
            total_produtos += p['total_item']

        # Processamento de Serviços
        total_servicos = 0
        for sv in data.get('servicos', []):
            sv['desc'] = str(sv.get('desc', '')).strip().capitalize() #
            sv['valor'] = limpar_valor(sv.get('valor', 0))
            total_servicos += sv['valor']

        # --- CONSTRUÇÃO DO PDF (LAYOUT IDÊNTICO AO MODELO) ---
        pdf = FPDF()
        pdf.add_page()
        
        # [cite_start]Cabeçalho Esquerda (Logo e Empresa) [cite: 1-4, 6]
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
        
        # Cabeçalho Direita (Título sem 'Numero')
        pdf.set_font("Arial", 'B', 11)
        pdf.text(145, 15, s("Ordem de servico")) 
        pdf.set_font("Arial", size=9)
        pdf.text(145, 20, s(f"Entrada: {datetime.now().strftime('%d/%m/%Y')}"))
        
        pdf.set_x(x_off)
        pdf.multi_cell(0, 5, s(EMPRESA["endereco"]))
        pdf.ln(5)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)

        # [cite_start]Dados Cliente e Veículo [cite: 7, 8]
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 6, s(f"Cliente: {data.get('cliente', '').upper()}"), ln=True)
        pdf.set_font("Arial", size=10)
        pdf.cell(0, 6, s(f"Veiculo: {data.get('veiculo', '')}  |  Placa: {placa_maiuscula}"), ln=True)
        pdf.cell(0, 6, s(f"Km: {data.get('km', '')}  |  Chassi: {data.get('chassi', '')}"), ln=True)
        pdf.ln(5)

        # [cite_start]Tabela de Produtos [cite: 10]
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 8, s("Produtos"), ln=True)
        pdf.set_fill_color(240, 240, 240) # Cinza claro para o cabeçalho
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

        # [cite_start]Tabela de Serviços [cite: 12]
        pdf.ln(5)
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 8, s("Servicos"), ln=True)
        pdf.cell(150, 8, s("Descricao"), 1, 0, 'L', True)
        pdf.cell(40, 8, "Valor Total", 1, 1, 'C', True)
        
        pdf.set_font("Arial", size=9)
        for sv in data.get('servicos', []):
            pdf.cell(150, 7, s(sv['desc']), 1)
            pdf.cell(40, 7, f"R$ {sv['valor']:.2f}", 1, 1, 'R')

        # [cite_start]Resumo e Total Geral [cite: 13-15]
        pdf.ln(5)
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(190, 7, s(f"Total De Produtos: R$ {total_produtos:.2f}"), ln=True, align='R')
        pdf.cell(190, 7, s(f"Total De Servicos R$ {total_servicos:.2f}"), ln=True, align='R')
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(190, 12, s(f"TOTAL: R$ {total_produtos + total_servicos:.2f}"), border=1, ln=True, align='R')

        path = os.path.join(os.getcwd(), "OS_Milanezzi.pdf")
        pdf.output(path)
        return send_file(path, as_attachment=True)

    except Exception:
        print(f"ERRO NO SERVIDOR:\n{traceback.format_exc()}")
        return "Erro interno no servidor", 500

if __name__ == '__main__':
    # Porta dinâmica para Render
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
