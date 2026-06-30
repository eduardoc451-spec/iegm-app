import re
import streamlit as st
import json
from io import BytesIO
from datetime import datetime, date

from db import conectar

# PDF (ReportLab)
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak

# Gráficos (Plotly)
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# =============================================================================
# CONSTANTES GLOBAIS
# =============================================================================
CATEGORIAS_MAP = {
    "infraestrutura": {"label": "Infraestrutura e Setor", "qids": ["1.0", "1.1", "1.2", "1.3", "1.3.1", "1.4", "1.4.1", "1.4.2"]},
    "planejamento":   {"label": "Planejamento (PDTIC)", "qids": ["2.0", "2.1", "2.2", "2.3"]},
    "seguranca":       {"label": "Segurança da Informação", "qids": ["3.0", "3.1", "3.1.1", "3.1.1.1", "3.2", "3.2.1", "3.3", "3.4", "3.5", "3.6", "3.6.1"]},
    "transparencia":   {"label": "Transparência e LAI", "qids": ["4.0", "4.1", "4.2", "6.0", "6.1", "6.2", "6.3", "6.4", "7.0", "7.1", "7.2", "7.3"]},
    "gov_digital":     {"label": "Governo Digital", "qids": ["5.0", "5.1", "5.2", "5.3", "9.0", "9.1", "9.2"]},
    "sistemas":        {"label": "Sistemas de Gestão", "qids": ["8.0", "8.1", "8.2", "8.2.1", "8.2.2", "8.3", "8.4"]},
    "lgpd":            {"label": "LGPD", "qids": ["10.0", "10.1", "10.2", "10.3", "10.4", "10.5", "10.5.1", "11.0", "11.1"]},
}

PONTUACOES_MAX = {
    "1.0": 30, "1.1": 30, "1.2": 30, "1.3": 30, "1.3.1": 30, "1.4.1": 40, "1.4.2": 20,
    "2.0": 40, "2.1": 20, "2.2": 40, "2.3": 20,
    "3.0": 50, "3.1": 20, "3.1.1": 40, "3.1.1.1": 10, "3.2.1": 10, "3.3": 30, "3.4": 30, "3.5": 30, "3.6": 20,
    "4.0": 40, "6.0": 20, "6.1": 20, "6.2": 20, "6.3": 10, "6.4": 30, "7.0": 25, "7.1": 10, "7.2": 10, "7.3": 5,
    "8.0": 40, "8.2.1": 50, "8.2.2": 30, "9.1": 120
}

FAIXA_CORES = {"C": "#ef4444", "C+": "#f97316", "B": "#eab308", "B+": "#22c55e", "A": "#16a34a"}

# =============================================================================
# MODAL DE AVISO AUTOMÁTICO (CORRIGIDO PARA LINKS CLICÁVEIS)
# =============================================================================
@st.dialog("⚠️ Atenção! Evidência em Link Externo")
def modal_aviso_link(qid, links_encontrados):
    st.warning(f"Detectamos a inclusão de link(s) no campo de evidências da questão **{qid}**.")
    
    for lk in links_encontrados:
        # CORREÇÃO: Removeu as crases e transformou em um link Markdown real e clicável
        st.markdown(f"🔗 **Endereço:** [{lk}]({lk})")
        
    st.markdown("""
    **Por favor, verifique se este link está configurado para acesso público/compartilhado.**
    
    Se as credenciais estiverem privadas ou exigirem login e senha do seu município, as equipes avaliadoras externas **não conseguirão acessar as provas**, invalidando os pontos desse quesito.
    """)
    if st.button("Confirmo que o link está liberado para o público", key=f"btn_conf_{qid}"):
        st.rerun()

# =============================================================================
# 1. FUNÇÕES DE APOIO E BANCO DE DADOS
# =============================================================================
import sqlite3
import json
import datetime
import streamlit as st

def get_connection():
    return sqlite3.connect("dados_igov_ti.db", check_same_thread=False)

