import os
import json
import re
from flask import Flask, request, send_file
from flask_cors import CORS
import google.generativeai as genai
from fpdf import FPDF
from datetime import datetime

app = Flask(__name__)
CORS(app)

# DADOS DA EMPRESA (Baseado no modelo GOL-BRUNA.pdf)
EMPRESA = {
    "nome": "AUTO MECANICA MILANEZZI",
    "proprietario": "FAUSTO MILANEZZI 29382323813",
    "cnpj": "17.865.934/0001-99",
    "fone": "(15) 3355-0707",
    "email": "automecanicamilanezzi@gmail.com",
    "endereco": "RUA MANOEL CIRIACO RAMOS NOGUEIRA, 1316-JD. BELA VISTA - ANGATUBA-SP"
}

# Configuração da API via Variável de Ambiente (Segurança)
API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

@app.route('/')
def home():
    return "Servidor da Oficina Rodando!"

@app.route('/gerar-pdf', methods=['POST'])
def gerar_pdf():
    dados_requisicao = request.json
    texto_usuario = dados_requisicao.get('texto', '')

    try:
        prompt = (
            f"Extraia os dados desta Ordem de Serviço: '{texto_usuario}'. "
            "Retorne APENAS um JSON puro (sem markdown) neste formato exato: "
            "{'cliente': '', 'veiculo': '', 'placa': '', 'km': '', 'chassi': '', "
            "'produtos': [{'qtd': 0, 'desc': '', 'unit': 0.0}], "
            "'servicos': [{'desc': '', 'valor': 0.0}]}"
        )
        
        response = model.generate_content(prompt)
        json_limpo = re.sub(r'```json|```', '', response.text).strip()
        data = json.loads(json_limpo)

        # Cálculos Matemáticos
        total_produtos = 0
        for p in data.get('produtos', []):
            p['desc'] = str(p['desc']).capitalize()
            p['unit'] = float(p.get('unit', 0))
            p['qtd'] = float(p.get('qtd', 0))
            p['total_item'] = p['qtd'] * p['unit']
            total_produtos += p['total_item']

        total_servicos = 0
        for s in data.get('servicos', []):
            s['desc'] = str(s['desc']).capitalize()
            s['valor'] = float(s.get('valor', 0))
            total_servicos += s['valor']

        total_geral = total_produtos + total_servicos

        # Geração do PDF (Layout Milanezzi)
        pdf = FPDF()
        pdf.add_page()
        
        if os.path.exists("logo.png"):
            pdf.image("logo.png", 10, 8, 30)
            pdf.set_x(45)
        
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(0, 5, EMPRESA["nome"], ln=True)
        pdf.set_font("Arial", size=8)
        x_offset = 45 if os.path.exists("logo.png") else 10
        pdf.set_x(x_offset)
        pdf.cell(0, 4, EMPRESA["proprietario"], ln=True)
        pdf.set_x(x_offset)
        pdf.cell(0, 4, f"CNPJ: {EMPRESA['cnpj']}", ln=True)
        pdf.set_x(x_offset)
        pdf.cell(0, 4, f"{EMPRESA['fone']} | {EMPRESA['email']}", ln=True)
        pdf.set_x(x_offset)
        pdf.multi_cell(0, 4, EMPRESA["endereco"])

        pdf.ln(5)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)

        pdf.set_font("Arial", 'B', 9)
        pdf.cell(0, 5, f"Cliente: {data.get('cliente', 'Não informado').upper()}", ln=True)
        pdf.set_font("Arial", size=9)
        pdf.cell(0, 5, f"Veículo: {data.get('veiculo', '')} | Placa: {data.get('placa', '')}", ln=True)
        pdf.cell(0, 5, f"Km: {data.get('km', '')} | Chassi: {data.get('chassi', 'Não informado')}", ln=True)
        pdf.ln(5)

        # Tabelas de Itens
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(0, 7, "Produtos", ln=True)
        pdf.cell(15, 7, "Qtd", 1)
        pdf.cell(100, 7, "Descricao", 1)
        pdf.cell(35, 7, "Valor Unit.", 1)
        pdf.cell(40, 7, "Total", 1, ln=True)

        pdf.set_font("Arial", size=9)
        for p in data.get('produtos', []):
            pdf.cell(15, 6, str(int(p['qtd'])), 1)
            pdf.cell(100, 6, p['desc'], 1)
            pdf.cell(35, 6, f"R$ {p['unit']:.2f}", 1)
            pdf.cell(40, 6, f"R$ {p['total_item']:.2f}", 1, ln=True)
        
        pdf.cell(190, 8, f"Total De Produtos: R$ {total_produtos:.2f}", ln=True, align='R')
        pdf.ln(5)

        pdf.set_font("Arial", 'B', 9)
        pdf.cell(0, 7, "Servicos", ln=True)
        pdf.cell(150, 7, "Descricao", 1)
        pdf.cell(40, 7, "Total", 1, ln=True)
        
        pdf.set_font("Arial", size=9)
        for s in data.get('servicos', []):
            pdf.cell(150, 6, s['desc'], 1)
            pdf.cell(40, 6, f"R$ {s['valor']:.2f}", 1, ln=True)
            
        pdf.cell(190, 8, f"Total De Servicos: R$ {total_servicos:.2f}", ln=True, align='R')

        pdf.ln(5)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(190, 10, f"TOTAL GERAL: R$ {total_geral:.2f}", border=1, ln=True, align='R')

        path = os.path.join(os.getcwd(), "Orcamento.pdf")
        pdf.output(path)
        return send_file(path, as_attachment=True)

    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    # PEÇA CHAVE: O host DEVE ser '0.0.0.0' para funcionar no Render
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

