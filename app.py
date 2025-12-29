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

# [cite_start]Dados Milanezzi [cite: 4-9]
EMPRESA = {
    "nome": "AUTO MECANICA MILANEZZI",
    "proprietario": "FAUSTO MILANEZZI 29382323813",
    "cnpj": "17.865.934/0001-99",
    "fone": "(15) 3355-0707",
    "email": "automecanicamilanezzi@gmail.com",
    "endereco": "RUA MANOEL CIRIACO RAMOS NOGUEIRA, 1316-JD. BELA VISTA - ANGATUBA-SP"
}

# Configuração da API
API_KEY = os.getenv("GEMINI_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

@app.route('/')
def home():
    return "Servidor Milanezzi Online!"

@app.route('/gerar-pdf', methods=['POST'])
def gerar_pdf():
    try:
        dados = request.json
        texto_usuario = dados.get('texto', '')
        print(f"Recebido: {texto_usuario[:50]}...")

        prompt = (
            f"Extraia os dados desta OS: '{texto_usuario}'. "
            "Retorne APENAS um JSON (sem markdown) neste formato: "
            "{'cliente': '', 'veiculo': '', 'placa': '', 'km': '', 'chassi': '', "
            "'produtos': [{'qtd': 0, 'desc': '', 'unit': 0.0}], "
            "'servicos': [{'desc': '', 'valor': 0.0}]}"
        )
        
        response = model.generate_content(prompt)
        # Limpeza de texto da IA para evitar erros de JSON
        json_limpo = re.sub(r'```json|```', '', response.text).strip()
        data = json.loads(json_limpo)

        # Matematica via Python
        total_prod = sum(float(p.get('qtd', 0)) * float(p.get('unit', 0)) for p in data.get('produtos', []))
        total_serv = sum(float(s.get('valor', 0)) for s in data.get('servicos', []))

        # Criar PDF
        pdf = FPDF()
        pdf.add_page()
        
        # Cabeçalho Seguro (Tratando acentos para não travar o FPDF)
        def txt_seguro(t):
            return str(t).encode('latin-1', 'replace').decode('latin-1')

        if os.path.exists("logo.png"):
            pdf.image("logo.png", 10, 8, 30)
            pdf.set_x(45)
        
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(0, 5, txt_seguro(EMPRESA["nome"]), ln=True)
        pdf.set_font("Arial", size=8)
        pdf.set_x(45 if os.path.exists("logo.png") else 10)
        pdf.cell(0, 4, txt_seguro(EMPRESA["proprietario"]), ln=True)
        pdf.ln(10)

        # Conteúdo do Orçamento
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 10, txt_seguro(f"Cliente: {data.get('cliente', 'N/A')}"), ln=True)
        pdf.cell(0, 10, txt_seguro(f"Veiculo: {data.get('veiculo', 'N/A')} | Placa: {data.get('placa', 'N/A')}"), ln=True)
        
        # Tabela de Produtos simplificada para teste
        pdf.ln(5)
        pdf.cell(0, 10, "PRODUTOS:", ln=True)
        pdf.set_font("Arial", size=9)
        for p in data.get('produtos', []):
            pdf.cell(0, 7, txt_seguro(f"{p['qtd']}x {p['desc']} - R$ {p['unit']}"), ln=True)

        pdf.ln(10)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, txt_seguro(f"TOTAL GERAL: R$ {total_prod + total_serv:.2f}"), border=1, ln=True, align='R')

        path = os.path.join(os.getcwd(), "os.pdf")
        pdf.output(path)
        return send_file(path, as_attachment=True)

    except Exception as e:
        print(f"ERRO DETALHADO NO RENDER:\n{traceback.format_exc()}")
        return f"Erro no servidor: {str(e)}", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
