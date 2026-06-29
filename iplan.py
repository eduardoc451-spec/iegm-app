import warnings
# Filtra qualquer aviso que mencione o parâmetro antigo do Streamlit
warnings.filterwarnings("ignore", message=".*use_container_width.*")
warnings.filterwarnings("ignore", category=UserWarning)

import streamlit as st
import re
import sqlite3
import json
import ast
from io import BytesIO
from datetime import datetime, date

# Bibliotecas para o PDF (Requer: pip install reportlab)
from reportlab.lib import colors as rl_colors  # Ajustado para casar com o rl_colors do seu código
from reportlab.lib import colors  # Mantido caso use 'colors.white' em outro ponto
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.lib.pagesizes import A4

# Bibliotecas para os Gráficos (Requer: pip install plotly)
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# =============================================================================
# CONSTANTES GLOBAIS
# =============================================================================

CATEGORIAS_MAP = {
    "planejamento": {"label": "Planejamento e Orçamento", "qids": ["1.0", "1.1", "1.2", "1.3", "1.3.1", "1.4", "2.0", "2.1", "3.0", "3.1", "3.1.1", "3.2", "4.0", "4.1", "4.1.1", "4.1.1.1", "4.1.1.1.1", "4.1.1.2", "4.1.1.2.1", "4.2", "4.3"]},
    "receita":       {"label": "Receita e LDO", "qids": ["5.0", "5.1", "5.1.1", "5.2", "6.0", "7.0", "7.1", "8.0", "8.1", "8.2", "9.0", "9.1", "9.2"]},
    "compatibilidade": {"label": "Compatibilidade e Créditos", "qids": ["10.0", "11.0", "11.1"]},
    "estrutura":     {"label": "Estrutura e Acompanhamento", "qids": ["12.0", "12.1", "12.1.1", "12.1.2", "13.0", "13.1", "13.1.1", "13.1.1.1", "13.2", "13.3"]},
    "controle":      {"label": "Controle Interno", "qids": ["14.0", "14.1", "14.2", "14.3", "14.4", "14.4.1", "14.4.2", "14.4.3", "14.4.4", "14.4.4.1", "14.4.4.2", "14.4.4.2.1", "14.4.5", "14.4.5.1", "14.4.5.1.1", "14.5", "14.5.1"]},
    "ouvidoria":     {"label": "Ouvidoria e Transparência", "qids": ["15.0", "15.1", "15.2", "15.3", "15.4", "15.4.1", "15.4.2", "15.5", "16.0", "16.1", "16.2", "16.3", "16.3.1", "16.3.2", "17.0", "17.1", "17.2"]},
    "plano_diretor": {"label": "Plano Diretor", "qids": ["18.0", "18.1", "19.0"]},
}

PONTUACOES_MAX = {
    "1.1": 3, "1.2": 2, "1.3.1": 3, "1.4": 4, "2.0": 6, "2.1": 2, "3.1": 14, "3.2": 10, "4.0": 10, "4.1": 15, "4.1.1": 10, "4.1.1.1": 7, "4.1.1.1.1": 60, "4.1.1.2": 4, "4.2": 25, "4.3": 15,
    "5.0": 6, "5.1": 4, "5.1.1": 2, "5.2": 6, "6.0": 3, "8.2": 3.5, "9.2": 3.5, "10.0": 17, "11.1": 6, "13.1": 6, "13.1.1": 3, "13.1.1.1": 2, "13.2": 4, "13.3": 20,
    "14.3": 15, "14.4": 0.5, "14.4.1": 5, "14.4.2": 6, "14.4.3": 5, "14.4.4": 6, "14.4.5": 5, "14.4.5.1": 6, "14.5.1": 5,
    "16.0": 4, "16.1": 2, "16.2": 2, "16.3": 4, "17.0": 4
}

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
# 1. FUNÇÕES DE APOIO E BANCO DE DADOS (IEGM - I-PLAN)
# =============================================================================

def get_connection():
    # Conecta no banco de dados isolado e específico do I-PLAN
    return sqlite3.connect("dados_iplan.db", check_same_thread=False)

