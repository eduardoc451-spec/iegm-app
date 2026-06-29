import streamlit as st
import sqlite3
from io import BytesIO

from datetime import datetime, date
# Bibliotecas para o PDF (Requer: pip install reportlab)
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

# --- 1. FUNÇÕES DE APOIO E BANCO DE DADOS ---

def get_connection():
    return sqlite3.connect("dados_iegm_web.db", check_same_thread=False)

def init_db():
    """Cria a tabela de respostas caso ela ainda não exista."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS respostas (
                id TEXT NOT NULL,
                ano INTEGER NOT NULL,
                valor TEXT,
                pontos INTEGER DEFAULT 0,
                link TEXT,
                PRIMARY KEY (id, ano)
            )
        """)
        conn.commit()

def load_respostas(ano):
    dados_ano = {}
    try:
        with get_connection() as conn:
            cursor = conn.execute("SELECT id, valor, pontos, link FROM respostas WHERE ano = ?", (ano,))
            rows = cursor.fetchall()
            for row in rows:
                dados_ano[row[0]] = {"valor": row[1], "pontos": row[2], "link": row[3]}
    except Exception:
        pass
    return dados_ano

def save_resp(qid, valor, pontos, link):
    ano_sel = st.session_state.get("ano_referencia_global")
    if not ano_sel: return
    with get_connection() as conn:
        conn.execute("INSERT OR REPLACE INTO respostas (id, ano, valor, pontos, link) VALUES (?, ?, ?, ?, ?)",
                    (qid, ano_sel, str(valor), pontos, str(link)))
        conn.commit()

def bloco_comentarios(qid, res_data):
    ano_atual = st.session_state.get("ano_referencia_global", "Geral")
    coment_key = f"COM_{qid}"
    form_id = f"form_coment_{qid}_{ano_atual}"
    with st.expander(f"💬 Notas Internas e Evidências - {qid}"):
        d_existente = res_data.get(coment_key, {"link": ""})
        if d_existente.get("link"):
            st.info(f"**Nota registrada:** {d_existente['link']}")
        with st.form(key=form_id, clear_on_submit=True):
            novo_comento = st.text_area("Adicionar comentário:", key=f"input_{form_id}")
            if st.form_submit_button("Salvar Nota"):
                if novo_comento:
                    save_resp(coment_key, "Comentário Interno", 0, novo_comento)
                    st.rerun()

# --- NOVAS FUNÇÕES DE ANÁLISE ---

def get_all_years_data():
    all_data = {}
    with get_connection() as conn:
        cursor = conn.execute("SELECT id, ano, valor, pontos, link FROM respostas ORDER BY ano DESC")
        for row in cursor.fetchall():
            qid, ano, valor, pontos, link = row
            if ano not in all_data:
                all_data[ano] = {}
            all_data[ano][qid] = {"valor": valor, "pontos": pontos, "link": link}
    return all_data

def analyze_performance(res_data):
    pontos_fortes = []
    
    # Dicionários para agrupar por relevância
    criticos_zero = {"Alta": [], "Média": [], "Baixa": []}
    criticos_negativos = {"Alta": [], "Média": [], "Baixa": []}

    # Dicionário com a pontuação máxima e mínima possível para cada quesito
    # Isso permite calcular o "impacto" real de uma pontuação zero ou negativa
    pontuacoes_referencia = {
        "1.0": {"max": 40, "min": 0}, "1.3": {"max": 5, "min": 0}, "1.4": {"max": 50, "min": 0},
        "2.0": {"max": 20, "min": 0}, "2.1": {"max": 30, "min": 0}, "2.2": {"max": 10, "min": 0},
        "3.0": {"max": 10, "min": 0}, "3.1": {"max": 10, "min": 0}, "4.2": {"max": 10, "min": 0},
        "5.0": {"max": 30, "min": 0}, "5.1.1": {"max": 20, "min": 0}, "5.2": {"max": 10, "min": 0},
        "6.0": {"max": 30, "min": 0}, "7.0": {"max": 30, "min": 0}, "7.1": {"max": 10, "min": 0},
        "7.2": {"max": 80, "min": 0}, "7.3": {"max": 10, "min": 0}, "7.4": {"max": 10, "min": 0},
        "7.5": {"max": 10, "min": 0}, "7.6": {"max": 10, "min": 0}, "8.0": {"max": 30, "min": 0},
        "8.1.1.1": {"max": 20, "min": 0}, "8.2": {"max": 10, "min": 0}, "9.0": {"max": 30, "min": 0},
        "10.0": {"max": 0, "min": -100}, "11.1": {"max": 20, "min": 0}, "11.1.1": {"max": 10, "min": 0},
        "11.2": {"max": 10, "min": 0}, "12.1": {"max": 20, "min": 0}, "12.1.3": {"max": 10, "min": 0},
        "14.0": {"max": 30, "min": 0}, "15.0": {"max": 30, "min": 0}, "16.0": {"max": 30, "min": 0},
        "C1.1": {"max": 0, "min": -30}
    }

    def classificar_relevancia(impacto):
        abs_impacto = abs(impacto)
        if abs_impacto >= 16:
            return "Alta"
        elif 6 <= abs_impacto <= 15:
            return "Média"
        else:
            return "Baixa"

    for qid, info in res_data.items():
        if qid.startswith("COM_"): # Ignora comentários
            continue
        
        pontos_atuais = info.get("pontos", 0)
        
        # Se o quesito não está na lista de pontuáveis, ele é informativo e deve ser ignorado
        if qid not in pontuacoes_referencia:
            continue

        ref = pontuacoes_referencia[qid]
        max_pontos = ref["max"]
        min_pontos = ref["min"]

        if pontos_atuais == max_pontos:
            # Se a pontuação atual é a máxima possível, é um ponto forte
            pontos_fortes.append((qid, pontos_atuais, info.get("valor", ""), info.get("link", "")))
        else:
            # Calcula o impacto: quanto deixou de ganhar (ou quanto perdeu além do mínimo)
            impacto = max_pontos - pontos_atuais
            relevancia = classificar_relevancia(impacto)

            if pontos_atuais == 0 and max_pontos > 0:
                # Quesitos que poderiam ter pontos positivos, mas tiraram zero
                criticos_zero[relevancia].append((qid, pontos_atuais, info.get("valor", ""), info.get("link", ""), impacto))
            elif pontos_atuais < 0:
                # Quesitos com pontuação negativa
                criticos_negativos[relevancia].append((qid, pontos_atuais, info.get("valor", ""), info.get("link", ""), impacto))
            elif pontos_atuais > 0 and pontos_atuais < max_pontos:
                # Quesitos com pontuação positiva, mas não máxima (considerar como crítico zero para fins de relatório)
                criticos_zero[relevancia].append((qid, pontos_atuais, info.get("valor", ""), info.get("link", ""), impacto))
    
    # Ordenar pontos fortes por pontuação decrescente
    pontos_fortes.sort(key=lambda x: x[1], reverse=True)
    
    # Ordenar as listas internas por impacto (decrescente de impacto)
    for rel in ["Alta", "Média", "Baixa"]:
        criticos_zero[rel].sort(key=lambda x: x[4], reverse=True)
        criticos_negativos[rel].sort(key=lambda x: x[4], reverse=True) # Impacto negativo: maior impacto (mais negativo) primeiro

    return pontos_fortes, criticos_zero, criticos_negativos

def analyze_recurrence(ano_atual, res_data_atual):
    reincidencias = []
    all_data = get_all_years_data()

    # Lista de QIDs que são pontuáveis, fornecida pelo usuário
    qids_pontuaveis = [
        "1.0", "1.3", "1.4", "2.0", "2.1", "2.2", "3.0", "3.1", "4.2",
        "5.0", "5.1.1", "5.2", "6.0", "7.0", "7.1", "7.2", "7.3", "7.4",
        "7.5", "7.6", "8.0", "8.1.1.1", "8.2", "9.0", "10.0", "11.1",
        "11.1.1", "11.2", "12.1", "12.1.3", "14.0", "15.0", "16.0", "C1.1"
    ]

    anos_anteriores = sorted([a for a in all_data.keys() if a < ano_atual], reverse=True)

    for qid_atual, info_atual in res_data_atual.items():
        if qid_atual.startswith("COM_") or qid_atual not in qids_pontuaveis:
            continue
        
        pontos_atual = info_atual.get("pontos", 0)
        
        # Só consideramos reincidência se a pontuação atual for zero ou negativa
        if pontos_atual <= 0:
            for ano_anterior in anos_anteriores:
                if qid_atual in all_data[ano_anterior]:
                    pontos_anterior = all_data[ano_anterior][qid_atual].get("pontos", 0)
                    # Se a pontuação anterior também era zero ou negativa, é uma reincidência
                    if pontos_anterior <= 0:
                        reincidencias.append((qid_atual, ano_anterior, pontos_anterior, pontos_atual))
                        break # Encontrou uma reincidência, não precisa verificar anos mais antigos para este qid
    return reincidencias

# --- 2. LÓGICA DO RELATÓRIO PDF ---

