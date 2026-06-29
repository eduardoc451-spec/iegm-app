import streamlit as st
import os
import sys

# =============================================================================
# BLOQUEIO INTERNO NATIVO DO STREAMLIT (ANTES DE QUALQUER OPERAÇÃO)
# =============================================================================
# Força o nível do Logger global do Streamlit para ignorar Warnings antes de renderizar
os.environ["STREAMLIT_LOGGER_LEVEL"] = "error"
os.environ["PYTHONWARNINGS"] = "ignore"

import sqlite3
import warnings
import logging
from io import BytesIO
from datetime import datetime, date
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak

# Silencia o interpretador Python padrão
warnings.filterwarnings("ignore", category=DeprecationWarning)
logging.getLogger("streamlit").setLevel(logging.ERROR)
# =============================================================================

# Bibliotecas para o PDF (Requer: pip install reportlab)
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics.charts.barcharts import VerticalBarChart

# Bibliotecas para os Gráficos (Requer: pip install plotly)
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# =============================================================================
# CONSTANTES GLOBAIS
# =============================================================================

CATEGORIAS_MAP = {
    "planejamento":   {"label": "Planejamento",    "qids": ["1.0", "1.3", "1.4"]},
    "gestao_fiscal":  {"label": "Gestão Fiscal",   "qids": ["2.0", "2.1", "2.2", "10.0", "C1.1"]},
    "educacao":       {"label": "Educação",         "qids": ["3.0", "3.1", "11.1", "11.1.1", "11.2"]},
    "saude":          {"label": "Saúde",            "qids": ["4.2", "12.1", "12.1.3"]},
    "meio_ambiente":  {"label": "Meio Ambiente",    "qids": ["5.0", "5.1.1", "5.2", "14.0"]},
    "cidades_proteg": {"label": "Cidades Proteg.",  "qids": ["6.0", "15.0"]},
    "governanca_ti":  {"label": "Governança TI",    "qids": ["7.0", "7.1", "7.2", "7.3", "7.4", "7.5", "7.6", "16.0"]},
    "transparencia":  {"label": "Transparência",    "qids": ["8.0", "8.1.1.1", "8.2", "9.0"]},
}
PONTUACOES_MAX = {
    "1.0": 40, 
    "1.3": 5, 
    "1.4": 50, 
    "2.0": 20, 
    "2.1": 30, 
    "2.2": 10, 
    "3.0": 10, 
    "3.1.1": 10, 
    "5.0": 200, 
    "7.0": 50, 
    "7.1": 5, 
    "7.2": 80, 
    "7.3": 50, 
    "7.4": 50, 
    "7.5": 10, 
    "7.6": 10, 
    "8.0": 50, 
    "8.1.1.1": 20, 
    "8.2": 50, 
    "9.0": 100, 
    "15.0": 50, 
    "16.0": 50, 
    "C1.1": 50
}

FAIXA_CORES = {"C": "#ef4444", "C+": "#f97316", "B": "#eab308", "B+": "#22c55e", "A": "#16a34a"}

# =============================================================================
# MODAL DE AVISO AUTOMÁTICO (CORRIGIDO PARA LINKS CLICÁVEIS)
# =============================================================================
@st.dialog("⚠️ Atenção! Evidência em Link Externo")
def modal_aviso_link(qid, links_encontrados):
    st.warning(f"Detectamos a inclusão de link(s) no campo de evidências da questão **{qid}**.")
    
    for lk in links_encontrados:
        st.markdown(f"🔗 **Endereço:** [{lk}]({lk})")
        
    st.markdown("""
    **Por favor, verifique se este link está configurado para acesso público/compartilhado.**
    
    Se as credenciais estiverem privadas ou exigirem login e senha do seu município, as equipes avaliadoras externas **não conseguirão acessar as provas**, invalidando os pontos desse quesito.
    """)
    if st.button("Confirmo que o link está liberado para o público", key=f"btn_conf_{qid}"):
        st.rerun()

# =============================================================================
# 1. FUNÇÕES DE APOIO E BANCO DE DADOS (IEGM - iCIDADE)
# =============================================================================
import sqlite3
import json
import datetime
import re
import ast
import streamlit as st

def get_connection():
    # Conecta no banco específico do iCidade / IEGM
    return sqlite3.connect("dados_iegm_web.db", check_same_thread=False)

def init_db():
    """Cria as tabelas do banco de dados com migração automática e correção de colunas truncadas."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Cria a tabela base se ela não existir
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
        
        # 2. PRAGMA para checar quais colunas realmente existem no arquivo físico do banco
        cursor.execute("PRAGMA table_info(respostas)")
        colunas_existentes = [row[1] for row in cursor.fetchall()]
        
        # 3. Força a criação da coluna de comentários em JSON se não existir
        if "comentarios" not in colunas_existentes:
            try:
                cursor.execute("ALTER TABLE respostas ADD COLUMN comentarios TEXT")
            except sqlite3.OperationalError:
                pass # Já existe
                
        # 4. CORREÇÃO DO ERRO: Garante que a coluna 'atualizado_em' esteja com o nome perfeito
        if "atualizado_em" not in colunas_existentes:
            try:
                cursor.execute("ALTER TABLE respostas ADD COLUMN atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            except sqlite3.OperationalError:
                pass
                
        # 5. Garante a coluna criado_em
        if "criado_em" not in colunas_existentes:
            try:
                cursor.execute("ALTER TABLE respostas ADD COLUMN criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
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

    # --- CORREÇÃO DO ERRO AQUI ---
    # Como você importou "from datetime import datetime", você deve chamar datetime.now() direto
    try:
        timestamp_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except AttributeError:
        # Caso haja conflito de escopo no seu arquivo, esse fallback impede a quebra
        import datetime as dt_modulo
        timestamp_atual = dt_modulo.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        with get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO respostas (id, ano, valor, pontos, link, comentarios, atualizado_em) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (qid, ano_sel, str(valor), float(pontos), str(link), comentarios_json, timestamp_atual))
            conn.commit()
    except sqlite3.OperationalError as e:
        if "no column named atualizado_em" in str(e):
            try:
                with get_connection() as conn:
                    conn.execute("ALTER TABLE respostas ADD COLUMN atualizado_em TEXT")
                    conn.commit()
                save_resp(qid, valor, pontos, link, comentarios)
            except Exception as ex:
                st.error(f"Erro crítico ao tentar corrigir estrutura: {ex}")
        else:
            st.error(f"Erro operacional no banco: {e}")
    except Exception as e:
        st.error(f"Erro ao salvar {qid}: {e}")

def bloco_comentarios(questao_id, res_data, sufixo=None):
    """
    Gera o diálogo interno avançado com histórico retrátil, status em realtime
    e controle individual de remoção por lixeira. Atualizado para padrões Streamlit post-2025.
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
        
        # CORREÇÃO AQUI: Trocado qualquer resquício interno de tamanho para a sintaxe nova do Streamlit
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
                        "status_definido": status_global
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
# 2. FUNÇÕES DE ANÁLISE
# =============================================================================

def analyze_performance(res_data):
    pontos_fortes = []
    criticos_zero = {"Alta": [], "Média": [], "Baixa": []}
    criticos_negativos = {"Alta": [], "Média": [], "Baixa": []}

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
        if qid.startswith("COM_"):
            continue
        if qid not in pontuacoes_referencia:
            continue

        pontos_atuais = info.get("pontos", 0)
        ref = pontuacoes_referencia[qid]
        max_pontos = ref["max"]

        if pontos_atuais == max_pontos:
            pontos_fortes.append((qid, pontos_atuais, info.get("valor", ""), info.get("link", "")))
        else:
            impacto = max_pontos - pontos_atuais
            relevancia = classificar_relevancia(impacto)

            if pontos_atuais < 0:
                criticos_negativos[relevancia].append(
                    (qid, pontos_atuais, info.get("valor", ""), info.get("link", ""), impacto)
                )
            else:
                criticos_zero[relevancia].append(
                    (qid, pontos_atuais, info.get("valor", ""), info.get("link", ""), impacto)
                )

    pontos_fortes.sort(key=lambda x: x[1], reverse=True)
    for rel in ["Alta", "Média", "Baixa"]:
        criticos_zero[rel].sort(key=lambda x: x[4], reverse=True)
        criticos_negativos[rel].sort(key=lambda x: x[4], reverse=True)

    return pontos_fortes, criticos_zero, criticos_negativos


def analyze_recurrence(ano_atual, res_data_atual):
    reincidencias = []
    all_data = get_all_years_data()

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
        if pontos_atual <= 0:
            for ano_anterior in anos_anteriores:
                if qid_atual in all_data[ano_anterior]:
                    pontos_anterior = all_data[ano_anterior][qid_atual].get("pontos", 0)
                    if pontos_anterior <= 0:
                        reincidencias.append((qid_atual, ano_anterior, pontos_anterior, pontos_atual))
                        break
    return reincidencias


# =============================================================================
# 3. GERADOR DO RELATÓRIO PDF
# =============================================================================

def gerar_relatorio_pdf(dados, ano, total, faixa):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()

    # Título do Relatório
    elements.append(Paragraph(f"RELATÓRIO DE AUDITORIA i-CIDADE - {ano}", styles["Title"]))
    elements.append(Spacer(1, 12))

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
    
    # --- ADICIONE ESTA LINHA ABAIXO PARA DEFINIR O ESTILO DO TÍTULO ---
    style_titulo_capa = ParagraphStyle(
        'TituloCapa', 
        parent=styles['Normal'], 
        fontName='Helvetica-Bold', 
        fontSize=24, 
        textColor=colors.HexColor("#2c3e50"), 
        alignment=1  # 1 significa centralizado
    )
    # ------------------------------------------------------------------

    # Agora o ReportLab saberá o que é 'style_titulo_capa'
    elements.append(Paragraph("Relatório I-Cidade", style_titulo_capa))
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
    # 1. RESUMO EXECUTIVO (ANÁLISE COMPARATIVA DE EXERCÍCIOS)
    # -------------------------------------------------------------------------
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

    all_data = {}
    try:
        all_data = get_all_years_data()
    except Exception:
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

    # -------------------------------------------------------------------------
    # 2. ANÁLISE DE DESEMPENHO POR QUESITO (FORTES E FRACOS COLETADOS)
    # -------------------------------------------------------------------------
    elements.append(Paragraph("<b>2. ANÁLISE DE DESEMPENHO POR QUESITO</b>", styles["h2"]))
    elements.append(Spacer(1, 6))

    lista_pontos_fortes = []
    lista_pontos_fracos = []
    reincidencias_detectadas = []

    for qid, info in dados.items():
        if qid.startswith("COM_") or not isinstance(info, dict): continue
        pts_obtidos = float(info.get("pontos", 0))
        valor_resposta = info.get("valor", "")
        link_evidencia = info.get("link", "")
        pts_maximo = float(PONTUACOES_MAX.get(qid, 0))
        
        if pts_maximo > 0:
            eficiencia = (pts_obtidos / pts_maximo) * 100
            item_data = {"qid": qid, "pts_obtidos": pts_obtidos, "pts_maximo": pts_maximo, "eficiencia": eficiencia, "valor": valor_resposta, "link": link_evidencia}
            if eficiencia >= 70.0: lista_pontos_fortes.append(item_data)
            elif eficiencia < 50.0:
                lista_pontos_fracos.append(item_data)
                if qid in dados_ano_anterior:
                    info_ant = dados_ano_anterior[qid]
                    pts_anterior = float(info_ant.get("pontos", 0))
                    if pts_obtidos == pts_anterior:
                        reincidencias_detectadas.append({"qid": qid, "tipo": "Ponto Fraco", "detalhe": "Eficiência Crítica Persistente", "ant": f"{pts_anterior:.1f} pts", "atual": f"{pts_obtidos:.1f} pts"})

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

    PENALIDADES_MAX = {"4.2": -50.0, "5.1.1": -100.0, "5.2": -50.0, "6.0": -50.0, "10": -100.0, "10.0": -100.0, "11.1": -20.0, "11.2": -20.0, "11.2.1": -20.0, "12.1.3": -50.0, "14.0": -50.0}

    lista_penalidades = []
    for qid, pen_max in PENALIDADES_MAX.items():
        if qid in dados:
            info = dados[qid]
            nota_real = float(info.get("pontos", 0))
            nota_risco = nota_real if nota_real <= 0 else 0.0
            eficiencia_preventiva = (1.0 - (nota_risco / pen_max)) * 100.0
            lista_penalidades.append({"qid": qid, "nota_real": nota_real, "pen_max": pen_max, "eficiencia": eficiencia_preventiva, "valor": info.get("valor", ""), "link": info.get("link", "")})
            if eficiencia_preventiva < 100.0 and qid in dados_ano_anterior:
                info_ant = dados_ano_anterior[qid]
                nota_real_ant = float(info_ant.get("pontos", 0))
                if nota_real == nota_real_ant:
                    reincidencias_detectadas.append({"qid": qid, "tipo": "Penalidade Aplicada", "detalhe": f"Impacto Recorrente de {nota_real:.1f} pts", "ant": f"{nota_real_ant:.1f} pts", "atual": f"{nota_real:.1f} pts"})

    if lista_penalidades:
        data_penalidades = [["Quesito", "Penalidade Aplicada", "Pior Cenário", "Eficiência Preventiva", "Status de Risco"]]
        for item in sorted(lista_penalidades, key=lambda x: x["eficiencia"]):
            nota_txt = f"{item['nota_real']:.1f} pts"; teto_txt = f"{item['pen_max']:.1f} pts"; ef_txt = f"{item['eficiencia']:.1f}%"
            if item['eficiencia'] == 100.0: status = "<font color='#28a745'><b>Risco Mitigado</b></font>"
            elif item['eficiencia'] <= 0.0: status = "<font color='#dc3545'><b>Impacto Máximo</b></font>"
            else: status = "<font color='#ffc107'><b>Impacto Parcial</b></font>"
            data_penalidades.append([item['qid'], nota_txt, teto_txt, ef_txt, Paragraph(status, styles["Normal"])])
        tabela_pen = Table(data_penalidades, colWidths=[65, 110, 80, 115, 120])
        tabela_pen.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1b4f72")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke), ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#1b4f72")), ("FONTSIZE", (0, 0), (-1, -1), 9), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        elements.append(tabela_pen)
        elements.append(Spacer(1, 15))

    # -------------------------------------------------------------------------
    # 4. DIAGNÓSTICO DE REINCIDÊNCIAS (GARGALOS PERSISTENTES)
    # -------------------------------------------------------------------------
    elements.append(Paragraph("<b>4. DIAGNÓSTICO DE REINCIDÊNCIAS (GARGALOS PERSISTENTES)</b>", styles["h2"]))
    elements.append(Spacer(1, 6))
    if reincidencias_detectadas:
        data_reinc = [["Quesito", "Origem da Falha", "Impacto Histórico", "Exercício Anterior", "Exercício Atual"]]
        for reinc in reincidencias_detectadas: data_reinc.append([reinc["qid"], reinc["tipo"], Paragraph(f"<b>{reinc['detalhe']}</b>", styles["Normal"]), reinc["ant"], reinc["atual"]])
        tabela_reinc = Table(data_reinc, colWidths=[65, 115, 170, 75, 65])
        tabela_reinc.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#c0392b")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke), ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#c0392b")), ("FONTSIZE", (0, 0), (-1, -1), 9), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        elements.append(tabela_reinc)
    else: elements.append(Paragraph("<font color='#28a745'><b>Nenhuma reincidência ativa detectada.</b></font>", styles["Normal"]))
    elements.append(Spacer(1, 15))

    # -------------------------------------------------------------------------
    # 5. ALINHAMENTO COM A AGENDA 2030 (METAS ODS / ONU)
    # -------------------------------------------------------------------------
    elements.append(Paragraph("<b>5. ALINHAMENTO COM A AGENDA 2030 (METAS ODS / ONU)</b>", styles["h2"]))
    elements.append(Spacer(1, 6))
    def calcular_percentual_checklist(resposta_bruta, total_itens):
        if not resposta_bruta: return 0.0
        itens = [i.strip().lower() for i in str(resposta_bruta).split(",") if i.strip()]
        itens_validos = [i for i in itens if "outros" not in i]
        return min((len(itens_validos) / total_itens) * 100.0, 100.0) if total_itens > 0 else 0.0

    analise_ods = []
    for qid, info in dados.items():
        if qid.startswith("COM_") or not isinstance(info, dict): continue
        resp = str(info.get("valor", "")).strip(); resp_l = resp.lower(); metas = ""; status = ""
        # (Lógica das ODS aqui...) - Mantido conforme sua especificação anterior
        if qid == "1.0": metas = "11.5, 16.6"; status = "Atendido" if "sim" in resp_l else "Não Atendido"
        elif qid == "1.4": metas = "11.5, 16.6"; status = "Não Atendido" if "não atuam de forma sistêmica" in resp_l else "Atendido"
        elif qid == "2.0": metas = "11.5, 16.6"; status = "Atendido" if "sim" in resp_l else "Não Atendido"
        elif qid == "3.0": metas = "11.5, 16.7, 16.10, 17.0"; status = "Atendido" if "sim" in resp_l else "Não Atendido"
        elif qid == "3.1": metas = "11b, 11.5, 16.7, 16.10"; status = f"{calcular_percentual_checklist(resp, 6):.1f}% Atendido"
        elif qid == "4.0": metas = "1.5, 11.5, 11b"; status = "Atendido" if "sim" in resp_l else "Não Atendido"
        elif qid == "5.0": metas = "1.5, 11.5, 16b"; status = "Atendido" if "sim" in resp_l else "Não Atendido"
        elif qid == "5.1": metas = "11b, 11.5, 16.7, 16.10"; status = f"{calcular_percentual_checklist(resp, 8):.1f}% Atendido"
        elif qid == "5.1.1": metas = "11b, 11.5, 16.6, 16.10"; status = "Atendido" if ("sim, integralmente" in resp_l or "sim, parcialmente" in resp_l) else "Não Atendido"
        elif qid == "5.1.1.1": metas = "11b, 11.5, 16.6"; status = "Atendido" if "sim" in resp_l else "Não Atendido"
        elif qid == "5.1.2": metas = "11b, 11.5, 16.6"; status = "Atendido" if "não" in resp_l else "Não Atendido"
        elif qid == "5.2": metas = "11b, 11.5, 16.6"; status = "Atendido" if ("sim" in resp_l or "parcialmente" in resp_l) else "Não Atendido"
        elif qid == "7.0": metas = "11b, 11.5, 16.6"; status = "Atendido" if "sim" in resp_l else "Não Atendido"
        elif qid == "7.3": metas = "11b, 11.5, 16.6"; status = "Atendido" if "sim" in resp_l else "Não Atendido"
        elif qid == "7.3.1": metas = "11b, 11.5, 16.6"; status = f"{calcular_percentual_checklist(resp, 7):.1f}% Atendido"
        elif qid == "7.4": metas = "11b, 11.5, 16.6"; status = "Atendido" if "sim" in resp_l else "Não Atendido"
        elif qid == "7.4.1": metas = "11.5, 16.6"; status = f"{calcular_percentual_checklist(resp, 7):.1f}% Atendido"
        elif qid == "7.5": metas = "1.5, 11.5, 16.6"; status = "Atendido" if ("sim, atualizado" in resp_l or "sim, mas não está atualizado" in resp_l) else "Não Atendido"
        elif qid == "7.6": metas = "1.5, 11.5, 16.6"; status = "Atendido" if ("sim, atualizado" in resp_l or "sim, mas não está atualizado" in resp_l) else "Não Atendido"
        elif qid in ["8", "8.0"]: metas = "1.5, 11.5, 16.6"; status = "Atendido" if "sim" in resp_l else "Não Atendido"
        elif qid == "8.1": metas = "1.5, 11.5, 16.6"; status = f"{calcular_percentual_checklist(resp, 6):.1f}% Atendido"
        elif qid == "8.1.1": metas = "1.5, 11.5, 16.6"; status = "Atendido" if "sim" in resp_l else "Não Atendido"
        elif qid == "8.1.1.1": metas = "1.5, 11.5, 16.6"; status = "Atendido" if "sim" in resp_l else "Não Atendido"
        elif qid == "8.2": metas = "1.5, 11.5, 16.6"; status = "Atendido" if "sim" in resp_l else "Não Atendido"
        elif qid == "9.0": metas = "1.5, 11.5, 16.6"; status = "Atendido" if ("todas as escolas" in resp_l or "maior parte" in resp_l) else "Não Atendido"
        elif qid in ["10", "10.0"]: metas = "11.2, 16.6"; status = "Atendido" if "sim" in resp_l else "Não Atendido"
        elif qid in ["11", "11.0"]: metas = "11.2, 16.6"; status = "Atendido" if "sim" in resp_l else "Não Atendido"
        elif qid == "11.1": metas = "11.2, 16.6"; status = "Atendido" if "sim" in resp_l else "Não Atendido"
        elif qid == "12.0": metas = "11.2, 17.0"; status = "Atendido" if "sim" in resp_l else "Não Atendido"
        elif qid == "12.1.3": metas = "11.2, 17.0"; status = "Atendido" if "sim" in resp_l else "Não Atendido"
        elif qid in ["13", "13.0"]: metas = "11.2, 11.7, 12.5"; status = "Atendido" if "sim" in resp_l else "Não Atendido"
        elif qid == "14.0": metas = "11.2, 17.14"; status = "Atendido" if "sim" in resp_l else "Não Atendido"
        elif qid in ["15", "15.0"]: metas = "11.2, 17.14"; status = "Atendido" if "sim" in resp_l else "Não Atendido"
        elif qid in ["16", "16.0"]: metas = "11.2, 17.14"; status = "Atendido" if "sim" in resp_l else "Não Atendido"

        if metas: analise_ods.append({"qid": qid, "status": status, "metas": metas, "resp": resp[:50]})

    if analise_ods:
        data_ods = [["Quesito", "Resposta Informada", "Vínculo Metas ODS", "Status de Cumprimento"]]
        style_td_ods = ParagraphStyle('TdOds', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, alignment=1)
        for item in sorted(analise_ods, key=lambda x: [float(i) if i.replace('.','',1).isdigit() else 999 for i in x['qid'].split('.')]):
            st_txt = item["status"]
            if "Não Atendido" in st_txt: st_p = Paragraph(f"<font color='#dc3545'><b>{st_txt}</b></font>", style_td_ods)
            elif "Atendido" in st_txt and "%" not in st_txt: st_p = Paragraph(f"<font color='#28a745'><b>{st_txt}</b></font>", style_td_ods)
            else: st_p = Paragraph(f"<font color='#007bff'><b>{st_txt}</b></font>", style_td_ods)
            data_ods.append([item["qid"], Paragraph(item["resp"], styles["Normal"]), item["metas"], st_p])
        tabela_ods = Table(data_ods, colWidths=[60, 200, 115, 110])
        tabela_ods.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f9d58")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke), ("ALIGN", (0, 0), (0, -1), "CENTER"), ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#0f9d58")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        elements.append(tabela_ods)
        elements.append(Spacer(1, 15))

    # -------------------------------------------------------------------------
    # 📊 6. SÉRIE HISTÓRICA DO I-CIDADE (CONSOLIDADO FINAL)
    # -------------------------------------------------------------------------
    elements.append(Spacer(1, 10))

    anos_serie = [2023, 2024, 2025, 2026, 2027, 2028, 2029, 2030]
    valores_serie = []
    for a in anos_serie:
        if a == ano_atual: valores_serie.append(nota_atual)
        elif a in all_data:
            valores_serie.append(float(sum(info_h.get("pontos", 0) for qid_h, info_h in all_data[a].items() if isinstance(info_h, dict) and not qid_h.startswith("COM_"))))
        else: valores_serie.append(0.0)

    # Configuração do Gráfico
    desenho_grafico = Drawing(480, 165)
    bc = VerticalBarChart()
    bc.x = 45; bc.y = 25; bc.height = 110; bc.width = 410
    bc.data = [valores_serie]
    bc.categoryAxis.categoryNames = [str(a) for a in anos_serie]
    bc.categoryAxis.labels.fontSize = 9; bc.categoryAxis.labels.fontName = 'Helvetica-Bold'; bc.categoryAxis.labels.dy = -10
    
    bc.valueAxis.valueMin = 0; bc.valueAxis.valueMax = 1000; bc.valueAxis.valueStep = 200; bc.valueAxis.labels.fontSize = 8
    
    # 🔥 ATIVAÇÃO DOS RÓTULOS (PONTUAÇÃO EM CIMA DA BARRA)
    bc.barLabels.nudge = 8
    bc.barLabels.fontSize = 8
    bc.barLabels.fontName = 'Helvetica-Bold'
    bc.barLabelFormat = '%.1f'  # Formato com uma casa decimal
    
    bc.bars[0].fillColor = colors.HexColor("#1b4f72")
    bc.bars[0].strokeColor = colors.HexColor("#2c3e50")
    bc.bars[0].strokeWidth = 0.5

    # Título do Gráfico solicitado
    desenho_grafico.add(String(240, 150, "Série Histórica do I-cidade", textAnchor='middle', fontName='Helvetica-Bold', fontSize=12, fillColor=colors.HexColor("#2c3e50")))
    desenho_grafico.add(bc)
    
    elements.append(desenho_grafico)

    # Fechamento do documento
    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()