def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS respostas (
                id TEXT NOT NULL,
                ano INTEGER NOT NULL,
                valor TEXT,
                pontos REAL DEFAULT 0,
                link TEXT,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id, ano)
            )
        """)
        try:
            cursor.execute("ALTER TABLE respostas ADD COLUMN comentarios TEXT")
        except sqlite3.OperationalError:
            pass
        conn.commit()

def load_respostas(ano):
    dados_ano = {}
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "SELECT id, valor, pontos, link, comentarios FROM respostas WHERE ano = ?", (ano,)
            )
            for row in cursor.fetchall():
                comentarios_lista = []
                if row[4]:
                    try:
                        comentarios_lista = json.loads(row[4])
                    except Exception:
                        comentarios_lista = []
                        
                dados_ano[row[0]] = {
                    "valor": row[1], 
                    "pontos": row[2], 
                    "link": row[3],
                    "comentarios": comentarios_lista
                }
    except Exception:
        pass
    return dados_ano

def save_resp(qid, valor, pontos, link, comentarios=None):
    ano_sel = st.session_state.get("ano_referencia_global")
    if not ano_sel:
        return
    
    comentarios_json = None
    if comentarios is not None:
        comentarios_json = json.dumps(comentarios, ensure_ascii=False)
    else:
        dados_atuais = load_respostas(ano_sel)
        if qid in dados_atuais:
            comentarios_json = json.dumps(dados_atuais[qid].get("comentarios", []), ensure_ascii=False)

    try:
        with get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO respostas (id, ano, valor, pontos, link, comentarios, atualizado_em) 
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (qid, ano_sel, str(valor), float(pontos), str(link), comentarios_json))
            conn.commit()
    except Exception as e:
        st.error(f"Erro ao salvar {qid}: {e}")

def bloco_comentarios(questao_id, res_data, sufixo=None):
    """
    Gera um bloco de diálogo direto com histórico retrátil e controle de status.
    A alteração do status grava direto no clique e independe do texto.
    Permite exclusão individual de mensagens e limpa a caixa ao enviar.
    """
    ano_sel = st.session_state.get("ano_referencia_global", datetime.date.today().year)
    usuario_atual = st.session_state.get("username", st.session_state.get("usuario", "Usuário Anônimo"))
    
    id_chave = f"{questao_id}_{sufixo}" if sufixo else questao_id
    key_texto = f"v_txt_com_{id_chave}_{ano_sel}"
    key_estado_limpar = f"limpar_input_{id_chave}_{ano_sel}"
    
    if key_estado_limpar not in st.session_state:
        st.session_state[key_estado_limpar] = False
        
    st.markdown("---")
    
    dados_questao = res_data.get(questao_id, {})
    historico = dados_questao.get("comentarios", [])
    
    status_global = "Resolvido"
    for com in historico:
        if "status_definido" in com:
            status_global = com["status_definido"]
            
    badge_status = "🔴 PENDENTE" if status_global == "Pendente" else "🟢 RESOLVIDO"
    
    with st.expander(f"💬 Diálogo Interno {id_chave} | Status: {badge_status}", expanded=(status_global == "Pendente")):
        
        st.markdown("<b style='font-size: 13px;'>Status Atual do Quesito:</b>", unsafe_allow_html=True)
        opcoes_status = ["Resolvido", "Pendente"]
        idx_status_atual = opcoes_status.index(status_global)
        
        novo_status_clicado = st.radio(
            f"Definir status para {id_chave}:",
            options=opcoes_status,
            index=idx_status_atual,
            horizontal=True,
            key=f"rad_status_{id_chave}_{ano_sel}",
            label_visibility="collapsed"
        )
        
        if novo_status_clicado != status_global:
            log_mudanca = {
                "autor": "Sistema / " + usuario_atual,
                "data": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
                "texto": f"ℹ️ Alterou o status do quesito para: **{novo_status_clicado.upper()}**.",
                "status_definido": novo_status_clicado
            }
            historico.append(log_mudanca)
            save_resp(
                qid=questao_id,
                valor=dados_questao.get("valor", ""),
                pontos=dados_questao.get("pontos", 0),
                link=dados_questao.get("link", ""),
                comentarios=historico
            )
            st.rerun()

        st.markdown("<div style='margin-bottom: 15px;'></div>", unsafe_allow_html=True)

        if historico:
            for idx, com in enumerate(historico):
                col_balao, col_lixeira = st.columns([11, 1])
                
                with col_balao:
                    if "Sistema /" in com['autor']:
                        st.markdown(
                            f"""
                            <div style="background-color: #f1f3f5; padding: 6px 12px; border-radius: 6px; margin-bottom: 4px; border-left: 3px solid #ced4da;">
                                <span style="font-size: 11px; color: #6c757d; font-style: italic;">{com['autor']} - {com['data']}</span>
                                <p style="margin: 2px 0 0 0; font-size: 12px; color: #495057; font-style: italic;">{com['texto']}</p>
                            </div>
                            """, 
                            unsafe_allow_html=True
                        )
                    else:
                        st.markdown(
                            f"""
                            <div style="background-color: #f8f9fa; padding: 10px 15px; border-radius: 8px; margin-bottom: 6px; border-left: 3px solid #1e88e5;">
                                <span style="font-size: 11px; color: #1e88e5; font-weight: bold;">{com['autor']}</span> 
                                <span style="font-size: 10px; color: #999; margin-left: 10px;">{com['data']}</span>
                                <p style="margin: 4px 0 0 0; font-size: 13px; color: #333;">{com['texto']}</p>
                            </div>
                            """, 
                            unsafe_allow_html=True
                        )
                
                with col_lixeira:
                    st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
                    if st.button("🗑️", key=f"btn_del_com_{id_chave}_{idx}_{ano_sel}", help="Excluir este comentário"):
                        historico.pop(idx)
                        save_resp(
                            qid=questao_id,
                            valor=dados_questao.get("valor", ""),
                            pontos=dados_questao.get("pontos", 0),
                            link=dados_questao.get("link", ""),
                            comentarios=historico
                        )
                        st.rerun()
                        
            st.markdown("<br>", unsafe_allow_html=True)
        else:
            st.markdown("<p style='font-size: 12px; color: #999; font-style: italic;'>Nenhum comentário enviado ainda.</p>", unsafe_allow_html=True)
            
        st.markdown("<b style='font-size: 13px;'>Adicionar Novo Comentário:</b>", unsafe_allow_html=True)
        
        if st.session_state[key_estado_limpar]:
            st.session_state[key_texto] = ""
            st.session_state[key_estado_limpar] = False
            
        novo_texto = st.text_area("Digite sua mensagem:", key=key_texto, height=80, label_visibility="collapsed")
        
        col_btn1, _ = st.columns([1, 3])
        with col_btn1:
            if st.button("Postar Comentário", key=f"btn_com_{id_chave}_{ano_sel}", type="primary"):
                if novo_texto.strip():
                    nova_mensagem = {
                        "autor": usuario_atual,
                        "data": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "texto": novo_texto.strip(),
                        "status_definido": status_global  # FIX: Chave corrigida de 'status_defined' para 'status_definido'
                    }
                    historico.append(nova_mensagem)
                    save_resp(
                        qid=questao_id, 
                        valor=dados_questao.get("valor", ""), 
                        pontos=dados_questao.get("pontos", 0), 
                        link=dados_questao.get("link", ""),
                        comentarios=historico
                    )
                    st.session_state[key_estado_limpar] = True
                    st.rerun()

def get_all_years_data():
    all_data = {}
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT id, ano, valor, pontos, link, comentarios FROM respostas ORDER BY ano DESC"
        )
        for row in cursor.fetchall():
            qid, ano, valor, pontos, link, comentarios_raw = row
            
            comentarios_lista = []
            if comentarios_raw:
                try:
                    comentarios_lista = json.loads(comentarios_raw)
                except Exception:
                    comentarios_lista = []
                    
            if ano not in all_data:
                all_data[ano] = {}
            all_data[ano][qid] = {
                "valor": valor, 
                "pontos": pontos, 
                "link": link, 
                "comentarios": comentarios_lista
            }
    return all_data

# =============================================================================
# 2. GERADOR DO RELATÓRIO PDF
# =============================================================================
def gerar_relatorio_pdf(dados, ano, total, faixa, all_data=None):
    # Inicializa o buffer na memória e vincula ao SimpleDocTemplate
    buffer = BytesIO()
    
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4, 
        rightMargin=30, 
        leftMargin=30, 
        topMargin=30, 
        bottomMargin=50
    )
    elements = []
    styles = getSampleStyleSheet()

    style_titulo_capa = ParagraphStyle('TituloCapa', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=24, leading=28, textColor=colors.HexColor("#1b4f72"), alignment=1)

    # -------------------------------------------------------------------------
    # FOLHA 1: CAPA
    # -------------------------------------------------------------------------
    elements.append(Spacer(1, 100))
    
    try:
        logo = Image("iegm.png", width=380, height=180)
        logo.hAlign = 'CENTER'
        elements.append(logo)
    except Exception:
        elements.append(Paragraph("[Logo: iegm.png]", styles["Title"]))
        
    elements.append(Spacer(1, 50))
    elements.append(Paragraph("Relatório I-Gov-TI", style_titulo_capa))
    elements.append(Spacer(1, 15))
    
    style_ano_capa = ParagraphStyle('AnoCapa', parent=styles['Normal'], fontName='Helvetica', fontSize=16, textColor=colors.HexColor("#7f8c8d"), alignment=1)
    elements.append(Paragraph(str(ano), style_ano_capa))
    elements.append(PageBreak())

    # -------------------------------------------------------------------------
    # FOLHA 2: SUMÁRIO
    # -------------------------------------------------------------------------
    elements.append(Paragraph("<b>SUMÁRIO</b>", styles["h1"]))
    elements.append(Spacer(1, 30))

    style_item_esquerda = ParagraphStyle('ItemEsq', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, textColor=colors.HexColor("#2c3e50"))
    style_pag_direita = ParagraphStyle('PagDir', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, textColor=colors.HexColor("#1b4f72"), alignment=2)

    dados_sumario = [
        [Paragraph("1. Resumo Executivo (Análise Comparativa)", style_item_esquerda), Paragraph("Pág. 3", style_pag_direita)],
        [Paragraph("2. Análise de Desempenho por Quesito", style_item_esquerda), Paragraph("Pág. 3", style_pag_direita)],
        [Paragraph("3. Análise de Impacto e Penalidades", style_item_esquerda), Paragraph("Pág. 4", style_pag_direita)],
        [Paragraph("4. Diagnóstico de Reincidências", style_item_esquerda), Paragraph("Pág. 4", style_pag_direita)],
        [Paragraph("5. Alinhamento com a Agenda 2030 (ODS)", style_item_esquerda), Paragraph("Pág. 4", style_pag_direita)],
        [Paragraph("6. Série Histórica do I-cidade", style_item_esquerda), Paragraph("Pág. 5", style_pag_direita)],
    ]
    
    tabela_sumario = Table(dados_sumario, colWidths=[400, 90])
    tabela_sumario.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor("#bdc3c7"), 1, (2, 4)), 
    ]))
    elements.append(tabela_sumario)
    elements.append(PageBreak())

    # -------------------------------------------------------------------------
    # FOLHA 3+: CONTEÚDO
    # -------------------------------------------------------------------------
    elements.append(Paragraph(f"RELATÓRIO DE AUDITORIA i-GOV TI - {ano}", styles["Title"]))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("<b>1. RESUMO EXECUTIVO (ANÁLISE COMPARATIVA)</b>", styles["h2"]))
    elements.append(Spacer(1, 8))

    nota_atual = float(total)
    ano_atual = int(str(ano).strip()[:4])
    ano_ant = ano_atual - 1

    def converter_pontos_em_faixa_iegm(pontos):
        pts = float(pontos)
        if pts < 500.0:              return "C"
        elif 500.0 <= pts <= 599.9:  return "C+"
        elif 600.0 <= pts <= 749.9:  return "B"
        elif 750.0 <= pts <= 899.9:  return "B+"
        else:                        return "A"

    # Se all_data não for fornecido, inicializa como dicionário vazio para evitar quebras
    if all_data is None:
        all_data = {}

    dados_ano_anterior = all_data.get(ano_ant, {})
    nota_anterior = 0.0
    if ano_ant in all_data:
        nota_anterior = float(sum(
            info_ant.get("pontos", 0) 
            for qid_ant, info_ant in dados_ano_anterior.items() 
            if isinstance(info_ant, dict) and not qid_ant.startswith("COM_")
        ))

    faixa_anterior = converter_pontos_em_faixa_iegm(nota_anterior)
    faixa_real_atual = faixa if faixa else converter_pontos_em_faixa_iegm(nota_atual)

    variacao_pontos = nota_atual - nota_anterior
    if nota_anterior > 0:
        variacao_percentual = (variacao_pontos / nota_anterior) * 100
        texto_percentual = f"{variacao_percentual:+.2f}%"
    else:
        texto_percentual = "0.00%"

    if variacao_pontos > 0:
        cor_variacao = colors.HexColor("#28a745")
        seta_tendencia = "▲"
    elif variacao_pontos < 0:
        cor_variacao = colors.HexColor("#dc3545")
        seta_tendencia = "▼"
    else:
        cor_variacao = colors.HexColor("#6c757d")
        seta_tendencia = "■"

    style_th = ParagraphStyle('Th', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, textColor=colors.whitesmoke, alignment=1)
    style_td_ano = ParagraphStyle('TdAno', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, textColor=colors.HexColor("#2c3e50"), alignment=1)
    style_td_pts = ParagraphStyle('TdPts', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=12, alignment=1)
    style_td_faixa = ParagraphStyle('TdFaixa', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=12, textColor=colors.HexColor("#1b4f72"), alignment=1)
    style_td_var = ParagraphStyle('TdVar', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=12, textColor=cor_variacao, alignment=1)

    dados_comparativos = [
        [Paragraph("Exercício", style_th), Paragraph("Pontuação Obtida", style_th), Paragraph("Faixa / Conceito", style_th), Paragraph("Variação Nominal", style_th), Paragraph("Variação Percentual", style_th)],
        [Paragraph(str(ano_ant), style_td_ano), Paragraph(f"{nota_anterior:.1f} pts", style_td_pts), Paragraph(str(faixa_anterior), style_td_faixa), Paragraph("-", style_td_var), Paragraph("-", style_td_var)],
        [Paragraph(str(ano_atual), style_td_ano), Paragraph(f"{nota_atual:.1f} pts", style_td_pts), Paragraph(str(faixa_real_atual), style_td_faixa), Paragraph(f"{seta_tendencia} {variacao_pontos:+.1f} pts", style_td_var), Paragraph(f"{seta_tendencia} {texto_percentual}", style_td_var)]
    ]

    tabela_comp = Table(dados_comparativos, colWidths=[80, 105, 95, 105, 105])
    tabela_comp.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#bdc3c7")), 
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#f8f9fa")), ("BACKGROUND", (0, 2), (-1, 2), colors.whitesmoke),          
    ]))
    elements.append(tabela_comp)
    elements.append(Spacer(1, 12))

    style_analise = ParagraphStyle('Analise', parent=styles['Normal'], fontSize=10, leading=14)
    if variacao_pontos > 0:
        texto_analise = f"<b>Análise de Tendência:</b> O município registrou uma evolução de desempenho com incremento de <b>{texto_percentual}</b> na sua pontuação global comparado ao exercício de {ano_ant}."
    elif variacao_pontos < 0:
        texto_analise = f"<b>Análise de Tendência:</b> <font color='#dc3545'><b>Alerta de Retrocesso:</b></font> Foi identificada uma redução de <b>{texto_percentual}</b> na eficiência dos indicadores em relação a {ano_ant}."
    else:
        texto_analise = f"<b>Análise de Tendência:</b> O município apresentou estagnação absoluta (0.00%) no seu índice geral de conformidade."

    elements.append(Paragraph(texto_analise, style_analise))
    elements.append(Spacer(1, 15))

    # 2. ANÁLISE DE DESEMPENHO POR QUESITO
    elements.append(Paragraph("<b>2. ANÁLISE DE DESEMPENHO POR QUESITO</b>", styles["h2"]))
    elements.append(Spacer(1, 6))

    lista_pontos_fortes = []
    lista_pontos_fracos = []

    for qid, info in dados.items():
        if qid.startswith("COM_") or not isinstance(info, dict): continue
        pts_obtidos = float(info.get("pontos", 0))
        valor_resposta = info.get("valor", "")
        link_evidencia = info.get("link", "")
        pts_maximo = float(PONTUACOES_MAX.get(qid, 0)) if 'PONTUACOES_MAX' in globals() else 10.0
        
        if pts_maximo > 0:
            eficiencia = (pts_obtidos / pts_maximo) * 100
            item_data = {"qid": qid, "pts_obtidos": pts_obtidos, "pts_maximo": pts_maximo, "eficiencia": eficiencia, "valor": valor_resposta, "link": link_evidencia}
            if eficiencia >= 100.0: 
                lista_pontos_fortes.append(item_data)
            elif eficiencia < 100.0:
                lista_pontos_fracos.append(item_data)

    if lista_pontos_fortes:
        elements.append(Paragraph("<b>✅ Pontos Fortes:</b>", styles["h3"]))
        data_fortes = [["Quesito", "Nota / Teto", "Eficiência", "Resposta / Evidência"]]
        for item in sorted(lista_pontos_fortes, key=lambda x: x["pts_obtidos"], reverse=True):
            evidencia = f"<b>{item['valor']}</b><br/>{item['link']}"
            data_fortes.append([item['qid'], f"{item['pts_obtidos']:.1f} / {item['pts_maximo']:.1f}", f"{item['eficiencia']:.1f}%", Paragraph(evidencia, styles["Normal"])])
        tabela_fortes = Table(data_fortes, colWidths=[65, 75, 65, 285])
        tabela_fortes.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#28a745")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke), ("ALIGN", (0, 0), (2, -1), "CENTER"), ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#28a745")), ("FONTSIZE", (0, 0), (-1, -1), 9), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        elements.append(tabela_fortes)
        elements.append(Spacer(1, 12))

    if lista_pontos_fracos:
        elements.append(Paragraph("<b>⚠️ Pontos Fracos Geral:</b>", styles["h3"]))
        data_fracos = [["Quesito", "Nota / Teto", "Eficiência", "Resposta / Evidência"]]
        for item in sorted(lista_pontos_fracos, key=lambda x: x["pts_obtidos"]):
            evidencia = f"<b>{item['valor']}</b><br/>{item['link']}"
            data_fracos.append([item['qid'], f"{item['pts_obtidos']:.1f} / {item['pts_maximo']:.1f}", f"{item['eficiencia']:.1f}%", Paragraph(evidencia, styles["Normal"])])
        tabela_fracos = Table(data_fracos, colWidths=[65, 75, 65, 285])
        tabela_fracos.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e67e22")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke), ("ALIGN", (0, 0), (2, -1), "CENTER"), ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e67e22")), ("FONTSIZE", (0, 0), (-1, -1), 9), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        elements.append(tabela_fracos)
        elements.append(Spacer(1, 15))

    # -------------------------------------------------------------------------
    # 3. ANÁLISE DE IMPACTO E PENALIDADES (EFICIÊNCIA PREVENTIVA)
    # -------------------------------------------------------------------------
    elements.append(Paragraph("<b>3. ANÁLISE DE IMPACTO E PENALIDADES (EFICIÊNCIA PREVENTIVA)</b>", styles["h2"]))
    elements.append(Spacer(1, 6))

    PENALIDADES_MAX = {
        "8.3": -51.0,
        "8.4": -51.0
    }

    lista_penalidades = []
    
    for qid, pen_max in PENALIDADES_MAX.items():
        info = dados.get(qid, {}) if isinstance(dados.get(qid), dict) else {"pontos": 0.0, "valor": "Não Respondido", "link": ""}
        
        try:
            nota_real = float(info.get("pontos", 0.0))
        except (ValueError, TypeError):
            nota_real = 0.0
        
        if nota_real < 0:
            eficiencia_preventiva = 0.0
            status_html = "<font color='#dc3545'><b>Impacto Máximo Aplicado</b></font>"
        else:
            eficiencia_preventiva = 100.0
            status_html = "<font color='#28a745'><b>Risco Mitigado (Sem Penalidade)</b></font>"

        lista_penalidades.append({
            "qid": qid,
            "nota_real": nota_real,
            "pen_max": pen_max,
            "eficiencia": eficiencia_preventiva,
            "status": status_html
        })

    data_penalidades = [["Quesito", "Nota Obtida", "Penalidade Máxima", "Eficiência Preventiva", "Status de Risco"]]
    
    for item in sorted(lista_penalidades, key=lambda x: x["eficiencia"]):
        nota_txt = f"{item['nota_real']:.1f} pts"
        teto_txt = f"{item['pen_max']:.1f} pts"
        ef_txt = f"{item['eficiencia']:.1f}%"
        
        data_penalidades.append([
            item['qid'], 
            nota_txt, 
            teto_txt, 
            ef_txt, 
            Paragraph(item['status'], styles["Normal"]) 
        ])
        
    tabela_pen = Table(data_penalidades, colWidths=[65, 100, 110, 115, 150])
    tabela_pen.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1b4f72")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#1b4f72")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    
    elements.append(tabela_pen)
    elements.append(Spacer(1, 15))

    # -------------------------------------------------------------------------
    # 4. DIAGNÓSTICO DE REINCIDÊNCIAS 
    # -------------------------------------------------------------------------
    elements.append(Paragraph("<b>4. DIAGNÓSTICO DE REINCIDÊNCIAS (GARGALOS PERSISTENTES)</b>", styles["h2"]))
    elements.append(Spacer(1, 6))
    
    reincidencias_detectadas = []
    
    # Dicionário de tetos oficiais para validar apenas quesitos de nota real
    TETOS_VALIDOS = {
        "1.0": 30, "1.1": 30, "1.2": 30, "1.3": 30, "1.3.1": 30, "1.4.1": 40, "1.4.2": 20,
        "2.0": 40, "2.1": 20, "2.2": 40, "2.3": 20,
        "3.0": 50, "3.1": 20, "3.1.1": 40, "3.1.1.1": 10, "3.2.1": 10, "3.3": 30, "3.4": 30, "3.5": 30, "3.6": 20,
        "4.0": 40, "6.0": 20, "6.1": 20, "6.2": 20, "6.3": 10, "6.4": 30, "7.0": 25, "7.1": 10, "7.2": 10, "7.3": 5,
        "8.0": 40, "8.2.1": 50, "8.2.2": 30, "9.1": 120, 
    }
    
    for qid, info_atual in dados.items():
        # Ignora comentários e chaves que não sejam dicionários válidos
        if qid.startswith("COM_") or not isinstance(info_atual, dict): 
            return_val = None
            continue
            
        # CRÍTICO: Só avalia se o quesito pertencer à lista de pontuações oficiais
        if qid not in TETOS_VALIDOS:
            continue
            
        pts_maximo = float(TETOS_VALIDOS[qid])
        pts_obtidos_atual = float(info_atual.get("pontos", 0.0))
        
        # Só analisa se o teto for válido e se houve falha real no ano atual (eficiência < 50%)
        if pts_maximo > 0 and (pts_obtidos_atual / pts_maximo) * 100 < 50.0:
            # Busca o mesmo quesito no ano anterior
            info_ant = dados_ano_anterior.get(qid, {}) if isinstance(dados_ano_anterior, dict) else {}
            pts_obtidos_ant = float(info_ant.get("pontos", 0.0)) if isinstance(info_ant, dict) else 0.0
            
            # Se também falhou no ano anterior (eficiência < 50%), temos uma Reincidência Crônica
            if (pts_obtidos_ant / pts_maximo) * 100 < 50.0:
                # Define a categoria dinamicamente com base no prefixo do quesito
                if qid.startswith("1") or qid.startswith("2") or qid.startswith("5"):
                    origem = "Governança de TI"
                elif qid.startswith("6") or qid.startswith("7"):
                    origem = "Transparência Digital"
                else:
                    origem = "Segurança / Operação"
                    
                reincidencias_detectadas.append({
                    "qid": qid,
                    "tipo": origem,
                    "detalhe": "Ineficiência Crônica de Desempenho (Abaixo de 50% por 2 anos)",
                    "ant": f"{pts_obtidos_ant:.1f} pts",
                    "atual": f"{pts_obtidos_atual:.1f} pts"
                })

    if reincidencias_detectadas:
        data_reinc = [["Quesito", "Origem da Falha", "Impacto Histórico", "Exercício Anterior", "Exercício Atual"]]
        # Ordena a tabela pelo ID do quesito para ficar organizado
        for reinc in sorted(reincidencias_detectadas, key=lambda x: [float(i) for i in x["qid"].split('.') if i.isdigit()]): 
            data_reinc.append([
                reinc["qid"], 
                reinc["tipo"], 
                Paragraph(f"<b>{reinc['detalhe']}</b>", styles["Normal"]), 
                reinc["ant"], 
                reinc["atual"]
            ])
            
        tabela_reinc = Table(data_reinc, colWidths=[65, 115, 170, 75, 65])
        tabela_reinc.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#c0392b")), 
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke), 
            ("ALIGN", (0, 0), (-1, 0), "CENTER"), 
            ("ALIGN", (0, 1), (1, -1), "CENTER"), 
            ("ALIGN", (3, 1), (-1, -1), "CENTER"), 
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#c0392b")), 
            ("FONTSIZE", (0, 0), (-1, -1), 9), 
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(tabela_reinc)
    else: 
        elements.append(Paragraph("<font color='#28a745'><b>✅ Nenhuma reincidência ativa detectada. O município corrigiu ou mitigou as falhas do ano anterior.</b></font>", styles["Normal"]))
        
    elements.append(Spacer(1, 15))

    # -------------------------------------------------------------------------
    # 5. ALINHAMENTO COM A AGENDA 2030 (METAS ODS / ONU)
    # -------------------------------------------------------------------------
    # Importação com apelido isolado para não afetar o escopo global do PDF
    import reportlab.lib.colors as rl_colors

    elements.append(Paragraph("<b>5. ALINHAMENTO COM A AGENDA 2030 (METAS ODS / ONU)</b>", styles["h2"]))
    elements.append(Spacer(1, 6))

    def calcular_percentual_checklist(resposta_bruta, total_itens):
        if not resposta_bruta: 
            return 0.0
        
        # Se a string salva contiver estrutura de lista do Python ['item1', 'item2']
        if str(resposta_bruta).startswith("["):
            try:
                import ast
                itens_lista = ast.literal_eval(str(resposta_bruta))
                if isinstance(itens_lista, list):
                    itens_validos = [str(i).strip().lower() for i in itens_lista if "outros" not in str(i).lower()]
                    return min((len(itens_validos) / total_itens) * 100.0, 100.0) if total_itens > 0 else 0.0
            except Exception:
                pass
                
        # Fallback limpo caso seja texto puro separado por vírgula
        itens = [i.strip().lower() for i in str(resposta_bruta).split(",") if i.strip()]
        itens_validos = [i for i in itens if "outros" not in i]
        return min((len(itens_validos) / total_itens) * 100.0, 100.0) if total_itens > 0 else 0.0

    # Dicionário de Metas ODS parametrizado conforme as regras do i-Gov TI
    REGRAS_ODS = {
        "1.0": {"metas": "16.6, 17.8", "total_chk": 0},
        "1.2": {"metas": "9.c", "total_chk": 0},
        "1.3": {"metas": "9.c, 16.6, 17.8", "total_chk": 0},
        "1.4": {"metas": "16.6, 17.8", "total_chk": 0},
        "1.4.2": {"metas": "16.6, 17.8", "total_chk": 0},
        "2.0": {"metas": "16.6, 16.7, 17.8", "total_chk": 0},
        "3.0": {"metas": "16.6, 16.a, 17.8", "total_chk": 0},
        "3.1": {"metas": "16.6", "total_chk": 0},
        "3.1.1": {"metas": "16.6", "total_chk": 0},
        "3.3": {"metas": "Mapeada", "total_chk": 0},
        "3.4": {"metas": "9.c, 16.6", "total_chk": 0},
        "3.5": {"metas": "16.5, 16.6, 16.7, 17.8", "total_chk": 0},
        "3.6": {"metas": "16.5, 16.6, 16.7, 17.8", "total_chk": 0},
        "4.0": {"metas": "16.5, 16.6, 17.8", "total_chk": 0},
        "5.0": {"metas": "9.4, 16.5, 16.6, 17.14", "total_chk": 0},
        "6.0": {"metas": "16.6, 17.8", "total_chk": 0},
        "6.1": {"metas": "9.c, 16.7, 17.8", "total_chk": 0},
        "6.2": {"metas": "16.6", "total_chk": 0},
        "6.3": {"metas": "16.6, 16.7", "total_chk": 0},
        "6.4": {"metas": "10.2, 16.6, 17.8", "total_chk": 0},
        "7.0": {"metas": "16.5, 16.6, 17.8", "total_chk": 0},
        "7.1": {"metas": "16.5, 16.6, 16.7, 17.8", "total_chk": 0},
        "7.2": {"metas": "16.5, 16.6, 17.8", "total_chk": 0},
        "7.3": {"metas": "16.5, 16.6, 16.7, 17.8", "total_chk": 0},
        "8.0": {"metas": "16.5, 16.6, 17.8, 17.14", "total_chk": 0},
        "8.1": {"metas": "Checklist Perc.", "total_chk": 17},
        "8.2": {"metas": "Checklist Perc.", "total_chk": 17},
        "8.2.1": {"metas": "16.5, 16.6, 16.7, 17.8, 17.14", "total_chk": 0},
        "8.4": {"metas": "Checklist Perc.", "total_chk": 17},
        "9.0": {"metas": "10.2, 16.6, 17.8", "total_chk": 0},
        "9.1": {"metas": "Checklist Perc.", "total_chk": 16},
        "10.0": {"metas": "16.5, 16.6, 16.7, 17.8", "total_chk": 0},
        "10.3": {"metas": "16.5, 16.6, 16.7, 17.8", "total_chk": 0},
        "10.4": {"metas": "16.5, 16.6, 16.7, 17.8", "total_chk": 0},
        "10.5": {"metas": "16.5, 16.6, 16.7, 17.8", "total_chk": 0},
        "11.0": {"metas": "16.5, 16.6, 16.7, 17.8", "total_chk": 0}
    }

    analise_ods = []
    
    # 🕵️‍♂️ Captura dinâmica do DICIONÁRIO DE DADOS para suportar qualquer escopo
    dados_reference = None
    for nome_var in ['dados', 'res_data', 'respostas', 'dados_municipio']:
        if nome_var in locals():
            dados_reference = locals()[nome_var]
            break

    # Se falhar localmente, tenta herdar o dicionário definido no escopo imediatamente superior
    if dados_reference is None:
        try:
            dados_reference = dados
        except NameError:
            try:
                dados_reference = res_data
            except NameError:
                dados_reference = {}

    for qid, config in REGRAS_ODS.items():
        info = dados_reference.get(qid, {}) if isinstance(dados_reference, dict) else {"valor": "Não Respondido"}
        if not isinstance(info, dict):
            info = {"valor": str(info)}
            
        resp = str(info.get("valor", "")).strip()
        resp_l = resp.lower()
        
        if not resp or resp_l == "não respondido" or resp == "[]": 
            continue
            
        if config["total_chk"] > 0:
            pct = calcular_percentual_checklist(resp, config["total_chk"])
            status = f"{pct:.1f}% Atendido"
        else:
            if "não" in resp_l and qid in ["5.1.2"]: 
                status = "Atendido"
            elif "sim" in resp_l or "parcialmente" in resp_l or "integralmente" in resp_l or "todas" in resp_l or "maior parte" in resp_l:
                status = "Atendido"
            else:
                status = "Não Atendido"

        # Formatação para exibição limpa na tabela removendo colchetes e aspas simples
        exibicao_resp = resp
        if exibicao_resp.startswith("["):
            exibicao_resp = exibicao_resp.replace("[", "").replace("]", "").replace("'", "")

        analise_ods.append({
            "qid": qid,
            "status": status,
            "metas": config["metas"],
            "resp": exibicao_resp[:45] + "..." if len(exibicao_resp) > 45 else exibicao_resp
        })

    if analise_ods:
        data_ods = [["Quesito", "Resposta Informada", "Vínculo Metas ODS", "Status de Cumprimento"]]
        style_td_ods = ParagraphStyle('TdOds', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, alignment=1)
        
        for item in sorted(analise_ods, key=lambda x: [float(i) if i.replace('.','',1).isdigit() else 999 for i in x['qid'].split('.')]):
            st_txt = item["status"]
            
            if "Não Atendido" in st_txt:
                st_p = Paragraph(f"<font color='#dc3545'><b>{st_txt}</b></font>", style_td_ods)
            elif "Atendido" in st_txt and "%" not in st_txt:
                st_p = Paragraph(f"<font color='#28a745'><b>{st_txt}</b></font>", style_td_ods)
            else:
                st_p = Paragraph(f"<font color='#007bff'><b>{st_txt}</b></font>", style_td_ods)
                
            data_ods.append([
                item["qid"], 
                Paragraph(item["resp"], styles["Normal"]), 
                item["metas"], 
                st_p
            ])
            
        tabela_ods = Table(data_ods, colWidths=[60, 200, 115, 110])
        tabela_ods.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), rl_colors.HexColor("#0f9d58")), 
            ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.whitesmoke), 
            ("ALIGN", (0, 0), (0, -1), "CENTER"), 
            ("GRID", (0, 0), (-1, -1), 0.5, rl_colors.HexColor("#0f9d58")), 
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(tabela_ods)
        elements.append(Spacer(1, 15))

    # -------------------------------------------------------------------------
    # 📊 6. SÉRIE HISTÓRICA DO I-GOV TI (CONSOLIDADO FINAL)
    # -------------------------------------------------------------------------
    # IMPORTS LOCAIS SEGUROS (Evita conflitos de escopo global no ReportLab)
    from reportlab.graphics.shapes import Drawing, String
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    import reportlab.lib.colors as rl_colors

    elements.append(Spacer(1, 10))
    elements.append(Paragraph("<b>6. SÉRIE HISTÓRICA DO I-GOV TI (CONSOLIDADO FINAL)</b>", styles["h2"]))
    elements.append(Spacer(1, 10))

    anos_serie = [2023, 2024, 2025, 2026, 2027, 2028, 2029, 2030]
    valores_serie = []
    
    # 🕵️‍♂️ Captura dinâmica do ANO para evitar conflito de nomenclatura
    ano_reference = None
    for nome_var in ['ano_sel', 'ano_atual', 'ano', 'exercicio']:
        if nome_var in locals():
            ano_reference = locals()[nome_var]
            break
    if ano_reference is None:
        ano_reference = 2026

    # 🕵️‍♂️ Captura dinâmica da NOTA ATUAL DO COMPILADOR
    nota_reference = 0.0
    for nome_var in ['total_pts', 'nota_atual', 'pontuacao_final']:
        if nome_var in locals():
            try:
                nota_reference = float(locals()[nome_var])
                break
            except (ValueError, TypeError):
                continue

    # Montagem dos dados do gráfico (Sincronizado com o parâmetro all_data + Fallbacks)
    import streamlit as st

    for a in anos_serie:
        # 1. Se for o ano selecionado atualmente no formulário
        if a == ano_reference: 
            if nota_reference > 0.0:
                valores_serie.append(min(nota_reference, 1000.0))
            elif dados_reference and isinstance(dados_reference, dict):
                nota_recuperada = float(sum(info_h.get("pontos", 0.0) for qid_h, info_h in dados_reference.items() if isinstance(info_h, dict) and not qid_h.startswith("COM_")))
                valores_serie.append(min(nota_recuperada, 1000.0))
            else:
                valores_serie.append(0.0)
                
        # 2. Se o ano estiver salvo no dicionário "all_data" passado por parâmetro
        elif all_data and a in all_data:
            dados_ano = all_data[a]
            if isinstance(dados_ano, dict):
                pontos_ano = float(sum(info_h.get("pontos", 0.0) for qid_h, info_h in dados_ano.items() if isinstance(info_h, dict) and not qid_h.startswith("COM_")))
                valores_serie.append(min(pontos_ano, 1000.0))
            else:
                valores_serie.append(min(float(dados_ano), 1000.0))

        # 3. Fallback: Se o ano estiver salvo no histórico do session_state do Streamlit
        elif hasattr(st, 'session_state') and 'all_data' in st.session_state and a in st.session_state.all_data:
            dados_ano = st.session_state.all_data[a]
            if isinstance(dados_ano, dict):
                pontos_ano = float(sum(info_h.get("pontos", 0.0) for qid_h, info_h in dados_ano.items() if isinstance(info_h, dict) and not qid_h.startswith("COM_")))
                valores_serie.append(min(pontos_ano, 1000.0))
            else:
                valores_serie.append(min(float(dados_ano), 1000.0))
                
        # 4. Se não encontrar o ano em lugar nenhum, deixa zerado
        else: 
            valores_serie.append(0.0)

    # Configuração do Gráfico do i-Gov TI
    desenho_grafico = Drawing(480, 165)
    bc = VerticalBarChart()
    bc.x = 45
    bc.y = 25
    bc.height = 110
    bc.width = 410
    bc.data = [valores_serie]
    bc.categoryAxis.categoryNames = [str(a) for a in anos_serie]
    bc.categoryAxis.labels.fontSize = 9
    bc.categoryAxis.labels.fontName = 'Helvetica-Bold'
    bc.categoryAxis.labels.dy = -10
    
    # Escala baseada nas regras de pontuação até 1000
    bc.valueAxis.valueMin = 0
    bc.valueAxis.valueMax = 1000
    bc.valueAxis.valueStep = 200
    bc.valueAxis.labels.fontSize = 8
    
    # 🔥 ATIVAÇÃO DOS RÓTULOS (PONTUAÇÃO EM CIMA DA BARRA)
    bc.barLabels.nudge = 8
    bc.barLabels.fontSize = 8
    bc.barLabels.fontName = 'Helvetica-Bold'
    bc.barLabelFormat = '%.1f'
    
    # Customização das cores utilizando o padrão institucional estável
    bc.bars[0].fillColor = rl_colors.HexColor("#1b4f72")
    bc.bars[0].strokeColor = rl_colors.HexColor("#2c3e50")
    bc.bars[0].strokeWidth = 0.5

    # Título do Gráfico atualizado para o i-Gov TI
    desenho_grafico.add(String(240, 150, "Série Histórica do I-Gov TI", textAnchor='middle', fontName='Helvetica-Bold', fontSize=12, fillColor=rl_colors.HexColor("#2c3e50")))
    desenho_grafico.add(bc)
    
    elements.append(desenho_grafico)
    elements.append(Spacer(1, 15))

    # =============================================================================
    # --- FECHAMENTO E RETORNO SEGURO DO RELATÓRIO (FIM DA FUNÇÃO) ---
    # =============================================================================
    doc.build(elements)
    buffer.seek(0)
    return buffer

# =============================================================================
# 3. INTERFACE E FORMULÁRIO (STREAMLIT)
# =============================================================================
def render_sidebar():
    st.sidebar.title("🛠️ Painel i-GOV TI")
    anos = [2023, 2024, 2025, 2026, 2027, 2028, 2029, 2030]
    ano_sel = st.sidebar.selectbox("Ano de Referência:", anos, key="ano_referencia_global")
    res_data = load_respostas(ano_sel)
    
    total_pts = sum(float(item.get("pontos", 0)) for k, item in res_data.items() if not k.startswith("COM_"))
    
    if total_pts <= 499:   faixa, cor = "C",  "red"
    elif total_pts <= 599: faixa, cor = "C+", "orange"
    elif total_pts <= 749: faixa, cor = "B",  "#d4d400"
    elif total_pts <= 899: faixa, cor = "B+", "lightgreen"
    elif total_pts <= 1000: faixa, cor = "A",  "green"

    st.sidebar.metric("Pontuação Total", f"{total_pts:.1f} pts")
    st.sidebar.markdown(f"**Faixa:** <span style='color:{cor}; font-size:20px; font-weight:bold;'>{faixa}</span>", unsafe_allow_html=True)
    
    # 🔥 Botão de Download do Relatório PDF Integrado na Sidebar (COM HISTÓRICO TRATADO)
    st.sidebar.markdown("---")
    st.sidebar.subheader("📄 Relatórios")
    
    # 1. Busca os dados brutos de todos os anos no banco de dados para a série histórica
    try:
        dados_historicos_brutos = get_all_years_data()
    except Exception:
        dados_historicos_brutos = {}
        
    # 2. TRATAMENTO CRÍTICO: Garante que as chaves dos anos sejam inteiros (ex: converte "2024" para 2024)
    historico_tratado = {}
    if isinstance(dados_historicos_brutos, dict):
        for ano_chave, valor_ano in dados_historicos_brutos.items():
            try:
                ano_int = int(str(ano_chave).strip()[:4])
                historico_tratado[ano_int] = valor_ano
            except (ValueError, TypeError):
                continue

    # 3. Alimenta o session_state como garantia extra para o componente do gráfico
    st.session_state.all_data = historico_tratado

    # 4. Gera o relatório passando o dicionário histórico tratado para o gráfico puxar os dados
    pdf_buffer = gerar_relatorio_pdf(res_data, ano_sel, total_pts, faixa, historico_tratado)
    
    st.sidebar.download_button(
        label="📥 Baixar Relatório PDF",
        data=pdf_buffer.getvalue(),  # Extrai o valor binário correto
        file_name=f"Relatorio_i-Gov TI_{ano_sel}.pdf",
        mime="application/pdf"
    )
    
    st.sidebar.markdown("---")
    if st.sidebar.button("🔄 Zerar Questionário"):
        with get_connection() as conn:
            conn.execute("DELETE FROM respostas WHERE ano = ?", (ano_sel,))
            conn.commit()
        st.rerun()
        
    return total_pts, res_data, ano_sel


def mostrar_formulario_gov():
    # =========================================================================
    # CORREÇÃO CRÍTICA PARA CONFLITO DE ESCOPO DO 're' (UNBOUNDLOCALERROR)
    # =========================================================================
    global re
    import sys
    re = sys.modules['re']
    # =========================================================================

    init_db()
    total_pts, res_data, ano_sel = render_sidebar()
    
    st.markdown("""
        <style>
        .quesito-card {
            background-color: #f8f9fa;
            padding: 20px;
            border-left: 6px solid #1e3a5f;
            border-radius: 8px;
            margin-bottom: 20px;
            border: 1px solid #ddd;
        }
        </style>
    """, unsafe_allow_html=True)

    st.title(f"📊 Auditoria i-Gov TI - {ano_sel}")
    
    aba_quest, aba_graf = st.tabs(["📋 Questionário", "📈 Gráficos"])
    
    with aba_quest:
        # Veja se o seu erro estava aqui para baixo:
        # Se a linha "st.header("1.0 Estrutura de TIC")" estiver aqui dentro, 
        # ela PRECISA ter 8 espaços de recuo (2 tabs) por estar dentro do "with aba_quest:"
        st.write("Conteúdo do questionário aqui...")

        # --- SEÇÃO 1: INFRAESTRUTURA E SETOR ---
        st.header("1.0 Estrutura de TIC")
        
        # =============================================================================
        # QUESITO 1.0
        # =============================================================================
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 1.0")
        st.write("**A Prefeitura possui uma área ou setor que cuida de Tecnologia da Informação e Comunicação bgvc (TIC)?**")
        d10 = res_data.get("1.0", {"valor": None, "pontos": 0, "link": ""})
        opcoes10 = ["Sim – 30", "Não – 00"]
        idx10 = opcoes10.index(d10["valor"]) if d10["valor"] in opcoes10 else None
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r10 = st.radio("Selecione 1.0:", opcoes10, index=idx10, key=f"q10_{ano_sel}")
        with col2:
            l10 = st.text_area("Link/Evidência (1.0):", value=d10.get("link", ""), key=f"l10_{ano_sel}", height=100)
            
            # Captura e renderiza o link ativo embaixo da caixa em tempo real
            import sys
            links_f10 = sys.modules['re'].findall(r'(https?://[^\s]+)', l10)
            if links_f10:
                for lk in links_f10:
                    st.markdown(f"🔗 **Link ativo:** [{lk}]({lk})")

        # Dispara quando houver QUALQUER alteração em relação ao banco
        if r10 and (r10 != d10["valor"] or l10 != d10["link"]):
            save_resp("1.0", r10, 30 if "Sim" in r10 else 0, l10)
            
            # Trava absoluta: o modal só abre se a lista do REGEX não estiver vazia E o link mudou
            if links_f10 and l10.strip() != d10["link"].strip():
                modal_aviso_link("1.0", [lk.strip() for lk in links_f10])
            else:
                st.rerun()
                
        bloco_comentarios("1.0", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # =============================================================================
        # QUESITO 1.1
        # =============================================================================
        if r10 and "Sim" in r10:
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader("QUESITO 1.1")
            st.write("**Informe a quantidade: Fórmula de cálculo: Funcionários concursados + Funcionários comissionados + Estagiários no suporte e atendimento de primeiro nível > 0 - 30 pontos**")
            d11 = res_data.get("1.1", {"valor": "0", "pontos": 0, "link": ""})
            
            v_conc_i, v_comi_i, v_esta_i, v_outr_i = 0, 0, 0, 0
            evidencia_11_salva = ""
            
            raw_link = d11.get("link", "")
            if raw_link:
                try:
                    if "|LINK:" in raw_link:
                        contadores_part, evidencia_11_salva = raw_link.split("|LINK:", 1)
                    else:
                        contadores_part = raw_link
                    
                    parts = contadores_part.split(",")
                    v_conc_i = int(parts[0].split(":")[1])
                    v_comi_i = int(parts[1].split(":")[1])
                    v_esta_i = int(parts[2].split(":")[1])
                    v_outr_i = int(parts[3].split(":")[1])
                except Exception:
                    v_conc_i, v_comi_i, v_esta_i, v_outr_i = 0, 0, 0, 0

            col1, col2, col3, col4 = st.columns(4)
            
            col1.markdown('<label style="font-size: 14px; font-weight: 500;" translate="no">Concursados:</label>', unsafe_allow_html=True)
            v_conc = col1.number_input("", min_value=0, step=1, value=v_conc_i, key=f"q11_conc_{ano_sel}", label_visibility="collapsed")
            
            col2.markdown('<label style="font-size: 14px; font-weight: 500;">Comissionados:</label>', unsafe_allow_html=True)
            v_comi = col2.number_input("", min_value=0, step=1, value=v_comi_i, key=f"q11_comi_{ano_sel}", label_visibility="collapsed")
            
            col3.markdown('<label style="font-size: 14px; font-weight: 500;">Estagiários:</label>', unsafe_allow_html=True)
            v_esta = col3.number_input("", min_value=0, step=1, value=v_esta_i, key=f"q11_esta_{ano_sel}", label_visibility="collapsed")
            
            col4.markdown('<label style="font-size: 14px; font-weight: 500;">Outros:</label>', unsafe_allow_html=True)
            v_outr = col4.number_input("", min_value=0, step=1, value=v_outr_i, key=f"q11_outr_{ano_sel}", label_visibility="collapsed")
            
            st.markdown("<div style='margin-bottom: 10px;'></div>", unsafe_allow_html=True)
            
            key_link_11 = f"l11_evidencia_{ano_sel}"
            l11 = st.text_area("Link/Evidência da composição da equipe (1.1):", value=evidencia_11_salva, key=key_link_11, height=80)
            
            links_f11 = re.findall(r'(https?://[^\s]+)', l11)
            if links_f11:
                for lk in links_f11:
                    st.markdown(f"🔗 **Link ativo:** [{lk}]({lk})")

            total_pessoal = v_conc + v_comi + v_esta
            pts11 = 30 if total_pessoal > 0 else 0
            
            new_link_composite = f"C:{v_conc},Co:{v_comi},E:{v_esta},O:{v_outr}|LINK:{l11.strip()}"
            
            if str(total_pessoal) != d11["valor"] or new_link_composite != raw_link:
                save_resp("1.1", str(total_pessoal), pts11, new_link_composite)
                
                # Trava no 1.1: valida se a lista do Regex tem dados e se difere do estado anterior
                if links_f11 and l11.strip() != evidencia_11_salva.strip():
                    modal_aviso_link("1.1", [lk.strip() for lk in links_f11])
                else:
                    st.rerun()
                    
            st.info(f"Total de pessoal (C+Co+E): {total_pessoal} | Pontos: {pts11}")
            bloco_comentarios("1.1", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

            # =============================================================================
            # QUESITO 1.2
            # =============================================================================
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader("QUESITO 1.2")
            st.write("**A prefeitura municipal definiu formalmente as atribuições do pessoal do setor de Tecnologia da Informação e Comunicação (TIC)?**")
            d12 = res_data.get("1.2", {"valor": None, "pontos": 0, "link": ""})
            opcoes12 = ["Sim – 30", "Não – 00"]
            idx12 = opcoes12.index(d12["valor"]) if d12["valor"] in opcoes12 else None
            
            col1, col2 = st.columns([1, 2])
            with col1:
                r12 = st.radio("Selecione 1.2:", opcoes12, index=idx12, key=f"q12_{ano_sel}")
            with col2:
                l12 = st.text_area("Link/Evidência (1.2):", value=d12.get("link", ""), key=f"l12_{ano_sel}", height=100)
                
                links_f12 = re.findall(r'(https?://[^\s]+)', l12)
                if links_f12:
                    for lk in links_f12:
                        st.markdown(f"🔗 **Link ativo:** [{lk}]({lk})")
            
            if r12 and (r12 != d12["valor"] or l12 != d12["link"]):
                save_resp("1.2", r12, 30 if "Sim" in r12 else 0, l12)
                
                # Trava no 1.2: Evita disparar se links_f12 for uma lista vazia (texto puro)
                if links_f12 and l12.strip() != d12["link"].strip():
                    modal_aviso_link("1.2", [lk.strip() for lk in links_f12])
                else:
                    st.rerun()
                    
            bloco_comentarios("1.2", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

            # =============================================================================
            # QUESITO 1.3
            # =============================================================================
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader("QUESITO 1.3")
            st.write("**A prefeitura disponibilizou capacitação para o pessoal da área de Tecnologia da Informação e Comunicação (TIC)?**")
            d13 = res_data.get("1.3", {"valor": None, "pontos": 0, "link": ""})
            opcoes13 = ["Sim – 30", "Não – 00"]
            idx13 = opcoes13.index(d13["valor"]) if d13["valor"] in opcoes13 else None
            
            col1, col2 = st.columns([1, 2])
            with col1:
                r13 = st.radio("Selecione 1.3:", opcoes13, index=idx13, key=f"q13_{ano_sel}")
            with col2:
                l13 = st.text_area("Link/Evidência (1.3):", value=d13.get("link", ""), key=f"l13_{ano_sel}", height=100)
                
                links_f13 = re.findall(r'(https?://[^\s]+)', l13)
                if links_f13:
                    for lk in links_f13:
                        st.markdown(f"🔗 **Link ativo:** [{lk}]({lk})")
            
            if r13 and (r13 != d13["valor"] or l13 != d13["link"]):
                save_resp("1.3", r13, 30 if "Sim" in r13 else 0, l13)
                
                # Trava no 1.3: Certifica-se de que existem URLs capturadas antes de chamar a janela modal
                if links_f13 and l13.strip() != d13["link"].strip():
                    modal_aviso_link("1.3", [lk.strip() for lk in links_f13])
                else:
                    st.rerun()
            
            # Sub-Quesito Dependente 1.3.1
            if r13 and "Sim" in r13:
                st.markdown("<br>", unsafe_allow_html=True)
                st.write("""**1.3.1 Informe em quais áreas houve capacitação...**""")
                d131 = res_data.get("1.3.1", {"valor": "[]", "pontos": 0})
                areas = ["Infraestrutura e Redes", "Desenvolvimento e Software", "Análise de Dados", "Gestão e Segurança", "Outros"]
                selecionadas = []
                
                for area in areas:
                    if st.checkbox(area, value=area in d131["valor"], key=f"q131_{area}_{ano_sel}"):
                        selecionadas.append(area)
                
                contagem = len([a for a in selecionadas if a != "Outros"])
                pts131 = 30 if contagem >= 3 else (15 if contagem == 2 else (5 if contagem == 1 else 0))
                
                if str(selecionadas) != d131["valor"]:
                    save_resp("1.3.1", str(selecionadas), pts131, "")
                    st.rerun()
            
            bloco_comentarios("1.3", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

            # =============================================================================
            # QUESITO 1.4
            # =============================================================================
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader("QUESITO 1.4")
            st.write("**Nas licitações e contratos que tenham como soluções o uso de Tecnologia da Informação e Comunicação, houve participação formalizada do pessoal de TIC? Considerar somente compras com verba municipal**")
            d14 = res_data.get("1.4", {"valor": None, "pontos": 0, "link": ""})
            
            col1, col2 = st.columns([1, 2])
            with col1:
                r14 = st.radio("Selecione 1.4:", ["Sim", "Não"], index=(0 if d14["valor"] == "Sim" else (1 if d14["valor"] == "Não" else None)), key=f"q14_{ano_sel}")
            with col2:
                l14 = st.text_area("Link/Evidência (1.4):", value=d14.get("link", ""), key=f"l14_{ano_sel}", height=100)
                
                # Captura e renderiza o link ativo embaixo da caixa em tempo real (1.4)
                links_f14 = re.findall(r'(https?://[^\s]+)', l14)
                if links_f14:
                    for lk in links_f14:
                        st.markdown(f"🔗 **Link ativo:** [{lk}]({lk})")

            # Executa se houver QUALQUER alteração
            if r14 and (r14 != d14["valor"] or l14 != d14["link"]):
                save_resp("1.4", r14, 0, l14)
                
                # Trava inteligente: só abre o modal se houver link HTTP E ele for diferente do banco
                if links_f14 and l14.strip() != d14["link"].strip():
                    modal_aviso_link("1.4", [lk.strip() for lk in links_f14])
                else:
                    st.rerun()  # Texto puro ou mudança de rádio: atualiza a tela de forma limpa
            
            if r14 == "Sim":
                st.write("**1.4.1 Etapas de participação:**")
                d141 = res_data.get("1.4.1", {"valor": "[]", "pontos": 0})
                etapas = {"Elaboração do edital / Especificação técnica – 15": 15, "Comissão de Licitação / Equipe de Apoio – 10": 10, "Recebimento / Gestão de Contrato – 15": 15}
                sel141 = []
                pts141 = 0
                for etapa, pts in etapas.items():
                    if st.checkbox(etapa, value=etapa in d141["valor"], key=f"q141_{etapa}_{ano_sel}"):
                        sel141.append(etapa)
                        pts141 += pts
                if str(sel141) != d141["valor"]:
                    save_resp("1.4.1", str(sel141), pts141, "")
                    st.rerun()

            bloco_comentarios("1.4", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

            # =============================================================================
            # QUESITO 1.4.2
            # =============================================================================
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader("QUESITO 1.4.2")
            st.write("**Sobre programas de computador (softwares) adquiridos ou licenciados nos últimos 5 anos, foi realizada análise ou estudo antes de sua contratação com a participação do pessoal de Tecnologia da Informação e Comunicação (TIC)?**")
            d142 = res_data.get("1.4.2", {"valor": None, "pontos": 0, "link": ""})
            opc142 = {"Sim, para todos os softwares – 20": 20, "Sim, para a maior parte dos softwares – 15": 15, "Sim, para a menor parte dos softwares – 08": 8, "Não foi realizado – 00": 0, "Não foi adquirido nenhum software nos últimos 5 anos – 20": 20}
            lista142 = list(opc142.keys())
            idx142 = lista142.index(d142["valor"]) if d142["valor"] in lista142 else None
            
            col1, col2 = st.columns([1, 2])
            with col1:
                r142 = st.radio("Selecione 1.4.2:", lista142, index=idx142, key=f"q142_{ano_sel}")
            with col2:
                l142 = st.text_area("Link/Evidência (1.4.2):", value=d142.get("link", ""), key=f"l142_{ano_sel}", height=100)
                
                # Captura e renderiza o link ativo embaixo da caixa em tempo real (1.4.2)
                links_f142 = re.findall(r'(https?://[^\s]+)', l142)
                if links_f142:
                    for lk in links_f142:
                        st.markdown(f"🔗 **Link ativo:** [{lk}]({lk})")
            
            # Executa se houver QUALQUER alteração
            if r142 and (r142 != d142["valor"] or l142 != d142["link"]):
                save_resp("1.4.2", r142, opc142[r142], l142)
                
                # Trava inteligente no 1.4.2 para barrar textos comuns no modal
                if links_f142 and l142.strip() != d142["link"].strip():
                    modal_aviso_link("1.4.2", [lk.strip() for lk in links_f142])
                else:
                    st.rerun()
                    
            bloco_comentarios("1.4.2", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

        # --- SEÇÃO 2: PLANEJAMENTO (PDTIC) ---
        st.divider()
        st.header("2.0 Planejamento de TIC")

        # =============================================================================
        # QUESITO 2.0
        # =============================================================================
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 2.0")
        st.write("**A prefeitura municipal possui um PDTIC – Plano Diretor de Tecnologia da Informação e Comunicação – vigente que estabeleça diretrizes e metas de atingimento no futuro?**")
        d20 = res_data.get("2.0", {"valor": None, "pontos": 0, "link": ""})
        opc20 = {"SIM, com metas acima de 02 anos – 40": 40, "SIM, com metas para até 02 anos – 30": 30, "NÃO POSSUI PDTIC – 00": 0}
        lista20 = list(opc20.keys())
        idx20 = lista20.index(d20["valor"]) if d20["valor"] in lista20 else None
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r20 = st.radio("Selecione 2.0:", lista20, index=idx20, key=f"q20_{ano_sel}")
        with col2:
            l20 = st.text_area("Link/Evidência (2.0):", value=d20.get("link", ""), key=f"l20_{ano_sel}", height=100)
            
            # Captura e renderiza o link ativo embaixo da caixa em tempo real (2.0)
            links_f20 = re.findall(r'(https?://[^\s]+)', l20)
            if links_f20:
                for lk in links_f20:
                    st.markdown(f"🔗 **Link ativo:** [{lk}]({lk})")
            
        # Executa se houver QUALQUER alteração (seja no rádio ou no texto de evidência)
        if r20 and (r20 != d20["valor"] or l20 != d20["link"]):
            save_resp("2.0", r20, opc20[r20], l20)
            
            # Trava inteligente contra textos comuns: Só abre se houver links REAIS no Regex e for link novo
            if links_f20 and l20.strip() != d20["link"].strip():
                modal_aviso_link("2.0", [lk.strip() for lk in links_f20])
            else:
                st.rerun()  # Texto puro ou mudança de botão: apenas atualiza a tela de forma limpa

        bloco_comentarios("2.0", res_data)
        st.markdown('</div>', unsafe_allow_html=True)
        
        if r20 and "NÃO POSSUI" not in r20:
            # =============================================================================
            # QUESITO 2.1
            # =============================================================================
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader("QUESITO 2.1")
            st.write("""**2.1 Informe a página eletrônica (link na internet) do PDTIC:**""")
            
            # Busca os dados já salvos no banco
            d21 = res_data.get("2.1", {"valor": "", "pontos": 0})
            valor_atual = d21["valor"].strip()
            
            # Define qual opção deve vir marcada por padrão com base no que está salvo
            if valor_atual == "XYZ" or valor_atual == "":
                indice_padrao = 1  # "Não disponível"
            else:
                indice_padrao = 0  # "Sim, disponível"
            
            # Interface com botões de opção claros
            opcao_disponivel = st.radio(
                "O PDTIC está disponível na internet?",
                options=["Sim, está disponível na internet", "Não está disponível na internet"],
                index=indice_padrao,
                key=f"q21_radio_{ano_sel}"
            )
            
            # Lógica dinâmica com base na escolha do usuário
            if opcao_disponivel == "Sim, está disponível na internet":
                # Se o valor antigo era XYZ ou vazio, limpa o campo pro usuário digitar o link novo
                valor_input = "" if valor_atual == "XYZ" else d21["valor"]
                
                v21 = st.text_input("Insira a página eletrônica (link URL):", value=valor_input, key=f"q21_input_{ano_sel}")
                
                # Fórmula de cálculo: se o link não for vazio (e não for XYZ), ganha 20 pontos
                pontos_finais = 20 if v21.strip() != "" and v21.strip().upper() != "XYZ" else 0
                valor_salvar = v21
            else:
                # Se não está disponível, exibe apenas a informação e força o XYZ nos bastidores
                st.warning('Conforme regra, será registrado o texto "XYZ" para documentos indisponíveis.')
                pontos_finais = 0
                valor_salvar = "XYZ"
            
            # Só dispara o salvamento se o usuário realmente alterou algo na tela
            if valor_salvar != d21["valor"] or pontos_finais != d21["pontos"]:
                save_resp("2.1", valor_salvar, pontos_finais, "")
                st.rerun()
                
            st.info(f"Pontuação atual neste quesito: {d21['pontos']} pontos")
            bloco_comentarios("2.1", res_data)
            st.markdown('</div>', unsafe_allow_html=True)


            # =============================================================================
            # QUESITO 2.2
            # =============================================================================
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader("QUESITO 2.2")
            st.write("**O plano de TIC vigente contempla:**")
            d22 = res_data.get("2.2", {"valor": "[]", "pontos": 0})
            contempla = {"Alocação de recursos orçamentários – 10": 10, "Alocação de recursos humanos – 10": 10, "Alocação de recursos materiais – 10": 10, "Estratégia de execução indireta (terceirização) – 10": 10}
            sel22 = []
            pts22 = 0
            for item, pts in contempla.items():
                if st.checkbox(item, value=item in d22["valor"], key=f"q22_{item}_{ano_sel}"):
                    sel22.append(item)
                    pts22 += pts
            if str(sel22) != d22["valor"]:
                save_resp("2.2", str(sel22), pts22, "")
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

            # =============================================================================
            # QUESITO 2.3
            # =============================================================================
            # Verifica se o PDTIC está disponível (com base na resposta do Quesito 2.1)
            d21_status = res_data.get("2.1", {"valor": ""})
            
            if d21_status["valor"] != "XYZ" and d21_status["valor"] != "":
                st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
                st.subheader("QUESITO 2.3")
                st.write("**Qual a data da última atualização do PDTIC? (Se não foi atualizado, informar a data da publicação)**")

                st.info("""
                **Regra de Pontuação:**
                * ✅ **Data de até 5 anos atrás:** 20 pontos.
                * ⚠️ **Data entre 5 e 10 anos atrás:** 10 pontos.
                * 🚫 **Data com mais de 10 anos:** 00 pontos.
                """)

                # 1. Busca os dados salvos para o 2.3 (Corrigido d24 para d23 para evitar conflitos de variáveis)
                d23 = res_data.get("2.3", {"valor": None, "pontos": 0, "link": ""})

                col_d23, col_j23 = st.columns([1, 2])

                with col_d23:
                    try:
                        # Tenta carregar a data salva do quesito 2.3 ou joga a data de hoje como padrão
                        dt_i = datetime.strptime(d23["valor"], '%Y-%m-%d').date() if d23["valor"] else date.today()
                    except:
                        dt_i = date.today()

                    data_sel = st.date_input(
                        "Selecione a data:",
                        value=dt_i,
                        key=f"dt23_{ano_sel}",
                        format="DD/MM/YYYY"
                    )

                # 2. Lógica de cálculo baseada na idade do documento
                if data_sel:
                    ano_documento = data_sel.year
                    
                    # Converte ano_sel para inteiro para garantir a matemática clara
                    ano_contexto = int(ano_sel) 
                    idade_anos = ano_contexto - ano_documento

                    # Regra de cálculo do quesito
                    if idade_anos <= 5:
                        pontos_23 = 20
                    elif 5 < idade_anos <= 10:
                        pontos_23 = 10
                    else:
                        pontos_23 = 0

                    # Garante que não calcule datas futuras de forma errônea
                    if idade_anos < 0:
                        pontos_23 = 20  # Se for o próprio ano ou futuro, entra na faixa mais recente

                    # 3. Salva se houver mudanças
                    data_str = data_sel.strftime('%Y-%m-%d')
                    if data_str != d23["valor"] or pontos_23 != d23["pontos"]:
                        save_resp("2.3", data_str, pontos_23, "")
                        st.rerun()

                with col_j23:
                    # Mensagem de feedback dinâmica para o usuário ver o cálculo
                    if d23["valor"]:
                        st.write(f"**Idade calculada do documento:** {idade_anos} ano(s) em relação a {ano_sel}.")
                    st.info(f"Pontuação atual neste quesito: {d23['pontos']} pontos")

                bloco_comentarios("2.3", res_data)
                st.markdown('</div>', unsafe_allow_html=True)

        # --- SEÇÃO 3: SEGURANÇA ---
        st.divider()
        st.header("3.0 Segurança da Informação")
                    
        # =============================================================================
        # QUESITO 3.0
        # =============================================================================
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 3.0")
        st.write("**A Prefeitura dispõe de Política de Segurança da informação formalmente instituída e de cumprimento obrigatório?**")
        d30 = res_data.get("3.0", {"valor": None, "pontos": 0, "link": ""})
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r30 = st.radio("Selecione 3.0:", ["Sim – 50", "Não – 00"], index=(0 if d30["valor"] and "Sim" in d30["valor"] else (1 if d30["valor"] else None)), key=f"q30_{ano_sel}")
        with col2:
            l30 = st.text_area("Link/Evidência (3.0):", value=d30.get("link", ""), key=f"l30_{ano_sel}", height=100)
            
            # Captura e renderiza os links ativos em tempo real (3.0)
            links_f30 = re.findall(r'(https?://[^\s]+)', l30)
            if links_f30:
                for lk in links_f30:
                    st.markdown(f"🔗 **Link ativo:** [{lk}]({lk})")
            
        if r30 and (r30 != d30["valor"] or l30 != d30["link"]):
            save_resp("3.0", r30, 50 if "Sim" in r30 else 0, l30)
            
            # Só dispara se houver URLs reais identificadas e o link for alterado
            if links_f30 and l30.strip() != d30["link"].strip():
                modal_aviso_link("3.0", [lk.strip() for lk in links_f30])
            else:
                st.rerun()
                
        bloco_comentarios("3.0", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # =============================================================================
        # QUESITO 3.1
        # =============================================================================
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 3.1")
        st.write("**A Prefeitura estabelece procedimentos e responsabilidades quanto ao uso da tecnologia da informação pelos funcionários municipais, conhecido como Termo de Responsabilidade/Compromisso?**")
        d31 = res_data.get("3.1", {"valor": None, "pontos": 0, "link": ""})
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r31 = st.radio("Selecione 3.1:", ["Sim – 20", "Não – 00"], index=(0 if d31["valor"] and "Sim" in d31["valor"] else (1 if d31["valor"] else None)), key=f"q31_{ano_sel}")
        with col2:
            l31 = st.text_area("Link/Evidência (3.1):", value=d31.get("link", ""), key=f"l31_{ano_sel}", height=100)
            
            # Captura e renderiza os links ativos em tempo real (3.1)
            links_f31 = re.findall(r'(https?://[^\s]+)', l31)
            if links_f31:
                for lk in links_f31:
                    st.markdown(f"🔗 **Link ativo:** [{lk}]({lk})")
            
        if r31 and (r31 != d31["valor"] or l31 != d31["link"]):
            save_resp("3.1", r31, 20 if "Sim" in r31 else 0, l31)
            
            if links_f31 and l31.strip() != d31["link"].strip():
                modal_aviso_link("3.1", [lk.strip() for lk in links_f31])
            else:
                st.rerun()
            
        bloco_comentarios("3.1", res_data, sufixo="principal")
        
        # Sub-bloco condicional do 3.1
        if r31 and "Sim" in r31:
            st.markdown('<div style="margin-top: 20px; padding-left: 15px; border-left: 3px solid #ccc;">', unsafe_allow_html=True)
            st.subheader("QUESITO 3.1.1")
            st.write("**O Termo de Responsabilidade/Compromisso dispõe sobre o uso da assinatura eletrônica pelos funcionários municipais?**")
            d311 = res_data.get("3.1.1", {"valor": None, "pontos": 0, "link": ""})
            
            col1_sub, col2_sub = st.columns([1, 2])
            with col1_sub:
                r311 = st.radio("Selecione 3.1.1:", ["Sim – 40", "Não – 00"], index=(0 if d311["valor"] and "Sim" in d311["valor"] else (1 if d311["valor"] else None)), key=f"q311_{ano_sel}")
            with col2_sub:
                l311 = st.text_area("Link/Evidência (3.1.1):", value=d311.get("link", ""), key=f"l311_{ano_sel}", height=100)
                
                links_f311 = re.findall(r'(https?://[^\s]+)', l311)
                if links_f311:
                    for lk in links_f311:
                        st.markdown(f"🔗 **Link ativo:** [{lk}]({lk})")
                        
            if r311 and (r311 != d311["valor"] or l311 != d311["link"]):
                save_resp("3.1.1", r311, 40 if "Sim" in r311 else 0, l311)
                
                if links_f311 and l311.strip() != d311["link"].strip():
                    modal_aviso_link("3.1.1", [lk.strip() for lk in links_f311])
                else:
                    st.rerun()
            
            if r311 and "Sim" in r311:
                st.write("**3.1.1.1 Tipo de assinatura eletrônica utilizada:**")
                d3111 = res_data.get("3.1.1.1", {"valor": "[]", "pontos": 0})
                tipos = {"Assinatura eletrônica de uso gratuito – 10": 10, "Assinatura eletrônica onerosa – 00": 0}
                sel3111 = []
                pts3111 = 0
                for t, p in tipos.items():
                    if st.checkbox(t, value=t in d3111["valor"], key=f"q3111_{t}_{ano_sel}"):
                        sel3111.append(t)
                        pts3111 += p
                if str(sel3111) != d3111["valor"]:
                    save_resp("3.1.1.1", str(sel3111), pts3111, "")
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
                    
        bloco_comentarios("3.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # =============================================================================
        # QUESITO 3.2
        # =============================================================================
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 3.2")
        st.write("**Os riscos de TIC são identificados de acordo com as normas brasileiras da família ISO/IEC 27000?**")
        d32 = res_data.get("3.2", {"valor": None, "link": ""})
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r32 = st.radio("Selecione 3.2:", ["Sim", "Não"], index=(0 if d32["valor"] == "Sim" else (1 if d32["valor"] == "Não" else None)), key=f"q32_{ano_sel}")
        with col2:
            l32 = st.text_area("Link/Evidência (3.2):", value=d32.get("link", ""), key=f"l32_{ano_sel}", height=100)
            
            # Captura e renderiza os links ativos em tempo real (3.2)
            links_f32 = re.findall(r'(https?://[^\s]+)', l32)
            if links_f32:
                for lk in links_f32:
                    st.markdown(f"🔗 **Link ativo:** [{lk}]({lk})")
                    
        if r32 and (r32 != d32["valor"] or l32 != d32["link"]):
            save_resp("3.2", r32, 0, l32)
            
            if links_f32 and l32.strip() != d32["link"].strip():
                modal_aviso_link("3.2", [lk.strip() for lk in links_f32])
            else:
                st.rerun()
                
        if r32 == "Sim":
            st.markdown('<div style="margin-top: 15px; padding-left: 15px; border-left: 3px solid #ccc;">', unsafe_allow_html=True)
            st.write("**3.2.1 As secretarias setoriais realizaram a fiscalização das áreas de risco? Informe quais normas da família ISO/IEC 27000 são utilizadas nos processos de segurança no uso de Tecnologia da Informação e Comunicação (TIC):**")
            d321 = res_data.get("3.2.1", {"valor": "[]", "pontos": 0})
            normas = {"ISO/IEC 27000 – 1,5": 1.5, "ISO/IEC 27001 – 1,5": 1.5, "ISO/IEC 27002 – 1,5": 1.5, "ISO/IEC 27003 – 1,5": 1.5, "ISO/IEC 27004 – 02": 2, "ISO/IEC 27005 – 02": 2}
            sel321 = []
            pts321 = 0
            for n, p in normas.items():
                if st.checkbox(n, value=n in d321["valor"], key=f"q321_{n}_{ano_sel}"):
                    sel321.append(n)
                    pts321 += p
            if str(sel321) != d321["valor"]:
                save_resp("3.2.1", str(sel321), float(pts321), "")
                st.rerun()
            bloco_comentarios("3.2.1", res_data)
            st.markdown('</div>', unsafe_allow_html=True)
            
        bloco_comentarios("3.2", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # =============================================================================
        # QUESITO 3.3
        # =============================================================================
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 3.3")
        st.write("**Os riscos de TIC são identificados de acordo com as normas da ABNT NBR ISO/IEC 31000? Se tiver apenas antivírus e firewall, a resposta é NÃO.**")
        d33 = res_data.get("3.3", {"valor": None, "pontos": 0, "link": ""})
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r33 = st.radio("Selecione 3.3:", ["Sim – 30", "Não – 00"], index=(0 if d33["valor"] and "Sim" in d33["valor"] else (1 if d33["valor"] else None)), key=f"q33_{ano_sel}")
        with col2:
            l33 = st.text_area("Link/Evidência (3.3):", value=d33.get("link", ""), key=f"l33_{ano_sel}", height=100)
            
            # Captura e renderiza os links ativos em tempo real (3.3)
            links_f33 = re.findall(r'(https?://[^\s]+)', l33)
            if links_f33:
                for lk in links_f33:
                    st.markdown(f"🔗 **Link ativo:** [{lk}]({lk})")
                    
        if r33 and (r33 != d33["valor"] or l33 != d33["link"]):
            save_resp("3.3", r33, 30 if "Sim" in r33 else 0, l33)
            
            if links_f33 and l33.strip() != d33["link"].strip():
                modal_aviso_link("3.3", [lk.strip() for lk in links_f33])
            else:
                st.rerun()
                
        bloco_comentarios("3.3", res_data)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # =============================================================================
        # QUESITO 3.4
        # =============================================================================
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 3.4")
        st.write("**A Prefeitura possui um Plano de Continuidade dos Serviços de Tecnologia da Informação e Comunicação (TIC)? Recomendamos anexar o Plano de continuidade de serviços de TI, conforme Instrução de Preenchimento (IP)**")
        d34 = res_data.get("3.4", {"valor": None, "pontos": 0, "link": ""})
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r34 = st.radio("Selecione 3.4:", ["Sim – 30", "Não – 00"], index=(0 if d34["valor"] and "Sim" in d34["valor"] else (1 if d34["valor"] else None)), key=f"q34_{ano_sel}")
        with col2:
            l34 = st.text_area("Link/Evidência (3.4):", value=d34.get("link", ""), key=f"l34_{ano_sel}", height=100)
            
            # Captura e renderiza os links ativos em tempo real (3.4)
            links_f34 = re.findall(r'(https?://[^\s]+)', l34)
            if links_f34:
                for lk in links_f34:
                    st.markdown(f"🔗 **Link ativo:** [{lk}]({lk})")
                    
        if r34 and (r34 != d34["valor"] or l34 != d34["link"]):
            save_resp("3.4", r34, 30 if "Sim" in r34 else 0, l34)
            
            if links_f34 and l34.strip() != d34["link"].strip():
                modal_aviso_link("3.4", [lk.strip() for lk in links_f34])
            else:
                st.rerun()
                
        bloco_comentarios("3.4", res_data)
        st.markdown('</div>', unsafe_allow_html=True)


        # =============================================================================
        # QUESITO 3.5 Política de Backup
        # =============================================================================
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 3.5")
        st.write("**A Prefeitura dispõe de política de cópias de segurança (backup) formalmente instituída como norma de cumprimento obrigatório?**")
        d35 = res_data.get("3.5", {"valor": None, "pontos": 0, "link": ""})
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r35 = st.radio("Selecione 3.5:", ["Sim – 30", "Não – 00"], index=(0 if d35["valor"] and "Sim" in d35["valor"] else (1 if d35["valor"] else None)), key=f"q35_{ano_sel}")
        with col2:
            l35 = st.text_area("Link/Evidência (3.5):", value=d35.get("link", ""), key=f"l35_{ano_sel}", height=100)
            
            # Captura e renderiza os links ativos em tempo real (3.5)
            links_f35 = re.findall(r'(https?://[^\s]+)', l35)
            if links_f35:
                for lk in links_f35:
                    st.markdown(f"🔗 **Link ativo:** [{lk}]({lk})")
                    
        if r35 and (r35 != d35["valor"] or l35 != d35["link"]):
            save_resp("3.5", r35, 30 if "Sim" in r35 else 0, l35)
            
            # Trava do modal: só abre se houver link real e modificado
            if links_f35 and l35.strip() != d35["link"].strip():
                modal_aviso_link("3.5", [lk.strip() for lk in links_f35])
            else:
                st.rerun()
                
        bloco_comentarios("3.5", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # =============================================================================
        # QUESITO 3.6 Inventário
        # =============================================================================
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 3.6")
        st.write("**A Prefeitura possui inventário atualizado dos ativos de TIC? Ativos de TIC: switches, roteadores, servidores, firewalls, Sistemas operacionais, carga de processamento, backup, utilização de storages, etc.**")
        d36 = res_data.get("3.6", {"valor": None, "pontos": 0, "link": ""})
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r36 = st.radio("Selecione 3.6:", ["Sim – 20", "Não – 00"], index=(0 if d36["valor"] and "Sim" in d36["valor"] else (1 if d36["valor"] else None)), key=f"q36_{ano_sel}")
        with col2:
            l36 = st.text_area("Link/Evidência (3.6):", value=d36.get("link", ""), key=f"l36_{ano_sel}", height=100)
            
            # Captura e renderiza os links ativos em tempo real (3.6)
            links_f36 = re.findall(r'(https?://[^\s]+)', l36)
            if links_f36:
                for lk in links_f36:
                    st.markdown(f"🔗 **Link ativo:** [{lk}]({lk})")
                    
        if r36 and (r36 != d36["valor"] or l36 != d36["link"]):
            save_resp("3.6", r36, 20 if "Sim" in r36 else 0, l36)
            
            if links_f36 and l36.strip() != d36["link"].strip():
                modal_aviso_link("3.6", [lk.strip() for lk in links_f36])
            else:
                st.rerun()
        
        # Sub-bloco condicional do 3.6
        if r36 and "Sim" in r36:
            st.markdown('<div style="margin-top: 15px; padding-left: 15px; border-left: 3px solid #ccc;">', unsafe_allow_html=True)
            st.write("**3.6.1 Como é composta a base de ativos:**")
            d361 = res_data.get("3.6.1", {"valor": "[]"})
            base = ["Ativos de informação", "Ativos de software", "Ativos físicos", "Serviços", "Pessoas e suas qualificações"]
            sel361 = []
            for b in base:
                if st.checkbox(b, value=b in d361["valor"], key=f"q361_{b}_{ano_sel}"):
                    sel361.append(b)
            if str(sel361) != d361["valor"]:
                save_resp("3.6.1", str(sel361), 0, "")
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
            
        bloco_comentarios("3.6", res_data)
        st.markdown('</div>', unsafe_allow_html=True)
           
        # --- SEÇÃO 4: LAI ---
        st.divider()
        st.header("4.0 Transparência e LAI")
        
        # =============================================================================
        # QUESITO 4.0
        # =============================================================================
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 4.0")
        st.write("**O município regulamentou a Lei de Acesso à Informação?**")
        d40 = res_data.get("4.0", {"valor": None, "pontos": 0, "link": ""})
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r40 = st.radio("Selecione 4.0:", ["Sim – 40", "Não – 00"], index=(0 if d40["valor"] and "Sim" in d40["valor"] else (1 if d40["valor"] else None)), key=f"q40_{ano_sel}")
        with col2:
            l40 = st.text_area("Link/Evidência (4.0):", value=d40.get("link", ""), key=f"l40_{ano_sel}", height=100)
            
            # Captura e renderiza os links ativos em tempo real (4.0)
            links_f40 = re.findall(r'(https?://[^\s]+)', l40)
            if links_f40:
                for lk in links_f40:
                    st.markdown(f"🔗 **Link ativo:** [{lk}]({lk})")
                    
        if r40 and (r40 != d40["valor"] or l40 != d40["link"]):
            save_resp("4.0", r40, 40 if "Sim" in r40 else 0, l40)
            
            if links_f40 and l40.strip() != d40["link"].strip():
                modal_aviso_link("4.0", [lk.strip() for lk in links_f40])
            else:
                st.rerun()
        
        # Sub-bloco dependente da LAI (4.1 e 4.2)
        if r40 and "Sim" in r40:
            st.markdown('<div style="margin-top: 20px; padding-left: 15px; border-left: 3px solid #ccc;">', unsafe_allow_html=True)
            
            # 4.1
            st.write("**4.1 Informe o Instrumento normativo, Número e Data:**")
            d41 = res_data.get("4.1", {"valor": ""})
            v41 = st.text_input("Informe:", value=d41["valor"], key=f"q41_{ano_sel}")
            if v41 != d41["valor"]:
                save_resp("4.1", v41, 0, "")
                st.rerun()
            bloco_comentarios("4.1", res_data)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # 4.2
            st.write("**4.2 Página eletrônica (link) do instrumento (XYZ se não disponível):**")
            d42 = res_data.get("4.2", {"valor": ""})
            v42 = st.text_input("Link URL:", value=d42["valor"], key=f"q42_{ano_sel}")
            if v42 != d42["valor"]:
                save_resp("4.2", v42, 0, "")
                st.rerun()
            bloco_comentarios("4.2", res_data)
            
            st.markdown('</div>', unsafe_allow_html=True)
            
        bloco_comentarios("4.0", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # --- SEÇÃO 5: GOVERNO DIGITAL ---
        st.divider()
        st.header("5.0 Governo Digital")
        
        # -------------------------------------------------------------------------
        # QUESITO 5.0, 5.1 e 5.2 - GOVERNO DIGITAL
        # -------------------------------------------------------------------------
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 5.0")
        st.write("**O município regulamentou a Lei sobre Eficiência Pública (Governo Digital)?**")
        st.caption("Lei Federal nº 14.129, de 29 de Março de 2021")
        
        # Carrega dados do 5.0
        d50 = res_data.get("5.0", {"valor": None, "link": ""})
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r50 = st.radio(
                "Selecione 5.0:", 
                ["Sim", "Não"], 
                index=(0 if d50["valor"] == "Sim" else (1 if d50["valor"] == "Não" else None)), 
                key=f"q50_{ano_sel}"
            )
        with col2:
            l50 = st.text_area("Link/Evidência (5.0):", value=d50.get("link", ""), key=f"l50_{ano_sel}", height=100)
            
            # Captura e renderiza os links ativos em tempo real (5.0)
            links_f50 = re.findall(r'(https?://[^\s]+)', l50)
            if links_f50:
                for lk in links_f50:
                    st.markdown(f"🔗 **Link ativo:** [{lk}]({lk})")
            
        # Salva alteração do 5.0
        if r50 and (r50 != d50["valor"] or l50 != d50["link"]):
            pontos_50 = 10.0 if r50 == "Sim" else 0.0
            save_resp("5.0", r50, pontos_50, l50)
            
            # Trava do modal: só dispara se houver links válidos modificados
            if links_f50 and l50.strip() != d50["link"].strip():
                modal_aviso_link("5.0", [lk.strip() for lk in links_f50])
            else:
                st.rerun()

        bloco_comentarios("5.0", res_data, sufixo="principal")
        
        # Se a resposta for "Sim", renderiza os quesitos dependentes 5.1 e 5.2 dentro do mesmo card
        if r50 == "Sim":
            st.markdown('<div style="margin-top: 15px; padding-left: 15px; border-left: 3px solid #ccc;">', unsafe_allow_html=True)
            
            # --- QUESITO 5.1 ---
            st.write("**5.1 Informe o Instrumento normativo, Número e Data da publicação:**")
            d51 = res_data.get("5.1", {"valor": ""})
            v51 = st.text_input("Informe:", value=d51["valor"], key=f"q51_{ano_sel}")
            
            if v51 != d51["valor"]:
                save_resp("5.1", v51, 0.0, "")
                st.rerun()

            bloco_comentarios("5.1", res_data)
            
            st.markdown("<hr style='margin: 15px 0; border: 0; border-top: 1px dashed #ccc;'>", unsafe_allow_html=True)

            # --- QUESITO 5.2 ---
            st.write("**5.2 Página eletrônica (link na internet) do instrumento normativo:**")
            st.caption("Se não estiver disponível na internet, inserir no campo de resposta o texto XYZ")
            d52 = res_data.get("5.2", {"valor": ""})
            v52 = st.text_input("URL:", value=d52["valor"], key=f"q52_{ano_sel}")
            
            if v52 != d52["valor"]:
                save_resp("5.2", v52, 0.0, "")
                st.rerun()
            
            bloco_comentarios("5.2", res_data)
            st.markdown('</div>', unsafe_allow_html=True)
            
        bloco_comentarios("5.0", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # -------------------------------------------------------------------------
        # QUESITO 6.0 e Subitens - SITE INTERNET E ACESSIBILIDADE
        # -------------------------------------------------------------------------
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 6.0")
        st.write("**A prefeitura mantém site na Internet com informações atualizadas?**")
        d60 = res_data.get("6.0", {"valor": None, "pontos": 0, "link": ""})
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r60 = st.radio("Selecione 6.0:", ["Sim – 20", "Não – 00"], index=(0 if d60["valor"] and "Sim" in d60["valor"] else (1 if d60["valor"] else None)), key=f"q60_{ano_sel}")
        with col2:
            l60 = st.text_area("Link/Evidência (6.0):", value=d60.get("link", ""), key=f"l60_{ano_sel}", height=100)
            
            # Captura e renderiza os links ativos em tempo real (6.0)
            links_f60 = re.findall(r'(https?://[^\s]+)', l60)
            if links_f60:
                for lk in links_f60:
                    st.markdown(f"🔗 **Link ativo:** [{lk}]({lk})")
                    
        if r60 and (r60 != d60["valor"] or l60 != d60["link"]):
            save_resp("6.0", r60, 20 if "Sim" in r60 else 0, l60)
            
            if links_f60 and l60.strip() != d60["link"].strip():
                modal_aviso_link("6.0", [lk.strip() for lk in links_f60])
            else:
                st.rerun()
        
        bloco_comentarios("6.0", res_data, sufixo="principal")

        # Renderização hierárquica e condicional dos subitens do quesito 6
        if r60 and "Sim" in r60:
            st.markdown('<div style="margin-top: 20px; padding-left: 15px; border-left: 3px solid #ccc;">', unsafe_allow_html=True)
            
            # 6.1 Pesquisa
            st.write("**6.1 O site eletrônico da prefeitura continha ferramenta de pesquisa/busca interna de conteúdo? Não considerar a opção de busca do próprio browser (Ctrl + F)**")
            d61 = res_data.get("6.1", {"valor": None, "pontos": 0})
            opc61 = {"Sim, para todo o conteúdo – 20": 20, "Sim, para a maior parte do conteúdo – 10": 10, "Sim, para a menor parte do conteúdo – 05": 5, "Não – 00": 0}
            lista61 = list(opc61.keys())
            idx61 = lista61.index(d61["valor"]) if d61["valor"] in lista61 else None
            r61 = st.radio("Selecione 6.1:", lista61, index=idx61, key=f"q61_{ano_sel}")
            if r61 and r61 != d61["valor"]:
                save_resp("6.1", r61, opc61[r61], "")
                st.rerun()
            bloco_comentarios("6.1", res_data)

            st.markdown("<hr style='margin: 15px 0; border: 0; border-top: 1px dashed #ccc;'>", unsafe_allow_html=True)

            # 6.2 Formatos Abertos
            st.write("**6.2 O site possibilita o download de dados/informações em formatos abertos e não proprietários? Exemplos de formatos abertos e não proprietários: JSON, XML, CSV, ODS, RDF, etc.**")
            d62 = res_data.get("6.2", {"valor": None, "pontos": 0})
            opc62 = {"Possibilita para todos os relatórios – 20": 20, "Possibilita para a maior parte dos relatórios – 10": 10, "Possibilita para a menor parte dos relatórios – 05": 5, "Não – 00": 0}
            lista62 = list(opc62.keys())
            idx62 = lista62.index(d62["valor"]) if d62["valor"] in lista62 else None
            r62 = st.radio("Selecione 6.2:", lista62, index=idx62, key=f"q62_{ano_sel}")
            if r62 and r62 != d62["valor"]:
                save_resp("6.2", r62, opc62[r62], "")
                st.rerun()
            bloco_comentarios("6.2", res_data)

            st.markdown("<hr style='margin: 15px 0; border: 0; border-top: 1px dashed #ccc;'>", unsafe_allow_html=True)

            # 6.3 FAQ
            st.write("**6.3 O site disponibiliza as respostas a perguntas mais frequentes da sociedade?**")
            d63 = res_data.get("6.3", {"valor": None, "pontos": 0})
            r63 = st.radio("Selecione 6.3:", ["Sim – 10", "Não – 00"], index=(0 if d63["valor"] and "Sim" in d63["valor"] else (1 if d63["valor"] else None)), key=f"q63_{ano_sel}")
            if r63 and r63 != d63["valor"]:
                save_resp("6.3", r63, 10 if "Sim" in r63 else 0, "")
                st.rerun()
            bloco_comentarios("6.3", res_data)
 
            st.markdown("<hr style='margin: 15px 0; border: 0; border-top: 1px dashed #ccc;'>", unsafe_allow_html=True)

            # 6.4 Acessibilidade
            st.write("**6.4 O site disponibiliza acessibilidade de conteúdo para pessoas com deficiência?**")
            d64 = res_data.get("6.4", {"valor": None, "pontos": 0})
            opc64 = {"Sim, para todo o conteúdo – 30": 30, "Sim, para a maior parte – 15": 15, "Sim, para a menor parte – 05": 5, "Não – 00": 0}
            lista64 = list(opc64.keys())
            idx64 = lista64.index(d64["valor"]) if d64["valor"] in lista64 else None
            r64 = st.radio("Selecione 6.4:", lista64, index=idx64, key=f"q64_{ano_sel}")
            if r64 and r64 != d64["valor"]:
                save_resp("6.4", r64, opc64[r64], "")
                st.rerun()
            bloco_comentarios("6.4", res_data)
            
            st.markdown('</div>', unsafe_allow_html=True)
            
        bloco_comentarios("6.0", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # --- SEÇÃO 7: e-SIC ---
        st.divider()
        st.header("7.0 Serviço de Informação (e-SIC)")
        
       # -------------------------------------------------------------------------
        # QUESITO 7.0 e Subitens - SERVIÇO DE INFORMAÇÃO AO CIDADÃO (e-SIC)
        # -------------------------------------------------------------------------
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 7.0")
        st.write("**A Prefeitura disponibiliza no site o Serviço de Informação ao Cidadão/e-SIC (LF nº 12.527/11)?**")
        
        d70 = res_data.get("7.0", {"valor": None, "pontos": 0, "link": ""})
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r70 = st.radio(
                "Selecione 7.0:", 
                ["Sim – 25", "Não – 00"], 
                index=(0 if d70["valor"] and "Sim" in d70["valor"] else (1 if d70["valor"] else None)), 
                key=f"q70_{ano_sel}"
            )
        with col2:
            l70 = st.text_area("Link/Evidência (7.0):", value=d70.get("link", ""), key=f"l70_{ano_sel}", height=100)
            
            # Captura e renderiza links ativos em tempo real (7.0)
            links_f70 = re.findall(r'(https?://[^\s]+)', l70)
            if links_f70:
                for lk in links_f70:
                    st.markdown(f"🔗 **Link ativo:** [{lk}]({lk})")
                    
        if r70 and (r70 != d70["valor"] or l70 != d70["link"]):
            save_resp("7.0", r70, 25 if "Sim" in r70 else 0, l70)
            
            if links_f70 and l70.strip() != d70["link"].strip():
                modal_aviso_link("7.0", [lk.strip() for lk in links_f70])
            else:
                st.rerun()
        
        bloco_comentarios("7.0", res_data, sufixo="principal")

        # Exibição condicional dos subitens filhos dentro do card principal
        if r70 and "Sim" in r70:
            st.markdown('<div style="margin-top: 20px; padding-left: 15px; border-left: 3px solid #ccc;">', unsafe_allow_html=True)
            
            # --- QUESITO 7.1 ---
            st.write("**7.1 A solicitação por meio do e-SIC é simplificada (sem a exigência de itens de identificação do requerente e demais dados desnecessários à solicitação)?**")
            d71 = res_data.get("7.1", {"valor": None, "pontos": 0})
            r71 = st.radio("Selecione 7.1:", ["Sim – 10", "Não – 00"], index=(0 if d71["valor"] and "Sim" in d71["valor"] else (1 if d71["valor"] else None)), key=f"q71_{ano_sel}")
            if r71 and r71 != d71["valor"]:
                save_resp("7.1", r71, 10 if "Sim" in r71 else 0, "")
                st.rerun()
            bloco_comentarios("7.1", res_data)

            st.markdown("<hr style='margin: 15px 0; border: 0; border-top: 1px dashed #ccc;'>", unsafe_allow_html=True)

            # --- QUESITO 7.2 ---
            st.write("**7.2 O Serviço de Informação ao Cidadão/e-SIC apresentou possibilidade de acompanhamento da solicitação?**")
            d72 = res_data.get("7.2", {"valor": None, "pontos": 0})
            r72 = st.radio("Selecione 7.2:", ["Sim – 10", "Não – 00"], index=(0 if d72["valor"] and "Sim" in d72["valor"] else (1 if d72["valor"] else None)), key=f"q72_{ano_sel}")
            if r72 and r72 != d72["valor"]:
                save_resp("7.2", r72, 10 if "Sim" in r72 else 0, "")
                st.rerun()
            bloco_comentarios("7.2", res_data)

            st.markdown("<hr style='margin: 15px 0; border: 0; border-top: 1px dashed #ccc;'>", unsafe_allow_html=True)

            # --- QUESITO 7.3 ---
            st.write("**7.3 Há necessidade de ser informado os motivos para a solicitação de informações de interesse público?**")
            d73 = res_data.get("7.3", {"valor": None, "pontos": 0})
            r73 = st.radio("Selecione 7.3:", ["Sim – 00", "Não – 05"], index=(0 if d73["valor"] and "Sim" in d73["valor"] else (1 if d73["valor"] else None)), key=f"q73_{ano_sel}")
            if r73 and r73 != d73["valor"]:
                save_resp("7.3", r73, 5 if "Não" in r73 else 0, "")
                st.rerun()
            bloco_comentarios("7.3", res_data)
            
            st.markdown('</div>', unsafe_allow_html=True)
            
        bloco_comentarios("7.0", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # -------------------------------------------------------------------------
        # QUESITO 8.0 - SOFTWARES DE GESTÃO DE PROCESSOS
        # -------------------------------------------------------------------------
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 8.0")
        st.write(
            "**A Prefeitura possui programas de computador (softwares) para gestão de processos?** "
            "<br><small>Exemplos: Sistema de contabilidade, sistema de lançamento de tributos, "
            "sistema de dívida ativa. Software próprio ou terceirizado.</small>", 
            unsafe_allow_html=True
        )
        
        d80 = res_data.get("8.0", {"valor": None, "pontos": 0, "link": ""})
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r80 = st.radio(
                "Selecione 8.0:", 
                ["Sim – 40", "Não – 00"], 
                index=(0 if d80["valor"] and "Sim" in d80["valor"] else (1 if d80["valor"] else None)), 
                key=f"q80_{ano_sel}"
            )
        with col2:
            l80 = st.text_area("Link/Evidência (8.0):", value=d80.get("link", ""), key=f"l80_{ano_sel}", height=100)
            
            # Captura e renderiza links ativos em tempo real (8.0)
            links_f80 = re.findall(r'(https?://[^\s]+)', l80)
            if links_f80:
                for lk in links_f80:
                    st.markdown(f"🔗 **Link ativo:** [{lk}]({lk})")
        
        if r80 and (r80 != d80["valor"] or l80 != d80["link"]):
            save_resp("8.0", r80, 40 if "Sim" in r80 else 0, l80)
            
            if links_f80 and l80.strip() != d80["link"].strip():
                modal_aviso_link("8.0", [lk.strip() for lk in links_f80])
            else:
                st.rerun()
                
        bloco_comentarios("8.0", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # -------------------------------------------------------------------------
        # QUESITO 8.1 - PROCESSOS / SETORES ENGLOBADOS
        # -------------------------------------------------------------------------
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 8.1")
        st.write("**Os programas de computador (softwares) englobam quais processos/setores?**")
        
        d81 = res_data.get("8.1", {"valor": "[]"})
        opcoes_setores = [
            "Contabilidade", "Gestão de tributos (arrecadação)", "Dívida Ativa", 
            "Precatórios", "Gestão patrimonial (bens e equipamentos)", 
            "Gestão de negócios (Business Intelligence)", "Planejamento", 
            "Recursos humanos / Departamento pessoal", "Almoxarifado", 
            "Controle de frotas", "Controle Interno", "Saúde", 
            "Ensino (education)", "Compras, licitações e contratos", 
            "Certidões e alvarás", "Saneamento", "Cemitérios"
        ]
        
        sel81 = []
        col_setor1, col_setor2 = st.columns(2)
        for i, setor in enumerate(opcoes_setores):
            with col_setor1 if i % 2 == 0 else col_setor2:
                if st.checkbox(setor, value=setor in d81["valor"], key=f"q81_{setor}_{ano_sel}"):
                    sel81.append(setor)
                    
        if str(sel81) != d81["valor"]:
            save_resp("8.1", str(sel81), 0, "")
            st.rerun()
            
        bloco_comentarios("8.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # -------------------------------------------------------------------------
        # QUESITO 8.2 - SISTEMAS INTEGRADOS À CONTABILIDADE
        # -------------------------------------------------------------------------
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 8.2")
        st.write("**Informe quais systems encontram-se integrados ao Sistema de Contabilidade do município:**")
        
        d82 = res_data.get("8.2", {"valor": "[]"})
        opcoes_integracao = [
            "Gestão de tributos (arrecadação)", "Dívida Ativa", "Precatórios", 
            "Gestão patrimonial (bens e equipamentos)", "Gestão de negócios (Business Intelligence)", 
            "Planejamento", "Recursos humanos / Departamento pessoal", "Almoxarifado", 
            "Controle de frotas", "Controle Interno", "Saúde", 
            "Ensino (educação)", "Compras, licitações e contratos", 
            "Certidões e alvarás", "Saneamento", "Cemitérios"
        ]
        
        sel82 = []
        col_int1, col_int2 = st.columns(2)
        for i, sistema in enumerate(opcoes_integracao):
            with col_int1 if i % 2 == 0 else col_int2:
                if st.checkbox(sistema, value=sistema in d82["valor"], key=f"q82_{sistema}_{ano_sel}"):
                    sel82.append(sistema)
                    
        if str(sel82) != d82["valor"]:
            save_resp("8.2", str(sel82), 0, "")
            st.rerun()
            
        bloco_comentarios("8.2", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # -------------------------------------------------------------------------
        # QUESITO 8.2.1 - INTEGRAÇÃO DÍVIDA ATIVA
        # -------------------------------------------------------------------------
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 8.2.1")
        st.write("**Informe o nível de integração entre o Sistema da Dívida Ativa e o de Contabilidade:**")
        
        d821 = res_data.get("8.2.1", {"valor": None, "pontos": 0})
        opcoes_821 = [
            "Totalmente integrado (Inscrição / Atualização e Baixa) – 50", 
            "Somente as Inscrições / Atualizações estão integrados – 10", 
            "Somente as Baixas estão integradas – 10"
        ]
        
        idx_821 = None
        if d821["valor"]:
            if "Totalmente" in d821["valor"]:
                idx_821 = 0
            elif "Inscrições" in d821["valor"]:
                idx_821 = 1
            elif "Baixas" in d821["valor"]:
                idx_821 = 2

        r821 = st.radio("Selecione 8.2.1:", opcoes_821, index=idx_821, key=f"q821_{ano_sel}")
        
        if r821 and r821 != d821["valor"]:
            if "Totalmente" in r821:
                pts_821 = 50
            elif "Inscrições" in r821 or "Baixas" in r821:
                pts_821 = 10
            else:
                pts_821 = 0
                
            save_resp("8.2.1", r821, pts_821, "")
            st.rerun()
            
        bloco_comentarios("8.2.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # -------------------------------------------------------------------------
        # QUESITO 8.2.2 - INTEGRAÇÃO PRECATÓRIOS
        # -------------------------------------------------------------------------
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 8.2.2")
        st.write("**Informe o nível de integração entre o Sistema de Precatórios e o de Contabilidade:**")
        
        d822 = res_data.get("8.2.2", {"valor": None, "pontos": 0})
        opcoes_822 = [
            "Totalmente integrado (Provisão e Baixa) – 30", 
            "Somente as Provisões estão integradas – 05", 
            "Somente as Baixas estão integradas – 05"
        ]
        
        idx_822 = None
        if d822["valor"]:
            if "Totalmente" in d822["valor"]:
                idx_822 = 0
            elif "Provisões" in d822["valor"]:
                idx_822 = 1
            elif "Baixas" in d822["valor"]:
                idx_822 = 2

        r822 = st.radio("Selecione 8.2.2:", opcoes_822, index=idx_822, key=f"q822_{ano_sel}")
        
        if r822 and r822 != d822["valor"]:
            if "Totalmente" in r822:
                pts_822 = 30
            elif "Provisões" in r822 or "Baixas" in r822:
                pts_822 = 5
            else:
                pts_822 = 0
                
            save_resp("8.2.2", r822, pts_822, "")
            st.rerun()
            
        bloco_comentarios("8.2.2", res_data)
        st.markdown('</div>', unsafe_allow_html=True)


        # --- LEITURA REALTIME DA FILTRAGEM DO 8.0 (USANDO OPERADOR 'IN' SEGURO) ---
        chave_radio_80 = f"q80_{ano_sel}"
        if chave_radio_80 in st.session_state:
            valor_80_atual = st.session_state[chave_radio_80]
        else:
            valor_80_atual = res_data.get("8.0", {}).get("valor", "")

        # Correção aqui: Verifica se a string "Sim" está contida no valor selecionado ("Sim – 40")
        deve_aplicar_penalidade = (valor_80_atual and "Sim" in str(valor_80_atual))


        # --- LEITURA REALTIME DA FILTRAGEM DO 8.0 (USANDO OPERADOR 'IN' SEGURO) ---
        chave_radio_80 = f"q80_{ano_sel}"
        if chave_radio_80 in st.session_state:
            valor_80_atual = st.session_state[chave_radio_80]
        else:
            valor_80_atual = res_data.get("8.0", {}).get("valor", "")

        deve_aplicar_penalidade = (valor_80_atual and "Sim" in str(valor_80_atual))

        # -------------------------------------------------------------------------
        # QUESITO 8.3 - GESTÃO DIRETA DE BASES DE DADOS (TRAVA ANTI-PERDA DE ANO)
        # -------------------------------------------------------------------------
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 8.3")
        st.write(
            "**Assinale quais bases de dados encontram-se sob gestão direta da Prefeitura:**"
            "<br><small>Obs. Gestão Direta = empresa terceira não pode mudar os dados sem que a "
            "Prefeitura tenha conhecimento.</small>", 
            unsafe_allow_html=True
        )
        
        d83 = res_data.get("8.3", {"valor": "[]", "pontos": 0})
        opcoes_bases = [
            "Contabilidade", "Gestão de tributos (arrecadação)", "Dívida Ativa", 
            "Precatórios", "Gestão patrimonial (bens e equipamentos)", 
            "Gestão de negócios (Business Intelligence)", "Planejamento", 
            "Recursos humanos / Departamento pessoal", "Almoxarifado", 
            "Controle de frotas", "Controle Interno", "Saúde", 
            "Ensino (educação)", "Compras, licitações e contratos", 
            "Certidões e alvarás", "Saneamento", "Cemitérios"
        ]
        
        # Desserialização blindada contra aspas simples/duplas
        try:
            val_83_banco = d83["valor"]
            if isinstance(val_83_banco, str):
                # Limpa strings de listas mal formatadas do banco
                if val_83_banco.strip() in ["", "[]", "None"]:
                    lista_salva_83 = []
                else:
                    import json
                    # Tenta converter aspas simples para duplas se necessário antes do parse
                    txt_tratado = val_83_banco.replace("'", '"')
                    lista_salva_83 = json.loads(txt_tratado)
            else:
                lista_salva_83 = list(val_83_banco)
        except Exception:
            try:
                lista_salva_83 = ast.literal_eval(d83["valor"])
            except:
                lista_salva_83 = []
        
        sel83 = []
        col_base1, col_base2 = st.columns(2)
        for i, base in enumerate(opcoes_bases):
            with col_base1 if i % 2 == 0 else col_base2:
                # O state do checkbox é isolado por ANO graças à key dinâmica
                esta_marcado = base in lista_salva_83
                if st.checkbox(base, value=esta_marcado, key=f"q83_{base}_{ano_sel}"):
                    sel83.append(base)
                    
        if deve_aplicar_penalidade:
            pontos_finais_83 = -51 + (len(sel83) * 3)
            if pontos_finais_83 > 0: 
                pontos_finais_83 = 0
        else:
            pontos_finais_83 = 0
        
        if deve_aplicar_penalidade:
            if pontos_finais_83 < 0:
                st.warning(f"⚠️ Penalidade aplicada: {pontos_finais_83} pontos")
            else:
                st.success("✅ Nenhuma penalidade aplicada (Todos os itens preenchidos)!")
        else:
            st.success("✅ Nenhuma penalidade aplicada (Quesito 8.0 é Não)!")
            
        try:
            pontos_banco_83 = int(float(d83.get("pontos", 0)))
        except:
            pontos_banco_83 = 0

        # Ordena as duas listas antes de comparar para evitar falsos-positivos de diferença por ordem!
        if sorted(sel83) != sorted(lista_salva_83) or pontos_finais_83 != pontos_banco_83:
            save_resp("8.3", str(sorted(sel83)), pontos_finais_83, "")
            st.rerun()
            
        st.markdown('</div>', unsafe_allow_html=True)
        bloco_comentarios("8.3", res_data)


        # -------------------------------------------------------------------------
        # QUESITO 8.4 - CONTROLE DE ACESSO À INFORMAÇÃO (TRAVA ANTI-PERDA DE ANO)
        # -------------------------------------------------------------------------
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 8.4")
        st.write(
            "**Assinale quais sistemas possuem controle de acesso à informação:**"
            "<br><small>Obs. Controle de acesso relativo à gravação de histórico, níveis "
            "de acesso e demais informações de ocorrências e eventos em um sistema.</small>", 
            unsafe_allow_html=True
        )
        
        d84 = res_data.get("8.4", {"valor": "[]", "pontos": 0})
        opcoes_sistemas = [
            "Contabilidade", "Gestão de tributos (arrecadação)", "Dívida Ativa", 
            "Precatórios", "Gestão patrimonial (bens e equipamentos)", 
            "Gestão de negócios (Business Intelligence)", "Planejamento", 
            "Recursos humanos / Departamento pessoal", "Almoxarifado", 
            "Controle de frotas", "Controle Interno", "Saúde", 
            "Ensino (educação)", "Compras, licitações e contratos", 
            "Certidões e alvarás", "Saneamento", "Cemitérios"
        ]
        
        try:
            val_84_banco = d84["valor"]
            if isinstance(val_84_banco, str):
                if val_84_banco.strip() in ["", "[]", "None"]:
                    lista_salva_84 = []
                else:
                    import json
                    txt_tratado = val_84_banco.replace("'", '"')
                    lista_salva_84 = json.loads(txt_tratado)
            else:
                lista_salva_84 = list(val_84_banco)
        except Exception:
            try:
                lista_salva_84 = ast.literal_eval(d84["valor"])
            except:
                lista_salva_84 = []
        
        sel84 = []
        col_sis1, col_sis2 = st.columns(2)
        for i, sistema in enumerate(opcoes_sistemas):
            with col_sis1 if i % 2 == 0 else col_sis2:
                esta_marcado = sistema in lista_salva_84
                if st.checkbox(sistema, value=esta_marcado, key=f"q84_{sistema}_{ano_sel}"):
                    sel84.append(sistema)
                    
        if deve_aplicar_penalidade:
            pontos_finais_84 = -51 + (len(sel84) * 3)
            if pontos_finais_84 > 0: 
                pontos_finais_84 = 0
        else:
            pontos_finais_84 = 0
        
        if deve_aplicar_penalidade:
            if pontos_finais_84 < 0:
                st.warning(f"⚠️ Penalidade aplicada: {pontos_finais_84} pontos")
            else:
                st.success("✅ Nenhuma penalidade aplicada (Todos os itens preenchidos)!")
        else:
            st.success("✅ Nenhuma penalidade aplicada (Quesito 8.0 é Não)!")
            
        try:
            pontos_banco_84 = int(float(d84.get("pontos", 0)))
        except:
            pontos_banco_84 = 0

        if sorted(sel84) != sorted(lista_salva_84) or pontos_finais_84 != pontos_banco_84:
            save_resp("8.4", str(sorted(sel84)), pontos_finais_84, "")
            st.rerun()
            
        st.markdown('</div>', unsafe_allow_html=True)
        bloco_comentarios("8.4", res_data)

        # -------------------------------------------------------------------------
        # QUESITO 9.0 - SERVIÇOS ONLINE (GATILHO PRINCIPAL)
        # -------------------------------------------------------------------------
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 9.0")
        st.write(
            "**A Prefeitura ofereceu serviços de forma online?**"
            "<br><small>Exemplo: alvarás, certidões, licenças, consulta a status de "
            "protocolos de atendimento, ouvidoria, consulta de débitos municipais, "
            "pagamento de tributos...</small>", 
            unsafe_allow_html=True
        )
        
        d90 = res_data.get("9.0", {"valor": None, "pontos": 0, "link": ""})
        col1, col2 = st.columns([1, 2])
        
        with col1:
            r90 = st.radio(
                "Selecione 9.0:", 
                ["Sim", "Não"], 
                index=(0 if d90["valor"] == "Sim" else (1 if d90["valor"] == "Não" else None)), 
                key=f"q90_{ano_sel}"
            )
        with col2:
            l90 = st.text_area("Link/Evidência (9.0):", value=d90.get("link", ""), key=f"l90_{ano_sel}", height=100)
            
            # Captura de links em tempo real
            links_f90 = re.findall(r'(https?://[^\s]+)', l90)
            if links_f90:
                for lk in links_f90:
                    st.markdown(f"🔗 **Link ativo:** [{lk}]({lk})")
        
        # Processamento do salvamento do 9.0
        if r90 and (r90 != d90["valor"] or l90 != d90["link"]):
            pontos_90 = 0 
            save_resp("9.0", r90, pontos_90, l90)
            
            # Se mudou para Não, limpa os filhos para evitar lixo lógico no banco
            if r90 == "Não":
                save_resp("9.1", "[]", 0.0, "")
                save_resp("9.2", "[]", 0, "")
                
            if links_f90 and l90.strip() != d90["link"].strip():
                modal_aviso_link("9.0", [lk.strip() for lk in links_f90])
            else:
                st.rerun()

        # Bloco condicional: 9.1 e 9.2 só existem e pontuam se 9.0 for "Sim"
        if r90 == "Sim":
            st.markdown('<div style="margin-top: 25px; padding-left: 20px; border-left: 3px solid #007BFF;">', unsafe_allow_html=True)
            
            # -------------------------------------------------------------------------
            # QUESITO 9.1 - DETALHAMENTO DE SERVIÇOS DIGITAIS (CORRIGIDO ANTI-PERDA)
            # -------------------------------------------------------------------------
            st.markdown("### QUESITO 9.1")
            st.write("**Quais tipos de serviços são oferecidos de forma digital?**")
            
            d91 = res_data.get("9.1", {"valor": "[]", "pontos": 0.0})
            
            opcoes_servicos = [
                "Alvarás / licenças de funcionamento", "Certidões", "Licenças / autorizações", 
                "Ouvidoria", "Consulta de débitos municipais", "Emissão de guias/boletos dos débitos municipais", 
                "Solicitação de serviços de zeladoria", "Solicitação de obras e serviços de urbanização", 
                "Inscrições em oficinas, cursos, eventos e vagas", "Nota fiscal eletrônica", 
                "Canal de denúncias", "Cadastro de fornecedores", 
                "Agendamento de cookies na rede pública de saúde", 
                "Agendamento de exames em relação a doenças crônicas na rede pública de saúde", 
                "Pesquisa de satisfação em relação aos serviços prestados pela Prefeitura", 
                "Consulta a status de protocolos de todos os atendimentos dos serviços assinalados acima"
            ]
            
            # Desserialização blindada contra aspas simples/duplas e estados fantasmas de ano
            try:
                val_91_banco = d91["valor"]
                if isinstance(val_91_banco, str):
                    if val_91_banco.strip() in ["", "[]", "None"]:
                        lista_salva_91 = []
                    else:
                        import json
                        txt_tratado = val_91_banco.replace("'", '"')
                        lista_salva_91 = json.loads(txt_tratado)
                else:
                    lista_salva_91 = list(val_91_banco)
            except Exception:
                try:
                    lista_salva_91 = ast.literal_eval(d91["valor"])
                except:
                    lista_salva_91 = []
            
            sel91 = []
            col_serv1, col_serv2 = st.columns(2)
            for i, servico in enumerate(opcoes_servicos):
                with col_serv1 if i % 2 == 0 else col_serv2:
                    esta_marcado = servico in lista_salva_91
                    # A key agora amarra o serviço E o ano selecionado perfeitamente
                    if st.checkbox(f"{servico} (+7,5 pts)", value=esta_marcado, key=f"q91_{servico}_{ano_sel}"):
                        sel91.append(servico)
            
            # Cálculo de pontuação tratado como float puro para evitar dízima periódica na comparação
            pontos_calculados = float(len(sel91) * 7.5)
            teto_maximo = 120.0
            eficiencia = (pontos_calculados / teto_maximo)
            
            st.markdown("<hr style='margin: 15px 0; border: 0; border-top: 1px solid #eee;'>", unsafe_allow_html=True)
            col_m1, col_m2 = st.columns([2, 1])
            with col_m1:
                st.progress(min(eficiencia, 1.0))
            with col_m2:
                st.markdown(f"**Pontuação auferida:** `{pontos_calculados:.1f} / {teto_maximo:.1f} pts`")
            
            try:
                pontos_banco_91 = float(d91.get("pontos", 0.0))
            except:
                pontos_banco_91 = 0.0

            # COMPARAÇÃO UTILIZANDO SORTED PARA IGNORAR A ORDEM DE CLIQUE DO USUÁRIO
            if sorted(sel91) != sorted(lista_salva_91) or abs(pontos_calculados - pontos_banco_91) > 0.01:
                save_resp("9.1", str(sorted(sel91)), pontos_calculados, "")
                st.rerun()
                
            bloco_comentarios("9.1", res_data)
            st.markdown("<hr style='margin: 25px 0; border: 0; border-top: 2px solid #eee;'>", unsafe_allow_html=True)

            # -------------------------------------------------------------------------
            # QUESITO 9.2 - FORMAS DE ATENDIMENTO À DISTÂNCIA
            # -------------------------------------------------------------------------
            st.markdown("### QUESITO 9.2")
            st.write("**Quais as formas de atendimento à distância disponibilizadas ao público pela Prefeitura?**")
            
            d92 = res_data.get("9.2", {"valor": "[]", "pontos": 0})
            
            opcoes_atendimento = [
                "Telefone", "Site da Prefeitura", "Aplicativo de mensagens", 
                "Redes sociais", "Aplicativo da Prefeitura", "Correio eletrônico (e-mail)", 
                "Outros"
            ]
            
            try:
                lista_salva_92 = ast.literal_eval(d92["valor"]) if isinstance(d92["valor"], str) else list(d92["valor"])
            except Exception:
                lista_salva_92 = []
            
            sel92 = []
            col_atend1, col_atend2 = st.columns(2)
            for i, forma in enumerate(opcoes_atendimento):
                with col_atend1 if i % 2 == 0 else col_atend2:
                    esta_marcado = forma in lista_salva_92
                    if st.checkbox(forma, value=esta_marcado, key=f"q92_{forma}_{ano_sel}"):
                        sel92.append(forma)
            
            if str(sel92) != d92["valor"]:
                pontos_92 = 0  
                save_resp("9.2", str(sel92), pontos_92, "")
                st.rerun()
                
            bloco_comentarios("9.2", res_data)
            st.markdown('</div>', unsafe_allow_html=True) # Fecha a div do recuo condicional
            
        bloco_comentarios("9.0", res_data, sufixo="principal")
        st.markdown('</div>', unsafe_allow_html=True) # Fecha o card principal do 9.0

        # -------------------------------------------------------------------------
        # QUESITO 10.0 - REGULAMENTAÇÃO DA LGPD (GATILHO PRINCIPAL)
        # -------------------------------------------------------------------------
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 10.0")
        st.write("**A Prefeitura Municipal regulamentou o tratamento de dados pessoais, inclusive nos meios digitais, segundo a LGPD (Lei Federal nº 13.709, de 14 de agosto de 2018)?**")
        
        d100 = res_data.get("10.0", {"valor": None, "pontos": 0, "link": ""})
        col1, col2 = st.columns([1, 2])
        
        with col1:
            r100 = st.radio(
                "Selecione 10.0:", 
                ["Sim", "Não"], 
                index=(0 if d100["valor"] == "Sim" else (1 if d100["valor"] == "Não" else None)), 
                key=f"q100_{ano_sel}"
            )
        with col2:
            l100 = st.text_area("Link/Evidência (10.0):", value=d100.get("link", ""), key=f"l100_{ano_sel}", height=100)
            
            # Usando injeção direta via sys.modules para blindar contra UnboundLocalError
            import sys
            _regex = sys.modules['re']
            
            links_f100 = _regex.findall(r'(https?://[^\s]+)', l100)
            if links_f100:
                for lk in links_f100:
                    st.markdown(f"🔗 **Link ativo:** [{lk}]({lk})")
        
        if r100 and (r100 != d100["valor"] or l100 != d100["link"]):
            pontos_100 = 0  
            save_resp("10.0", r100, pontos_100, l100)
            
            if r100 == "Não":
                save_resp("10.1", "", 0, "")
                save_resp("10.2", "", 0, "")
                
            if links_f100 and l100.strip() != d100["link"].strip():
                modal_aviso_link("10.0", [lk.strip() for lk in links_f100])
            else:
                st.rerun()
                
        bloco_comentarios("10.0", res_data, sufixo="principal")

        # Exibição Condicional de Detalhes do Instrumento Normativo
        if r100 == "Sim":
            st.markdown('<div style="margin-top: 20px; padding-left: 15px; border-left: 3px solid #00CC66;">', unsafe_allow_html=True)
            
            # --- QUESITO 10.1 ---
            st.markdown("### QUESITO 10.1")
            st.write("**Informe o Instrumento normativo, Número e Data da publicação:**")
            d101 = res_data.get("10.1", {"valor": "", "pontos": 0})
            t101 = st.text_area(
                "Informe os dados aqui:", 
                value=d101.get("valor", ""), 
                key=f"t101_{ano_sel}", 
                height=100,
                placeholder="Exemplo: Decreto Municipal nº 1.234, publicado em DD/MM/AAAA"
            )
            if t101 != d101["valor"]:
                save_resp("10.1", t101, 0, "")
                st.rerun()
            bloco_comentarios("10.1", res_data)

            st.markdown("<hr style='margin: 15px 0; border: 0; border-top: 1px dashed #ccc;'>", unsafe_allow_html=True)

            # --- QUESITO 10.2 ---
            st.markdown("### QUESITO 10.2")
            st.write("**Informe a página eletrônica (link na internet):**<br><small>Se não estiver disponível na internet, inserir no campo de resposta o texto XYZ</small>", unsafe_allow_html=True)
            d102 = res_data.get("10.2", {"valor": "", "pontos": 0})
            t102 = st.text_input(
                "Link ou texto de contingência:", 
                value=d102.get("valor", ""), 
                key=f"t102_{ano_sel}",
                placeholder="Cole o link aqui ou digite XYZ"
            )
            
            links_f102 = _regex.findall(r'(https?://[^\s]+)', t102)
            if links_f102:
                for lk in links_f102:
                    st.markdown(f"🔗 **Link ativo detectado:** [{lk}]({lk})")
                    
            if t102 != d102["valor"]:
                save_resp("10.2", t102, 0, "")
                if links_f102:
                    modal_aviso_link("10.2", [lk.strip() for lk in links_f102])
                else:
                    st.rerun()
            bloco_comentarios("10.2", res_data)
            
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

        # -------------------------------------------------------------------------
        # QUESITO 10.3 - CLÁUSULAS DE CONTRATOS VIGENTES
        # -------------------------------------------------------------------------
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 10.3")
        st.write("**Os contratos com os prestadores de serviços contêm cláusulas de observância à LGPD?**")
        
        d103 = res_data.get("10.3", {"valor": None, "pontos": 0})
        opcoes_103 = [
            "Todos os contratos vigentes",
            "A maior parte dos contratos vigentes",
            "A menor parte dos contratos vigentes",
            "Não"
        ]
        
        idx_103 = None
        if d103["valor"]:
            if "Todos" in d103["valor"]: idx_103 = 0
            elif "maior parte" in d103["valor"]: idx_103 = 1
            elif "menor parte" in d103["valor"]: idx_103 = 2
            elif "Não" in d103["valor"]: idx_103 = 3

        r103 = st.radio("Selecione 10.3:", opcoes_103, index=idx_103, key=f"q103_{ano_sel}")
        
        if r103 and r103 != d103["valor"]:
            pontos_103 = 0  
            save_resp("10.3", r103, pontos_103, "")
            st.rerun()
            
        bloco_comentarios("10.3", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # -------------------------------------------------------------------------
        # QUESITO 10.4 - MAPEAMENTO DE DADOS (DATA MAPPING)
        # -------------------------------------------------------------------------
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 10.4")
        st.write("**A Prefeitura Municipal realizou mapeamento de dados (data mapping)?**")
        
        d104 = res_data.get("10.4", {"valor": None, "pontos": 0, "link": ""})
        col1, col2 = st.columns([1, 2])
        
        with col1:
            r104 = st.radio(
                "Selecione 10.4:", 
                ["Sim", "Não"], 
                index=(0 if d104["valor"] == "Sim" else (1 if d104["valor"] == "Não" else None)), 
                key=f"q104_{ano_sel}"
            )
        with col2:
            l104 = st.text_area("Link/Evidência (10.4):", value=d104.get("link", ""), key=f"l104_{ano_sel}", height=100)
            
            links_f104 = _regex.findall(r'(https?://[^\s]+)', l104)
            if links_f104:
                for lk in links_f104:
                    st.markdown(f"🔗 **Link ativo:** [{lk}]({lk})")
        
        if r104 and (r104 != d104["valor"] or l104 != d104["link"]):
            pontos_104 = 0  
            save_resp("10.4", r104, pontos_104, l104)
            
            if links_f104 and l104.strip() != d104["link"].strip():
                modal_aviso_link("10.4", [lk.strip() for lk in links_f104])
            else:
                st.rerun()
                
        bloco_comentarios("10.4", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # -------------------------------------------------------------------------
        # QUESITO 10.5 e Subitem - MEDIDAS DE SEGURANÇA ADOTADAS
        # -------------------------------------------------------------------------
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 10.5")
        st.write("**Foram adotadas medidas de segurança, técnicas e administrativas a fim de proteger os dados pessoais de acessos não autorizados e de situações acidentais ou ilícitas?**")
        
        d105 = res_data.get("10.5", {"valor": None, "pontos": 0, "link": ""})
        col1, col2 = st.columns([1, 2])
        
        with col1:
            r105 = st.radio(
                "Selecione 10.5:", 
                ["Sim", "Não"], 
                index=(0 if d105["valor"] == "Sim" else (1 if d105["valor"] == "Não" else None)), 
                key=f"q105_{ano_sel}"
            )
        with col2:
            l105 = st.text_area("Link/Evidência (10.5):", value=d105.get("link", ""), key=f"l105_{ano_sel}", height=100)
            
            links_f105 = _regex.findall(r'(https?://[^\s]+)', l105)
            if links_f105:
                for lk in links_f105:
                    st.markdown(f"🔗 **Link ativo:** [{lk}]({lk})")
        
        if r105 and (r105 != d105["valor"] or l105 != d105["link"]):
            pontos_105 = 0  
            save_resp("10.5", r105, pontos_105, l105)
            
            if r105 == "Não":
                save_resp("10.5.1", "", 0, "")
                
            if links_f105 and l105.strip() != d105["link"].strip():
                modal_aviso_link("10.5", [lk.strip() for lk in links_f105])
            else:
                st.rerun()
                
        bloco_comentarios("10.5", res_data, sufixo="principal")

        if r105 == "Sim":
            st.markdown('<div style="margin-top: 20px; padding-left: 15px; border-left: 3px solid #FF9900;">', unsafe_allow_html=True)
            st.markdown("### QUESITO 10.5.1")
            st.write("**Informe as medidas adotadas:**")
            
            d1051 = res_data.get("10.5.1", {"valor": "", "pontos": 0})
            t1051 = st.text_area(
                "Informe as medidas aqui:", 
                value=d1051.get("valor", ""), 
                key=f"t1051_{ano_sel}", 
                height=120,
                placeholder="Descreva aqui as medidas administrativas, técnicas ou de segurança implementadas..."
            )
            if t1051 != d1051["valor"]:
                save_resp("10.5.1", t1051, 0, "")
                st.rerun()
                
            bloco_comentarios("10.5.1", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

        # -------------------------------------------------------------------------
        # QUESITO 11.0 - ENCARREGADO DE DADOS / DPO (GATILHO)
        # -------------------------------------------------------------------------
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 11.0")
        st.write("**A Prefeitura Municipal designou um encarregado para as operações de tratamento de dados pessoais?**")
        
        d110 = res_data.get("11.0", {"valor": None, "pontos": 0, "link": ""})
        col1, col2 = st.columns([1, 2])
        
        with col1:
            r110 = st.radio(
                "Selecione 11.0:", 
                ["Sim", "Não"], 
                index=(0 if d110["valor"] == "Sim" else (1 if d110["valor"] == "Não" else None)), 
                key=f"q110_{ano_sel}"
            )
        with col2:
            l110 = st.text_area("Link/Evidência (11.0):", value=d110.get("link", ""), key=f"l110_{ano_sel}", height=100)
            
            links_f110 = _regex.findall(r'(https?://[^\s]+)', l110)
            if links_f110:
                for lk in links_f110:
                    st.markdown(f"🔗 **Link ativo:** [{lk}]({lk})")
        
        if r110 and (r110 != d110["valor"] or l110 != d110["link"]):
            pontos_110 = 0  
            save_resp("11.0", r110, pontos_110, l110)
            
            if r110 == "Não":
                save_resp("11.1", "", 0, "")
                
            if links_f110 and l110.strip() != d110["link"].strip():
                modal_aviso_link("11.0", [lk.strip() for lk in links_f110])
            else:
                st.rerun()
                
        bloco_comentarios("11.0", res_data, sufixo="principal")

        if r110 == "Sim":
            st.markdown('<div style="margin-top: 20px; padding-left: 15px; border-left: 3px solid #00CC66;">', unsafe_allow_html=True)
            
            # --- QUESITO 11.1 ---
            st.markdown("### QUESITO 11.1")
            st.write(
                "**Informe a página eletrônica (link no site da prefeitura), que contenha a identidade "
                "e as informações de contato do encarregado:**<br><small>Se não estiver disponível na internet, "
                "inserir no campo de resposta o texto XYZ</small>", 
                unsafe_allow_html=True
            )
            
            d111 = res_data.get("11.1", {"valor": "", "pontos": 0})
            t111 = st.text_input(
                "Link ou texto de contingência (11.1):", 
                value=d111.get("valor", ""), 
                key=f"t111_{ano_sel}",
                placeholder="Cole a URL da página do encarregado ou digite XYZ"
            )
            
            links_f111 = _regex.findall(r'(https?://[^\s]+)', t111)
            if links_f111:
                for lk in links_f111:
                    st.markdown(f"🔗 **Link ativo detectado:** [{lk}]({lk})")
                    
            if t111 != d111["valor"]:
                save_resp("11.1", t111, 0, "")
                if links_f111:
                    modal_aviso_link("11.1", [lk.strip() for lk in links_f111])
                else:
                    st.rerun()
                    
            bloco_comentarios("11.1", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)

        # -------------------------------------------------------------------------
        # QUESITO 12.0 - CONSIDERAÇÕES FINAIS E FEEDBACK
        # -------------------------------------------------------------------------
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 12.0")
        st.write(
            "**Gostaria de registrar suas impressões, comentários e sugestões a respeito do presente questionário?**"
            "<br><small>Utilize o espaço abaixo para registrar suas impressões, comentários e sugestões.</small>", 
            unsafe_allow_html=True
        )
        
        d120 = res_data.get("12.0", {"valor": "", "pontos": 0})
        t120 = st.text_area(
            "Suas impressões / comentários:", 
            value=d120.get("valor", ""), 
            key=f"t120_{ano_sel}", 
            height=160,
            placeholder="Escreva aqui suas críticas, elogios, dificuldades ou sugestões de melhoria para os próximos anos..."
        )
        
        if t120 != d120["valor"]:
            save_resp("12.0", t120, 0, "")
            st.rerun()
            
        bloco_comentarios("12.0", res_data)
        st.markdown('</div>', unsafe_allow_html=True) # Fim do card 12.0 (8 espaços de recuo)

    # =========================================================================
    # ATENÇÃO AQUI: Note que o "with aba_graf:" tem EXATAMENTE 4 ESPAÇOS (1 Tab)
    # Ele fica alinhado verticalmente com o "with aba_quest:" lá do topo!
    # =========================================================================
    with aba_graf:
        st.subheader("📈 Evolução dos Resultados — Série Histórica")
        st.write("Acompanhe o desempenho da pontuação total acumulada ao longo dos anos:")

        # 1. Recupera o histórico tratado na sidebar
        dados_historicos = st.session_state.get("all_data", {})
        anos_periodo = [2023, 2024, 2025, 2026, 2027, 2028, 2029, 2030]
        
        # 2. Processa os pontos de cada ano da série histórica
        pontuacoes_por_ano = {}
        for ano in anos_periodo:
            dados_do_ano = dados_historicos.get(ano, {})
            if isinstance(dados_do_ano, dict) and dados_do_ano:
                pts_ano = sum(float(v.get("pontos", 0)) for k, v in dados_do_ano.items() if not k.startswith("COM_"))
            else:
                pts_ano = 0.0
            pontuacoes_por_ano[str(ano)] = pts_ano

        # 3. Renderiza o Gráfico de Barras
        st.bar_chart(
            pontuacoes_por_ano, 
            x_label="Ano de Referência", 
            y_label="Pontuação Total",
            color="#1e3a5f"
        )
        
        # 4. Tabela resumida de apoio
        st.markdown("#### 📋 Resumo dos Dados")
        dados_tabela = {
            "Ano": list(pontuacoes_por_ano.keys()),
            "Pontuação": [f"{pts:.1f} pts" if pts > 0 else "-" for pts in pontuacoes_por_ano.values()]
        }
        st.dataframe(dados_tabela, hide_index=True, use_container_width=True)