def init_db():
    """Cria as tabelas do banco de dados com migração automática e suporte a comentários estruturados em JSON."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Cria a tabela base estruturada
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
        
        # 2. PRAGMA para checar quais colunas realmente existem no arquivo físico do banco do I-PLAN
        cursor.execute("PRAGMA table_info(respostas)")
        colunas_existentes = [row[1] for row in cursor.fetchall()]
        
        # 3. Força a migração da coluna de comentários em JSON se não existir
        if "comentarios" not in colunas_existentes:
            try:
                cursor.execute("ALTER TABLE respostas ADD COLUMN comentarios TEXT")
            except sqlite3.OperationalError:
                pass
                
        # 4. Garante que a coluna 'atualizado_em' esteja com o nome perfeito
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

    try:
        timestamp_atual = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except AttributeError:
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
            st.error(f"Erro operacional no banco do I-PLAN: {e}")
    except Exception as e:
        st.error(f"Erro ao salvar {qid}: {e}")

def bloco_comentarios(questao_id, res_data, sufixo=None):
    """
    Gera o diálogo interno avançado com histórico retrátil, status em realtime
    e controle individual de remoção por lixeira para o módulo I-PLAN.
    """
    # Busca o ano atual de forma segura direto do construtor de data do próprio Python
    import datetime as dt_modulo
    ano_atual_padrao = dt_modulo.date.today().year

    ano_sel = st.session_state.get("ano_referencia_global", ano_atual_padrao)
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
                "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "texto": f"ℹ️ Alterou o status do quesito para: **{novo_status_clicado.upper()}**.",
                "status_definido": novo_status_clicado
            }
            historico.append(log_mudanca)
            save_resp(
                qid=questao_id,
                valor=dados_questao.get("valor", ""),
                pontos=dados_questao.get("pontos", 0.0),
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
                            pontos=dados_questao.get("pontos", 0.0),
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
                        "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "texto": novo_texto.strip(),
                        "status_definido": status_global
                    }
                    historico.append(nova_mensagem)
                    save_resp(
                        qid=questao_id, 
                        valor=dados_questao.get("valor", ""), 
                        pontos=dados_questao.get("pontos", 0.0), 
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
# 3. GERADOR DO RELATÓRIO PDF - i-PLAN
# =============================================================================

def gerar_relatorio_pdf(dados, ano, total, faixa, all_data=None):
    # TEXTO DE TESTE FORÇADO NO LOG:
    print("\n" + "="*50)
    print("DENTRO DO GERADOR DE PDF:")
    print("O que veio no all_data?:", all_data)
    print("="*50 + "\n")    

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    
    styles = getSampleStyleSheet()
    
    style_titulo_capa = ParagraphStyle(
        'TituloCapa', 
        parent=styles['Normal'], 
        fontName='Helvetica-Bold', 
        fontSize=24, 
        leading=28, 
        textColor=colors.HexColor("#2e7d32"), 
        alignment=1
    )
    
    style_ano_capa = ParagraphStyle(
        'AnoCapa', 
        parent=styles['Normal'], 
        fontName='Helvetica', 
        fontSize=16, 
        leading=20,
        textColor=colors.HexColor("#7f8c8d"), 
        alignment=1
    )

    style_tabela_padrao = ParagraphStyle(
        'TextoTabela',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        alignment=0
    )

    style_tabela_centro = ParagraphStyle(
        'TextoTabelaCentro',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        alignment=1
    )

    def limpar_xml(texto):
        return str(texto).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    
    if all_data is None:
        all_data = {}

    # =========================================================================
    # CORREÇÃO CRÍTICA: Força a conversão de chaves para String e faz Fallback
    # =========================================================================
    all_data_limpo = {str(k).strip(): v for k, v in all_data.items()}
    ano_alvo = str(ano).strip()[:4]
    ano_atual = int(ano_alvo)
    
    if ano_alvo not in all_data_limpo or not all_data_limpo[ano_alvo]:
        if '2024' in all_data_limpo and all_data_limpo['2024']:
            print(f"--- [AVISO PDF] Ano {ano_alvo} veio vazio. Usando fallback dos dados de 2024! ---")
            dados_historico = all_data_limpo['2024']
        else:
            dados_historico = {}
    else:
        dados_historico = all_data_limpo[ano_alvo]
    # ========================================================================= 
        
    if 'PONTUACOES_MAX' not in globals():
        PONTUACOES_MAX = {
            "1.1.2": 20.0, "1.1.3": 5.0, "1.2": 20.0, "2.0": 10.0, "2.1": 50.0, "3.0": 10.0, "3.1": 20.0, "4.0": 20.0,
            "5.2.1": 20.0, "6.0": 20.0, "6.1": 50.0, "6.2": 25.0, "7.2": 2.0, "7.3": 10.0, "7.3.1": 20.0, "7.4": 10.0,
            "7.4.1": 20.0, "7.5": 30.0, "7.7": 30.0, "7.8": 20.0, "7.8.1": 50.0, "7.9": 3.0, "8.2": 2.0, "8.3": 10.0,
            "8.4": 20.0, "8.4.1": 10.0, "8.4.2": 30.0, "8.4.3": 50.0, "9.2": 100.0, "9.3": 5.0, "9.3.1": 5.0,
            "11.2": 2.0, "11.3": 30.0, "11.3.2": 20.0, "11.3.3": 40.0, "11.5": 10.0, "12.1": 54.0, "14.3": 30.0,
            "15": 2.0, "15.1": 3.0, "A4.1.1": 90.0, "A4.1.2": 20.0, "A4.1.3": 22.0, "A6": 5.0, "11": 10.0
        }
    else:
        PONTUACOES_MAX = globals()['PONTUACOES_MAX']

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
    elements.append(Paragraph("Relatório i-PLAN", style_titulo_capa))
    elements.append(Spacer(1, 5))
    elements.append(Paragraph("Índice de Planejamento", ParagraphStyle('SubCapa', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=14, leading=18, textColor=colors.HexColor("#718096"), alignment=1)))
    elements.append(Spacer(1, 15))
    
    elements.append(Paragraph(str(ano), style_ano_capa))
    elements.append(PageBreak())

    # -------------------------------------------------------------------------
    # FOLHA 2: SUMÁRIO
    # -------------------------------------------------------------------------
    elements.append(Paragraph("<b>SUMÁRIO</b>", styles["h1"]))
    elements.append(Spacer(1, 30))

    style_item_esquerda = ParagraphStyle('ItemEsq', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, leading=14, textColor=colors.HexColor("#2c3e50"))
    style_pag_direita = ParagraphStyle('PagDir', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, leading=14, textColor=colors.HexColor("#2e7d32"), alignment=2)

    dados_sumario = [
        [Paragraph("1. Resumo Executivo (Análise Comparativa Planejamento)", style_item_esquerda), Paragraph("Pág. 3", style_pag_direita)],
        [Paragraph("2. Análise de Desempenho por Quesito i-PLAN", style_item_esquerda), Paragraph("Pág. 3", style_pag_direita)],
        [Paragraph("3. Análise de Impacto e Penalidades", style_item_esquerda), Paragraph("Pág. 4", style_pag_direita)],
        [Paragraph("4. Diagnóstico de Reincidências", style_item_esquerda), Paragraph("Pág. 4", style_pag_direita)],
        [Paragraph("5. Alinhamento com a Agenda 2030 (ODS Meio Ambiente)", style_item_esquerda), Paragraph("Pág. 4", style_pag_direita)],
        [Paragraph("6. Série Histórica Planejamento", style_item_esquerda), Paragraph("Pág. 5", style_pag_direita)],
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
    elements.append(Paragraph(f"RELATÓRIO DE AUDITORIA i-PLAN (PLANEJAMENTO) - {ano}", styles["Title"]))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("<b>1. RESUMO EXECUTIVO (ANÁLISE COMPARATIVA I-PLAN)</b>", styles["h2"]))
    elements.append(Spacer(1, 8))

    nota_atual = float(total)

    def converter_pontos_em_faixa_iplan(pontos):
        pts = float(pontos)
        if pts <= 499.0:     return "C"
        elif pts <= 599.0:   return "C+"
        elif pts <= 749.0:   return "B"
        elif pts <= 899.0:   return "B+"
        else:                return "A"

    # --- DESCOBERTA DINÂMICA DO HISTÓRICO REAL ANTERIOR (BLINDAGEM CONTRA SALTO DE ANOS) ---
    anos_com_dados = sorted([int(k) for k in all_data_limpo.keys() if all_data_limpo[k]], reverse=True)
    
    ano_ant_real = None
    dados_originais_ant = {}

    for a in anos_com_dados:
        if a < ano_atual:
            ano_ant_real = a
            dados_originais_ant = all_data_limpo[str(a)]
            break

    # Fallback padrão caso o banco de dados histórico esteja completamente zerado
    if ano_ant_real is None:
        ano_ant_real = ano_atual - 1
        dados_originais_ant = {}

    ano_ant = ano_ant_real
    dados_ano_anterior = {}
    
    if isinstance(dados_originais_ant, dict):
        for k, v in dados_originais_ant.items():
            dados_ano_anterior[str(k).strip()] = v

    nota_anterior = 0.0
    for qid_ant, info_ant in dados_ano_anterior.items():
        if str(qid_ant).startswith("COM_"):
            continue
            
        if isinstance(info_ant, dict):
            nota_anterior += float(info_ant.get("pontos", 0.0))
        elif isinstance(info_ant, (int, float)):
            nota_anterior += float(info_ant)

    faixa_anterior = converter_pontos_em_faixa_iplan(nota_anterior)
    faixa_real_atual = faixa if faixa else converter_pontos_em_faixa_iplan(nota_atual)

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

    style_th = ParagraphStyle('Th', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=13, textColor=colors.whitesmoke, alignment=1)
    style_td_ano = ParagraphStyle('TdAno', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=13, textColor=colors.HexColor("#2c3e50"), alignment=1)
    style_td_pts = ParagraphStyle('TdPts', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=12, leading=15, alignment=1)
    style_td_faixa = ParagraphStyle('TdFaixa', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=12, leading=15, textColor=colors.HexColor("#2e7d32"), alignment=1)
    style_td_var = ParagraphStyle('TdVar', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=12, leading=15, textColor=cor_variacao, alignment=1)

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
        texto_analise = f"<b>Análise de Tendência:</b> O município registrou uma evolução de desempenho com incremento de <b>{texto_percentual}</b> na sua pontuação global socioambientais comparado ao exercício de {ano_ant}."
    elif variacao_pontos < 0:
        texto_analise = f"<b>Análise de Tendência:</b> <font color='#dc3545'><b>Alerta de Retrocesso:</b></font> Foi identificada uma redução de <b>{texto_percentual}</b> na eficiência dos indicadores de sustentabilidade e conservação em relação a {ano_ant}."
    else:
        texto_analise = f"<b>Análise de Tendência:</b> O município apresentou estagnação absoluta (0.00%) no seu índice geral de conformidade ambiental."

    elements.append(Paragraph(texto_analise, style_analise))
    elements.append(Spacer(1, 15))

    # =========================================================================
    # 2. ANÁLISE DE DESEMPENHO POR QUESITO
    # =========================================================================
    elements.append(Paragraph("<b>2. ANÁLISE DE DESEMPENHO POR QUESITO</b>", styles["h2"]))
    elements.append(Spacer(1, 6))

    lista_pontos_fortes = []
    lista_pontos_fracos = []
    dados_consolidados = {}

    subquestoes_11 = ["11.2", "11.3", "11.3.2", "11.3.3", "11.5"]
    resposta_11_nao = False
    if "11" in dados and isinstance(dados["11"], dict):
        if str(dados["11"].get("valor", "")).strip().lower() in ["não", "nao", "n"]:
            resposta_11_nao = True

    for sub_id in subquestoes_11:
        if resposta_11_nao or (sub_id not in dados):
            dados[sub_id] = {
                "pontos": 0.0,
                "valor": "Não aplicável / Não implantado (Mãe respondida como Não)",
                "link": ""
            }

    for qid, info in dados.items():
        if qid.startswith("COM_") or not isinstance(info, dict): 
            continue
        
        pts_obtidos = float(info.get("pontos", 0))
        valor_resposta = info.get("valor", "")
        link_evidencia = info.get("link", "")

        qid_str = str(qid).strip()
        
        if qid_str.startswith("A4.1.1_"):   chave_mae = "A4.1.1"
        elif qid_str.startswith("A4.1.2_"): chave_mae = "A4.1.2"
        elif qid_str.startswith("A4.1.3_"): chave_mae = "A4.1.3"
        elif qid_str == "11" or qid_str.startswith("11."):
            if qid_str in PONTUACOES_MAX:
                chave_mae = qid_str
            else:
                chave_mae = "11"
        else:
            chave_mae = qid_str

        if chave_mae not in PONTUACOES_MAX:
            continue

        if chave_mae not in dados_consolidados:
            dados_consolidados[chave_mae] = {"pts_obtidos": 0.0, "valores": [], "links": []}
        
        dados_consolidados[chave_mae]["pts_obtidos"] += pts_obtidos
        
        if valor_resposta:
            sub_nome = qid_str.split('_')[-1] if '_' in qid_str else qid_str
            dados_consolidados[chave_mae]["valores"].append(f"{sub_nome}: {limpar_xml(valor_resposta)}")
            
        if link_evidencia:
            link_limpo = limpar_xml(link_evidencia)
            if link_limpo not in dados_consolidados[chave_mae]["links"]:
                dados_consolidados[chave_mae]["links"].append(link_limpo)

    for qid, info in dados_consolidados.items():
        pts_maximo = float(PONTUACOES_MAX.get(qid, 10.0))
        if pts_maximo <= 0: pts_maximo = 10.0
            
        pts_obtidos = max(0.0, min(info["pts_obtidos"], pts_maximo))
        eficiencia = (pts_obtidos / pts_maximo) * 100
        
        respostas_unificadas = " | ".join(info["valores"]) if info["valores"] else "-"
        evidencias_unificadas = ", ".join(info["links"]) if info["links"] else ""

        item_data = {
            "qid": qid, 
            "pts_obtidos": pts_obtidos, 
            "pts_maximo": pts_maximo, 
            "eficiencia": eficiencia, 
            "valor": respostas_unificadas, 
            "link": evidencias_unificadas
        }

        if eficiencia >= 100.0: 
            lista_pontos_fortes.append(item_data)
        else:
            lista_pontos_fracos.append(item_data)

    # CORREÇÃO: Estruturação limpa da montagem final do esqueleto Reportlab (Substituído o 'f' solto)
    if lista_pontos_fortes:
        elements.append(Paragraph("<b>✅ Pontos Fortes Planejamento:</b>", styles["h3"]))
        data_fortes = [[
            Paragraph("Quesito", style_th), 
            Paragraph("Nota / Teto", style_th), 
            Paragraph("Eficiência", style_th), 
            Paragraph("Resposta / Evidência", style_th)
        ]]
        for item in sorted(lista_pontos_fortes, key=lambda x: x["pts_obtidos"], reverse=True):
            texto_celula = f"<b>{item['valor']}</b>"
            if item['link']:
                texto_celula += f"<br/><font size=8 color='gray'>{item['link']}</font>"
            data_fortes.append([
                Paragraph(item['qid'], style_tabela_centro), 
                Paragraph(f"{item['pts_obtidos']:.1f} / {item['pts_maximo']:.1f}", style_tabela_centro), 
                Paragraph(f"{item['eficiencia']:.1f}%", style_tabela_centro), 
                Paragraph(texto_celula, style_tabela_padrao)
            ])
        
        tabela_fortes = Table(data_fortes, colWidths=[65, 75, 65, 285])
        tabela_fortes.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2e7d32")), 
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#2e7d32")), 
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(tabela_fortes)
        elements.append(Spacer(1, 12))

    if lista_pontos_fracos:
        elements.append(Paragraph("<b>⚠️ Pontos Fracos / Oportunidades de Melhoria:</b>", styles["h3"]))
        data_fracos = [[
            Paragraph("Quesito", style_th), 
            Paragraph("Nota / Teto", style_th), 
            Paragraph("Eficiência", style_th), 
            Paragraph("Resposta / Evidência", style_th)
        ]]
        for item in sorted(lista_pontos_fracos, key=lambda x: x["eficiencia"]):
            texto_celula = f"<b>{item['valor']}</b>"
            if item['link']:
                texto_celula += f"<br/><font size=8 color='gray'>{item['link']}</font>"
            data_fracos.append([
                Paragraph(item['qid'], style_tabela_centro), 
                Paragraph(f"{item['pts_obtidos']:.1f} / {item['pts_maximo']:.1f}", style_tabela_centro), 
                Paragraph(f"{item['eficiencia']:.1f}%", style_tabela_centro), 
                Paragraph(texto_celula, style_tabela_padrao)
            ])
        
        tabela_fracos = Table(data_fracos, colWidths=[65, 75, 65, 285])
        tabela_fracos.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e67e22")), 
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e67e22")), 
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(tabela_fracos)
        elements.append(Spacer(1, 15))

    # =========================================================================
    # 3. ANÁLISE DE IMPACTO E PENALIDADES
    # =========================================================================
    elements.append(Paragraph("<b>3. ANÁLISE DE IMPACTO E PENALIDADES</b>", styles["h2"]))
    elements.append(Spacer(1, 6))

    PENALIDADES_MAX = {
    "4.3": -10.0,
    "7.1": -30.0,
    "8.1": -10.0,
    "9.1": -10.0,
    "10.0": -10.0,
    "12.1.1": -10.0,
    "12.1.2": -10.0,
    "13.1": -10.0,
    "14.4.4.1": -6.0,
    "14.4.4.2": -3.0,
    "14.4.5.1.1": -3.0,
    "15.3": -2.5,
    "15.4.1": -10.0,
    "15.4.2": -10.0,
    "15.5": -1.0,
    "18.1": -10.0
    }
   
    dados_penalidades = dados.copy()
    reincidencias_detectadas = []

    for qid_pen, val_max in PENALIDADES_MAX.items():
        if qid_pen not in dados_penalidades:
            dados_penalidades[qid_pen] = {"pontos": val_max, "valor": "Não preenchido", "link": ""}

    lista_penalidades = []
    
    for qid, pen_max in PENALIDADES_MAX.items():
        if qid in dados_penalidades:
            info = dados_penalidades[qid]
            nota_real = float(info.get("pontos", 0.0))
            nota_risco = nota_real if nota_real <= 0.0 else 0.0
            
            if pen_max != 0:
                eficiencia_preventiva = (1.0 - (nota_risco / pen_max)) * 100.0
            else:
                eficiencia_preventiva = 100.0
                
            eficiencia_preventiva = max(0.0, min(eficiencia_preventiva, 100.0))

            lista_penalidades.append({
                "qid": qid, "nota_real": nota_real, "pen_max": pen_max, "eficiencia": eficiencia_preventiva, 
                "valor": info.get("valor", ""), "link": info.get("link", "")
            })
            
            # BUSCA DINÂMICA DE REINCIDÊNCIA EM PENALIDADES
            qid_limpo = str(qid).strip()
            if eficiencia_preventiva < 100.0 and qid_limpo in dados_ano_anterior:
                info_ant = dados_ano_anterior[qid_limpo]
                if isinstance(info_ant, dict):
                    nota_real_ant = float(info_ant.get("pontos", 0.0))
                elif isinstance(info_ant, (int, float)):
                    nota_real_ant = float(info_ant)
                else:
                    nota_real_ant = 0.0
                    
                if nota_real == nota_real_ant:
                    reincidencias_detectadas.append({
                        "qid": qid, "tipo": "Penalidade Aplicada", 
                        "detalhe": f"Impacto Recorrente de Penalidade de {nota_real:.1f} pts", 
                        "ant": f"{nota_real_ant:.1f} pts", "atual": f"{nota_real:.1f} pts"
                    })

    if lista_penalidades:
        data_penalidades = [[
            Paragraph("Quesito", style_th), 
            Paragraph("Penalidade Aplicada", style_th), 
            Paragraph("Pior Cenário", style_th), 
            Paragraph("Eficiência Preventiva", style_th), 
            Paragraph("Status de Risco", style_th)
        ]]
        
        def ordenar_quesitos(x):
            limpo = ''.join(c for c in x["qid"] if c.isdigit() or c == '.')
            partes = [int(i) for i in limpo.split('.') if i.isdigit()]
            return partes if partes else [999]

        for item in sorted(lista_penalidades, key=ordenar_quesitos):
            nota_txt = f"{item['nota_real']:.1f} pts"
            teto_txt = f"{item['pen_max']:.1f} pts"
            ef_txt = f"{item['eficiencia']:.1f}%"
            
            if item['eficiencia'] >= 100.0: 
                status = "<font color='#2e7d32'><b>Risco Mitigado</b></font>"
            elif item['eficiencia'] <= 0.0: 
                status = "<font color='#c0392b'><b>Impacto Máximo</b></font>"
            else: 
                status = "<font color='#d35400'><b>Impacto Parcial</b></font>"
                
            data_penalidades.append([
                Paragraph(item['qid'], style_tabela_centro), 
                Paragraph(nota_txt, style_tabela_centro), 
                Paragraph(teto_txt, style_tabela_centro), 
                Paragraph(ef_txt, style_tabela_centro), 
                Paragraph(status, style_tabela_padrao)
            ])
            
        tabela_pen = Table(data_penalidades, colWidths=[70, 110, 80, 115, 125])
        tabela_pen.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1b4f72")), 
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#1b4f72")), 
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(tabela_pen)
        elements.append(Spacer(1, 15))
 
    # =========================================================================
    # 4. DIAGNÓSTICO DE REINCIDÊNCIAS (GARGALOS PERSISTENTES i-PLAN)
    # =========================================================================
    elements.append(Paragraph("<b>4. DIAGNÓSTICO DE REINCIDÊNCIAS (GARGALOS PERSISTENTES)</b>", styles["h2"]))
    elements.append(Spacer(1, 6))
    
    # Nota: A lista 'reincidencias_detectadas' já foi populada dinamicamente 
    # na Seção 3 ao comparar os impactos reais das penalidades entre os dois anos.

    # Renderização da Tabela de Gargalos Baseada nas Penalidades do i-PLAN
    if reincidencias_detectadas:
        data_reinc = [[
            Paragraph("Quesito", style_th),
            Paragraph("Macro-Categoria", style_th),
            Paragraph("Descrição do Gargalo", style_th),
            Paragraph("Exercício Ant.", style_th),
            Paragraph("Exercício Atual", style_th)
        ]]
        for reinc in reincidencias_detectadas:
            data_reinc.append([
                Paragraph(reinc["qid"], style_tabela_centro),
                Paragraph(reinc["tipo"], style_tabela_padrao),
                Paragraph(reinc["detalhe"], style_tabela_padrao),
                Paragraph(reinc["ant"], style_tabela_centro),
                Paragraph(reinc["atual"], style_tabela_centro)
            ])
        tabela_reinc = Table(data_reinc, colWidths=[60, 110, 170, 80, 80])
        tabela_reinc.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#78281f")),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#78281f")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(tabela_reinc)
    else:
        elements.append(Paragraph("<i>Nenhuma reincidência de impacto crítico por penalidade detectada entre os dois exercícios analíticos.</i>", style_analise))

    # -------------------------------------------------------------------------
    # 5. ALINHAMENTO COM A AGENDA 2030 (METAS ODS / ONU - PADRÃO i-PLAN)
    # -------------------------------------------------------------------------
    elements.append(Paragraph("<b>5. ALINHAMENTO COM A AGENDA 2030 (METAS ODS / ONU)</b>", styles["h2"]))
    elements.append(Spacer(1, 6))

    def calcular_percentual_checklist(resposta_bruta, total_itens):
        if not resposta_bruta: return 0.0
        # Divide as opções selecionadas por vírgula
        itens = [i.strip().lower() for i in str(resposta_bruta).split(",") if i.strip()]
        # Remove eventuais strings vazias ou nulas
        itens_validos = [i for i in itens if i and "não" not in i]
        if total_itens <= 0: return 0.0
        return min((len(itens_validos) / total_itens) * 100.0, 100.0)

    analise_ods = []
    
    for qid, info in dados.items():
        if qid.startswith("COM_") or not isinstance(info, dict): 
            continue
            
        resp = str(info.get("valor", "")).strip()
        resp_l = resp.lower()
        metas = ""
        status = ""
        
        # ---------------------------------------------------------------------
        # REGRAS DE MAPEAMENTO DOS QUESITOS E METAS ODS (i-PLAN)
        # ---------------------------------------------------------------------
        if qid == "1.0":
            metas = "16.6"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"
            
        elif qid == "1.2":
            metas = "16.6"
            condicoes_12 = ["dia de semana após horário comercial", "aos sábados, domingos e feriados", "sábados", "domingos", "feriados"]
            status = "Atendido" if any(c in resp_l for c in condicoes_12) else "Não Atendido"
            
        elif qid == "1.3":
            metas = "16.6"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"
            
        elif qid == "1.4": # Checklist com 8 opções
            metas = "16.6"
            status = f"{calcular_percentual_checklist(resp, 8):.1f}% Atendido"
            
        elif qid in ["2", "2.0"]:
            metas = "16.6"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"
            
        elif qid == "2.1":
            metas = "16.6"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"
            
        elif qid == "3.0":
            metas = "16.6, 17.14"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"
            
        elif qid == "3.1":
            metas = "16.6, 17.14"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"
            
        elif qid == "3.2":
            metas = "16.6"
            status = "Atendido" if "sim, para todos os programas ppa" in resp_l else "Não Atendido"
            
        elif qid == "4.0":
            metas = "16.6, 17.14"
            status = "Atendido" if "sim, com metas físicas e financeiras" in resp_l else "Não Atendido"
            
        elif qid == "4.1.1.1.1": # Checklist com 3 opções
            metas = "16.6"
            status = f"{calcular_percentual_checklist(resp, 3):.1f}% Atendido"
            
        elif qid == "4.1.1.2":
            metas = "16.6, 17.14"
            status = "Atendido" if "sim, para todos os programas finalísticos avaliados do ppa" in resp_l else "Não Atendido"
            
        elif qid == "4.2":
            metas = "16.6, 17.14"
            status = "Atendido" if "todos os indicadores do ppa" in resp_l else "Não Atendido"
            
        elif qid == "4.3": # Checklist com 9 opções
            metas = "16.6"
            status = f"{calcular_percentual_checklist(resp, 9):.1f}% Atendido"
            
        elif qid == "5.0":
            metas = "16.6, 17.1"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"
            
        elif qid == "5.1": # Checklist com 7 opções
            metas = "16.6, 17.1"
            status = f"{calcular_percentual_checklist(resp, 7):.1f}% Atendido"
            
        elif qid == "5.1.1":
            metas = "16.6, 17.1"
            status = "Atendido" if "sim, com reestimativa da receita prevista na loa no decorrer da execução orçamentária-financeira" in resp_l else "Não Atendido"
            
        elif qid == "5.2":
            metas = "16.6, 17.1"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"
            
        elif qid == "6.0": # Checklist com 11 opções
            metas = "16.6"
            status = f"{calcular_percentual_checklist(resp, 11):.1f}% Atendido"
            
        elif qid == "7.0":
            metas = "16.6"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"
            
        elif qid == "8.0":
            metas = "16.6"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"
            
        elif qid == "8.2": # Checklist com 8 opções
            metas = "16.6"
            status = f"{calcular_percentual_checklist(resp, 8):.1f}% Atendido"
            
        elif qid == "9.0":
            metas = "16.6"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"
            
        elif qid == "9.2": # Checklist com 6 opções
            metas = "16.6"
            status = f"{calcular_percentual_checklist(resp, 6):.1f}% Atendido"
            
        elif qid == "10.0": # Checklist com 9 opções
            metas = "16.6"
            status = f"{calcular_percentual_checklist(resp, 9):.1f}% Atendido"
            
        elif qid == "12.0":
            metas = "16.6"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"
            
        elif qid == "12.1":
            metas = "16.6"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"
            
        elif qid == "12.1.1":
            metas = "16.6"
            status = "Atendido" if "sim, todos os servidores possuem qualificação técnica" in resp_l else "Não Atendido"
            
        elif qid == "12.1.2":
            metas = "16.6"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"
            
        elif qid in ["13", "13.0"]:
            metas = "16.6"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"
            
        elif qid == "13.1": # Checklist com 3 opções
            metas = "16.6"
            status = f"{calcular_percentual_checklist(resp, 3):.1f}% Atendido"
            
        elif qid == "13.1.1": # Checklist com 3 opções
            metas = "16.6"
            status = f"{calcular_percentual_checklist(resp, 3):.1f}% Atendido"
            
        elif qid == "13.2":
            metas = "16.6"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"
            
        elif qid == "14.0":
            metas = "16.6"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"
            
        elif qid == "14.3": # Checklist com 15 opções
            metas = "16.6"
            status = f"{calcular_percentual_checklist(resp, 15):.1f}% Atendido"
            
        elif qid == "14.4":
            metas = "16.6"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"
            
        elif qid == "14.4.1":
            metas = "16.6"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"
            
        elif qid == "14.4.5":
            metas = "16.6"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"
            
        elif qid == "15.0":
            metas = "16.1"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"
            
        elif qid == "15.4":
            metas = "16.1"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"
            
        elif qid == "16.0":
            metas = "16.6"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"
            
        elif qid == "16.2":
            metas = "16.6, 16.7"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"
            
        elif qid == "16.3":
            metas = "16.6, 16.7"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"
            
        elif qid == "17.0":
            metas = "16.6, 16.7"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"
            
        elif qid == "18.0":
            metas = "16.6"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"

        if metas: 
            analise_ods.append({"qid": qid, "status": status, "metas": metas, "resp": resp[:50]})

    if analise_ods:
        data_ods = [["Quesito", "Resposta Informada", "Vínculo Metas ODS", "Status de Cumprimento"]]
        style_td_ods = ParagraphStyle('TdOds', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, alignment=1)
        
        # Ordenação inteligente de chaves aninhadas (ex: 4.1.1.1.1 antes de 4.1.1.2)
        def sort_key_ods(x):
            partes = [int(i) for i in ''.join(c for c in x['qid'] if c.isdigit() or c == '.').split('.') if i.isdigit()]
            return partes if partes else [999]

        for item in sorted(analise_ods, key=sort_key_ods):
            st_txt = item["status"]
            if "Não Atendido" in st_txt: 
                st_p = Paragraph(f"<font color='#dc3545'><b>{st_txt}</b></font>", style_td_ods)
            elif "Atendido" in st_txt and "%" not in st_txt: 
                st_p = Paragraph(f"<font color='#28a745'><b>{st_txt}</b></font>", style_td_ods)
            else: 
                st_p = Paragraph(f"<font color='#007bff'><b>{st_txt}</b></font>", style_td_ods)
                
            data_ods.append([item["qid"], Paragraph(item["resp"], styles["Normal"]), item["metas"], st_p])
            
        tabela_ods = Table(data_ods, colWidths=[65, 195, 115, 110])
        tabela_ods.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f9d58")), 
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke), 
            ("ALIGN", (0, 0), (0, -1), "CENTER"), 
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#0f9d58")), 
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        elements.append(tabela_ods)
        elements.append(Spacer(1, 15))

    # -------------------------------------------------------------------------
    # 📊 6. SÉRIE HISTÓRICA DO I-PLAN (CONSOLIDADO FINAL)
    # -------------------------------------------------------------------------
    elements.append(Spacer(1, 10))

    anos_serie = [2023, 2024, 2025, 2026, 2027, 2028, 2029, 2030]
    valores_serie = []
    
    for a in anos_serie:
        a_str = str(a)
        
        # Alinhado de volta para 'ano_atual' e 'nota_atual' que você usa no escopo
        if a == ano_atual: 
            valores_serie.append(nota_atual)
        elif a_str in all_data and all_data[a_str]:
            soma_ano = float(sum(
                float(info_h.get("pontos", 0.0)) 
                for qid_h, info_h in all_data[a_str].items() 
                if isinstance(info_h, dict) and not qid_h.startswith("COM_")
            ))
            valores_serie.append(soma_ano)
        else: 
            valores_serie.append(0.0)

    # Configuração do Gráfico ReportLab
    desenho_grafico = Drawing(480, 165)
    bc = VerticalBarChart()
    bc.x = 45; bc.y = 25; bc.height = 110; bc.width = 410
    bc.data = [valores_serie]
    bc.categoryAxis.categoryNames = [str(a) for a in anos_serie]
    bc.categoryAxis.labels.fontSize = 9; bc.categoryAxis.labels.fontName = 'Helvetica-Bold'; bc.categoryAxis.labels.dy = -10
    
    bc.valueAxis.valueMin = 0; bc.valueAxis.valueMax = 1000; bc.valueAxis.valueStep = 200; bc.valueAxis.labels.fontSize = 8
    
    bc.barLabels.nudge = 8
    bc.barLabels.fontSize = 8
    bc.barLabels.fontName = 'Helvetica-Bold'
    bc.barLabelFormat = '%.1f'
    
    bc.bars[0].fillColor = colors.HexColor("#1b4f72")
    bc.bars[0].strokeColor = colors.HexColor("#2c3e50")
    bc.bars[0].strokeWidth = 0.5

    desenho_grafico.add(String(240, 150, "Série Histórica do i-PLAN", textAnchor='middle', fontName='Helvetica-Bold', fontSize=12, fillColor=colors.HexColor("#2c3e50")))
    desenho_grafico.add(bc)
    
    elements.append(desenho_grafico)

    # -------------------------------------------------------------------------
    # COMPILAÇÃO FINAL DO BUFFER DO PDF
    # -------------------------------------------------------------------------
    doc.build(elements)
    buffer.seek(0)
    return buffer
    
# =============================================================================
# 2. INTERFACE E FORMULÁRIO
# =============================================================================

def render_sidebar():
    st.sidebar.title("🛠️ Painel i-PLAN")
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
    
    # =========================================================================
    # CORREÇÃO: Carrega o histórico completo de todos os anos para o PDF
    # =========================================================================
    historico_completo = {}
    for ano_h in anos:
        dados_ano_h = load_respostas(ano_h)
        if dados_ano_h: # Só adiciona se houver respostas salvas para aquele ano
            historico_completo[str(ano_h)] = dados_ano_h
    # =========================================================================

    # Geração Dinâmica do PDF na Sidebar passando o historico_completo
    try:
        pdf_buffer = gerar_relatorio_pdf(res_data, ano_sel, total_pts, faixa, all_data=historico_completo)
        st.sidebar.download_button(
            label="📥Relatório PDF",
            data=pdf_buffer.getvalue(),
            file_name=f"Relatorio_iPLAN_{ano_sel}.pdf",
            mime="application/pdf"
        )
    except Exception as e:
        st.sidebar.error(f"Erro ao gerar PDF para download: {e}")
    
    if st.sidebar.button("🔄 Zerar Questionário"):
        with get_connection() as conn:
            conn.execute("DELETE FROM respostas WHERE ano = ?", (ano_sel,))
            conn.commit()
        
        # Limpa o session_state para desmarcar todos os widgets (radio, checkbox, etc)
        # Filtramos as chaves que terminam com o ano de referência para não afetar configurações globais
        for key in list(st.session_state.keys()):
            if key.endswith(f"_{ano_sel}"):
                del st.session_state[key]
                
        st.rerun()
        
    return total_pts, res_data, ano_sel

def mostrar_formulario_plan():
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

    st.title(f"📊 Auditoria i-Plan - {ano_sel}")
    
    # 1. Criamos as abas normalmente
    aba_quest, aba_graf = st.tabs(["📋 Questionário", "📈 Gráficos"])
    
    # 2. SEPARADOS: Criamos a lógica dos gráficos isolada aqui em cima
    with aba_graf:
        st.subheader("📊 Evolução dos Resultados — Série Histórica")
        st.write("Acompanhe o desempenho da pontuação total acumulada ao longo dos anos:")
        
        # Aqui montamos o gráfico em Plotly para a tela do Streamlit (já que o ReportLab é só pro PDF)
        anos_serie = [2023, 2024, 2025, 2026, 2027, 2028, 2029, 2030]
        valores_serie = []
        
        # Carrega os dados para o gráfico da tela
        for a in anos_serie:
            dados_ano_h = load_respostas(a)
            soma_ano = sum(float(item.get("pontos", 0)) for k, item in dados_ano_h.items() if not k.startswith("COM_"))
            valores_serie.append(soma_ano)
            
        import plotly.express as px
        fig = px.bar(
            x=[str(a) for a in anos_serie], 
            y=valores_serie,
            labels={'x': 'Ano de Referência', 'y': 'Pontuação Total'},
            range_y=[0, 1000]
        )
        fig.update_traces(marker_color='#1b4f72')
        st.plotly_chart(fig, use_container_width=True)
        
    # 3. O SEGREDO: Abrimos a aba de questionário e DEIXAMOS ELA ABERTA. 
    # Todo o resto do seu arquivo gigante que vem abaixo vai cair automaticamente dentro dela!
    with aba_quest:
        # --- SEÇÃO 1: AUDIÊNCIAS PÚBLICAS ---
        st.header("1.0 Audiências Públicas")
        
        # O RESTO DO SEU ARQUIVO SEGUE AQUI PARA BAIXO NORMALMENTE...
        
        # =============================================================================
        # BLOCO DE QUESITOS - 1.0 (I-PLAN)
        # =============================================================================

        # 1.0
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 1.0")
        st.write("**A Prefeitura realizou audiências públicas para elaboração das peças orçamentárias? Obs. Serão consideradas apenas as audiências públicas realizadas durante o processo de planejamento municipal (PPA, LDO e LOA).**")
        
        d10 = res_data.get("1.0", {"valor": None, "pontos": 0.0, "link": ""})
        opc10 = ["Sim", "Não"]
        idx10 = opc10.index(d10["valor"]) if d10["valor"] in opc10 else None

        col1, col2 = st.columns([1, 2])
        with col1:
            r10 = st.radio("Selecione 1.0:", opc10, index=idx10, key=f"q10_{ano_sel}")
        with col2:
            l10 = st.text_area("Link/Evidência (1.0):", value=d10.get("link", ""), key=f"l10_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS inline
            links_10_atuais = re.findall(r'(https?://[^\s]+)', l10)
            if links_10_atuais:
                botoes_10 = " | ".join([f"🔗 [{u}]({u})" for u in links_10_atuais])
                st.markdown(f"**Links Ativos:** {botoes_10}")

        if r10 is not None and (r10 != d10["valor"] or l10 != d10["link"]):
            save_resp("1.0", r10, 0.0, l10)
            
            if links_10_atuais:
                links_10_antigos = re.findall(r'(https?://[^\s]+)', d10["link"])
                if links_10_atuais != links_10_antigos:
                    modal_aviso_link("1.0", links_10_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("1.0", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        if r10 == "Sim":
            # 1.1
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader("QUESITO 1.1")
            st.write("**Assinale para quais peças orçamentárias foram realizadas as audiências públicas: Considerar as audiências públicas da LOA e LDO realizadas no exercício avaliado e o último PPA elaborado**")
            
            d11 = res_data.get("1.1", {"valor": "[]", "pontos": 0.0, "link": ""})
            pecas = {"PPA inicial 2026-2029 – 01": 1.0, "LDO 2026 – 01": 1.0, "LOA 2026 – 01": 1.0}
            
            try:
                lista_salva_11 = ast.literal_eval(d11["valor"])
                if not isinstance(lista_salva_11, list):
                    lista_salva_11 = []
            except Exception:
                lista_salva_11 = []
            
            col1, col2 = st.columns([1, 2])
            with col1:
                sel11 = []
                pts11 = 0.0
                for p, pt in pecas.items():
                    if st.checkbox(p, value=p in lista_salva_11, key=f"q11_{p}_{ano_sel}"):
                        sel11.append(p)
                        pts11 += pt
            with col2:
                l11 = st.text_area("Link/Evidência (1.1):", value=d11.get("link", ""), key=f"l11_{ano_sel}", height=100)
                
                links_11_atuais = re.findall(r'(https?://[^\s]+)', l11)
                if links_11_atuais:
                    botoes_11 = " | ".join([f"🔗 [{u}]({u})" for u in links_11_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_11}")

            if str(sel11) != d11["valor"] or l11 != d11["link"]:
                save_resp("1.1", str(sel11), pts11, l11)
                
                if links_11_atuais:
                    links_11_antigos = re.findall(r'(https?://[^\s]+)', d11["link"])
                    if links_11_atuais != links_11_antigos:
                        modal_aviso_link("1.1", links_11_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()

            bloco_comentarios("1.1", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

            # 1.2
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader("QUESITO 1.2")
            st.write("**Assinale o dia e horário de realização das audiências públicas:**")
            
            d12 = res_data.get("1.2", {"valor": "[]", "pontos": 0.0, "link": ""})
            horarios = {
                "Dia de semana em horário comercial (ex: 8 as 18 horas) – 00": 0.0, 
                "Dia de semana após horário comercial (ex: após às 18 horas) – 02": 2.0, 
                "Aos sábados, domingos e feriados – 02": 2.0
            }
            
            try:
                lista_salva_12 = ast.literal_eval(d12["valor"])
                if not isinstance(lista_salva_12, list):
                    lista_salva_12 = []
            except Exception:
                lista_salva_12 = []
            
            col1, col2 = st.columns([1, 2])
            with col1:
                sel12 = []
                pts12 = 0.0
                for h, pt in horarios.items():
                    if st.checkbox(h, value=h in lista_salva_12, key=f"q12_{h}_{ano_sel}"):
                        sel12.append(h)
                        pts12 = max(pts12, pt)
            with col2:
                l12 = st.text_area("Link/Evidência (1.2):", value=d12.get("link", ""), key=f"l12_{ano_sel}", height=100)
                
                links_12_atuais = re.findall(r'(https?://[^\s]+)', l12)
                if links_12_atuais:
                    botoes_12 = " | ".join([f"🔗 [{u}]({u})" for u in links_12_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_12}")

            if str(sel12) != d12["valor"] or l12 != d12["link"]:
                save_resp("1.2", str(sel12), pts12, l12)
                
                if links_12_atuais:
                    links_12_antigos = re.findall(r'(https?://[^\s]+)', d12["link"])
                    if links_12_atuais != links_12_antigos:
                        modal_aviso_link("1.2", links_12_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()

            bloco_comentarios("1.2", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

            # =============================================================================
            # QUESITO 1.3: AUDIÊNCIAS PÚBLICAS
            # =============================================================================
            with st.container(border=True):  # Substitui a div instável e resolve o 'removeChild'
                st.subheader("QUESITO 1.3")
                st.write("**As audiências públicas são transcritas em atas ou outro documento de registro das demandas/sugestões apresentadas pela participação popular?**")
                
                # Tratamento preventivo de dicionários nulos
                d13 = res_data.get("1.3", {"valor": None, "pontos": 0.0, "link": ""})
                if d13 is None: d13 = {"valor": None, "pontos": 0.0, "link": ""}
                
                idx13 = opc10.index(d13["valor"]) if d13.get("valor") in opc10 else None
                
                col1, col2 = st.columns([1, 2])
                with col1:
                    # Sufixo adicionado à chave para evitar colisão global
                    r13 = st.radio("Selecione 1.3:", opc10, index=idx13, key=f"q13_{ano_sel}_sec13_radio")
                with col2:
                    val_l13 = d13.get("link", "") if d13.get("link") is not None else ""
                    l13 = st.text_area("Link/Evidência (1.3):", value=val_l13, key=f"l13_{ano_sel}_sec13_area", height=100)
                    
                    links_13_atuais = re.findall(r'(https?://[^\s]+)', l13) if l13 else []
                    if links_13_atuais:
                        botoes_13 = " | ".join([f"🔗 [{u}]({u})" for u in links_13_atuais])
                        st.markdown(f"**Links Ativos:** {botoes_13}")

                if r13 is not None and (r13 != d13.get("valor") or l13 != d13.get("link")):
                    save_resp("1.3", r13, 0.0, l13)
                    
                    if links_13_atuais:
                        links_13_antigos = re.findall(r'(https?://[^\s]+)', d13.get("link", "")) if d13.get("link") else []
                        if links_13_atuais != links_13_antigos:
                            modal_aviso_link("1.3", links_13_atuais)
                        else:
                            st.rerun()
                    else:
                        st.rerun()
                    
                # --- BLOCO DEPENDENTE DO QUESITO 1.3 ---
                if r13 == "Sim":
                    st.write("**1.3.1. Página eletrônica (link) do instrumento (XYZ se não disponível):**")
                    
                    d131 = res_data.get("1.3.1", {"valor": "", "pontos": 0.0, "link": ""})
                    if d131 is None: d131 = {"valor": "", "pontos": 0.0, "link": ""}
                    if not isinstance(d131, dict):
                        d131 = {"valor": str(d131), "pontos": 0.0, "link": ""}

                    val_v131_init = d131.get("valor", "") if d131.get("valor") is not None else ""
                    # Sufixo adicionado à chave do input de texto
                    v131 = st.text_input("Link URL:", value=val_v131_init, key=f"q131_{ano_sel}_sec13_input")
                    
                    v131_clean = v131.strip().upper() if v131 else ""
                    if v131_clean == "XYZ" or not v131.strip():
                        st.markdown(f"<span style='color:#dc3545; font-weight:bold;'>Pontuação: 0.0 / 3.0 pts</span> (Link indisponível)", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<span style='color:#28a745; font-weight:bold;'>Pontuação: 3.0 / 3.0 pts</span> (Link válido)", unsafe_allow_html=True)
                    
                    if v131 != d131.get("valor"):
                        nota_calculada = 0.0 if (v131_clean == "XYZ" or not v131.strip()) else 3.0
                        save_resp("1.3.1", v131, nota_calculada, "")
                        st.rerun()
                        
                elif r13 == "Não":
                    d131_check = res_data.get("1.3.1")
                    v131_atual = d131_check.get("valor") if isinstance(d131_check, dict) else d131_check
                    
                    if v131_atual != "XYZ":
                        save_resp("1.3.1", "XYZ", 0.0, "")
                        st.rerun()
                
                bloco_comentarios("1.3", res_data)

            # 1.4
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader("QUESITO 1.4")
            st.write("**Assinale os elements considerados no processo de planejamento e organização das audiências públicas:**")
            
            d14 = res_data.get("1.4", {"valor": "[]", "pontos": 0.0, "link": ""})
            elementos = {
                "Estabelecimento da Pauta – 0,5": 0.5,
                "Disponibilização prévia de material de apoio a respeito dos temas a serem debatidos – 0,5": 0.5,
                "Convocação contendo o dia, horário e o local através dos jornais, das rádios, do Portal da Prefeitura e outras plataformas digitais. Ex.: Instagram, Facebook etc. – 0,5 ": 0.5,
                "Planejamento logístico. Ex.:localização do ambiente, acomodações adequadas aos participantes, regulação e testagem dos equipamentos eletrônicos (som, vídeo e iluminação), verificação dos equipamentos relacionados a transmissão das audiências etc. – 01": 1.0,
                "Indicação de mediador qualificado – 0,5": 0.5,
                "Estabelecimento da abordagem de interação – 0,5": 0.5,
                "Definição de mecanismos de avaliação – 0,5": 0.5,
                "Elaboração e divulgação do Relatório contendo a análise das demandas e sugestões coletadas – 01": 1.0
            }
            
            try:
                lista_salva_14 = ast.literal_eval(d14["valor"])
                if not isinstance(lista_salva_14, list):
                    lista_salva_14 = []
            except Exception:
                lista_salva_14 = []
            
            col1, col2 = st.columns([1, 2])
            with col1:
                sel14 = []
                pts14 = 0.0
                for e, pt in elementos.items():
                    if st.checkbox(e, value=e in lista_salva_14, key=f"q14_{e}_{ano_sel}"):
                        sel14.append(e)
                        pts14 += pt
            with col2:
                l14 = st.text_area("Link/Evidência (1.4):", value=d14.get("link", ""), key=f"l14_{ano_sel}", height=100)
                
                links_14_atuais = re.findall(r'(https?://[^\s]+)', l14)
                if links_14_atuais:
                    botoes_14 = " | ".join([f"🔗 [{u}]({u})" for u in links_14_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_14}")

            if str(sel14) != d14["valor"] or l14 != d14["link"]:
                save_resp("1.4", str(sel14), pts14, l14)
                
                if links_14_atuais:
                    links_14_antigos = re.findall(r'(https?://[^\s]+)', d14["link"])
                    if links_14_atuais != links_14_antigos:
                        modal_aviso_link("1.4", links_14_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
                    
            bloco_comentarios("1.4", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

        # =============================================================================
        # SEÇÃO 2: CONSULTA PÚBLICA
        # =============================================================================
        st.header("2.0 Consulta Pública Online")
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 2.0")
        st.write("**Houve a realização de consulta pública online para coleta de sugestões para a elaboração do PPA 2026-2029?**")
        
        d20 = res_data.get("2.0", {"valor": None, "pontos": 0, "link": ""})
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r20 = st.radio("Selecione 2.0:", ["Sim – 06", "Não – 00"], index=(0 if d20["valor"] and "Sim" in d20["valor"] else (1 if d20["valor"] else None)), key=f"q20_{ano_sel}")
        with col2:
            l20 = st.text_area("Link/Evidência (2.0):", value=d20.get("link", ""), key=f"l20_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS inline
            links_20_atuais = re.findall(r'(https?://[^\s]+)', l20)
            if links_20_atuais:
                botoes_20 = " | ".join([f"🔗 [{u}]({u})" for u in links_20_atuais])
                st.markdown(f"**Links Ativos:** {botoes_20}")

        if r20 and (r20 != d20["valor"] or l20 != d20["link"]):
            save_resp("2.0", r20, 6 if "Sim" in r20 else 0, l20)
            
            if links_20_atuais:
                links_20_antigos = re.findall(r'(https?://[^\s]+)', d20["link"])
                if links_20_atuais != links_20_antigos:
                    modal_aviso_link("2.0", links_20_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
        
        if r20 and "Sim" in r20:
            st.write("**2.1 Na consulta pública online de elaboração do Plano Plurianual (PPA) foi disponibilizado glossário explicando os objetivos, como contribuir, in linguagem clara e simples?**")
            d21 = res_data.get("2.1", {"valor": None, "pontos": 0, "link": ""})
            r21 = st.radio("Selecione 2.1:", ["Sim – 02", "Não – 00"], index=(0 if d21["valor"] and "Sim" in d21["valor"] else (1 if d21["valor"] else None)), key=f"q21_{ano_sel}")
            if r21 and r21 != d21["valor"]:
                save_resp("2.1", r21, 2 if "Sim" in r21 else 0, "")
                st.rerun()
        bloco_comentarios("2.0", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # =============================================================================
        # --- SEÇÃO 3: DIAGNÓSTICO ----------------------------------------------------
        # =============================================================================
        st.header("3.0 Diagnóstico Prévio")
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 3.0")
        st.write("**Além das audiências públicas, a Prefeitura realizou diagnóstico anteriormente ao planejamento, através do levantamento formal de seus problemas, necessidades e deficiências?**")
        st.caption("Obs: Os Planos Municipais Setoriais (Educação, Saúde, Saneamento Básico etc.) somente podem ser considerados se neles houver evidências do levantamento formal dos problemas. Planejamento do PPA inicial 2026-2029.")

        d30 = res_data.get("3.0", {"valor": None, "pontos": 0.0, "link": ""})
        
        col1, col2 = st.columns([1, 2])
        with col1:
            opcoes_30 = ["Sim", "Não"]
            idx30 = opcoes_30.index(d30["valor"]) if d30["valor"] in opcoes_30 else None
            r30 = st.radio("Selecione 3.0:", opcoes_30, index=idx30, key=f"q30_{ano_sel}")
            
        with col2:
            l30 = st.text_area("Link/Evidência (3.0):", value=d30.get("link", ""), key=f"l30_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS INLINE VIA REGEX
            links_30_atuais = re.findall(r'(https?://[^\s]+)', l30)
            if links_30_atuais:
                botoes_30 = " | ".join([f"🔗 [{u}]({u})" for u in links_30_atuais])
                st.markdown(f"**Links Ativos:** {botoes_30}")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 3.0
        if r30 is not None and (r30 != d30["valor"] or l30 != d30["link"]):
            save_resp("3.0", r30, 0.0, l30)
            
            if links_30_atuais:
                links_30_antigos = re.findall(r'(https?://[^\s]+)', d30.get("link", ""))
                if links_30_atuais != links_30_antigos:
                    modal_aviso_link("3.0", links_30_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
        
        # --- BLOCO CONDICIONAL FILHO DO DIAGNÓSTICO PRÉVIO -------------------
        if r30 == "Sim":
            st.markdown('<div style="margin-left: 20px; border-left: 2px solid #eee; padding-left: 20px; margin-top: 15px;">', unsafe_allow_html=True)
            
            # --- QUESITO 3.1 -------------------------------------------------
            st.write("**3.1 A abordagem do diagnóstico levou em conta algum plano do governo federal e/ou estadual?**")
            d31 = res_data.get("3.1", {"valor": None, "pontos": 0.0, "link": ""})
            opcoes_31 = ["Sim – 14", "Não – 00"]
            
            idx31 = None
            if d31["valor"] and "Sim" in d31["valor"]:
                idx31 = 0
            elif d31["valor"] and "Não" in d31["valor"]:
                idx31 = 1
                
            r31 = st.radio("Selecione 3.1:", opcoes_31, index=idx31, key=f"q31_{ano_sel}")
            
            if r31 is not None and r31 != d31["valor"]:
                pts31 = 14.0 if "Sim" in r31 else 0.0
                save_resp("3.1", r31, pts31, "")
                st.rerun()
            
            # --- QUESITO 3.1.1 -----------------------------------------------
            if r31 and "Sim" in r31:
                st.write("**3.1.1 Descreva os programas utilizados:**")
                d311 = res_data.get("3.1.1", {"valor": "", "pontos": 0.0, "link": ""})
                v311 = st.text_area("Descrição dos programas:", value=d311.get("valor", ""), key=f"q311_{ano_sel}", height=80)
                
                if v311 != d311["valor"]:
                    save_resp("3.1.1", v311, 0.0, "")
                    st.rerun()

            st.divider()

            # --- QUESITO 3.2 -------------------------------------------------
            st.write("**3.2 Os programas do PPA 2026-2029 tiveram diagnóstico prévio?**")
            st.caption("Obs: Os Planos Municipais Setoriais (Educação, Saúde, Saneamento Básico etc.) somente podem ser considerados se neles houver evidências do levantamento formal dos problemas.")
            
            d32 = res_data.get("3.2", {"valor": None, "pontos": 0.0, "link": ""})
            opc32 = {
                "Sim, para todos os programas PPA – 10": 10.0, 
                "Sim, para a maior parte dos programas do PPA – 05": 5.0, 
                "Sim, para a menor parte dos programas do PPA  – 03": 3.0, 
                "Não – 00": 0.0
            }
            lista_opcoes_32 = list(opc32.keys())
            idx32 = lista_opcoes_32.index(d32["valor"]) if d32["valor"] in opc32 else None
            
            r32 = st.radio("Selecione 3.2:", lista_opcoes_32, index=idx32, key=f"q32_{ano_sel}")
            
            if r32 is not None and r32 != d32["valor"]:
                save_resp("3.2", r32, float(opc32[r32]), "")
                st.rerun()
                
            st.markdown('</div>', unsafe_allow_html=True) # Fecha o bloco de recuo do 3.1/3.2

        bloco_comentarios("3.0", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # =============================================================================
        # SEÇÃO 4: METAS E INDICADORES
        # =============================================================================
        st.header("4.0 Metas e Indicadores")

        # --- QUESITO 4.0 ---
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 4.0")
        st.write("**Há o estabelecimento de metas físicas e financeiras de forma anual nas ações previstas no PPA?**")

        d40 = res_data.get("4.0", {"valor": None, "pontos": 0, "link": ""})
        opc40 = {
            "Sim, com metas físicas e financeiras – 10": 10, 
            "Sim, apenas financeiras – 05": 5, 
            "Sim, apenas físicas – 05": 5, 
            "Não houve o estabelecimento de metas anuais – 00": 0
        }

        col1, col2 = st.columns([1, 2])
        with col1:
            r40 = st.radio(
                "Selecione 4.0:", 
                list(opc40.keys()), 
                index=(list(opc40.keys()).index(d40["valor"]) if d40["valor"] in opc40 else None), 
                key=f"q40_{ano_sel}"
            )
        with col2:
            l40 = st.text_area("Link/Evidência (4.0):", value=d40.get("link", ""), key=f"l40_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS inline
            links_40_atuais = re.findall(r'(https?://[^\s]+)', l40)
            if links_40_atuais:
                botoes_40 = " | ".join([f"🔗 [{u}]({u})" for u in links_40_atuais])
                st.markdown(f"**Links Ativos:** {botoes_40}")

        if r40 and (r40 != d40["valor"] or l40 != d40["link"]):
            save_resp("4.0", r40, opc40[r40], l40)
            
            if links_40_atuais:
                links_40_antigos = re.findall(r'(https?://[^\s]+)', d40["link"])
                if links_40_atuais != links_40_antigos:
                    modal_aviso_link("4.0", links_40_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        # --- QUESITO 4.1 ---
        st.write("**4.1 Os programas finalísticos articulam um conjunto de ações que concorrem para um objective comum preestabelecido, visando à solução de um problema ou necessidade da sociedade?**")
        d41 = res_data.get("4.1", {"valor": None, "pontos": 0, "link": ""})
        opc41 = {
            "Todos os programas finalísticos – 15": 15, 
            "A maior parte dos programas finalísticos – 10": 10, 
            "A menor parte dos programas finalísticos – 05": 5, 
            "Nenhum programa finalístico – 00": 0
        }
        r41 = st.radio("Selecione 4.1:", list(opc41.keys()), index=(list(opc41.keys()).index(d41["valor"]) if d41["valor"] in opc41 else None), key=f"q41_{ano_sel}")
        if r41 and r41 != d41["valor"]:
            save_resp("4.1", r41, opc41[r41], "")
            st.rerun()

        # --- QUESITO 4.1.1 ---
        st.write("**4.1.1 Houve avaliação da implementação dos programas finalísticos em relação a seus indicadores, objetivos e metas?**")
        d411 = res_data.get("4.1.1", {"valor": None, "pontos": 0, "link": ""})
        opc411 = {
            "Sim, para todos os programas finalísticos monitorados – 10": 10, 
            "Sim, para a maior parte dos programas finalísticos monitorados – 07": 7, 
            "Sim, para a menor parte dos programas finalísticos monitorados – 03": 3, 
            "Não houve avaliação – 00": 0
        }
        r411 = st.radio("Selecione 4.1.1:", list(opc411.keys()), index=(list(opc411.keys()).index(d411["valor"]) if d411["valor"] in opc411 else None), key=f"q411_{ano_sel}")
        if r411 and r411 != d411["valor"]:
            save_resp("4.1.1", r411, opc411[r411], "")
            st.rerun()

        # --- QUESITO 4.1.1.1 ---
        st.write("**4.1.1.1 Houve a elaboração de Relatório Anual de Avaliação dos programas finalísticos do PPA?**")
        d4111 = res_data.get("4.1.1.1", {"valor": None, "pontos": 0, "link": ""})
        opc4111 = {
            "Sim, para todos os programas finalísticos do PPA – 07": 7, 
            "Sim, para a maior parte dos programas finalísticos do PPA – 04": 4, 
            "Sim, para a menor parte dos programas finalísticos do PPA – 01": 1, 
            "Não houve execução do Relatório Anual de Avaliação do PPA – 00": 0
        }
        r4111 = st.radio("Selecione 4.1.1.1:", list(opc4111.keys()), index=(list(opc4111.keys()).index(d4111["valor"]) if d4111["valor"] in opc4111 else None), key=f"q4111_{ano_sel}")
        if r4111 and r4111 != d4111["valor"]:
            save_resp("4.1.1.1", r4111, opc4111[r4111], "")
            st.rerun()

        # --- QUESITO 4.1.1.1.1 ---
        st.write("**4.1.1.1.1 Assinale os aspectos analisados no processo de acompanhamento e avaliação do PPA:**")
        d41111 = res_data.get("4.1.1.1.1", {"valor": "[]", "pontos": 0, "link": ""})
        aspectos = {
            "Percepção de coerência, em todos os programas, do necessário encadeamento lógicocausal entre os insumos que mobiliza, os produtos/ações que gera, os resultados que provoca e os impactos esperados pela sociedade – 20": 20, 
            "Análise quanto a se Programas, Metas e Ações são mensurados por um ou mais indicadores próprios e adequados, e que permitam aferir a situação atual (aquela que se pretende modificar) e os avanços obtidos ao longo da execução do programa (em direção àquela mudança pretendida) – 20": 20, 
            "Avaliação entre os produtos ofertados à população e as reais demandas da sociedade, coletadas, principalmente, nas audiências públicas realizadas e nos demais instrumentos de diagnóstico dos problemas, necessidades e deficiências do município– 20": 20, 
            "Outros – 00": 0
        }

        try:
            lista_salva_41111 = ast.literal_eval(d41111["valor"])
            if not isinstance(lista_salva_41111, list):
                lista_salva_41111 = []
        except Exception:
            lista_salva_41111 = []

        sel41111 = []
        pts41111 = 0
        for i, (asp, pt) in enumerate(aspectos.items()):
            if st.checkbox(asp, value=asp in lista_salva_41111, key=f"q41111_opt_{i}_{ano_sel}"):
                sel41111.append(asp)
                pts41111 += pt

        if str(sel41111) != d41111["valor"]:
            save_resp("4.1.1.1.1", str(sel41111), pts41111, "")
            st.rerun()

        # --- QUESITO 4.1.1.2 ---
        st.write("**4.1.1.2 Houve publicação dos resultados da avaliação dos programas finalísticos do PPA?**")
        d4112 = res_data.get("4.1.1.2", {"valor": None, "pontos": 0, "link": ""})
        opc4112 = {
            "Sim, para todos os programas finalísticos avaliados do PPA – 04": 4, 
            "Sim, para a maior parte dos programas finalísticos avaliados – 03": 3, 
            "Sim, para a menor parte dos programas finalísticos avaliados – 01": 1, 
            "Não – 00": 0
        }

        r4112 = st.radio(
            "Selecione 4.1.1.2:", 
            list(opc4112.keys()), 
            index=(list(opc4112.keys()).index(d4112["valor"]) if d4112["valor"] in opc4112 else None), 
            key=f"q4112_{ano_sel}"
        )

        if r4112 and r4112 != d4112["valor"]:
            save_resp("4.1.1.2", r4112, opc4112[r4112], "")
            st.rerun()

        if r4112 and "Sim" in r4112:
            st.write("**4.1.1.2.1 Página eletrônica (link) de divulgação dos resultados (XYZ se não disponível):**")
            d41121 = res_data.get("4.1.1.2.1", {"valor": "", "pontos": 0, "link": ""})
            if not isinstance(d41121, dict):
                d41121 = {"valor": str(d41121)}

            v41121 = st.text_input("Link URL (PPA):", value=d41121.get("valor", ""), key=f"q41121_{ano_sel}")
            if v41121 != d41121.get("valor", ""):
                save_resp("4.1.1.2.1", v41121, 0, "")
                st.rerun()
                
        elif r4112 and "Não" in r4112:
            d41121 = res_data.get("4.1.1.2.1", {"valor": "XYZ"})
            if isinstance(d41121, dict) and d41121.get("valor") != "XYZ":
                save_resp("4.1.1.2.1", "XYZ", 0, "")
                st.rerun()

        bloco_comentarios("4.0", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # --- QUESITO 4.2 ---
        st.write("**4.2 Os indicadores são mensuráveis e estão coerentes com as metas físico-financeiras estabelecidas?**")
        d42 = res_data.get("4.2", {"valor": None, "pontos": 0, "link": ""})
        opc42 = {
            "Todos os indicadores do PPA - 25": 25, 
            "A maior parte dos indicadores – 17": 17, 
            "A menor parte dos indicadores – 08": 8, 
            "Nenhum indicador – 00": 0
        }
        r42 = st.radio(
            "Selecione 4.2:", 
            list(opc42.keys()), 
            index=(list(opc42.keys()).index(d42["valor"]) if d42["valor"] in opc42 else None), 
            key=f"q42_{ano_sel}"
        )
        if r42 and r42 != d42["valor"]:
            save_resp("4.2", r42, opc42[r42], "")
            st.rerun()

        # --- QUESITO 4.3 ---
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 4.3")
        st.write("**Assinale os Planos Setoriais que foram incorporados no Plano Plurianual (PPA):**")
        d43 = res_data.get("4.3", {"valor": "[]", "pontos": 0, "link": ""})
            
        planos_pesos = {
            "Plano Diretor – 00": 0.0,
            "Plano Municipal da Educação – 2,5": 2.5,
            "Plano Municipal pela Primeira Infância – 00": 0.0,
            "Plano Municipal da Saúde – 2,5": 2.5,
            "Plano de Mobilidade Urbana – 00": 0.0,
            "Plano de Saneamento Básico – 2,5": 2.5,
            "Plano de Resíduos Sólidos – 2,5": 2.5,
            "Plano de Contingência Municipal – PLANCON de Defesa Civil – 2,5": 2.5,
            "Plano Diretor de Tecnologia da Informação – 2,5": 2.5,
            "Não incorporou nenhum dos planos acima – -10 (perde 10 pontos)": -10.0
        }
            
        col1, col2 = st.columns([1, 2])
        with col1:
            try:
                lista_salva_43 = ast.literal_eval(d43["valor"])
                if not isinstance(lista_salva_43, list):
                    lista_salva_43 = []
            except Exception:
                lista_salva_43 = []

            sel43 = []
            for idx, (plano, pt) in enumerate(planos_pesos.items()):
                if st.checkbox(plano, value=plano in lista_salva_43, key=f"q43_opt_{idx}_{ano_sel}"):
                    sel43.append(plano)
                
            if any("Não incorporou" in p for p in sel43):
                pts43 = -10.0
            else:
                pts43 = sum(planos_pesos[p] for p in sel43)
                    
            if pts43 < 0:
                st.markdown(f"<span style='color:#dc3545; font-weight:bold;'>Pontuação Total: {pts43} pts</span> (Penalidade aplicada)", unsafe_allow_html=True)
            else:
                st.markdown(f"<span style='color:#28a745; font-weight:bold;'>Pontuação Total: {pts43} pts</span>", unsafe_allow_html=True)

        with col2:
            l43 = st.text_area("Link/Evidência (4.3):", value=d43.get("link", ""), key=f"l43_{ano_sel}", height=100)
            
            # Suporte a múltiplos links ativos na interface igual ao Quesito 4.0
            links_43_atuais = re.findall(r'(https?://[^\s]+)', l43)
            if links_43_atuais:
                botoes_43 = " | ".join([f"🔗 [{u}]({u})" for u in links_43_atuais])
                st.markdown(f"**Links Ativos:** {botoes_43}")

        if str(sel43) != d43["valor"] or l43 != d43["link"]:
            save_resp("4.3", str(sel43), pts43, l43)
            
            if links_43_atuais:
                links_43_antigos = re.findall(r'(https?://[^\s]+)', d43.get("link", ""))
                if links_43_atuais != links_43_antigos:
                    modal_aviso_link("4.3", links_43_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
                
        bloco_comentarios("4.3", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # =============================================================================
        # SEÇÃO 5: RECEITA
        # =============================================================================
        st.header("5.0 Previsão de Receitas")
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 5.0")
        st.write("**É realizado estudo/análise para previsão de receitas, no mínimo, anualmente? Aplicação de índice inflacionário ao valor arrecadado do exercício anterior NÃO é estudo/análise de previsão de receita**")
        d50 = res_data.get("5.0", {"valor": None, "pontos": 0, "link": ""})
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r50 = st.radio("Selecione 5.0:", ["Sim – 06", "Não – 00"], index=(0 if d50["valor"] and "Sim" in d50["valor"] else (1 if d50["valor"] else None)), key=f"q50_{ano_sel}")
        with col2:
            l50 = st.text_area("Link/Evidência (5.0):", value=d50.get("link", ""), key=f"l50_{ano_sel}", height=100)
            
            # Suporte multi-links ativos inline
            links_50_atuais = re.findall(r'(https?://[^\s]+)', l50)
            if links_50_atuais:
                botoes_50 = " | ".join([f"🔗 [{u}]({u})" for u in links_50_atuais])
                st.markdown(f"**Links Ativos:** {botoes_50}")

        if r50 and (r50 != d50["valor"] or l50 != d50["link"]):
            save_resp("5.0", r50, 6 if "Sim" in r50 else 0, l50)
            
            if links_50_atuais:
                links_50_antigos = re.findall(r'(https?://[^\s]+)', d50.get("link", ""))
                if links_50_atuais != links_50_antigos:
                    modal_aviso_link("5.0", links_50_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
        
        if r50 and "Sim" in r50:
            st.write("**5.1 Assinale os tipos de tributos e repasses/transferências avaliados na análise e estudo da previsão da receita:**")
            d51 = res_data.get("5.1", {"valor": "[]", "pontos": 0, "link": ""})
            tribs = {
                "Imposto sobre a Propriedade Predial e Territorial Urbano (IPTU) – 0,5": 0.5, 
                "Imposto sobre a Transmissão de Bens Imóveis (ITBI) – 0,5": 0.5, 
                "Imposto Sobre Serviços de Qualquer Natureza (ISSQN) – 0,5": 0.5, 
                "Taxas – 0,25": 0.25, 
                "Contribuições – 0,25": 0.25, 
                "Transferências Obrigatórias Recebidas da União. Ex.: FPM, CIDE, ITR, Royalties e FUNDEB. – 01": 1.0, 
                "Transferências Obrigatórias Recebidas do Estado. Ex.: ICMS, IPVA. – 01": 1.0, 
                "Outros - 0,0": 0.0
            }
            
            try:
                lista_salva_51 = ast.literal_eval(d51["valor"])
                if not isinstance(lista_salva_51, list):
                    lista_salva_51 = []
            except Exception:
                lista_salva_51 = []

            sel51 = []
            pts51 = 0.0
            for idx, (t, pt) in enumerate(tribs.items()):
                if st.checkbox(t, value=t in lista_salva_51, key=f"q51_opt_{idx}_{ano_sel}"):
                    sel51.append(t)
                    pts51 += pt
            if str(sel51) != d51["valor"]:
                save_resp("5.1", str(sel51), pts51, "")
                st.rerun()

            st.write("**5.1.1 A estimativa de transferências obrigatórias leva em consideração o cálculo de previsão de repasse do ICMS realizado periodicamente pela Fazenda Pública Estadual?**")
            d511 = res_data.get("5.1.1", {"valor": None, "pontos": 0, "link": ""})
            opc511 = {
                "Sim, com reestimativa da receita prevista na LOA no decorrer da execução orçamentária-financeira – 02": 2, 
                "Sim, somente para elaborar a LOA – 01": 1, 
                "Não – 00": 0
            }
            r511 = st.radio("Selecione 5.1.1:", list(opc511.keys()), index=(list(opc511.keys()).index(d511["valor"]) if d511["valor"] in opc511 else None), key=f"q511_{ano_sel}")
            if r511 and r511 != d511["valor"]:
                save_resp("5.1.1", r511, opc511[r511], "")
                st.rerun()

        st.write("**5.2 A metodologia utilizada para projeção da receita varia de acordo com a espécie da receita orçamentária projetada?**")
        d52 = res_data.get("5.2", {"valor": None, "pontos": 0, "link": ""})
        r52 = st.radio("Selecione 5.2:", ["Sim – 06", "Não – 00"], index=(0 if d52["valor"] and "Sim" in d52["valor"] else (1 if d52["valor"] else None)), key=f"q52_{ano_sel}")
        if r52 and r52 != d52["valor"]:
            save_resp("5.2", r52, 6 if "Sim" in r52 else 0, "")
            st.rerun()
            
        bloco_comentarios("5.0", res_data)
        st.markdown('</div>', unsafe_allow_html=True)


        # =============================================================================
        # SEÇÃO 6, 7, 8, 9: LDO E RISCOS
        # =============================================================================
        st.header("6.0 a 9.0 LDO e Riscos Fiscais")
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 6.0")
        st.write("**Assinale os itens que a LDO dispõe:**")
        d60 = res_data.get("6.0", {"valor": "[]", "pontos": 0, "link": ""})
        
        itens_ldo = {
            "Custos estimados, indicators e metas físicas que se correlacionam com as ações do governo municipal – 0,5": 0.5, 
            "Critérios para limitação desempenho e movimentação financeira; ressalvados os pagamentos do serviço da dívida, os relativos à inovação e ao desenvolvimento científico e tecnológico custeadas por fundo criado para tal finalidade. – 0,5": 0.5, 
            "Critérios para repasses a entidades do terceiro setor – 00": 0.0, 
            "Critérios para ajuda financeira a entidades da Administração indireta – 00": 0.0, 
            "Critérios para o Poder Executivo estabelecer a programação financeira mensal para todo o Município, nele incluído a Câmara – 01": 1.0, 
            "Percentual da Receita Corrente Líquida que será retido, na peça orçamentária, enquanto Reserva de Contingência, destinada a passivos contingentes e outros riscos fiscais – 01": 1.0, 
            "Critérios para contratação de horas extras quando o Poder superar o limite prudencial para pessoal: Executivo, 51,30% da RCL; Legislativo, 5,7% da RCL – 0,5": 0.5, 
            "Determinação do índice de preços para atualização monetária do principal da Dívida Mobiliária Refinanciada – 00": 0.0, 
            "Autorização para o Município auxiliar o custeio de despesas próprias do Estado e da União – 00": 0.0, 
            "Requisitos para início de novos projetos, após o adequado atendimento/manutenção dos que estão em andamento – 0,5": 0.5,
            "Dispor sobre pagamento de servidor ou empregado público com recursos vinculados à parceria firmada com o terceiro setor – 00": 0.0
        }
        
        col1, col2 = st.columns([1, 2])
        with col1:
            try:
                lista_salva_60 = ast.literal_eval(d60["valor"])
                if not isinstance(lista_salva_60, list):
                    lista_salva_60 = []
            except Exception:
                lista_salva_60 = []

            sel60 = []
            pts60 = 0.0
            for idx, (item_texto, pt) in enumerate(itens_ldo.items()):
                if st.checkbox(item_texto, value=item_texto in lista_salva_60, key=f"q60_opt_{idx}_{ano_sel}"):
                    sel60.append(item_texto)
                    pts60 += pt
            
            st.markdown(f"<span style='color:#28a745; font-weight:bold;'>Pontuação Total: {pts60} pts</span>", unsafe_allow_html=True)

        with col2:
            l60 = st.text_area("Link/Evidência (6.0):", value=d60.get("link", ""), key=f"l60_{ano_sel}", height=100)
            
            # Suporte multi-links ativos inline
            links_60_atuais = re.findall(r'(https?://[^\s]+)', l60)
            if links_60_atuais:
                botoes_60 = " | ".join([f"🔗 [{u}]({u})" for u in links_60_atuais])
                st.markdown(f"**Links Ativos:** {botoes_60}")

        if str(sel60) != d60["valor"] or l60 != d60["link"]:
            save_resp("6.0", str(sel60), pts60, l60)
            
            if links_60_atuais:
                links_60_antigos = re.findall(r'(https?://[^\s]+)', d60.get("link", ""))
                if links_60_atuais != links_60_antigos:
                    modal_aviso_link("6.0", links_60_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
            
        bloco_comentarios("6.0", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 7.0")
        st.write("**Houve alteração orçamentária decorrente de remanejamento, transposição ou transferência de uma categoria de programação para outra ou de um órgão para outro por decreto?**")
        d70 = res_data.get("7.0", {"valor": None, "pontos": 0, "link": ""})
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r70 = st.radio("Selecione 7.0:", ["Sim", "Não"], index=(0 if d70["valor"] == "Sim" else (1 if d70["valor"] == "Não" else None)), key=f"q70_{ano_sel}")
        with col2:
            l70 = st.text_area("Link/Evidência (7.0):", value=d70.get("link", ""), key=f"l70_{ano_sel}", height=100)
            
            # Suporte multi-links ativos inline
            links_70_atuais = re.findall(r'(https?://[^\s]+)', l70)
            if links_70_atuais:
                botoes_70 = " | ".join([f"🔗 [{u}]({u})" for u in links_70_atuais])
                st.markdown(f"**Links Ativos:** {botoes_70}")

        if r70 and (r70 != d70["valor"] or l70 != d70["link"]):
            save_resp("7.0", r70, 0, l70)
            
            if links_70_atuais:
                links_70_antigos = re.findall(r'(https?://[^\s]+)', d70.get("link", ""))
                if links_70_atuais != links_70_antigos:
                    modal_aviso_link("7.0", links_70_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
        
        if r70 == "Sim":
            st.write("**7.1 Assinale a classificação funcional da despesa, objeto de alterações orçamentárias decorrentes de remanejamento, transposição e transferências realizadas por decreto:**")
            d71 = res_data.get("7.1", {"valor": "[]", "pontos": 0, "link": ""})
            funcs_alt = [
                "10 - Saúde – -05 (perde 05 pontos)", 
                "12 - Educação – -05 (perde 05 pontos)", 
                "17 - Saneamento – -05 (perde 05 pontos)", 
                "19 - Ciência e Tecnologia – 00", 
                "26 - Transporte – -05 (perde 05 pontos)", 
                "Outras – -05 (perde 05 pontos)"
            ]
            
            try:
                lista_salva_71 = ast.literal_eval(d71["valor"])
                if not isinstance(lista_salva_71, list):
                    lista_salva_71 = []
            except Exception:
                lista_salva_71 = []

            sel71 = []
            pts71 = 0
            for idx, f in enumerate(funcs_alt):
                if st.checkbox(f, value=f in lista_salva_71, key=f"q71_opt_{idx}_{ano_sel}"):
                    sel71.append(f)
                    if "perde 05 pontos" in f:
                        pts71 -= 5
            
            if str(sel71) != d71["valor"]:
                save_resp("7.1", str(sel71), pts71, "")
                st.rerun()
                
        bloco_comentarios("7.0", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # =============================================================================
        # SEÇÃO 8: ANEXO DE METAS FISCAIS (LDO)
        # =============================================================================
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 8.0")
        st.write("**O Anexo de Metas Fiscais integra a Lei de Diretrizes Orçamentárias (LDO), nos termos exigidos pela Lei de Responsabilidade Fiscal? Obs. Estabelecidas metas anuais, em valores correntes e constantes, relativas a receitas, despesas, resultados nominal e primário e montante da dívida pública, para o exercício a que se referirem e para os dois seguintes. Caso não esteja disponível na internet, recomendamos anexar o Anexo de Metas Fiscais (MDF), conforme Instrução de Preenchimento (IP) no Sistema de Questionários.**")
        d80 = res_data.get("8.0", {"valor": None, "pontos": 0, "link": ""})
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r80 = st.radio("Selecione 8.0:", ["Sim", "Não"], index=(0 if d80["valor"] == "Sim" else (1 if d80["valor"] == "Não" else None)), key=f"q80_{ano_sel}")
        with col2:
            l80 = st.text_area("Link/Evidência (8.0):", value=d80.get("link", ""), key=f"l80_{ano_sel}", height=100)
            
            # Verificação de múltiplos links ativos
            links_80_atuais = re.findall(r'(https?://[^\s]+)', l80)
            if links_80_atuais:
                botoes_80 = " | ".join([f"🔗 [{u}]({u})" for u in links_80_atuais])
                st.markdown(f"**Links Ativos:** {botoes_80}")

        if r80 and (r80 != d80["valor"] or l80 != d80["link"]):
            save_resp("8.0", r80, 0, l80)
            
            # Se mudou para Não, limpa os quesitos dependentes para evitar lixo no banco
            if r80 == "Não":
                save_resp("8.1", "", 0.0, "")
                save_resp("8.2", "[]", 0.0, "")
            
            if links_80_atuais:
                links_80_antigos = re.findall(r'(https?://[^\s]+)', d80.get("link", ""))
                if links_80_atuais != links_80_antigos:
                    modal_aviso_link("8.0", links_80_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
            
        bloco_comentarios("8.0", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # --- BLOCO DEPENDENTE (SÓ ABRE SE 8.0 FOR SIM) ---
        if r80 == "Sim":
            # --- QUESITO 8.1 ---
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader("QUESITO 8.1")
            st.write("**Informe a página eletrônica (link na internet) de divulgação do Anexo de Metas Fiscais (XYZ se não disponível):**")
            d81 = res_data.get("8.1", {"valor": "", "pontos": 0.0, "link": ""})
            if not isinstance(d81, dict):
                d81 = {"valor": str(d81), "pontos": 0.0, "link": ""}

            col1, col2 = st.columns([1, 2])
            with col1:
                v81 = st.text_input("Página eletrônica (link):", value=d81["valor"], key=f"q81_{ano_sel}")
                
                # --- CÁLCULO E EXIBIÇÃO DA PONTUAÇÃO ---
                if v81.strip().upper() == "XYZ":
                    pts81 = -10.0
                    st.markdown(f"<span style='color:#dc3545; font-weight:bold;'>Pontuação: {pts81} pts</span> (Penalidade aplicada)", unsafe_allow_html=True)
                elif not v81.strip():
                    pts81 = 0.0
                    st.markdown(f"<span style='color:#6c757d; font-weight:bold;'>Pontuação: {pts81} pts</span> (Aguardando preenchimento)", unsafe_allow_html=True)
                else:
                    pts81 = 0.0
                    st.markdown(f"<span style='color:#28a745; font-weight:bold;'>Pontuação: {pts81} pts</span> (Link válido)", unsafe_allow_html=True)

            with col2:
                l81 = st.text_area("Link/Evidência (8.1):", value=d81.get("link", ""), key=f"l81_{ano_sel}", height=100)
                
                # Verificação de múltiplos links ativos para o campo de evidência do 8.1
                links_81_atuais = re.findall(r'(https?://[^\s]+)', l81)
                if links_81_atuais:
                    botoes_81 = " | ".join([f"🔗 [{u}]({u})" for u in links_81_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_81}")

            if v81 != d81["valor"] or l81 != d81["link"]:
                save_resp("8.1", v81, pts81, l81)
                
                if links_81_atuais:
                    links_81_antigos = re.findall(r'(https?://[^\s]+)', d81.get("link", ""))
                    if links_81_atuais != links_81_antigos:
                        modal_aviso_link("8.1", links_81_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
                
            bloco_comentarios("8.1", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

            # --- QUESITO 8.2 ---
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader("QUESITO 8.2")
            st.write("**Assinale os demonstrativos contidos no Anexo de Metas Fiscais:**")
            d82 = res_data.get("8.2", {"valor": "[]", "pontos": 0.0, "link": ""})
            
            demonstrativos = {
                "Metas Anuais – 0,7": 0.7,
                "Avaliação do Cumprimento das Metas Fiscais do Exercício Anterior – 0,7": 0.7,
                "Metas Fiscais Atuais Comparadas com as Metas Fiscais Fixadas nos três exercícios anteriores – 0,7": 0.7,
                "Evolução do Patrimônio Líquido – 0,7": 0.7,
                "Origem e Aplicação dos Recursos Obtidos com a Alienação de Ativos – 00": 0.0,
                "Avaliação da Situação Financeira e Atuarial do RPPS – 00": 0.0,
                "Estimativa e Compensação da Renúncia de Receita – 00": 0.0,
                "Margem de Expansão das Despesas Obrigatórias de Caráter Continuado – 1,2": 1.2,
                "Outros – 00": 0.0
            }
            
            col1, col2 = st.columns([1, 2])
            with col1:
                # Desserialização segura de strings convertidas para listas
                try:
                    lista_salva_82 = ast.literal_eval(d82["valor"])
                    if not isinstance(lista_salva_82, list):
                        lista_salva_82 = []
                except Exception:
                    lista_salva_82 = []

                sel82 = []
                pts82 = 0.0
                
                # Substituição do hash() por indexação enumerada estável
                for idx, (item, pt) in enumerate(demonstrativos.items()):
                    if st.checkbox(item, value=item in lista_salva_82, key=f"q82_opt_{idx}_{ano_sel}"):
                        sel82.append(item)
                        pts82 += pt
                
                st.markdown(f"<span style='color:#28a745; font-weight:bold;'>Pontuação Total: {pts82:.1f} pts</span>", unsafe_allow_html=True)

            with col2:
                l82 = st.text_area("Link/Evidência (8.2):", value=d82.get("link", ""), key=f"l82_{ano_sel}", height=100)
                
                # Verificação de múltiplos links ativos para o campo de evidência do 8.2
                links_82_atuais = re.findall(r'(https?://[^\s]+)', l82)
                if links_82_atuais:
                    botoes_82 = " | ".join([f"🔗 [{u}]({u})" for u in links_82_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_82}")

            if str(sel82) != d82["valor"] or l82 != d82["link"]:
                save_resp("8.2", str(sel82), pts82, l82)
                
                if links_82_atuais:
                    links_82_antigos = re.findall(r'(https?://[^\s]+)', d82.get("link", ""))
                    if links_82_atuais != links_82_antigos:
                        modal_aviso_link("8.2", links_82_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
                
            bloco_comentarios("8.2", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

        # =============================================================================
        # SEÇÃO 9: ANEXO DE RISCOS FISCAIS (LDO)
        # =============================================================================
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 9.0")
        st.write("**O Anexo de Riscos Fiscais integra a Lei de Diretrizes Orçamentárias (LDO), nos termos exigidos pela Lei de Responsabilidade Fiscal? Obs. Avalia os passivos contingentes e outros riscos capazes de afetar as contas públicas, informando as providências a serem tomadas, caso se concretizem. Caso não esteja disponível na internet, recomendamos anexar o Anexo de Metas Fiscais (MDF), conforme Instrução de Preenchimento (IP) no Sistema de Questionários.**")
        d90 = res_data.get("9.0", {"valor": None, "pontos": 0, "link": ""})
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r90 = st.radio("Selecione 9.0:", ["Sim", "Não"], index=(0 if d90["valor"] == "Sim" else (1 if d90["valor"] == "Não" else None)), key=f"q90_{ano_sel}")
        with col2:
            l90 = st.text_area("Link/Evidência (9.0):", value=d90.get("link", ""), key=f"l90_{ano_sel}", height=100)

            # Extração e exibição dinâmica de múltiplos links ativos
            links_90_atuais = re.findall(r'(https?://[^\s]+)', l90)
            if links_90_atuais:
                botoes_90 = " | ".join([f"🔗 [{u}]({u})" for u in links_90_atuais])
                st.markdown(f"**Links Ativos:** {botoes_90}")

        if r90 and (r90 != d90["valor"] or l90 != d90["link"]):
            save_resp("9.0", r90, 0, l90)
            
            # Se mudou para Não, limpa os quesitos dependentes para evitar lixo no banco
            if r90 == "Não":
                save_resp("9.1", "", 0.0, "")
                save_resp("9.2", "[]", 0.0, "")
            
            if links_90_atuais:
                links_90_antigos = re.findall(r'(https?://[^\s]+)', d90.get("link", ""))
                if links_90_atuais != links_90_antigos:
                    modal_aviso_link("9.0", links_90_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
            
        bloco_comentarios("9.0", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # --- BLOCO DEPENDENTE (SÓ ABRE SE 9.0 FOR SIM) ---
        if r90 == "Sim":
            # --- QUESITO 9.1 ---
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader("QUESITO 9.1")
            st.write("**Informe a página eletrônica (link na internet) de divulgação do Anexo de Riscos Fiscais (XYZ se não disponível):**")
            d91 = res_data.get("9.1", {"valor": "", "pontos": 0.0, "link": ""})
            if not isinstance(d91, dict):
                d91 = {"valor": str(d91), "pontos": 0.0, "link": ""}

            col1, col2 = st.columns([1, 2])
            with col1:
                v91 = st.text_input("Página eletrônica (link):", value=d91["valor"], key=f"q91_{ano_sel}")
                
                # --- CÁLCULO E EXIBIÇÃO DA PONTUAÇÃO ---
                if v91.strip().upper() == "XYZ":
                    pts91 = -10.0
                    st.markdown(f"<span style='color:#dc3545; font-weight:bold;'>Pontuação: {pts91} pts</span> (Penalidade aplicada)", unsafe_allow_html=True)
                elif not v91.strip():
                    pts91 = 0.0
                    st.markdown(f"<span style='color:#6c757d; font-weight:bold;'>Pontuação: {pts91} pts</span> (Aguardando preenchimento)", unsafe_allow_html=True)
                else:
                    pts91 = 0.0
                    st.markdown(f"<span style='color:#28a745; font-weight:bold;'>Pontuação: {pts91} pts</span> (Link válido)", unsafe_allow_html=True)

            with col2:
                l91 = st.text_area("Link/Evidência (9.1):", value=d91.get("link", ""), key=f"l91_{ano_sel}", height=100)

                # Extração e exibição dinâmica de múltiplos links ativos para o 9.1
                links_91_atuais = re.findall(r'(https?://[^\s]+)', l91)
                if links_91_atuais:
                    botoes_91 = " | ".join([f"🔗 [{u}]({u})" for u in links_91_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_91}")

            if v91 != d91["valor"] or l91 != d91["link"]:
                save_resp("9.1", v91, pts91, l91)
                
                if links_91_atuais:
                    links_91_antigos = re.findall(r'(https?://[^\s]+)', d91.get("link", ""))
                    if links_91_atuais != links_91_antigos:
                        modal_aviso_link("9.1", links_91_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
                
            bloco_comentarios("9.1", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

            # --- QUESITO 9.2 ---
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader("QUESITO 9.2")
            st.write("**Assinale as etapas para gerenciamento dos riscos contidas Anexo de Riscos Fiscais:**")
            d92 = res_data.get("9.2", {"valor": "[]", "pontos": 0.0, "link": ""})
            
            etapas_risco = {
                "Identificação do tipo de risco e da exposição ao risco – 0,5": 0.5,
                "Mensuração ou quantificação dessa exposição – 0,5": 0.5,
                "Estimativa do grau de tolerância das contas públicas ao comportamento frente ao risco – 0,5": 0.5,
                "Decisão estratégica sobre as opções para enfrentar o risco – 0,5": 0.5,
                "Implementação de condutas de mitigação do risco e de mechanisms de controle para prevenir perdas decorrentes do risco – 0,5": 0.5,
                "Monitoramento contínuo da exposição ao longo do tempo, preferencialmente através de sitemas institucionalizados (Controle Interno) – 01": 1.0
            }
            
            col1, col2 = st.columns([1, 2])
            with col1:
                # Desserialização segura do array do banco para o estado da lista
                try:
                    lista_salva_92 = ast.literal_eval(d92["valor"])
                    if not isinstance(lista_salva_92, list):
                        lista_salva_92 = []
                except Exception:
                    lista_salva_92 = []

                sel92 = []
                pts92 = 0.0
                
                # Renderização dos Checkboxes com indexador de chaves fixas (evitando hash dinâmico)
                for idx, (item, pt) in enumerate(etapas_risco.items()):
                    if st.checkbox(item, value=item in lista_salva_92, key=f"q92_opt_{idx}_{ano_sel}"):
                        sel92.append(item)
                        pts92 += pt
                
                st.markdown(f"<span style='color:#28a745; font-weight:bold;'>Pontuação Total: {pts92:.1f} pts</span>", unsafe_allow_html=True)

            with col2:
                l92 = st.text_area("Link/Evidência (9.2):", value=d92.get("link", ""), key=f"l92_{ano_sel}", height=100)

                # Extração e exibição dinâmica de múltiplos links ativos para o 9.2
                links_92_atuais = re.findall(r'(https?://[^\s]+)', l92)
                if links_92_atuais:
                    botoes_92 = " | ".join([f"🔗 [{u}]({u})" for u in links_92_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_92}")

            if str(sel92) != d92["valor"] or l92 != d92["link"]:
                save_resp("9.2", str(sel92), pts92, l92)
                
                if links_92_atuais:
                    links_92_antigos = re.findall(r'(https?://[^\s]+)', d92.get("link", ""))
                    if links_92_atuais != links_92_antigos:
                        modal_aviso_link("9.2", links_92_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
                
            bloco_comentarios("9.2", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

        # =============================================================================
        # SEÇÃO 10: COMPATIBILIDADE ORÇAMENTÁRIA (LOA x PPA x LDO)
        # =============================================================================
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 10.0")
        st.write("**Assinale os itens capazes de atestar a compatibilidade entre a LOA, PPA e LDO:**")
        d100 = res_data.get("10.0", {"valor": "[]", "pontos": 0.0, "link": ""})
        
        compatibilidades = {
            "Programas constantes do PPA constam na LOA – 01": 1.0,
            "Programas e ações constantes da LDO constam da LOA – 02": 2.0,
            "As receitas e despesas da LOA são compatíveis com o Resultado Primário da LDO, incluindo, no máximo, a variação da inflação do interregno temporal dos referidos projetos de lei – 02": 2.0,
            "O Resultado Nominal constante da LDO consta da LOA, com variação de no máximo a variação da inflação do interregno temporal dos referidos projetos de lei – 02": 2.0,
            "A estimativa de renúncia fiscal prevista na LDO coincide com o estimado na LOA com variação limitada à variação da inflação – 02": 2.0,
            "A estimativa de receita e respectivos critérios presentes na LOA são compatíveis com os previstos na LDO em relação à receita de IPTU – 02": 2.0,
            "A estimativa de receita e respectivos critérios presentes na LOA são compatíveis com os previstos na LDO em relação à receita de ISSQN – 02": 2.0,
            "A estimativa de receita e respectivos critérios presentes na LOA são compatíveis com os previstos na LDO em relação à receita de ITBI – 02": 2.0,
            "Os investimentos, parte das despesas de capital, previstas na LOA e LDO are compatíveis com as previsões do PPA – 02": 2.0,
            "A LDO e a LOA não são compatíveis com o PPA – -10 (perde 10 pontos)": -10.0
        }
        
        col1, col2 = st.columns([1, 2])
        with col1:
            # Desserialização de strings salvas em formato de lista estruturada
            try:
                lista_salva_100 = ast.literal_eval(d100["valor"])
                if not isinstance(lista_salva_100, list):
                    lista_salva_100 = []
            except Exception:
                lista_salva_100 = []

            sel100 = []
            
            # Substituição do hash(item) instável por indexação enumerada fixa
            for idx, (item, pt) in enumerate(compatibilidades.items()):
                if st.checkbox(item, value=item in lista_salva_100, key=f"q100_opt_{idx}_{ano_sel}"):
                    sel100.append(item)
            
            # --- CÁLCULO DA PONTUAÇÃO (COM PENALIDADE ANULATÓRIA) ---
            if any("não são compatíveis" in p for p in sel100):
                pts100 = -10.0
                st.markdown(f"<span style='color:#dc3545; font-weight:bold;'>Pontuação Total: {pts100} pts</span> (Penalidade aplicada)", unsafe_allow_html=True)
            else:
                pts100 = sum(compatibilidades[p] for p in sel100)
                st.markdown(f"<span style='color:#28a745; font-weight:bold;'>Pontuação Total: {pts100:.1f} pts</span>", unsafe_allow_html=True)

        with col2:
            l100 = st.text_area("Link/Evidência (10.0):", value=d100.get("link", ""), key=f"l100_{ano_sel}", height=100)

            # Varredura por Regex para exibição inline de múltiplos links ativos
            links_100_atuais = re.findall(r'(https?://[^\s]+)', l100)
            if links_100_atuais:
                botoes_100 = " | ".join([f"🔗 [{u}]({u})" for u in links_100_atuais])
                st.markdown(f"**Links Ativos:** {botoes_100}")

        if str(sel100) != d100["valor"] or l100 != d100["link"]:
            save_resp("10.0", str(sel100), pts100, l100)
            
            if links_100_atuais:
                links_100_antigos = re.findall(r'(https?://[^\s]+)', d100.get("link", ""))
                if links_100_atuais != links_100_antigos:
                    modal_aviso_link("10.0", links_100_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
            
        bloco_comentarios("10.0", res_data)
        st.markdown('</div>', unsafe_allow_html=True)


        # =============================================================================
        # SEÇÃO 11: CRÉDITOS ADICIONAIS NA LOA
        # =============================================================================
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 11.0")
        st.write("**Na Lei Orçamentária Anual (LOA), há previsão para abertura de créditos adicionais por decreto?**")
        d110 = res_data.get("11.0", {"valor": None, "pontos": 0, "link": ""})
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r110 = st.radio("Selecione 11.0:", ["Sim", "Não"], index=(0 if d110["valor"] == "Sim" else (1 if d110["valor"] == "Não" else None)), key=f"q110_{ano_sel}")
        with col2:
            l110 = st.text_area("Link/Evidência (11.0):", value=d110.get("link", ""), key=f"l110_{ano_sel}", height=100)

            # Varredura por Regex para exibição inline de múltiplos links ativos
            links_110_atuais = re.findall(r'(https?://[^\s]+)', l110)
            if links_110_atuais:
                botoes_110 = " | ".join([f"🔗 [{u}]({u})" for u in links_110_atuais])
                st.markdown(f"**Links Ativos:** {botoes_110}")

        if r110 and (r110 != d110["valor"] or l110 != d110["link"]):
            save_resp("11.0", r110, 0, l110)
            
            if r110 == "Não":
                save_resp("11.1", "0.0|0.0", 0.0, "")
            
            if links_110_atuais:
                links_110_antigos = re.findall(r'(https?://[^\s]+)', d110.get("link", ""))
                if links_110_atuais != links_110_antigos:
                    modal_aviso_link("11.0", links_110_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
            
        bloco_comentarios("11.0", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # --- BLOCO DEPENDENTE (SÓ ABRE SE 11.0 FOR SIM) ---
        if r110 == "Sim":
            # --- QUESITO 11.1 ---
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader("QUESITO 11.1")
            st.write("**Qual o percentual autorizado na Lei Orçamentária Anual (LOA) para abertura de crédito adicional suplementar?**")
            d111 = res_data.get("11.1", {"valor": "0.0|0.0", "pontos": 0.0, "link": ""})
            
            # Faz o parse seguro do valor composto da LOA e da Inflação
            try:
                string_valores = d111["valor"] if "|" in d111["valor"] else f"{d111['valor']}|0.0"
                v_loa_salvo, v_inf_salvo = string_valores.split("|")
                val_loa_inicial = float(v_loa_salvo)
                val_inf_inicial = float(v_inf_salvo)
            except Exception:
                val_loa_inicial = 0.0
                val_inf_inicial = 0.0

            col1, col2 = st.columns([1, 2])
            with col1:
                v111 = st.number_input("Percentual autorizado na LOA (%):", min_value=0.0, max_value=100.0, value=val_loa_inicial, step=0.01, format="%.2f", key=f"q111_loa_{ano_sel}")
                inf111 = st.number_input("Informe a inflação oficial do período (%):", min_value=0.0, max_value=100.0, value=val_inf_inicial, step=0.01, format="%.2f", key=f"q111_inf_{ano_sel}")
                
                # --- CÁLCULO CONDICIONAL SÓ APÓS EDIÇÃO ---
                if v111 == 0.0 and inf111 == 0.0:
                    pts111 = 0.0
                    st.markdown(f"<span style='color:#6c757d; font-weight:bold;'>Pontuação: {pts111:.1f} pts</span> (Aguardando modificação dos campos)", unsafe_allow_html=True)
                else:
                    if v111 <= inf111:
                        pts111 = 6.0
                        st.markdown(f"<span style='color:#28a745; font-weight:bold;'>Pontuação: {pts111:.1f} pts</span> (% alteração ≤ inflação)", unsafe_allow_html=True)
                    else:
                        pts111 = 0.0
                        st.markdown(f"<span style='color:#dc3545; font-weight:bold;'>Pontuação: {pts111:.1f} pts</span> (% alteração > inflação)", unsafe_allow_html=True)

            with col2:
                l111 = st.text_area("Link/Evidência (11.1):", value=d111.get("link", ""), key=f"l111_{ano_sel}", height=140)

                # Varredura por Regex para exibição inline de múltiplos links ativos
                links_111_atuais = re.findall(r'(https?://[^\s]+)', l111)
                if links_111_atuais:
                    botoes_111 = " | ".join([f"🔗 [{u}]({u})" for u in links_111_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_111}")

            # Junta os valores editados em uma única string estruturada para salvar no banco
            valor_composto = f"{v111}|{inf111}"

            if valor_composto != d111["valor"] or l111 != d111["link"]:
                save_resp("11.1", valor_composto, pts111, l111)
                
                if links_111_atuais:
                    links_111_antigos = re.findall(r'(https?://[^\s]+)', d111.get("link", ""))
                    if links_111_atuais != links_111_antigos:
                        modal_aviso_link("11.1", links_111_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
                
            bloco_comentarios("11.1", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

        # =============================================================================
        # SEÇÃO 12: ESTRUTURA ADMINISTRATIVA DE PLANEJAMENTO
        # =============================================================================
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 12.0")
        st.write("**Há estrutura administrativa voltada para planejamento?**")
        d120 = res_data.get("12.0", {"valor": None, "pontos": 0, "link": ""})
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r120 = st.radio("Selecione 12.0:", ["Sim", "Não"], index=(0 if d120["valor"] == "Sim" else (1 if d120["valor"] == "Não" else None)), key=f"q120_{ano_sel}")
        with col2:
            l120 = st.text_area("Link/Evidência (12.0):", value=d120.get("link", ""), key=f"l120_{ano_sel}", height=100)

            # Varredura por Regex para exibição inline de múltiplos links ativos
            links_120_atuais = re.findall(r'(https?://[^\s]+)', l120)
            if links_120_atuais:
                botoes_120 = " | ".join([f"🔗 [{u}]({u})" for u in links_120_atuais])
                st.markdown(f"**Links Ativos:** {botoes_120}")

        if r120 and (r120 != d120["valor"] or l120 != d120["link"]):
            save_resp("12.0", r120, 0, l120)
            
            # Cascata de limpeza se o principal for Não para evitar lixo residual no banco
            if r120 == "Não":
                save_resp("12.1", "Não", 0.0, "")
                save_resp("12.1.1", "", 0.0, "")
                save_resp("12.1.2", "", 0.0, "")
            
            if links_120_atuais:
                links_120_antigos = re.findall(r'(https?://[^\s]+)', d120.get("link", ""))
                if links_120_atuais != links_120_antigos:
                    modal_aviso_link("12.0", links_120_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
            
        bloco_comentarios("12.0", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # --- GATILHO NÍVEL 1 (SÓ ABRE SE 12.0 FOR SIM) ---
        if r120 == "Sim":
            # --- QUESITO 12.1 ---
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader("QUESITO 12.1")
            st.write("**A prefeitura dispõe de recursos humanos para operacionalização das atividades de planejamento?**")
            d121 = res_data.get("12.1", {"valor": None, "pontos": 0.0, "link": ""})
            
            col1, col2 = st.columns([1, 2])
            with col1:
                r121 = st.radio("Selecione 12.1:", ["Sim", "Não"], index=(0 if d121["valor"] == "Sim" else (1 if d121["valor"] == "Não" else None)), key=f"q121_{ano_sel}")
            with col2:
                l121 = st.text_area("Link/Evidência (12.1):", value=d121.get("link", ""), key=f"l121_{ano_sel}", height=100)

                # Varredura por Regex para exibição inline de múltiplos links ativos
                links_121_atuais = re.findall(r'(https?://[^\s]+)', l121)
                if links_121_atuais:
                    botoes_121 = " | ".join([f"🔗 [{u}]({u})" for u in links_121_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_121}")

            if r121 and (r121 != d121["valor"] or l121 != d121["link"]):
                save_resp("12.1", r121, 0.0, l121)
                
                # Se o RH de planejamento for Não, limpa em cascata os níveis inferiores subsequentes
                if r121 == "Não":
                    save_resp("12.1.1", "", 0.0, "")
                    save_resp("12.1.2", "", 0.0, "")
                
                if links_121_atuais:
                    links_121_antigos = re.findall(r'(https?://[^\s]+)', d121.get("link", ""))
                    if links_121_atuais != links_121_antigos:
                        modal_aviso_link("12.1", links_121_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
                
            bloco_comentarios("12.1", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

            # --- GATILHO NÍVEL 2 (SÓ ABRE SE 12.1 FOR SIM) ---
            if r121 == "Sim":
                # --- QUESITO 12.1.1 ---
                st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
                st.subheader("QUESITO 12.1.1")
                st.write("**Os servidores da equipe de planejamento possuem qualificação técnica para o exercício das atividades de planejamento, gestão e orçamento?**")
                d1211 = res_data.get("12.1.1", {"valor": None, "pontos": 0.0, "link": ""})
                
                opcoes_1211 = {
                    "Sim, todos os servidores possuem qualificação técnica – 00": 0.0,
                    "Sim, a maior parte dos servidores possuem qualificação técnica – -05 (perde 05 pontos)": -5.0,
                    "Sim, a menor parte dos servidores possuem qualificação técnica – -08 (perde 08 pontos)": -8.0,
                    "Não – -10 (perde 10 pontos)": -10.0
                }
                
                idx_1211 = None
                if d1211["valor"] in opcoes_1211:
                    idx_1211 = list(opcoes_1211.keys()).index(d1211["valor"])

                col1, col2 = st.columns([1, 2])
                with col1:
                    r1211 = st.radio("Selecione 12.1.1:", list(opcoes_1211.keys()), index=idx_1211, key=f"q1211_{ano_sel}")
                    pts1211 = opcoes_1211[r1211] if r1211 else 0.0
                    
                    if r1211:
                        if pts1211 < 0:
                            st.markdown(f"<span style='color:#dc3545; font-weight:bold;'>Pontuação: {pts1211:.1f} pts</span> (Penalidade aplicada)", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<span style='color:#28a745; font-weight:bold;'>Pontuação: {pts1211:.1f} pts</span>", unsafe_allow_html=True)

                with col2:
                    l1211 = st.text_area("Link/Evidência (12.1.1):", value=d1211.get("link", ""), key=f"l1211_{ano_sel}", height=150)

                    # Varredura por Regex para exibição inline de múltiplos links ativos
                    links_1211_atuais = re.findall(r'(https?://[^\s]+)', l1211)
                    if links_1211_atuais:
                        botoes_1211 = " | ".join([f"🔗 [{u}]({u})" for u in links_1211_atuais])
                        st.markdown(f"**Links Ativos:** {botoes_1211}")

                if r1211 and (r1211 != d1211["valor"] or l1211 != d1211["link"]):
                    save_resp("12.1.1", r1211, pts1211, l1211)
                    
                    if links_1211_atuais:
                        links_1211_antigos = re.findall(r'(https?://[^\s]+)', d1211.get("link", ""))
                        if links_1211_atuais != links_1211_antigos:
                            modal_aviso_link("12.1.1", links_1211_atuais)
                        else:
                            st.rerun()
                    else:
                        st.rerun()
                    
                bloco_comentarios("12.1.1", res_data)
                st.markdown('</div>', unsafe_allow_html=True)

                # --- QUESITO 12.1.2 ---
                st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
                st.subheader("QUESITO 12.1.2")
                st.write("**Os servidores responsáveis pelo planejamento recebem treinamento específico para a matéria? Treinamento periódico pelo menos 1 vez ao ano.**")
                d1212 = res_data.get("12.1.2", {"valor": None, "pontos": 0.0, "link": ""})
                
                opcoes_1212 = {
                    "Sim – 00": 0.0,
                    "Não – -10 (perde 10 pontos)": -10.0
                }
                
                idx_1212 = None
                if d1212["valor"] in opcoes_1212:
                    idx_1212 = list(opcoes_1212.keys()).index(d1212["valor"])

                col1, col2 = st.columns([1, 2])
                with col1:
                    r1212 = st.radio("Selecione 12.1.2:", list(opcoes_1212.keys()), index=idx_1212, key=f"q1212_{ano_sel}")
                    pts1212 = opcoes_1212[r1212] if r1212 else 0.0
                    
                    if r1212:
                        if pts1212 < 0:
                            st.markdown(f"<span style='color:#dc3545; font-weight:bold;'>Pontuação: {pts1212:.1f} pts</span> (Penalidade aplicada)", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<span style='color:#28a745; font-weight:bold;'>Pontuação: {pts1212:.1f} pts</span>", unsafe_allow_html=True)

                with col2:
                    l1212 = st.text_area("Link/Evidência (12.1.2):", value=d1212.get("link", ""), key=f"l1212_{ano_sel}", height=120)

                    # Varredura por Regex para exibição inline de múltiplos links ativos
                    links_1212_atuais = re.findall(r'(https?://[^\s]+)', l1212)
                    if links_1212_atuais:
                        botoes_1212 = " | ".join([f"🔗 [{u}]({u})" for u in links_1212_atuais])
                        st.markdown(f"**Links Ativos:** {botoes_1212}")

                if r1212 and (r1212 != d1212["valor"] or l1212 != d1212["link"]):
                    save_resp("12.1.2", r1212, pts1212, l1212)
                    
                    if links_1212_atuais:
                        links_1212_antigos = re.findall(r'(https?://[^\s]+)', d1212.get("link", ""))
                        if links_1212_atuais != links_1212_antigos:
                            modal_aviso_link("12.1.2", links_1212_atuais)
                        else:
                            st.rerun()
                    else:
                        st.rerun()
                    
                bloco_comentarios("12.1.2", res_data)
                st.markdown('</div>', unsafe_allow_html=True)

   # =============================================================================
        # SEÇÃO 13: ACOMPANHAMENTO DA EXECUÇÃO DO PLANEJAMENTO
        # =============================================================================
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 13.0")
        st.write("**Há acompanhamento da execução do planejamento?**")
        d130 = res_data.get("13.0", {"valor": None, "pontos": 0, "link": ""})
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r130 = st.radio("Selecione 13.0:", ["Sim", "Não"], index=(0 if d130["valor"] == "Sim" else (1 if d130["valor"] == "Não" else None)), key=f"q130_{ano_sel}")
        with col2:
            l130 = st.text_area("Link/Evidência (13.0):", value=d130.get("link", ""), key=f"l130_{ano_sel}", height=100)

            # Varredura por Regex para exibição inline de múltiplos links ativos
            links_130_atuais = re.findall(r'(https?://[^\s]+)', l130)
            if links_130_atuais:
                botoes_130 = " | ".join([f"🔗 [{u}]({u})" for u in links_130_atuais])
                st.markdown(f"**Links Ativos:** {botoes_130}")

        if r130 and (r130 != d130["valor"] or l130 != d130["link"]):
            save_resp("13.0", r130, 0, l130)
            
            # Cascata de limpeza completa caso a raiz mude para Não para evitar lixo residual
            if r130 == "Não":
                save_resp("13.1", "[]", 0.0, "")
                save_resp("13.1.1", "[]", 0.0, "")
                save_resp("13.1.1.1", "", 0.0, "")
                save_resp("13.2", None, 0.0, "")
                save_resp("13.3", None, 0.0, "")
            
            if links_130_atuais:
                links_130_antigos = re.findall(r'(https?://[^\s]+)', d130.get("link", ""))
                if links_130_atuais != links_130_antigos:
                    modal_aviso_link("13.0", links_130_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
                
        bloco_comentarios("13.0", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # --- BLOCO CONDICIONAL (Só exibe sub-quesitos se 13.0 for "Sim") ---
        if r130 == "Sim":

            # --- QUESITO 13.1 ---
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader("QUESITO 13.1")
            st.write("**A prefeitura demonstra e avalia, com periodicidade quadrimestral, o cumprimento das metas fiscais em audiências públicas?** *(Art. 9º, § 4º, da LRF)*")
            
            d131 = res_data.get("13.1", {"valor": "[]", "pontos": 0.0, "link": ""})
            opc131 = {
                "Realizou Audiência pública do 1º Quadrimestre até o final do mês de maio de 2025 – 02": 2.0,
                "Realizou Audiência pública do 2º Quadrimestre até o final do mês de setembro de 2025 – 02": 2.0,
                "Realizou Audiência pública do 3º Quadrimestre até o final do mês de fevereiro de 2026 – 02": 2.0,
                "Não realizou audiência pública quadrimestral dentro do prazo – 00": 0.0,
                "Não realizou nenhuma audiência pública quadrimestral na Câmara Municipal – -10 (perde 10 pontos)": -10.0
            }
            
            col1, col2 = st.columns([1, 2])
            with col1:
                try:
                    lista_salva_131 = ast.literal_eval(d131["valor"])
                    if not isinstance(lista_salva_131, list):
                        lista_salva_131 = []
                except Exception:
                    lista_salva_131 = []

                sel131 = []
                for idx, (opt, pt) in enumerate(opc131.items()):
                    if st.checkbox(opt, value=opt in lista_salva_131, key=f"q131_opt_{idx}_{ano_sel}"):
                        sel131.append(opt)
                
                # Regra de pontuação com penalidade anulatória
                if any("Não realizou nenhuma" in p for p in sel131):
                    pts131 = -10.0
                    st.markdown(f"<span style='color:#dc3545; font-weight:bold;'>Pontuação Total: {pts131} pts</span> (Penalidade aplicada)", unsafe_allow_html=True)
                elif any("dentro do prazo" in p for p in sel131):
                    pts131 = 0.0
                    st.markdown(f"<span style='color:#6c757d; font-weight:bold;'>Pontuação Total: {pts131} pts</span>", unsafe_allow_html=True)
                else:
                    pts131 = sum(opc131[p] for p in sel131)
                    st.markdown(f"<span style='color:#28a745; font-weight:bold;'>Pontuação Total: {pts131:.1f} pts</span>", unsafe_allow_html=True)
            
            with col2:
                l131 = st.text_area("Link/Evidência (13.1):", value=d131.get("link", ""), key=f"l131_{ano_sel}", height=120)
                
                links_131_atuais = re.findall(r'(https?://[^\s]+)', l131)
                if links_131_atuais:
                    botoes_131 = " | ".join([f"🔗 [{u}]({u})" for u in links_131_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_131}")

            if str(sel131) != d131["valor"] or l131 != d131["link"]:
                save_resp("13.1", str(sel131), pts131, l131)
                
                if links_131_atuais:
                    links_131_antigos = re.findall(r'(https?://[^\s]+)', d131.get("link", ""))
                    if links_131_atuais != links_131_antigos:
                        modal_aviso_link("13.1", links_131_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
                    
            bloco_comentarios("13.1", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

            # --- QUESITO 13.1.1 ---
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader("QUESITO 13.1.1")
            st.write("**Foram elaborados os Relatórios Quadrimestrais das metas fiscais para as audiências públicas?**")
            
            d1311 = res_data.get("13.1.1", {"valor": "[]", "pontos": 0.0, "link": ""})
            opc1311 = {
                "Relatório da Audiência pública do 1º Quadrimestre – 01": 1.0,
                "Relatório da Audiência pública do 2º Quadrimestre – 01": 1.0,
                "Relatório da Audiência pública do 3º Quadrimestre – 01": 1.0,
                "Não elaborou relatório de nenhuma audiência pública quadrimestral – 00": 0.0
            }
            
            col1, col2 = st.columns([1, 2])
            with col1:
                try:
                    lista_salva_1311 = ast.literal_eval(d1311["valor"])
                    if not isinstance(lista_salva_1311, list):
                        lista_salva_1311 = []
                except Exception:
                    lista_salva_1311 = []

                sel1311 = []
                for idx, (opt, pt) in enumerate(opc1311.items()):
                    if st.checkbox(opt, value=opt in lista_salva_1311, key=f"q1311_opt_{idx}_{ano_sel}"):
                        sel1311.append(opt)
                        
                if any("Não elaborou" in p for p in sel1311):
                    pts1311 = 0.0
                    st.markdown(f"<span style='color:#dc3545; font-weight:bold;'>Pontuação Total: {pts1311} pts</span>", unsafe_allow_html=True)
                else:
                    pts1311 = sum(opc1311[p] for p in sel1311)
                    st.markdown(f"<span style='color:#28a745; font-weight:bold;'>Pontuação Total: {pts1311:.1f} pts</span>", unsafe_allow_html=True)
            
            with col2:
                l1311 = st.text_area("Link/Evidência (13.1.1):", value=d1311.get("link", ""), key=f"l1311_{ano_sel}", height=120)
                
                links_1311_atuais = re.findall(r'(https?://[^\s]+)', l1311)
                if links_1311_atuais:
                    botoes_1311 = " | ".join([f"🔗 [{u}]({u})" for u in links_1311_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_1311}")
                    
            if str(sel1311) != d1311["valor"] or l1311 != d1311["link"]:
                save_resp("13.1.1", str(sel1311), pts1311, l1311)
                
                if links_1311_atuais:
                    links_1311_antigos = re.findall(r'(https?://[^\s]+)', d1311.get("link", ""))
                    if links_1311_atuais != links_1311_antigos:
                        modal_aviso_link("13.1.1", links_1311_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
                    
            bloco_comentarios("13.1.1", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

            # --- QUESITO 13.1.1.1 ---
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader("QUESITO 13.1.1.1")
            st.write("**Informe a página eletrônica (link na internet) de divulgação dos Relatórios Quadrimestrais de Metas Fiscais:** *(Insira XYZ se indisponível)*")
            
            d13111 = res_data.get("13.1.1.1", {"valor": "", "pontos": 0.0, "link": ""})
            
            col1, col2 = st.columns([1, 2])
            with col1:
                v13111 = st.text_input("Link URL (Relatórios):", value=d13111["valor"], key=f"l13111_{ano_sel}")
                
                pts13111 = 0.0
                if v13111.strip() and v13111.strip().upper() != "XYZ":
                    pts13111 = 2.0
                    st.markdown(f"<span style='color:#28a745; font-weight:bold;'>Pontuação: {pts13111:.1f} pts</span>", unsafe_allow_html=True)
                elif v13111.strip().upper() == "XYZ":
                    st.markdown("<span style='color:#dc3545; font-weight:bold;'>Pontuação: 0.0 pts</span> (Indisponível)", unsafe_allow_html=True)
                else:
                    st.markdown("<span style='color:#6c757d; font-weight:bold;'>Pontuação: 0.0 pts</span> (Aguardando preenchimento)", unsafe_allow_html=True)
            
            with col2:
                l13111 = st.text_area("Link/Evidência (13.1.1.1):", value=d13111.get("link", ""), key=f"l13111_evid_{ano_sel}", height=100)
                
                links_13111_atuais = re.findall(r'(https?://[^\s]+)', l13111)
                if links_13111_atuais:
                    botoes_13111 = " | ".join([f"🔗 [{u}]({u})" for u in links_13111_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_13111}")

            if v13111 != d13111["valor"] or l13111 != d13111["link"]:
                save_resp("13.1.1.1", v13111, pts13111, l13111)
                
                if links_13111_atuais:
                    links_13111_antigos = re.findall(r'(https?://[^\s]+)', d13111.get("link", ""))
                    if links_13111_atuais != links_13111_antigos:
                        modal_aviso_link("13.1.1.1", links_13111_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
                    
            bloco_comentarios("13.1.1.1", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

            # --- QUESITO 13.2 ---
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader("QUESITO 13.2")
            st.write("**Houve acompanhamento mensal da execução orçamentária com participação do Prefeito?**")
            
            d132 = res_data.get("13.2", {"valor": None, "pontos": 0.0, "link": ""})
            opc132 = {"Sim – 04": 4.0, "Não – 00": 0.0}
            
            col1, col2 = st.columns([1, 2])
            with col1:
                r132 = st.radio("Selecione 13.2:", list(opc132.keys()), index=(list(opc132.keys()).index(d132["valor"]) if d132["valor"] in opc132 else None), key=f"q132_{ano_sel}")
                pts132 = opc132[r132] if r132 else 0.0
                if r132:
                    color = "#28a745" if pts132 > 0 else "#6c757d"
                    st.markdown(f"<span style='color:{color}; font-weight:bold;'>Pontuação: {pts132:.1f} pts</span>", unsafe_allow_html=True)
            
            with col2:
                l132 = st.text_area("Link/Evidência (13.2):", value=d132.get("link", ""), key=f"l132_{ano_sel}", height=100)
                
                links_132_atuais = re.findall(r'(https?://[^\s]+)', l132)
                if links_132_atuais:
                    botoes_132 = " | ".join([f"🔗 [{u}]({u})" for u in links_132_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_132}")
                    
            if r132 and (r132 != d132["valor"] or l132 != d132["link"]):
                save_resp("13.2", r132, pts132, l132)
                
                if links_132_atuais:
                    links_132_antigos = re.findall(r'(https?://[^\s]+)', d132.get("link", ""))
                    if links_132_atuais != links_132_antigos:
                        modal_aviso_link("13.2", links_132_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
                    
            bloco_comentarios("13.2", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

            # --- QUESITO 13.3 ---
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader("QUESITO 13.3")
            st.write("**O acompanhamento e avaliação da execução orçamentária serve de retroalimentação para o replanejamento dos programas e metas das peças orçamentárias?**")
            
            d133 = res_data.get("13.3", {"valor": None, "pontos": 0.0, "link": ""})
            opc133 = {
                "Sim, com emissão de relatórios e ciência do prefeito – 20": 20.0,
                "Sim, com emissão de relatório e sem ciência do prefeito – 10": 10.0,
                "Sim, sem emissão de relatório e sem ciência do prefeito – 05": 5.0,
                "Não – 00": 0.0
            }
            
            col1, col2 = st.columns([1, 2])
            with col1:
                r133 = st.radio("Selecione 13.3:", list(opc133.keys()), index=(list(opc133.keys()).index(d133["valor"]) if d133["valor"] in opc133 else None), key=f"q133_{ano_sel}")
                pts133 = opc133[r133] if r133 else 0.0
                if r133:
                    color = "#28a745" if pts133 > 0 else "#dc3545"
                    st.markdown(f"<span style='color:{color}; font-weight:bold;'>Pontuação: {pts133:.1f} pts</span>", unsafe_allow_html=True)
            
            with col2:
                l133 = st.text_area("Link/Evidência (13.3):", value=d133.get("link", ""), key=f"l133_{ano_sel}", height=120)
                
                links_133_atuais = re.findall(r'(https?://[^\s]+)', l133)
                if links_133_atuais:
                    botoes_133 = " | ".join([f"🔗 [{u}]({u})" for u in links_133_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_133}")
                    
            if r133 and (r133 != d133["valor"] or l133 != d133["link"]):
                save_resp("13.3", r133, pts133, l133)
                
                if links_133_atuais:
                    links_133_antigos = re.findall(r'(https?://[^\s]+)', d133.get("link", ""))
                    if links_133_atuais != links_133_antigos:
                        modal_aviso_link("13.3", links_133_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
                    
            bloco_comentarios("13.3", res_data)
            st.markdown('</div>', unsafe_allow_html=True)
        

        # =============================================================================
        # SEÇÃO 14: SISTEMA DE CONTROLE INTERNO
        # =============================================================================
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 14.0")
        st.write("**Houve a instituição e regulamentação das operações do Sistema de Controle Interno?**")
        d140 = res_data.get("14.0", {"valor": None, "pontos": 0, "link": ""})
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r140 = st.radio("Selecione 14.0:", ["Sim", "Não"], index=(0 if d140["valor"] == "Sim" else (1 if d140["valor"] == "Não" else None)), key=f"q140_{ano_sel}")
        with col2:
            l140 = st.text_area("Link/Evidência (14.0):", value=d140.get("link", ""), key=f"l140_{ano_sel}", height=100)

            # Varredura por Regex para exibição inline de múltiplos links ativos
            links_140_atuais = re.findall(r'(https?://[^\s]+)', l140)
            if links_140_atuais:
                botoes_140 = " | ".join([f"🔗 [{u}]({u})" for u in links_140_atuais])
                st.markdown(f"**Links Ativos:** {botoes_140}")

        if r140 and (r140 != d140["valor"] or l140 != d140["link"]):
            save_resp("14.0", r140, 0, l140)
            
            # Cascata de limpeza completa se mudar para Não para evitar lixo residual
            if r140 == "Não":
                save_resp("14.1", "||", 0.0, "")
                save_resp("14.2", "", 0.0, "")
                save_resp("14.3", "[]", 0.0, "")
            
            if links_140_atuais:
                links_140_antigos = re.findall(r'(https?://[^\s]+)', d140.get("link", ""))
                if links_140_atuais != links_140_antigos:
                    modal_aviso_link("14.0", links_140_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
                
        bloco_comentarios("14.0", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # --- BLOCO DEPENDENTE (SÓ ABRE SE 14.0 FOR SIM) ---
        if r140 == "Sim":
            
            # --- QUESITO 14.1 ---
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader("QUESITO 14.1")
            st.write("**Informe o instrumento normativo de regulamentação do Sistema de Controle Interno, Número e Data da publicação:**")
            d141 = res_data.get("14.1", {"valor": "||", "pontos": 0.0, "link": ""})
            
            try:
                partes_141 = d141["valor"].split("|")
                inst_inicial = partes_141[0] if len(partes_141) > 0 else ""
                num_inicial = partes_141[1] if len(partes_141) > 1 else ""
                data_inicial = partes_141[2] if len(partes_141) > 2 else ""
            except Exception:
                inst_inicial, num_inicial, data_inicial = "", "", ""

            col1, col2 = st.columns([1, 2])
            with col1:
                v_inst = st.text_input("Instrumento Normativo (Ex: Lei, Decreto):", value=inst_inicial, key=f"q141_inst_{ano_sel}")
                v_num = st.text_input("Número do instrumento:", value=num_inicial, key=f"q141_num_{ano_sel}")
                v_data = st.text_input("Data da publicação (DD/MM/AAAA):", value=data_inicial, key=f"q141_data_{ano_sel}")
            
            with col2:
                l141 = st.text_area("Link/Evidência (14.1):", value=d141.get("link", ""), key=f"l141_{ano_sel}", height=180)
                
                links_141_atuais = re.findall(r'(https?://[^\s]+)', l141)
                if links_141_atuais:
                    botoes_141 = " | ".join([f"🔗 [{u}]({u})" for u in links_141_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_141}")

            valor_composto_141 = f"{v_inst}|{v_num}|{v_data}"

            if valor_composto_141 != d141["valor"] or l141 != d141["link"]:
                save_resp("14.1", valor_composto_141, 0.0, l141)
                
                if links_141_atuais:
                    links_141_antigos = re.findall(r'(https?://[^\s]+)', d141.get("link", ""))
                    if links_141_atuais != links_141_antigos:
                        modal_aviso_link("14.1", links_141_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
                    
            bloco_comentarios("14.1", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

            # --- QUESITO 14.2 ---
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader("QUESITO 14.2")
            st.write("**Página eletrônica (link na internet) de divulgação do instrumento de regulamentação do sistema de controle interno (XYZ se não disponível):**")
            d142 = res_data.get("14.2", {"valor": "", "pontos": 0.0, "link": ""})
            if not isinstance(d142, dict):
                d142 = {"valor": str(d142), "pontos": 0.0, "link": ""}

            col1, col2 = st.columns([1, 2])
            with col1:
                v142 = st.text_input("Página eletrônica (link) 14.2:", value=d142["valor"], key=f"q142_txt_{ano_sel}")
            
            with col2:
                l142 = st.text_area("Link/Evidência (14.2):", value=d142.get("link", ""), key=f"l142_{ano_sel}", height=100)
                
                links_142_atuais = re.findall(r'(https?://[^\s]+)', l142)
                if links_142_atuais:
                    botoes_142 = " | ".join([f"🔗 [{u}]({u})" for u in links_142_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_142}")

            if v142 != d142["valor"] or l142 != d142["link"]:
                save_resp("14.2", v142, 0.0, l142)
                
                if links_142_atuais:
                    links_142_antigos = re.findall(r'(https?://[^\s]+)', d142.get("link", ""))
                    if links_142_atuais != links_142_antigos:
                        modal_aviso_link("14.2", links_142_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
                    
            bloco_comentarios("14.2", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

            # --- QUESITO 14.3 ---
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader("QUESITO 14.3")
            st.write("**Assinale as funções atribuídas ao sistema controle interno:**")
            d143 = res_data.get("14.3", {"valor": "[]", "pontos": 0.0, "link": ""})
            
            opcoes_143 = {
                "Avaliar o cumprimento das metas físicas e financeiras dos planos orçamentários, bem como a eficiência de seus resultados – 01": 1.0,
                "Comprovar a legalidade da gestão orçamentária, financeira e patrimonial – 01": 1.0,
                "Comprovar a legalidade dos repasses a entidades do terceiro setor, avaliando a eficácia e a eficiência dos resultados alcançados – 01": 1.0,
                "Exercer o controle das operações de crédito, avais e garantias, bem como dos direitos e haveres do Município – 01": 1.0,
                "Em conjunto com autoridades da Administração Financeira do Município, assinar o Relatório de Gestão Fiscal – 01": 1.0,
                "Atestar a regularidade da tomada de contas dos ordenadores de despesa, recebedores, tesoureiros, pagadores ou assemelhados – 01": 1.0,
                "Apoiar o Tribunal de Contas no exercício de sua missão institutional – 01": 1.0,
                "Comprovar a eficácia e a eficiência da gestão orçamentária, financeira e patrimonial – 01": 1.0,
                "Acompanhar as metas de superávit orçamentário, primário e nominal – 01": 1.0,
                "Observar se as operações de créditos sujeitam-se aos limites e condições das Resoluções 40 e 43/2001, do Senado – 01": 1.0,
                "Verificar se os empréstimos e financiamentos vêm sendo pagos tal qual previsto nos respectivos contratos – 01": 1.0,
                "Verificar se está sendo providenciada a recondução da despesa de pessoal e da dívida consolidada a seus limites fiscais – 01": 1.0,
                "Comprovar se os recursos da alienação de ativos estão sendo despendidos em gastos de capital e, não, em despesas correntes – 01": 1.0,
                "Constatar se está sendo satisfeito o limite para gastos totais das Câmaras Municipais – 01": 1.0,
                "Verificar a fidelidade funcional dos responsáveis por bens e valores públicos – 01": 1.0
            }
            
            col1, col2 = st.columns([1, 2])
            with col1:
                try:
                    lista_salva_143 = ast.literal_eval(d143["valor"])
                    if not isinstance(lista_salva_143, list):
                        lista_salva_143 = []
                except Exception:
                    lista_salva_143 = []

                sel143 = []
                for idx, (item, pt) in enumerate(opcoes_143.items()):
                    if st.checkbox(item, value=item in lista_salva_143, key=f"q143_chk_{idx}_{ano_sel}"):
                        sel143.append(item)
                
                pts143 = sum(opcoes_143[p] for p in sel143)
                st.markdown(f"<span style='color:#28a745; font-weight:bold;'>Pontuação Total: {pts143:.1f} pts</span>", unsafe_allow_html=True)

            with col2:
                l143 = st.text_area("Link/Evidência (14.3):", value=d143.get("link", ""), key=f"l143_{ano_sel}", height=200)
                
                links_143_atuais = re.findall(r'(https?://[^\s]+)', l143)
                if links_143_atuais:
                    botoes_143 = " | ".join([f"🔗 [{u}]({u})" for u in links_143_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_143}")

            if str(sel143) != d143["valor"] or l143 != d143["link"]:
                save_resp("14.3", str(sel143), pts143, l143)
                
                if links_143_atuais:
                    links_143_antigos = re.findall(r'(https?://[^\s]+)', d143.get("link", ""))
                    if links_143_atuais != links_143_antigos:
                        modal_aviso_link("14.3", links_143_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
                    
            bloco_comentarios("14.3", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

            # --- QUESITO 14.4 ---
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader("QUESITO 14.4")
            st.write("**A prefeitura dispõe de recursos humanos para operacionalização das atividades do sistema de controle interno?**")
            d144 = res_data.get("14.4", {"valor": None, "pontos": 0.0, "link": ""})
            
            opcoes_144 = {"Sim – 0,5": 0.5, "Não – 00": 0.0}
            idx_144 = list(opcoes_144.keys()).index(d144["valor"]) if d144["valor"] in opcoes_144 else None

            col1, col2 = st.columns([1, 2])
            with col1:
                r144 = st.radio("Selecione 14.4:", list(opcoes_144.keys()), index=idx_144, key=f"q144_{ano_sel}")
                pts144 = opcoes_144[r144] if r144 else 0.0
                if r144:
                    color = "#28a745" if pts144 > 0 else "#6c757d"
                    st.markdown(f"<span style='color:{color}; font-weight:bold;'>Pontuação: {pts144:.1f} pts</span>", unsafe_allow_html=True)

            with col2:
                l144 = st.text_area("Link/Evidência (14.4):", value=d144.get("link", ""), key=f"l144_{ano_sel}", height=100)
                
                links_144_atuais = re.findall(r'(https?://[^\s]+)', l144)
                if links_144_atuais:
                    botoes_144 = " | ".join([f"🔗 [{u}]({u})" for u in links_144_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_144}")

            if r144 and (r144 != d144["valor"] or l144 != d144["link"]):
                save_resp("14.4", r144, pts144, l144)
                
                if links_144_atuais:
                    links_144_antigos = re.findall(r'(https?://[^\s]+)', d144.get("link", ""))
                    if links_144_atuais != links_144_antigos:
                        modal_aviso_link("14.4", links_144_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
                    
            bloco_comentarios("14.4", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

            # --- QUESITO 14.4.1 ---
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader("QUESITO 14.4.1")
            st.write("**O responsável pela Unidade Central de Controle Interno (UCCI) ocupa cargo efetivo na Administração Municipal?** *(Responsável = controlador interno ou controlador geral)*")
            d1441 = res_data.get("14.4.1", {"valor": None, "pontos": 0.0, "link": ""})
            
            opcoes_1441 = {"Sim – 05": 5.0, "Não – 00": 0.0}
            idx_1441 = list(opcoes_1441.keys()).index(d1441["valor"]) if d1441["valor"] in opcoes_1441 else None

            col1, col2 = st.columns([1, 2])
            with col1:
                r1441 = st.radio("Selecione 14.4.1:", list(opcoes_1441.keys()), index=idx_1441, key=f"q1441_{ano_sel}")
                pts1441 = opcoes_1441[r1441] if r1441 else 0.0
                if r1441:
                    color = "#28a745" if pts1441 > 0 else "#6c757d"
                    st.markdown(f"<span style='color:{color}; font-weight:bold;'>Pontuação: {pts1441:.1f} pts</span>", unsafe_allow_html=True)

            with col2:
                l1441 = st.text_area("Link/Evidência (14.4.1):", value=d1441.get("link", ""), key=f"l1441_{ano_sel}", height=100)
                
                links_1441_atuais = re.findall(r'(https?://[^\s]+)', l1441)
                if links_1441_atuais:
                    botoes_1441 = " | ".join([f"🔗 [{u}]({u})" for u in links_1441_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_1441}")

            if r1441 and (r1441 != d1441["valor"] or l1441 != d1441["link"]):
                save_resp("14.4.1", r1441, pts1441, l1441)
                
                if links_1441_atuais:
                    links_1441_antigos = re.findall(r'(https?://[^\s]+)', d1441.get("link", ""))
                    if links_1441_atuais != links_1441_antigos:
                        modal_aviso_link("14.4.1", links_1441_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
                    
            bloco_comentarios("14.4.1", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

            # --- QUESITO 14.4.2 ---
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader("QUESITO 14.4.2")
            st.write("**O quadro funcional do Sistema de Controle Interno recebe treinamento específico para execução das atividades inerentes ao cargo?** *(Treinamento periódico pelo menos 1 vez ao ano)*")
            d1442 = res_data.get("14.4.2", {"valor": None, "pontos": 0.0, "link": ""})
            
            opcoes_1442 = {"Sim – 06": 6.0, "Não – 00": 0.0}
            idx_1442 = list(opcoes_1442.keys()).index(d1442["valor"]) if d1442["valor"] in opcoes_1442 else None

            col1, col2 = st.columns([1, 2])
            with col1:
                r1442 = st.radio("Selecione 14.4.2:", list(opcoes_1442.keys()), index=idx_1442, key=f"q1442_{ano_sel}")
                pts1442 = opcoes_1442[r1442] if r1442 else 0.0
                if r1442:
                    color = "#28a745" if pts1442 > 0 else "#6c757d"
                    st.markdown(f"<span style='color:{color}; font-weight:bold;'>Pontuação: {pts1442:.1f} pts</span>", unsafe_allow_html=True)

            with col2:
                l1442 = st.text_area("Link/Evidência (14.4.2):", value=d1442.get("link", ""), key=f"l1442_{ano_sel}", height=100)
                
                links_1442_atuais = re.findall(r'(https?://[^\s]+)', l1442)
                if links_1442_atuais:
                    botoes_1442 = " | ".join([f"🔗 [{u}]({u})" for u in links_1442_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_1442}")

            if r1442 and (r1442 != d1442["valor"] or l1442 != d1442["link"]):
                save_resp("14.4.2", r1442, pts1442, l1442)
                
                if links_1442_atuais:
                    links_1442_antigos = re.findall(r'(https?://[^\s]+)', d1442.get("link", ""))
                    if links_1442_atuais != links_1442_antigos:
                        modal_aviso_link("14.4.2", links_1442_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
                    
            bloco_comentarios("14.4.2", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

            # --- QUESITO 14.4.3 ---
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader("QUESITO 14.4.3")
            st.write("**Na Prefeitura existe formalização da segregação de funções financeiras e de controle?**")
            d1443 = res_data.get("14.4.3", {"valor": None, "pontos": 0.0, "link": ""})
            
            opcoes_1443 = {"Sim – 05": 5.0, "Não – 00": 0.0}
            idx_1443 = list(opcoes_1443.keys()).index(d1443["valor"]) if d1443["valor"] in opcoes_1443 else None

            col1, col2 = st.columns([1, 2])
            with col1:
                r1443 = st.radio("Selecione 14.4.3:", list(opcoes_1443.keys()), index=idx_1443, key=f"q1443_{ano_sel}")
                pts1443 = opcoes_1443[r1443] if r1443 else 0.0
                if r1443:
                    color = "#28a745" if pts1443 > 0 else "#6c757d"
                    st.markdown(f"<span style='color:{color}; font-weight:bold;'>Pontuação: {pts1443:.1f} pts</span>", unsafe_allow_html=True)

            with col2:
                l1443 = st.text_area("Link/Evidência (14.4.3):", value=d1443.get("link", ""), key=f"l1443_{ano_sel}", height=100)
                
                links_1443_atuais = re.findall(r'(https?://[^\s]+)', l1443)
                if links_1443_atuais:
                    botoes_1443 = " | ".join([f"🔗 [{u}]({u})" for u in links_1443_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_1443}")

            if r1443 and (r1443 != d1443["valor"] or l1443 != d1443["link"]):
                save_resp("14.4.3", r1443, pts1443, l1443)
                
                if links_1443_atuais:
                    links_1443_antigos = re.findall(r'(https?://[^\s]+)', d1443.get("link", ""))
                    if links_1443_atuais != links_1443_antigos:
                        modal_aviso_link("14.4.3", links_1443_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
                    
            bloco_comentarios("14.4.3", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

            # --- QUESITO 14.4.4 ---
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader("QUESITO 14.4.4")
            st.write("**A Unidade Central de Controle Interno (UCCI) possui autonomia e independência para o exercício de suas funções?**")
            d1444 = res_data.get("14.4.4", {"valor": None, "pontos": 0.0, "link": ""})
            opc1444 = {"Sim – 06": 6.0, "Não – 00": 0.0}
            
            col1, col2 = st.columns([1, 2])
            with col1:
                r1444 = st.radio("Selecione 14.4.4:", list(opc1444.keys()), index=(list(opc1444.keys()).index(d1444["valor"]) if d1444["valor"] in opc1444 else None), key=f"q1444_{ano_sel}")
                pts1444 = opc1444[r1444] if r1444 else 0.0
                if r1444:
                    color = "#28a745" if pts1444 > 0 else "#6c757d"
                    st.markdown(f"<span style='color:{color}; font-weight:bold;'>Pontuação: {pts1444:.1f} pts</span>", unsafe_allow_html=True)

            with col2:
                l1444 = st.text_area("Link/Evidência (14.4.4):", value=d1444.get("link", ""), key=f"l1444_{ano_sel}", height=100)
                
                links_1444_atuais = re.findall(r'(https?://[^\s]+)', l1444)
                if links_1444_atuais:
                    botoes_1444 = " | ".join([f"🔗 [{u}]({u})" for u in links_1444_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_1444}")

            if r1444 and (r1444 != d1444["valor"] or l1444 != d1444["link"]):
                save_resp("14.4.4", r1444, pts1444, l1444)
                
                if links_1444_atuais:
                    links_1444_antigos = re.findall(r'(https?://[^\s]+)', d1444.get("link", ""))
                    if links_1444_atuais != links_1444_antigos:
                        modal_aviso_link("14.4.4", links_1444_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()

            bloco_comentarios("14.4.4", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

            # --- QUESITO 14.4.4.1 ---
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader("QUESITO 14.4.4.1")
            st.write("**A estrutura organizacional da Unidade Central de Controle Interno (UCCI) está associada ou subordinada a qual secretaria/diretoria?**")
            d14441 = res_data.get("14.4.4.1", {"valor": None, "pontos": 0.0, "link": ""})
            opc14441 = {
                "Administração – -06 (perde 06 pontos)": -6.0,
                "Finanças/Fazenda – -06 (perde 06 pontos)": -6.0,
                "Planejamento/Orçamento/Gestão – -06 (perde 06 pontos)": -6.0,
                "Gabinete do Prefeito – 00": 0.0,
                "Outra – -06 (perde 06 pontos)": -6.0
            }
            
            col1, col2 = st.columns([1, 2])
            with col1:
                r14441 = st.radio("Selecione 14.4.4.1:", list(opc14441.keys()), index=(list(opc14441.keys()).index(d14441["valor"]) if d14441["valor"] in opc14441 else None), key=f"q14441_{ano_sel}")
                pts14441 = opc14441[r14441] if r14441 else 0.0
                if r14441:
                    color = "#28a745" if pts14441 == 0 else "#dc3545"
                    st.markdown(f"<span style='color:{color}; font-weight:bold;'>Pontuação: {pts14441:.1f} pts</span>", unsafe_allow_html=True)

            with col2:
                l14441 = st.text_area("Link/Evidência (14.4.4.1):", value=d14441.get("link", ""), key=f"l14441_{ano_sel}", height=140)
                
                links_14441_atuais = re.findall(r'(https?://[^\s]+)', l14441)
                if links_14441_atuais:
                    botoes_14441 = " | ".join([f"🔗 [{u}]({u})" for u in links_14441_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_14441}")

            if r14441 and (r14441 != d14441["valor"] or l14441 != d14441["link"]):
                save_resp("14.4.4.1", r14441, pts14441, l14441)
                
                if links_14441_atuais:
                    links_14441_antigos = re.findall(r'(https?://[^\s]+)', d14441.get("link", ""))
                    if links_14441_atuais != links_14441_antigos:
                        modal_aviso_link("14.4.4.1", links_14441_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()

            bloco_comentarios("14.4.4.1", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

            # --- QUESITO 14.4.4.2 ---
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader("QUESITO 14.4.4.2")
            st.write("**A Unidade Central de Controle Interno (UCCI) procedeu com alguma comunicação de irregularidade ou ilegalidade em 2025?**")
            d14442 = res_data.get("14.4.4.2", {"valor": None, "pontos": 0.0, "link": ""})
            opc14442 = {
                "Sim, houve comunicação da irregularidade ou ilegalidade – 00": 0.0,
                "Houve irregularidade ou ilegalidade, mas não procedeu a comunicação – -03 (perde 03 pontos)": -3.0,
                "Não houve irregularidades nem ilegalidades – 00": 0.0
            }
            
            col1, col2 = st.columns([1, 2])
            with col1:
                r14442 = st.radio("Selecione 14.4.4.2:", list(opc14442.keys()), index=(list(opc14442.keys()).index(d14442["valor"]) if d14442["valor"] in opc14442 else None), key=f"q14442_{ano_sel}")
                pts14442 = opc14442[r14442] if r14442 else 0.0
                if r14442:
                    color = "#28a745" if pts14442 == 0 else "#dc3545"
                    st.markdown(f"<span style='color:{color}; font-weight:bold;'>Pontuação: {pts14442:.1f} pts</span>", unsafe_allow_html=True)

            with col2:
                l14442 = st.text_area("Link/Evidência (14.4.4.2):", value=d14442.get("link", ""), key=f"l14442_{ano_sel}", height=120)
                
                links_14442_atuais = re.findall(r'(https?://[^\s]+)', l14442)
                if links_14442_atuais:
                    botoes_14442 = " | ".join([f"🔗 [{u}]({u})" for u in links_14442_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_14442}")

            if r14442 and (r14442 != d14442["valor"] or l14442 != d14442["link"]):
                save_resp("14.4.4.2", r14442, pts14442, l14442)
                
                # Se mudar a raiz, limpa os sub-reparos numéricos acoplados
                if r14442 != "Sim, houve comunicação da irregularidade ou ilegalidade – 00":
                    save_resp("14.4.4.2.1_tcesp", "0", 0.0, "")
                    save_resp("14.4.4.2.1_mpsp", "0", 0.0, "")
                
                if links_14442_atuais:
                    links_14442_antigos = re.findall(r'(https?://[^\s]+)', d14442.get("link", ""))
                    if links_14442_atuais != links_14442_antigos:
                        modal_aviso_link("14.4.4.2", links_14442_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()

            bloco_comentarios("14.4.4.2", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

            # --- QUESITO CONDICIONAL 14.4.4.2.1 ---
            if r14442 == "Sim, houve comunicação da irregularidade ou ilegalidade – 00":
                st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
                st.subheader("QUESITO 14.4.4.2.1")
                st.write("**Informe a quantidade de irregularidades ou ilegalidades comunicadas ao:**")
                
                d144421_tce = res_data.get("14.4.4.2.1_tcesp", {"valor": "0", "pontos": 0.0, "link": ""})
                d144421_mp = res_data.get("14.4.4.2.1_mpsp", {"valor": "0", "pontos": 0.0, "link": ""})
                
                col1, col2 = st.columns([1, 2])
                with col1:
                    col_tce, col_mp = st.columns(2)
                    with col_tce:
                        v144421_tce = st.number_input(
                            "TCESP:", 
                            min_value=0, 
                            step=1, 
                            value=int(d144421_tce["valor"]) if d144421_tce["valor"].isdigit() else 0,
                            key=f"q144421_tce_{ano_sel}"
                        )
                    with col_mp:
                        v144421_mp = st.number_input(
                            "MPSP:", 
                            min_value=0, 
                            step=1, 
                            value=int(d144421_mp["valor"]) if d144421_mp["valor"].isdigit() else 0,
                            key=f"q144421_mp_{ano_sel}"
                        )
                    st.markdown("<span style='color:#28a745; font-weight:bold;'>Pontuação: 0.0 pts</span>", unsafe_allow_html=True)
                
                with col2:
                    # Unificado em um único text_area de evidências compartilhado pelo quesito composto
                    l144421 = st.text_area("Link/Evidência (14.4.4.2.1):", value=d144421_tce.get("link", ""), key=f"l144421_{ano_sel}", height=100)
                    
                    links_144421_atuais = re.findall(r'(https?://[^\s]+)', l144421)
                    if links_144421_atuais:
                        botoes_144421 = " | ".join([f"🔗 [{u}]({u})" for u in links_144421_atuais])
                        st.markdown(f"**Links Ativos:** {botoes_144421}")
                
                if str(v144421_tce) != d144421_tce["valor"] or str(v144421_mp) != d144421_mp["valor"] or l144421 != d144421_tce["link"]:
                    save_resp("14.4.4.2.1_tcesp", str(v144421_tce), 0.0, l144421)
                    save_resp("14.4.4.2.1_mpsp", str(v144421_mp), 0.0, l144421)
                    
                    if links_144421_atuais:
                        links_144421_antigos = re.findall(r'(https?://[^\s]+)', d144421_tce.get("link", ""))
                        if links_144421_atuais != links_144421_antigos:
                            modal_aviso_link("14.4.4.2.1", links_144421_atuais)
                        else:
                            st.rerun()
                    else:
                        st.rerun()
                        
                bloco_comentarios("14.4.4.2.1", res_data)
                st.markdown('</div>', unsafe_allow_html=True)

           # --- QUESITO 14.4.5 ---
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader("QUESITO 14.4.5")
            st.write("**O responsável pela Unidade Central de Controle Interno (UCCI) apresentou relatórios periódicos que demonstram efetivo exercício de suas atribuições?** *(Periodicidade mínima anual)*")
            d1445 = res_data.get("14.4.5", {"valor": None, "pontos": 0.0, "link": ""})
            
            opcoes_1445 = {"Sim – 05": 5.0, "Não – 00": 0.0}
            idx_1445 = list(opcoes_1445.keys()).index(d1445["valor"]) if d1445["valor"] in opcoes_1445 else None

            col1, col2 = st.columns([1, 2])
            with col1:
                r1445 = st.radio("Selecione 14.4.5:", list(opcoes_1445.keys()), index=idx_1445, key=f"q1445_{ano_sel}")
                pts1445 = opcoes_1445[r1445] if r1445 else 0.0
                if r1445:
                    color = "#28a745" if pts1445 > 0 else "#6c757d"
                    st.markdown(f"<span style='color:{color}; font-weight:bold;'>Pontuação: {pts1445:.1f} pts</span>", unsafe_allow_html=True)

            with col2:
                l1445 = st.text_area("Link/Evidência (14.4.5):", value=d1445.get("link", ""), key=f"l1445_{ano_sel}", height=100)
                
                links_1445_atuais = re.findall(r'(https?://[^\s]+)', l1445)
                if links_1445_atuais:
                    botoes_1445 = " | ".join([f"🔗 [{u}]({u})" for u in links_1445_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_1445}")

            if r1445 and (r1445 != d1445["valor"] or l1445 != d1445["link"]):
                save_resp("14.4.5", r1445, pts1445, l1445)
                
                # Cascata de limpeza se mudar para Não
                if r1445 == "Não – 00":
                    save_resp("14.4.5.1", "", 0.0, "")
                    save_resp("14.4.5.1.1", "", 0.0, "")
                
                if links_1445_atuais:
                    links_1445_antigos = re.findall(r'(https?://[^\s]+)', d1445.get("link", ""))
                    if links_1445_atuais != links_1445_antigos:
                        modal_aviso_link("14.4.5", links_1445_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
                    
            bloco_comentarios("14.4.5", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

            # --- SUB-GATILHO 14.4.5 (SÓ ABRE SE 14.4.5 FOR SIM) ---
            if r1445 == "Sim – 05":
                # --- QUESITO 14.4.5.1 ---
                st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
                st.subheader("QUESITO 14.4.5.1")
                st.write("**Com base no relatório do Controle Interno, o Prefeito determinou as providências cabíveis diante das irregularidades e ilegalidades apontadas?**")
                d14451 = res_data.get("14.4.5.1", {"valor": None, "pontos": 0.0, "link": ""})
                
                opcoes_14451 = {
                    "Sim - de todos os apontamentos – 06": 6.0,
                    "Sim - de parte dos apontamentos – 02": 2.0,
                    "Não – 00": 0.0,
                    "Não foram relatadas irregularidades – 06": 6.0
                }
                idx_14451 = list(opcoes_14451.keys()).index(d14451["valor"]) if d14451["valor"] in opcoes_14451 else None

                col1, col2 = st.columns([1, 2])
                with col1:
                    r14451 = st.radio("Selecione 14.4.5.1:", list(opcoes_14451.keys()), index=idx_14451, key=f"q14451_{ano_sel}")
                    pts14451 = opcoes_14451[r14451] if r14451 else 0.0
                    if r14451:
                        color = "#28a745" if pts14451 > 0 else "#6c757d"
                        st.markdown(f"<span style='color:{color}; font-weight:bold;'>Pontuação: {pts14451:.1f} pts</span>", unsafe_allow_html=True)

                with col2:
                    l14451 = st.text_area("Link/Evidência (14.4.5.1):", value=d14451.get("link", ""), key=f"l14451_{ano_sel}", height=120)
                    
                    links_14451_atuais = re.findall(r'(https?://[^\s]+)', l14451)
                    if links_14451_atuais:
                        botoes_14451 = " | ".join([f"🔗 [{u}]({u})" for u in links_14451_atuais])
                        st.markdown(f"**Links Ativos:** {botoes_14451}")

                if r14451 and (r14451 != d14451["valor"] or l14451 != d14451["link"]):
                    save_resp("14.4.5.1", r14451, pts14451, l14451)
                    
                    if links_14451_atuais:
                        links_14451_antigos = re.findall(r'(https?://[^\s]+)', d14451.get("link", ""))
                        if links_14451_atuais != links_14451_antigos:
                            modal_aviso_link("14.4.5.1", links_14451_atuais)
                        else:
                            st.rerun()
                    else:
                        st.rerun()
                        
                bloco_comentarios("14.4.5.1", res_data)
                st.markdown('</div>', unsafe_allow_html=True)

                # --- QUESITO 14.4.5.1.1 ---
                st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
                st.subheader("QUESITO 14.4.5.1.1")
                st.write("**O Controle Interno acompanhou as medidas e os prazos das providências determinadas pelo Prefeito diante dos apontamentos do relatório do Controle Interno?**")
                d144511 = res_data.get("14.4.5.1.1", {"valor": None, "pontos": 0.0, "link": ""})
                
                opcoes_144511 = {
                    "Sim - de todas as providências determinadas pelo Prefeito – 00": 0.0,
                    "Sim - de parte das providências determinadas pelo Prefeito – 00": 0.0,
                    "Não – -03 (perde 03 pontos)": -3.0
                }
                idx_144511 = list(opcoes_144511.keys()).index(d144511["valor"]) if d144511["valor"] in opcoes_144511 else None

                col1, col2 = st.columns([1, 2])
                with col1:
                    r144511 = st.radio("Selecione 14.4.5.1.1:", list(opcoes_144511.keys()), index=idx_144511, key=f"q144511_{ano_sel}")
                    pts144511 = opcoes_144511[r144511] if r144511 else 0.0
                    if r144511:
                        cor_144511 = "#dc3545" if pts144511 < 0 else "#28a745"
                        st.markdown(f"<span style='color:{cor_144511}; font-weight:bold;'>Pontuação: {pts144511:.1f} pts</span>", unsafe_allow_html=True)

                with col2:
                    l144511 = st.text_area("Link/Evidência (14.4.5.1.1):", value=d144511.get("link", ""), key=f"l144511_{ano_sel}", height=120)
                    
                    links_144511_atuais = re.findall(r'(https?://[^\s]+)', l144511)
                    if links_144511_atuais:
                        botoes_144511 = " | ".join([f"🔗 [{u}]({u})" for u in links_144511_atuais])
                        st.markdown(f"**Links Ativos:** {botoes_144511}")

                if r144511 and (r144511 != d144511["valor"] or l144511 != d144511["link"]):
                    save_resp("14.4.5.1.1", r144511, pts144511, l144511)
                    
                    if links_144511_atuais:
                        links_144511_antigos = re.findall(r'(https?://[^\s]+)', d144511.get("link", ""))
                        if links_144511_atuais != links_144511_antigos:
                            modal_aviso_link("14.4.5.1.1", links_144511_atuais)
                        else:
                            st.rerun()
                    else:
                        st.rerun()
                        
                bloco_comentarios("14.4.5.1.1", res_data)
                st.markdown('</div>', unsafe_allow_html=True)

            # --- QUESITO 14.5 ---
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader("QUESITO 14.5")
            st.write("**Houve a operação de Plano Operativo Anual?** *(Obs.: Plano Operativo Anual consiste no planejamento das atividades a serem executadas no exercício seguinte a sua elaboração).*")
            d145 = res_data.get("14.5", {"valor": None, "pontos": 0.0, "link": ""})
            
            col1, col2 = st.columns([1, 2])
            with col1:
                r145 = st.radio("Selecione 14.5:", ["Sim", "Não"], index=(0 if d145["valor"] == "Sim" else (1 if d145["valor"] == "Não" else None)), key=f"q145_{ano_sel}")
                if r145:
                    st.markdown("<span style='color:#28a745; font-weight:bold;'>Pontuação: 0.0 pts</span>", unsafe_allow_html=True)
            with col2:
                l145 = st.text_area("Link/Evidência (14.5):", value=d145.get("link", ""), key=f"l145_{ano_sel}", height=100)
                
                links_145_atuais = re.findall(r'(https?://[^\s]+)', l145)
                if links_145_atuais:
                    botoes_145 = " | ".join([f"🔗 [{u}]({u})" for u in links_145_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_145}")

            if r145 and (r145 != d145["valor"] or l145 != d145["link"]):
                save_resp("14.5", r145, 0.0, l145)
                
                # Cascata de limpeza se mudar para Não
                if r145 == "Não":
                    save_resp("14.5.1", "[]", 0.0, "")
                
                if links_145_atuais:
                    links_145_antigos = re.findall(r'(https?://[^\s]+)', d145.get("link", ""))
                    if links_145_atuais != links_145_antigos:
                        modal_aviso_link("14.5", links_145_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
                    
            bloco_comentarios("14.5", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

            # --- BLOCO DEPENDENTE (SÓ ABRE SE 14.5 FOR SIM) ---
            if r145 == "Sim":
                # --- QUESITO 14.5.1 ---
                st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
                st.subheader("QUESITO 14.5.1")
                st.write("**Assinale as atividades previstas no Plano Operativo Anual:**")
                d1451 = res_data.get("14.5.1", {"valor": "[]", "pontos": 0.0, "link": ""})
                
                opcoes_1451 = [
                    "Receitas",
                    "Despesas",
                    "Administração de pessoal",
                    "Estoques e almoxarifados",
                    "Administração do patrimônio",
                    "Cumprimento das metas do PPA e a execução dos programas de governo e dos orçamentos (LOA e LDO)",
                    "Cumprimento das metas fiscais, físicas e de resultados dos programas de governo, no que tange a eficiência, eficácia e efetividade",
                    "Aplicação de recursos públicos por entidades de direito público",
                    "Aplicação de recursos públicos por entidades de direito privado",
                    "Os limites e condições para a inscrição de despesas em Restos a Pagar",
                    "Cumprimento da legislação de licitações e fiscalização de contratos",
                    "Cumprimento do limite de gastos totais dos legislativos municipais, inclusive no que se refere ao atingimento de metas fiscais (Gestão Fiscal)",
                    "Transferência para o Legislativo Municipal (Repasses de Duodécimos)",
                    "Contabilidade",
                    "Transparência",
                    "Lei de Acesso à Informação",
                    "Outros"
                ]
                
                col1, col2 = st.columns([1, 2])
                with col1:
                    sel1451 = []
                    for item in opcoes_1451:
                        if st.checkbox(item, value=item in d1451["valor"], key=f"q1451_chk_{item}_{ano_sel}"):
                            sel1451.append(item)
                    
                    # Aplicação rigorosa da fórmula por faixas
                    qtd_selecionada = len(sel1451)
                    if qtd_selecionada == 0:
                        pts1451 = 0.0
                    elif 1 <= qtd_selecionada <= 5:
                        pts1451 = 1.0
                    elif 6 <= qtd_selecionada <= 10:
                        pts1451 = 3.0
                    else: # acima de 11 opções
                        pts1451 = 5.0
                        
                    st.markdown(f"<span style='color:#28a745; font-weight:bold;'>Opções selecionadas: {qtd_selecionada} | Pontuação: {pts1451:.1f} pts</span>", unsafe_allow_html=True)

                with col2:
                    l1451 = st.text_area("Link/Evidência (14.5.1):", value=d1451.get("link", ""), key=f"l1451_{ano_sel}", height=200)
                    
                    links_1451_atuais = re.findall(r'(https?://[^\s]+)', l1451)
                    if links_1451_atuais:
                        botoes_1451 = " | ".join([f"🔗 [{u}]({u})" for u in links_1451_atuais])
                        st.markdown(f"**Links Ativos:** {botoes_1451}")

                if str(sel1451) != d1451["valor"] or l1451 != d1451["link"]:
                    save_resp("14.5.1", str(sel1451), pts1451, l1451)
                    
                    if links_1451_atuais:
                        links_1451_antigos = re.findall(r'(https?://[^\s]+)', d1451.get("link", ""))
                        if links_1451_atuais != links_1451_antigos:
                            modal_aviso_link("14.5.1", links_1451_atuais)
                        else:
                            st.rerun()
                    else:
                        st.rerun()
                        
                bloco_comentarios("14.5.1", res_data)
                st.markdown('</div>', unsafe_allow_html=True)

    # =========================================================================
    # GRUPO 15 - OUVIDORIA PÚBLICA
    # =========================================================================
    st.markdown("## 🏢 GRUPO 15 - OUVIDORIA PÚBLICA")

    # --- QUESITO 15.0 (RAIZ) ---
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("QUESITO 15.0")
    st.write("**Houve a criação da ouvidoria pública no âmbito do Poder Executivo Municipal?**")
    d150 = res_data.get("15.0", {"valor": None, "pontos": 0.0, "link": ""})
    
    col1, col2 = st.columns([1, 2])
    with col1:
        r150 = st.radio(
            "Selecione 15.0:", 
            ["Sim", "Não"], 
            index=(0 if d150["valor"] == "Sim" else (1 if d150["valor"] == "Não" else None)), 
            key=f"q150_{ano_sel}"
        )
        if r150:
            st.markdown("<span style='color:#28a745; font-weight:bold;'>Pontuação: 0.0 pts</span>", unsafe_allow_html=True)
            
    with col2:
        l150 = st.text_area("Link/Evidência (15.0):", value=d150.get("link", ""), key=f"l150_{ano_sel}", height=100)
        
        links_150_atuais = re.findall(r'(https?://[^\s]+)', l150)
        if links_150_atuais:
            botoes_150 = " | ".join([f"🔗 [{u}]({u})" for u in links_150_atuais])
            st.markdown(f"**Links Ativos:** {botoes_150}")

    if r150 and (r150 != d150["valor"] or l150 != d150["link"]):
        save_resp("15.0", r150, 0.0, l150)
        
        # Cascata de Limpeza se for Não
        if r150 == "Não":
            save_resp("15.1", "", 0.0, "")
            save_resp("15.2", "", 0.0, "")
            save_resp("15.3", "[]", 0.0, "")
            save_resp("15.4", "", 0.0, "")
            save_resp("15.4.1", "[]", 0.0, "")
            save_resp("15.4.2", "", 0.0, "")
            save_resp("15.5", "[]", 0.0, "")
            
        if links_150_atuais:
            links_150_antigos = re.findall(r'(https?://[^\s]+)', d150.get("link", ""))
            if links_150_atuais != links_150_antigos:
                modal_aviso_link("15.0", links_150_atuais)
            else:
                st.rerun()
        else:
            st.rerun()
        
    bloco_comentarios("15.0", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- BLOCO DEPENDENTE DA EXISTÊNCIA DE OUVIDORIA (8 ESPAÇOS DE RECUO) ---
    if r150 == "Sim":
        
        # --- QUESITO 15.1 ---
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 15.1")
        st.write("**Informe o instrumento normativo de criação da ouvidoria pública, número e data da publicação:**")
        st.info("ℹ️ *Caso não esteja disponível na internet, recomendamos anexar o Instrumento Normativo no Sistema de Questionários.*")
        d151 = res_data.get("15.1", {"valor": "", "pontos": 0.0, "link": ""})
        
        col1, col2 = st.columns([1, 2])
        with col1:
            v151 = st.text_input("Instrumento, número e data:", value=d151["valor"], key=f"q151_{ano_sel}")
            st.markdown("<span style='color:#28a745; font-weight:bold;'>Pontuação: 0.0 pts</span>", unsafe_allow_html=True)
            
        with col2:
            l151 = st.text_area("Link/Evidência (15.1):", value=d151.get("link", ""), key=f"l151_{ano_sel}", height=100)
            
            links_151_atuais = re.findall(r'(https?://[^\s]+)', l151)
            if links_151_atuais:
                botoes_151 = " | ".join([f"🔗 [{u}]({u})" for u in links_151_atuais])
                st.markdown(f"**Links Ativos:** {botoes_151}")
        
        if v151 != d151["valor"] or l151 != d151["link"]:
            save_resp("15.1", v151, 0.0, l151)
            
            if links_151_atuais:
                links_151_antigos = re.findall(r'(https?://[^\s]+)', d151.get("link", ""))
                if links_151_atuais != links_151_antigos:
                    modal_aviso_link("15.1", links_151_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
            
        bloco_comentarios("15.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # --- QUESITO 15.2 ---
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 15.2")
        st.write("**Informe a página eletrônica (link na internet) de divulgação do instrumento normativo de criação da Ouvidoria Pública:**")
        st.warning("⚠️ *Se não estiver disponível na internet, insira exatamente o texto **XYZ** no campo abaixo.*")
        d152 = res_data.get("15.2", {"valor": "", "pontos": 0.0, "link": ""})
        
        col1, col2 = st.columns([1, 2])
        with col1:
            v152 = st.text_input("Página eletrônica / Link:", value=d152["valor"], key=f"q152_{ano_sel}")
            st.markdown("<span style='color:#28a745; font-weight:bold;'>Pontuação: 0.0 pts</span>", unsafe_allow_html=True)
            
        with col2:
            links_152_atuais = re.findall(r'(https?://[^\s]+)', v152)
            if links_152_atuais:
                botoes_152 = " | ".join([f"🔗 [{u}]({u})" for u in links_152_atuais])
                st.markdown(f"**Links Ativos:** {botoes_152}")
            else:
                st.markdown("*Nenhum link ativo detectado no campo.*")
        
        if v152 != d152["valor"]:
            save_resp("15.2", v152, 0.0, v152)
            
            if links_152_atuais:
                links_152_antigos = re.findall(r'(https?://[^\s]+)', d152.get("link", ""))
                if links_152_atuais != links_152_antigos:
                    modal_aviso_link("15.2", links_152_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
            
        bloco_comentarios("15.2", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # --- QUESITO 15.3 (CÁLCULO SUBTRATIVO) ---
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 15.3")
        st.write("**Assinale as características que a ouvidoria dispõe para a execução de suas atribuições:**")
        d153 = res_data.get("15.3", {"valor": "[]", "pontos": 0.0, "link": ""})
        
        caracteristicas_obrigatorias = ["Independência", "Isenção", "Acessibilidade", "Transparência", "Confidencialidade"]
        
        col1, col2 = st.columns([1, 2])
        with col1:
            sel153 = []
            for item in caracteristicas_obrigatorias:
                if st.checkbox(item, value=item in d153["valor"], key=f"q153_chk_{item}_{ano_sel}"):
                    sel153.append(item)
            
            if st.checkbox("Outros", value="Outros" in d153["valor"], key=f"q153_chk_outros_{ano_sel}"):
                sel153.append("Outros")
            
            itens_nao_assinalados = sum(1 for x in caracteristicas_obrigatorias if x not in sel153)
            pts153 = -(itens_nao_assinalados * 0.5)
            pts153 = max(pts153, -2.5)
            
            cor_nota = "#28a745" if pts153 == 0.0 else "#dc3545"
            st.markdown(f"<span style='color:{cor_nota}; font-weight:bold;'>Pontuação: {pts153:.2f} pts (Perda: -{itens_nao_assinalados * 0.5:.1f})</span>", unsafe_allow_html=True)
            
        with col2:
            l153 = st.text_area("Link/Evidência (15.3):", value=d153.get("link", ""), key=f"l153_{ano_sel}", height=180)
            
            links_153_atuais = re.findall(r'(https?://[^\s]+)', l153)
            if links_153_atuais:
                botoes_153 = " | ".join([f"🔗 [{u}]({u})" for u in links_153_atuais])
                st.markdown(f"**Links Ativos:** {botoes_153}")
            
        if str(sel153) != d153["valor"] or l153 != d153["link"]:
            save_resp("15.3", str(sel153), pts153, l153)
            
            if links_153_atuais:
                links_153_antigos = re.findall(r'(https?://[^\s]+)', d153.get("link", ""))
                if links_153_atuais != links_153_antigos:
                    modal_aviso_link("15.3", links_153_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
            
        bloco_comentarios("15.3", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # --- QUESITO 15.4 ---
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 15.4")
        st.write("**A ouvidoria elaborou Relatório de Gestão do exercício de 2025 contendo a consolidação das manifestações encaminhadas pelos usuários de serviços públicos, e com base nelas, apontou falhas e sugeriu melhorias em sua prestação?**")
        d154 = res_data.get("15.4", {"valor": None, "pontos": 0.0, "link": ""})
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r154 = st.radio(
                "Selecione 15.4:", 
                ["Sim", "Não"], 
                index=(0 if d154["valor"] == "Sim" else (1 if d154["valor"] == "Não" else None)), 
                key=f"q154_{ano_sel}"
            )
            pts154 = 0.0 if r154 == "Sim" else (-10.0 if r154 == "Não" else 0.0)
            if r154:
                cor_nota = "#28a745" if pts154 == 0.0 else "#dc3545"
                st.markdown(f"<span style='color:{cor_nota}; font-weight:bold;'>Pontuação: {pts154:.1f} pts</span>", unsafe_allow_html=True)
                
        with col2:
            l154 = st.text_area("Link/Evidência (15.4):", value=d154.get("link", ""), key=f"l154_{ano_sel}", height=100)
            
            links_154_atuais = re.findall(r'(https?://[^\s]+)', l154)
            if links_154_atuais:
                botoes_154 = " | ".join([f"🔗 [{u}]({u})" for u in links_154_atuais])
                st.markdown(f"**Links Ativos:** {botoes_154}")

        if r154 and (r154 != d154["valor"] or l154 != d154["link"]):
            save_resp("15.4", r154, pts154, l154)
            
            # Cascata de Limpeza interna se mudar para Não
            if r154 == "Não":
                save_resp("15.4.1", "[]", 0.0, "")
                save_resp("15.4.2", "", 0.0, "")
                
            if links_154_atuais:
                links_154_antigos = re.findall(r'(https?://[^\s]+)', d154.get("link", ""))
                if links_154_atuais != links_154_antigos:
                    modal_aviso_link("15.4", links_154_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
            
        bloco_comentarios("15.4", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # --- SUBNÍVEIS DO RELATÓRIO DE GESTÃO (12 ESPAÇOS DE RECUO) ---
        if r154 == "Sim":
            
            # --- QUESITO 15.4.1 (CÁLCULO SUBTRATIVO) ---
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader("QUESITO 15.4.1")
            st.write("**Assinale as informações constantes nos relatórios gerenciais elaborados pela ouvidoria:**")
            d1541 = res_data.get("15.4.1", {"valor": "[]", "pontos": 0.0, "link": ""})
            
            itens_obrigatorios_1541 = [
                "Número de manifestações recebidas no exercício anterior",
                "Motivos das Manifestações",
                "Análise dos Pontos recorrentes",
                "Providências adotadas pela administração pública nas soluções apresentadas"
            ]
            
            col1, col2 = st.columns([1, 2])
            with col1:
                sel1541 = []
                for item in itens_obrigatorios_1541:
                    if st.checkbox(item, value=item in d1541["valor"], key=f"q1541_chk_{item}_{ano_sel}"):
                        sel1541.append(item)
                        
                ausentes_1541 = sum(1 for x in itens_obrigatorios_1541 if x not in sel1541)
                pts1541 = -(ausentes_1541 * 2.5)
                
                cor_nota = "#28a745" if pts1541 == 0.0 else "#dc3545"
                st.markdown(f"<span style='color:{cor_nota}; font-weight:bold;'>Pontuação: {pts1541:.1f} pts (Perda: -{ausentes_1541 * 2.5:.1f})</span>", unsafe_allow_html=True)
                
            with col2:
                l1541 = st.text_area("Link/Evidência (15.4.1):", value=d1541.get("link", ""), key=f"l1541_{ano_sel}", height=150)
                
                links_1541_atuais = re.findall(r'(https?://[^\s]+)', l1541)
                if links_1541_atuais:
                    botoes_1541 = " | ".join([f"🔗 [{u}]({u})" for u in links_1541_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_1541}")
                
            if str(sel1541) != d1541["valor"] or l1541 != d1541["link"]:
                save_resp("15.4.1", str(sel1541), pts1541, l1541)
                
                if links_1541_atuais:
                    links_1541_antigos = re.findall(r'(https?://[^\s]+)', d1541.get("link", ""))
                    if links_1541_atuais != links_1541_antigos:
                        modal_aviso_link("15.4.1", links_1541_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
                
            bloco_comentarios("15.4.1", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

            # --- QUESITO 15.4.2 (GATILHO DE STRING PUNITIVA) ---
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader("QUESITO 15.4.2")
            st.write("**Informe a página eletrônica (link na internet) de divulgação do Relatório de Gestão do exercício de 2025:**")
            st.warning("⚠️ *Se não estiver disponível na internet, insira explicitamente o texto **XYZ** para anexar manualmente. (Atenção: digitar XYZ aplica uma penalidade de -10 pontos).*")
            d1542 = res_data.get("15.4.2", {"valor": "", "pontos": 0.0, "link": ""})
            
            col1, col2 = st.columns([1, 2])
            with col1:
                v1542 = st.text_input("Página eletrônica (Link ou XYZ):", value=d1542["valor"], key=f"q1542_{ano_sel}")
                pts1542 = -10.0 if v1542.strip() == "XYZ" else 0.0
                
                if v1542:
                    cor_nota = "#28a745" if pts1542 == 0.0 else "#dc3545"
                    st.markdown(f"<span style='color:{cor_nota}; font-weight:bold;'>Pontuação: {pts1542:.1f} pts</span>", unsafe_allow_html=True)
                
            with col2:
                links_1542_atuais = re.findall(r'(https?://[^\s]+)', v1542)
                if links_1542_atuais:
                    botoes_1542 = " | ".join([f"🔗 [{u}]({u})" for u in links_1542_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_1542}")
                else:
                    st.markdown("*Nenhum link ativo detectado no campo.*")
            
            if v1542 != d1542["valor"]:
                save_resp("15.4.2", v1542, pts1542, v1542)
                
                if links_1542_atuais:
                    links_1542_antigos = re.findall(r'(https?://[^\s]+)', d1542.get("link", ""))
                    if links_1542_atuais != links_1542_antigos:
                        modal_aviso_link("15.4.2", links_1542_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
                
            bloco_comentarios("15.4.2", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

        # --- QUESITO 15.5 (VOLTA PARA 8 ESPAÇOS) ---
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 15.5")
        st.write("**Assinale as iniciativas de divulgação e mobilização social das ouvidorias:**")
        d155 = res_data.get("15.5", {"valor": "[]", "pontos": 0.0, "link": ""})
        
        itens_penalizaveis_155 = [
            "Link da página eletrônica da ouvidoria no sítio da Prefeitura Municipal",
            "Utilização de outras plataformas digitais para a divulgação da missão, do modo de trabalho das ouvidorias e incentivando a participação popular. Ex.: instagram, facebook, twiter etc."
        ]
        
        itens_neutros_155 = [
            "Realização de palestras para grupos e institutions. Ex.: escolas, igrejas, associações civis, outros grupos organizados etc.",
            "Realização de eventos que estimulem a participação e coleta das demandas sociais. Ex.: realização de audiências públicas para divulgação dos trabalhos desempenhados pela ouvidoria e ouvir as demandas da população."
        ]
        
        col1, col2 = st.columns([1, 2])
        with col1:
            sel155 = []
            
            # Renderiza itens com penalidade
            for idx, item in enumerate(itens_penalizaveis_155):
                if st.checkbox(item, value=item in d155["valor"], key=f"q155_chk_pen_{idx}_{ano_sel}"):
                    sel155.append(item)
            
            # Renderiza itens neutros
            for idx, item in enumerate(itens_neutros_155):
                if st.checkbox(item, value=item in d155["valor"], key=f"q155_chk_neu_{idx}_{ano_sel}"):
                    sel155.append(item)
            
            # Opção neutra complementar
            if st.checkbox("Outras", value="Outras" in d155["valor"], key=f"q155_chk_outras_{ano_sel}"):
                sel155.append("Outras")
                
            ausentes_155 = sum(1 for x in itens_penalizaveis_155 if x not in sel155)
            pts155 = -(ausentes_155 * 0.5)
            
            cor_nota = "#28a745" if pts155 == 0.0 else "#dc3545"
            st.markdown(f"<span style='color:{cor_nota}; font-weight:bold;'>Pontuação: {pts155:.2f} pts (Perda: -{ausentes_155 * 0.5:.1f})</span>", unsafe_allow_html=True)
            
        with col2:
            l155 = st.text_area("Link/Evidência (15.5):", value=d155.get("link", ""), key=f"l155_{ano_sel}", height=200)
            
            links_155_atuais = re.findall(r'(https?://[^\s]+)', l155)
            if links_155_atuais:
                botoes_155 = " | ".join([f"🔗 [{u}]({u})" for u in links_155_atuais])
                st.markdown(f"**Links Ativos:** {botoes_155}")
                
        if str(sel155) != d155["valor"] or l155 != d155["link"]:
            save_resp("15.5", str(sel155), pts155, l155)
            
            if links_155_atuais:
                links_155_antigos = re.findall(r'(https?://[^\s]+)', d155.get("link", ""))
                if links_155_atuais != links_155_antigos:
                    modal_aviso_link("15.5", links_155_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
                
        bloco_comentarios("15.5", res_data)
        st.markdown('</div>', unsafe_allow_html=True)
            
 # =========================================================================
    # GRUPO 16 - CARTA DE SERVIÇOS AO USUÁRIO
    # =========================================================================

    # --- QUESITO 16.0 ---
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("QUESITO 16.0")
    st.write("**A prefeitura elaborou a \"Carta de Serviço ao Usuário\", que trata dos serviços prestados pelos seus órgãos e entidades, as formas de acesso a esses serviços e seus compromissos e padrões de qualidade de atendimento ao público, conforme artigo 7°, §§ 2º e 3º, da Lei Federal nº 13.460/2017?**")
    d160 = res_data.get("16.0", {"valor": None, "pontos": 0.0, "link": ""})
    opc160 = {"Sim – 04": 4.0, "Não – 00": 0.0}
    
    col1, col2 = st.columns([1, 2])
    with col1:
        r160 = st.radio(
            "Selecione 16.0:", 
            list(opc160.keys()), 
            index=(list(opc160.keys()).index(d160["valor"]) if d160["valor"] in opc160 else None), 
            key=f"q160_{ano_sel}"
        )
        if r160:
            cor_nota = "#28a745" if opc160[r160] > 0 else "#dc3545"
            st.markdown(f"<span style='color:{cor_nota}; font-weight:bold;'>Pontuação: {opc160[r160]:.1f} pts</span>", unsafe_allow_html=True)
            
    with col2:
        l160 = st.text_area("Link/Evidência (16.0):", value=d160.get("link", ""), key=f"l160_{ano_sel}", height=100)
        
        links_160_atuais = re.findall(r'(https?://[^\s]+)', l160)
        if links_160_atuais:
            botoes_160 = " | ".join([f"🔗 [{u}]({u})" for u in links_160_atuais])
            st.markdown(f"**Links Ativos:** {botoes_160}")

    if r160 and (r160 != d160["valor"] or l160 != d160["link"]):
        save_resp("16.0", r160, opc160[r160], l160)
        
        # Cascata de Limpeza se mudar para Não
        if "Não" in r160:
            save_resp("16.1", "XYZ", 0.0, "")
            
        if links_160_atuais:
            links_160_antigos = re.findall(r'(https?://[^\s]+)', d160.get("link", ""))
            if links_160_atuais != links_160_antigos:
                modal_aviso_link("16.0", links_160_atuais)
            else:
                st.rerun()
        else:
            st.rerun()
        
    bloco_comentarios("16.0", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO CONDICIONAL 16.1 (ENTRA NO RECUO DE 8 ESPAÇOS) ---
    if r160 and "Sim" in r160:
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 16.1")
        st.write("**Informe a página eletrônica (link na internet) de divulgação da \"Carta de Serviço ao Usuário\":**")
        st.warning("⚠️ *Se não estiver disponível, insira exatamente o texto **XYZ**.*")
        d161 = res_data.get("16.1", {"valor": "", "pontos": 0.0, "link": ""})
        
        col1, col2 = st.columns([1, 2])
        with col1:
            v161 = st.text_input("Página eletrônica (Link ou XYZ):", value=d161["valor"], key=f"q161_{ano_sel}")
            pts161 = 2.0 if v161 and v161 != "XYZ" else 0.0
            
            if v161:
                cor_nota = "#28a745" if pts161 > 0 else "#dc3545"
                st.markdown(f"<span style='color:{cor_nota}; font-weight:bold;'>Pontuação: {pts161:.1f} pts</span>", unsafe_allow_html=True)
                
        with col2:
            links_161_atuais = re.findall(r'(https?://[^\s]+)', v161)
            if links_161_atuais:
                botoes_161 = " | ".join([f"🔗 [{u}]({u})" for u in links_161_atuais])
                st.markdown(f"**Links Ativos:** {botoes_161}")
            else:
                st.markdown("*Nenhum link ativo detectado no campo.*")
                
        if v161 != d161["valor"]:
            save_resp("16.1", v161, pts161, v161)
            
            if links_161_atuais:
                links_161_antigos = re.findall(r'(https?://[^\s]+)', d161.get("link", ""))
                if links_161_atuais != links_161_antigos:
                    modal_aviso_link("16.1", links_161_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
                
        bloco_comentarios("16.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True) 

    # --- QUESITO 16.2 (VOLTA PARA A RAIZ DE 4 ESPAÇOS) ---
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("QUESITO 16.2")
    st.write("**A 'Carta de Serviço ao Usuário' está atualizada?**")
    d162 = res_data.get("16.2", {"valor": None, "pontos": 0.0, "link": ""})
    
    map_opcoes_162 = {"Sim – 02": "Sim", "Não – 00": "Não"}
    inv_map_162 = {"Sim": "Sim – 02", "Não": "Não – 00"}
    idx_162 = list(map_opcoes_162.keys()).index(inv_map_162[d162["valor"]]) if d162["valor"] in inv_map_162 else None
    
    col1, col2 = st.columns([1, 2])
    with col1:
        r162_sel = st.radio("Selecione 16.2:", list(map_opcoes_162.keys()), index=idx_162, key=f"q162_{ano_sel}")
        r162 = map_opcoes_162[r162_sel] if r162_sel else None
        pts162 = 2.0 if r162 == "Sim" else 0.0
        
        if r162:
            cor_nota = "#28a745" if pts162 > 0 else "#dc3545"
            st.markdown(f"<span style='color:{cor_nota}; font-weight:bold;'>Pontuação: {pts162:.1f} pts</span>", unsafe_allow_html=True)
            
    with col2:
        l162 = st.text_area("Link/Evidência (16.2):", value=d162.get("link", ""), key=f"l162_{ano_sel}", height=100)
        
        links_162_atuais = re.findall(r'(https?://[^\s]+)', l162)
        if links_162_atuais:
            botoes_162 = " | ".join([f"🔗 [{u}]({u})" for u in links_162_atuais])
            st.markdown(f"**Links Ativos:** {botoes_162}")

    if r162 and (r162 != d162["valor"] or l162 != d162["link"]):
        save_resp("16.2", r162, pts162, l162)
        
        if links_162_atuais:
            links_162_antigos = re.findall(r'(https?://[^\s]+)', d162.get("link", ""))
            if links_162_atuais != links_162_antigos:
                modal_aviso_link("16.2", links_162_atuais)
            else:
                st.rerun()
        else:
            st.rerun()
        
    bloco_comentarios("16.2", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 16.3 ---
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("QUESITO 16.3")
    st.write("**A prefeitura regulamentou a operacionalização da Carta de Serviços ao Usuário, conforme o artigo 7°, § 5°, da Lei Federal n° 13.460/2017?**")
    d163 = res_data.get("16.3", {"valor": None, "pontos": 0.0, "link": ""})
    
    map_opcoes_163 = {"Sim – 04": "Sim", "Não – 00": "Não"}
    inv_map_163 = {"Sim": "Sim – 04", "Não": "Não – 00"}
    idx_163 = list(map_opcoes_163.keys()).index(inv_map_163[d163["valor"]]) if d163["valor"] in inv_map_163 else None
    
    col1, col2 = st.columns([1, 2])
    with col1:
        r163_sel = st.radio("Selecione 16.3:", list(map_opcoes_163.keys()), index=idx_163, key=f"q163_{ano_sel}")
        r163 = map_opcoes_163[r163_sel] if r163_sel else None
        pts163 = 4.0 if r163 == "Sim" else 0.0
        
        if r163:
            cor_nota = "#28a745" if pts163 > 0 else "#dc3545"
            st.markdown(f"<span style='color:{cor_nota}; font-weight:bold;'>Pontuação: {pts163:.1f} pts</span>", unsafe_allow_html=True)
            
    with col2:
        l163 = st.text_area("Link/Evidência (16.3):", value=d163.get("link", ""), key=f"l163_{ano_sel}", height=100)
        
        links_163_atuais = re.findall(r'(https?://[^\s]+)', l163)
        if links_163_atuais:
            botoes_163 = " | ".join([f"🔗 [{u}]({u})" for u in links_163_atuais])
            st.markdown(f"**Links Ativos:** {botoes_163}")

    if r163 and (r163 != d163["valor"] or l163 != d163["link"]):
        save_resp("16.3", r163, pts163, l163)
        
        # Cascata de Limpeza interna se mudar para Não
        if r163 == "Não":
            save_resp("16.3.1", "", 0.0, "")
            save_resp("16.3.2", "", 0.0, "")
            
        if links_163_atuais:
            links_163_antigos = re.findall(r'(https?://[^\s]+)', d163.get("link", ""))
            if links_163_atuais != links_163_antigos:
                modal_aviso_link("16.3", links_163_atuais)
            else:
                st.rerun()
        else:
            st.rerun()
        
    bloco_comentarios("16.3", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- SUBNÍVEIS CONDICIONAIS (SÓ ABRE SE 16.3 FOR SIM - RECUO DE 8 ESPAÇOS) ---
    if r163 == "Sim":
        
        # --- QUESITO 16.3.1 ---
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 16.3.1")
        st.write("**Informe o instrumento normativo que regulamentou a 'Carta de Serviço ao Usuário', Número e Data da publicação:**")
        st.info("ℹ️ *Caso não esteja disponível na internet, recomendamos anexar o Instrumento Normativo de regulamentação no Sistema de Questionários.*")
        d1631 = res_data.get("16.3.1", {"valor": "", "pontos": 0.0, "link": ""})
        
        col1, col2 = st.columns([1, 2])
        with col1:
            v1631 = st.text_input("Instrumento normativo, número e data:", value=d1631["valor"], key=f"q1631_{ano_sel}")
            st.markdown("<span style='color:#28a745; font-weight:bold;'>Pontuação: 0.0 pts</span>", unsafe_allow_html=True)
            
        with col2:
            l1631 = st.text_area("Link/Evidência (16.3.1):", value=d1631.get("link", ""), key=f"l1631_{ano_sel}", height=100)
            
            links_1631_atuais = re.findall(r'(https?://[^\s]+)', l1631)
            if links_1631_atuais:
                botoes_1631 = " | ".join([f"🔗 [{u}]({u})" for u in links_1631_atuais])
                st.markdown(f"**Links Ativos:** {botoes_1631}")
        
        if v1631 != d1631["valor"] or l1631 != d1631["link"]:
            save_resp("16.3.1", v1631, 0.0, l1631)
            
            if links_1631_atuais:
                links_1631_antigos = re.findall(r'(https?://[^\s]+)', d1631.get("link", ""))
                if links_1631_atuais != links_1631_antigos:
                    modal_aviso_link("16.3.1", links_1631_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
            
        bloco_comentarios("16.3.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # --- QUESITO 16.3.2 ---
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 16.3.2")
        st.write("**Informe a página eletrônica (link na internet) de divulgação do instrumento normativo que regulamentou a 'Carta de Serviço ao Usuário':**")
        st.warning("⚠️ *Se não estiver disponível na internet, insira exatamente o texto **XYZ** no campo abaixo.*")
        d1632 = res_data.get("16.3.2", {"valor": "", "pontos": 0.0, "link": ""})
        
        col1, col2 = st.columns([1, 2])
        with col1:
            v1632 = st.text_input("Página eletrônica (Link ou XYZ) do instrumento:", value=d1632["valor"], key=f"q1632_{ano_sel}")
            st.markdown("<span style='color:#28a745; font-weight:bold;'>Pontuação: 0.0 pts</span>", unsafe_allow_html=True)
            
        with col2:
            links_1632_atuais = re.findall(r'(https?://[^\s]+)', v1632)
            if links_1632_atuais:
                botoes_1632 = " | ".join([f"🔗 [{u}]({u})" for u in links_1632_atuais])
                st.markdown(f"**Links Ativos:** {botoes_1632}")
            else:
                st.markdown("*Nenhum link ativo detectado no campo.*")
        
        if v1632 != d1632["valor"]:
            save_resp("16.3.2", v1632, 0.0, v1632)
            
            if links_1632_atuais:
                links_1632_antigos = re.findall(r'(https?://[^\s]+)', d1632.get("link", ""))
                if links_1632_atuais != links_1632_antigos:
                    modal_aviso_link("16.3.2", links_1632_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
            
        bloco_comentarios("16.3.2", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

  # =========================================================================
    # GRUPO 17 - CONSELHO DE USUÁRIOS
    # =========================================================================
    st.markdown("## 👥 GRUPO 17 - CONSELHO DE USUÁRIOS")

    # --- QUESITO 17.0 (RAIZ DO BLOCO) ---
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("QUESITO 17.0")
    st.write("**A prefeitura regulamentou e instituiu o Conselho de Usuários, nos termos definidos nos artigos 18 a 21 da Lei Federal nº 13.460/2017?**")
    d170 = res_data.get("17.0", {"valor": None, "pontos": 0.0, "link": ""})
    
    map_opcoes_170 = {"Sim – 04": "Sim", "Não – 00": "Não"}
    inv_map_170 = {"Sim": "Sim – 04", "Não": "Não – 00"}
    idx_170 = list(map_opcoes_170.keys()).index(inv_map_170[d170["valor"]]) if d170["valor"] in inv_map_170 else None

    col1, col2 = st.columns([1, 2])
    with col1:
        r170_sel = st.radio(
            "Selecione 17.0:", 
            list(map_opcoes_170.keys()), 
            index=idx_170, 
            key=f"q170_final_radio_{ano_sel}"
        )
        r170 = map_opcoes_170[r170_sel] if r170_sel else None
        pts170 = 4.0 if r170 == "Sim" else 0.0
        
        if r170:
            cor_nota = "#28a745" if pts170 > 0 else "#dc3545"
            st.markdown(f"<span style='color:{cor_nota}; font-weight:bold;'>Pontuação: {pts170:.1f} pts</span>", unsafe_allow_html=True)
            
    with col2:
        l170 = st.text_area("Link/Evidência (17.0):", value=d170.get("link", ""), key=f"l170_final_txt_{ano_sel}", height=100)
        
        links_170_atuais = re.findall(r'(https?://[^\s]+)', l170)
        if links_170_atuais:
            botoes_170 = " | ".join([f"🔗 [{u}]({u})" for u in links_170_atuais])
            st.markdown(f"**Links Ativos:** {botoes_170}")

    if r170 and (r170 != d170["valor"] or l170 != d170["link"]):
        save_resp("17.0", r170, pts170, l170)
        
        # Cascata de Limpeza se mudar para Não
        if r170 == "Não":
            save_resp("17.1", "", 0.0, "")
            save_resp("17.2", "", 0.0, "")
            
        if links_170_atuais:
            links_170_antigos = re.findall(r'(https?://[^\s]+)', d170.get("link", ""))
            if links_170_atuais != links_170_antigos:
                modal_aviso_link("17.0", links_170_atuais)
            else:
                st.rerun()
        else:
            st.rerun()
        
    bloco_comentarios("17.0_exclusivo_g17", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- SUBNÍVEIS CONDICIONAIS (SÓ ABRE SE 17.0 FOR SIM) ---
    if r170 == "Sim":
        
        # --- QUESITO 17.1 ---
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 17.1")
        st.write("**Informe o instrumento normativo que regulamentou os Conselhos de Usuários, Número e Data da publicação:**")
        st.info("ℹ️ *Caso não esteja disponível na internet, recomendamos anexar o Instrumento Normativo no Sistema de Questionários.*")
        d171 = res_data.get("17.1", {"valor": "", "pontos": 0.0, "link": ""})
        
        col1, col2 = st.columns([1, 2])
        with col1:
            v171 = st.text_input("Instrumento normativo, número e data:", value=d171["valor"], key=f"q171_final_input_{ano_sel}")
            st.markdown("<span style='color:#28a745; font-weight:bold;'>Pontuação: 0.0 pts</span>", unsafe_allow_html=True)
            
        with col2:
            l171 = st.text_area("Link/Evidência (17.1):", value=d171.get("link", ""), key=f"l171_final_input_{ano_sel}", height=100)
            
            links_171_atuais = re.findall(r'(https?://[^\s]+)', l171)
            if links_171_atuais:
                botoes_171 = " | ".join([f"🔗 [{u}]({u})" for u in links_171_atuais])
                st.markdown(f"**Links Ativos:** {botoes_171}")
        
        if v171 != d171["valor"] or l171 != d171["link"]:
            save_resp("17.1", v171, 0.0, l171)
            
            if links_171_atuais:
                links_171_antigos = re.findall(r'(https?://[^\s]+)', d171.get("link", ""))
                if links_171_atuais != links_171_antigos:
                    modal_aviso_link("17.1", links_171_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
            
        bloco_comentarios("17.1_exclusivo_g17", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # --- QUESITO 17.2 ---
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 17.2")
        st.write("**Informe a página eletrônica (link na internet) de divulgação da regulamentação do Conselho de Usuários:**")
        st.warning("⚠️ *Se não estiver disponível na internet, insira exatamente o texto **XYZ** no campo abaixo.*")
        d172 = res_data.get("17.2", {"valor": "", "pontos": 0.0, "link": ""})
        
        col1, col2 = st.columns([1, 2])
        with col1:
            v172 = st.text_input("Página eletrônica (Link ou XYZ):", value=d172["valor"], key=f"q172_final_input_{ano_sel}")
            st.markdown("<span style='color:#28a745; font-weight:bold;'>Pontuação: 0.0 pts</span>", unsafe_allow_html=True)
            
        with col2:
            links_172_atuais = re.findall(r'(https?://[^\s]+)', v172)
            if links_172_atuais:
                botoes_172 = " | ".join([f"🔗 [{u}]({u})" for u in links_172_atuais])
                st.markdown(f"**Links Ativos:** {botoes_172}")
            else:
                st.markdown("*Nenhum link ativo detectado no campo.*")
        
        if v172 != d172["valor"]:
            save_resp("17.2", v172, 0.0, v172)
            
            if links_172_atuais:
                links_172_antigos = re.findall(r'(https?://[^\s]+)', d172.get("link", ""))
                if links_172_atuais != links_172_antigos:
                    modal_aviso_link("17.2", links_172_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
            
        bloco_comentarios("17.2_exclusivo_g17", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

    # =========================================================================
    # GRUPO 8 - PLANO DIRETOR
    # =========================================================================
    st.markdown("## 🏗️ GRUPO 8 - PLANO DIRETOR")
    from datetime import datetime, date

    # --- QUESITO 18.0 (RAIZ DO BLOCO) ---
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("QUESITO 18.0")
    st.write("**O município elaborou Plano Diretor conforme Lei nº 10.257/01?**")
    d180 = res_data.get("18.0", {"valor": None, "pontos": 0.0, "link": ""})
    
    col1, col2 = st.columns([1, 2])
    with col1:
        opcoes_80 = ["Sim", "Não", "Não se aplica"]
        idx_80 = opcoes_80.index(d80["valor"]) if d80["valor"] in opcoes_80 else None

        r80 = st.radio(
            "Selecione 8.0:", 
            opcoes_80, 
            index=idx_80, 
            key=f"q80_radio_final_{ano_sel}"
        )
        st.markdown("<span style='color:#28a745; font-weight:bold;'>Pontuação: 0.0 pts</span>", unsafe_allow_html=True)
        
    with col2:
        l80 = st.text_area("Link/Evidência (8.0):", value=d80.get("link", ""), key=f"l80_txt_final_{ano_sel}", height=100)
        
        links_80_atuais = re.findall(r'(https?://[^\s]+)', l80)
        if links_80_atuais:
            botoes_80 = " | ".join([f"🔗 [{u}]({u})" for u in links_80_atuais])
            st.markdown(f"**Links Ativos:** {botoes_80}")

    if r80 and (r80 != d80["valor"] or l80 != d80["link"]):
        save_resp("18.0", r80, 0.0, l80)  # O quesito 8.0 pontua a partir da condicional abaixo
        
        if r80 != "Sim":
            save_resp("18.1", "", 0.0, "")  # Limpa o subnível se não for 'Sim'
            
        if links_80_atuais:
            links_80_antigos = re.findall(r'(https?://[^\s]+)', d80.get("link", ""))
            if links_80_atuais != links_80_antigos:
                modal_aviso_link("18.0", links_80_atuais)
            else:
                st.rerun()
        else:
            st.rerun()
        
    bloco_comentarios("18.0_exclusivo_g8", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 18.1 - ATUALIZAÇÃO DO PLANO DIRETOR ---
    if r80 == "Sim":
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 18.1")
        st.write("**Informe a data da última atualização do Plano Diretor:**")

        st.info("""
        **Fórmula de Cálculo:**
        * 📅 **Até 31/12/2015:** -10 pontos (Perde 10 pontos).
        * 📅 **A partir de 01/01/2016:** 00 ponto.
        """)

        d181 = res_data.get("18.1", {"valor": None, "pontos": 0.0, "link": ""})

        col_d181, col_j181 = st.columns([1, 2])
        with col_d181:
            try:
                dt_i_181 = datetime.strptime(d181["valor"], '%Y-%m-%d').date() if d181["valor"] else date.today()
            except:
                dt_i_181 = date.today()

            data_sel_181 = st.date_input(
                "Data da última atualização:",
                value=dt_i_181,
                key=f"dt181_{ano_sel}",
                format="DD/MM/YYYY"
            )

            pts181 = -10.0 if data_sel_181 <= date(2015, 12, 31) else 0.0
            data_br_181 = data_sel_181.strftime('%d/%m/%Y')
            
            cor_nota = "#dc3545" if pts181 == -10.0 else "#28a745"
            st.markdown(f"<span style='color:{cor_nota}; font-weight:bold;'>Pontuação: {pts181:.1f} pts ({data_br_181})</span>", unsafe_allow_html=True)

        with col_j181:
            l181 = st.text_area("Justificativa / Link de Evidência (18.1):", value=d181["link"], key=f"l181_{ano_sel}", height=120)
            
            links_181_atuais = re.findall(r'(https?://[^\s]+)', l181)
            if links_181_atuais:
                botoes_181 = " | ".join([f"🔗 [{u}]({u})" for u in links_181_atuais])
                st.markdown(f"**Links Ativos:** {botoes_181}")

        if d181["valor"] is not None or l181 != "":
            if str(data_sel_181) != d181["valor"] or l181 != d181["link"]:
                save_resp("18.1", str(data_sel_181), pts181, l181)
                
                if links_181_atuais:
                    links_181_antigos = re.findall(r'(https?://[^\s]+)', d181.get("link", ""))
                    if links_181_atuais != links_181_antigos:
                        modal_aviso_link("18.1", links_181_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()

        bloco_comentarios("18.1_exclusivo_g8", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- QUESITO 19.0 (ENCERRAMENTO/FEEDBACK) ---
    st.markdown('---', unsafe_allow_html=True)
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("QUESITO 19.0")
    st.write("**Gostaria de registrar suas impressões, comentários e sugestões a respeito do presente questionário?**")

    d190 = res_data.get("19.0", {"valor": "", "pontos": 0.0, "link": ""})

    col_feed1, col_feed2 = st.columns([1, 2])
    with col_feed1:
        st.markdown("<span style='color:#28a745; font-weight:bold;'>Quesito Informativo (Sem atribuição de nota)</span>", unsafe_allow_html=True)
        
    with col_feed2:
        l190 = st.text_area(
            "Utilize o espaço abaixo para registrar suas observações:",
            value=d190["link"] if d190["link"] else "",
            key=f"l190_text_{ano_sel}",
            placeholder="Digite aqui suas observações, críticas ou sugestões...",
            height=140
        )
        
        links_190_atuais = re.findall(r'(https?://[^\s]+)', l190)
        if links_190_atuais:
            botoes_190 = " | ".join([f"🔗 [{u}]({u})" for u in links_190_atuais])
            st.markdown(f"**Links Detectados:** {botoes_190}")

    if l190 != d190["link"]:
        save_resp("19.0", l190, 0.0, l190)
        
        if links_190_atuais:
            links_190_antigos = re.findall(r'(https?://[^\s]+)', d190.get("link", ""))
            if links_190_atuais != links_190_antigos:
                modal_aviso_link("19.0", links_190_atuais)
            else:
                st.rerun()
        else:
            st.rerun()

    bloco_comentarios("19.0_exclusivo_g19", res_data)
    st.markdown('</div>', unsafe_allow_html=True)