# =============================================================================
# 4. SIDEBAR
# =============================================================================

def zerar_questionario(ano):
    """Deleta todas as respostas do ano selecionado."""
    with get_connection() as conn:
        conn.execute("DELETE FROM respostas WHERE ano = ?", (ano,))
        conn.commit()

def render_sidebar():
    st.sidebar.title("🛠️ Painel de Controle")
    anos = [2023, 2024, 2025, 2026, 2027, 2028, 2029, 2030]
    ano_sel = st.sidebar.selectbox("Ano de Referência:", anos, key="ano_referencia_global")

    res_data = load_respostas(ano_sel)
    total_pts = sum(item.get("pontos", 0) for item in res_data.values())

    if total_pts <= 500:   faixa, cor = "C",  "red"
    elif total_pts <= 599: faixa, cor = "C+", "orange"
    elif total_pts <= 749: faixa, cor = "B",  "#d4d400"
    elif total_pts <= 899: faixa, cor = "B+", "lightgreen"
    else:                  faixa, cor = "A",  "green"

    st.sidebar.metric("Pontuação Total", f"{total_pts} pts")
    st.sidebar.markdown(
        f"**Faixa:** <span style='color:{cor}; font-size:20px; font-weight:bold;'>{faixa}</span>",
        unsafe_allow_html=True
    )

    st.sidebar.divider()
    
    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("📄 Gerar Relatório PDF"):
            pdf = gerar_relatorio_pdf(res_data, ano_sel, total_pts, faixa)
            st.download_button(
                "⬇️ Baixar PDF", pdf, f"Relatorio_{ano_sel}.pdf", "application/pdf"
            )
    
    with col2:
        if st.button("🔄 Zerar Questionário", help="Limpar todas as respostas do ano selecionado"):
            zerar_questionario(ano_sel)
            st.success(f"✅ Questionário de {ano_sel} foi zerado!")
            st.rerun()

    return total_pts, res_data, ano_sel

# =============================================================================
# 5. GRÁFICOS COMPARATIVOS
# =============================================================================

def get_faixa(total):
    if total <= 500:  return "C"
    if total <= 599:  return "C+"
    if total <= 749:  return "B"
    if total <= 899:  return "B+"
    return "A"


def calcular_pontos_por_categoria(res_data):
    resultado = {}
    for cat_key, cat_info in CATEGORIAS_MAP.items():
        resultado[cat_key] = sum(
            res_data.get(qid, {}).get("pontos", 0) for qid in cat_info["qids"]
        )
    return resultado


def calcular_max_por_categoria():
    resultado = {}
    for cat_key, cat_info in CATEGORIAS_MAP.items():
        resultado[cat_key] = sum(PONTUACOES_MAX.get(qid, 0) for qid in cat_info["qids"])
    return resultado


def grafico_comparativo_total(all_data):
    anos = sorted(all_data.keys())
    totais, faixas, cores = [], [], []
    for ano in anos:
        res = all_data[ano]
        total = sum(v.get("pontos", 0) for k, v in res.items() if not k.startswith("COM_"))
        faixa = get_faixa(total)
        totais.append(total)
        faixas.append(faixa)
        cores.append(FAIXA_CORES[faixa])

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[str(a) for a in anos],
        y=totais,
        marker_color=cores,
        text=[f"{t} pts<br>Faixa {f}" for t, f in zip(totais, faixas)],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>%{text}<extra></extra>",
    ))
    for y_val, label, cor in [
        (500, "C→C+", "#f97316"), (600, "C+→B", "#eab308"),
        (750, "B→B+", "#22c55e"), (900, "B+→A", "#16a34a")
    ]:
        fig.add_hline(y=y_val, line_dash="dash", line_color=cor,
                      annotation_text=label, annotation_position="right")
    fig.update_layout(
        title="Pontuação Total por Ano",
        xaxis_title="Ano", yaxis_title="Pontos",
        plot_bgcolor="white", paper_bgcolor="white",
        showlegend=False, height=400,
    )
    return fig


def grafico_evolucao_categorias(all_data):
    anos = sorted(all_data.keys())
    CORES_CAT = ["#1e3a5f","#0ea5e9","#22c55e","#f97316","#ef4444","#8b5cf6","#ec4899","#6b7280"]
    fig = go.Figure()
    for idx, (cat_key, cat_info) in enumerate(CATEGORIAS_MAP.items()):
        valores = [
            sum(all_data.get(ano, {}).get(qid, {}).get("pontos", 0) for qid in cat_info["qids"])
            for ano in anos
        ]
        fig.add_trace(go.Scatter(
            x=[str(a) for a in anos], y=valores,
            mode="lines+markers", name=cat_info["label"],
            line=dict(color=CORES_CAT[idx % len(CORES_CAT)], width=2),
            marker=dict(size=7),
        ))
    fig.update_layout(
        title="Evolução por Categoria ao Longo dos Anos",
        xaxis_title="Ano", yaxis_title="Pontos",
        plot_bgcolor="white", paper_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=-0.4),
        height=450,
    )
    return fig


def grafico_radar_categorias(res_data, ano):
    maximos = calcular_max_por_categoria()
    pontos  = calcular_pontos_por_categoria(res_data)
    labels  = [CATEGORIAS_MAP[k]["label"] for k in CATEGORIAS_MAP]
    valores_pct = [
        round(max(0, pontos.get(k, 0) / maximos[k] * 100), 1) if maximos[k] > 0 else 0
        for k in CATEGORIAS_MAP
    ]
    labels_fechado  = labels + [labels[0]]
    valores_fechado = valores_pct + [valores_pct[0]]
    fig = go.Figure(go.Scatterpolar(
        r=valores_fechado, theta=labels_fechado,
        fill="toself", fillcolor="rgba(30,58,95,0.15)",
        line=dict(color="#1e3a5f", width=2),
        hovertemplate="%{theta}: %{r:.1f}%<extra></extra>",
    ))
    fig.update_layout(
        title=f"Radar de Categorias — {ano}",
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=False, height=420, paper_bgcolor="white",
    )
    return fig


def grafico_quesitos_barra(res_data, ano):
    qids_pontuaveis = sorted([q for q, v in PONTUACOES_MAX.items() if v > 0])
    qids, obtido, maximo, cores = [], [], [], []
    for qid in qids_pontuaveis:
        pts = res_data.get(qid, {}).get("pontos", 0)
        mx  = PONTUACOES_MAX[qid]
        qids.append(qid)
        obtido.append(pts)
        maximo.append(mx)
        if pts == mx:   cores.append("#16a34a")
        elif pts < 0:   cores.append("#ef4444")
        elif pts == 0:  cores.append("#9ca3af")
        else:           cores.append("#0ea5e9")

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Máximo", x=maximo, y=qids, orientation="h",
        marker_color="rgba(200,200,200,0.35)", hoverinfo="skip",
    ))
    fig.add_trace(go.Bar(
        name="Obtido", x=obtido, y=qids, orientation="h",
        marker_color=cores,
        hovertemplate="<b>%{y}</b><br>Obtido: %{x} pts<extra></extra>",
    ))
    fig.update_layout(
        title=f"Pontuação por Quesito — {ano}",
        barmode="overlay", xaxis_title="Pontos",
        plot_bgcolor="white", paper_bgcolor="white",
        height=max(500, len(qids) * 22),
        legend=dict(orientation="h"),
        yaxis=dict(autorange="reversed"),
    )
    return fig


def grafico_pontos_por_ano(all_data):
    """Gráfico de barras vertical com pontos totais por ano."""
    anos = sorted(all_data.keys())
    totais = []
    cores = []
    
    for ano in anos:
        res = all_data[ano]
        total = sum(v.get("pontos", 0) for k, v in res.items() if not k.startswith("COM_"))
        totais.append(total)
        
        # Definir cor baseado na faixa
        if total <= 500:   cores.append("#ef4444")  # C - Vermelho
        elif total <= 599: cores.append("#f97316")  # C+ - Laranja
        elif total <= 749: cores.append("#eab308")  # B - Amarelo
        elif total <= 899: cores.append("#22c55e")  # B+ - Verde Claro
        else:              cores.append("#16a34a")  # A - Verde
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[str(a) for a in anos],
        y=totais,
        marker_color=cores,
        text=[f"{t} pts" for t in totais],
        textposition="outside",
        hovertemplate="<b>Ano: %{x}</b><br>Pontos: %{y}<extra></extra>",
    ))
    
    fig.update_layout(
        title="Pontuação Total por Ano",
        xaxis_title="Ano",
        yaxis_title="Pontos",
        plot_bgcolor="white",
        paper_bgcolor="white",
        showlegend=False,
        height=400,
    )
    
    return fig

def render_graficos(res_data_atual, ano_sel):
    st.header("📊 Gráfico de Pontuação")
    
    all_data = get_all_years_data()
    
    if not all_data:
        st.info("Nenhum dado registrado ainda. Preencha os quesitos para ver o gráfico.")
        return

    st.plotly_chart(grafico_pontos_por_ano(all_data), use_container_width=True)

# =============================================================================
# 6. FORMULÁRIO PRINCIPAL
# =============================================================================