def gerar_relatorio_pdf(dados, ano, total, faixa):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()

    # Título principal
    elements.append(Paragraph(f"RELATÓRIO DE AUDITORIA i-CIDADE - {ano}", styles["Title"]))
    elements.append(Paragraph(f"<b>Pontuação Total:</b> {total} pts | <b>Faixa:</b> {faixa}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    # --- Análise de Desempenho ---
    pontos_fortes, criticos_zero, criticos_negativos = analyze_performance(dados)

    elements.append(Paragraph("<b>ANÁLISE DE DESEMPENHO</b>", styles["h2"]))
    elements.append(Spacer(1, 6))

    # Pontos Fortes
    if pontos_fortes:
        elements.append(Paragraph("<b>✅ Pontos Fortes (Quesitos com maior pontuação):</b>", styles["h3"]))
        data_fortes = [["Quesito", "Pontos", "Resposta / Evidência"]]
        for qid, pontos, valor, link in pontos_fortes:
            evidencia = f"<b>{valor}</b><br/>{link}"
            data_fortes.append([qid, str(pontos), Paragraph(evidencia, styles["Normal"])])
        tabela_fortes = Table(data_fortes, colWidths=[65, 40, 385])
        tabela_fortes.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#28a745")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#28a745")),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        elements.append(tabela_fortes)
        elements.append(Spacer(1, 12))

    # Pontos Críticos (Zero) por Relevância
    elements.append(Paragraph("<b>❌ Pontos Críticos (Quesitos com pontuação zero):</b>", styles["h3"]))
    for relevancia in ["Alta", "Média", "Baixa"]:
        if criticos_zero[relevancia]:
            elements.append(Paragraph(f"**Relevância {relevancia}:**", styles["h4"]))
            data_criticos_zero = [["Quesito", "Pontos", "Resposta / Evidência"]]
            for qid, pontos, valor, link, _ in criticos_zero[relevancia]:
                evidencia = f"<b>{valor}</b><br/>{link}"
                data_criticos_zero.append([qid, str(pontos), Paragraph(evidencia, styles["Normal"])])
            
            cor_fundo = colors.HexColor("#dc3545") # Vermelho padrão para zero
            if relevancia == "Alta": cor_fundo = colors.HexColor("#8b0000") # Vermelho escuro
            elif relevancia == "Média": cor_fundo = colors.HexColor("#ff4500") # Laranja avermelhado
            elif relevancia == "Baixa": cor_fundo = colors.HexColor("#ff6347") # Tomate

            tabela_criticos_zero = Table(data_criticos_zero, colWidths=[65, 40, 385])
            tabela_criticos_zero.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), cor_fundo),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.5, cor_fundo),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            elements.append(tabela_criticos_zero)
            elements.append(Spacer(1, 12))

    # Pontos Críticos (Negativos) por Relevância
    elements.append(Paragraph("<b>🚨 Pontos Críticos (Quesitos com pontuação negativa):</b>", styles["h3"]))
    for relevancia in ["Alta", "Média", "Baixa"]:
        if criticos_negativos[relevancia]:
            elements.append(Paragraph(f"**Relevância {relevancia}:**", styles["h4"]))
            data_criticos_negativos = [["Quesito", "Pontos", "Resposta / Evidência"]]
            for qid, pontos, valor, link, _ in criticos_negativos[relevancia]:
                evidencia = f"<b>{valor}</b><br/>{link}"
                data_criticos_negativos.append([qid, str(pontos), Paragraph(evidencia, styles["Normal"])])
            
            cor_fundo = colors.HexColor("#ff0000") # Vermelho padrão para negativo
            if relevancia == "Alta": cor_fundo = colors.HexColor("#800000") # Vinho
            elif relevancia == "Média": cor_fundo = colors.HexColor("#b22222") # Firebrick
            elif relevancia == "Baixa": cor_fundo = colors.HexColor("#cd5c5c") # IndianRed

            tabela_criticos_negativos = Table(data_criticos_negativos, colWidths=[65, 40, 385])
            tabela_criticos_negativos.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), cor_fundo),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("GRID", (0, 0), (-1, -1), 0.5, cor_fundo),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]))
            elements.append(tabela_criticos_negativos)
            elements.append(Spacer(1, 12))

    # --- Análise de Reincidência ---
    reincidencias = analyze_recurrence(ano, dados)
    if reincidencias:
        elements.append(Paragraph("<b>⚠️ Reincidências (Quesitos com pontuação zero/negativa em anos anteriores):</b>", styles["h2"]))
        elements.append(Spacer(1, 6))
        data_reincidencia = [["Quesito", "Ano Anterior", "Pontos Anteriores", "Pontos Atuais"]]
        for qid, ano_ant, pts_ant, pts_atual in reincidencias:
            data_reincidencia.append([qid, str(ano_ant), str(pts_ant), str(pts_atual)])
        tabela_reincidencia = Table(data_reincidencia, colWidths=[100, 100, 100, 100])
        tabela_reincidencia.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ffc107")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#ffc107")),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        elements.append(tabela_reincidencia)
        elements.append(Spacer(1, 12))

    # --- Tabela de Respostas Detalhadas (Existente) ---
    elements.append(Paragraph("<b>RESPOSTAS DETALHADAS POR QUESITO</b>", styles["h2"]))
    elements.append(Spacer(1, 6))
    data_table = [["Quesito", "Resultado / Evidência", "Pts"]]
    for qid in sorted(dados.keys()):
        if qid.startswith("COM_"): continue
        info = dados[qid]
        evidencia = f"<b>{info.get("valor", "")}</b><br/>{info.get("link", "")}"
        data_table.append([qid, Paragraph(evidencia, styles["Normal"]), str(info.get("pontos", 0))])
    tabela = Table(data_table, colWidths=[65, 385, 40])
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(tabela)
    doc.build(elements)
    buffer.seek(0)
    return buffer

# --- 3. SIDEBAR (CORRIGIDA) ---

def render_sidebar():
    st.sidebar.title("🛠️ Painel de Controle")
    anos = [2024, 2025, 2026, 2027, 2028, 2029, 2030]
    ano_sel = st.sidebar.selectbox("Ano de Referência:", anos, key="ano_referencia_global")
    
    res_data = load_respostas(ano_sel)
    total_pts = sum(item.get("pontos", 0) for item in res_data.values())

    # Lógica de Classificação
    if total_pts <= 500: faixa, cor = "C", "red"
    elif total_pts <= 599: faixa, cor = "C+", "orange"
    elif total_pts <= 749: faixa, cor = "B", "#d4d400"
    elif total_pts <= 899: faixa, cor = "B+", "lightgreen"
    else: faixa, cor = "A", "green"

    st.sidebar.metric("Pontuação Total", f"{total_pts} pts")
    st.sidebar.markdown(f"**Faixa:** <span style='color:{cor}; font-size:20px; font-weight:bold;'>{faixa}</span>", unsafe_allow_html=True)

    if st.sidebar.button("📄 Gerar Relatório PDF"):
        pdf = gerar_relatorio_pdf(res_data, ano_sel, total_pts, faixa)
        st.sidebar.download_button("⬇️ Baixar PDF", pdf, f"Relatorio_{ano_sel}.pdf", "application/pdf")
    
    return total_pts, res_data, ano_sel

# --- 4. FORMULÁRIO PRINCIPAL ---

