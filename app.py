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

[cite_start]# [cite: 1, 2] Dados Padronizados conforme modelo Milanezzi
EMPRESA = {
    "nome": "AUTO MECANICA MILANEZZI",
    "proprietario": "FAUSTO MILANEZZI 29382323813",
    "cnpj": "17.865.934/0001-99",
    "fone": "(15) 3355-0707",
    "email": "automecanicamilanezzi@gmail.com",
    "endereco": "RUA MANOEL CIRIACO RAMOS NOGUEIRA, 1316-JD. BELA VISTA - ANGATUBA-SP"
}

# Configuração Segura (Mantendo a lógica que deu certo)
API_KEY = os.getenv("GEMINI_API_KEY")
if API_KEY:
    genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-2.5-flash')

def limpar_valor(valor):
    if isinstance(valor, (int, float)): return float(valor)
    texto = str(valor).replace('R$', '').replace('.', '').replace(',', '.').strip()
    try:
        return float(re.findall(r"[-+]?\d*\.\d+|\d+", texto)[0])
    except:
        return 0.0

def s(t):
    """Trata acentos para evitar erro no FPDF"""
    return str(t).encode('latin-1', 'replace').decode('latin-1')

@app.route('/')
def home():
    return "Servidor Milanezzi Online e Protegido!"

@app.route('/gerar-pdf', methods=['POST'])
def gerar_pdf():
    try:
        dados = request.json
        texto_usuario = dados.get('texto', '')

        prompt = (
            f"Extraia os dados desta OS: '{texto_usuario}'. "
            "Retorne APENAS o JSON puro (sem markdown) neste formato: "
            "{{'cliente': '', 'veiculo': '', 'placa': '', 'km': '', 'chassi': '', "
            "'produtos': [{{'qtd': 0, 'desc': '', 'unit': 0.0}}], "
            "'servicos': [{{'desc': '', 'valor': 0.0}}]}}"
        )
        
        response = model.generate_content(prompt)
        json_texto = re.sub(r'```json|```', '', response.text).strip()
        data = json.loads(json_texto)

        # --- MODIFICAÇÃO VISUAL: PLACA MAIÚSCULA ---
        placa_formatada = str(data.get('placa', '')).upper()

        pdf = FPDF()
        pdf.add_page()
        
        # [cite_start]Cabeçalho [cite: 1]
        if os.path.exists("logo.png"):
            pdf.image("logo.png", 10, 8, 33)
            pdf.set_x(45)
        
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 6, s(EMPRESA["nome"]), ln=True)
        pdf.set_font("Arial", size=9)
        x_pos = 45 if os.path.exists("logo.png") else 10
        pdf.set_x(x_pos)
        pdf.cell(0, 5, s(EMPRESA["proprietario"]), ln=True)
        pdf.set_x(x_pos)
        pdf.cell(0, 5, s(f"CNPJ: {EMPRESA['cnpj']}"), ln=True)
        pdf.set_x(x_pos)
        pdf.cell(0, 5, s(f"{EMPRESA['fone']} | {EMPRESA['email']}"), ln=True)
        
        # --- MODIFICAÇÃO VISUAL: TÍTULO SEM NÚMERO ---
        pdf.set_font("Arial", 'B', 11)
        pdf.text(145, 15, s("Ordem de servico"))
        pdf.set_font("Arial", size=9)
        pdf.text(145, 20, s(f"Entrada: {datetime.now().strftime('%d/%m/%Y')}"))
        
        pdf.set_x(x_pos)
        pdf.multi_cell(0, 5, s(EMPRESA["endereco"]))
        pdf.ln(5)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)

        # [cite_start]Info Cliente/Veículo [cite: 2]
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 6, s(f"Cliente: {data.get('cliente', '').upper()}"), ln=True)
        pdf.set_font("Arial", size=10)
        pdf.cell(0, 6, s(f"Veiculo: {data.get('veiculo', '')} | Placa: {placa_formatada}"), ln=True)
        pdf.cell(0, 6, s(f"Km: {data.get('km', '')} | Chassi: {data.get('chassi', '')}"), ln=True)
        pdf.ln(5)

        # [cite_start]Tabela de Produtos [cite: 3]
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 8, s("Produtos"), ln=True)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(15, 8, "Qtd", 1, 0, 'C', True)
        pdf.cell(100, 8, s("Descricao"), 1, 0, 'L', True)
        pdf.cell(35, 8, "Valor Unit.", 1, 0, 'C', True)
        pdf.cell(40, 8, "Valor Total", 1, 1, 'C', True)
        
        total_prod = 0
        pdf.set_font("Arial", size=9)
        for p in data.get('produtos', []):
            # --- MODIFICAÇÃO VISUAL: ITEM CAPITALIZADO ---
            desc_cap = str(p.get('desc', '')).strip().capitalize()
            qtd = limpar_valor(p.get('qtd', 1))
            unit = limpar_valor(p.get('unit', 0))
            subtotal = qtd * unit
            total_prod += subtotal
            
            pdf.cell(15, 7, str(int(qtd)), 1, 0, 'C')
            pdf.cell(100, 7, s(desc_cap), 1)
            pdf.cell(35, 7, f"R$ {unit:.2f}", 1, 0, 'R')
            pdf.cell(40, 7, f"R$ {subtotal:.2f}", 1, 1, 'R')

        # [cite_start]Tabela de Serviços [cite: 4, 5]
        total_serv = 0
        servicos_lista = data.get('servicos', [])
        if servicos_lista:
            pdf.ln(5)
            pdf.set_font("Arial", 'B', 10)
            pdf.cell(0, 8, s("Servicos"), ln=True)
            pdf.cell(150, 8, s("Descricao"), 1, 0, 'L', True)
            pdf.cell(40, 8, "Valor Total", 1, 1, 'C', True)
            
            pdf.set_font("Arial", size=9)
            for sv in servicos_lista:
                desc_sv = str(sv.get('desc', '')).strip().capitalize()
                valor = limpar_valor(sv.get('valor', 0))
                total_serv += valor
                pdf.cell(150, 7, s(desc_sv), 1)
                pdf.cell(40, 7, f"R$ {valor:.2f}", 1, 1, 'R')

        # [cite_start]Totais Finais [cite: 6]
        pdf.ln(5)
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(190, 7, s(f"Total De Produtos: R$ {total_prod:.2f}"), ln=True, align='R')
        pdf.cell(190, 7, s(f"Total De Servicos R$ {total_serv:.2f}"), ln=True, align='R')
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(190, 12, s(f"TOTAL: R$ {total_prod + total_serv:.2f}"), border=1, ln=True, align='R')

        caminho = os.path.join(os.getcwd(), "Orcamento_Milanezzi.pdf")
        pdf.output(caminho)
        return send_file(caminho, as_attachment=True)

    except Exception:
        print(f"--- ERRO NO RENDER ---\n{traceback.format_exc()}")
        return "Erro interno no servidor", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