def mostrar_formulario_cidade():
    total_pts, res_data, ano_sel = render_sidebar()
    st.title(f"🏙️ Preenchimento do IEG-M - {ano_sel}")

    st.markdown("""
        <style>
        .quesito-card {
            background-color: #f8f9fa;
            padding: 20px;
            border-left: 6px solid #2c3e50;
            border-radius: 8px;
            margin-bottom: 20px;
            border: 1px solid #ddd;
        }
        </style>
    """, unsafe_allow_html=True)

    r10 = res_data.get("1.0", {}).get("valor", "")

    # -------------------------------------------------------------------------
    # ABAS PRINCIPAIS — adicione aqui suas abas de questionário + gráficos
    # -------------------------------------------------------------------------
    aba_questionario, aba_graficos = st.tabs(["📋 Questionário", "📊 Gráficos"])

    with aba_questionario:
        st.info("Preencha os quesitos do formulário aqui.")
        # ← cole aqui o restante do seu formulário original

    with aba_graficos:
        render_graficos(res_data, ano_sel)
    
    # -------------------------------------------------------------------------
    # --- QUESITO 1.0 (LINK AZUL ATIVO + DISPARO INTELIGENTE DE MODAL) ---
    # -------------------------------------------------------------------------
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("QUESITO 1.0")
    st.write("**Foi criada a Coordenadoria Municipal de Proteção e Defesa Civil-COMPDEC ou órgão similar responsável pela execução, coordenação e mobilização de todas as ações de defesa civil no município?**")
    
    d10 = res_data.get("1.0", {"valor": "", "link": "", "pontos": 0.0})
    opc10 = ["Sim (40 pts)", "Não (00 pts)"]
    idx10 = opc10.index(d10["valor"]) if d10["valor"] in opc10 else None
    
    col1, col2 = st.columns([1, 2])
    with col1:
        r10_input = st.radio("Selecione:", opc10, index=idx10, key=f"radio_q10_{ano_sel}")
    with col2:
        l10 = st.text_area("Link/Evidência:", value=d10.get("link", ""), key=f"link_q10_{ano_sel}", height=100)
        
        # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
        links_10_atuais = re.findall(r'(https?://[^\s]+)', l10)
        if links_10_atuais:
            st.markdown(f"🔗 **Link Ativo:** [{links_10_atuais[0]}]({links_10_atuais[0]})")

    # Processamento do salvamento e verificação do modal para o Quesito 1.0
    if r10_input and (r10_input != d10["valor"] or l10 != d10["link"]):
        pts_10 = 40.0 if "Sim" in r10_input else 0.0
        save_resp("1.0", r10_input, pts_10, l10)
        
        # SÓ avalia o modal se houver de fato um link capturado no texto atual
        if links_10_atuais:
            links_10_antigos = re.findall(r'(https?://[^\s]+)', d10["link"])
            # Dispara APENAS se não havia link antes ou se o link atual mudou
            if not links_10_antigos or links_10_atuais[0] != links_10_antigos[0]:
                modal_aviso_link("1.0", links_10_atuais)
            else:
                st.rerun()
        else:
            # Se for texto puro ou remoção de link, pula o modal e recarrega direto
            st.rerun()
        
    bloco_comentarios("1.0", res_data)
    st.markdown("</div>", unsafe_allow_html=True)

    r10 = r10_input

    # -------------------------------------------------------------------------
    # --- QUESITOS CONDICIONAIS 1.1 e 1.2 (LINK AZUL E MODAL INTELIGENTE) ---
    # -------------------------------------------------------------------------
    if r10 and "Sim" in r10:
        config_condicionais = [
            ("1.1", "**Informe o Instrumento normativo, Número e Data da publicação da criação da COMPDEC ou órgão similar:**"), 
            ("1.2", "**Informe a página eletrônica (link na internet) do instrumento normativo que criou a COMPDEC ou órgão similar:**")
        ]
        
        for qid, txt in config_condicionais:
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader(f"QUESITO {qid}")
            
            dq = res_data.get(qid, {"valor": "", "link": "", "pontos": 0.0})
            v_q = st.text_input(txt, value=dq["valor"], key=f"v{qid}_{ano_sel}")
            
            # MOSTRA O LINK AZUL SE O USER DIGITAR UM URL NO TEXT_INPUT
            links_cond_atuais = re.findall(r'(https?://[^\s]+)', v_q)
            if links_cond_atuais:
                st.markdown(f"🔗 **Link Ativo:** [{links_cond_atuais[0]}]({links_cond_atuais[0]})")
            
            # Validação inteligente estruturada para evitar spam em texto comum
            if v_q != dq["valor"]:
                save_resp(qid, v_q, 0.0, "")
                
                # SÓ tenta avaliar o modal se a regex achar um link válido digitado
                if links_cond_atuais:
                    links_cond_antigos = re.findall(r'(https?://[^\s]+)', dq["valor"])
                    # Dispara APENAS se for uma URL nova de fato
                    if not links_cond_antigos or links_cond_atuais[0] != links_cond_antigos[0]:
                        modal_aviso_link(qid, links_cond_atuais)
                    else:
                        st.rerun()
                else:
                    # É texto puro/comum, não abre nada de modal e dá rerun funcional
                    st.rerun()
                
            bloco_comentarios(qid, res_data)
            st.markdown('</div>', unsafe_allow_html=True)

        # -------------------------------------------------------------------------
        # --- QUESITO 1.3 ---------------------------------------------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 1.3")
        st.write("**A COMPDEC ou órgão similar está associada ou subordinada a qual secretaria/diretoria?**")
        d13 = res_data.get("1.3", {"valor": "", "pontos": 0.0})
        opts13 = {
            "Gabinete do Prefeito (05 pts)": 5.0, 
            "Segurança Pública (00 pts)": 0.0, 
            "Controladoria (00 pts)": 0.0, 
            "Outra (00 pts)": 0.0
        }
        lista13 = list(opts13.keys())
        idx13 = lista13.index(d13["valor"]) if d13["valor"] in lista13 else None
        r13 = st.radio("Selecione:", lista13, index=idx13, key=f"q13_{ano_sel}")
        
        if r13 is not None and r13 != d13["valor"]:
            save_resp("1.3", r13, opts13[r13], "")
            st.rerun()
            
        bloco_comentarios("1.3", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # --- QUESITO 1.5 (Condicional se Não) -------------------------------------
    # -------------------------------------------------------------------------
    elif r10 and "Não" in r10:
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 1.5")
        st.write("**Motivo da COMPDEC não ter sido instituída:**")
        d15 = res_data.get("1.5", {"valor": "", "pontos": 0.0})
        opts15 = ["Instrumento normativo em elaboração", "Falta de estrutura", "Outros"]
        idx15 = opts15.index(d15["valor"]) if d15["valor"] in opts15 else None
        r15 = st.radio("Motivo:", opts15, index=idx15, key=f"q15_{ano_sel}")
        
        if r15 is not None and r15 != d15["valor"]:
            save_resp("1.5", r15, 0.0, "")
            st.rerun()
            
        bloco_comentarios("1.5", res_data)
        st.markdown("</div>", unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # --- QUESITO 1.4 ---------------------------------------------------------
    # -------------------------------------------------------------------------
    if r10 and "Sim" in r10:
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 1.4")
        st.write("**Os órgãos e entidades da administration pública municipal atuam de forma sistêmica, articulados com a COMPDEC, nas ações de prevenção, mitigação, preparação, resposta e recuperação de acordo com a Política Nacional de Proteção e Defesa Civil - PNPDEC?**")

        d14 = res_data.get("1.4", {"valor": None, "link": "", "pontos": 0.0})
        opts14 = {
            "Sim, inclusive com a participação de entidades privadas e da comunidade (50 pts)": 50.0,
            "Sim, com participação de entidades privadas (20 pts)": 20.0,
            "Sim, com participação da comunidade (20 pts)": 20.0,
            "Sim, apenas com representantes da administração municipal (10 pts)": 10.0,
            "Não atuam de forma sistêmica (00 pts)": 0.0
        }
        lista_opts14 = list(opts14.keys())
        idx14 = lista_opts14.index(d14["valor"]) if d14["valor"] in lista_opts14 else None

        r14 = st.radio("Nível de atuação:", lista_opts14, index=idx14, key=f"q14_{ano_sel}")

        if r14 is not None and r14 != d14["valor"]:
            save_resp("1.4", r14, opts14[r14], "")
            st.rerun()

        bloco_comentarios("1.4", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # --- QUESITO 2.0 (LINK AZUL ATIVO + DISPARO INTELIGENTE DE MODAL) -------
    # -------------------------------------------------------------------------
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("QUESITO 2.0")
    st.write("**Sobre treinamento e capacitação sobre Proteção e Defesa Civil, a Prefeitura capacita seus agentes para ações municipais de Defesa Civil?**")

    d20 = res_data.get("2.0", {"valor": None, "link": "", "pontos": 0.0})
    opcoes_20 = ["Sim (20 pts)", "Não (00 pts)"]
    idx20 = opcoes_20.index(d20["valor"]) if d20["valor"] in opcoes_20 else None

    col1, col2 = st.columns([1, 2])
    with col1:
        r20_input = st.radio("Resposta 2.0:", opcoes_20, index=idx20, key=f"q20_{ano_sel}")
    with col2:
        l20 = st.text_area("Justificativa e Evidência (2.0):", value=d20["link"], key=f"l20_{ano_sel}", height=100)
        
        # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
        links_20_atuais = re.findall(r'(https?://[^\s]+)', l20)
        if links_20_atuais:
            st.markdown(f"🔗 **Link Ativo:** [{links_20_atuais[0]}]({links_20_atuais[0]})")

    # SÓ dispara o modal se o link mudou E se o link atual for inédito comparado ao banco
    if l20 != d20["link"]:
        links_20_antigos = re.findall(r'(https?://[^\s]+)', d20["link"])
        if links_20_atuais and (not links_20_antigos or links_20_atuais[0] != links_20_antigos[0]):
            modal_aviso_link("2.0", links_20_atuais)

    # Salva se houver qualquer alteração real nos dados
    if r20_input and (r20_input != d20["valor"] or l20 != d20["link"]):
        pts_20 = 20.0 if "Sim" in r20_input else 0.0
        save_resp("2.0", r20_input, pts_20, l20)
        st.rerun()

    bloco_comentarios("2.0", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # Atualiza a variável de controle local para os quesitos filhos (como o 2.1 que você já tem aí)
    r20 = r20_input

    # -------------------------------------------------------------------------
    # --- QUESITO 2.1 (CÁLCULO DE DATA DINÂMICO + LINK ATIVO + MODAL) --------
    # -------------------------------------------------------------------------
    # A variável r20 vem do bloco anterior
    if r20 and "Sim" in r20:
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 2.1")
        st.write("**Qual a data da última capacitação dos agentes municipais para ações de Defesa Civil?**")

        # Regra de pontuação com textos 100% dinâmicos baseados no ano selecionado
        st.info(f"""
        **Regra de Pontuação:**
        * ✅ **Data a partir de 01/01/{ano_sel}:** 30 pontos.
        * ⚠️ **Data até 31/12/{ano_sel - 1}:** 00 pontos.
        * 🚫 **Capacitações em {ano_sel + 1}:** Não pontuam (00 pontos).
        """)

        # 1. Busca os dados do banco
        d21 = res_data.get("2.1", {"valor": None, "pontos": 0.0, "link": ""})

        col_d21, col_j21 = st.columns([1, 2])

        with col_d21:
            try:
                dt_i = datetime.strptime(d21["valor"], '%Y-%m-%d').date() if d21["valor"] else date(ano_sel, 1, 1)
            except:
                dt_i = date(ano_sel, 1, 1)

            data_sel = st.date_input(
                "Selecione a data:",
                value=dt_i,
                key=f"dt21_{ano_sel}",
                format="DD/MM/YYYY"
            )

            # --- CÁLCULO AUTOMÁTICO DINÂMICO DE VERDADE ---
            # Deve ser maior ou igual a 01/01 do ano selecionado E não pode ser do ano seguinte (superior)
            if data_sel >= date(ano_sel, 1, 1) and data_sel.year == ano_sel:
                pts21 = 30.0
            else:
                pts21 = 0.0

            data_formatada = data_sel.strftime('%d/%m/%Y')
            if pts21 == 30.0:
                st.success(f"Pontuação: 30 pts ({data_formatada})")
            else:
                st.warning(f"Pontuação: 00 pts ({data_formatada})")

        with col_j21:
            l21 = st.text_area(
                "Justificativa e Evidência (2.1):",
                value=d21["link"],
                key=f"l21_{ano_sel}",
                placeholder="Cole o link do certificado ou portaria aqui...",
                height=100
            )
            
            # RENDERIZA O LINK AZUL ATIVO SE EXISTIR NA TELA
            links_21_atuais = re.findall(r'(https?://[^\s]+)', l21)
            if links_21_atuais:
                st.markdown(f"🔗 **Link Ativo:** [{links_21_atuais[0]}]({links_21_atuais[0]})")

        # --- MOTOR DE DISPARO INTELIGENTE DO MODAL ---
        if l21 != d21["link"]:
            links_21_antigos = re.findall(r'(https?://[^\s]+)', d21["link"])
            # Só estoura o modal na tela se for um link inédito
            if links_21_atuais and (not links_21_antigos or links_21_atuais[0] != links_21_antigos[0]):
                modal_aviso_link("2.1", links_21_atuais)

        # 4. SALVAMENTO NO BANCO
        valor_para_salvar = str(data_sel)

        if valor_para_salvar != d21["valor"] or l21 != d21["link"]:
            save_resp("2.1", valor_para_salvar, pts21, l21)
            st.rerun()

        bloco_comentarios("2.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # --- QUESITO 2.2 (MÚLTIPLA ESCOLA + LINK AZUL + MODAL INTELIGENTE) -------
    # -------------------------------------------------------------------------
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("QUESITO 2.2")
    st.write("**A Prefeitura Municipal ofereceu cursos/treinamento sobre Proteção e Defesa Civil para qual público?**")

    d22 = res_data.get("2.2", {"valor": "[]", "pontos": 0.0, "link": ""})
    valor_salvo_22 = d22["valor"]

    col_c22, col_j22 = st.columns([1, 2])
    
    with col_c22:
        c1 = st.checkbox("Para escolas – 05 pts", value="Escolas" in valor_salvo_22, key=f"c22a_{ano_sel}")
        c2 = st.checkbox("Para outras secretarias / entidades municipais – 03 pts", value="Secretarias" in valor_salvo_22, key=f"c22b_{ano_sel}")
        c3 = st.checkbox("Para munícipes ou empresas – 02 pts", value="Munícipes" in valor_salvo_22, key=f"c22c_{ano_sel}")
        c4 = st.checkbox("Não ofereceu nenhum curso/treinamento no ano – 00 pts", value="Nenhum" in valor_salvo_22, key=f"c22d_{ano_sel}")

    # Lógica de cálculo acumulado
    p22 = 0.0
    sel22 = []
    if c4:
        sel22 = ["Nenhum"]
        p22 = 0.0
    else:
        if c1: p22 += 5.0; sel22.append("Escolas")
        if c2: p22 += 3.0; sel22.append("Secretarias")
        if c3: p22 += 2.0; sel22.append("Munícipes")

    with col_j22:
        l22 = st.text_area("Evidência 2.2:", value=d22["link"], key=f"l22_{ano_sel}", height=100)
        
        # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
        links_22_atuais = re.findall(r'(https?://[^\s]+)', l22)
        if links_22_atuais:
            st.markdown(f"🔗 **Link Ativo:** [{links_22_atuais[0]}]({links_22_atuais[0]})")

    # DISPARO DO MODAL
    if l22 != d22["link"]:
        links_22_antigos = re.findall(r'(https?://[^\s]+)', d22["link"])
        if links_22_atuais and (not links_22_antigos or links_22_atuais[0] != links_22_antigos[0]):
            modal_aviso_link("2.2", links_22_atuais)

    # Salvamento automático
    if str(sel22) != d22["valor"] or l22 != d22["link"]:
        if sel22 or l22 != "" or d22["valor"] != "[]":
            save_resp("2.2", str(sel22), p22, l22)
            st.rerun()

    st.info(f"Pontuação Acumulada 2.2: {p22} pts")
    bloco_comentarios("2.2", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

# -------------------------------------------------------------------------
    # --- QUESITO 3.0 (LINK AZUL ATIVO + MODAL INTELIGENTE) -------------------
    # -------------------------------------------------------------------------
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("QUESITO 3.0")
    st.write("**O Município realiza ações para estabelecer a participação de entidades privadas, associações de voluntários, clubes de serviços, organizações não governamentais e associações de classe e comunitárias nas ações de proteção e defesa civil?**") 

    d30 = res_data.get("3.0", {"valor": None, "pontos": 0.0, "link": ""})
    opces_30 = ["Sim – 10 pts", "Não – 00 pts"]
    idx30 = opces_30.index(d30["valor"]) if d30["valor"] in opces_30 else None

    col1, col2 = st.columns([1, 2])
    with col1:
        r30_input = st.radio("Escolha 3.0:", opces_30, index=idx30, key=f"q30_{ano_sel}")
    with col2:
        l30 = st.text_area("Evidência 3.0:", value=d30["link"], key=f"l30_{ano_sel}", height=100)
        
        # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
        links_30_atuais = re.findall(r'(https?://[^\s]+)', l30)
        if links_30_atuais:
            st.markdown(f"🔗 **Link Ativo:** [{links_30_atuais[0]}]({links_30_atuais[0]})")

    # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 3.0
    if r30_input is not None and (r30_input != d30["valor"] or l30 != d30["link"]):
        pts30 = 10.0 if "Sim" in r30_input else 0.0
        save_resp("3.0", r30_input, pts30, l30)
        
        # SÓ avalia o modal se houver de fato um link capturado no texto atual
        if links_30_atuais:
            links_30_antigos = re.findall(r'(https?://[^\s]+)', d30["link"])
            if not links_30_antigos or links_30_atuais[0] != links_30_antigos[0]:
                modal_aviso_link("3.0", links_30_atuais)
            else:
                st.rerun()
        else:
            st.rerun()

    bloco_comentarios("3.0", res_data)
    st.markdown('</div>', unsafe_allow_html=True)


    # -------------------------------------------------------------------------
    # --- QUESITO 3.1 - AÇÕES REALIZADAS (MÚLTIPLA ESCOLHA) ------------------
    # -------------------------------------------------------------------------
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("QUESITO 3.1")
    st.write("**Assinale quais ações foram realizadas:**")

    d31 = res_data.get("3.1", {"valor": "[]", "pontos": 0.0, "link": ""})

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

        # Monta a lista dinâmica marcando o que já estava persistido
        selecionados_31 = []
        for opcao in opcoes_31:
            if st.checkbox(opcao, value=opcao in d31["valor"], key=f"check_31_{opcao}_{ano_sel}"):
                selecionados_31.append(opcao)

        pts31 = 0.0  # Quesito apenas informativo/estrutural, pontua no filho

    with col_j31:
        l31 = st.text_area("Evidências das ações (3.1):", value=d31["link"], key=f"l31_{ano_sel}", height=120)
        
        # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
        links_31_atuais = re.findall(r'(https?://[^\s]+)', l31)
        if links_31_atuais:
            st.markdown(f"🔗 **Link Ativo:** [{links_31_atuais[0]}]({links_31_atuais[0]})")

    # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 3.1
    if str(selecionados_31) != d31["valor"] or l31 != d31["link"]:
        if selecionados_31 or l31 != "" or d31["valor"] != "[]":
            save_resp("3.1", str(selecionados_31), pts31, l31)
            
            # SÓ avalia o modal se houver de fato um link capturado no texto atual
            if links_31_atuais:
                links_31_antigos = re.findall(r'(https?://[^\s]+)', d31["link"])
                if not links_31_antigos or links_31_atuais[0] != links_31_antigos[0]:
                    modal_aviso_link("3.1", links_31_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

    bloco_comentarios("3.1", res_data)
    st.markdown('</div>', unsafe_allow_html=True)


    # -------------------------------------------------------------------------
    # --- QUESITO 3.1.1 - DATA DE TREINAMENTO DINÂMICA ------------------------
    # -------------------------------------------------------------------------
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("QUESITO 3.1.1")
    st.write("**Qual a data do último treinamento de associações de voluntários?**")

    # Textos informativos recalculados dinamicamente com base no ano ativo da Sidebar
    st.info(f"""
    **Fórmula de Cálculo:**
    * 📅 **Até 31/12/{ano_sel - 1}:** 00 pontos.
    * 📅 **A partir de 01/01/{ano_sel}:** 10 pontos.
    * 🚫 **Observação:** Treinamentos em {ano_sel + 1} não pontuam.
    """)

    d311 = res_data.get("3.1.1", {"valor": None, "pontos": 0.0, "link": ""})

    col_d311, col_j311 = st.columns([1, 2])
    with col_d311:
        try:
            dt_i_311 = datetime.strptime(d311["valor"], '%Y-%m-%d').date() if d311["valor"] else date(ano_sel, 1, 1)
        except:
            dt_i_311 = date(ano_sel, 1, 1)

        data_sel_311 = st.date_input(
            "Data do treinamento:",
            value=dt_i_311,
            key=f"dt311_{ano_sel}",
            format="DD/MM/YYYY"
        )

        # --- RECONSTRUÇÃO DA LÓGICA MATEMÁTICA DINÂMICA ---
        # Pontua apenas se for no ano corrente selecionado
        if data_sel_311 >= date(ano_sel, 1, 1) and data_sel_311.year == ano_sel:
            pts311 = 10.0
        else:
            pts311 = 0.0

        data_br_311 = data_sel_311.strftime('%d/%m/%Y')
        if pts311 == 10.0:
            st.success(f"Pontuação: 10 pts ({data_br_311})")
        else:
            st.warning(f"Pontuação: 00 pts ({data_br_311})")

    with col_j311:
        l311 = st.text_area("Justificativa (3.1.1):", value=d311["link"], key=f"l311_{ano_sel}", height=100)
        
        # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
        links_311_atuais = re.findall(r'(https?://[^\s]+)', l311)
        if links_311_atuais:
            st.markdown(f"🔗 **Link Ativo:** [{links_311_atuais[0]}]({links_311_atuais[0]})")

    # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 3.1.1
    if d311["valor"] is not None or l311 != "":
        if str(data_sel_311) != d311["valor"] or l311 != d311["link"]:
            save_resp("3.1.1", str(data_sel_311), pts311, l311)
            
            # SÓ avalia o modal se houver de fato um link capturado no campo de texto justificativa
            if links_311_atuais:
                links_311_antigos = re.findall(r'(https?://[^\s]+)', d311["link"])
                if not links_311_antigos or links_311_atuais[0] != links_311_antigos[0]:
                    modal_aviso_link("3.1.1", links_311_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

    bloco_comentarios("3.1.1", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

   # -------------------------------------------------------------------------
    # --- QUESITO 4.0 (LINK AZUL ATIVO + DISPARO INTELIGENTE DE MODAL) -------
    # -------------------------------------------------------------------------
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("QUESITO 4.0")
    st.write("**O Município recebeu a Carta Geotécnica de Suscetibilidade, Aptidão à Urbanização e Risco?**")

    d40 = res_data.get("4.0", {"valor": None, "pontos": 0.0, "link": ""})
    col_r40, col_j40 = st.columns([1, 2])
    opcoes_40 = ["Sim", "Não"]

    with col_r40:
        idx40 = opcoes_40.index(d40["valor"]) if d40["valor"] in opcoes_40 else None
        r40 = st.radio("Resposta 4.0:", opcoes_40, index=idx40, key=f"q40_r_{ano_sel}")
        pts40 = 10.0 if r40 == "Sim" else 0.0

    with col_j40:
        l40 = st.text_area("Evidência (4.0):", value=d40["link"], key=f"l40_{ano_sel}", height=100)
        
        # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
        links_40_atuais = re.findall(r'(https?://[^\s]+)', l40)
        if links_40_atuais:
            st.markdown(f"🔗 **Link Ativo:** [{links_40_atuais[0]}]({links_40_atuais[0]})")

    # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 4.0
    if r40 is not None and (r40 != d40["valor"] or l40 != d40["link"]):
        save_resp("4.0", r40, pts40, l40)
        
        # SÓ avalia o modal se houver de fato um link capturado no texto atual
        if links_40_atuais:
            links_40_antigos = re.findall(r'(https?://[^\s]+)', d40["link"])
            if not links_40_antigos or links_40_atuais[0] != links_40_antigos[0]:
                modal_aviso_link("4.0", links_40_atuais)
            else:
                st.rerun()
        else:
            st.rerun()

    bloco_comentarios("4.0", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # --- QUESITO 4.1 (CONDICIONAL SE SIM - MÚLTIPLA ESCOLA) ------------------
    # -------------------------------------------------------------------------
    if r40 == "Sim":
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 4.1")
        st.write("**Assinale quais os tipos de ameaças potenciais identificadas na Carta Geotécnica:**")

        d41 = res_data.get("4.1", {"valor": "[]", "pontos": 0.0, "link": ""})
        col_c41, col_j41 = st.columns([1, 2])

        with col_c41:
            ameacas_cobrade = ["Riscos Geológicos", "Riscos Hidrológicos", "Riscos Meteorológicos",
                               "Riscos Climatológicos", "Riscos Biológicos", "Riscos Tecnológicos"]
            selecionados_41 = []
            for ameaca in ameacas_cobrade:
                if st.checkbox(ameaca, value=ameaca in d41["valor"], key=f"chk_41_{ameaca}_{ano_sel}"):
                    selecionados_41.append(ameaca)
            pts41 = 0.0

        with col_j41:
            l41 = st.text_area("Justificativa (4.1):", value=d41["link"], key=f"l41_{ano_sel}", height=120)
            
            # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
            links_41_atuais = re.findall(r'(https?://[^\s]+)', l41)
            if links_41_atuais:
                st.markdown(f"🔗 **Link Ativo:** [{links_41_atuais[0]}]({links_41_atuais[0]})")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 4.1
        if str(selecionados_41) != d41["valor"] or l41 != d41["link"]:
            save_resp("4.1", str(selecionados_41), pts41, l41)
            
            # SÓ avalia o modal se houver de fato um link capturado no texto atual
            if links_41_atuais:
                links_41_antigos = re.findall(r'(https?://[^\s]+)', d41["link"])
                if not links_41_antigos or links_41_atuais[0] != links_41_antigos[0]:
                    modal_aviso_link("4.1", links_41_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("4.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # --- QUESITO 4.2 (PONTUAÇÃO NEGATIVA + LINK AZUL) -----------------------
    # -------------------------------------------------------------------------
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("QUESITO 4.2")
    st.write("**A Carta Geotécnica de Suscetibilidade, Aptidão à Urbanização e Risco consta no Plano Diretor?**")

    d42 = res_data.get("4.2", {"valor": None, "pontos": -50.0, "link": ""})
    opts42 = {
        "Sim (00 pts)": 0.0,
        "Não (-50 pts)": -50.0,
        "Não se aplica o Plano Diretor (00 pts)": 0.0
    }
    lista_opcoes = list(opts42.keys())
    idx42 = lista_opcoes.index(d42["valor"]) if d42["valor"] in lista_opcoes else None

    col_r42, col_j42 = st.columns([1, 2])
    with col_r42:
        r42 = st.radio("Situação:", lista_opcoes, index=idx42, key=f"q42_{ano_sel}")
    with col_j42:
        l42 = st.text_area("Evidência (4.2):", value=d42["link"], key=f"l42_{ano_sel}", height=100)
        
        # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
        links_42_atuais = re.findall(r'(https?://[^\s]+)', l42)
        if links_42_atuais:
            st.markdown(f"🔗 **Link Ativo:** [{links_42_atuais[0]}]({links_42_atuais[0]})")

    # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 4.2
    if r42 is not None and (r42 != d42["valor"] or l42 != d42["link"]):
        save_resp("4.2", r42, float(opts42[r42]), l42)
        
        # SÓ avalia o modal se houver de fato um link capturado no texto atual
        if links_42_atuais:
            links_42_antigos = re.findall(r'(https?://[^\s]+)', d42["link"])
            if not links_42_antigos or links_42_atuais[0] != links_42_antigos[0]:
                modal_aviso_link("4.2", links_42_atuais)
            else:
                st.rerun()
        else:
            st.rerun()

    bloco_comentarios("4.2", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

# -------------------------------------------------------------------------
    # --- QUESITO 5.0 (LINK AZUL ATIVO + DISPARO INTELIGENTE DE MODAL) -------
    # -------------------------------------------------------------------------
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("QUESITO 5.0")
    st.write("**O Município realizou, por conta própria, o mapeamento e identificação das principais ameaças existentes em seu território?**")

    d50 = res_data.get("5.0", {"valor": None, "pontos": 0.0, "link": ""})
    col_r50, col_j50 = st.columns([1, 2])
    opcoes_50 = ["Sim (200 pts)", "Não (00 pts)"]

    with col_r50:
        idx50 = opcoes_50.index(d50["valor"]) if d50["valor"] in opcoes_50 else None
        r50 = st.radio("Resposta 5.0:", opcoes_50, index=idx50, key=f"q50_{ano_sel}")
        pts50 = 200.0 if r50 and "Sim" in r50 else 0.0

    with col_j50:
        l50 = st.text_area("Justificativa Técnica (5.0):", value=d50["link"], key=f"l50_{ano_sel}", height=100)
        
        # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
        links_50_atuais = re.findall(r'(https?://[^\s]+)', l50)
        if links_50_atuais:
            st.markdown(f"🔗 **Link Ativo:** [{links_50_atuais[0]}]({links_50_atuais[0]})")

    # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 5.0
    if r50 is not None and (r50 != d50["valor"] or l50 != d50["link"]):
        save_resp("5.0", r50, pts50, l50)
        
        # SÓ avalia o modal se houver de fato um link capturado no texto atual
        if links_50_atuais:
            links_50_antigos = re.findall(r'(https?://[^\s]+)', d50["link"])
            if not links_50_antigos or links_50_atuais[0] != links_50_antigos[0]:
                modal_aviso_link("5.0", links_50_atuais)
            else:
                st.rerun()
        else:
            st.rerun()

    bloco_comentarios("5.0", res_data)
    st.markdown('</div>', unsafe_allow_html=True)


    # -------------------------------------------------------------------------
    # --- QUESITO 5.1 (CONDICIONAL - MÚLTIPLA ESCOLHA) ------------------------
    # -------------------------------------------------------------------------
    if r50 and "Sim" in r50:
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 5.1")
        st.write("**Assinale as principais ameaças identificadas:**")

        d51 = res_data.get("5.1", {"valor": "[]", "pontos": 0.0, "link": ""})
        col_c51, col_j51 = st.columns([1, 2])

        with col_c51:
            ameacas_51 = ["Epidemias", "Estiagem", "Incêndios (urbanos e florestais)",
                          "Ondas de calor ou ondas de frio", "Inundações", "Infestações e Pragas",
                          "Ameaças radioativas", "Deslizamentos", "Outros"]

            selecionados_51 = []
            for ameaca in ameacas_51:
                ameaca_id = ameaca.replace(" ", "_").lower()
                if st.checkbox(ameaca, value=ameaca in d51["valor"], key=f"chk51_{ameaca_id}_{ano_sel}"):
                    selecionados_51.append(ameaca)

        with col_j51:
            l51 = st.text_area("Descrição / Evidências (5.1):", value=d51["link"],
                               key=f"l51_{ano_sel}", placeholder="Se marcou 'Outros', especifique aqui...", height=150)
            
            # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
            links_51_atuais = re.findall(r'(https?://[^\s]+)', l51)
            if links_51_atuais:
                st.markdown(f"🔗 **Link Ativo:** [{links_51_atuais[0]}]({links_51_atuais[0]})")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 5.1
        if str(selecionados_51) != d51["valor"] or l51 != d51["link"]:
            if selecionados_51 or l51 != "" or d51["valor"] != "[]":
                save_resp("5.1", str(selecionados_51), 0.0, l51)
                
                # SÓ avalia o modal se houver de fato um link capturado no texto atual
                if links_51_atuais:
                    links_51_antigos = re.findall(r'(https?://[^\s]+)', d51["link"])
                    if not links_51_antigos or links_51_atuais[0] != links_51_antigos[0]:
                        modal_aviso_link("5.1", links_51_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()

        bloco_comentarios("5.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)


    # -------------------------------------------------------------------------
    # --- QUESITO 5.1.1 (PONTUAÇÃO NEGATIVA FLUTUANTE) ------------------------
    # -------------------------------------------------------------------------
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("QUESITO 5.1.1")
    st.write("**As secretarias setoriais realizaram a fiscalização das áreas de risco?**")

    d511 = res_data.get("5.1.1", {"valor": None, "pontos": -100.0, "link": ""})
    opts511 = {
        "Sim, integralmente (00 pts)": 0.0,
        "Sim, parcialmente (00 pts)": 0.0,
        "Não houve fiscalização (-100 pts)": -100.0
    }
    lista_opcoes_511 = list(opts511.keys())
    idx511 = lista_opcoes_511.index(d511["valor"]) if d511["valor"] in lista_opcoes_511 else None

    col_r511, col_j511 = st.columns([1, 2])
    with col_r511:
        r511 = st.radio("Status da Fiscalização:", lista_opcoes_511, index=idx511, key=f"q511_{ano_sel}")
    with col_j511:
        l511 = st.text_area("Evidência (5.1.1):", value=d511["link"], key=f"l511_{ano_sel}", height=100)
        
        # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
        links_511_atuais = re.findall(r'(https?://[^\s]+)', l511)
        if links_511_atuais:
            st.markdown(f"🔗 **Link Ativo:** [{links_511_atuais[0]}]({links_511_atuais[0]})")

    # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 5.11
    if r511 is not None and (r511 != d511["valor"] or l511 != d511["link"]):
        save_resp("5.1.1", r511, float(opts511[r511]), l511)
        
        # SÓ avalia o modal se houver de fato um link capturado no texto atual
        if links_511_atuais:
            links_511_antigos = re.findall(r'(https?://[^\s]+)', d511["link"])
            if not links_511_antigos or links_511_atuais[0] != links_511_antigos[0]:
                modal_aviso_link("5.1.1", links_511_atuais)
            else:
                st.rerun()
        else:
            st.rerun()

    bloco_comentarios("5.1.1", res_data)
    st.markdown('</div>', unsafe_allow_html=True)


    # -------------------------------------------------------------------------
    # --- QUESITO 5.1.2 (ESTRUTURAL / INFORMATIVO) ----------------------------
    # -------------------------------------------------------------------------
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("QUESITO 5.1.2")
    st.write("**O município possui áreas de risco com possibilidade de ocupação/invasão?**")

    d512 = res_data.get("5.1.2", {"valor": "Não", "pontos": 0.0, "link": ""})
    col_r512, col_j512 = st.columns([1, 2])

    with col_r512:
        r512 = st.radio("Possui áreas com risco de invasão?", ["Sim", "Não"],
                        index=0 if d512["valor"] == "Sim" else 1, key=f"q512_{ano_sel}")

    with col_j512:
        l512 = st.text_area("Justificativa (5.1.2):", value=d512["link"], key=f"l512_{ano_sel}", height=100)
        
        # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
        links_512_atuais = re.findall(r'(https?://[^\s]+)', l512)
        if links_512_atuais:
            st.markdown(f"🔗 **Link Ativo:** [{links_512_atuais[0]}]({links_512_atuais[0]})")

    # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 5.1.2
    if r512 is not None and (r512 != d512["valor"] or l512 != d512["link"]):
        save_resp("5.1.2", r512, 0.0, l512)
        
        # SÓ avalia o modal se houver de fato um link capturado no texto atual
        if links_512_atuais:
            links_512_antigos = re.findall(r'(https?://[^\s]+)', d512["link"])
            if not links_512_antigos or links_512_atuais[0] != links_512_antigos[0]:
                modal_aviso_link("5.1.2", links_512_atuais)
            else:
                st.rerun()
        else:
            st.rerun()

    bloco_comentarios("5.1.2", res_data)
    st.markdown('</div>', unsafe_allow_html=True)


    # -------------------------------------------------------------------------
    # --- QUESITO 5.1.2.1 (CONDICIONAL - MÚLTIPLA ESCOLA) --------------------
    # -------------------------------------------------------------------------
    if r512 == "Sim":
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 5.1.2.1")
        st.write("**Assinale os mecanismos para vedar novas ocupações nas áreas de riscos:**")

        d5121 = res_data.get("5.1.2.1", {"valor": "[]", "pontos": 0.0, "link": ""})
        col_c5121, col_j5121 = st.columns([1, 2])

        with col_c5121:
            mecanismos = ["Aplicação de sanções monetárias (multas)", "Monitoramento (fiscalização)",
                          "Notificação dos infratores", "Interdição do local e remoção das famílias",
                          "Demolição das ocupações", "Outros"]

            selecionados_5121 = []
            for mec in mecanismos:
                mec_id = mec.replace(" ", "_").replace("(", "").replace(")", "").lower()
                if st.checkbox(mec, value=mec in d5121["valor"], key=f"chk5121_{mec_id}_{ano_sel}"):
                    selecionados_5121.append(mec)

        with col_j5121:
            l5121 = st.text_area("Evidências dos Mecanismos (5.1.2.1):", value=d5121["link"],
                                 key=f"l5121_{ano_sel}", height=150)
            
            # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
            links_5121_atuais = re.findall(r'(https?://[^\s]+)', l5121)
            if links_5121_atuais:
                st.markdown(f"🔗 **Link Ativo:** [{links_5121_atuais[0]}]({links_5121_atuais[0]})")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 5.1.2.1
        if str(selecionados_5121) != d5121["valor"] or l5121 != d5121["link"]:
            if selecionados_5121 or l5121 != "" or d5121["valor"] != "[]":
                save_resp("5.1.2.1", str(selecionados_5121), 0.0, l5121)
                
                # SÓ avalia o modal se houver de fato um link capturado no texto atual
                if links_5121_atuais:
                    links_5121_antigos = re.findall(r'(https?://[^\s]+)', d5121["link"])
                    if not links_5121_antigos or links_5121_atuais[0] != links_5121_antigos[0]:
                        modal_aviso_link("5.1.2.1", links_5121_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()

        bloco_comentarios("5.1.2.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # --- QUESITO 5.2 (PONTUAÇÃO NEGATIVA FLUTUANTE) --------------------------
    # -------------------------------------------------------------------------
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("QUESITO 5.2")
    st.write("**A população foi informada sobre todas as ameaças identificadas pelo município?**")

    d52 = res_data.get("5.2", {"valor": None, "pontos": -50.0, "link": ""})
    opts52 = {
        "Sim (00 pts)": 0.0,
        "Parcialmente (00 pts)": 0.0,
        "Não (-50 pts)": -50.0
    }
    lista_opcoes_52 = list(opts52.keys())
    idx52 = lista_opcoes_52.index(d52["valor"]) if d52["valor"] in lista_opcoes_52 else None

    col_r52, col_j52 = st.columns([1, 2])
    with col_r52:
        r52 = st.radio("Informação à população:", lista_opcoes_52, index=idx52, key=f"q52_{ano_sel}")
    with col_j52:
        l52 = st.text_area("Meios de comunicação utilizados / Evidência (5.2):", value=d52["link"], key=f"l52_{ano_sel}", height=100)
        
        # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
        links_52_atuais = re.findall(r'(https?://[^\s]+)', l52)
        if links_52_atuais:
            st.markdown(f"🔗 **Link Ativo:** [{links_52_atuais[0]}]({links_52_atuais[0]})")

    # DISPARO DO MODAL INTELIGENTE
    if l52 != d52["link"]:
        links_52_antigos = re.findall(r'(https?://[^\s]+)', d52["link"])
        if links_52_atuais and (not links_52_antigos or links_52_atuais[0] != links_52_antigos[0]):
            modal_aviso_link("5.2", links_52_atuais)

    if r52 is not None and (r52 != d52["valor"] or l52 != d52["link"]):
        save_resp("5.2", r52, float(opts52[r52]), l52)
        st.rerun()

    bloco_comentarios("5.2", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

# -------------------------------------------------------------------------
    # --- QUESITO 6.0 (VISTORIAS E PONTUAÇÃO NEGATIVA FLUTUANTE) ------------
    # -------------------------------------------------------------------------
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("QUESITO 6.0")
    st.write("**A Secretaria responsável realizou vistorias em edificações vulneráveis com o objetivo de identificar a necessidade de intervenção preventiva nos imóveis?**")

    d60 = res_data.get("6.0", {"valor": None, "pontos": -50.0, "link": ""})
    opts60 = {
        "Sim, de acordo com um cronograma preestabelecido (00 pts)": 0.0,
        "Sim, de acordo com a demanda (00 pts)": 0.0,
        "Não foram vistoriadas (-50 pts)": -50.0,
        "Não houve casos de edificações vulneráveis (00 pts)": 0.0
    }
    lista_opcoes_60 = list(opts60.keys())
    idx60 = lista_opcoes_60.index(d60["valor"]) if d60["valor"] in lista_opcoes_60 else None

    col_r60, col_j60 = st.columns([1, 2])
    with col_r60:
        r60 = st.radio(
            "Status das Vistorias:",
            lista_opcoes_60,
            index=idx60,
            key=f"q60_radio_{ano_sel}"
        )
    with col_j60:
        l60 = st.text_area(
            "Relatórios de Vistoria / Evidências (6.0):",
            value=d60["link"],
            key=f"l60_text_{ano_sel}",
            height=100
        )
        
        # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
        links_60_atuais = re.findall(r'(https?://[^\s]+)', l60)
        if links_60_atuais:
            st.markdown(f"🔗 **Link Ativo:** [{links_60_atuais[0]}]({links_60_atuais[0]})")

    # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 6.0
    if r60 is not None and (r60 != d60["valor"] or l60 != d60["link"]):
        save_resp("6.0", r60, float(opts60[r60]), l60)
        
        # SÓ avalia o modal se houver de fato um link capturado no texto atual
        if links_60_atuais:
            links_60_antigos = re.findall(r'(https?://[^\s]+)', d60["link"])
            if not links_60_antigos or links_60_atuais[0] != links_60_antigos[0]:
                modal_aviso_link("6.0", links_60_atuais)
            else:
                st.rerun()
        else:
            st.rerun()

    bloco_comentarios("6.0", res_data)
    st.markdown('</div>', unsafe_allow_html=True)


    # -------------------------------------------------------------------------
    # --- QUESITO 7.0 (PLANCON - LINK AZUL ATIVO + MODAL INTELIGENTE) ---------
    # -------------------------------------------------------------------------
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("QUESITO 7.0")
    st.write("**O Município possui Plano de Contingência Municipal – PLANCON de Defesa Civil?**")

    d70 = res_data.get("7.0", {"valor": None, "pontos": 0.0, "link": ""})
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
        pts70 = 50.0 if r70 and "Sim" in r70 else 0.0

    with col_j70:
        l70 = st.text_area(
            "Link do PLANCON / Decreto (7.0):",
            value=d70["link"],
            key=f"l70_text_{ano_sel}",
            height=100
        )
        
        # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
        links_70_atuais = re.findall(r'(https?://[^\s]+)', l70)
        if links_70_atuais:
            st.markdown(f"🔗 **Link Ativo:** [{links_70_atuais[0]}]({links_70_atuais[0]})")

    # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 7.0
    if r70 is not None and (r70 != d70["valor"] or l70 != d70["link"]):
        save_resp("7.0", r70, pts70, l70)
        
        # SÓ avalia o modal se houver de fato um link capturado no texto atual
        if links_70_atuais:
            links_70_antigos = re.findall(r'(https?://[^\s]+)', d70["link"])
            if not links_70_antigos or links_70_atuais[0] != links_70_antigos[0]:
                modal_aviso_link("7.0", links_70_atuais)
            else:
                st.rerun()
        else:
            st.rerun()

    bloco_comentarios("7.0", res_data)
    st.markdown('</div>', unsafe_allow_html=True)


    # -------------------------------------------------------------------------
    # --- QUESITO 7.1 (DEPENDENTE DO 7.0 - CONDICIONAL) ----------------------
    # -------------------------------------------------------------------------
    if r70 and "Sim" in r70:
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 7.1")
        st.write("**Foi elaborado um PLANCON específico para cada ameaça identificada?**")

        d71 = res_data.get("7.1", {"valor": None, "pontos": 0.0, "link": ""})
        opts71 = {
            "Sim, cada ameaça mapeada possui um PLANCON diferente (05 pts)": 5.0,
            "Sim, parte das ameaças possuem PLANCON diferentes (03 pts)": 3.0,
            "Existe apenas um PLANCON que abrange todas as ameaças (00 pts)": 0.0
        }
        lista_opcoes_71 = list(opts71.keys())
        idx71 = lista_opcoes_71.index(d71["valor"]) if d71["valor"] in lista_opcoes_71 else None

        col_r71, col_j71 = st.columns([1, 2])
        with col_r71:
            r71 = st.radio(
                "Abrangência do PLANCON:",
                lista_opcoes_71,
                index=idx71,
                key=f"q71_radio_{ano_sel}"
            )
        with col_j71:
            l71 = st.text_area(
                "Evidências/Links dos planos específicos (7.1):",
                value=d71["link"],
                key=f"l71_text_{ano_sel}",
                height=100
            )
            
            # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
            links_71_atuais = re.findall(r'(https?://[^\s]+)', l71)
            if links_71_atuais:
                st.markdown(f"🔗 **Link Ativo:** [{links_71_atuais[0]}]({links_71_atuais[0]})")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 7.1
        if r71 is not None and (r71 != d71["valor"] or l71 != d71["link"]):
            save_resp("7.1", r71, float(opts71[r71]), l71)
            
            # SÓ avalia o modal se houver de fato um link capturado no texto atual
            if links_71_atuais:
                links_71_antigos = re.findall(r'(https?://[^\s]+)', d71["link"])
                if not links_71_antigos or links_71_atuais[0] != links_71_antigos[0]:
                    modal_aviso_link("7.1", links_71_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("7.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # --- QUESITO 7.2 (SIMULADOS) ---------------------------------------------
    # -------------------------------------------------------------------------
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("QUESITO 7.2")
    st.write("**São realizados regularmente exercícios simulados para as contingências previstas no PLANCON?**")

    d72 = res_data.get("7.2", {"valor": None, "pontos": 0.0, "link": ""})
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
        pts72 = 80.0 if r72 and "Sim" in r72 else 0.0

    with col_j72:
        l72 = st.text_area(
            "Cronograma/Relatório dos Simulados (7.2):",
            value=d72["link"],
            key=f"l72_text_{ano_sel}",
            height=100
        )
        
        # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
        links_72_atuais = re.findall(r'(https?://[^\s]+)', l72)
        if links_72_atuais:
            st.markdown(f"🔗 **Link Ativo:** [{links_72_atuais[0]}]({links_72_atuais[0]})")

    # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 7.2
    if r72 is not None and (r72 != d72["valor"] or l72 != d72["link"]):
        save_resp("7.2", r72, pts72, l72)
        
        # SÓ avalia o modal se houver de fato um link capturado no texto atual
        if links_72_atuais:
            links_72_antigos = re.findall(r'(https?://[^\s]+)', d72["link"])
            if not links_72_antigos or links_72_atuais[0] != links_72_antigos[0]:
                modal_aviso_link("7.2", links_72_atuais)
            else:
                st.rerun()
        else:
            st.rerun()

    bloco_comentarios("7.2", res_data)
    st.markdown('</div>', unsafe_allow_html=True)


    # -------------------------------------------------------------------------
    # --- QUESITO 7.3 (SISTEMA DE ALERTA) -------------------------------------
    # -------------------------------------------------------------------------
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("QUESITO 7.3")
    st.write("**O Município possui sistema de alerta para desastres?**")
    st.caption("Objetivo: avisar a população vulnerável antes de ocorrer o evento.")

    d73 = res_data.get("7.3", {"valor": None, "pontos": 0.0, "link": ""})
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
        pts73 = 50.0 if r73 and "Sim" in r73 else 0.0

    with col_j73:
        l73 = st.text_area(
            "Descrição do sistema (SMS, Sirenes, etc) (7.3):",
            value=d73["link"],
            key=f"l73_text_{ano_sel}",
            height=100
        )
        
        # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
        links_73_atuais = re.findall(r'(https?://[^\s]+)', l73)
        if links_73_atuais:
            st.markdown(f"🔗 **Link Ativo:** [{links_73_atuais[0]}]({links_73_atuais[0]})")

    # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 7.3
    if r73 is not None and (r73 != d73["valor"] or l73 != d73["link"]):
        save_resp("7.3", r73, pts73, l73)
        
        # SÓ avalia o modal se houver de fato um link capturado no texto atual
        if links_73_atuais:
            links_73_antigos = re.findall(r'(https?://[^\s]+)', d73["link"])
            if not links_73_antigos or links_73_atuais[0] != links_73_antigos[0]:
                modal_aviso_link("7.3", links_73_atuais)
            else:
                st.rerun()
        else:
            st.rerun()

    bloco_comentarios("7.3", res_data)
    st.markdown('</div>', unsafe_allow_html=True)


    # -------------------------------------------------------------------------
    # --- QUESITO 7.3.1 (CONDICIONAL DO 7.3 - MÚLTIPLA ESCOLHA) ---------------
    # -------------------------------------------------------------------------
    if r73 and "Sim" in r73:
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 7.3.1")
        st.write("**Assinale os tipos de sistemas de alerta utilizados pelo Município:**")

        d731 = res_data.get("7.3.1", {"valor": "[]", "pontos": 0.0, "link": ""})
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
                key=f"l731_text_{ano_sel}",
                height=150
            )
            
            # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
            links_731_atuais = re.findall(r'(https?://[^\s]+)', l731)
            if links_731_atuais:
                st.markdown(f"🔗 **Link Ativo:** [{links_731_atuais[0]}]({links_731_atuais[0]})")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 7.3.1
        if str(sel_731) != d731["valor"] or l731 != d731["link"]:
            if sel_731 or l731 != "" or d731["valor"] != "[]":
                save_resp("7.3.1", str(sel_731), 0.0, l731)
                
                # SÓ avalia o modal se houver de fato um link capturado no texto atual
                if links_731_atuais:
                    links_731_antigos = re.findall(r'(https?://[^\s]+)', d731["link"])
                    if not links_731_antigos or links_731_atuais[0] != links_731_antigos[0]:
                        modal_aviso_link("7.3.1", links_731_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()

        bloco_comentarios("7.3.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)


    # -------------------------------------------------------------------------
    # --- QUESITO 7.4 (SISTEMA DE ALARME) -------------------------------------
    # -------------------------------------------------------------------------
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("QUESITO 7.4")
    st.write("**O Município dispõe de sinal, dispositivo ou sistema de alarme para desastres?**")
    st.caption("Objetivo: avisar a população sobre o evento que ESTÁ OCORRENDO.")

    d74 = res_data.get("7.4", {"valor": None, "pontos": 0.0, "link": ""})
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
        pts74 = 50.0 if r74 and "Sim" in r74 else 0.0

    with col_j74:
        l74 = st.text_area(
            "Evidência do sistema de alarme (7.4):",
            value=d74["link"],
            key=f"l74_text_{ano_sel}",
            height=100
        )
        
        # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
        links_74_atuais = re.findall(r'(https?://[^\s]+)', l74)
        if links_74_atuais:
            st.markdown(f"🔗 **Link Ativo:** [{links_74_atuais[0]}]({links_74_atuais[0]})")

    # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 7.4
    if r74 is not None and (r74 != d74["valor"] or l74 != d74["link"]):
        save_resp("7.4", r74, pts74, l74)
        
        # SÓ avalia o modal se houver de fato um link capturado no texto atual
        if links_74_atuais:
            links_74_antigos = re.findall(r'(https?://[^\s]+)', d74["link"])
            if not links_74_antigos or links_74_atuais[0] != links_74_antigos[0]:
                modal_aviso_link("7.4", links_74_atuais)
            else:
                st.rerun()
        else:
            st.rerun()

    bloco_comentarios("7.4", res_data)
    st.markdown('</div>', unsafe_allow_html=True)


    # -------------------------------------------------------------------------
    # --- QUESITO 7.4.1 (CONDICIONAL DO 7.4 - MÚLTIPLA ESCOLHA) ---------------
    # -------------------------------------------------------------------------
    if r74 and "Sim" in r74:
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 7.4.1")
        st.write("**Assinale os tipos de sinal, dispositivo ou sistema de alarme utilizado:**")

        d741 = res_data.get("7.4.1", {"valor": "[]", "pontos": 0.0, "link": ""})
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
                key=f"l741_text_{ano_sel}",
                height=150
            )
            
            # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
            links_741_atuais = re.findall(r'(https?://[^\s]+)', l741)
            if links_741_atuais:
                st.markdown(f"🔗 **Link Ativo:** [{links_741_atuais[0]}]({links_741_atuais[0]})")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 7.4.1
        if str(sel_741) != d741["valor"] or l741 != d741["link"]:
            if sel_741 or l741 != "" or d741["valor"] != "[]":
                save_resp("7.4.1", str(sel_741), 0.0, l741)
                
                # SÓ avalia o modal se houver de fato um link capturado no texto atual
                if links_741_atuais:
                    links_741_antigos = re.findall(r'(https?://[^\s]+)', d741["link"])
                    if not links_741_antigos or links_741_atuais[0] != links_741_antigos[0]:
                        modal_aviso_link("7.4.1", links_741_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()

        bloco_comentarios("7.4.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # --- QUESITO 7.5 (CADASTRO DE ABRIGOS) -----------------------------------
    # -------------------------------------------------------------------------
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("QUESITO 7.5")
    st.write("**Possui cadastro dos locais para abrigo à população em situação de desastre junto à Coordenadoria Estadual de Proteção e Defesa Civil (CEPDEC)?**")

    d75 = res_data.get("7.5", {"valor": None, "pontos": 0.0, "link": ""})
    opts75 = {
        "Sim, atualizado (10 pts)": 10.0,
        "Sim, mas não está atualizado (03 pts)": 3.0,
        "Não (00 pts)": 0.0
    }
    lista_opcoes_75 = list(opts75.keys())
    idx75 = lista_opcoes_75.index(d75["valor"]) if d75["valor"] in lista_opcoes_75 else None

    col_r75, col_j75 = st.columns([1, 2])
    with col_r75:
        r75 = st.radio(
            "Cadastro de Abrigos (CEPDEC):",
            lista_opcoes_75,
            index=idx75,
            key=f"q75_radio_{ano_sel}"
        )
    with col_j75:
        l75 = st.text_area(
            "Evidência do Cadastro/Protocolo (7.5):",
            value=d75["link"],
            key=f"l75_text_{ano_sel}",
            height=100
        )
        
        # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
        links_75_atuais = re.findall(r'(https?://[^\s]+)', l75)
        if links_75_atuais:
            st.markdown(f"🔗 **Link Ativo:** [{links_75_atuais[0]}]({links_75_atuais[0]})")

    # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 7.5
    if r75 is not None and (r75 != d75["valor"] or l75 != d75["link"]):
        save_resp("7.5", r75, float(opts75[r75]), l75)
        
        # SÓ avalia o modal se houver de fato um link capturado no texto atual
        if links_75_atuais:
            links_75_antigos = re.findall(r'(https?://[^\s]+)', d75["link"])
            if not links_75_antigos or links_75_atuais[0] != links_75_antigos[0]:
                modal_aviso_link("7.5", links_75_atuais)
            else:
                st.rerun()
        else:
            st.rerun()

    bloco_comentarios("7.5", res_data)
    st.markdown('</div>', unsafe_allow_html=True)


   # -------------------------------------------------------------------------
    # --- QUESITO 7.6 (FORNECEDORES DE AJUDA) ---------------------------------
    # -------------------------------------------------------------------------
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("QUESITO 7.6")
    st.write("**O Município possui cadastro da lista de fornecedores para coleta e distribuição de suprimentos de ajuda humanitária para o caso de desastre?**")

    d76 = res_data.get("7.6", {"valor": None, "pontos": 0.0, "link": ""})
    opts76 = {
        "Sim, atualizado (10 pts)": 10.0,
        "Sim, mas não está atualizado (03 pts)": 3.0,
        "Não (00 pts)": 0.0
    }
    lista_opcoes_76 = list(opts76.keys())
    idx76 = lista_opcoes_76.index(d76["valor"]) if d76["valor"] in lista_opcoes_76 else None

    col_r76, col_j76 = st.columns([1, 2])
    with col_r76:
        r76 = st.radio(
            "Lista de Fornecedores:",
            lista_opcoes_76,
            index=idx76,
            key=f"q76_radio_{ano_sel}"
        )
    with col_j76:
        l76 = st.text_area(
            "Evidência da lista/cadastro (7.6):",
            value=d76["link"],
            key=f"l76_text_{ano_sel}",
            height=100
        )
        
        # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
        links_76_atuais = re.findall(r'(https?://[^\s]+)', l76)
        if links_76_atuais:
            st.markdown(f"🔗 **Link Ativo:** [{links_76_atuais[0]}]({links_76_atuais[0]})")

    # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 7.6
    if r76 is not None and (r76 != d76["valor"] or l76 != d76["link"]):
        save_resp("7.6", r76, float(opts76[r76]), l76)
        
        # SÓ avalia o modal se houver de fato um link capturado no texto atual
        if links_76_atuais:
            links_76_antigos = re.findall(r'(https?://[^\s]+)', d76["link"])
            if not links_76_antigos or links_76_atuais[0] != links_76_antigos[0]:
                modal_aviso_link("7.6", links_76_atuais)
            else:
                st.rerun()
        else:
            st.rerun()

    bloco_comentarios("7.6", res_data)
    st.markdown('</div>', unsafe_allow_html=True)


    # -------------------------------------------------------------------------
    # --- QUESITO 7.7 (DATA PLANCON - CAMPO DE DATA) -------------------------
    # -------------------------------------------------------------------------
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("QUESITO 7.7")
    st.write("**Qual a data da última atualização do PLANCON?**")
    st.caption("Se não houve atualização, informar a data do início da vigência.")

    d77 = res_data.get("7.7", {"valor": "", "pontos": 0.0, "link": ""})

    data_77 = st.text_input(
        "Data de Atualização/Vigência (DD/MM/AAAA):",
        value=d77["valor"],
        key=f"q77_date_{ano_sel}",
        placeholder="Ex: 15/05/2024"
    )

    if data_77 != d77["valor"]:
        if data_77 != "" or d77["valor"] != "":
            save_resp("7.7", data_77, 0.0, "")
            st.rerun()

    bloco_comentarios("7.7", res_data)
    st.markdown('</div>', unsafe_allow_html=True)


    # -------------------------------------------------------------------------
    # --- QUESITO 8.0 (CANAL DE EMERGÊNCIA) ---
    # -------------------------------------------------------------------------
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
        pts80 = 50.0 if r80 and "Sim" in r80 else 0.0

    with col_j80:
        l80 = st.text_area(
            "Descrição/Evidência do Canal (8.0):",
            value=d80["link"],
            key=f"l80_text_{ano_sel}",
            placeholder="Ex: Telefone 199, WhatsApp oficial, Site de chamados..."
        )
        
        # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
        links_80_atuais = re.findall(r'(https?://[^\s]+)', l80)
        if links_80_atuais:
            st.markdown(f"🔗 **Link Ativo:** [{links_80_atuais[0]}]({links_80_atuais[0]})")

    # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 8.0
    if r80 is not None and (r80 != d80["valor"] or l80 != d80["link"]):
        save_resp("8.0", r80, pts80, l80)
        
        # SÓ avalia o modal se houver de fato um link capturado no texto atual
        if links_80_atuais:
            links_80_antigos = re.findall(r'(https?://[^\s]+)', d80["link"])
            if not links_80_antigos or links_80_atuais[0] != links_80_antigos[0]:
                modal_aviso_link("8.0", links_80_atuais)
            else:
                st.rerun()
        else:
            st.rerun()

    bloco_comentarios("8.0", res_data)


    # -------------------------------------------------------------------------
    # --- QUESITO 8.1 e 8.1.1 (Condicionais Dependentes do 8.0) ---------------
    # -------------------------------------------------------------------------
    if r80 and "Sim" in r80:
        st.markdown('<div style="margin-left: 20px; border-left: 2px solid #eee; padding-left: 20px; margin-bottom: 20px;">', unsafe_allow_html=True)

        # --- QUESITO 8.1 ---
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
            
            # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
            links_81_atuais = re.findall(r'(https?://[^\s]+)', l81)
            if links_81_atuais:
                st.markdown(f"🔗 **Link Ativo:** [{links_81_atuais[0]}]({links_81_atuais[0]})")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 8.1
        if str(sel_81) != d81["valor"] or l81 != d81["link"]:
            if sel_81 or l81 != "" or d81["valor"] != "[]":
                save_resp("8.1", str(sel_81), 0.0, l81)
                
                # SÓ avalia o modal se houver de fato um link capturado no texto atual
                if links_81_atuais:
                    links_81_antigos = re.findall(r'(https?://[^\s]+)', d81["link"])
                    if not links_81_antigos or links_81_atuais[0] != links_81_antigos[0]:
                        modal_aviso_link("8.1", links_81_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()

        bloco_comentarios("8.1", res_data)

        # --- QUESITO 8.1.1 ---
        st.subheader("QUESITO 8.1.1")
        st.write("**Sobre o número de telefone de emergência, utiliza o número 199 da Defesa Civil?**")

        d811 = res_data.get("8.1.1", {"valor": None, "pontos": 0, "link": ""})
        opcoes_811 = ["Sim", "Não"]
        idx811 = opcoes_811.index(d811["valor"]) if d811["valor"] in opcoes_811 else None

        r811 = st.radio("Utiliza o 199?", opcoes_811, index=idx811, key=f"q811_radio_{ano_sel}")

        if r811 is not None and r811 != d811["valor"]:
            save_resp("8.1.1", r811, 0.0, "")
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
            pts8111 = 20.0 if r8111 and "Sim" in r8111 else 0.0

            if r8111 is not None and r8111 != d8111["valor"]:
                save_resp("8.1.1.1", r8111, pts8111, "")
                st.rerun()

            bloco_comentarios("8.1.1.1", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True) # Fecha recuo do div condicional do 8.0

    st.markdown('</div>', unsafe_allow_html=True) # Fecha o card principal do QUESITO 8.0

    # -------------------------------------------------------------------------
    # --- QUESITO 8.2 (REGISTRO ELETRÔNICO) -----------------------------------
    # -------------------------------------------------------------------------
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 8.2")
    st.write("**O Município registra as ocorrências de Defesa Civil de forma eletrônica?**")

    d82 = res_data.get("8.2", {"valor": None, "pontos": 0.0, "link": ""})
    col_r82, col_j82 = st.columns([1, 2])
    opcoes_82 = ["Sim (50 pts)", "Não (00 pts)"]

    with col_r82:
        idx82 = opcoes_82.index(d82["valor"]) if d82["valor"] in opcoes_82 else None
        r82 = st.radio("Registro eletrônico?", opcoes_82, index=idx82, key=f"q82_radio_{ano_sel}")
        pts82 = 50.0 if r82 and "Sim" in r82 else 0.0

    with col_j82:
        l82 = st.text_area("Evidência do Sistema (8.2):", value=d82["link"], key=f"l82_text_{ano_sel}")
        
        # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
        links_82_atuais = re.findall(r'(https?://[^\s]+)', l82)
        if links_82_atuais:
            st.markdown(f"🔗 **Link Ativo:** [{links_82_atuais[0]}]({links_82_atuais[0]})")

    # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 8.2
    if r82 is not None and (r82 != d82["valor"] or l82 != d82["link"]):
        save_resp("8.2", r82, pts82, l82)
        
        if links_82_atuais:
            links_82_antigos = re.findall(r'(https?://[^\s]+)', d82["link"])
            if not links_82_antigos or links_82_atuais[0] != links_82_antigos[0]:
                modal_aviso_link("8.2", links_82_atuais)
            else:
                st.rerun()
        else:
            st.rerun()

    bloco_comentarios("8.2", res_data)
    st.markdown('</div>', unsafe_allow_html=True)


    # -------------------------------------------------------------------------
    # --- QUESITO 9.0 (ESCOLAS E SAÚDE) ---------------------------------------
    # -------------------------------------------------------------------------
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 9.0")
    st.write("**O Município realizou um estudo de avaliação da estrutura de todas as escolas e unidades de saúde para garantir que, em caso de desastre, esses locais estejam preparados para abrigar e atender a população afetada?**")

    d90 = res_data.get("9.0", {"valor": None, "pontos": 0.0, "link": ""})
    opts90 = {
        "Sim, em todas as escolas e centros de saúde (100 pts)": 100.0,
        "Sim, na maior parte das escolas e centros de saúde (50 pts)": 50.0,
        "Sim, na menor parte das escolas e centros de saúde (20 pts)": 20.0,
        "Não (00 pts)": 0.0
    }
    lista_opcoes_90 = list(opts90.keys())
    idx90 = lista_opcoes_90.index(d90["valor"]) if d90["valor"] in lista_opcoes_90 else None

    col_r90, col_j90 = st.columns([1, 2])
    with col_r90:
        r90 = st.radio("Abrangência:", lista_opcoes_90, index=idx90, key=f"q90_radio_{ano_sel}")
        
    with col_j90:
        l90 = st.text_area("Link do Estudo / Relatório (9.0):", value=d90["link"], key=f"l90_text_{ano_sel}")
        
        # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
        links_90_atuais = re.findall(r'(https?://[^\s]+)', l90)
        if links_90_atuais:
            st.markdown(f"🔗 **Link Ativo:** [{links_90_atuais[0]}]({links_90_atuais[0]})")

    # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 9.0
    if r90 is not None and (r90 != d90["valor"] or l90 != d90["link"]):
        save_resp("9.0", r90, float(opts90[r90]), l90)
        
        if links_90_atuais:
            links_90_antigos = re.findall(r'(https?://[^\s]+)', d90["link"])
            if not links_90_antigos or links_90_atuais[0] != links_90_antigos[0]:
                modal_aviso_link("9.0", links_90_atuais)
            else:
                st.rerun()
        else:
            st.rerun()

    bloco_comentarios("9.0", res_data)
    st.markdown('</div>', unsafe_allow_html=True)


    # -------------------------------------------------------------------------
    # --- QUESITO 10.0 (PLANO DE MOBILIDADE) ----------------------------------
    # -------------------------------------------------------------------------
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 10.0")
    st.write("**O Município elaborou seu Plano de Mobilidade Urbana?**")

    d100 = res_data.get("10.0", {"valor": None, "pontos": 0.0, "link": ""})
    opts100 = {
        "Sim (00 pts)": 0.0,
        "Não (-100 pts)": -100.0,
        "Não se aplica (00 pts)": 0.0
    }
    lista_opcoes_100 = list(opts100.keys())
    idx100 = lista_opcoes_100.index(d100["valor"]) if d100["valor"] in lista_opcoes_100 else None

    col_r100, col_j100 = st.columns([1, 2])
    with col_r100:
        r100 = st.radio(
            "Status Plano de Mobilidade:",
            lista_opcoes_100,
            index=idx100,
            key=f"q100_radio_{ano_sel}"
        )

    with col_j100:
        l100 = st.text_area(
            "Evidência (10.0):",
            value=d100["link"],
            key=f"l100_text_{ano_sel}"
        )
        
        # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
        links_100_atuais = re.findall(r'(https?://[^\s]+)', l100)
        if links_100_atuais:
            st.markdown(f"🔗 **Link Ativo:** [{links_100_atuais[0]}]({links_100_atuais[0]})")

    # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 10.0
    if r100 is not None and (r100 != d100["valor"] or l100 != d100["link"]):
        save_resp("10.0", r100, float(opts100[r100]), l100)
        
        if links_100_atuais:
            links_100_antigos = re.findall(r'(https?://[^\s]+)', d100["link"])
            if not links_100_antigos or links_100_atuais[0] != links_100_antigos[0]:
                modal_aviso_link("10.0", links_100_atuais)
            else:
                st.rerun()
        else:
            st.rerun()

    bloco_comentarios("10.0", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # --- QUESITO 11.0 (TRANSPORTE COLETIVO) ----------------------------------
    # -------------------------------------------------------------------------
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 11.0")
    st.write("**No Município existe transporte público coletivo?**")

    d110 = res_data.get("11.0", {"valor": None, "pontos": 0.0, "link": ""})
    col_r110, col_j110 = st.columns([1, 2])
    opcoes_110 = ["Sim", "Não"]

    with col_r110:
        idx110 = opcoes_110.index(d110["valor"]) if d110["valor"] in opcoes_110 else None
        r110 = st.radio("Transporte Coletivo:", opcoes_110, index=idx110, key=f"q110_radio_{ano_sel}")

    with col_j110:
        l110 = st.text_area("Justificativa / Detalhes (11.0):", value=d110["link"], key=f"l110_text_{ano_sel}")
        
        # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
        links_110_atuais = re.findall(r'(https?://[^\s]+)', l110)
        if links_110_atuais:
            st.markdown(f"🔗 **Link Ativo:** [{links_110_atuais[0]}]({links_110_atuais[0]})")

    # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 11.0
    if r110 is not None and (r110 != d110["valor"] or l110 != d110["link"]):
        save_resp("11.0", r110, 0.0, l110)
        
        if links_110_atuais:
            links_110_antigos = re.findall(r'(https?://[^\s]+)', d110["link"])
            if not links_110_antigos or links_110_atuais[0] != links_110_antigos[0]:
                modal_aviso_link("11.0", links_110_atuais)
            else:
                st.rerun()
        else:
            st.rerun()

    bloco_comentarios("11.0", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- SUBQUESITOS CONDICIONAIS DE TRANSPORTE PÚBLICO MUNICIPAL -------------
    if r110 == "Sim":
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 11.1")
        st.write("**Foram estabelecidas metas de qualidade e desempenho para o transporte público coletivo municipal?**")

        d111 = res_data.get("11.1", {"valor": None, "pontos": 0.0, "link": ""})
        opts111 = {"Sim (00 pts)": 0.0, "Não (-20 pts)": -20.0}
        lista_opcoes_111 = list(opts111.keys())
        idx111 = lista_opcoes_111.index(d111["valor"]) if d111["valor"] in lista_opcoes_111 else None

        col_r111, col_j111 = st.columns([1, 2])
        with col_r111:
            r111 = st.radio("Metas estabelecidas:", lista_opcoes_111, index=idx111, key=f"q111_radio_{ano_sel}")

        with col_j111:
            l111 = st.text_area("Evidência (11.1):", value=d111["link"], key=f"l111_text_{ano_sel}")
            
            # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
            links_111_atuais = re.findall(r'(https?://[^\s]+)', l111)
            if links_111_atuais:
                st.markdown(f"🔗 **Link Ativo:** [{links_111_atuais[0]}]({links_111_atuais[0]})")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 11.1
        if r111 is not None and (r111 != d111["valor"] or l111 != d111["link"]):
            save_resp("11.1", r111, float(opts111[r111]), l111)
            
            if links_111_atuais:
                links_111_antigos = re.findall(r'(https?://[^\s]+)', d111["link"])
                if not links_111_antigos or links_111_atuais[0] != links_111_antigos[0]:
                    modal_aviso_link("11.1", links_111_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        # --- QUESITO 11.1.1 (ATENDIMENTO DAS METAS) -------------------------
        if r111 and "Sim" in r111:
            st.divider()
            st.subheader("QUESITO 11.1.1")
            st.write("**As metas de qualidade e desempenho estão sendo atingidas?**")

            d1111 = res_data.get("11.1.1", {"valor": None, "pontos": 0.0, "link": ""})
            opts1111 = {
                "Todas as metas foram atingidas (00 pts)": 0.0,
                "A maior parte das metas foram atingidas (-05 pts)": -5.0,
                "A menor parte das metas foram atingidas (-10 pts)": -10.0,
                "As metas não foram atingidas (-20 pts)": -20.0
            }
            lista_opcoes_1111 = list(opts1111.keys())
            idx1111 = lista_opcoes_1111.index(d1111["valor"]) if d1111["valor"] in lista_opcoes_1111 else None

            col_r1111, col_j1111 = st.columns([1, 2])
            with col_r1111:
                r1111 = st.radio("Cumprimento das metas:", lista_opcoes_1111, index=idx1111, key=f"q1111_radio_{ano_sel}")

            with col_j1111:
                l1111 = st.text_area("Relatório de Desempenho (11.1.1):", value=d1111["link"], key=f"l1111_text_{ano_sel}")
                
                # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
                links_1111_atuais = re.findall(r'(https?://[^\s]+)', l1111)
                if links_1111_atuais:
                    st.markdown(f"🔗 **Link Ativo:** [{links_1111_atuais[0]}]({links_1111_atuais[0]})")

            # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 11.1.1
            if r1111 is not None and (r1111 != d1111["valor"] or l1111 != d1111["link"]):
                save_resp("11.1.1", r1111, float(opts1111[r1111]), l1111)
                
                if links_1111_atuais:
                    links_1111_antigos = re.findall(r'(https?://[^\s]+)', d1111["link"])
                    if not links_1111_antigos or links_1111_atuais[0] != links_1111_antigos[0]:
                        modal_aviso_link("11.1.1", links_1111_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()

            bloco_comentarios("11.1.1", res_data)

            # --- QUESITO 11.1.1.1 (PENALIDADE) -------------------------------
            if r1111 and "Todas" not in r1111:
                st.divider()
                st.subheader("QUESITO 11.1.1.1")
                st.write("**Foi aplicada penalidade pela meta não cumprida?**")

                d11111 = res_data.get("11.1.1.1", {"valor": None, "pontos": 0.0, "link": ""})
                opcoes_11111 = ["Sim (00 pts)", "Não (-50 pts)"]
                
                col_r11111, col_j11111 = st.columns([1, 2])
                with col_r11111:
                    idx11111 = opcoes_11111.index(d11111["valor"]) if d11111["valor"] in opcoes_11111 else None
                    r11111 = st.radio("Aplicação de penalidade:", opcoes_11111, index=idx11111, key=f"q11111_radio_{ano_sel}")
                    pts11111 = -50.0 if r11111 and "Não" in r11111 else 0.0

                with col_j11111:
                    l11111 = st.text_area("Auto de Infração (11.1.1.1):", value=d11111["link"], key=f"l11111_text_{ano_sel}")
                    
                    # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
                    links_11111_atuais = re.findall(r'(https?://[^\s]+)', l11111)
                    if links_11111_atuais:
                        st.markdown(f"🔗 **Link Ativo:** [{links_11111_atuais[0]}]({links_11111_atuais[0]})")

                # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 11.1.1.1
                if r11111 is not None and (r11111 != d11111["valor"] or l11111 != d11111["link"]):
                    save_resp("11.1.1.1", r11111, pts11111, l11111)
                    
                    if links_11111_atuais:
                        links_11111_antigos = re.findall(r'(https?://[^\s]+)', d11111["link"])
                        if not links_11111_antigos or links_11111_atuais[0] != links_11111_antigos[0]:
                            modal_aviso_link("11.1.1.1", links_11111_atuais)
                        else:
                            st.rerun()
                    else:
                        st.rerun()

                bloco_comentarios("11.1.1.1", res_data)

        # Bloco de comentários pai (11.1) e fechamento do card externo
        bloco_comentarios("11.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # --- QUESITO 11.2 (PESQUISA DE SATISFAÇÃO) -------------------------------
    # -------------------------------------------------------------------------
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 11.2")

    # ✔️ PEGA APENAS OS NÚMEROS DO ANO (DESENRAIZA TEXTOS COMPLEXOS COMO "2026 - IEGM")
    ano_puro = "".join([c for c in str(ano_sel) if c.isdigit()])[:4]
    ano_anterior = int(ano_puro) - 1

    st.write(f"**Foi realizada pesquisa de satisfação dos usuários em {ano_anterior}?**")

    d112 = res_data.get("11.2", {"valor": None, "pontos": 0.0, "link": ""})
    opcoes_112 = ["Sim (00 pts)", "Não (-20 pts)"]
    idx112 = opcoes_112.index(d112["valor"]) if d112["valor"] in opcoes_112 else None

    col_r112, col_j112 = st.columns([1, 2])
    with col_r112:
        r112 = st.radio("Realizou pesquisa?", opcoes_112, index=idx112, key=f"q112_radio_{ano_sel}")
        pts112 = -20.0 if r112 and "Não" in r112 else 0.0

    with col_j112:
        l112 = st.text_area(f"Resultado da Pesquisa {ano_anterior} (11.2):", value=d112.get("link", ""), key=f"l112_text_{ano_sel}")
        
        # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
        links_112_atuais = re.findall(r'(https?://[^\s]+)', l112)
        if links_112_atuais:
            st.markdown(f"🔗 **Link Ativo:** [{links_112_atuais[0]}]({links_112_atuais[0]})")

    # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 11.2
    if r112 is not None and (r112 != d112["valor"] or l112 != d112["link"]):
        save_resp("11.2", r112, pts112, l112)
        
        if links_112_atuais:
            links_112_antigos = re.findall(r'(https?://[^\s]+)', d112.get("link", ""))
            if not links_112_antigos or links_112_atuais[0] != links_112_antigos[0]:
                modal_aviso_link("11.2", links_112_atuais)
            else:
                st.rerun()
        else:
            st.rerun()

    bloco_comentarios("11.2", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 11.2.1 (AÇÕES PÓS-PESQUISA) ---------------------------------
    if r112 and "Sim" in r112:
        st.markdown('<div style="margin-left: 20px; border-left: 2px solid #eee; padding-left: 20px; margin-bottom: 20px;">', unsafe_allow_html=True)
        st.subheader("QUESITO 11.2.1")
        st.write("**Foram realizadas ações com base nesta pesquisa?**")

        d1121 = res_data.get("11.2.1", {"valor": None, "pontos": 0.0, "link": ""})
        opcoes_1121 = ["Sim (00 pts)", "Não (-20 pts)"]
        idx1121 = opcoes_1121.index(d1121["valor"]) if d1121["valor"] in opcoes_1121 else None

        col_r1121, col_j1121 = st.columns([1, 2])
        with col_r1121:
            r1121 = st.radio("Ações realizadas?", opcoes_1121, index=idx1121, key=f"q1121_radio_{ano_sel}")
            pts1121 = -20.0 if r1121 and "Não" in r1121 else 0.0

        with col_j1121:
            l1121 = st.text_area("Descrição das Ações (11.2.1):", value=d1121["link"], key=f"l1121_text_{ano_sel}")
            
            # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
            links_1121_atuais = re.findall(r'(https?://[^\s]+)', l1121)
            if links_1121_atuais:
                st.markdown(f"🔗 **Link Ativo:** [{links_1121_atuais[0]}]({links_1121_atuais[0]})")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 11.2.1
        if r1121 is not None and (r1121 != d1121["valor"] or l1121 != d1121["link"]):
            save_resp("11.2.1", r1121, pts1121, l1121)
            
            if links_1121_atuais:
                links_1121_antigos = re.findall(r'(https?://[^\s]+)', d1121["link"])
                if not links_1121_antigos or links_1121_atuais[0] != links_1121_antigos[0]:
                    modal_aviso_link("11.2.1", links_1121_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("11.2.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)


    # -------------------------------------------------------------------------
    # --- QUESITO 11.3 (RESULTADO FINANCEIRO) ---------------------------------
    # -------------------------------------------------------------------------
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 11.3")
    st.write(f"**Quanto ao custo do transporte público (tarifa de remuneração da prestação de serviço de transporte público) e o preço de passagem (tarifa pública cobrada do usuário), informe qual o resultado no ano de 2025:**")

    d113 = res_data.get("11.3", {"valor": None, "pontos": 0.0, "link": ""})
    opcoes_113 = ["Déficit ou subsídio tarifário", "Superávit tarifário", "Não sabe informar"]

    col_r113, col_j113 = st.columns([1, 2])
    with col_r113:
        idx113 = opcoes_113.index(d113["valor"]) if d113["valor"] in opcoes_113 else None
        r113 = st.radio("Resultado:", opcoes_113, index=idx113, key=f"q113_radio_{ano_sel}")

    with col_j113:
        l113 = st.text_area("Justificativa Financeira (11.3):", value=d113["link"], key=f"l113_text_extra_{ano_sel}")
        
        # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
        links_113_atuais = re.findall(r'(https?://[^\s]+)', l113)
        if links_113_atuais:
            st.markdown(f"🔗 **Link Ativo:** [{links_113_atuais[0]}]({links_113_atuais[0]})")

    # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 11.3
    if r113 is not None and (r113 != d113["valor"] or l113 != d113["link"]):
        save_resp("11.3", r113, 0.0, l113)
        
        if links_113_atuais:
            links_113_antigos = re.findall(r'(https?://[^\s]+)', d113["link"])
            if not links_113_antigos or links_113_atuais[0] != links_113_antigos[0]:
                modal_aviso_link("11.3", links_113_atuais)
            else:
                st.rerun()
        else:
            st.rerun()


    # --- 11.3.1 (TRANSPARÊNCIA TARIFÁRIA) -----------------------------------
    st.divider()
    st.subheader("QUESITO 11.3.1")
    st.write("**Informe a página eletrônica (link na internet) em que os benefícios tarifários concedidos no valor das tarifas do transporte público foram divulgados: Se não estiver disponível na internet, inserir no campo de resposta o texto XYZ**")

    d1131 = res_data.get("11.3.1", {"valor": "Link fornecido", "pontos": 0.0, "link": ""})
    l1131 = st.text_input("Link (Transparência):", value=d1131["link"], key=f"l1131_text_{ano_sel}")
    
    # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
    links_1131_atuais = re.findall(r'(https?://[^\s]+)', l1131)
    if links_1131_atuais:
        st.markdown(f"🔗 **Link Ativo:** [{links_1131_atuais[0]}]({links_1131_atuais[0]})")

    # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 11.3.1
    if l1131 != d1131["link"]:
        if l1131 != "" or d1131["link"] != "":
            save_resp("11.3.1", "Link fornecido", 0.0, l1131)
            
            if links_1131_atuais:
                links_1131_antigos = re.findall(r'(https?://[^\s]+)', d1131["link"])
                if not links_1131_antigos or links_1131_atuais[0] != links_1131_antigos[0]:
                    modal_aviso_link("11.3.1", links_1131_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

    bloco_comentarios("11.3.1", res_data)
    bloco_comentarios("11.3", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # --- QUESITO 12.0 (TRANSPORTE POR APP) -----------------------------------
    # -------------------------------------------------------------------------
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 12.0")
    st.write("**O Município possui transporte remunerado privado individual (App)?**")

    d120 = res_data.get("12.0", {"valor": None, "pontos": 0.0, "link": ""})
    col_r120, col_j120 = st.columns([1, 2])
    opcoes_120 = ["Sim", "Não"]

    with col_r120:
        idx120 = opcoes_120.index(d120["valor"]) if d120["valor"] in opcoes_120 else None
        r120 = st.radio("Possui transporte por App?", opcoes_120, index=idx120, key=f"q120_radio_{ano_sel}")

    with col_j120:
        l120 = st.text_area("Empresas atuantes (12.0):", value=d120["link"], key=f"l120_text_{ano_sel}")
        
        # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
        links_120_atuais = re.findall(r'(https?://[^\s]+)', l120)
        if links_120_atuais:
            st.markdown(f"🔗 **Link Ativo:** [{links_120_atuais[0]}]({links_120_atuais[0]})")

    # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 12.0
    if r120 is not None and (r120 != d120["valor"] or l120 != d120["link"]):
        save_resp("12.0", r120, 0.0, l120)
        
        if links_120_atuais:
            links_120_antigos = re.findall(r'(https?://[^\s]+)', d120["link"])
            if not links_120_antigos or links_120_atuais[0] != links_120_antigos[0]:
                modal_aviso_link("12.0", links_120_atuais)
            else:
                st.rerun()
        else:
            st.rerun()

    bloco_comentarios("12.0", res_data)
    st.markdown('</div>', unsafe_allow_html=True)


    # -------------------------------------------------------------------------
    # --- QUESITO 12.1 (REGULAMENTAÇÃO APP) -----------------------------------
    # -------------------------------------------------------------------------
    # Inicialização de segurança unificada a partir do cache
    d121_cache = res_data.get("12.1", {"valor": None})
    r121 = d121_cache["valor"]

    if r120 and "Sim" in str(r120):
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 12.1")
        st.write("**O Município regulamentou o transporte remunerado privado individual?**")

        d121 = res_data.get("12.1", {"valor": None, "pontos": 0.0, "link": ""})
        opts121 = {"Sim (00 pts)": 0.0, "Não (-50 pts)": -50.0}
        lista_opcoes_121 = list(opts121.keys())
        idx121 = lista_opcoes_121.index(d121["valor"]) if d121["valor"] in lista_opcoes_121 else None

        col_r121, col_j121 = st.columns([1, 2])
        with col_r121:
            r121 = st.radio("Regulamentado?", lista_opcoes_121, index=idx121, key=f"q121_radio_{ano_sel}")

        with col_j121:
            l121 = st.text_area("Evidência (Lei/Decreto) (12.1):", value=d121["link"], key=f"l121_text_{ano_sel}")
            
            # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
            links_121_atuais = re.findall(r'(https?://[^\s]+)', l121)
            if links_121_atuais:
                st.markdown(f"🔗 **Link Ativo:** [{links_121_atuais[0]}]({links_121_atuais[0]})")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 12.1
        if r121 is not None and (r121 != d121["valor"] or l121 != d121["link"]):
            pts_121 = float(opts121.get(r121, 0.0))
            save_resp("12.1", r121, pts_121, l121)
            
            if links_121_atuais:
                links_121_antigos = re.findall(r'(https?://[^\s]+)', d121["link"])
                if not links_121_antigos or links_121_atuais[0] != links_121_antigos[0]:
                    modal_aviso_link("12.1", links_121_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("12.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)


    # -------------------------------------------------------------------------
    # --- QUESITOS 12.1.1 a 12.1.3 (DETALHES DA REGULAMENTAÇÃO) ---------------
    # -------------------------------------------------------------------------
    if r121 and "Sim" in str(r121):
        st.markdown('<div style="margin-left: 20px; border-left: 2px solid #eee; padding-left: 20px; margin-bottom: 20px;">', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("QUESITO 12.1.1")
            st.write("Informe o Instrumento normativo, Número e Data da publicação:")
            d1211 = res_data.get("12.1.1", {"valor": "", "pontos": 0.0, "link": ""})
            v1211 = st.text_input(
                f"Ex: Lei 123 de 01/01/{ano_sel}",
                value=d1211["valor"],
                key=f"q1211_val_{ano_sel}"
            )
            if v1211 != d1211["valor"]:
                if v1211 != "" or d1211["valor"] != "":
                    save_resp("12.1.1", v1211, 0.0, "")
                    st.rerun()
            bloco_comentarios("12.1.1", res_data)

        with col2: # CORRIGIDO: mudado para col2 para não empilhar na mesma coluna horizontal
            st.subheader("QUESITO 12.1.2")
            st.write("Informe a página eletrônica (link na internet) do instrumento normativo:")
            d1212 = res_data.get("12.1.2", {"valor": "Link fornecido", "pontos": 0.0, "link": ""})
            v1212 = st.text_input(
                "URL da norma:",
                value=d1212["link"],
                key=f"q1212_link_{ano_sel}"
            )
            
            # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
            links_1212_atuais = re.findall(r'(https?://[^\s]+)', v1212)
            if links_1212_atuais:
                st.markdown(f"🔗 **Link Ativo:** [{links_1212_atuais[0]}]({links_1212_atuais[0]})")

            if v1212 != d1212["link"]:
                if v1212 != "" or d1212["link"] != "":
                    save_resp("12.1.2", "Link fornecido", 0.0, v1212)
                    
                    if links_1212_atuais:
                        links_1212_antigos = re.findall(r'(https?://[^\s]+)', d1212["link"])
                        if not links_1212_antigos or links_1212_atuais[0] != links_1212_antigos[0]:
                            modal_aviso_link("12.1.2", links_1212_atuais)
                        else:
                            st.rerun()
                    else:
                        st.rerun()
            bloco_comentarios("12.1.2", res_data)

        st.divider()

        # --- 12.1.3 (FISCALIZAÇÃO APP) ---------------------------------------
        st.subheader("QUESITO 12.1.3")
        st.write("**O Município fiscaliza regularmente o transporte remunerado privado individual de passageiros (táxi por aplicativo)?**")

        d1213 = res_data.get("12.1.3", {"valor": None, "pontos": 0.0, "link": ""})
        col_r1213, col_j1213 = st.columns([1, 2])
        opcoes_1213 = ["Sim (00 pts)", "Não (-50 pts)"]

        with col_r1213:
            idx1213 = opcoes_1213.index(d1213["valor"]) if d1213["valor"] in opcoes_1213 else None
            r1213 = st.radio("Fiscaliza?", opcoes_1213, index=idx1213, key=f"q1213_radio_{ano_sel}")

        with col_j1213:
            l1213 = st.text_area("Evidência da fiscalização (12.1.3):", value=d1213["link"], key=f"l1213_text_{ano_sel}")
            
            # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
            links_1213_atuais = re.findall(r'(https?://[^\s]+)', l1213)
            if links_1213_atuais:
                st.markdown(f"🔗 **Link Ativo:** [{links_1213_atuais[0]}]({links_1213_atuais[0]})")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 12.1.3
        if r1213 is not None and (r1213 != d1213["valor"] or l1213 != d1213["link"]):
            pts1213 = -50.0 if "Não" in r1213 else 0.0
            save_resp("12.1.3", r1213, pts1213, l1213)
            
            if links_1213_atuais:
                links_1213_antigos = re.findall(r'(https?://[^\s]+)', d1213["link"])
                if not links_1213_antigos or links_1213_atuais[0] != links_1213_antigos[0]:
                    modal_aviso_link("12.1.3", links_1213_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        # --- 12.1.3.1 (PERIODICIDADE) ---------------------------------------
        if r1213 and "Sim" in r1213:
            st.divider()
            st.subheader("QUESITO 12.1.3.1")
            st.write("Informe a periodicidade da fiscalização:")
            d12131 = res_data.get("12.1.3.1", {"valor": None, "pontos": 0.0, "link": ""})
            perio = ["Diariamente", "Semanalmente", "Mensalmente", "Anualmente"]
            idx_p = perio.index(d12131["valor"]) if d12131["valor"] in perio else None

            r12131 = st.radio("Periodicidade:", perio, index=idx_p, key=f"q12131_radio_{ano_sel}")

            if r12131 is not None and r12131 != d12131["valor"]:
                save_resp("12.1.3.1", r12131, 0.0, "")
                st.rerun()
                
            bloco_comentarios("12.1.3.1", res_data)

        bloco_comentarios("12.1.3", res_data)
        st.markdown('</div>', unsafe_allow_html=True) # Fecha recuo condicional do 12.1

    # -------------------------------------------------------------------------
    # --- QUESITO 13.0 (MOBILIDADE ATIVA) -------------------------------------
    # -------------------------------------------------------------------------
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 13.0")

    # ✔️ CÁLCULO DINÂMICO DO ANO ANTERIOR
    ano_anterior = int(str(ano_sel).strip()[:4]) - 1

    st.write(f"**Foram realizadas ações para estimular a adoção/uso dos meios de transporte não motorizados em {ano_anterior}?**")
    st.caption("Ex: Ciclovias, campanhas de incentivo ao uso de bicicletas ou caminhadas.")

    d130 = res_data.get("13.0", {"valor": None, "pontos": 0.0, "link": ""})
    col_r130, col_j130 = st.columns([1, 2])
    opcoes_130 = ["Sim", "Não"]

    with col_r130:
        idx130 = opcoes_130.index(d130["valor"]) if d130["valor"] in opcoes_130 else None
        r130 = st.radio("Realizou ações?", opcoes_130, index=idx130, key=f"q130_radio_{ano_sel}")

    with col_j130:
        l130 = st.text_area(f"Descrição/Evidências {ano_anterior} (13.0):", value=d130["link"], key=f"l130_text_{ano_sel}")
        
        # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
        links_130_atuais = re.findall(r'(https?://[^\s]+)', l130)
        if links_130_atuais:
            st.markdown(f"🔗 **Link Ativo:** [{links_130_atuais[0]}]({links_130_atuais[0]})")

    # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 13.0
    if r130 is not None and (r130 != d130["valor"] or l130 != d130["link"]):
        save_resp("13.0", r130, 0.0, l130)
        
        if links_130_atuais:
            links_130_antigos = re.findall(r'(https?://[^\s]+)', d130["link"])
            if not links_130_antigos or links_130_atuais[0] != links_130_antigos[0]:
                modal_aviso_link("13.0", links_130_atuais)
            else:
                st.rerun()
        else:
            st.rerun()

    bloco_comentarios("13.0", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- BLOCO CONDICIONAL COMPLETO SE HOUVE MOBILIDADE ATIVA -----------------
    if r130 == "Sim":
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 13.1")
        st.write(f"**Assinale as ações realizadas para estimular a adoção/uso dos meios de transporte não motorizados em {ano_anterior}:**")

        d131 = res_data.get("13.1", {"valor": "[]", "pontos": 0.0, "link": ""})
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
            
            # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
            links_131_atuais = re.findall(r'(https?://[^\s]+)', l131)
            if links_131_atuais:
                st.markdown(f"🔗 **Link Ativo:** [{links_131_atuais[0]}]({links_131_atuais[0]})")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 13.1
        if str(sel_131) != d131["valor"] or l131 != d131["link"]:
            if sel_131 or l131 != "" or d131["valor"] != "[]":
                save_resp("13.1", str(sel_131), 0.0, l131)
                
                if links_131_atuais:
                    links_131_antigos = re.findall(r'(https?://[^\s]+)', d131["link"])
                    if not links_131_antigos or links_131_atuais[0] != links_131_antigos[0]:
                        modal_aviso_link("13.1", links_131_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()

        bloco_comentarios("13.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # --- RECUPERAÇÃO DE SEGURANÇA PARA VARIÁVEIS DO ESCOPO ANTERIOR -------
        d131_cache = res_data.get("13.1", {"valor": "[]"})
        if 'sel_131' not in locals():
            sel_131 = d131_cache["valor"]

        # --- QUESITO 13.1.1 (CRONOGRAMA DE CICLOVIAS) ------------------------
        if "Instalação/manutenção de ciclovias ou ciclofaixas" in str(sel_131):
            st.markdown('<div style="margin-left: 20px; border-left: 2px solid #eee; padding-left: 20px; margin-bottom: 20px;">', unsafe_allow_html=True)
            st.subheader("QUESITO 13.1.1")
            st.write("**Possui um cronograma de manutenção da infraestrutura das ciclovias ou ciclofaixas?**")

            d1311 = res_data.get("13.1.1", {"valor": None, "pontos": 0.0, "link": ""})
            opcoes_1311 = ["Sim (00 pts)", "Não (-20 pts)"]
            idx1311 = opcoes_1311.index(d1311["valor"]) if d1311["valor"] in opcoes_1311 else None

            col_r1311, col_j1311 = st.columns([1, 2])
            with col_r1311:
                r1311 = st.radio("Possui cronograma?", opcoes_1311, index=idx1311, key=f"q1311_radio_{ano_sel}")

            with col_j1311:
                l1311 = st.text_area(f"Link/Arquivo do Cronograma ({ano_sel}) (13.1.1):", value=d1311["link"], key=f"l1311_text_{ano_sel}")
                
                # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
                links_1311_atuais = re.findall(r'(https?://[^\s]+)', l1311)
                if links_1311_atuais:
                    st.markdown(f"🔗 **Link Ativo:** [{links_1311_atuais[0]}]({links_1311_atuais[0]})")

            # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 13.1.1
            if r1311 is not None and (r1311 != d1311["valor"] or l1311 != d1311["link"]):
                pts1311 = 0.0 if "Sim" in r1311 else -20.0
                save_resp("13.1.1", r1311, pts1311, l1311)
                
                if links_1311_atuais:
                    links_1311_antigos = re.findall(r'(https?://[^\s]+)', d1311["link"])
                    if not links_1311_antigos or links_1311_atuais[0] != links_1311_antigos[0]:
                        modal_aviso_link("13.1.1", links_1311_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()

            # --- QUESITO 13.1.1.1 (EXECUÇÃO DO CRONOGRAMA) --------------------
            if r1311 and "Sim" in r1311:
                st.divider()
                st.subheader("QUESITO 13.1.1.1")
                st.write("**As manutenções preventivas da infraestrutura das ciclovias ou ciclofaixas foram realizadas dentro do prazo?**")

                d13111 = res_data.get("13.1.1.1", {"valor": None, "pontos": 0.0, "link": ""})
                opts13111 = {
                    "Sim, para todos os trechos (00 pts)": 0.0,
                    "Sim, para a maior parte dos trechos (-05 pts)": -5.0,
                    "Sim, para a menor parte dos trechos (-10 pts)": -10.0,
                    "Não foram realizadas dentro do prazo (-15 pts)": -15.0,
                    "Não foram realizadas manutenções preventivas no exercício (-20 pts)": -20.0
                }
                lista_opcoes_13111 = list(opts13111.keys())
                idx13111 = lista_opcoes_13111.index(d13111["valor"]) if d13111["valor"] in lista_opcoes_13111 else None

                col_r13111, col_j13111 = st.columns([1, 2])
                with col_r13111:
                    r13111 = st.radio("Status da manutenção:", lista_opcoes_13111, index=idx13111, key=f"q13111_radio_{ano_sel}")

                with col_j13111:
                    l13111 = st.text_area(f"Evidência da execução em {ano_sel} (13.1.1.1):", value=d13111["link"], key=f"l13111_text_{ano_sel}")
                    
                    # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
                    links_13111_atuais = re.findall(r'(https?://[^\s]+)', l13111)
                    if links_13111_atuais:
                        st.markdown(f"🔗 **Link Ativo:** [{links_13111_atuais[0]}]({links_13111_atuais[0]})")

                # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 13.1.1.1
                if r13111 is not None and (r13111 != d13111["valor"] or l13111 != d13111["link"]):
                    save_resp("13.1.1.1", r13111, float(opts13111[r13111]), l13111)
                    
                    if links_13111_atuais:
                        links_13111_antigos = re.findall(r'(https?://[^\s]+)', d13111["link"])
                        if not links_13111_antigos or links_13111_atuais[0] != links_13111_antigos[0]:
                            modal_aviso_link("13.1.1.1", links_13111_atuais)
                        else:
                            st.rerun()
                    else:
                        st.rerun()

                bloco_comentarios("13.1.1.1", res_data)

            bloco_comentarios("13.1.1", res_data)
            st.markdown('</div>', unsafe_allow_html=True) # Fecha o bloco de recuo condicional do 13.1.1

   # -------------------------------------------------------------------------
    # --- QUESITO 14.0 (ACESSIBILIDADE) ---------------------------------------
    # -------------------------------------------------------------------------
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 14.0")
    st.write("**O Município adequou os calçamentos públicos para acessibilidade (PcD e restrição de mobilidade)?**")
    st.caption("Calçamento público é no entorno de prédios públicos e locais de grande circulação.")

    d140 = res_data.get("14.0", {"valor": "Não possui acessibilidade em calçamentos públicos (-50 pts)", "pontos": -50.0, "link": ""})
    opts140 = {
        "Sim, integralmente - Todos os calçamentos públicos (00 pts)": 0.0,
        "Sim, parcialmente - Em parte dos calçamentos públicos (-10 pts)": -10.0,
        "Não possui acessibilidade em calçamentos públicos (-50 pts)": -50.0
    }
    lista_opcoes_140 = list(opts140.keys())
    idx140 = lista_opcoes_140.index(d140["valor"]) if d140["valor"] in lista_opcoes_140 else 2

    col_r140, col_j140 = st.columns([1, 2])
    with col_r140:
        r140 = st.radio("Status da acessibilidade:", lista_opcoes_140, index=idx140, key=f"q140_radio_{ano_sel}")
    
    with col_j140:
        l140 = st.text_area("Locais adequados / Fotos / Links (14.0):", value=d140["link"], key=f"l140_text_{ano_sel}")
        
        # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
        links_140_atuais = re.findall(r'(https?://[^\s]+)', l140)
        if links_140_atuais:
            st.markdown(f"🔗 **Link Ativo:** [{links_140_atuais[0]}]({links_140_atuais[0]})")

    # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 14.0
    if r140 is not None and (r140 != d140["valor"] or l140 != d140["link"]):
        save_resp("14.0", r140, float(opts140[r140]), l140)
        
        if links_140_atuais:
            links_140_antigos = re.findall(r'(https?://[^\s]+)', d140["link"])
            if not links_140_antigos or links_140_atuais[0] != links_140_antigos[0]:
                modal_aviso_link("14.0", links_140_atuais)
            else:
                st.rerun()
        else:
            st.rerun()

    bloco_comentarios("14.0", res_data)
    st.markdown('</div>', unsafe_allow_html=True)


    # --- QUESITO 14.1 (RECURSOS DE ACESSIBILIDADE) ---------------------------
    if r140 and "Não possui acessibilidade" not in r140:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 14.1")
        st.write("**Informe os recursos de acessibilidade oferecidos pela Prefeitura:**")

        d141 = res_data.get("14.1", {"valor": "[]", "pontos": 0.0, "link": ""})
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
            
            # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
            links_141_atuais = re.findall(r'(https?://[^\s]+)', l141)
            if links_141_atuais:
                st.markdown(f"🔗 **Link Ativo:** [{links_141_atuais[0]}]({links_141_atuais[0]})")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 14.1
        if str(sel_141) != d141["valor"] or l141 != d141["link"]:
            save_resp("14.1", str(sel_141), 0.0, l141)
            
            if links_141_atuais:
                links_141_antigos = re.findall(r'(https?://[^\s]+)', d141["link"])
                if not links_141_antigos or links_141_atuais[0] != links_141_antigos[0]:
                    modal_aviso_link("14.1", links_141_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("14.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)


    # -------------------------------------------------------------------------
    # --- QUESITO 15.0 (SINALIZAÇÃO VIÁRIA) -----------------------------------
    # -------------------------------------------------------------------------
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 15.0")
    st.write("**As vias públicas pavimentadas estão devidamente sinalizadas (vertical e horizontalmente) de forma a garantir as condições adequadas de segurança na circulação?**")

    d150 = res_data.get("15.0", {"valor": None, "pontos": 0.0, "link": ""})
    opts150 = {
        "Sim, integralmente - Todas as vias públicas municipais (50 pts)": 50.0,
        "Sim, parcialmente - Em parte das vias municipais (10 pts)": 10.0,
        "Não estão sinalizadas (00 pts)": 0.0
    }
    lista_opcoes_150 = list(opts150.keys())
    idx150 = lista_opcoes_150.index(d150["valor"]) if d150["valor"] in lista_opcoes_150 else None

    col_r150, col_j150 = st.columns([1, 2])
    with col_r150:
        r150 = st.radio("Status da sinalização:", lista_opcoes_150, index=idx150, key=f"q150_radio_{ano_sel}")

    with col_j150:
        l150 = st.text_area(f"Evidências da sinalização ({ano_sel}) (15.0):", value=d150["link"], key=f"l150_text_{ano_sel}")
        
        # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
        links_150_atuais = re.findall(r'(https?://[^\s]+)', l150)
        if links_150_atuais:
            st.markdown(f"🔗 **Link Ativo:** [{links_150_atuais[0]}]({links_150_atuais[0]})")

    # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 15.0
    if r150 is not None and (r150 != d150["valor"] or l150 != d150["link"]):
        save_resp("15.0", r150, float(opts150[r150]), l150)
        
        if links_150_atuais:
            links_150_antigos = re.findall(r'(https?://[^\s]+)', d150["link"])
            if not links_150_antigos or links_150_atuais[0] != links_150_antigos[0]:
                modal_aviso_link("15.0", links_150_atuais)
            else:
                st.rerun()
        else:
            st.rerun()

    bloco_comentarios("15.0", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

   # -------------------------------------------------------------------------
    # --- QUESITO 16.0 (MANUTENÇÃO DE VIAS) -----------------------------------
    # -------------------------------------------------------------------------
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 16.0")
    st.write("**Há manutenção adequada das vias públicas no Município?**")
    st.caption("Referência: Manuais de Manutenção Rodoviária do DNIT.")

    d160 = res_data.get("16.0", {"valor": None, "pontos": 0.0, "link": ""})
    opts160 = {
        "Sim, integralmente - Todas as vias públicas municipais (50 pts)": 50.0,
        "Sim, parcialmente - Em parte das vias municipais (10 pts)": 10.0,
        "Não estão adequadas (00 pts)": 0.0
    }
    lista_opcoes_160 = list(opts160.keys())
    idx160 = lista_opcoes_160.index(d160["valor"]) if d160["valor"] in lista_opcoes_160 else None

    col_r160, col_j160 = st.columns([1, 2])
    with col_r160:
        r160 = st.radio("Qualidade da manutenção:", lista_opcoes_160, index=idx160, key=f"q160_radio_{ano_sel}")

    with col_j160:
        l160 = st.text_area(f"Contratos / Cronograma de Obras ({ano_sel}) (16.0):", value=d160["link"], key=f"l160_text_{ano_sel}")
        
        # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
        links_160_atuais = re.findall(r'(https?://[^\s]+)', l160)
        if links_160_atuais:
            st.markdown(f"🔗 **Link Ativo:** [{links_160_atuais[0]}]({links_160_atuais[0]})")

    # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 16.0
    if r160 is not None and (r160 != d160["valor"] or l160 != d160["link"]):
        save_resp("16.0", r160, float(opts160[r160]), l160)
        
        if links_160_atuais:
            links_160_antigos = re.findall(r'(https?://[^\s]+)', d160["link"])
            if not links_160_antigos or links_160_atuais[0] != links_160_antigos[0]:
                modal_aviso_link("16.0", links_160_atuais)
            else:
                st.rerun()
        else:
            st.rerun()

    bloco_comentarios("16.0", res_data)
    st.markdown('</div>', unsafe_allow_html=True)


    # -------------------------------------------------------------------------
    # --- QUESITO 17.1 (ENCERRAMENTO/FEEDBACK) --------------------------------
    # -------------------------------------------------------------------------
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO 17.1")
    st.write("**Utilize o espaço abaixo para registrar suas impressões e sugestões sobre o questionário.**")

    d171 = res_data.get("17.1", {"valor": None, "pontos": 0.0, "link": ""})
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
        
        # MOSTRA O LINK ATIVO AZUL SE EXISTIR NO CAMPO
        links_171_atuais = re.findall(r'(https?://[^\s]+)', l171)
        if links_171_atuais:
            st.markdown(f"🔗 **Link Ativo:** [{links_171_atuais[0]}]({links_171_atuais[0]})")

    # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 17.1
    if r171 is not None and (r171 != d171["valor"] or l171 != d171["link"]):
        save_resp("17.1", r171, 0.0, l171)
        
        if links_171_atuais:
            links_171_antigos = re.findall(r'(https?://[^\s]+)', d171["link"])
            if not links_171_antigos or links_171_atuais[0] != links_171_antigos[0]:
                modal_aviso_link("17.1", links_171_atuais)
            else:
                st.rerun()
        else:
            st.rerun()

    bloco_comentarios("17.1", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- SEÇÃO: DADOS EXTERNOS ---
    st.markdown("## 🌐 DADOS EXTERNOS DO i-CIDADE")

    # --- QUESITO C1 (ONU MCR2030) ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("QUESITO C1")
    st.write(f"**O Município estava inscrito no Programa Construindo Cidades Resilientes 2030 da ONU?**")

    dc1 = res_data.get("C1", {"valor": None, "pontos": 0, "link": ""})
    opcoes_c1 = ["Sim", "Não"]
    idx_c1 = opcoes_c1.index(dc1["valor"]) if dc1["valor"] in opcoes_c1 else None

    col_rc1, col_jc1 = st.columns([1, 2])
    with col_rc1:
        rc1 = st.radio("Inscrito no MCR2030?", opcoes_c1, index=idx_c1, key=f"qc1_radio_{ano_sel}")

    with col_jc1:
        lc1 = st.text_area(f"Comprovante ({ano_sel}) (C1):", value=dc1["link"], key=f"lc1_text_{ano_sel}")

    if rc1 is not None:
        if rc1 is not None and (rc1 != dc1["valor"] or lc1 != dc1["link"]):
            save_resp("C1", rc1, 0, lc1)
            st.rerun()

    # --- C1.1 (ESTÁGIO ONU) ---
    if rc1 == "Sim":
        st.divider()
        st.subheader("QUESITO C1.1")
        st.write(f"**O Município foi classificado em qual estágio do Programa?**")

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
            if rc11 is not None and (rc11 != dc11["valor"] or lc11 != dc11["link"]):
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