def mostrar_formulario_cidade():
    total_pts, res_data, ano_sel = render_sidebar()
    st.title(f"🏙️ Painel de Auditoria - {ano_sel}")

    st.markdown("""<style>.quesito-card {background-color:#f8f9fa; padding:20px; border-left:6px solid #2c3e50; border-radius:8px; margin-bottom:20px; border:1px solid #ddd;}</style>""", unsafe_allow_html=True)

    # Definição segura e antecipada de r10 baseada no banco para evitar NameError nas condicionais
    r10 = res_data.get("1.0", {}).get("valor", "")

    # --- QUESITO 1.0 ---
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("QUESITO 1.0")
    st.write("**Foi criada a COMPDEC ou órgão similar?**")
    d10 = res_data.get("1.0", {"valor": "", "link": "", "pontos": 0})
    opc10 = ["Sim (40 pts)", "Não (00 pts)"]
    idx10 = opc10.index(d10["valor"]) if d10["valor"] in opc10 else 0
    
    col1, col2 = st.columns([1, 2])
    with col1:
        r10_input = st.radio("Selecione:", opc10, index=idx10, key=f"radio_q10_{ano_sel}")
    with col2:
        l10 = st.text_area("Link/Evidência:", value=d10.get("link", ""), key=f"link_q10_{ano_sel}", height=100)

    if r10_input and (r10_input != d10["valor"] or l10 != d10["link"]):
        save_resp("1.0", r10_input, (40 if "Sim" in r10_input else 0), l10)
        st.rerun()
    bloco_comentarios("1.0", res_data)
    st.markdown("</div>", unsafe_allow_html=True)

    # Atualiza a variável com a escolha atual da tela antes das condicionais seguintes
    r10 = r10_input

    # --- QUESITO 1.1 e 1.2 (Condicional) ---
    if r10 and "Sim" in r10:
        for qid, txt in [("1.1", "Instrumento normativo, Número e Data:"), ("1.2", "Link eletrônico ou texto de evidência:")]:
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader(f"QUESITO {qid}")
            dq = res_data.get(qid, {"valor": "", "link": ""})
            v_q = st.text_input(txt, value=dq["valor"], key=f"v{qid}_{ano_sel}")
            if v_q != dq["valor"]:
                save_resp(qid, v_q, 0, "")
                st.rerun()
            bloco_comentarios(qid, res_data)
            st.markdown('</div>', unsafe_allow_html=True)

        # QUESITO 1.3
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 1.3")
        st.write("**A COMPDEC está subordinada a qual secretaria?**")
        d13 = res_data.get("1.3", {"valor": "", "pontos": 0})
        opts13 = {"Gabinete do Prefeito (05 pts)": 5, "Segurança Pública (00 pts)": 0, "Controladoria (00 pts)": 0, "Outra (00 pts)": 0}
        lista13 = list(opts13.keys())
        idx13 = lista13.index(d13["valor"]) if d13["valor"] in lista13 else 0
        r13 = st.radio("Selecione:", lista13, index=idx13, key=f"q13_{ano_sel}")
        if r13 != d13["valor"]:
            save_resp("1.3", r13, opts13[r13], "")
            st.rerun()
        bloco_comentarios("1.3", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 1.5 (Condicional se Não) ---
    elif r10 and "Não" in r10:
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 1.5")
        st.write("**Motivo da COMPDEC não ter sido instituída:**")
        d15 = res_data.get("1.5", {"valor": ""})
        opts15 = ["Instrumento normativo em elaboração", "Falta de estrutura", "Outros"]
        idx15 = opts15.index(d15["valor"]) if d15["valor"] in opts15 else 0
        r15 = st.radio("Motivo:", opts15, index=idx15, key=f"q15_{ano_sel}")
        if r15 != d15["valor"]:
            save_resp("1.5", r15, 0, "")
            st.rerun()
        bloco_comentarios("1.5", res_data)
        st.markdown("</div>", unsafe_allow_html=True)

    # ----------------------------
    # QUESITO 1.4
    # ----------------------------
    if r10 and "Sim" in r10: # Garantido que só aparece se o 1.0 for Sim
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 1.4")
        st.write("**Os órgãos municipais atuam de forma sistêmica, articulados com a COMPDEC nas ações de prevenção e resposta?**")

        d14 = res_data.get("1.4", {"valor": None, "link": "", "pontos": 0})

        opts14 = {
            "Sim, inclusive com a participação de entidades privadas e da comunidade (50 pts)": 50,
            "Sim, com participação de entidades privadas (20 pts)": 20,
            "Sim, com participação da comunidade (20 pts)": 20,
            "Sim, apenas com representantes da administração municipal (10 pts)": 10,
            "Não atuam de forma sistêmica (00 pts)": 0
        }

        lista_opts14 = list(opts14.keys())

        # Localiza o índice da resposta salva para não perder a seleção ao recarregar
        idx14 = lista_opts14.index(d14["valor"]) if d14["valor"] in lista_opts14 else 0

        r14 = st.radio("Nível de atuação:", lista_opts14, index=idx14, key=f"q14_{ano_sel}")

        # Lógica de salvamento automático ao mudar o rádio
        if r14 != d14["valor"]:
            save_resp("1.4", r14, opts14[r14], "")
            st.rerun()

        bloco_comentarios("1.4", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 2.0 ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 2.0")
    st.write("**Sobre treinamento e capacitação sobre Proteção e Defesa Civil, a Prefeitura capacita seus agentes para ações municipais de Defesa Civil?**")

    d20 = res_data.get("2.0", {"valor": None, "link": ""})
    opcoes_20 = ["Sim (20 pts)", "Não (00 pts)"]
    idx20 = opcoes_20.index(d20["valor"]) if d20["valor"] in opcoes_20 else None

    r20 = st.radio("Resposta 2.0:", opcoes_20, index=idx20, key=f"q20_{ano_sel}")
    l20 = st.text_area("Justificativa e Evidência (2.0):", value=d20["link"], key=f"l20_{ano_sel}")

    if r20 is not None:
        if r20 != d20["valor"] or l20 != d20["link"]:
            save_resp("2.0", r20, 20 if "Sim" in r20 else 0, l20)
            st.rerun()

    bloco_comentarios("2.0", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 2.1 (Cálculo de Data) ---
    # A variável r20 vem do bloco anterior
    if r20 and "Sim" in r20:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 2.1")
        st.write("**Qual a data da última capacitação dos agentes municipais para ações de Defesa Civil?**")

        st.info("""
        **Regra de Pontuação:**
        * ✅ **Data a partir de 01/01/2024:** 30 pontos.
        * ⚠️ **Data até 31/12/2023:** 00 pontos.
        * 🚫 **Capacitações em 2026:** Não pontuam (00 pontos).
        """)

        # 1. Busca os dados
        d21 = res_data.get("2.1", {"valor": None, "pontos": 0, "link": ""})

        col_d21, col_j21 = st.columns([1, 2])

        with col_d21:
            try:
                dt_i = datetime.strptime(d21["valor"], '%Y-%m-%d').date() if d21["valor"] else date.today()
            except:
                dt_i = date.today()

            data_sel = st.date_input(
                "Selecione a data:",
                value=dt_i,
                key=f"dt21_{ano_sel}",
                format="DD/MM/YYYY"
            )

            # Cálculo automático da pontuação
            pts21 = 30 if data_sel > date(2023, 12, 31) and data_sel.year != 2026 else 0

            data_formatada = data_sel.strftime('%d/%m/%Y')
            if pts21 == 30:
                st.success(f"Pontuação: 30 pts ({data_formatada})")
            else:
                st.warning(f"Pontuação: 00 pts ({data_formatada})")

        with col_j21:
            l21 = st.text_area(
                "Justificativa e Evidência (2.1):",
                value=d21["link"],
                key=f"l21_{ano_sel}",
                placeholder="Cole o link do certificado ou portaria aqui..."
            )

        # 4. SALVAMENTO
        valor_para_salvar = str(data_sel)

        # Salva se houver alteração ou se o usuário estiver preenchendo pela primeira vez
        # Garante que a data seja salva mesmo que o link esteja vazio inicialmente
        if valor_para_salvar != d21["valor"] or l21 != d21["link"]:
            save_resp("2.1", valor_para_salvar, pts21, l21)
            st.rerun()

        bloco_comentarios("2.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 2.2 (Múltipla Escolha) ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 2.2")
    st.write("**A Prefeitura Municipal ofereceu cursos/treinamento sobre Proteção e Defesa Civil para qual público?**")

    d22 = res_data.get("2.2", {"valor": "[]", "pontos": 0, "link": ""})
    valor_salvo_22 = d22["valor"]

    # Checkboxes
    c1 = st.checkbox("Para escolas – 05 pts", value="Escolas" in valor_salvo_22, key=f"c22a_{ano_sel}")
    c2 = st.checkbox("Para outras secretarias / entidades municipais – 03 pts", value="Secretarias" in valor_salvo_22, key=f"c22b_{ano_sel}")
    c3 = st.checkbox("Para munícipes ou empresas – 02 pts", value="Munícipes" in valor_salvo_22, key=f"c22c_{ano_sel}")
    c4 = st.checkbox("Não ofereceu nenhum curso/treinamento no ano – 00 pts", value="Nenhum" in valor_salvo_22, key=f"c22d_{ano_sel}")

    # Lógica de pontuação
    p22 = 0; sel22 = []
    if c4:
        sel22 = ["Nenhum"]
        p22 = 0
    else:
        if c1: p22 += 5; sel22.append("Escolas")
        if c2: p22 += 3; sel22.append("Secretarias")
        if c3: p22 += 2; sel22.append("Munícipes")

    l22 = st.text_area("Evidência 2.2:", value=d22["link"], key=f"l22_{ano_sel}")

    # Salvamento
    if str(sel22) != d22["valor"] or l22 != d22["link"]:
        if sel22 or l22 != "" or d22["valor"] != "[]":
            save_resp("2.2", str(sel22), p22, l22)
            st.rerun()

    st.info(f"Pontuação Acumulada 2.2: {p22} pts")
    bloco_comentarios("2.2", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 3.0 ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 3.0")
    st.write("**O Município realiza ações para estimular a participação de entidades privadas, associações de voluntários, etc?**")

    d30 = res_data.get("3.0", {"valor": None, "pontos": 0, "link": ""})
    opces_30 = ["Sim – 10 pts", "Não – 00 pts"]
    idx30 = opces_30.index(d30["valor"]) if d30["valor"] in opces_30 else None

    r30 = st.radio("Escolha 3.0:", opces_30, index=idx30, key=f"q30_{ano_sel}")
    l30 = st.text_area("Evidência 3.0:", value=d30["link"], key=f"l30_{ano_sel}")

    if r30 is not None:
        if r30 != d30["valor"] or l30 != d30["link"]:
            pts30 = 10 if "Sim" in r30 else 0
            save_resp("3.0", r30, pts30, l30)
            st.rerun()

    bloco_comentarios("3.0", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 3.1 - AÇÕES REALIZADAS (Múltipla Escolha) ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 3.1")
    st.write("**Assinale quais ações foram realizadas:**")

    d31 = res_data.get("3.1", {"valor": "[]", "pontos": 0, "link": ""})

    col_c31, col_j31 = st.columns([1, 2])
    with col_c31:
        opcoes_31 = [
            "Workshop / Palestra",
            "Reunião",
            "Conferência",
            "Congresso",
            "Discussão na Câmara Municipal",
            "Treinamentos",
            "Outros"
        ]

        selecionados_31 = []
        for opcao in opcoes_31:
            # Key única por opção e por ano
            if st.checkbox(opcao,
                           value=opcao in d31["valor"],
                           key=f"check_31_{opcao}_{ano_sel}"):
                selecionados_31.append(opcao)

        pts31 = 0

    with col_j31:
        l31 = st.text_area("Evidências das ações (3.1):",
                           value=d31["link"],
                           key=f"l31_{ano_sel}")

    if str(selecionados_31) != d31["valor"] or l31 != d31["link"]:
        if selecionados_31 or l31 != "" or d31["valor"] != "[]":
            save_resp("3.1", str(selecionados_31), pts31, l31)
            st.rerun()

    bloco_comentarios("3.1", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 3.1.1 - DATA DE TREINAMENTO ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 3.1.1")
    st.write("**Qual a data do último treinamento de associações de voluntários?**")

    st.info("""
    **Fórmula de Cálculo:**
    * 📅 **Até 31/12/2023:** 00 pontos.
    * 📅 **A partir de 01/01/2024:** 10 pontos.
    * 🚫 **Observação:** Treinamentos em 2026 não pontuam.
    """)

    d311 = res_data.get("3.1.1", {"valor": None, "pontos": 0, "link": ""})

    col_d311, col_j311 = st.columns([1, 2])
    with col_d311:
        try:
            dt_i_311 = datetime.strptime(d311["valor"], '%Y-%m-%d').date() if d311["valor"] else date.today()
        except:
            dt_i_311 = date.today()

        data_sel_311 = st.date_input(
            "Data do treinamento:",
            value=dt_i_311,
            key=f"dt311_{ano_sel}",
            format="DD/MM/YYYY"
        )

        pts311 = 10 if data_sel_311 > date(2023, 12, 31) and data_sel_311.year != 2026 else 0

        data_br_311 = data_sel_311.strftime('%d/%m/%Y')
        if pts311 == 10:
            st.success(f"Pontuação: 10 pts ({data_br_311})")
        else:
            st.warning(f"Pontuação: 00 pts ({data_br_311})")

    with col_j311:
        l311 = st.text_area("Justificativa (3.1.1):", value=d311["link"], key=f"l311_{ano_sel}")

    if d311["valor"] is not None or l311 != "":
        if str(data_sel_311) != d311["valor"] or l311 != d311["link"]:
            save_resp("3.1.1", str(data_sel_311), pts311, l311)
            st.rerun()

    bloco_comentarios("3.1.1", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 4.0 ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 4.0")
    st.write("**O Município recebeu a Carta Geotécnica de Suscetibilidade, Aptidão à Urbanização e Risco?**")

    d40 = res_data.get("4.0", {"valor": None, "pontos": 0, "link": ""})
    col_r40, col_j40 = st.columns([1, 2])
    opcoes_40 = ["Sim", "Não"]

    with col_r40:
        idx40 = opcoes_40.index(d40["valor"]) if d40["valor"] in opcoes_40 else None
        r40 = st.radio("Resposta 4.0:", opcoes_40, index=idx40, key=f"q40_r_{ano_sel}")
        pts40 = 10 if r40 == "Sim" else 0

    with col_j40:
        l40 = st.text_area("Evidência (4.0):", value=d40["link"], key=f"l40_{ano_sel}")

    if r40 is not None:
        if r40 != d40["valor"] or l40 != d40["link"]:
            save_resp("4.0", r40, pts40, l40)
            st.rerun()

    bloco_comentarios("4.0", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 4.1 ---
    if r40 == "Sim":
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 4.1")
        st.write("**Assinale quais os tipos de ameaças potenciais identificadas na Carta Geotécnica:**")

        d41 = res_data.get("4.1", {"valor": "[]", "pontos": 0, "link": ""})
        col_c41, col_j41 = st.columns([1, 2])

        with col_c41:
            ameacas_cobrade = ["Riscos Geológicos", "Riscos Hidrológicos", "Riscos Meteorológicos",
                               "Riscos Climatológicos", "Riscos Biológicos", "Riscos Tecnológicos"]
            selecionados_41 = []
            for ameaca in ameacas_cobrade:
                if st.checkbox(ameaca, value=ameaca in d41["valor"], key=f"chk_41_{ameaca}_{ano_sel}"):
                    selecionados_41.append(ameaca)
            pts41 = 0

        with col_j41:
            l41 = st.text_area("Justificativa (4.1):", value=d41["link"], key=f"l41_{ano_sel}")

        if str(selecionados_41) != d41["valor"] or l41 != d41["link"]:
            save_resp("4.1", str(selecionados_41), pts41, l41)
            st.rerun()

        bloco_comentarios("4.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 4.2 (PONTUAÇÃO NEGATIVA) ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 4.2")
    st.write("**A Carta Geotécnica consta no Plano Diretor?**")

    d42 = res_data.get("4.2", {"valor": None, "pontos": -50, "link": ""})
    opts42 = {
        "Sim (00 pts)": 0,
        "Não (-50 pts)": -50,
        "Não se aplica o Plano Diretor (00 pts)": 0
    }
    lista_opcoes = list(opts42.keys())
    idx42 = lista_opcoes.index(d42["valor"]) if d42["valor"] in lista_opcoes else None

    r42 = st.radio("Situação:", lista_opcoes, index=idx42, key=f"q42_{ano_sel}")
    l42 = st.text_area("Evidência (4.2):", value=d42["link"], key=f"l42_{ano_sel}")

    if r42 is not None:
        if r42 != d42["valor"] or l42 != d42["link"]:
            save_resp("4.2", r42, int(opts42[r42]), l42)
            st.rerun()

    bloco_comentarios("4.2", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 5.0 ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 5.0")
    st.write("**O Município realizou, por conta própria, o mapeamento e identificação das principais ameaças existentes em seu território?**")

    d50 = res_data.get("5.0", {"valor": None, "pontos": 0, "link": ""})
    col_r50, col_j50 = st.columns([1, 2])
    opcoes_50 = ["Sim (200 pts)", "Não (00 pts)"]

    with col_r50:
        idx50 = opcoes_50.index(d50["valor"]) if d50["valor"] in opcoes_50 else None
        r50 = st.radio("Resposta 5.0:", opcoes_50, index=idx50, key=f"q50_{ano_sel}")
        pts50 = 200 if r50 and "Sim" in r50 else 0

    with col_j50:
        l50 = st.text_area("Justificativa Técnica (5.0):", value=d50["link"], key=f"l50_{ano_sel}")

    if r50 is not None:
        if r50 != d50["valor"] or l50 != d50["link"]:
            save_resp("5.0", r50, pts50, l50)
            st.rerun()

    bloco_comentarios("5.0", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 5.1 (Condicional) ---
    if r50 and "Sim" in r50:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 5.1")
        st.write("**Assinale as principais ameaças identificadas:**")

        d51 = res_data.get("5.1", {"valor": "[]", "pontos": 0, "link": ""})
        col_c51, col_j51 = st.columns([1, 2])

        with col_c51:
            ameacas_51 = ["Epidemias", "Estiagem", "Incêndios (urbanos e florestais)",
                          "Ondas de calor ou ondas de frio", "Inundações", "Infestações e Pragas",
                          "Ameaças radioativas", "Deslizamentos", "Outros"]

            selecionados_51 = []
            for ameaca in ameacas_51:
                # Sanitização simples para a key do checkbox
                ameaca_id = ameaca.replace(" ", "_").lower()
                if st.checkbox(ameaca, value=ameaca in d51["valor"], key=f"chk51_{ameaca_id}_{ano_sel}"):
                    selecionados_51.append(ameaca)

        with col_j51:
            l51 = st.text_area("Descrição / Evidências (5.1):", value=d51["link"],
                               key=f"l51_{ano_sel}", placeholder="Se marcou 'Outros', especifique aqui...")

        if str(selecionados_51) != d51["valor"] or l51 != d51["link"]:
            if selecionados_51 or l51 != "" or d51["valor"] != "[]":
                save_resp("5.1", str(selecionados_51), 0, l51)
                st.rerun()

        bloco_comentarios("5.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 5.1.1 (PONTUAÇÃO NEGATIVA) ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 5.1.1")
    st.write("**As secretarias setoriais realizaram a fiscalização das áreas de risco?**")

    d511 = res_data.get("5.1.1", {"valor": None, "pontos": -100, "link": ""})
    opts511 = {
        "Sim, integralmente (00 pts)": 0,
        "Sim, parcialmente (00 pts)": 0,
        "Não houve fiscalização (-100 pts)": -100
    }
    lista_opcoes_511 = list(opts511.keys())
    idx511 = lista_opcoes_511.index(d511["valor"]) if d511["valor"] in lista_opcoes_511 else None

    r511 = st.radio("Status da Fiscalização:", lista_opcoes_511, index=idx511, key=f"q511_{ano_sel}")
    l511 = st.text_area("Evidência (5.1.1):", value=d511["link"], key=f"l511_{ano_sel}")

    if r511 is not None:
        if r511 != d511["valor"] or l511 != d511["link"]:
            save_resp("5.1.1", r511, opts511[r511], l511)
            st.rerun()

    bloco_comentarios("5.1.1", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 5.1.2 ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 5.1.2")
    st.write("**O município possui áreas de risco com possibilidade de ocupação/invasão?**")

    d512 = res_data.get("5.1.2", {"valor": "Não", "pontos": 0, "link": ""})
    col_r512, col_j512 = st.columns([1, 2])

    with col_r512:
        r512 = st.radio("Possui áreas com risco de invasão?", ["Sim", "Não"],
                        index=0 if d512["valor"] == "Sim" else 1, key=f"q512_{ano_sel}")

    with col_j512:
        l512 = st.text_area("Justificativa (5.1.2):", value=d512["link"], key=f"l512_{ano_sel}", height=100)

    if r512 != d512["valor"] or l512 != d512["link"]:
        save_resp("5.1.2", r512, 0, l512)
        st.rerun()

    bloco_comentarios("5.1.2", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 5.1.2.1 (Condicional) ---
    if r512 == "Sim":
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 5.1.2.1")
        st.write("**Assinale os mechanisms para vedar novas ocupações nas áreas de riscos:**")

        d5121 = res_data.get("5.1.2.1", {"valor": "[]", "pontos": 0, "link": ""})
        col_c5121, col_j5121 = st.columns([1, 2])

        with col_c5121:
            mecanismos = ["Aplicação de sanções monetárias (multas)", "Monitoramento (fiscalização)",
                          "Notificação dos infratores", "Interdição do local e remoção das famílias",
                          "Demolição das ocupações", "Outros"]

            selecionados_5121 = []
            for mec in mecanismos:
                # Sanitização segura para a chave identificadora do componente do Streamlit
                mec_id = mec.replace(" ", "_").replace("(", "").replace(")", "").lower()
                if st.checkbox(mec, value=mec in d5121["valor"], key=f"chk5121_{mec_id}_{ano_sel}"):
                    selecionados_5121.append(mec)

        with col_j5121:
            l5121 = st.text_area("Evidências dos Mecanismos (5.1.2.1):", value=d5121["link"],
                                 key=f"l5121_{ano_sel}", height=150)

        if str(selecionados_5121) != d5121["valor"] or l5121 != d5121["link"]:
            if selecionados_5121 or l5121 != "" or d5121["valor"] != "[]":
                save_resp("5.1.2.1", str(selecionados_5121), 0, l5121)
                st.rerun()

        bloco_comentarios("5.1.2.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 5.2 (RESET POR ANO E PONTUAÇÃO NEGATIVA) ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 5.2")
    st.write("**A população foi informada sobre todas as ameaças identificadas pelo município?**")

    d52 = res_data.get("5.2", {"valor": None, "pontos": -50, "link": ""})
    opts52 = {
        "Sim (00 pts)": 0,
        "Parcialmente (00 pts)": 0,
        "Não (-50 pts)": -50
    }
    lista_opcoes_52 = list(opts52.keys())
    idx52 = lista_opcoes_52.index(d52["valor"]) if d52["valor"] in lista_opcoes_52 else None

    r52 = st.radio(
        "Informação à população:",
        lista_opcoes_52,
        index=idx52,
        key=f"q52_{ano_sel}"
    )

    l52 = st.text_area(
        "Meios de comunicação utilizados / Evidência (5.2):",
        value=d52["link"],
        key=f"l52_{ano_sel}"
    )

    if r52 is not None:
        if r52 != d52["valor"] or l52 != d52["link"]:
            save_resp("5.2", r52, int(opts52[r52]), l52)
            st.rerun()

    bloco_comentarios("5.2", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 6.0 (VISTORIAS E PONTUAÇÃO NEGATIVA) ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 6.0")
    st.write("**A Secretaria realizou vistorias em edificações vulneráveis para identificar a necessidade de intervenção preventiva?**")

    d60 = res_data.get("6.0", {"valor": None, "pontos": -50, "link": ""})
    opts60 = {
        "Sim, de acordo com um cronograma preestabelecido (00 pts)": 0,
        "Sim, de acordo com a demanda (00 pts)": 0,
        "Não foram vistoriadas (-50 pts)": -50,
        "Não houve casos de edificações vulneráveis (00 pts)": 0
    }
    lista_opcoes_60 = list(opts60.keys())
    idx60 = lista_opcoes_60.index(d60["valor"]) if d60["valor"] in lista_opcoes_60 else None

    r60 = st.radio(
        "Status das Vistorias:",
        lista_opcoes_60,
        index=idx60,
        key=f"q60_radio_{ano_sel}"
    )

    l60 = st.text_area(
        "Relatórios de Vistoria / Evidências (6.0):",
        value=d60["link"],
        key=f"l60_text_{ano_sel}"
    )

    if r60 is not None:
        if r60 != d60["valor"] or l60 != d60["link"]:
            save_resp("6.0", r60, int(opts60[r60]), l60)
            st.rerun()

    bloco_comentarios("6.0", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 7.0 (PLANCON) ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 7.0")
    st.write("**O Município possui Plano de Contingência Municipal – PLANCON de Defesa Civil?**")

    d70 = res_data.get("7.0", {"valor": None, "pontos": 0, "link": ""})
    col_r70, col_j70 = st.columns([1, 2])
    opcoes_70 = ["Sim (50 pts)", "Não (00 pts)"]

    with col_r70:
        idx70 = opcoes_70.index(d70["valor"]) if d70["valor"] in opcoes_70 else None
        r70 = st.radio(
            "Possui PLANCON?",
            opcoes_70,
            index=idx70,
            key=f"q70_radio_{ano_sel}"
        )
        pts70 = 50 if r70 and "Sim" in r70 else 0

    with col_j70:
        l70 = st.text_area(
            "Link do PLANCON / Decreto (7.0):",
            value=d70["link"],
            key=f"l70_text_{ano_sel}"
        )

    if r70 is not None:
        if r70 != d70["valor"] or l70 != d70["link"]:
            save_resp("7.0", r70, pts70, l70)
            st.rerun()

    bloco_comentarios("7.0", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 7.1 (Dependente do 7.0) ---
    if r70 and "Sim" in r70:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 7.1")
        st.write("**Foi elaborado um PLANCON específico para cada ameaça identificada?**")

        d71 = res_data.get("7.1", {"valor": None, "pontos": 0, "link": ""})
        opts71 = {
            "Sim, cada ameaça mapeada possui um PLANCON diferente (05 pts)": 5,
            "Sim, parte das ameaças possuem PLANCON diferentes (03 pts)": 3,
            "Existe apenas um PLANCON que abrange todas as ameaças (00 pts)": 0
        }
        lista_opcoes_71 = list(opts71.keys())
        idx71 = lista_opcoes_71.index(d71["valor"]) if d71["valor"] in lista_opcoes_71 else None

        r71 = st.radio(
            "Abrangência do PLANCON:",
            lista_opcoes_71,
            index=idx71,
            key=f"q71_radio_{ano_sel}"
        )

        l71 = st.text_area(
            "Evidências/Links dos planos específicos (7.1):",
            value=d71["link"],
            key=f"l71_text_{ano_sel}"
        )

        if r71 is not None:
            if r71 != d71["valor"] or l71 != d71["link"]:
                save_resp("7.1", r71, int(opts71[r71]), l71)
                st.rerun()

        bloco_comentarios("7.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 7.2 (SIMULADOS) ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 7.2")
    st.write("**São realizados regularmente exercícios simulados para as contingências previstas no PLANCON?**")

    d72 = res_data.get("7.2", {"valor": None, "pontos": 0, "link": ""})
    col_r72, col_j72 = st.columns([1, 2])
    opcoes_72 = ["Sim (80 pts)", "Não (00 pts)"]

    with col_r72:
        idx72 = opcoes_72.index(d72["valor"]) if d72["valor"] in opcoes_72 else None
        r72 = st.radio(
            "Realiza simulados?",
            opcoes_72,
            index=idx72,
            key=f"q72_radio_{ano_sel}"
        )
        pts72 = 80 if r72 and "Sim" in r72 else 0

    with col_j72:
        l72 = st.text_area(
            "Cronograma/Relatório dos Simulados (7.2):",
            value=d72["link"],
            key=f"l72_text_{ano_sel}"
        )

    if r72 is not None:
        if r72 != d72["valor"] or l72 != d72["link"]:
            save_resp("7.2", r72, pts72, l72)
            st.rerun()

    bloco_comentarios("7.2", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 7.3 (SISTEMA DE ALERTA) ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 7.3")
    st.write("**O Município possui sistema de alerta para desastres?**")
    st.caption("Objetivo: avisar a população vulnerável antes de ocorrer o evento.")

    d73 = res_data.get("7.3", {"valor": None, "pontos": 0, "link": ""})
    col_r73, col_j73 = st.columns([1, 2])
    opcoes_73 = ["Sim (50 pts)", "Não (00 pts)"]

    with col_r73:
        idx73 = opcoes_73.index(d73["valor"]) if d73["valor"] in opcoes_73 else None
        r73 = st.radio(
            "Possui sistema de alerta?",
            opcoes_73,
            index=idx73,
            key=f"q73_radio_{ano_sel}"
        )
        pts73 = 50 if r73 and "Sim" in r73 else 0

    with col_j73:
        l73 = st.text_area(
            "Descrição do sistema (SMS, Sirenes, etc) (7.3):",
            value=d73["link"],
            key=f"l73_text_{ano_sel}"
        )

    if r73 is not None:
        if r73 != d73["valor"] or l73 != d73["link"]:
            save_resp("7.3", r73, pts73, l73)
            st.rerun()

    bloco_comentarios("7.3", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 7.3.1 (Condicional do 7.3) ---
    if r73 and "Sim" in r73:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 7.3.1")
        st.write("**Assinale os tipos de sistemas de alerta utilizados pelo Município:**")

        d731 = res_data.get("7.3.1", {"valor": "[]", "pontos": 0, "link": ""})
        col_c731, col_j731 = st.columns([1, 2])

        with col_c731:
            tipos_alerta = [
                "Alerta via SMS",
                "Anúncio por rádio/Televisão",
                "Placas de identificação de área de risco",
                "Aviso por telefone / Aplicativo de mensagens",
                "Aviso por email",
                "Aviso aos membros do Nupdec",
                "Outro"
            ]

            sel_731 = []
            for t in tipos_alerta:
                # Sanitização robusta da key para evitar quebras de renderização no Streamlit
                t_key = t.replace("/", "_").replace(" ", "_").replace("-", "_").lower()
                if st.checkbox(
                    t,
                    value=t in d731["valor"],
                    key=f"chk731_{t_key}_{ano_sel}"
                ):
                    sel_731.append(t)

        with col_j731:
            l731 = st.text_area(
                "Justificativa / Detalhes (7.3.1):",
                value=d731["link"],
                key=f"l731_text_{ano_sel}"
            )

        if str(sel_731) != d731["valor"] or l731 != d731["link"]:
            if sel_731 or l731 != "" or d731["valor"] != "[]":
                save_resp("7.3.1", str(sel_731), 0, l731)
                st.rerun()

        bloco_comentarios("7.3.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 7.4 (SISTEMA DE ALARME) ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 7.4")
    st.write("**O Município dispõe de sinal, dispositivo ou sistema de alarme para desastres?**")
    st.caption("Objetivo: avisar a população sobre o evento que ESTÁ OCORRENDO.")

    d74 = res_data.get("7.4", {"valor": None, "pontos": 0, "link": ""})
    col_r74, col_j74 = st.columns([1, 2])
    opcoes_74 = ["Sim (50 pts)", "Não (00 pts)"]

    with col_r74:
        idx74 = opcoes_74.index(d74["valor"]) if d74["valor"] in opcoes_74 else None
        r74 = st.radio(
            "Possui sistema de alarme?",
            opcoes_74,
            index=idx74,
            key=f"q74_radio_{ano_sel}"
        )
        pts74 = 50 if r74 and "Sim" in r74 else 0

    with col_j74:
        l74 = st.text_area(
            "Evidência do sistema de alarme (7.4):",
            value=d74["link"],
            key=f"l74_text_{ano_sel}"
        )

    if r74 is not None:
        if r74 != d74["valor"] or l74 != d74["link"]:
            save_resp("7.4", r74, pts74, l74)
            st.rerun()

    bloco_comentarios("7.4", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 7.4.1 (Condicional do 7.4) ---
    if r74 and "Sim" in r74:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 7.4.1")
        st.write("**Assinale os tipos de sinal, dispositivo ou sistema de alarme utilizado:**")

        d741 = res_data.get("7.4.1", {"valor": "[]", "pontos": 0, "link": ""})
        col_c741, col_j741 = st.columns([1, 2])

        with col_c741:
            tipos_alarme = [
                "Sinal sonoro (sirene)",
                "Sinal luminoso",
                "Carros de emergência com sirenes",
                "Carros de emergência com alto-falantes",
                "Aviso aos membros do Nupdec",
                "Aviso por telefone / Aplicativo de mensagens",
                "Uso da imprensa (TV, rádio, internet)",
                "Outro"
            ]

            sel_741 = []
            for ta in tipos_alarme:
                # Geramos um ID limpo e seguro para a key do Streamlit
                ta_id = ta.replace('(', '').replace(')', '').replace('/', '_').replace(' ', '_').replace(',', '_').lower()
                if st.checkbox(
                    ta,
                    value=ta in d741["valor"],
                    key=f"chk741_{ta_id}_{ano_sel}"
                ):
                    sel_741.append(ta)

        with col_j741:
            l741 = st.text_area(
                "Justificativa / Detalhes (7.4.1):",
                value=d741["link"],
                key=f"l741_text_{ano_sel}"
            )

        if str(sel_741) != d741["valor"] or l741 != d741["link"]:
            if sel_741 or l741 != "" or d741["valor"] != "[]":
                save_resp("7.4.1", str(sel_741), 0, l741)
                st.rerun()

        bloco_comentarios("7.4.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 7.5 (CADASTRO DE ABRIGOS) ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 7.5")
    st.write("**Possui cadastro dos locais para abrigo à população em situação de desastre junto à CEPDEC?**")

    d75 = res_data.get("7.5", {"valor": None, "pontos": 0, "link": ""})
    opts75 = {
        "Sim, atualizado (10 pts)": 10,
        "Sim, mas não está atualizado (03 pts)": 3,
        "Não (00 pts)": 0
    }
    lista_opcoes_75 = list(opts75.keys())
    idx75 = lista_opcoes_75.index(d75["valor"]) if d75["valor"] in lista_opcoes_75 else None

    r75 = st.radio(
        "Cadastro de Abrigos (CEPDEC):",
        lista_opcoes_75,
        index=idx75,
        key=f"q75_radio_{ano_sel}"
    )

    l75 = st.text_area(
        "Evidência do Cadastro/Protocolo (7.5):",
        value=d75["link"],
        key=f"l75_text_{ano_sel}"
    )

    if r75 is not None:
        if r75 != d75["valor"] or l75 != d75["link"]:
            save_resp("7.5", r75, int(opts75[r75]), l75)
            st.rerun()

    bloco_comentarios("7.5", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 7.6 (FORNECEDORES DE AJUDA) ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 7.6")
    st.write("**O Município possui cadastro da lista de fornecedores para suprimentos de ajuda humanitária?**")

    d76 = res_data.get("7.6", {"valor": None, "pontos": 0, "link": ""})
    opts76 = {
        "Sim, atualizado (10 pts)": 10,
        "Sim, mas não está atualizado (03 pts)": 3,
        "Não (00 pts)": 0
    }
    lista_opcoes_76 = list(opts76.keys())
    idx76 = lista_opcoes_76.index(d76["valor"]) if d76["valor"] in lista_opcoes_76 else None

    r76 = st.radio(
        "Lista de Fornecedores:",
        lista_opcoes_76,
        index=idx76,
        key=f"q76_radio_{ano_sel}"
    )

    l76 = st.text_area(
        "Evidência da lista/cadastro (7.6):",
        value=d76["link"],
        key=f"l76_text_{ano_sel}"
    )

    if r76 is not None:
        if r76 != d76["valor"] or l76 != d76["link"]:
            save_resp("7.6", r76, int(opts76[r76]), l76)
            st.rerun()

    bloco_comentarios("7.6", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 7.7 (DATA PLANCON) ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 7.7")
    st.write("**Qual a data da última atualização do PLANCON?**")
    st.caption("Se não houve atualização, informar a data do início da vigência.")

    d77 = res_data.get("7.7", {"valor": "", "pontos": 0, "link": ""})

    data_77 = st.text_input(
        "Data de Atualização/Vigência (DD/MM/AAAA):",
        value=d77["valor"],
        key=f"q77_date_{ano_sel}",
        placeholder="Ex: 15/05/2024"
    )

    if data_77 != d77["valor"]:
        if data_77 != "" or d77["valor"] != "":
            save_resp("7.7", data_77, 0, "")
            st.rerun()

    bloco_comentarios("7.7", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 8.0 (CANAL DE EMERGÊNCIA) ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 8.0")
    st.write("**O Município possui um canal de atendimento de emergência à população para registro de ocorrências de desastres?**")

    d80 = res_data.get("8.0", {"valor": None, "pontos": 0, "link": ""})
    col_r80, col_j80 = st.columns([1, 2])
    opcoes_80 = ["Sim (50 pts)", "Não (00 pts)"]

    with col_r80:
        idx80 = opcoes_80.index(d80["valor"]) if d80["valor"] in opcoes_80 else None
        r80 = st.radio(
            "Possui canal de emergência?",
            opcoes_80,
            index=idx80,
            key=f"q80_radio_{ano_sel}"
        )
        pts80 = 50 if r80 and "Sim" in r80 else 0

    with col_j80:
        l80 = st.text_area(
            "Descrição/Evidência do Canal (8.0):",
            value=d80["link"],
            key=f"l80_text_{ano_sel}",
            placeholder="Ex: Telefone 199, WhatsApp oficial, Site de chamados..."
        )

    if r80 is not None:
        if r80 != d80["valor"] or l80 != d80["link"]:
            save_resp("8.0", r80, pts80, l80)
            st.rerun()

    bloco_comentarios("8.0", res_data)

    # --- QUESITO 8.1 e 8.1.1 (Condicionais) ---
    if r80 and "Sim" in r80:
        st.markdown('<div style="margin-left: 20px; border-left: 2px solid #eee; padding-left: 20px; margin-bottom: 20px;">', unsafe_allow_html=True)

        # --- 8.1 ---
        st.subheader("QUESITO 8.1")
        st.write("**Assinale os canais que o município possui:**")

        d81 = res_data.get("8.1", {"valor": "[]", "pontos": 0, "link": ""})
        col_c81, col_j81 = st.columns([1, 2])

        with col_c81:
            canais = [
                "Telefone de emergências", "Aplicativo de mensagens",
                "Correio eletrônico (e-mail)", "Aplicativo da Prefeitura",
                "Site da Prefeitura", "Redes sociais", "Outros"
            ]
            sel_81 = []
            for c in canais:
                c_key = c.replace(" ", "_").replace("(", "").replace(")", "").replace("-", "_").lower()
                if st.checkbox(c, value=c in d81["valor"], key=f"chk81_{c_key}_{ano_sel}"):
                    sel_81.append(c)

        with col_j81:
            l81 = st.text_area("Links/Números dos canais (8.1):", value=d81["link"], key=f"l81_text_{ano_sel}")

        if str(sel_81) != d81["valor"] or l81 != d81["link"]:
            if sel_81 or l81 != "" or d81["valor"] != "[]":
                save_resp("8.1", str(sel_81), 0, l81)
                st.rerun()

        bloco_comentarios("8.1", res_data)

        # --- 8.1.1 ---
        st.subheader("QUESITO 8.1.1")
        st.write("**Sobre o número de telefone de emergência, utiliza o número 199 da Defesa Civil?**")

        d811 = res_data.get("8.1.1", {"valor": None, "pontos": 0, "link": ""})
        opcoes_811 = ["Sim", "Não"]
        idx811 = opcoes_811.index(d811["valor"]) if d811["valor"] in opcoes_811 else None

        r811 = st.radio("Utiliza o 199?", opcoes_811, index=idx811, key=f"q811_radio_{ano_sel}")

        if r811 is not None and r811 != d811["valor"]:
            save_resp("8.1.1", r811, 0, "")
            st.rerun()

        bloco_comentarios("8.1.1", res_data)

        # --- QUESITO 8.1.1.1 (Condicional do 8.1.1) ---
        if r811 == "Sim":
            st.markdown('<div style="margin-left: 30px; border-left: 2px solid #ccc; padding-left: 15px; margin-bottom: 15px;">', unsafe_allow_html=True)
            st.subheader("QUESITO 8.1.1.1")
            st.write("**O telefone 199 tem atendimento 24 horas por dia?**")

            d8111 = res_data.get("8.1.1.1", {"valor": None, "pontos": 0, "link": ""})
            opcoes_8111 = ["Sim (20 pts)", "Não (00 pts)"]
            idx8111 = opcoes_8111.index(d8111["valor"]) if d8111["valor"] in opcoes_8111 else None

            r8111 = st.radio("Atendimento 24h?", opcoes_8111, index=idx8111, key=f"q8111_radio_{ano_sel}")
            pts8111 = 20 if r8111 and "Sim" in r8111 else 0

            if r8111 is not None and r8111 != d8111["valor"]:
                save_resp("8.1.1.1", r8111, pts8111, "")
                st.rerun()

            bloco_comentarios("8.1.1.1", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True) # Fecha recuo do div condicional do 8.0

    st.markdown('</div>', unsafe_allow_html=True) # Fecha o card principal do QUESITO 8.0

    # --- QUESITO 8.2 (REGISTRO ELETRÔNICO) ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 8.2")
    st.write("**O Município registra as ocorrências de Defesa Civil de forma eletrônica?**")

    d82 = res_data.get("8.2", {"valor": None, "pontos": 0, "link": ""})
    col_r82, col_j82 = st.columns([1, 2])
    opcoes_82 = ["Sim (50 pts)", "Não (00 pts)"]

    with col_r82:
        idx82 = opcoes_82.index(d82["valor"]) if d82["valor"] in opcoes_82 else None
        r82 = st.radio("Registro eletrônico?", opcoes_82, index=idx82, key=f"q82_radio_{ano_sel}")
        pts82 = 50 if r82 and "Sim" in r82 else 0

    with col_j82:
        l82 = st.text_area("Evidência do Sistema (8.2):", value=d82["link"], key=f"l82_text_{ano_sel}")

    if r82 is not None:
        if r82 != d82["valor"] or l82 != d82["link"]:
            save_resp("8.2", r82, pts82, l82)
            st.rerun()

    bloco_comentarios("8.2", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 9.0 (ESCOLAS E SAÚDE) ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 9.0")
    st.write("**Avaliação da estrutura de escolas e unidades de saúde para casos de desastre?**")

    d90 = res_data.get("9.0", {"valor": None, "pontos": 0, "link": ""})
    opts90 = {
        "Sim, em todas as escolas e centros de saúde (100 pts)": 100,
        "Sim, na maior parte das escolas e centros de saúde (50 pts)": 50,
        "Sim, na menor parte das escolas e centros de saúde (20 pts)": 20,
        "Não (00 pts)": 0
    }
    lista_opcoes_90 = list(opts90.keys())
    idx90 = lista_opcoes_90.index(d90["valor"]) if d90["valor"] in lista_opcoes_90 else None

    r90 = st.radio("Abrangência:", lista_opcoes_90, index=idx90, key=f"q90_radio_{ano_sel}")

    l90 = st.text_area("Link do Estudo / Relatório (9.0):", value=d90["link"], key=f"l90_text_{ano_sel}")

    if r90 is not None:
        if r90 != d90["valor"] or l90 != d90["link"]:
            save_resp("9.0", r90, int(opts90[r90]), l90)
            st.rerun()

    bloco_comentarios("9.0", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 10.0 (PLANO DE MOBILIDADE) ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 10.0")
    st.write("**O Município elaborou seu Plano de Mobilidade Urbana?**")

    # Inicia com None para não negativar pontos automaticamente no reset de ano
    d100 = res_data.get("10.0", {"valor": None, "pontos": 0, "link": ""})

    opts100 = {
        "Sim (00 pts)": 0,
        "Não (-100 pts)": -100,
        "Não se aplica (00 pts)": 0
    }
    lista_opcoes_100 = list(opts100.keys())
    idx100 = lista_opcoes_100.index(d100["valor"]) if d100["valor"] in lista_opcoes_100 else None

    r100 = st.radio(
        "Status Plano de Mobilidade:",
        lista_opcoes_100,
        index=idx100,
        key=f"q100_radio_{ano_sel}"
    )

    l100 = st.text_area(
        "Evidência (10.0):",
        value=d100["link"],
        key=f"l100_text_{ano_sel}"
    )

    if r100 is not None:
        if r100 != d100["valor"] or l100 != d100["link"]:
            save_resp("10.0", r100, int(opts100[r100]), l100)
            st.rerun()

    bloco_comentarios("10.0", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 11.0 (TRANSPORTE COLETIVO) ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 11.0")
    st.write("**No Município existe transporte público coletivo?**")

    d110 = res_data.get("11.0", {"valor": None, "pontos": 0, "link": ""})
    col_r110, col_j110 = st.columns([1, 2])
    opcoes_110 = ["Sim", "Não"]

    with col_r110:
        idx110 = opcoes_110.index(d110["valor"]) if d110["valor"] in opcoes_110 else None
        r110 = st.radio("Transporte Coletivo:", opcoes_110, index=idx110, key=f"q110_radio_{ano_sel}")

    with col_j110:
        l110 = st.text_area("Justificativa / Detalhes (11.0):", value=d110["link"], key=f"l110_text_{ano_sel}")

    if r110 is not None:
        if r110 != d110["valor"] or l110 != d110["link"]:
            save_resp("11.0", r110, 0, l110)
            st.rerun()

    bloco_comentarios("11.0", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 11.1 (METAS DE QUALIDADE) ---
    if r110 == "Sim":
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 11.1")
        st.write("**Foram estabelecidas metas de qualidade e desempenho para o transporte público coletivo municipal?**")

        d111 = res_data.get("11.1", {"valor": None, "pontos": 0, "link": ""})
        opts111 = {"Sim (00 pts)": 0, "Não (-20 pts)": -20}
        lista_opcoes_111 = list(opts111.keys())
        idx111 = lista_opcoes_111.index(d111["valor"]) if d111["valor"] in lista_opcoes_111 else None

        col_r111, col_j111 = st.columns([1, 2])
        with col_r111:
            r111 = st.radio("Metas estabelecidas:", lista_opcoes_111, index=idx111, key=f"q111_radio_{ano_sel}")

        with col_j111:
            l111 = st.text_area("Evidência (11.1):", value=d111["link"], key=f"l111_text_{ano_sel}")

        if r111 is not None:
            if r111 != d111["valor"] or l111 != d111["link"]:
                save_resp("11.1", r111, int(opts111[r111]), l111)
                st.rerun()

        # --- 11.1.1 (ATENDIMENTO DAS METAS) ---
        if r111 and "Sim" in r111:
            st.divider()
            st.subheader("QUESITO 11.1.1")
            st.write("**As metas de qualidade e desempenho estão sendo atingidas?**")

            d1111 = res_data.get("11.1.1", {"valor": None, "pontos": 0, "link": ""})
            opts1111 = {
                "Todas as metas foram atingidas (00 pts)": 0,
                "A maior parte das metas foram atingidas (-05 pts)": -5,
                "A menor parte das metas foram atingidas (-10 pts)": -10,
                "As metas não foram atingidas (-20 pts)": -20
            }
            lista_opcoes_1111 = list(opts1111.keys())
            idx1111 = lista_opcoes_1111.index(d1111["valor"]) if d1111["valor"] in lista_opcoes_1111 else None

            col_r1111, col_j1111 = st.columns([1, 2])
            with col_r1111:
                r1111 = st.radio("Cumprimento das metas:", lista_opcoes_1111, index=idx1111, key=f"q1111_radio_{ano_sel}")

            with col_j1111:
                l1111 = st.text_area("Relatório de Desempenho (11.1.1):", value=d1111["link"], key=f"l1111_text_{ano_sel}")

            if r1111 is not None:
                if r1111 != d1111["valor"] or l1111 != d1111["link"]:
                    save_resp("11.1.1", r1111, int(opts1111[r1111]), l1111)
                    st.rerun()

            bloco_comentarios("11.1.1", res_data)

            # --- 11.1.1.1 (PENALIDADE) ---
            if r1111 and "Todas" not in r1111:
                st.divider()
                st.subheader("QUESITO 11.1.1.1")
                st.write("**Foi aplicada penalidade pela meta não cumprida?**")

                d11111 = res_data.get("11.1.1.1", {"valor": None, "pontos": 0, "link": ""})
                opcoes_11111 = ["Sim (00 pts)", "Não (-50 pts)"]
                idx11111 = opcoes_11111.index(d11111["valor"]) if d11111["valor"] in opcoes_11111 else None

                r11111 = st.radio("Aplicação de penalidade:", opcoes_11111, index=idx11111, key=f"q11111_radio_{ano_sel}")
                pts11111 = -50 if r11111 and "Não" in r11111 else 0

                l11111 = st.text_area("Auto de Infração (11.1.1.1):", value=d11111["link"], key=f"l11111_text_{ano_sel}")

                if r11111 is not None:
                    if r11111 != d11111["valor"] or l11111 != d11111["link"]:
                        save_resp("11.1.1.1", r11111, pts11111, l11111)
                        st.rerun()

                bloco_comentarios("11.1.1.1", res_data)

        # Bloco de comentários pai (11.1) e fechamento do card externo
        bloco_comentarios("11.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 11.2 (PESQUISA DE SATISFAÇÃO) ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 11.2")
    st.write(f"**Foi realizada pesquisa de satisfação dos usuários em {ano_sel}?**")

    d112 = res_data.get("11.2", {"valor": None, "pontos": 0, "link": ""})
    col_r112, col_j112 = st.columns([1, 2])
    opcoes_112 = ["Sim (00 pts)", "Não (-20 pts)"]

    with col_r112:
        idx112 = opcoes_112.index(d112["valor"]) if d112["valor"] in opcoes_112 else None
        r112 = st.radio("Realizou pesquisa?", opcoes_112, index=idx112, key=f"q112_radio_{ano_sel}")
        pts112 = -20 if r112 and "Não" in r112 else 0

    with col_j112:
        l112 = st.text_area(f"Resultado da Pesquisa {ano_sel} (11.2):", value=d112["link"], key=f"l112_text_{ano_sel}")

    if r112 is not None:
        if r112 != d112["valor"] or l112 != d112["link"]:
            save_resp("11.2", r112, pts112, l112)
            st.rerun()

    bloco_comentarios("11.2", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 11.2.1 (AÇÕES PÓS-PESQUISA) ---
    if r112 and "Sim" in r112:
        st.markdown('<div style="margin-left: 20px; border-left: 2px solid #eee; padding-left: 20px; margin-bottom: 20px;">', unsafe_allow_html=True)
        st.subheader("QUESITO 11.2.1")
        st.write("**Foram realizadas ações com base nesta pesquisa?**")

        d1121 = res_data.get("11.2.1", {"valor": None, "pontos": 0, "link": ""})
        opcoes_1121 = ["Sim (00 pts)", "Não (-20 pts)"]
        idx1121 = opcoes_1121.index(d1121["valor"]) if d1121["valor"] in opcoes_1121 else None

        col_r1121, col_j1121 = st.columns([1, 2])
        with col_r1121:
            r1121 = st.radio("Ações realizadas?", opcoes_1121, index=idx1121, key=f"q1121_radio_{ano_sel}")
            pts1121 = -20 if r1121 and "Não" in r1121 else 0

        with col_j1121:
            l1121 = st.text_area("Descrição das Ações (11.2.1):", value=d1121["link"], key=f"l1121_text_{ano_sel}")

        if r1121 is not None:
            if r1121 != d1121["valor"] or l1121 != d1121["link"]:
                save_resp("11.2.1", r1121, pts1121, l1121)
                st.rerun()

        bloco_comentarios("11.2.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 11.3 (RESULTADO FINANCEIRO) ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 11.3")
    st.write(f"**Resultado financeiro/tarifário no ano de {ano_sel}:**")

    d113 = res_data.get("11.3", {"valor": None, "pontos": 0, "link": ""})
    opcoes_113 = ["Déficit ou subsídio tarifário", "Superávit tarifário", "Não sabe informar"]

    col_r113, col_j113 = st.columns([1, 2])
    with col_r113:
        idx113 = opcoes_113.index(d113["valor"]) if d113["valor"] in opcoes_113 else None
        r113 = st.radio("Resultado:", opcoes_113, index=idx113, key=f"q113_radio_{ano_sel}")

    with col_j113:
        l113 = st.text_area("Justificativa Financeira (11.3):", value=d113["link"], key=f"l113_text_extra_{ano_sel}")

    if r113 is not None:
        if r113 != d113["valor"] or l113 != d113["link"]:
            save_resp("11.3", r113, 0, l113)
            st.rerun()

    # --- 11.3.1 (TRANSPARÊNCIA TARIFÁRIA) ---
    st.divider()
    st.subheader("QUESITO 11.3.1")
    st.write("**Link de divulgação dos benefícios tarifários concedidos:**")

    d1131 = res_data.get("11.3.1", {"valor": "", "pontos": 0, "link": ""})
    l1131 = st.text_input("Link (Transparência):", value=d1131["link"], key=f"l1131_text_{ano_sel}")

    if l1131 != d1131["link"]:
        if l1131 != "" or d1131["link"] != "":
            save_resp("11.3.1", "Link fornecido", 0, l1131)
            st.rerun()

    bloco_comentarios("11.3.1", res_data)
    bloco_comentarios("11.3", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 12.0 (TRANSPORTE POR APP) ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 12.0")
    st.write("**O Município possui transporte remunerado privado individual (App)?**")

    d120 = res_data.get("12.0", {"valor": None, "pontos": 0, "link": ""})
    col_r120, col_j120 = st.columns([1, 2])
    opcoes_120 = ["Sim", "Não"]

    with col_r120:
        idx120 = opcoes_120.index(d120["valor"]) if d120["valor"] in opcoes_120 else None
        r120 = st.radio("Possui transporte por App?", opcoes_120, index=idx120, key=f"q120_radio_{ano_sel}")

    with col_j120:
        l120 = st.text_area("Empresas atuantes (12.0):", value=d120["link"], key=f"l120_text_{ano_sel}")

    if r120 is not None:
        if r120 != d120["valor"] or l120 != d120["link"]:
            save_resp("12.0", r120, 0, l120)
            st.rerun()

    bloco_comentarios("12.0", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 12.1 (REGULAMENTAÇÃO APP) ---
    # Inicialização de segurança unificada a partir do cache
    d121_cache = res_data.get("12.1", {"valor": None})
    r121 = d121_cache["valor"]

    if r120 and "Sim" in str(r120):
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 12.1")
        st.write("**O Município regulamentou o transporte remunerado privado individual?**")

        d121 = res_data.get("12.1", {"valor": None, "pontos": 0, "link": ""})
        opts121 = {"Sim (00 pts)": 0, "Não (-50 pts)": -50}
        lista_opcoes_121 = list(opts121.keys())

        idx121 = lista_opcoes_121.index(d121["valor"]) if d121["valor"] in lista_opcoes_121 else None

        col_r121, col_j121 = st.columns([1, 2])
        with col_r121:
            r121 = st.radio("Regulamentado?", lista_opcoes_121, index=idx121, key=f"q121_radio_{ano_sel}")

        with col_j121:
            l121 = st.text_area("Evidência (Lei/Decreto) (12.1):", value=d121["link"], key=f"l121_text_{ano_sel}")

        if r121 is not None:
            if r121 != d121["valor"] or l121 != d121["link"]:
                pts_121 = int(opts121.get(r121, 0))
                save_resp("12.1", r121, pts_121, l121)
                st.rerun()

        bloco_comentarios("12.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

      # --- QUESITOS 12.1.1 a 12.1.3 (DETALHES DA REGULAMENTAÇÃO) ---
    if r121 and "Sim" in r121:
        st.markdown('<div style="margin-left: 20px; border-left: 2px solid #eee; padding-left: 20px; margin-bottom: 20px;">', unsafe_allow_html=True)
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("QUESITO 12.1.1")
            st.write("Instrumento normativo, Número e Data:")
            d1211 = res_data.get("12.1.1", {"valor": "", "pontos": 0, "link": ""})
            v1211 = st.text_input(
                f"Ex: Lei 123 de 01/01/{ano_sel}",
                value=d1211["valor"],
                key=f"q1211_val_{ano_sel}"
            )
            if v1211 != d1211["valor"]:
                if v1211 != "" or d1211["valor"] != "":
                    save_resp("12.1.1", v1211, 0, "")
                    st.rerun()
            bloco_comentarios("12.1.1", res_data)

        with col2:
            st.subheader("QUESITO 12.1.2")
            st.write("Link da norma:")
            d1212 = res_data.get("12.1.2", {"valor": "", "pontos": 0, "link": ""})
            v1212 = st.text_input(
                "URL da norma:",
                value=d1212["link"],
                key=f"q1212_link_{ano_sel}"
            )
            if v1212 != d1212["link"]:
                if v1212 != "" or d1212["link"] != "":
                    save_resp("12.1.2", "Link fornecido", 0, v1212)
                    st.rerun()
            bloco_comentarios("12.1.2", res_data)

        st.divider()

        # --- 12.1.3 (FISCALIZAÇÃO APP) ---
        st.subheader("QUESITO 12.1.3")
        st.write("**O Município fiscaliza regularmente o transporte por aplicativo?**")

        d1213 = res_data.get("12.1.3", {"valor": None, "pontos": 0, "link": ""})
        col_r1213, col_j1213 = st.columns([1, 2])
        opcoes_1213 = ["Sim (00 pts)", "Não (-50 pts)"]

        with col_r1213:
            idx1213 = opcoes_1213.index(d1213["valor"]) if d1213["valor"] in opcoes_1213 else None
            r1213 = st.radio("Fiscaliza?", opcoes_1213, index=idx1213, key=f"q1213_radio_{ano_sel}")

        with col_j1213:
            l1213 = st.text_area("Evidência da fiscalização (12.1.3):", value=d1213["link"], key=f"l1213_text_{ano_sel}")

        if r1213 is not None:
            if r1213 != d1213["valor"] or l1213 != d1213["link"]:
                pts1213 = -50 if "Não" in r1213 else 0
                save_resp("12.1.3", r1213, pts1213, l1213)
                st.rerun()

        # --- 12.1.3.1 (PERIODICIDADE) ---
        if r1213 and "Sim" in r1213:
            st.divider()
            st.subheader("QUESITO 12.1.3.1")
            st.write("Informe a periodicidade da fiscalização:")
            d12131 = res_data.get("12.1.3.1", {"valor": None, "pontos": 0, "link": ""})
            perio = ["Diariamente", "Semanalmente", "Mensalmente", "Anualmente"]
            idx_p = perio.index(d12131["valor"]) if d12131["valor"] in perio else None

            r12131 = st.radio("Periodicidade:", perio, index=idx_p, key=f"q12131_radio_{ano_sel}")

            if r12131 is not None and r12131 != d12131["valor"]:
                save_resp("12.1.3.1", r12131, 0, "")
                st.rerun()
            bloco_comentarios("12.1.3.1", res_data)

        bloco_comentarios("12.1.3", res_data)
        st.markdown('</div>', unsafe_allow_html=True) # Fecha recuo condicional do 12.1

    # --- QUESITO 13.0 (MOBILIDADE ATIVA) ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 13.0")
    st.write(f"**Foram realizadas ações para estimular meios de transporte não motorizados em {ano_sel}?**")
    st.caption("Ex: Ciclovias, campanhas de incentivo ao uso de bicicletas ou caminhadas.")

    d130 = res_data.get("13.0", {"valor": None, "pontos": 0, "link": ""})
    col_r130, col_j130 = st.columns([1, 2])
    opcoes_130 = ["Sim", "Não"]

    with col_r130:
        idx130 = opcoes_130.index(d130["valor"]) if d130["valor"] in opcoes_130 else None
        r130 = st.radio("Realizou ações?", opcoes_130, index=idx130, key=f"q130_radio_{ano_sel}")

    with col_j130:
        l130 = st.text_area(f"Descrição/Evidências {ano_sel} (13.0):", value=d130["link"], key=f"l130_text_{ano_sel}")

    if r130 is not None:
        if r130 != d130["valor"] or l130 != d130["link"]:
            save_resp("13.0", r130, 0, l130)
            st.rerun()

    bloco_comentarios("13.0", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 13.1 (DETALHAMENTO MOBILIDADE ATIVA) ---
    if r130 == "Sim":
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 13.1")
        st.write(f"**Assinale as ações realizadas em {ano_sel}:**")

        d131 = res_data.get("13.1", {"valor": "[]", "pontos": 0, "link": ""})
        col_c131, col_j131 = st.columns([1, 2])

        with col_c131:
            acoes_131 = [
                "Instalação/manutenção de ciclovias ou ciclofaixas",
                "Instalação/manutenção de pontos de locação de bicicletas",
                "Instalação/manutenção de pontos de locação de patinetes",
                "Outras"
            ]
            sel_131 = []
            for ac in acoes_131:
                ac_key = ac.replace(" ", "_").replace("/", "_").replace("-", "_").lower()
                if st.checkbox(ac, value=ac in d131["valor"], key=f"chk131_{ac_key}_{ano_sel}"):
                    sel_131.append(ac)

        with col_j131:
            l131 = st.text_area("Detalhes/Localização (13.1):", value=d131["link"], key=f"l131_text_{ano_sel}")

        if str(sel_131) != d131["valor"] or l131 != d131["link"]:
            if sel_131 or l131 != "" or d131["valor"] != "[]":
                save_resp("13.1", str(sel_131), 0, l131)
                st.rerun()

        bloco_comentarios("13.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

       # --- RECUPERAÇÃO DE SEGURANÇA PARA VARIÁVEIS DO ESCOPO ANTERIOR ---
    d131_cache = res_data.get("13.1", {"valor": "[]"})
    if 'sel_131' not in locals():
        sel_131 = d131_cache["valor"]

    # --- QUESITO 13.1.1 (CRONOGRAMA DE CICLOVIAS) ---
    if r130 == "Sim" and "Instalação/manutenção de ciclovias ou ciclofaixas" in str(sel_131):
        st.markdown('<div style="margin-left: 20px; border-left: 2px solid #eee; padding-left: 20px; margin-bottom: 20px;">', unsafe_allow_html=True)
        st.subheader("QUESITO 13.1.1")
        st.write("**Possui um cronograma de manutenção da infraestrutura das ciclovias ou ciclofaixas?**")

        d1311 = res_data.get("13.1.1", {"valor": None, "pontos": 0, "link": ""})
        opcoes_1311 = ["Sim (00 pts)", "Não (-20 pts)"]
        idx1311 = opcoes_1311.index(d1311["valor"]) if d1311["valor"] in opcoes_1311 else None

        col_r1311, col_j1311 = st.columns([1, 2])
        with col_r1311:
            r1311 = st.radio("Possui cronograma?", opcoes_1311, index=idx1311, key=f"q1311_radio_{ano_sel}")

        with col_j1311:
            l1311 = st.text_area(f"Link/Arquivo do Cronograma ({ano_sel}) (13.1.1):", value=d1311["link"], key=f"l1311_text_{ano_sel}")

        if r1311 is not None:
            if r1311 != d1311["valor"] or l1311 != d1311["link"]:
                pts1311 = 0 if "Sim" in r1311 else -20
                save_resp("13.1.1", r1311, pts1311, l1311)
                st.rerun()

        # --- 13.1.1.1 (EXECUÇÃO DO CRONOGRAMA) ---
        if r1311 and "Sim" in r1311:
            st.divider()
            st.subheader("QUESITO 13.1.1.1")
            st.write("**As manutenções preventivas foram realizadas dentro do prazo?**")

            d13111 = res_data.get("13.1.1.1", {"valor": None, "pontos": 0, "link": ""})
            opts13111 = {
                "Sim, para todos os trechos (00 pts)": 0,
                "Sim, para a maior parte dos trechos (-05 pts)": -5,
                "Sim, para a menor parte dos trechos (-10 pts)": -10,
                "Não foram realizadas dentro do prazo (-15 pts)": -15,
                "Não foram realizadas manutenções preventivas no exercício (-20 pts)": -20
            }
            lista_opcoes_13111 = list(opts13111.keys())
            idx13111 = lista_opcoes_13111.index(d13111["valor"]) if d13111["valor"] in lista_opcoes_13111 else None

            col_r13111, col_j13111 = st.columns([1, 2])
            with col_r13111:
                r13111 = st.radio("Status da manutenção:", lista_opcoes_13111, index=idx13111, key=f"q13111_radio_{ano_sel}")

            with col_j13111:
                l13111 = st.text_area(f"Evidência da execução em {ano_sel} (13.1.1.1):", value=d13111["link"], key=f"l13111_text_{ano_sel}")

            if r13111 is not None:
                if r13111 != d13111["valor"] or l13111 != d13111["link"]:
                    save_resp("13.1.1.1", r13111, int(opts13111[r13111]), l13111)
                    st.rerun()
            bloco_comentarios("13.1.1.1", res_data)

        bloco_comentarios("13.1.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True) # Fecha o bloco de recuo condicional do 13.1.1

    # --- QUESITO 14.0 (ACESSIBILIDADE) ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 14.0")
    st.write("**O Município adequou os calçamentos públicos para acessibilidade (PcD e restrição de mobilidade)?**")

    d140 = res_data.get("14.0", {"valor": "Não possui acessibilidade em calçamentos públicos (-50 pts)", "pontos": -50, "link": ""})
    opts140 = {
        "Sim, integralmente - Todos os calçamentos públicos (00 pts)": 0,
        "Sim, parcialmente - Em parte dos calçamentos públicos (-10 pts)": -10,
        "Não possui acessibilidade em calçamentos públicos (-50 pts)": -50
    }
    lista_opcoes_140 = list(opts140.keys())
    idx140 = lista_opcoes_140.index(d140["valor"]) if d140["valor"] in lista_opcoes_140 else 2

    col_r140, col_j140 = st.columns([1, 2])
    with col_r140:
        r140 = st.radio("Status da acessibilidade:", lista_opcoes_140, index=idx140, key=f"q140_radio_{ano_sel}")
    with col_j140:
        l140 = st.text_area("Locais adequados / Fotos / Links (14.0):", value=d140["link"], key=f"l140_text_{ano_sel}")

    if r140 != d140["valor"] or l140 != d140["link"]:
        save_resp("14.0", r140, int(opts140[r140]), l140)
        st.rerun()

    bloco_comentarios("14.0", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 14.1 (RECURSOS DE ACESSIBILIDADE) ---
    if r140 and "Não possui acessibilidade" not in r140:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 14.1")
        st.write(f"**Informe os recursos de acessibilidade oferecidos pela Prefeitura em {ano_sel}:**")

        d141 = res_data.get("14.1", {"valor": "[]", "pontos": 0, "link": ""})
        col_c141, col_j141 = st.columns([1, 2])

        with col_c141:
            recursos_141 = [
                "Calçadas com dimensões mínimas para a circulação",
                "Sinalização tátil em pisos",
                "Rampas de acesso",
                "Escadas com corrimão"
            ]
            sel_141 = []
            for rec in recursos_141:
                rec_key = rec.replace(" ", "_").replace("ç", "c").replace("ã", "a").replace("í", "i").lower()[:20]
                if st.checkbox(rec, value=rec in d141["valor"], key=f"chk141_{rec_key}_{ano_sel}"):
                    sel_141.append(rec)

        with col_j141:
            l141 = st.text_area(f"Justificativa e Fotos ({ano_sel}) (14.1):", value=d141["link"], key=f"l141_text_{ano_sel}")

        if str(sel_141) != d141["valor"] or l141 != d141["link"]:
            save_resp("14.1", str(sel_141), 0, l141)
            st.rerun()

        bloco_comentarios("14.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 15.0 (SINALIZAÇÃO VIÁRIA) ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 15.0")
    st.write(f"**As vias públicas pavimentadas estão devidamente sinalizadas em {ano_sel}?**")

    d150 = res_data.get("15.0", {"valor": None, "pontos": 0, "link": ""})
    opts150 = {
        "Sim, integralmente - Todas as vias públicas municipais (50 pts)": 50,
        "Sim, parcialmente - Em parte das vias municipais (10 pts)": 10,
        "Não estão sinalizadas (00 pts)": 0
    }
    lista_opcoes_150 = list(opts150.keys())
    idx150 = lista_opcoes_150.index(d150["valor"]) if d150["valor"] in lista_opcoes_150 else None

    col_r150, col_j150 = st.columns([1, 2])
    with col_r150:
        r150 = st.radio("Status da sinalização:", lista_opcoes_150, index=idx150, key=f"q150_radio_{ano_sel}")

    with col_j150:
        l150 = st.text_area(f"Evidências da sinalização ({ano_sel}) (15.0):", value=d150["link"], key=f"l150_text_{ano_sel}")

    if r150 is not None:
        if r150 != d150["valor"] or l150 != d150["link"]:
            save_resp("15.0", r150, int(opts150[r150]), l150)
            st.rerun()

    bloco_comentarios("15.0", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 16.0 (MANUTENÇÃO DE VIAS) ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 16.0")
    st.write(f"**Há manutenção adequada das vias públicas no Município em {ano_sel}?**")
    st.caption("Referência: Manuais de Manutenção Rodoviária do DNIT.")

    d160 = res_data.get("16.0", {"valor": None, "pontos": 0, "link": ""})
    opts160 = {
        "Sim, integralmente - Todas as vias públicas municipais (50 pts)": 50,
        "Sim, parcialmente - Em parte das vias municipais (10 pts)": 10,
        "Não estão adequadas (00 pts)": 0
    }
    lista_opcoes_160 = list(opts160.keys())
    idx160 = lista_opcoes_160.index(d160["valor"]) if d160["valor"] in lista_opcoes_160 else None

    col_r160, col_j160 = st.columns([1, 2])
    with col_r160:
        r160 = st.radio("Qualidade da manutenção:", lista_opcoes_160, index=idx160, key=f"q160_radio_{ano_sel}")

    with col_j160:
        l160 = st.text_area(f"Contratos / Cronograma de Obras ({ano_sel}) (16.0):", value=d160["link"], key=f"l160_text_{ano_sel}")

    if r160 is not None:
        if r160 != d160["valor"] or l160 != d160["link"]:
            save_resp("16.0", r160, int(opts160[r160]), l160)
            st.rerun()

    bloco_comentarios("16.0", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 17.1 (ENCERRAMENTO/FEEDBACK) ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 17.1")
    st.write("**Utilize o espaço abaixo para registrar suas impressões e sugestões sobre o questionário.**")

    d171 = res_data.get("17.1", {"valor": None, "pontos": 0, "link": ""})
    opcoes_171 = ["Sim", "Não"]
    idx171 = opcoes_171.index(d171["valor"]) if d171["valor"] in opcoes_171 else None

    col_r171, col_j171 = st.columns([1, 2])
    with col_r171:
        r171 = st.radio(f"Gostaria de registrar impressões em {ano_sel}?", opcoes_171, index=idx171, key=f"q171_radio_{ano_sel}")

    with col_j171:
        l171 = st.text_area(
            "Espaço para Registro (17.1):",
            value=d171["link"],
            key=f"l171_text_{ano_sel}",
            placeholder="Sugestões ou observações sobre este exercício...",
            height=120,
            disabled=(r171 != "Sim")
        )

    if r171 is not None:
        if r171 != d171["valor"] or l171 != d171["link"]:
            save_resp("17.1", r171, 0, l171)
            st.rerun()

    bloco_comentarios("17.1", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- SEÇÃO: DADOS EXTERNOS ---
    st.markdown("## 🌐 DADOS EXTERNOS DO i-CIDADE")

    # --- QUESITO C1 (ONU MCR2030) ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO C1")
    st.write(f"**Inscrito no Programa Construindo Cidades Resilientes 2030 (ONU) em {ano_sel}?**")

    dc1 = res_data.get("C1", {"valor": None, "pontos": 0, "link": ""})
    opcoes_c1 = ["Sim", "Não"]
    idx_c1 = opcoes_c1.index(dc1["valor"]) if dc1["valor"] in opcoes_c1 else None

    col_rc1, col_jc1 = st.columns([1, 2])
    with col_rc1:
        rc1 = st.radio("Inscrito no MCR2030?", opcoes_c1, index=idx_c1, key=f"qc1_radio_{ano_sel}")

    with col_jc1:
        lc1 = st.text_area(f"Comprovante ({ano_sel}) (C1):", value=dc1["link"], key=f"lc1_text_{ano_sel}")

    if rc1 is not None:
        if rc1 != dc1["valor"] or lc1 != dc1["link"]:
            save_resp("C1", rc1, 0, lc1)
            st.rerun()

    # --- C1.1 (ESTÁGIO ONU) ---
    if rc1 == "Sim":
        st.divider()
        st.subheader("QUESITO C1.1")
        st.write(f"**Qual o estágio do Programa em {ano_sel}?**")

        dc11 = res_data.get("C1.1", {"valor": None, "pontos": 0, "link": ""})
        opts_c11 = {"Etapa A (10 pts)": 10, "Etapa B (20 pts)": 20, "Etapa C (50 pts)": 50, "Não classificada (00 pts)": 0}
        lista_opcoes_c11 = list(opts_c11.keys())
        idx_c11 = lista_opcoes_c11.index(dc11["valor"]) if dc11["valor"] in lista_opcoes_c11 else None

        col_rc11, col_jc11 = st.columns([1, 2])
        with col_rc11:
            rc11 = st.radio("Estágio atual:", lista_opcoes_c11, index=idx_c11, key=f"qc11_radio_{ano_sel}")

        with col_jc11:
            lc11 = st.text_area(f"Evidência Classificação ({ano_sel}) (C1.1):", value=dc11["link"], key=f"lc11_text_{ano_sel}")

        if rc11 is not None:
            if rc11 != dc11["valor"] or lc11 != dc11["link"]:
                save_resp("C1.1", rc11, int(opts_c11[rc11]), lc11)
                st.rerun()
        bloco_comentarios("C1.1", res_data)

    bloco_comentarios("C1", res_data)
    st.markdown('</div>', unsafe_allow_html=True) # Fecha com segurança o card do bloco C1

# --- INICIALIZAÇÃO DO SCRIPT ---
if __name__ == "__main__":
    try:
        st.set_page_config(page_title="IEGM i-Cidade", layout="wide", page_icon="🏙️")
    except Exception:
        pass

    init_db()
    mostrar_formulario_cidade()
