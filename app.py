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

# Dados Milanezzi baseados no modelo
EMPRESA = {
    "nome": "AUTO MECANICA MILANEZZI",
    "proprietario": "FAUSTO MILANEZZI 29382323813",
    "cnpj": "17.865.934/0001-99",
    "fone": "(15) 3355-0707",
    "email": "automecanicamilanezzi@gmail.com",
    "endereco": "RUA MANOEL CIRIACO RAMOS NOGUEIRA, 1316-JD. BELA VISTA - ANGATUBA-SP"
}

# Configuração Segura
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    print("ALERTA: Variável GEMINI_API_KEY não encontrada no Render!")
else:
    genai.configure(api_key=API_KEY)

model = genai.GenerativeModel('gemini-2.5-flash')

# Função para limpar preços vindo da IA (Ex: "R$ 40,00" -> 40.0)
def limpar_valor(valor):
    if isinstance(valor, (int, float)): return float(valor)
    texto = str(valor).replace('R$', '').replace('.', '').replace(',', '.').strip()
    try:
        return float(re.findall(r"[-+]?\d*\.\d+|\d+", texto)[0])
    except:
        return 0.0

# Função para evitar erros de acento no PDF
def s(t):
    return str(t).encode('latin-1', 'replace').decode('latin-1')

@app.route('/')
def home():
    return "Servidor Milanezzi Online e Protegido!"

@app.route('/gerar-pdf', methods=['POST'])
def gerar_pdf():
    try:
        dados = request.json
        texto_usuario = dados.get('texto', '')
        print(f"Iniciando processamento: {texto_usuario[:30]}...")

        prompt = (
            f"Extraia os dados desta OS: '{texto_usuario}'. "
            "Retorne APENAS o JSON puro (sem markdown) neste formato: "
            "{'cliente': '', 'veiculo': '', 'placa': '', 'km': '', 'chassi': '', "
            "'produtos': [{'qtd': 0, 'desc': '', 'unit': 0.0}], "
            "'servicos': [{'desc': '', 'valor': 0.0}]}"
        )
        
        response = model.generate_content(prompt)
        json_texto = re.sub(r'```json|```', '', response.text).strip()
        data = json.loads(json_texto)

        # Matematica com limpeza de dados
        total_prod = 0
        for p in data.get('produtos', []):
            p['qtd'] = limpar_valor(p.get('qtd', 1))
            p['unit'] = limpar_valor(p.get('unit', 0))
            p['subtotal'] = p['qtd'] * p['unit']
            total_prod += p['subtotal']

        total_serv = sum(limpar_valor(s.get('valor', 0)) for s in data.get('servicos', []))

        # Criar PDF
        pdf = FPDF()
        pdf.add_page()
        
        if os.path.exists("logo.png"):
            pdf.image("logo.png", 10, 8, 30)
            pdf.set_x(45)
        
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(0, 5, s(EMPRESA["nome"]), ln=True)
        pdf.set_font("Arial", size=8)
        pdf.set_x(45 if os.path.exists("logo.png") else 10)
        pdf.cell(0, 4, s(EMPRESA["proprietario"]), ln=True)
        
        # Info Cliente/Veículo
        pdf.ln(10)
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 8, s(f"Cliente: {data.get('cliente', 'N/A')}"), ln=True)
        pdf.set_font("Arial", size=9)
        pdf.cell(0, 6, s(f"Veiculo: {data.get('veiculo', '')} | Placa: {data.get('placa', '')}"), ln=True)
        pdf.cell(0, 6, s(f"KM: {data.get('km', '')}"), ln=True)

        # Tabela de Produtos
        pdf.ln(5)
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(15, 7, "Qtd", 1); pdf.cell(100, 7, s("Descrição"), 1); pdf.cell(35, 7, "Unit.", 1); pdf.cell(40, 7, "Total", 1, ln=True)
        
        pdf.set_font("Arial", size=9)
        for p in data.get('produtos', []):
            pdf.cell(15, 6, str(int(p['qtd'])), 1)
            pdf.cell(100, 6, s(str(p['desc']).capitalize()), 1)
            pdf.cell(35, 6, f"R$ {p['unit']:.2f}", 1)
            pdf.cell(40, 6, f"R$ {p['subtotal']:.2f}", 1, ln=True)

        pdf.set_font("Arial", 'B', 10)
        pdf.cell(190, 10, f"TOTAL GERAL: R$ {total_prod + total_serv:.2f}", border=1, ln=True, align='R')

        caminho = os.path.join(os.getcwd(), "os_final.pdf")
        pdf.output(caminho)
        return send_file(caminho, as_attachment=True)

    except Exception as e:
        print(f"--- ERRO DETALHADO NO RENDER ---")
        print(traceback.format_exc()) # Isso é o que você deve olhar nas logs do Render
        return f"Erro no servidor: {str(e)}", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
