import streamlit as st
import sqlite3
import json
from io import BytesIO
from datetime import datetime, date

# Bibliotecas para o PDF (Requer: pip install reportlab)
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle  # <-- Garanta que ele está aqui em cima!
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

# Bibliotecas para os Gráficos (Requer: pip install plotly)
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# =============================================================================
# CONSTANTES GLOBAIS - IAMB
# =============================================================================

PONTUACOES_MAX = {
    "1.1.2": 20,
    "1.1.3": 5,
    "1.2": 20,
    "2.0": 10,
    "2.1": 50,
    "3.0": 10,
    "3.1": 20,
    "4.0": 20,
    "5.2.1": 20,
    "6.0": 20,
    "6.1": 50,
    "6.2": 25,
    "7.2": 2,
    "7.3": 10,
    "7.3.1": 20,
    "7.4": 10,
    "7.4.1": 20,
    "7.5": 30,
    "7.7": 30,
    "7.8": 20,
    "7.8.1": 50,
    "7.9": 3,
    "8.2": 2,
    "8.3": 10,
    "8.4": 20,
    "8.4.1": 10,
    "8.4.2": 30,
    "8.4.3": 50,
    "9.2": 100,
    "9.3": 5,
    "9.3.1": 5,
    "11.2": 2,
    "11.3": 30,
    "11.3.2": 20,
    "11.3.3": 40,
    "11.5": 10,
    "12.1": 54,
    "14.3": 30,
    "15": 2,
    "15.1": 3,
    "A4.1.1": 90,
    "A4.1.2": 20,
    "A4.1.3": 22,
    "A6": 5
}

CATEGORIAS_MAP = {
    "planejamento":   {"label": "Planejamento",    "qids": ["1.1.2", "1.1.3", "1.2"]},
    "gestao_fiscal":  {"label": "Gestão Fiscal",   "qids": ["2.0", "2.1"]},
    "educacao":       {"label": "Educação",         "qids": ["3.0", "3.1"]},
    "saude":          {"label": "Saúde",            "qids": ["4.0"]},
    "meio_ambiente":  {"label": "Meio Ambiente",    "qids": ["5.2.1", "6.0", "6.1", "6.2", "14.3"]},
    "governanca_ti":  {"label": "Governança TI",    "qids": ["7.2", "7.3", "7.3.1", "7.4", "7.4.1", "7.5", "7.7", "7.8", "7.8.1", "7.9"]},
    "transparencia":  {"label": "Transparência",    "qids": ["8.2", "8.3", "8.4", "8.4.1", "8.4.2", "8.4.3", "9.2", "9.3", "9.3.1"]},
    "outros":         {"label": "Outros",           "qids": ["11.2", "11.3", "11.3.2", "11.3.3", "11.5", "12.1", "15", "15.1", "A4.1.1", "A4.1.2", "A4.1.3", "A6"]},
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
# 1. FUNÇÕES DE APOIO E BANCO DE DADOS (IEGM - I-AMB)
# =============================================================================
import sqlite3
import json
import datetime
import re
import ast
import streamlit as st

def get_connection():
    # Conecta no banco de dados isolado e específico do I-AMB
    return sqlite3.connect("dados_iamb.db", check_same_thread=False)

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
        
        # 2. PRAGMA para checar quais colunas realmente existem no arquivo físico do banco do I-AMB
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
        timestamp_atual = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
            st.error(f"Erro operacional no banco do I-AMB: {e}")
    except Exception as e:
        st.error(f"Erro ao salvar {qid}: {e}")

def bloco_comentarios(questao_id, res_data, sufixo=None):
    """
    Gera o diálogo interno avançado com histórico retrátil, status em realtime
    e controle individual de remoção por lixeira para o módulo I-AMB.
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
                        "data": datetime.datetime.now().strftime("%d/%m/%Y %H:%M"),
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
# 2. INTERFACE E FORMULÁRIO (SIDEBAR E ESTRUTURA GLOBAL)
# =============================================================================

def render_sidebar():
    st.sidebar.title("🌿 Painel i-AMB")
    anos = [2023, 2024, 2025, 2026, 2027, 2028, 2029, 2030]
    ano_sel = st.sidebar.selectbox("Ano de Referência:", anos, key="ano_referencia_global")
    
    # Carrega dados do banco do ano selecionado
    res_data = load_respostas(ano_sel)
    
    # Soma os pontos de forma segura ignorando comentários
    total_pts = sum(float(item.get("pontos", 0)) for k, item in res_data.items() if not k.startswith("COM_"))
    total_pts = round(total_pts, 1)
    
    # 1. Nova Lógica de Faixas do i-AMB (Definição dos Limites)
    if total_pts <= 500: 
        faixa, cor = "C", "red"
    elif total_pts <= 599: 
        faixa, cor = "C+", "orange"
    elif total_pts <= 749: 
        faixa, cor = "B", "#d4d400"
    elif total_pts <= 899: 
        faixa, cor = "B+", "lightgreen"
    else: 
        faixa, cor = "A", "green"

    # 2. Regra Especial A2: Rebaixar 1 Faixa se condições inadequadas
    rebaixar = res_data.get("A2", {}).get("valor") == "Condições inadequadas"
    
    if rebaixar:
        if faixa == "A": 
            faixa, cor = "B+", "lightgreen"
        elif faixa == "B+": 
            faixa, cor = "B", "#d4d400"
        elif faixa == "B": 
            faixa, cor = "C+", "orange"
        elif faixa == "C+": 
            faixa, cor = "C", "red"

    # 3. Exibição das Métricas na Interface Lateral
    st.sidebar.metric("Pontuação Total", f"{total_pts:.1f} pts")
    st.sidebar.markdown(f"**Faixa:** <span style='color:{cor}; font-size:20px; font-weight:bold;'>{faixa}</span>", unsafe_allow_html=True)
    
    # Exibe o alerta caso a regra de rebaixamento tenha sido disparada
    if rebaixar:
        st.sidebar.warning("⚠️ Faixa rebaixada devido ao IQR (A2)")
        
    # -------------------------------------------------------------------------
    # 🔥 BOTÃO DE DOWNLOAD DO RELATÓRIO PDF INTEGRADO (COM HISTÓRICO TRATADO)
    # -------------------------------------------------------------------------
    st.sidebar.markdown("---")
    st.sidebar.subheader("📄 Relatórios")
    
    # 1. Busca os dados brutos de todos os anos no banco de dados para a série histórica
    try:
        dados_historicos_brutos = get_all_years_data()
    except Exception:
        dados_historicos_brutos = {}
        
    # 2. TRATAMENTO CRÍTICO: Garante que as chaves dos anos sejam inteiros
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

    # 4. Gera o relatório passando o dicionário histórico tratado e captura o buffer do PDF
    try:
        pdf_buffer = gerar_relatorio_pdf(res_data, ano_sel, total_pts, faixa, historico_tratado)
        
        st.sidebar.download_button(
            label="📥 Baixar Relatório PDF",
            data=pdf_buffer.getvalue(),  # Extrai o valor binário correto do BytesIO
            file_name=f"Relatorio_i-AMB_{ano_sel}.pdf",
            mime="application/pdf"
        )
    except Exception as e:
        st.sidebar.error(f"Erro ao gerar o PDF: {e}")
        
    st.sidebar.markdown("---")
    
    # 5. Ação de Reset com Segurança no Banco de Dados e Interface
    if st.sidebar.button("🔄 Zerar Questionário"):
        # 1. Limpa o Banco de Dados para o ano selecionado
        with get_connection() as conn:
            conn.execute("DELETE FROM respostas WHERE ano = ?", (ano_sel,))
            conn.commit()
        
        # 2. Limpa apenas os widgets da interface
        prefixos_limpar = ("q", "l", "ext", "COM_")
        for key in list(st.session_state.keys()):
            if key.startswith(prefixos_limpar):
                del st.session_state[key]
                
        st.rerun()
        
    return total_pts, res_data, ano_sel

import io
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# =============================================================================
# 3. GERADOR DO RELATÓRIO PDF - i-AMB
# =============================================================================

def gerar_relatorio_pdf(dados, ano, total, faixa, all_data=None):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    
    # Inicializa os estilos padrões do ReportLab
    styles = getSampleStyleSheet()
    
    # Definição explícita dos estilos customizados da capa e tabelas
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

    # Função interna para limpar strings contra quebras no interpretador XML do ReportLab
    def limpar_xml(texto):
        return str(texto).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    if all_data is None:
        all_data = {}
        
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
    elements.append(Paragraph("Relatório i-AMB", style_titulo_capa))
    elements.append(Spacer(1, 5))
    elements.append(Paragraph("Índice de Governança Ambiental Municipal", ParagraphStyle('SubCapa', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=14, leading=18, textColor=colors.HexColor("#718096"), alignment=1)))
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
        [Paragraph("1. Resumo Executivo (Análise Comparativa Ambiental)", style_item_esquerda), Paragraph("Pág. 3", style_pag_direita)],
        [Paragraph("2. Análise de Desempenho por Quesito i-AMB", style_item_esquerda), Paragraph("Pág. 3", style_pag_direita)],
        [Paragraph("3. Análise de Impacto e Penalidades", style_item_esquerda), Paragraph("Pág. 4", style_pag_direita)],
        [Paragraph("4. Diagnóstico de Reincidências", style_item_esquerda), Paragraph("Pág. 4", style_pag_direita)],
        [Paragraph("5. Alinhamento com a Agenda 2030 (ODS Meio Ambiente)", style_item_esquerda), Paragraph("Pág. 4", style_pag_direita)],
        [Paragraph("6. Série Histórica Ambiental", style_item_esquerda), Paragraph("Pág. 5", style_pag_direita)],
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
    elements.append(Paragraph(f"RELATÓRIO DE AUDITORIA i-AMB (MEIO AMBIENTE) - {ano}", styles["Title"]))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("<b>1. RESUMO EXECUTIVO (ANÁLISE COMPARATIVA AMBIENTAL)</b>", styles["h2"]))
    elements.append(Spacer(1, 8))

    nota_atual = float(total)
    ano_atual = int(str(ano).strip()[:4])
    ano_ant = ano_atual - 1

    def converter_pontos_em_faixa_iamb(pontos):
        pts = float(pontos)
        if pts <= 500.0:             return "C"
        elif 501.0 <= pts <= 599.9:  return "C+"
        elif 600.0 <= pts <= 749.9:  return "B"
        elif 750.0 <= pts <= 899.9:  return "B+"
        else:                        return "A"

    dados_ano_anterior = all_data.get(ano_ant, {})
    nota_anterior = 0.0
    if ano_ant in all_data:
        nota_anterior = float(sum(
            info_ant.get("pontos", 0) 
            for qid_ant, info_ant in dados_ano_anterior.items() 
            if isinstance(info_ant, dict) and not qid_ant.startswith("COM_")
        ))

    faixa_anterior = converter_pontos_em_faixa_iamb(nota_anterior)
    faixa_real_atual = faixa if faixa else converter_pontos_em_faixa_iamb(nota_atual)

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

    if lista_pontos_fortes:
        elements.append(Paragraph("<b>✅ Pontos Fortes Ambientais:</b>", styles["h3"]))
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
    # 3. ANÁLISE DE IMPACTO E PENALIDADES (EFICIÊNCIA PREVENTIVA)
    # =========================================================================
    elements.append(Paragraph("<b>3. ANÁLISE DE IMPACTO E PENALIDADES (EFICIÊNCIA PREVENTIVA)</b>", styles["h2"]))
    elements.append(Spacer(1, 6))

    PENALIDADES_MAX = {
        "5.2": -15.0, "5.3": -10.0, "7.3.2": -5.0, "7.4.2": -5.0, "7.5.1": -5.0, 
        "8.4.4": -30.0, "9.1": -30.0, "10.0": -100.0, "10.1": -30.0, "10.2": -30.0, 
        "10.3.1": -50.0, "10.3.1.1": -50.0, "11.4": -10.0, "13.1": -110.0, 
        "13.2": -50.0, "13.2.1": -50.0, "14.0": -30.0, "A1": -200.0, "A3": -50.0
    }

    dados_penalidades = dados.copy()
    reincidencias_detectadas = []

    for qid_pen, val_max in PENALIDADES_MAX.items():
        if qid_pen not in dados_penalidades:
            dados_penalidades[qid_pen] = {"pontos": val_max, "valor": "Não preenchido / Ocultado por condicional", "link": ""}

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
            
            if eficiencia_preventiva < 100.0 and isinstance(dados_ano_anterior, dict) and qid in dados_ano_anterior:
                info_ant = dados_ano_anterior[qid]
                nota_real_ant = float(info_ant.get("pontos", 0.0)) if isinstance(info_ant, dict) else 0.0
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
    # 4. DIAGNÓSTICO DE REINCIDÊNCIAS (GARGALOS PERSISTENTES)
    # =========================================================================
    elements.append(Paragraph("<b>4. DIAGNÓSTICO DE REINCIDÊNCIAS (GARGALOS PERSISTENTES)</b>", styles["h2"]))
    elements.append(Spacer(1, 6))
    
    TETOS_VALIDOS = {
        "1.1.2": 20, "1.1.3": 5, "1.2": 20, "2.0": 10, "2.1": 50, "3.0": 10, "3.1": 20, "4.0": 20,
        "5.2.1": 20, "6.0": 20, "6.1": 50, "6.2": 25, "7.2": 2, "7.3": 10, "7.3.1": 20, "7.4": 10,
        "7.4.1": 20, "7.5": 30, "7.7": 30, "7.8": 20, "7.8.1": 50, "7.9": 3, "8.2": 2, "8.3": 10,
        "8.4": 20, "8.4.1": 10, "8.4.2": 30, "8.4.3": 50, "9.2": 100, "9.3": 5, "9.3.1": 5,
        "11.2": 2, "11.3": 30, "11.3.2": 20, "11.3.3": 40, "11.5": 10, "12.1": 54, "14.3": 30,
        "15": 2, "15.1": 3, "A4.1.1": 90, "A4.1.2": 20, "A4.1.3": 22, "A6": 5
    }
    
    dados_analise_reinc = dados.copy()
    
    for sub_id in subquestoes_11:
        if resposta_11_nao or (sub_id not in dados_analise_reinc):
            dados_analise_reinc[sub_id] = {"pontos": 0.0, "valor": "Não", "link": ""}

    for qid, info_atual in dados_analise_reinc.items():
        if qid.startswith("COM_") or not isinstance(info_atual, dict): 
            continue
            
        qid_str = str(qid).strip()
        
        if qid_str.startswith("A4.1.1_"):   chave_mae = "A4.1.1"
        elif qid_str.startswith("A4.1.2_"): chave_mae = "A4.1.2"
        elif qid_str.startswith("A4.1.3_"): chave_mae = "A4.1.3"
        else:                               chave_mae = qid_str
            
        if chave_mae not in TETOS_VALIDOS:
            continue
            
        pts_maximo = float(TETOS_VALIDOS[chave_mae])
        pts_obtidos_atual = float(info_atual.get("pontos", 0.0))
        
        if pts_maximo > 0 and (pts_obtidos_atual / pts_maximo) * 100 < 50.0:
            info_ant = dados_ano_anterior.get(qid, {}) if isinstance(dados_ano_anterior, dict) else {}
            pts_obtidos_ant = float(info_ant.get("pontos", 0.0)) if isinstance(info_ant, dict) else 0.0
            
            if (pts_obtidos_ant / pts_maximo) * 100 < 50.0:
                origem = "Gestão Ambiental Geral"
                if 'CATEGORIAS_MAP' in globals():
                    for cat_chave, cat_info in CATEGORIAS_MAP.items():
                        if chave_mae in cat_info.get("qids", []):
                            origem = cat_info.get("label", "Outros")
                            break
                else:
                    if chave_mae.startswith("1.") or chave_mae.startswith("2.") or chave_mae.startswith("3."):
                        origem = "Planejamento e Infraestrutura"
                    elif chave_mae.startswith("7.") or chave_mae.startswith("8."):
                        origem = "Resíduos e Saneamento"
                    elif chave_mae.startswith("11.") or chave_mae.startswith("12."):
                        origem = "Biodiversidade e Água"
                    elif chave_mae.startswith("A4"):
                        origem = "Indicadores SINISA"
                            
                reincidencias_detectadas.append({
                    "qid": qid_str, 
                    "tipo": origem, 
                    "detalhe": "Ineficiência Crônica de Desempenho (Eficiência inferior a 50% por 2 anos)",
                    "ant": f"{pts_obtidos_ant:.1f} / {pts_maximo:.1f} pts", 
                    "atual": f"{pts_obtidos_atual:.1f} / {pts_maximo:.1f} pts"
                })

    if reincidencias_detectadas:
        data_reinc = [[
            Paragraph("Quesito", style_th), 
            Paragraph("Origem da Falha", style_th), 
            Paragraph("Impacto Histórico", style_th), 
            Paragraph("Exercício Anterior", style_th), 
            Paragraph("Exercício Atual", style_th)
        ]]
        
        def ordenacao_segura(x):
            limpo = ''.join(c for c in x["qid"].split('_')[0] if c.isdigit() or c == '.')
            partes = [int(i) for i in limpo.split('.') if i.isdigit()]
            return partes if partes else [999]

        for reinc in sorted(reincidencias_detectadas, key=ordenacao_segura): 
            data_reinc.append([
                Paragraph(reinc["qid"], style_tabela_centro), 
                Paragraph(reinc["tipo"], style_tabela_centro), 
                Paragraph(f"<b>{reinc['detalhe']}</b>", style_tabela_padrao), 
                Paragraph(reinc["ant"], style_tabela_centro), 
                Paragraph(reinc["atual"], style_tabela_centro)
            ])
            
        tabela_reinc = Table(data_reinc, colWidths=[65, 115, 170, 75, 65])
        tabela_reinc.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#c0392b")), 
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#c0392b")), 
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), 
            ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(tabela_reinc)
    else: 
        elements.append(Paragraph("<font color='#2e7d32'><b>✅ Nenhuma reincidência ativa detectada. O município corrigiu ou mitigou as falhas do ano anterior.</b></font>", styles["Normal"]))
        
    elements.append(Spacer(1, 15))
        
# -------------------------------------------------------------------------
    # 5. ALINHAMENTO COM A AGENDA 2030 (METAS ODS / ONU) - FORMATADO PADRÃO I-GOV
    # -------------------------------------------------------------------------
    import reportlab.lib.colors as rl_colors
    # Mudança radical no nome do import local para extinguir o erro de UnboundLocalError
    from reportlab.lib.styles import ParagraphStyle as Alias_Style

    elements.append(Paragraph("<b>5. ALINHAMENTO COM A AGENDA 2030 (METAS ODS / ONU)</b>", styles["h2"]))
    elements.append(Spacer(1, 6))
    
    def calcular_percentual_checklist(resposta_bruta, total_itens):
        if not resposta_bruta: return 0.0
        itens = [i.strip().lower() for i in str(resposta_bruta).split(",") if i.strip()]
        itens_validos = [i for i in itens if "outros" not in i and i != ""]
        if total_itens > 0:
            return min((len(itens_validos) / total_itens) * 100.0, 100.0)
        return 0.0

    analise_ods = []
    quesitos_validos_ods = ["1.0", "1.1", "2.0", "3.0", "4.0", "8.0", "8.3", "8.3.1", "8.4", "8.4.1", "9.0", "10.0", "10.1", "10.2", "10.3", "12.0", "13.0", "14.0", "15.0"]

    for qid in quesitos_validos_ods:
        if qid not in dados: 
            continue
            
        info = dados[qid]
        if qid.startswith("COM_") or not isinstance(info, dict): 
            continue
            
        resp = str(info.get("valor", "")).strip()
        resp_l = resp.lower()
        
        if not resp or resp_l == "não respondido" or resp == "[]": 
            continue

        metas = ""
        status = "Não Atendido"

        # Lógica de Mapeamento do iAMB
        if qid in ["1.0", "1.1"]:
            metas = "12.2, 15.2, 16.6"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"
        elif qid == "2.0":
            metas = "4.7, 12.8, 15.1"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"
        elif qid == "3.0":
            metas = "12.2, 16.6, 17.14"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"
        elif qid == "4.0":
            metas = "12.4"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"
        elif qid in ["8.0", "8.3", "8.4", "9.0"]:
            metas = "11.6, 12.5"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"
        elif qid == "8.3.1":
            metas = "11.6, 12.5, 12.4"
            pct = calcular_percentual_checklist(resp, 3)
            status = f"{pct:.1f}% Atendido"
        elif qid == "8.4.1":
            metas = "11.6, 12.5, 12.4"
            pct = calcular_percentual_checklist(resp, 4)
            status = f"{pct:.1f}% Atendido"
        elif qid in ["10.0", "10.1"]:
            metas = "11.6, 12.5, 16.6"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"
        elif qid == "10.2":
            metas = "11.6, 12.5, 16.6"
            status = "Atendido" if "todos os bairros do município são atendidos" in resp_l else "Não Atendido"
        elif qid == "10.3":
            metas = "11.6, 12.5, 12.4, 16.6"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"
        elif qid == "12.0":
            metas = "11.6, 12.5, 12.4"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"
        elif qid in ["13.0", "14.0"]:
            metas = "11.6, 12.4"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"
        elif qid == "15.0":
            metas = "12.0, 16.6"
            status = "Atendido" if "sim" in resp_l else "Não Atendido"

        # Trata tamanho da string da diretriz para não quebrar o layout
        exibicao_resp = limpar_xml(resp)
        if len(exibicao_resp) > 45:
            exibicao_resp = exibicao_resp[:45] + "..."

        analise_ods.append({
            "qid": qid,
            "metas": metas,
            "resp": exibicao_resp,
            "status": status
        })

    if analise_ods:
        data_ods = [["Quesito", "Diretriz Declarada", "Vínculo Metas ODS", "Status de Alinhamento"]]
        # Modificado para usar a classe instanciada com o novo alias isolado
        style_td_ods = Alias_Style('TdOds', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, alignment=1)
        
        # Ordenação correta dos quesitos (ex: 1.0, 1.1, 2.0...)
        for item in sorted(analise_ods, key=lambda x: [float(i) if i.replace('.','',1).isdigit() else 999 for i in x['qid'].split('.')]):
            st_txt = item["status"]
            
            # Formatação de Cores Dinâmicas para o Status igual ao iGov
            if "Não Atendido" in st_txt:
                st_p = Paragraph(f"<font color='#dc3545'><b>{st_txt}</b></font>", style_td_ods)
            elif "Atendido" in st_txt and "%" not in st_txt:
                st_p = Paragraph(f"<font color='#28a745'><b>{st_txt}</b></font>", style_td_ods)
            else:
                st_p = Paragraph(f"<font color='#007bff'><b>{st_txt}</b></font>", style_td_ods)
                
            data_ods.append([
                Paragraph(f"<b>{item['qid']}</b>", style_tabela_centro), 
                Paragraph(item["resp"], style_tabela_padrao), 
                Paragraph(item["metas"], style_tabela_centro), 
                st_p
            ])
            
        tabela_ods = Table(data_ods, colWidths=[55, 210, 115, 110])
        tabela_ods.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), rl_colors.HexColor("#0f9d58")), # Verde institucional do iGov aplicado aqui
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
    # 📊 6. SÉRIE HISTÓRICA DO IAMB (CONSOLIDADO FINAL)
    # -------------------------------------------------------------------------
    from reportlab.graphics.shapes import Drawing, String
    from reportlab.graphics.charts.barcharts import VerticalBarChart

    elements.append(Spacer(1, 10))
    elements.append(Paragraph("<b>6. SÉRIE HISTÓRICA DO IAMB (CONSOLIDADO FINAL)</b>", styles["h2"]))
    elements.append(Spacer(1, 10))

    anos_serie = [2023, 2024, 2025, 2026, 2027, 2028, 2029, 2030]
    valores_serie = []
    
    # Captura do ano atual de forma segura
    ano_reference = None
    for nome_var in ['ano_sel', 'ano_atual', 'ano', 'exercicio']:
        if nome_var in locals():
            ano_reference = locals()[nome_var]
            break
    if ano_reference is None:
        ano_reference = 2026

    # Captura da nota atual (calculada no início do seu compilador)
    nota_reference = 0.0
    for nome_var in ['total_pts', 'nota_atual', 'pontuacao_final', 'total']:
        if nome_var in locals():
            try:
                nota_reference = float(locals()[nome_var])
                break
            except (ValueError, TypeError):
                continue

    import streamlit as st
    
    # Captura segura da variável all_data sem disparar NameError
    var_all_data = locals().get('all_data', globals().get('all_data', None))

    # Montagem do array de dados para o Gráfico
    for a in anos_serie:
        if a == 0 or a == "0":
            valores_serie.append(0.0)
        elif a == ano_reference: 
            valores_serie.append(min(nota_reference, 100.0) if nota_reference <= 100.0 else min(nota_reference, 1000.0))
        elif var_all_data and a in var_all_data:
            dados_ano = var_all_data[a]
            if isinstance(dados_ano, dict):
                pontos_ano = float(sum(info_h.get("pontos", 0.0) for qid_h, info_h in dados_ano.items() if isinstance(info_h, dict) and not qid_h.startswith("COM_")))
                valores_serie.append(pontos_ano)
            else:
                valores_serie.append(float(dados_ano))
        elif hasattr(st, 'session_state') and 'all_data' in st.session_state and a in st.session_state.all_data:
            dados_ano = st.session_state.all_data[a]
            if isinstance(dados_ano, dict):
                pontos_ano = float(sum(info_h.get("pontos", 0.0) for qid_h, info_h in dados_ano.items() if isinstance(info_h, dict) and not qid_h.startswith("COM_")))
                valores_serie.append(pontos_ano)
            else:
                valores_serie.append(float(dados_ano))
        else: 
            valores_serie.append(0.0)

    # Identifica se a escala do iAMB é até 100 ou até 1000 para ajustar o gráfico dinamicamente
    max_escala = 1000 if any(v > 100 for v in valores_serie) else 100
    passo_escala = 200 if max_escala == 1000 else 20

    # Configuração e renderização do Gráfico do iAMB
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
    
    bc.valueAxis.valueMin = 0
    bc.valueAxis.valueMax = max_escala
    bc.valueAxis.valueStep = passo_escala
    bc.valueAxis.labels.fontSize = 8
    
    # Ativação dos rótulos acima das barras
    bc.barLabels.nudge = 8
    bc.barLabels.fontSize = 8
    bc.barLabels.fontName = 'Helvetica-Bold'
    bc.barLabelFormat = '%.1f'
    
    # Customização de cor temática azul-escura/institucional
    bc.bars[0].fillColor = rl_colors.HexColor("#1b4f72")
    bc.bars[0].strokeColor = rl_colors.HexColor("#2c3e50")
    bc.bars[0].strokeWidth = 0.5

    desenho_grafico.add(String(240, 150, "Série Histórica de Evolução do iAMB", textAnchor='middle', fontName='Helvetica-Bold', fontSize=12, fillColor=rl_colors.HexColor("#2c3e50")))
    desenho_grafico.add(bc)
    
    elements.append(desenho_grafico)
    elements.append(Spacer(1, 15))

    # =========================================================================
    # FIM DA FUNÇÃO: GERAÇÃO E RETORNO SEGURO DO BUFFER
    # =========================================================================
    doc.build(elements)
    buffer.seek(0)
    return buffer

# =============================================================================
# 4. FORMULÁRIO PRINCIPAL E ABAS
# =============================================================================

def mostrar_formulario_amb():
    init_db()
    total_pts, res_data, ano_sel = render_sidebar()
    
    st.markdown("""
        <style>
        .quesito-card {
            background-color: #f0f4f0;
            padding: 20px;
            border-left: 6px solid #2e7d32;
            border-radius: 8px;
            margin-bottom: 20px;
            border: 1px solid #c8e6c9;
        }
        .externo-card {
            background-color: #f0f7ff;
            padding: 20px;
            border-left: 6px solid #007bff;
            border-radius: 8px;
            margin-bottom: 20px;
            border: 1px solid #cce5ff;
        }
        </style>
    """, unsafe_allow_html=True)

    st.title(f"🍃 Auditoria i-AMB (Meio Ambiente) - {ano_sel}")
    
    aba_quest, aba_ext, aba_graf = st.tabs(["📋 Questionário", "📊 Dados Externos", "📈 Gráficos"])
    
    with aba_quest:
        # --- SEÇÃO 1: ESTRUTURA ---
        st.header("1.0 Estrutura Organizacional")
        
        # -------------------------------------------------------------------------
        # --- QUESITO 1.0 (ESTRUTURA AMBIENTAL) ------------------------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 1.0")
        st.write("**A prefeitura possui alguma estrutura organizacional para tratar de assuntos ligados ao Meio Ambiente Municipal?**")
        
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

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 1.0
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


        # -------------------------------------------------------------------------
        # --- QUESITO 1.1 (RECURSOS HUMANOS) --------------------------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 1.1")
        st.write("**A Prefeitura possui recursos humanos para operacionalização dos assuntos ligados ao Meio Ambiente?**")
        
        d11 = res_data.get("1.1", {"valor": None, "pontos": 0.0, "link": ""})
        opc11 = ["Sim", "Não"]
        idx11 = opc11.index(d11["valor"]) if d11["valor"] in opc11 else None
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r11 = st.radio("Selecione 1.1:", opc11, index=idx11, key=f"q11_{ano_sel}")
        with col2:
            l11 = st.text_area("Link/Evidência (1.1):", value=d11.get("link", ""), key=f"l11_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS inline
            links_11_atuais = re.findall(r'(https?://[^\s]+)', l11)
            if links_11_atuais:
                botoes_11 = " | ".join([f"🔗 [{u}]({u})" for u in links_11_atuais])
                st.markdown(f"**Links Ativos:** {botoes_11}")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 1.1
        if r11 is not None and (r11 != d11["valor"] or l11 != d11["link"]):
            save_resp("1.1", r11, 0.0, l11)
            
            if links_11_atuais:
                links_11_antigos = re.findall(r'(https?://[^\s]+)', d11["link"])
                if links_11_atuais != links_11_antigos:
                    modal_aviso_link("1.1", links_11_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
                
        # SUBQUESITO CONDICIONAL 1.1.1 (CONTAGEM DE RH)
        if r11 == "Sim":
            st.markdown("<br>", unsafe_allow_html=True)
            st.write("**1.1.1 Informe a quantidade de pessoal:**")
            d111 = res_data.get("1.1.1", {"valor": "", "pontos": 0.0, "link": ""})
            
            try:
                parts = d111["link"].split(",")
                v_efe = int(parts[0].split(":")[1])
                v_com = int(parts[1].split(":")[1])
                v_ter = int(parts[2].split(":")[1])
            except:
                v_efe, v_com, v_ter = 0, 0, 0
            
            c1, c2, c3 = st.columns(3)
            n_efe = c1.number_input("Efetivos:", min_value=0, value=v_efe, key=f"q111_efe_{ano_sel}")
            n_com = c2.number_input("Comissionados:", min_value=0, value=v_com, key=f"q111_com_{ano_sel}")
            n_ter = c3.number_input("Terceirizados:", min_value=0, value=v_ter, key=f"q111_ter_{ano_sel}")
            
            total_rh = n_efe + n_com + n_ter
            new_link_rh = f"E:{n_efe}, C:{n_com}, T:{n_ter}"
            
            if d111["valor"] != "" or total_rh > 0:
                if str(total_rh) != d111["valor"] or new_link_rh != d111["link"]:
                    save_resp("1.1.1", str(total_rh), 0.0, new_link_rh)
                    st.rerun()

        bloco_comentarios("1.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)


        # -------------------------------------------------------------------------
        # --- QUESITO 1.1.2 (TREINAMENTO ESPECÍFICO) ------------------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 1.1.2")
        ano_anterior = int(ano_sel) - 1
        st.write(f"**Os servidores responsáveis pelo Meio Ambiente receberam treinamento específico voltado ao Meio Ambiente em {ano_anterior}?**")
        
        d112 = res_data.get("1.1.2", {"valor": None, "pontos": 0.0, "link": ""})
        opc112 = ["Sim – 20", "Não – 00"]
        idx112 = opc112.index(d112["valor"]) if d112["valor"] in opc112 else None
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r112 = st.radio("Selecione 1.1.2:", opc112, index=idx112, key=f"q112_{ano_sel}")
        with col2:
            l112 = st.text_area("Link/Evidência (1.1.2):", value=d112.get("link", ""), key=f"l112_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS inline
            links_112_atuais = re.findall(r'(https?://[^\s]+)', l112)
            if links_112_atuais:
                botoes_112 = " | ".join([f"🔗 [{u}]({u})" for u in links_112_atuais])
                st.markdown(f"**Links Ativos:** {botoes_112}")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 1.1.2
        if r112 is not None and (r112 != d112["valor"] or l112 != d112["link"]):
            pts_calculados_112 = 20.0 if "Sim" in r112 else 0.0
            save_resp("1.1.2", r112, pts_calculados_112, l112)
            
            if links_112_atuais:
                links_112_antigos = re.findall(r'(https?://[^\s]+)', d112["link"])
                if links_112_atuais != links_112_antigos:
                    modal_aviso_link("1.1.2", links_112_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("1.1.2", res_data)
        st.markdown('</div>', unsafe_allow_html=True)


        # -------------------------------------------------------------------------
        # --- QUESITO 1.1.3 (EDUCAÇÃO AMBIENTAL) ----------------------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 1.1.3")
        st.write("**A Secretaria Municipal de Meio Ambiente ou similar ofereceu cursos/treinamento sobre educação ambiental para qual público?**")
        
        d113 = res_data.get("1.1.3", {"valor": "", "pontos": 0.0, "link": ""})
        
        col1, col2 = st.columns([1, 2])
        with col1:
            opts113 = {
                "Para escolas – 05": 5.0, 
                "Para outras secretarias / entidades municipais – 02": 2.0, 
                "Para munícipes ou empresas – 03": 3.0, 
                "Não ofereceu nenhum curso/treinamento no ano – 00": 0.0
            }
            sel113 = []
            pts113 = 0.0
            texto_seguro_113 = str(d113["valor"]) if d113["valor"] not in ["", "[]"] else ""
            for txt, pts in opts113.items():
                marcado = (txt in texto_seguro_113) if texto_seguro_113 else False
                if st.checkbox(txt, value=marcado, key=f"q113_{txt}_{ano_sel}"):
                    sel113.append(txt)
                    pts113 += pts
                    
        with col2:
            l113 = st.text_area("Link/Evidência (1.1.3):", value=d113.get("link", ""), key=f"l113_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS inline
            links_113_atuais = re.findall(r'(https?://[^\s]+)', l113)
            if links_113_atuais:
                botoes_113 = " | ".join([f"🔗 [{u}]({u})" for u in links_113_atuais])
                st.markdown(f"**Links Ativos:** {botoes_113}")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 1.1.3
        if str(sel113) != d113["valor"] or l113 != d113["link"]:
            save_resp("1.1.3", str(sel113), float(pts113), l113)
            
            if links_113_atuais:
                links_113_antigos = re.findall(r'(https?://[^\s]+)', d113["link"])
                if links_113_atuais != links_113_antigos:
                    modal_aviso_link("1.1.3", links_113_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("1.1.3", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # -------------------------------------------------------------------------
        # --- QUESITO 1.2 (RECURSOS DISPONIBILIZADOS) ----------------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 1.2")
        st.write("**Assinale os recursos disponibilizados para a operacionalização das atividades de meio ambiente: Não considerar Recursos Humanos e Estrutura Física nesta questão.**")
        
        d12 = res_data.get("1.2", {"valor": "", "pontos": 0.0, "link": ""})
        
        col1, col2 = st.columns([1, 2])
        with col1:
            opts12 = ["Recursos Tecnológicos – 05", "Recursos Orçamentários – 05", "Recursos Materiais – 05", "Outros – 05"]
            sel12 = []
            pts12 = 0.0
            texto_seguro_12 = str(d12["valor"]) if d12["valor"] not in ["", "[]"] else ""
            for opt in opts12:
                marcado = (opt in texto_seguro_12) if texto_seguro_12 else False
                if st.checkbox(opt, value=marcado, key=f"q12_{opt}_{ano_sel}"):
                    sel12.append(opt)
                    pts12 += 5.0
        with col2:
            l12 = st.text_area("Link/Evidência (1.2):", value=d12.get("link", ""), key=f"l12_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_12_atuais = re.findall(r'(https?://[^\s]+)', l12)
            if links_12_atuais:
                botoes_12 = " | ".join([f"🔗 [{u}]({u})" for u in links_12_atuais])
                st.markdown(f"**Links Ativos:** {botoes_12}")
        
        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 1.2
        if str(sel12) != d12["valor"] or l12 != d12["link"]:
            save_resp("1.2", str(sel12), float(pts12), l12)
            
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


        # --- SEÇÃO 2: EDUCAÇÃO AMBIENTAL ---
        st.divider()
        st.header("2.0 Educação Ambiental")
        
        # -------------------------------------------------------------------------
        # --- QUESITO 2.0 (PARTICIPAÇÃO EM PROGRAMA) ------------------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 2.0")
        st.write("**O Município participa de algum Programa de Educação Ambiental?**")
        
        d20 = res_data.get("2.0", {"valor": None, "pontos": 0.0, "link": ""})
        opc20 = ["Sim – 10", "Não – 00"]
        idx20 = opc20.index(d20["valor"]) if d20["valor"] in opc20 else None
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r20 = st.radio("Selecione 2.0:", opc20, index=idx20, key=f"q20_{ano_sel}")
        with col2:
            l20 = st.text_area("Link/Evidência (2.0):", value=d20.get("link", ""), key=f"l20_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_20_atuais = re.findall(r'(https?://[^\s]+)', l20)
            if links_20_atuais:
                botoes_20 = " | ".join([f"🔗 [{u}]({u})" for u in links_20_atuais])
                st.markdown(f"**Links Ativos:** {botoes_20}")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 2.0
        if r20 is not None and (r20 != d20["valor"] or l20 != d20["link"]):
            pts_calculados_20 = 10.0 if "Sim" in r20 else 0.0
            save_resp("2.0", r20, pts_calculados_20, l20)
            
            if links_20_atuais:
                links_20_antigos = re.findall(r'(https?://[^\s]+)', d20["link"])
                if links_20_atuais != links_20_antigos:
                    modal_aviso_link("2.0", links_20_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("2.0", res_data)
        st.markdown('</div>', unsafe_allow_html=True)


        # -------------------------------------------------------------------------
        # --- QUESITO 2.1 (AÇÃO EM REDE ESCOLAR) ----------------------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 2.1")
        st.write("**Sobre programa ou ação de educação ambiental na rede escolar municipal, informe o número de escolas dos Anos Iniciais (1º ao 5º ano) que adotam o programa.**")
        
        d21 = res_data.get("2.1", {"valor": "", "pontos": 0.0, "link": ""})
       
        try:
            valores_salvos = json.loads(d21["valor"]) if d21["valor"] != "" else {"n_com_programa": 0, "n_total": 1}
        except:
            valores_salvos = {"n_com_programa": 0, "n_total": 1}

        col1, col2 = st.columns([1, 2])
        with col1:
            st.markdown("**Dados para o cálculo:**")
            n_com_programa = st.number_input(
                "Nº de escolas com programa/ação ambiental:",
                min_value=0,
                value=int(valores_salvos.get("n_com_programa", 0)),
                key=f"q21_com_prog_{ano_sel}"
            )
            n_total = st.number_input(
                "Nº total de escolas de Anos Iniciais no município (i-Educ = E3.3):",
                min_value=1,
                value=int(valores_salvos.get("n_total", 1)),
                key=f"q21_total_{ano_sel}"
            )
            P = n_com_programa / n_total
            P_max = 50.0
            pts21 = min(P * P_max, P_max)
            st.metric(label="Pontuação Calculada (Máx: 50)", value=f"{pts21:.2f} pts")

        with col2:
            l21 = st.text_area("Link/Evidência (2.1):", value=d21.get("link", ""), key=f"l21_{ano_sel}", height=150)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_21_atuais = re.findall(r'(https?://[^\s]+)', l21)
            if links_21_atuais:
                botoes_21 = " | ".join([f"🔗 [{u}]({u})" for u in links_21_atuais])
                st.markdown(f"**Links Ativos:** {botoes_21}")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 2.1
        valores_atuais = json.dumps({"n_com_programa": n_com_programa, "n_total": n_total})
        if d21["valor"] != "" or n_com_programa > 0:
            if valores_atuais != d21["valor"] or l21 != d21["link"]:
                save_resp("2.1", valores_atuais, float(pts21), l21)
                
                if links_21_atuais:
                    links_21_antigos = re.findall(r'(https?://[^\s]+)', d21["link"])
                    if links_21_atuais != links_21_antigos:
                        modal_aviso_link("2.1", links_21_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()

        bloco_comentarios("2.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)
  
        # --- SEÇÃO 3: USO DE RECURSOS ---
        st.divider()
        st.header("3.0 Uso de Recursos")
        
        # -------------------------------------------------------------------------
        # --- QUESITO 3.0 (ESTÍMULO AO USO RACIONAL) -----------------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 3.0")
        st.write("**A prefeitura municipal estimula entre seus órgãos e entidades de sua responsabilidade projetos e/ou ações que promovam o uso racional de recursos naturais? Ex.: implantação de dispositivos para uso racional da água, coleta seletiva, reuso ou reciclagem de material entre outros.**")
        
        d30 = res_data.get("3.0", {"valor": None, "pontos": 0.0, "link": ""})
        opc30 = ["Sim, para todos os órgãos e entidades – 10", "Parcialmente - 3", "Não – 00"]
        idx30 = opc30.index(d30["valor"]) if d30["valor"] in opc30 else None
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r30 = st.radio("Selecione 3.0:", opc30, index=idx30, key=f"q30_{ano_sel}")
        with col2:
            l30 = st.text_area("Link/Evidência (3.0):", value=d30.get("link", ""), key=f"l30_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_30_atuais = re.findall(r'(https?://[^\s]+)', l30)
            if links_30_atuais:
                botoes_30 = " | ".join([f"🔗 [{u}]({u})" for u in links_30_atuais])
                st.markdown(f"**Links Ativos:** {botoes_30}")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 3.0
        if r30 is not None and (r30 != d30["valor"] or l30 != d30["link"]):
            pts_30 = 10.0 if "todos" in r30 else (3.0 if "Parcialmente" in r30 else 0.0)
            save_resp("3.0", r30, pts_30, l30)
            
            if links_30_atuais:
                links_30_antigos = re.findall(r'(https?://[^\s]+)', d30["link"])
                if links_30_atuais != links_30_antigos:
                    modal_aviso_link("3.0", links_30_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("3.0", res_data)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # -------------------------------------------------------------------------
        # --- QUESITO 3.1 (AÇÕES REALIZADAS PELO MUNICÍPIO) -----------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 3.1")
        st.write("**Assinale quais tipos de ações realizadas pela Prefeitura para o uso racional de recursos naturais:**")
        
        d31 = res_data.get("3.1", {"valor": "", "pontos": 0.0, "link": ""})
        
        col1, col2 = st.columns([1, 2])
        with col1:
            opts31 = {
                "Coleta seletiva – 1,5": 1.5,
                "Uso racional da água – 1,5": 1.5,
                "Uso racional de energia elétrica – 1,5": 1.5,
                "Reúso de materiais – 1,5": 1.5,
                "Horta coletiva – 1,5": 1.5,
                "Compostagem – 1,5": 1.5,
                "Instalação de bicicletários e vestiários para os servidores públicos – 1,5": 1.5,
                "Implantação de caixas acopladas nos vasos sanitários – 1,5": 1.5,
                "Substituição de lâmpadas fluorescentes por lâmpadas LED – 1,5": 1.5,
                "Instalação de structures para a captação de água de chuva – 1,5": 1.5,
                "Instalação de torneiras com redutores de pressão – 1,5": 1.5,
                "Substituição de material descartável – 1,5": 1.5,
                "Logística reversa de pilhas, baterias e eletrônicos – 1,5": 1.5,
                "Outros – 0,5": 0.5
            }
            sel31 = []
            pts31 = 0.0
            texto_seguro_31 = str(d31["valor"]) if d31["valor"] not in ["", "[]"] else ""
            for i, (txt, pts) in enumerate(opts31.items()):
                marcado = (txt in texto_seguro_31) if texto_seguro_31 else False
                if st.checkbox(txt, value=marcado, key=f"q31_opt_{i}_{ano_sel}"):
                    sel31.append(txt)
                    pts31 += pts
        with col2:
            l31 = st.text_area("Link/Evidência (3.1):", value=d31.get("link", ""), key=f"l31_{ano_sel}", height=150)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_31_atuais = re.findall(r'(https?://[^\s]+)', l31)
            if links_31_atuais:
                botoes_31 = " | ".join([f"🔗 [{u}]({u})" for u in links_31_atuais])
                st.markdown(f"**Links Ativos:** {botoes_31}")
        
        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 3.1
        if str(sel31) != d31["valor"] or l31 != d31["link"]:
            save_resp("3.1", str(sel31), float(pts31), l31)
            
            if links_31_atuais:
                links_31_antigos = re.findall(r'(https?://[^\s]+)', d31["link"])
                if links_31_atuais != links_31_antigos:
                    modal_aviso_link("3.1", links_31_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("3.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # --- SEÇÃO 4: CONTROLE DE POLUIÇÃO ---
        st.divider()
        st.header("4.0 Controle de Poluição")
        
        # -------------------------------------------------------------------------
        # --- QUESITO 4.0 (FISCALIZAÇÃO DE EMISSÃO DE POLUENTES) ------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 4.0")
        st.write("**O município fiscalizou a emissão de poluentes de combustíveis fósseis (diesel) na frota da Prefeitura Municipal?**")
        
        d40 = res_data.get("4.0", {"valor": None, "pontos": 0.0, "link": ""})
        opc40 = ["Sim, com medição da densidade colorimétrica da Escala Ringelmann ou equivalente – 20", "Sim, através de outra forma de medição – 15", "Não – 00"]
        idx40 = opc40.index(d40["valor"]) if d40["valor"] in opc40 else None
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r40 = st.radio("Selecione 4.0:", opc40, index=idx40, key=f"q40_{ano_sel}")
        with col2:
            l40 = st.text_area("Link/Evidência (4.0):", value=d40.get("link", ""), key=f"l40_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_40_atuais = re.findall(r'(https?://[^\s]+)', l40)
            if links_40_atuais:
                botoes_40 = " | ".join([f"🔗 [{u}]({u})" for u in links_40_atuais])
                st.markdown(f"**Links Ativos:** {botoes_40}")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 4.0
        if r40 is not None and (r40 != d40["valor"] or l40 != d40["link"]):
            pts_40 = 20.0 if "Ringelmann" in r40 else (15.0 if "outra" in r40 else 0.0)
            save_resp("4.0", r40, pts_40, l40)
            
            if links_40_atuais:
                links_40_antigos = re.findall(r'(https?://[^\s]+)', d40["link"])
                if links_40_atuais != links_40_antigos:
                    modal_aviso_link("4.0", links_40_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("4.0", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # --- SEÇÃO 5: ARBORIZAÇÃO ---
        st.divider()
        st.header("5.0 Arborização e Podas")
        
        # -------------------------------------------------------------------------
        # --- QUESITO 5.0 (CONTRATO DE PRESTAÇÃO DE SERVIÇO) ----------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 5.0")
        st.write("**A Prefeitura Municipal possui contrato de prestação de serviço de poda e corte de árvores, arbustos e outras plantas lenhosas em áreas urbanas?**")
        
        d50 = res_data.get("5.0", {"valor": None, "pontos": 0.0, "link": ""})
        opc50 = ["Sim", "Não"]
        idx50 = opc50.index(d50["valor"]) if d50["valor"] in opc50 else None
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r50 = st.radio("Selecione 5.0:", opc50, index=idx50, key=f"q50_{ano_sel}")
        with col2:
            l50 = st.text_area("Link/Evidência (5.0):", value=d50.get("link", ""), key=f"l50_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_50_atuais = re.findall(r'(https?://[^\s]+)', l50)
            if links_50_atuais:
                botoes_50 = " | ".join([f"🔗 [{u}]({u})" for u in links_50_atuais])
                st.markdown(f"**Links Ativos:** {botoes_50}")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 5.0
        if r50 is not None and (r50 != d50["valor"] or l50 != d50["link"]):
            save_resp("5.0", r50, 0.0, l50)
            
            if links_50_atuais:
                links_50_antigos = re.findall(r'(https?://[^\s]+)', d50["link"])
                if links_50_atuais != links_50_antigos:
                    modal_aviso_link("5.0", links_50_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("5.0", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # -------------------------------------------------------------------------
        # --- QUESITO 5.1 (NÚMERO DO CONTRATO E PRESTADOR) -----------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 5.1")
        st.write("**Informe o número do contrato e o prestador de serviço:**")
        
        d51 = res_data.get("5.1", {"valor": "", "pontos": 0.0, "link": ""})
        try:
            parts = d51["valor"].split("|")
            c_salvo = parts[0].split(":")[1].strip()
            p_salvo = parts[1].split(":")[1].strip()
        except:
            c_salvo, p_salvo = "", ""

        col1, col2 = st.columns([1, 2])
        with col1:
            num_contrato = st.text_input("Número do contrato:", value=c_salvo, key=f"q51_cont_{ano_sel}")
            prestador = st.text_input("Prestador de serviço:", value=p_salvo, key=f"q51_prest_{ano_sel}")
        with col2:
            l51 = st.text_area("Link/Evidência (5.1):", value=d51.get("link", ""), key=f"l51_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS (Corrigido escopo da variável para links_51_atuais)
            links_51_atuais = re.findall(r'(https?://[^\s]+)', l51)
            if links_51_atuais:
                botoes_51 = " | ".join([f"🔗 [{u}]({u})" for u in links_51_atuais])
                st.markdown(f"**Links Ativos:** {botoes_51}")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 5.1
        valor_ajustado = f"Contrato: {num_contrato} | Prestador: {prestador}"
        if num_contrato or prestador or d51["valor"] != "":
            if valor_ajustado != d51["valor"] or l51 != d51["link"]:
                save_resp("5.1", valor_ajustado, 0.0, l51)
                
                if links_51_atuais:
                    links_51_antigos = re.findall(r'(https?://[^\s]+)', d51["link"])
                    if links_51_atuais != links_51_antigos:
                        modal_aviso_link("5.1", links_51_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()

        bloco_comentarios("5.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # -------------------------------------------------------------------------
        # --- QUESITO 5.2 (PERIODICIDADE DE PODA) ----------------------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 5.2")
        st.write("**A Prefeitura mantém uma periodicidade de poda/manutenção das árvores?**")
        
        d52 = res_data.get("5.2", {"valor": None, "pontos": 0.0, "link": ""})

        col1, col2 = st.columns([1, 2])
        with col1:
            opts52 = {
                "Sim – 00": 0.0,
                "Não tem uma periodicidade – -10": -10.0,
                "Somente por solicitação – -10": -10.0,
                "Não realiza poda e/ou corte de árvores – -15": -15.0
            }
            lista_opts = list(opts52.keys())
            idx_salvo = lista_opts.index(d52["valor"]) if d52["valor"] in lista_opts else None
            sel52 = st.radio("Selecione uma opção:", options=lista_opts, index=idx_salvo, key=f"q52_{ano_sel}")
        with col2:
            l52 = st.text_area("Link/Evidência (5.2):", value=d52.get("link", ""), key=f"l52_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_52_atuais = re.findall(r'(https?://[^\s]+)', l52)
            if links_52_atuais:
                botoes_52 = " | ".join([f"🔗 [{u}]({u})" for u in links_52_atuais])
                st.markdown(f"**Links Ativos:** {botoes_52}")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 5.2
        if sel52 is not None and (sel52 != d52["valor"] or l52 != d52["link"]):
            pts52 = opts52[sel52]
            save_resp("5.2", sel52, float(pts52), l52)
            
            if links_52_atuais:
                links_52_antigos = re.findall(r'(https?://[^\s]+)', d52["link"])
                if links_52_atuais != links_52_antigos:
                    modal_aviso_link("5.2", links_52_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("5.2", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # -------------------------------------------------------------------------
        # --- QUESITO 5.2.1 (DESTINAÇÃO DOS RESÍDUOS DE PODAS) ---------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 5.2.1")
        st.write("**Qual a destinação dos resíduos das podas de árvores?**")
        
        d521 = res_data.get("5.2.1", {"valor": "", "pontos": 0.0, "link": ""})

        col1, col2 = st.columns([1, 2])
        with col1:
            opts_pontuam = [
                "Reaproveitamento para produzir móveis, brinquedos, utensílios ou objetos de decoração",
                "Compostagem para produção de mudas, na jardinagem e arborização da cidade",
                "Queima para aquecimento e cocção",
                "Geração de energia",
                "Uso na construção civil"
            ]
            sel521 = []
            qtd_validas = 0
            penalidade = 0.0
            texto_seguro_521 = str(d521["valor"]) if d521["valor"] not in ["", "[]"] else ""
            
            for i, opt in enumerate(opts_pontuam):
                marcado = (opt in texto_seguro_521) if texto_seguro_521 else False
                if st.checkbox(opt, value=marcado, key=f"q521_pos_{i}_{ano_sel}"):
                    sel521.append(opt)
                    qtd_validas += 1
            
            opt_aterro = "Envio para aterro sanitário – -05"
            marcado_aterro = (opt_aterro in texto_seguro_521) if texto_seguro_521 else False
            if st.checkbox(opt_aterro, value=marcado_aterro, key=f"q521_aterro_{ano_sel}"):
                sel521.append(opt_aterro)
                penalidade = -5.0
        
            opt_armazenamento = "Armazenamento dos resíduos das podas"
            marcado_arm = (opt_armazenamento in texto_seguro_521) if texto_seguro_521 else False
            if st.checkbox(opt_armazenamento, value=marcado_arm, key=f"q521_arm_{ano_sel}"):
                sel521.append(opt_armazenamento)

            if qtd_validas >= 3: pts_base = 20.0
            elif qtd_validas == 2: pts_base = 10.0
            elif qtd_validas == 1: pts_base = 5.0
            else: pts_base = 0.0
            pts521 = pts_base + penalidade

        with col2:
            l521 = st.text_area("Link/Evidência (5.2.1):", value=d521.get("link", ""), key=f"l521_{ano_sel}", height=150)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_521_atuais = re.findall(r'(https?://[^\s]+)', l521)
            if links_521_atuais:
                botoes_521 = " | ".join([f"🔗 [{u}]({u})" for u in links_521_atuais])
                st.markdown(f"**Links Ativos:** {botoes_521}")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 5.2.1
        if str(sel521) != d521["valor"] or l521 != d521["link"]:
            save_resp("5.2.1", str(sel521), float(pts521), l521)
            
            if links_521_atuais:
                links_521_antigos = re.findall(r'(https?://[^\s]+)', d521["link"])
                if links_521_atuais != links_521_antigos:
                    modal_aviso_link("5.2.1", links_521_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("5.2.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # -------------------------------------------------------------------------
        # --- QUESITO 5.3 (ORIENTAÇÃO/TREINAMENTO DE EQUIPE) ---------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 5.3")
        st.write("**O pessoal da prefeitura responsável por manutenção das árvores é devidamente orientado/treinado para realizar a poda de maneira correta?**")
        
        d53 = res_data.get("5.3", {"valor": None, "pontos": 0.0, "link": ""})

        col1, col2 = st.columns([1, 2])
        with col1:
            opts53 = {
                "Sim – 00": 0.0,
                "Não – -10": -10.0
            }
            lista_opts53 = list(opts53.keys())
            idx_salvo53 = lista_opts53.index(d53["valor"]) if d53["valor"] in lista_opts53 else None
            sel53 = st.radio("Selecione uma opção:", options=lista_opts53, index=idx_salvo53, key=f"q53_{ano_sel}")
        with col2:
            l53 = st.text_area("Link/Evidência (5.3):", value=d53.get("link", ""), key=f"l53_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_53_atuais = re.findall(r'(https?://[^\s]+)', l53)
            if links_53_atuais:
                botoes_53 = " | ".join([f"🔗 [{u}]({u})" for u in links_53_atuais])
                st.markdown(f"**Links Ativos:** {botoes_53}")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 5.3
        if sel53 is not None and (sel53 != d53["valor"] or l53 != d53["link"]):
            pts53 = opts53[sel53]
            save_resp("5.3", sel53, float(pts53), l53)
            
            if links_53_atuais:
                links_53_antigos = re.findall(r'(https?://[^\s]+)', d53["link"])
                if links_53_atuais != links_53_antigos:
                    modal_aviso_link("5.3", links_53_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("5.3", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # --- SEÇÃO 6: ESTIAGEM ---
        st.divider()
        st.header("6.0 Medidas para Estiagem")
        
        # -------------------------------------------------------------------------
        # --- QUESITO 6.0 (AÇÕES PREVENTIVAS DE ESTIAGEM) --------------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 6.0")
        st.write("**Existem ações e medidas preventivas de contingenciamento para os períodos de estiagem executados pela Prefeitura? Estiagem é um período prolongado de baixa pluviosidade, ou sua ausência, na qual a perda de umidade do solo é superior à sua reposição**")
        
        d60 = res_data.get("6.0", {"valor": None, "pontos": 0, "link": ""})
        opc60 = ["Sim – 20", "Não – 00"]
        idx60 = opc60.index(d60["valor"]) if d60["valor"] in opc60 else None
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r60 = st.radio("Selecione 6.0:", opc60, index=idx60, key=f"q60_{ano_sel}")
        with col2:
            l60 = st.text_area("Link/Evidência (6.0):", value=d60.get("link", ""), key=f"l60_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_60_atuais = re.findall(r'(https?://[^\s]+)', l60)
            if links_60_atuais:
                botoes_60 = " | ".join([f"🔗 [{u}]({u})" for u in links_60_atuais])
                st.markdown(f"**Links Ativos:** {botoes_60}")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 6.0
        if r60 and (r60 != d60["valor"] or l60 != d60["link"]):
            pts60 = 20 if "Sim" in (r60 or "") else 0
            save_resp("6.0", r60, float(pts60), l60)
            
            if links_60_atuais:
                links_60_antigos = re.findall(r'(https?://[^\s]+)', d60["link"])
                if links_60_atuais != links_60_antigos:
                    modal_aviso_link("6.0", links_60_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("6.0", res_data)
        st.markdown('</div>', unsafe_allow_html=True)


        # -------------------------------------------------------------------------
        # --- QUESITO 6.1 (DETALHAMENTO DAS MEDIDAS DE ESTIAGEM) ------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 6.1")
        st.write("**Assinale as ações e medidas preventivas de contingenciamento para os períodos de estiagem executados pela Prefeitura:**")

        d61 = res_data.get("6.1", {"valor": "", "pontos": 0.0, "link": ""})

        col1, col2 = st.columns([1, 2])
        with col1:
            opts61 = {
                "Plano emergencial ou de contingenciamento sobre abastecimento de água no caso de sua escassez – 30": 30.0,
                "Manejo/manobras de água entre os reservatórios – 00": 0.0,
                "Campanha de conscientização da população – 05": 5.0,
                "Busca de fontes alternativas de abastecimento, como: poços artesianos – 00": 0.0,
                "Uso racional da distribuição de água (racionamento) – 00": 0.0,
                "Implantação de rodízio de fornecimento de água – 00": 0.0,
                "Redução da pressão no abastecimento de água – 00": 0.0,
                "Multa em caso de desperdício de água – 00": 0.0,
                "Tarifa/taxa diferenciada para o aumento de consumo de água – 00": 0.0,
                "Fornecimento de caminhões pipa – 00": 0.0,
                "Drenagem pluvial – 00": 0.0,
                "Incentivo à instalação de sistema para água de reúso – 05": 5.0,
                "Redução das perdas na distribuição de água – 00": 0.0,
                "Desassoreamento – 00": 0.0,
                "Divulgação dos resultados obtidos com o contingenciamento, situação dos mananciais/represas/ETAs – 10": 10.0
            }
    
            sel61 = []
            pts61 = 0.0
            texto_seguro_61 = str(d61["valor"]) if d61["valor"] not in ["", "[]"] else ""
    
            for i, (txt, pts) in enumerate(opts61.items()):
                marcado = (txt in texto_seguro_61) if texto_seguro_61 else False
                if st.checkbox(txt, value=marcado, key=f"q61_opt_{i}_{ano_sel}"):
                    sel61.append(txt)
                    pts61 += pts

        with col2:
            l61 = st.text_area("Link/Evidência (6.1):", value=d61.get("link", ""), key=f"l61_{ano_sel}", height=150)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_61_atuais = re.findall(r'(https?://[^\s]+)', l61)
            if links_61_atuais:
                botoes_61 = " | ".join([f"🔗 [{u}]({u})" for u in links_61_atuais])
                st.markdown(f"**Links Ativos:** {botoes_61}")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 6.1
        if str(sel61) != d61["valor"] or l61 != d61["link"]:
            save_resp("6.1", str(sel61), float(pts61), l61)
            
            if links_61_atuais:
                links_61_antigos = re.findall(r'(https?://[^\s]+)', d61["link"])
                if links_61_atuais != links_61_antigos:
                    modal_aviso_link("6.1", links_61_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("6.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)


        # -------------------------------------------------------------------------
        # --- QUESITO 6.2 (SETORES ATENDIDOS) --------------------------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 6.2")
        st.write("**Em quais setores existem ações e medidas de contingenciamento específicos para provisão de água potável?**")
 
        d62 = res_data.get("6.2", {"valor": "", "pontos": 0.0, "link": ""})

        col1, col2 = st.columns([1, 2])
        with col1:
            opts62 = {
                "Rede Municipal de Educação – 10": 10.0,
                "Rede Municipal da Atenção Básica da Saúde – 10": 10.0,
                "Outro – 05": 5.0
            }
    
            sel62 = []
            pts62 = 0.0
            texto_seguro_62 = str(d62["valor"]) if d62["valor"] not in ["", "[]"] else ""
    
            for i, (txt, pts) in enumerate(opts62.items()):
                marcado = (txt in texto_seguro_62) if texto_seguro_62 else False
                if st.checkbox(txt, value=marcado, key=f"q62_opt_{i}_{ano_sel}"):
                    sel62.append(txt)
                    pts62 += pts

        with col2:
            l62 = st.text_area("Link/Evidência (6.2):", value=d62.get("link", ""), key=f"l62_{ano_sel}", height=120)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_62_atuais = re.findall(r'(https?://[^\s]+)', l62)
            if links_62_atuais:
                botoes_62 = " | ".join([f"🔗 [{u}]({u})" for u in links_62_atuais])
                st.markdown(f"**Links Ativos:** {botoes_62}")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 6.2
        if str(sel62) != d62["valor"] or l62 != d62["link"]:
            save_resp("6.2", str(sel62), float(pts62), l62)
            
            if links_62_atuais:
                links_62_antigos = re.findall(r'(https?://[^\s]+)', d62["link"])
                if links_62_atuais != links_62_antigos:
                    modal_aviso_link("6.2", links_62_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("6.2", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # --- SEÇÃO 7: SANEAMENTO ---
        st.divider()
        st.header("7.0 Saneamento Básico")
        
        # -------------------------------------------------------------------------
        # --- QUESITO 7.0 (INSTITUIÇÃO DO PLANO DE SANEAMENTO) --------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 7.0")
        st.write("**O município possui seu Plano Municipal ou Regional de Saneamento Básico instituído?**")
        
        d70 = res_data.get("7.0", {"valor": None, "link": ""})
        opc70 = ["Sim", "Não"]
        idx70 = opc70.index(d70["valor"]) if d70["valor"] in opc70 else None
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r70 = st.radio("Selecione 7.0:", opc70, index=idx70, key=f"q70_{ano_sel}")
        with col2:
            l70 = st.text_area("Link/Evidência (7.0):", value=d70.get("link", ""), key=f"l70_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_70_atuais = re.findall(r'(https?://[^\s]+)', l70)
            if links_70_atuais:
                botoes_70 = " | ".join([f"🔗 [{u}]({u})" for u in links_70_atuais])
                st.markdown(f"**Links Ativos:** {botoes_70}")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 7.0
        if r70 and (r70 != d70["valor"] or l70 != d70["link"]):
            save_resp("7.0", r70, 0.0, l70)
            
            if links_70_atuais:
                links_70_antigos = re.findall(r'(https?://[^\s]+)', d70["link"])
                if links_70_atuais != links_70_antigos:
                    modal_aviso_link("7.0", links_70_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("7.0", res_data)
        st.markdown('</div>', unsafe_allow_html=True)


        # -------------------------------------------------------------------------
        # --- QUESITO 7.1 (INSTRUMENTO NORMATIVO DO PLANO) -----------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 7.1")
        st.write("**Informe o Instrumento normativo, Número e Data da publicação:**")

        d71 = res_data.get("7.1", {"valor": "", "link": ""})

        try:
            parts = d71["valor"].split("|")
            inst_salvo = parts[0].split(":")[1].strip()
            num_salvo = parts[1].split(":")[1].strip()
            data_salvo = parts[2].split(":")[1].strip()
        except:
            inst_salvo, num_salvo, data_salvo = "", "", ""

        col1, col2 = st.columns([1, 2])
        with col1:
            inst_normativo = st.text_input("Instrumento normativo:", value=inst_salvo, key=f"q71_inst_{ano_sel}")
            num_normativo = st.text_input("Número:", value=num_salvo, key=f"q71_num_{ano_sel}")
            data_pub = st.text_input("Data da publicação:", value=data_salvo, key=f"q71_data_{ano_sel}")

        with col2:
            l71 = st.text_area("Link/Evidência (7.1):", value=d71.get("link", ""), key=f"l71_{ano_sel}", height=120)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_71_atuais = re.findall(r'(https?://[^\s]+)', l71)
            if links_71_atuais:
                botoes_71 = " | ".join([f"🔗 [{u}]({u})" for u in links_71_atuais])
                st.markdown(f"**Links Ativos:** {botoes_71}")

        valor_ajustado_71 = f"Inst: {inst_normativo} | Nº: {num_normativo} | Data: {data_pub}"

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 7.1
        if inst_normativo or num_normativo or data_pub or d71["valor"] != "":
            if valor_ajustado_71 != d71["valor"] or l71 != d71["link"]:
                save_resp("7.1", valor_ajustado_71, 0.0, l71)
                
                if links_71_atuais:
                    links_71_antigos = re.findall(r'(https?://[^\s]+)', d71["link"])
                    if links_71_atuais != links_71_antigos:
                        modal_aviso_link("7.1", links_71_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()

        bloco_comentarios("7.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)


        # -------------------------------------------------------------------------
        # --- QUESITO 7.2 (PÁGINA ELETRÔNICA DO PLANO) -----------------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 7.2")
        st.write("**Informe a página eletrônica (link na internet) do Plano Municipal ou Regional de Saneamento Básico:**")
        st.caption("Se não estiver disponível na internet, insira o texto **XYZ** no campo de resposta.")

        d72 = res_data.get("7.2", {"valor": "", "pontos": 0.0, "link": ""})

        col1, col2 = st.columns([1, 2])
        with col1:
            link_plano = st.text_input("Link do Plano ou XYZ:", value=d72.get("valor", ""), key=f"q72_link_{ano_sel}")
            
            texto_validado = link_plano.strip().upper()
            if texto_validado == "XYZ" or texto_validado == "":
                pts72 = 0.0
            else:
                pts72 = 2.0

            st.metric(label="Pontuação", value=f"{pts72:.1f} pts")

        with col2:
            l72 = st.text_area("Link/Evidência (7.2):", value=d72.get("link", ""), key=f"l72_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_72_atuais = re.findall(r'(https?://[^\s]+)', l72)
            if links_72_atuais:
                botoes_72 = " | ".join([f"🔗 [{u}]({u})" for u in links_72_atuais])
                st.markdown(f"**Links Ativos:** {botoes_72}")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 7.2
        if link_plano != d72["valor"] or l72 != d72["link"]:
            save_resp("7.2", link_plano, float(pts72), l72)
            
            if links_72_atuais:
                links_72_antigos = re.findall(r'(https?://[^\s]+)', d72["link"])
                if links_72_atuais != links_72_antigos:
                    modal_aviso_link("7.2", links_72_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("7.2", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # -------------------------------------------------------------------------
        # --- QUESITO 7.3 (METAS DE ABASTECIMENTO DE ÁGUA) -----------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 7.3")
        st.write("**O Plano Municipal ou Regional de Saneamento Básico possui metas de abastecimento de água potável?**")

        d73 = res_data.get("7.3", {"valor": None, "pontos": 0.0, "link": ""})

        col1, col2 = st.columns([1, 2])
        with col1:
            opts73 = {
                "Sim – 10": 10.0,
                "Não – 00": 0.0
            }
            lista_opts73 = list(opts73.keys())
            idx_salvo73 = lista_opts73.index(d73["valor"]) if d73["valor"] in lista_opts73 else None
            
            sel73 = st.radio("Selecione uma opção:", options=lista_opts73, index=idx_salvo73, key=f"q73_{ano_sel}")

        with col2:
            l73 = st.text_area("Link/Evidência (7.3):", value=d73.get("link", ""), key=f"l73_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_73_atuais = re.findall(r'(https?://[^\s]+)', l73)
            if links_73_atuais:
                botoes_73 = " | ".join([f"🔗 [{u}]({u})" for u in links_73_atuais])
                st.markdown(f"**Links Ativos:** {botoes_73}")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 7.3
        if sel73 and (sel73 != d73["valor"] or l73 != d73["link"]):
            pts73 = opts73[sel73]
            save_resp("7.3", sel73, float(pts73), l73)
            
            if links_73_atuais:
                links_73_antigos = re.findall(r'(https?://[^\s]+)', d73["link"])
                if links_73_atuais != links_73_antigos:
                    modal_aviso_link("7.3", links_73_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("7.3", res_data)
        st.markdown('</div>', unsafe_allow_html=True)


        # -------------------------------------------------------------------------
        # --- QUESITO 7.3.1 (DETALHAMENTO DAS METAS) -----------------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 7.3.1")
        st.write("**Assinale quais as metas estabelecidas sobre abastecimento de água potável:**")

        d731 = res_data.get("7.3.1", {"valor": "", "pontos": 0.0, "link": ""})

        col1, col2 = st.columns([1, 2])
        with col1:
            opts731 = {
                "Metas de expansão do serviço de abastecimento de água – 00": 0.0,
                "Metas de redução de perdas na distribuição de água tratada – 2,5": 2.5,
                "Metas de qualidade na prestação do serviço de abastecimento de água – 2,5": 2.5,
                "Metas de eficiência e de uso racional da água – 2,5": 2.5,
                "Estabelecimento de volume mínimo de abastecimento de água per capita – 2,5": 2.5,
                "Estabelecimento de direitos e deveres dos usuários – 2,5": 2.5,
                "Meta de universalização do abastecimento de água potável até 31 de dezembro de 2033 – 2,5": 2.5,
                "Estabelecimento de cronograma para o atingimento das metas assinaladas acima – 05": 5.0
            }
            
            sel731 = []
            pts731 = 0.0
            texto_seguro_731 = str(d731["valor"]) if d731["valor"] not in ["", "[]"] else ""
            
            for i, (txt, pts) in enumerate(opts731.items()):
                marcado = (txt in texto_seguro_731) if texto_seguro_731 else False
                if st.checkbox(txt, value=marcado, key=f"q731_opt_{i}_{ano_sel}"):
                    sel731.append(txt)
                    pts731 += pts

        with col2:
            l731 = st.text_area("Link/Evidência (7.3.1):", value=d731.get("link", ""), key=f"l731_{ano_sel}", height=150)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_731_atuais = re.findall(r'(https?://[^\s]+)', l731)
            if links_731_atuais:
                botoes_731 = " | ".join([f"🔗 [{u}]({u})" for u in links_731_atuais])
                st.markdown(f"**Links Ativos:** {botoes_731}")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 7.3.1
        if str(sel731) != d731["valor"] or l731 != d731["link"]:
            save_resp("7.3.1", str(sel731), float(pts731), l731)
            
            if links_731_atuais:
                links_731_antigos = re.findall(r'(https?://[^\s]+)', d731["link"])
                if links_731_atuais != links_731_antigos:
                    modal_aviso_link("7.3.1", links_731_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("7.3.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)


        # -------------------------------------------------------------------------
        # --- QUESITO 7.3.2 (DATA DE UNIVERSALIZAÇÃO) -----------------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 7.3.2")
        st.write("**Qual a data prevista para universalização do abastecimento de água potável no município?**")
        st.caption("Caso já tenha sido universalizado, informe a data **01/01/2001**.")

        d732 = res_data.get("7.3.2", {"valor": "31/12/2033", "pontos": 0.0, "link": ""})

        try:
            dia_salvo, mes_salvo, ano_salvo = map(int, d732["valor"].split("/"))
        except:
            dia_salvo, mes_salvo, ano_salvo = 31, 12, 2033

        col1, col2 = st.columns([1, 2])
        with col1:
            c_dia, c_mes, c_ano = st.columns(3)
            with c_dia:
                dia = st.number_input("Dia", min_value=1, max_value=31, value=dia_salvo, key=f"q732_d_{ano_sel}")
            with c_mes:
                mes = st.number_input("Mês", min_value=1, max_value=12, value=mes_salvo, key=f"q732_m_{ano_sel}")
            with c_ano:
                ano = st.number_input("Ano", min_value=2000, max_value=2100, value=ano_salvo, key=f"q732_a_{ano_sel}")

            if ano > 2033 or (ano == 2033 and mes == 12 and dia > 31) or (ano == 2033 and mes > 12):
                pts732 = -5.0
            else:
                pts732 = 0.0

            st.metric(label="Pontuação", value=f"{pts732:.1f} pts")

        with col2:
            l732 = st.text_area("Link/Evidência (7.3.2):", value=d732.get("link", ""), key=f"l732_{ano_sel}", height=120)
            
            # SUPORTE MULTI-LINKS ATIVOS (Nomenclatura corrigida de 722 para 732)
            links_732_atuais = re.findall(r'(https?://[^\s]+)', l732)
            if links_732_atuais:
                botoes_732 = " | ".join([f"🔗 [{u}]({u})" for u in links_732_atuais])
                st.markdown(f"**Links Ativos:** {botoes_732}")

        data_formatada = f"{dia:02d}/{mes:02d}/{ano}"

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 7.3.2
        if d732["valor"] != "" or (dia != 31 or mes != 12 or ano != 2033):
            if data_formatada != d732["valor"] or l732 != d732["link"]:
                save_resp("7.3.2", data_formatada, float(pts732), l732)
                
                if links_732_atuais:
                    links_732_antigos = re.findall(r'(https?://[^\s]+)', d732["link"])
                    if links_732_atuais != links_732_antigos:
                        modal_aviso_link("7.3.2", links_732_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()

        bloco_comentarios("7.3.2", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # -------------------------------------------------------------------------
        # --- QUESITO 7.4 (METAS DE COLETA DE ESGOTO) -----------------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 7.4")
        st.write("**O Plano Municipal ou Regional de Saneamento Básico possui metas de coleta de esgoto?**")

        d74 = res_data.get("7.4", {"valor": None, "pontos": 0.0, "link": ""})

        col1, col2 = st.columns([1, 2])
        with col1:
            opts74 = {
                "Sim – 10": 10.0,
                "Não – 00": 0.0
            }
            lista_opts74 = list(opts74.keys())
            idx_salvo74 = lista_opts74.index(d74["valor"]) if d74["valor"] in lista_opts74 else None
            
            sel74 = st.radio("Selecione uma opção:", options=lista_opts74, index=idx_salvo74, key=f"q74_{ano_sel}")

        with col2:
            l74 = st.text_area("Link/Evidência (7.4):", value=d74.get("link", ""), key=f"l74_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_74_atuais = re.findall(r'(https?://[^\s]+)', l74)
            if links_74_atuais:
                botoes_74 = " | ".join([f"🔗 [{u}]({u})" for u in links_74_atuais])
                st.markdown(f"**Links Ativos:** {botoes_74}")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 7.4
        if sel74 and (sel74 != d74["valor"] or l74 != d74["link"]):
            pts74 = opts74[sel74]
            save_resp("7.4", sel74, float(pts74), l74)
            
            if links_74_atuais:
                links_74_antigos = re.findall(r'(https?://[^\s]+)', d74["link"])
                if links_74_atuais != links_74_antigos:
                    modal_aviso_link("7.4", links_74_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("7.4", res_data)
        st.markdown('</div>', unsafe_allow_html=True)


        # -------------------------------------------------------------------------
        # --- QUESITO 7.4.1 (DETALHAMENTO DAS METAS DE ESGOTO) --------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 7.4.1")
        st.write("**Assinale quais as metas estabelecidas sobre coleta de esgoto:**")

        d741 = res_data.get("7.4.1", {"valor": "", "pontos": 0.0, "link": ""})

        col1, col2 = st.columns([1, 2])
        with col1:
            opts741 = {
                "Metas de expansão do serviço de coleta de esgoto – 00": 0.0,
                "Metas de qualidade na prestação do serviço de coleta de esgoto – 3,5": 3.5,
                "Meta do reúso de efluentes sanitários – 3,5": 3.5,
                "Estabelecimento de direitos e deveres dos usuários – 3,5": 3.5,
                "Meta de universalização da coleta de esgoto até 31 de dezembro de 2033 – 3,5": 3.5,
                "Estabelecimento de cronograma para o atingimento das metas assinaladas acima – 06": 6.0
            }
    
            sel741 = []
            pts741 = 0.0
            texto_seguro_741 = str(d741["valor"]) if d741["valor"] not in ["", "[]"] else ""
    
            for i, (txt, pts) in enumerate(opts741.items()):
                marcado = (txt in texto_seguro_741) if texto_seguro_741 else False
                if st.checkbox(txt, value=marcado, key=f"q741_opt_{i}_{ano_sel}"):
                    sel741.append(txt)
                    pts741 += pts

        with col2:
            l741 = st.text_area("Link/Evidência (7.4.1):", value=d741.get("link", ""), key=f"l741_{ano_sel}", height=150)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_741_atuais = re.findall(r'(https?://[^\s]+)', l741)
            if links_741_atuais:
                botoes_741 = " | ".join([f"🔗 [{u}]({u})" for u in links_741_atuais])
                st.markdown(f"**Links Ativos:** {botoes_741}")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 7.4.1
        if str(sel741) != d741["valor"] or l741 != d741["link"]:
            save_resp("7.4.1", str(sel741), float(pts741), l741)
            
            if links_741_atuais:
                links_741_antigos = re.findall(r'(https?://[^\s]+)', d741["link"])
                if links_741_atuais != links_741_antigos:
                    modal_aviso_link("7.4.1", links_741_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("7.4.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)


        # -------------------------------------------------------------------------
        # --- QUESITO 7.4.2 (DATA DE UNIVERSALIZAÇÃO DO ESGOTO) -------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 7.4.2")
        st.write("**Qual a data prevista para universalização da coleta de esgoto no município?**")
        st.caption("Caso já tenha sido universalizado, informe a data **01/01/2001**.")

        d742 = res_data.get("7.4.2", {"valor": "31/12/2033", "pontos": 0.0, "link": ""})

        try:
            dia_salvo, mes_salvo, ano_salvo = map(int, d742["valor"].split("/"))
        except:
            dia_salvo, mes_salvo, ano_salvo = 31, 12, 2033

        col1, col2 = st.columns([1, 2])
        with col1:
            c_dia, c_mes, c_ano = st.columns(3)
            with c_dia:
                dia = st.number_input("Dia", min_value=1, max_value=31, value=dia_salvo, key=f"q742_d_{ano_sel}")
            with c_mes:
                mes = st.number_input("Mês", min_value=1, max_value=12, value=mes_salvo, key=f"q742_m_{ano_sel}")
            with c_ano:
                ano = st.number_input("Ano", min_value=2000, max_value=2100, value=ano_salvo, key=f"q742_a_{ano_sel}")

            if ano > 2033 or (ano == 2033 and mes == 12 and dia > 31) or (ano == 2033 and mes > 12):
                pts742 = -5.0
            else:
                pts742 = 0.0

            st.metric(label="Pontuação", value=f"{pts742:.1f} pts")

        with col2:
            l742 = st.text_area("Link/Evidência (7.4.2):", value=d742.get("link", ""), key=f"l742_{ano_sel}", height=120)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_742_atuais = re.findall(r'(https?://[^\s]+)', l742)
            if links_742_atuais:
                botoes_742 = " | ".join([f"🔗 [{u}]({u})" for u in links_742_atuais])
                st.markdown(f"**Links Ativos:** {botoes_742}")

        data_formatada_742 = f"{dia:02d}/{mes:02d}/{ano}"

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 7.4.2
        if d742["valor"] != "" or (dia != 31 or mes != 12 or ano != 2033):
            if data_formatada_742 != d742["valor"] or l742 != d742["link"]:
                save_resp("7.4.2", data_formatada_742, float(pts742), l742)
                
                if links_742_atuais:
                    links_742_antigos = re.findall(r'(https?://[^\s]+)', d742["link"])
                    if links_742_atuais != links_742_antigos:
                        modal_aviso_link("7.4.2", links_742_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()

        bloco_comentarios("7.4.2", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # -------------------------------------------------------------------------
        # --- QUESITO 7.5 (METAS DE TRATAMENTO DE ESGOTO) -------------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 7.5")
        st.write("**O Plano Municipal ou Regional de Saneamento Básico possui metas de tratamento de esgoto?**")

        d75 = res_data.get("7.5", {"valor": None, "points": 0.0, "link": ""})

        col1, col2 = st.columns([1, 2])
        with col1:
            opts75 = {
                "Sim – 30": 30.0,
                "Não – 00": 0.0
            }
            lista_opts75 = list(opts75.keys())
            idx_salvo75 = lista_opts75.index(d75["valor"]) if d75["valor"] in lista_opts75 else None
            
            sel75 = st.radio("Selecione uma opção:", options=lista_opts75, index=idx_salvo75, key=f"q75_{ano_sel}")

        with col2:
            l75 = st.text_area("Link/Evidência (7.5):", value=d75.get("link", ""), key=f"l75_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_75_atuais = re.findall(r'(https?://[^\s]+)', l75)
            if links_75_atuais:
                botoes_75 = " | ".join([f"🔗 [{u}]({u})" for u in links_75_atuais])
                st.markdown(f"**Links Ativos:** {botoes_75}")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 7.5
        if sel75 and (sel75 != d75["valor"] or l75 != d75["link"]):
            pts75 = opts75[sel75]
            save_resp("7.5", sel75, float(pts75), l75)
            
            if links_75_atuais:
                links_75_antigos = re.findall(r'(https?://[^\s]+)', d75["link"])
                if links_75_atuais != links_75_antigos:
                    modal_aviso_link("7.5", links_75_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("7.5", res_data)
        st.markdown('</div>', unsafe_allow_html=True)


        # -------------------------------------------------------------------------
        # --- QUESITO 7.5.1 (DATA DE UNIVERSALIZAÇÃO DO TRATAMENTO) ---------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 7.5.1")
        st.write("**Qual a data prevista para universalização do tratamento de esgoto no município?**")
        st.caption("Caso já tenha sido universalizado, informe a data **01/01/2001**.")

        d751 = res_data.get("7.5.1", {"valor": "31/12/2033", "pontos": 0.0, "link": ""})

        try:
            dia_salvo, mes_salvo, ano_salvo = map(int, d751["valor"].split("/"))
        except:
            dia_salvo, mes_salvo, ano_salvo = 31, 12, 2033

        col1, col2 = st.columns([1, 2])
        with col1:
            c_dia, c_mes, c_ano = st.columns(3)
            with c_dia:
                dia = st.number_input("Dia", min_value=1, max_value=31, value=dia_salvo, key=f"q751_d_{ano_sel}")
            with c_mes:
                mes = st.number_input("Mês", min_value=1, max_value=12, value=mes_salvo, key=f"q751_m_{ano_sel}")
            with c_ano:
                ano = st.number_input("Ano", min_value=2000, max_value=2100, value=ano_salvo, key=f"q751_a_{ano_sel}")

            if ano > 2033 or (ano == 2033 and mes == 12 and dia > 31) or (ano == 2033 and mes > 12):
                pts751 = -5.0
            else:
                pts751 = 0.0

            st.metric(label="Pontuação", value=f"{pts751:.1f} pts")

        with col2:
            l751 = st.text_area("Link/Evidência (7.5.1):", value=d751.get("link", ""), key=f"l751_{ano_sel}", height=120)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_751_atuais = re.findall(r'(https?://[^\s]+)', l751)
            if links_751_atuais:
                botoes_751 = " | ".join([f"🔗 [{u}]({u})" for u in links_751_atuais])
                st.markdown(f"**Links Ativos:** {botoes_751}")

        data_formatada_751 = f"{dia:02d}/{mes:02d}/{ano}"

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 7.5.1
        if d751["valor"] != "" or (dia != 31 or mes != 12 or ano != 2033):
            if data_formatada_751 != d751["valor"] or l751 != d751["link"]:
                save_resp("7.5.1", data_formatada_751, float(pts751), l751)
                
                if links_751_atuais:
                    links_751_antigos = re.findall(r'(https?://[^\s]+)', d751["link"])
                    if links_751_atuais != links_751_antigos:
                        modal_aviso_link("7.5.1", links_751_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()

        bloco_comentarios("7.5.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)


        # -------------------------------------------------------------------------
        # --- QUESITO 7.6 (METAS DE DRENAGEM URBANAS) -----------------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 7.6")
        st.write("**O Plano Municipal ou Regional de Saneamento Básico possui metas de drenagem e manejo de águas pluviais urbanas?**")

        d76 = res_data.get("7.6", {"valor": None, "pontos": 0.0, "link": ""})

        col1, col2 = st.columns([1, 2])
        with col1:
            opts76 = {
                "Sim": 0.0,
                "Não": 0.0
            }
            lista_opts76 = list(opts76.keys())
            idx_salvo76 = lista_opts76.index(d76["valor"]) if d76["valor"] in lista_opts76 else None
            
            sel76 = st.radio("Selecione uma opção:", options=lista_opts76, index=idx_salvo76, key=f"q76_{ano_sel}")

        with col2:
            l76 = st.text_area("Link/Evidência (7.6):", value=d76.get("link", ""), key=f"l76_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_76_atuais = re.findall(r'(https?://[^\s]+)', l76)
            if links_76_atuais:
                botoes_76 = " | ".join([f"🔗 [{u}]({u})" for u in links_76_atuais])
                st.markdown(f"**Links Ativos:** {botoes_76}")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 7.6
        if sel76 and (sel76 != d76["valor"] or l76 != d76["link"]):
            pts76 = opts76[sel76]
            save_resp("7.6", sel76, float(pts76), l76)
            
            if links_76_atuais:
                links_76_antigos = re.findall(r'(https?://[^\s]+)', d76["link"])
                if links_76_atuais != links_76_antigos:
                    modal_aviso_link("7.6", links_76_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("7.6", res_data)
        st.markdown('</div>', unsafe_allow_html=True)


        # -------------------------------------------------------------------------
        # --- QUESITO 7.6.1 (DETALHAMENTO DAS METAS DE DRENAGEM) ------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 7.6.1")
        st.write("**Assinale quais as metas estabelecidas sobre drenagem e manejo de águas pluviais urbanas:**")

        d761 = res_data.get("7.6.1", {"valor": "", "pontos": 0.0, "link": ""})

        col1, col2 = st.columns([1, 2])
        with col1:
            opts761 = {
                "Metas de expansão do serviço de drenagem e manejo de águas pluviais urbanas": 0.0,
                "Metas de qualidade na prestação do serviço de drenagem e manejo de águas pluviais urbanas": 0.0,
                "Metas de aproveitamento de águas da chuva": 0.0,
                "Estabelecimento de direitos e deveres dos usuários": 0.0,
                "Estabelecimento de cronograma para o atingimento das metas assinaladas acima": 0.0
            }
    
            sel761 = []
            pts761 = 0.0
            texto_seguro_761 = str(d761["valor"]) if d761["valor"] not in ["", "[]"] else ""
    
            for i, (txt, pts) in enumerate(opts761.items()):
                marcado = (txt in texto_seguro_761) if texto_seguro_761 else False
                if st.checkbox(txt, value=marcado, key=f"q761_opt_{i}_{ano_sel}"):
                    sel761.append(txt)
                    pts761 += pts

        with col2:
            l761 = st.text_area("Link/Evidência (7.6.1):", value=d761.get("link", ""), key=f"l761_{ano_sel}", height=150)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_761_atuais = re.findall(r'(https?://[^\s]+)', l761)
            if links_761_atuais:
                botoes_761 = " | ".join([f"🔗 [{u}]({u})" for u in links_761_atuais])
                st.markdown(f"**Links Ativos:** {botoes_761}")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 7.6.1
        if str(sel761) != d761["valor"] or l761 != d761["link"]:
            save_resp("7.6.1", str(sel761), float(pts761), l761)
            
            if links_761_atuais:
                links_761_antigos = re.findall(r'(https?://[^\s]+)', d761["link"])
                if links_761_atuais != links_761_antigos:
                    modal_aviso_link("7.6.1", links_761_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("7.6.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # -------------------------------------------------------------------------
        # --- QUESITO 7.7 (MONITORAMENTO DE ÁGUA E ESGOTO) ------------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 7.7")
        st.write("**Realiza monitoramento e avaliação das ações e metas relacionadas ao abastecimento de água potável e esgotamento sanitário?**")

        d77 = res_data.get("7.7", {"valor": None, "pontos": 0.0, "link": ""})

        col1, col2 = st.columns([1, 2])
        with col1:
            opts77 = {
                "Sim – 30": 30.0,
                "Não – 00": 0.0
            }
            lista_opts77 = list(opts77.keys())
            idx_salvo77 = lista_opts77.index(d77["valor"]) if d77["valor"] in lista_opts77 else None
            
            sel77 = st.radio("Selecione uma opção:", options=lista_opts77, index=idx_salvo77, key=f"q77_{ano_sel}")

        with col2:
            l77 = st.text_area("Link/Evidência (7.7):", value=d77.get("link", ""), key=f"l77_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_77_atuais = re.findall(r'(https?://[^\s]+)', l77)
            if links_77_atuais:
                botoes_77 = " | ".join([f"🔗 [{u}]({u})" for u in links_77_atuais])
                st.markdown(f"**Links Ativos:** {botoes_77}")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 7.7
        if sel77 and (sel77 != d77["valor"] or l77 != d77["link"]):
            pts77 = opts77[sel77]
            save_resp("7.7", sel77, float(pts77), l77)
            
            if links_77_atuais:
                links_77_antigos = re.findall(r'(https?://[^\s]+)', d77["link"])
                if links_77_atuais != links_77_antigos:
                    modal_aviso_link("7.7", links_77_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("7.7", res_data)
        st.markdown('</div>', unsafe_allow_html=True)


        # -------------------------------------------------------------------------
        # --- QUESITO 7.7.1 (FORMA DE MONITORAMENTO) ------------------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 7.7.1")
        st.write("**De que forma é realizado o monitoramento e avaliação relacionadas ao abastecimento de água potável e esgotamento sanitário?**")

        d771 = res_data.get("7.7.1", {"valor": "", "pontos": 0.0, "link": ""})

        col1, col2 = st.columns([1, 2])
        with col1:
            opts771 = {
                "Relatórios anuais discutidos e/ou publicados": 0.0,
                "Indicadores de eficácia e eficiência": 0.0,
                "Avaliação de recursos aplicados": 0.0,
                "Outro": 0.0
            }
            
            sel771 = []
            pts771 = 0.0
            texto_seguro_771 = str(d771["valor"]) if d771["valor"] not in ["", "[]"] else ""
            
            for i, (txt, pts) in enumerate(opts771.items()):
                marcado = (txt in texto_seguro_771) if texto_seguro_771 else False
                if st.checkbox(txt, value=marcado, key=f"q771_opt_{i}_{ano_sel}"):
                    sel771.append(txt)
                    pts771 += pts

        with col2:
            l771 = st.text_area("Link/Evidência (7.7.1):", value=d771.get("link", ""), key=f"l771_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_771_atuais = re.findall(r'(https?://[^\s]+)', l771)
            if links_771_atuais:
                botoes_771 = " | ".join([f"🔗 [{u}]({u})" for u in links_771_atuais])
                st.markdown(f"**Links Ativos:** {botoes_771}")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 7.7.1
        if str(sel771) != d771["valor"] or l771 != d771["link"]:
            save_resp("7.7.1", str(sel771), float(pts771), l771)
            
            if links_771_atuais:
                links_771_antigos = re.findall(r'(https?://[^\s]+)', d771["link"])
                if links_771_atuais != links_771_antigos:
                    modal_aviso_link("7.7.1", links_771_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("7.7.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # -------------------------------------------------------------------------
        # --- QUESITO 7.8 (CRONOGRAMA DE METAS) -----------------------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 7.8")
        st.write("**O Plano Municipal ou Regional de Saneamento Básico possui cronograma com as metas a serem cumpridas?**")

        d78 = res_data.get("7.8", {"valor": None, "pontos": 0.0, "link": ""})

        col1, col2 = st.columns([1, 2])
        with col1:
            opts78 = {
                "Sim – 20": 20.0,
                "Não – 00": 0.0
            }
            lista_opts78 = list(opts78.keys())
            idx_salvo78 = lista_opts78.index(d78["valor"]) if d78["valor"] in lista_opts78 else None
            
            sel78 = st.radio("Selecione uma opção (7.8):", options=lista_opts78, index=idx_salvo78, key=f"q78_{ano_sel}")

        with col2:
            l78 = st.text_area("Link/Evidência (7.8):", value=d78.get("link", ""), key=f"l78_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_78_atuais = re.findall(r'(https?://[^\s]+)', l78)
            if links_78_atuais:
                botoes_78 = " | ".join([f"🔗 [{u}]({u})" for u in links_78_atuais])
                st.markdown(f"**Links Ativos:** {botoes_78}")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 7.8
        if sel78 and (sel78 != d78["valor"] or l78 != d78["link"]):
            pts78 = opts78[sel78]
            save_resp("7.8", sel78, float(pts78), l78)
            
            if links_78_atuais:
                links_78_antigos = re.findall(r'(https?://[^\s]+)', d78["link"])
                if links_78_atuais != links_78_antigos:
                    modal_aviso_link("7.8", links_78_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("7.8", res_data)
        st.markdown('</div>', unsafe_allow_html=True)


        # -------------------------------------------------------------------------
        # --- QUESITO 7.8.1 (CUMPRIMENTO DOS PRAZOS ESTIPULADOS) ------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 7.8.1")
        st.write("**As metas do Plano relacionadas ao abastecimento de água potável e esgotamento sanitário estão sendo cumpridas no prazo estipulado?**")

        d781 = res_data.get("7.8.1", {"valor": None, "pontos": 0.0, "link": ""})

        col1, col2 = st.columns([1, 2])
        with col1:
            opts781 = {
                "Todas as metas foram cumpridas dentro do prazo – 50": 50.0,
                "A maior parte das metas foram cumpridas dentro do prazo – 30": 30.0,
                "A menor parte das metas foram cumpridas dentro do prazo – 10": 10.0,
                "As metas não foram cumpridas dentro do prazo – 00": 0.0
            }
            lista_opts781 = list(opts781.keys())
            idx_salvo781 = lista_opts781.index(d781["valor"]) if d781["valor"] in lista_opts781 else None
            
            sel781 = st.radio("Selecione uma opção (7.8.1):", options=lista_opts781, index=idx_salvo781, key=f"q781_{ano_sel}")

        with col2:
            l781 = st.text_area("Link/Evidência (7.8.1):", value=d781.get("link", ""), key=f"l781_{ano_sel}", height=120)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_781_atuais = re.findall(r'(https?://[^\s]+)', l781)
            if links_781_atuais:
                botoes_781 = " | ".join([f"🔗 [{u}]({u})" for u in links_781_atuais])
                st.markdown(f"**Links Ativos:** {botoes_781}")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 7.8.1
        if sel781 and (sel781 != d781["valor"] or l781 != d781["link"]):
            pts781 = opts781[sel781]
            save_resp("7.8.1", sel781, float(pts781), l781)
            
            if links_781_atuais:
                links_781_antigos = re.findall(r'(https?://[^\s]+)', d781["link"])
                if links_781_atuais != links_781_antigos:
                    modal_aviso_link("7.8.1", links_781_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("7.8.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)


        # -------------------------------------------------------------------------
        # --- QUESITO 7.8.1.1 (MOTIVOS DO NÃO CUMPRIMENTO) -------------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 7.8.1.1")
        st.write("**Assinale os motivos pelos quais as metas relacionadas ao abastecimento de água potável e esgotamento sanitário não estão sendo cumpridas:**")

        d7811 = res_data.get("7.8.1.1", {"valor": "", "pontos": 0.0, "link": ""})

        col1, col2 = st.columns([1, 2])
        with col1:
            opts7811 = {
                "Falta de recursos orçamentários": 0.0,
                "Falta de aprovação legislativa": 0.0,
                "Atraso na licitação": 0.0,
                "Não realizou licitação necessária": 0.0,
                "Falta de pessoal qualificado": 0.0,
                "Falta de consenso no consórcio intermunicipal": 0.0,
                "Outros": 0.0
            }
            
            sel7811 = []
            pts7811 = 0.0
            texto_seguro_7811 = str(d7811["valor"]) if d7811["valor"] not in ["", "[]"] else ""
            
            for i, (txt, pts) in enumerate(opts7811.items()):
                marcado = (txt in texto_seguro_7811) if texto_seguro_7811 else False
                if st.checkbox(txt, value=marcado, key=f"q7811_opt_{i}_{ano_sel}"):
                    sel7811.append(txt)
                    pts7811 += pts

        with col2:
            l7811 = st.text_area("Link/Evidência (7.8.1.1):", value=d7811.get("link", ""), key=f"l7811_{ano_sel}", height=150)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_7811_atuais = re.findall(r'(https?://[^\s]+)', l7811)
            if links_7811_atuais:
                botoes_7811 = " | ".join([f"🔗 [{u}]({u})" for u in links_7811_atuais])
                st.markdown(f"**Links Ativos:** {botoes_7811}")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 7.8.1.1
        if str(sel7811) != d7811["valor"] or l7811 != d7811["link"]:
            save_resp("7.8.1.1", str(sel7811), float(pts7811), l7811)
            
            if links_7811_atuais:
                links_7811_antigos = re.findall(r'(https?://[^\s]+)', d7811["link"])
                if links_7811_atuais != links_7811_antigos:
                    modal_aviso_link("7.8.1.1", links_7811_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("7.8.1.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # -------------------------------------------------------------------------
        # --- QUESITO 7.9 (ÁREAS PRIORITÁRIAS / CRÍTICAS) -------------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 7.9")
        st.write("**Possui previsão para áreas prioritárias/críticas de abastecimento de água potável e esgotamento sanitário do município?**")
        st.caption("Ex.: Áreas com assentamentos habitacionais precários, corpos de água degradados (em especial nas regiões de mananciais) ou áreas vulneráveis quanto aos indicadores de saúde pública.")

        d79 = res_data.get("7.9", {"valor": None, "pontos": 0.0, "link": ""})

        col1, col2 = st.columns([1, 2])
        with col1:
            opts79 = {
                "Sim – 03": 3.0,
                "Não – 00": 0.0,
                "Não há áreas prioritárias/críticas no município – 03": 3.0
            }
            lista_opts79 = list(opts79.keys())
            idx_salvo79 = lista_opts79.index(d79["valor"]) if d79["valor"] in lista_opts79 else None
            
            sel79 = st.radio("Selecione uma opção (7.9):", options=lista_opts79, index=idx_salvo79, key=f"q79_{ano_sel}")

        with col2:
            l79 = st.text_area("Link/Evidência (7.9):", value=d79.get("link", ""), key=f"l79_{ano_sel}", height=120)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_79_atuais = re.findall(r'(https?://[^\s]+)', l79)
            if links_79_atuais:
                botoes_79 = " | ".join([f"🔗 [{u}]({u})" for u in links_79_atuais])
                st.markdown(f"**Links Ativos:** {botoes_79}")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 7.9
        if sel79 and (sel79 != d79["valor"] or l79 != d79["link"]):
            pts79 = opts79[sel79]
            save_resp("7.9", sel79, float(pts79), l79)
            
            if links_79_atuais:
                links_79_antigos = re.findall(r'(https?://[^\s]+)', d79["link"])
                if links_79_atuais != links_79_antigos:
                    modal_aviso_link("7.9", links_79_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("7.9", res_data)
        st.markdown('</div>', unsafe_allow_html=True)


        # -------------------------------------------------------------------------
        # --- QUESITO 7.10 (ÚLTIMA REVISÃO DO PLANO) ------------------------------
        # -------------------------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 7.10")
        st.write("**Qual a data da última revisão do Plano Municipal ou Regional de Saneamento Básico?**")
        st.caption("Se não houve revisão do plano de saneamento básico, informe a data do início de vigência do plano.")

        d710 = res_data.get("7.10", {"valor": "01/01/2015", "pontos": 0.0, "link": ""})

        try:
            dia_salvo, mes_salvo, ano_salvo = map(int, d710["valor"].split("/"))
        except:
            dia_salvo, mes_salvo, ano_salvo = 1, 1, 2015

        col1, col2 = st.columns([1, 2])
        with col1:
            c_dia, c_mes, c_ano = st.columns(3)
            with c_dia:
                dia = st.number_input("Dia", min_value=1, max_value=31, value=dia_salvo, key=f"q710_d_{ano_sel}")
            with c_mes:
                mes = st.number_input("Mês", min_value=1, max_value=12, value=mes_salvo, key=f"q710_m_{ano_sel}")
            with c_ano:
                ano = st.number_input("Ano", min_value=1900, max_value=2100, value=ano_salvo, key=f"q710_a_{ano_sel}")

            if ano < 2014 or (ano == 2014 and mes < 12) or (ano == 2014 and mes == 12 and dia <= 31):
                pts710 = -30.0
            else:
                pts710 = 0.0

            st.metric(label="Pontuação", value=f"{pts710:.1f} pts")

        with col2:
            l710 = st.text_area("Link/Evidência (7.10):", value=d710.get("link", ""), key=f"l710_{ano_sel}", height=120)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_710_atuais = re.findall(r'(https?://[^\s]+)', l710)
            if links_710_atuais:
                botoes_710 = " | ".join([f"🔗 [{u}]({u})" for u in links_710_atuais])
                st.markdown(f"**Links Ativos:** {botoes_710}")

        data_formatada_710 = f"{dia:02d}/{mes:02d}/{ano}"

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 7.10
        if d710["valor"] != "" or (dia != 1 or mes != 1 or ano != 2015):
            if data_formatada_710 != d710["valor"] or l710 != d710["link"]:
                save_resp("7.10", data_formatada_710, float(pts710), l710)
                
                if links_710_atuais:
                    links_710_antigos = re.findall(r'(https?://[^\s]+)', d710["link"])
                    if links_710_atuais != links_710_antigos:
                        modal_aviso_link("7.10", links_710_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()

        bloco_comentarios("7.10", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # -------------------------------------------------------------------------
        # --- SEÇÃO 8: RESÍDUOS SÓLIDOS -------------------------------------------
        # -------------------------------------------------------------------------
        st.divider()
        st.header("8.0 Gestão de Resíduos Sólidos")
        
        # --- QUESITO 8.0 ---------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 8.0")
        st.write("**Foi elaborado o Plano Municipal ou Regional de Gestão Integrada de Resíduos Sólidos?**")
        
        d80 = res_data.get("8.0", {"valor": None, "link": ""})
        opc80 = ["Sim", "Não"]
        idx80 = opc80.index(d80["valor"]) if d80["valor"] in opc80 else None
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r80 = st.radio("Selecione 8.0:", opc80, index=idx80, key=f"q80_{ano_sel}")
        with col2:
            l80 = st.text_area("Link/Evidência (8.0):", value=d80.get("link", ""), key=f"l80_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_80_atuais = re.findall(r'(https?://[^\s]+)', l80)
            if links_80_atuais:
                botoes_80 = " | ".join([f"🔗 [{u}]({u})" for u in links_80_atuais])
                st.markdown(f"**Links Ativos:** {botoes_80}")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 8.0
        if r80 and (r80 != d80["valor"] or l80 != d80["link"]):
            save_resp("8.0", r80, 0, l80)
            
            if links_80_atuais:
                links_80_antigos = re.findall(r'(https?://[^\s]+)', d80["link"])
                if links_80_atuais != links_80_antigos:
                    modal_aviso_link("8.0", links_80_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("8.0", res_data)
        st.markdown('</div>', unsafe_allow_html=True)


        # --- QUESITO 8.1 ---------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 8.1")
        st.write("**Informe o Instrumento normativo, Número e Data da publicação:**")
        
        d81 = res_data.get("8.1", {"valor": "", "link": ""})
        
        col1, col2 = st.columns([1, 2])
        with col1:
            v81 = st.text_area("Instrumento normativo, Número e Data da publicação (8.1):", value=d81["valor"], key=f"q81_{ano_sel}", height=100)
        with col2:
            # SUPORTE MULTI-LINKS ATIVOS DETECTADOS NO PRÓPRIO CONTEÚDO TEXTUAL
            links_81_atuais = re.findall(r'(https?://[^\s]+)', v81)
            if links_81_atuais:
                botoes_81 = " | ".join([f"🔗 [{u}]({u})" for u in links_81_atuais])
                st.markdown(f"**Links Detectados:** {botoes_81}")
            else:
                st.write("")

        # PROCESSAMENTO DE SALVAMENTO DO QUESITO 8.1
        if v81 != d81["valor"]:
            save_resp("8.1", v81, 0, "")
            
            if links_81_atuais:
                links_81_antigos = re.findall(r'(https?://[^\s]+)', d81["valor"])
                if links_81_atuais != links_81_antigos:
                    modal_aviso_link("8.1", links_81_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("8.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)


        # --- QUESITO 8.2 ---------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 8.2")
        st.write("**Informe a página eletrônica (link na internet) do instrumento normativo do Plano Municipal ou Regional de Gestão Integrada de Resíduos Sólidos:**")
        st.caption("Se não estiver disponível na internet, insira no campo de resposta o texto **XYZ**.")

        d82 = res_data.get("8.2", {"valor": "XYZ", "pontos": 0.0, "link": ""})

        col1, col2 = st.columns([1, 2])
        with col1:
            val82 = st.text_input("Endereço eletrônico (Link) ou XYZ:", value=d82.get("valor", "XYZ"), key=f"q82_{ano_sel}")
            if val82.strip().upper() == "XYZ" or val82.strip() == "":
                pts82 = 0.0
            else:
                pts82 = 2.0
            st.metric(label="Pontuação", value=f"{pts82:.1f} pts")

            # Tratamento de múltiplos links ativos inseridos no campo de valor principal
            links_v82_atuais = re.findall(r'(https?://[^\s]+)', val82)
            if links_v82_atuais:
                botoes_v82 = " | ".join([f"🔗 [{u}]({u})" for u in links_v82_atuais])
                st.markdown(f"**Links do Plano:** {botoes_v82}")

        with col2:
            l82 = st.text_area("Link/Evidência Adicional (8.2):", value=d82.get("link", ""), key=f"l82_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS NO CAMPO DE EVIDÊNCIA ADICIONAL
            links_82_atuais = re.findall(r'(https?://[^\s]+)', l82)
            if links_82_atuais:
                botoes_82 = " | ".join([f"🔗 [{u}]({u})" for u in links_82_atuais])
                st.markdown(f"**Links de Evidência:** {botoes_82}")

        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 8.2
        if val82 != d82["valor"] or l82 != d82["link"]:
            save_resp("8.2", val82, float(pts82), l82)
            
            todos_links_82 = links_v82_atuais + links_82_atuais
            if todos_links_82:
                links_antigos_v82 = re.findall(r'(https?://[^\s]+)', d82["valor"])
                links_antigos_l82 = re.findall(r'(https?://[^\s]+)', d82["link"])
                todos_antigos_82 = links_antigos_v82 + links_antigos_l82
                
                if todos_links_82 != todos_antigos_82:
                    modal_aviso_link("8.2", todos_links_82)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("8.2", res_data)
        st.markdown('</div>', unsafe_allow_html=True)


        # --- QUESITO 8.3 ---------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 8.3")
        st.write("**A Prefeitura realizou a caracterização qualitativa e quantitativa dos resíduos sólidos urbanos gerados no município, identificando ainda sua origem?**")
        
        d83 = res_data.get("8.3", {"valor": None, "pontos": 0.0, "link": ""})
        opc83 = ["Sim – 10", "Não – 00"]
        idx83 = opc83.index(d83["valor"]) if d83["valor"] in opc83 else None
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r83 = st.radio("Selecione 8.3:", opc83, index=idx83, key=f"q83_{ano_sel}")
        with col2:
            l83 = st.text_area("Link/Evidência (8.3):", value=d83.get("link", ""), key=f"l83_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_83_atuais = re.findall(r'(https?://[^\s]+)', l83)
            if links_83_atuais:
                botoes_83 = " | ".join([f"🔗 [{u}]({u})" for u in links_83_atuais])
                st.markdown(f"**Links Ativos:** {botoes_83}")
        
        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 8.3
        pts83 = 10.0 if r83 and "Sim" in r83 else 0.0
        if r83 and (r83 != d83["valor"] or l83 != d83["link"]):
            save_resp("8.3", r83, pts83, l83)
            
            if links_83_atuais:
                links_83_antigos = re.findall(r'(https?://[^\s]+)', d83["link"])
                if links_83_atuais != links_83_antigos:
                    modal_aviso_link("8.3", links_83_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("8.3", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # --- QUESITO SUBORDINADO 8.3.1 -------------------------------------------
        if r83 and "Sim" in r83:
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.write("**8.3.1 Assinale a forma utilizada para caracterizar os resíduos sólidos do município:**")
            d831 = res_data.get("8.3.1", {"valor": "", "pontos": 0.0, "link": ""})
            
            col1_831, col2_831 = st.columns([1, 2])
            with col1_831:
                opts831 = ["Estimativa com base em dados secundários", "Realização de estudo gravimétrico, por amostragem", "Pesquisa de dados primários com medição direta", "Outros"]
                sel831 = []
                pts831 = 0.0
                texto_seguro_831 = str(d831["valor"]) if d831["valor"] not in ["", "[]"] else ""
                
                for opt in opts831:
                    marcado = (opt in texto_seguro_831) if texto_seguro_831 else False
                    if st.checkbox(opt, value=marcado, key=f"q831_{opt}_{ano_sel}"):
                        sel831.append(opt)
            
            with col2_831:
                l831 = st.text_area("Link/Evidência (8.3.1):", value=d831.get("link", ""), key=f"l831_{ano_sel}", height=100)
                
                # SUPORTE MULTI-LINKS ATIVOS
                links_831_atuais = re.findall(r'(https?://[^\s]+)', l831)
                if links_831_atuais:
                    botoes_831 = " | ".join([f"🔗 [{u}]({u})" for u in links_831_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_831}")
            
            # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 8.3.1
            if str(sel831) != d831["valor"] or l831 != d831["link"]:
                save_resp("8.3.1", str(sel831), pts831, l831)
                
                if links_831_atuais:
                    links_831_antigos = re.findall(r'(https?://[^\s]+)', d831["link"])
                    if links_831_atuais != links_831_antigos:
                        modal_aviso_link("8.3.1", links_831_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
                    
            bloco_comentarios("8.3.1", res_data)
            st.markdown('</div>', unsafe_allow_html=True)

        # --- QUESITO 8.4 ---------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 8.4")
        st.write("**Possui cronograma com as metas a serem cumpridas de resíduos sólidos?**")
        
        d84 = res_data.get("8.4", {"valor": None, "pontos": 0, "link": ""})
        opc84 = ["Sim – 20", "Não – 00"]
        idx84 = opc84.index(d84["valor"]) if d84["valor"] in opc84 else None
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r84 = st.radio("Selecione 8.4:", opc84, index=idx84, key=f"q84_{ano_sel}")
        with col2:
            l84 = st.text_area("Link/Evidência (8.4):", value=d84.get("link", ""), key=f"l84_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_84_atuais = re.findall(r'(https?://[^\s]+)', l84)
            if links_84_atuais:
                botoes_84 = " | ".join([f"🔗 [{u}]({u})" for u in links_84_atuais])
                st.markdown(f"**Links Ativos:** {botoes_84}")
        
        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 8.4
        pts84 = 20 if r84 and "Sim" in r84 else 0
        if r84 and (r84 != d84["valor"] or l84 != d84["link"]):
            save_resp("8.4", r84, pts84, l84)
            
            if links_84_atuais:
                links_84_antigos = re.findall(r'(https?://[^\s]+)', d84["link"])
                if links_84_atuais != links_84_antigos:
                    modal_aviso_link("8.4", links_84_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
                
        bloco_comentarios("8.4", res_data)

        # DEPENDÊNCIAS DO QUESITO 8.4 (CASO SEJA "SIM")
        if r84 and "Sim" in r84:
            st.divider()
            
            # --- SUBQUESITO 8.4.1 ------------------------------------------------
            st.write("**8.4.1 Assinale quais as metas estabelecidas sobre resíduos sólidos:**")
            d841 = res_data.get("8.4.1", {"valor": "", "pontos": 0.0, "link": ""})
            
            col1_841, col2_841 = st.columns([1, 2])
            with col1_841:
                opts841 = {
                    "Metas de redução da geração de resíduos sólidos na fonte – 2,5": 2.5, 
                    "Metas de coleta seletiva – 02": 2.0, 
                    "Metas de redução de resíduos sólidos secos dispostos em aterros – 2,5": 2.5, 
                    "Metas de redução de resíduos sólidos úmidos dispostos em aterros – 2,5": 2.5, 
                    "Outro – 0,5": 0.5
                }
                sel841 = []
                pts841 = 0.0
                texto_seguro_841 = str(d841["valor"]) if d841["valor"] not in ["", "[]"] else ""
                for txt, pts in opts841.items():
                    marcado = (txt in texto_seguro_841) if texto_seguro_841 else False
                    if st.checkbox(txt, value=marcado, key=f"q841_{txt}_{ano_sel}"):
                        sel841.append(txt)
                        pts841 += pts
            with col2_841:
                l841 = st.text_area("Link/Evidência (8.4.1):", value=d841.get("link", ""), key=f"l841_{ano_sel}", height=100)
                
                # SUPORTE MULTI-LINKS ATIVOS
                links_841_atuais = re.findall(r'(https?://[^\s]+)', l841)
                if links_841_atuais:
                    botoes_841 = " | ".join([f"🔗 [{u}]({u})" for u in links_841_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_841}")
            
            # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 8.4.1
            if str(sel841) != d841["valor"] or l841 != d841["link"]:
                save_resp("8.4.1", str(sel841), float(pts841), l841)
                
                if links_841_atuais:
                    links_841_antigos = re.findall(r'(https?://[^\s]+)', d841["link"])
                    if links_841_atuais != links_841_antigos:
                        modal_aviso_link("8.4.1", links_841_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
                    
            bloco_comentarios("8.4.1", res_data)
            st.divider()

            # --- SUBQUESITO 8.4.2 ------------------------------------------------
            st.write("**8.4.2 Realiza monitoramento e avaliação das ações e metas de resíduos sólidos?**")
            d842 = res_data.get("8.4.2", {"valor": None, "pontos": 0, "link": ""})
            opc842 = ["Sim – 30", "Não – 00"]
            idx842 = opc842.index(d842["valor"]) if d842["valor"] in opc842 else None
            
            col1_842, col2_842 = st.columns([1, 2])
            with col1_842:
                r842 = st.radio("Selecione 8.4.2:", opc842, index=idx842, key=f"q842_{ano_sel}")
            with col2_842:
                l842 = st.text_area("Link/Evidência (8.4.2):", value=d842.get("link", ""), key=f"l842_{ano_sel}", height=100)
                
                # SUPORTE MULTI-LINKS ATIVOS
                links_842_atuais = re.findall(r'(https?://[^\s]+)', l842)
                if links_842_atuais:
                    botoes_842 = " | ".join([f"🔗 [{u}]({u})" for u in links_842_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_842}")
            
            # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 8.4.2
            pts842 = 30 if r842 and "Sim" in r842 else 0
            if r842 and (r842 != d842["valor"] or l842 != d842["link"]):
                save_resp("8.4.2", r842, pts842, l842)
                
                if links_842_atuais:
                    links_842_antigos = re.findall(r'(https?://[^\s]+)', d842["link"])
                    if links_842_atuais != links_842_antigos:
                        modal_aviso_link("8.4.2", links_842_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
                    
            bloco_comentarios("8.4.2", res_data)

            # SUBQUESITO CONDICIONAL VIA 8.4.2 (FORMA DE MONITORAMENTO)
            if r842 and "Sim" in r842:
                st.write("**8.4.2.1 De que forma é realizado o monitoramento e avaliação das ações e metas de resíduos sólidos?**")
                d8421 = res_data.get("8.4.2.1", {"valor": "", "pontos": 0, "link": ""})
                
                col1_8421, col2_8421 = st.columns([1, 2])
                with col1_8421:
                    # Lista definida de forma estática e segura
                    opts8421 = [
                        "Relatórios anuais discutidos e/ou publicados", 
                        "Indicadores de eficácia e eficiência", 
                        "Avaliação de recursos aplicados", 
                        "Outros"
                    ]
                    sel8421 = []
                    pts8421 = 0
                    texto_seguro_8421 = str(d8421["valor"]) if d8421["valor"] not in ["", "[]"] else ""
                    
                    # Forçando strings isoladas no escopo do loop para evitar conflitos
                    for item_opt in opts8421:
                        marcado = (item_opt in texto_seguro_8421) if texto_seguro_8421 else False
                        if st.checkbox(item_opt, value=marcado, key=f"q8421_{item_opt}_{ano_sel}"):
                            sel8421.append(item_opt)
                            
                with col2_8421:
                    l8421 = st.text_area("Link/Evidência (8.4.2.1):", value=d8421.get("link", ""), key=f"l8421_{ano_sel}", height=100)
                    
                    # SUPORTE MULTI-LINKS ATIVOS
                    links_8421_atuais = re.findall(r'(https?://[^\s]+)', l8421)
                    if links_8421_atuais:
                        botoes_8421 = " | ".join([f"🔗 [{u}]({u})" for u in links_8421_atuais])
                        st.markdown(f"**Links Ativos:** {botoes_8421}")
                
                # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 8.4.2.1
                if str(sel8421) != d8421["valor"] or l8421 != d8421["link"]:
                    save_resp("8.4.2.1", str(sel8421), pts8421, l8421)
                    
                    if links_8421_atuais:
                        links_8421_antigos = re.findall(r'(https?://[^\s]+)', d8421["link"])
                        if links_8421_atuais != links_8421_antigos:
                            if 'modal_aviso_link' in globals():
                                modal_aviso_link("8.4.2.1", links_8421_atuais)
                            else:
                                st.rerun()
                        else:
                            st.rerun()
                    else:
                        st.rerun()
                        
                bloco_comentarios("8.4.2.1", res_data)
            st.divider()

            # --- SUBQUESITO 8.4.3 ------------------------------------------------
            st.write("**8.4.3 As metas do Plano Municipal ou Regional de Gestão Integrada de Resíduos Sólidos estão sendo cumpridas no prazo estipulado?**")
            d843 = res_data.get("8.4.3", {"valor": None, "pontos": 0, "link": ""})
            opc843 = ["Todas as metas foram cumpridas dentro do prazo – 50", "A maior parte das metas foram cumpridas dentro do prazo – 30", "A menor parte das metas foram cumpridas dentro do prazo – 10", "As metas não foram cumpridas dentro do prazo – 00"]
            idx843 = opc843.index(d843["valor"]) if d843["valor"] in opc843 else None
            
            col1_843, col2_843 = st.columns([1, 2])
            with col1_843:
                r843 = st.radio("Selecione 8.4.3:", opc843, index=idx843, key=f"q843_{ano_sel}")
            with col2_843:
                l843 = st.text_area("Link/Evidência (8.4.3):", value=d843.get("link", ""), key=f"l843_{ano_sel}", height=100)
                
                # SUPORTE MULTI-LINKS ATIVOS
                links_843_atuais = re.findall(r'(https?://[^\s]+)', l843)
                if links_843_atuais:
                    botoes_843 = " | ".join([f"🔗 [{u}]({u})" for u in links_843_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_843}")
            
            pts843 = 0
            if r843:
                if "Todas" in r843: pts843 = 50
                elif "maior parte" in r843: pts843 = 30
                elif "menor parte" in r843: pts843 = 10

            # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 8.4.3
            if r843 and (r843 != d843["valor"] or l843 != d843["link"]):
                save_resp("8.4.3", r843, pts843, l843)
                
                if links_843_atuais:
                    links_843_antigos = re.findall(r'(https?://[^\s]+)', d843["link"])
                    if links_843_atuais != links_843_antigos:
                        modal_aviso_link("8.4.3", links_843_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
                    
            bloco_comentarios("8.4.3", res_data)

            # SUBQUESITO CONDICIONAL VIA 8.4.3 (MOTIVOS DO NÃO CUMPRIMENTO)
            if r843 and "não foram cumpridas" in r843:
                st.write("**8.4.3.1 Assinale os motivos pelos quais as metas do Plano Municipal ou Regional de Gestão Integrada de Resíduos Sólidos não estão sendo cumpridas:**")
                d8431 = res_data.get("8.4.3.1", {"valor": "", "pontos": 0, "link": ""})
                
                col1_8431, col2_8431 = st.columns([1, 2])
                with col1_8431:
                    opts8431 = ["Falta de recursos orçamentários", "Falta de aprovação legislativa", "Atraso na licitação", "Não realizou licitação necessária", "Falta de pessoal qualificado", "Falta de consenso no consórcio intermunicipal", "Outros"]
                    sel8431 = []
                    pts8431 = 0
                    texto_seguro_8431 = str(d8431["valor"]) if d8431["valor"] not in ["", "[]"] else ""
                    for opt in opts8431:
                        marcado = (opt in texto_seguro_8431) if texto_seguro_8431 else False
                        if st.checkbox(opt, value=marcado, key=f"q8431_{opt}_{ano_sel}"):
                            sel8431.append(opt)
                with col2_8431:
                    l8431 = st.text_area("Link/Evidência (8.4.3.1):", value=d8431.get("link", ""), key=f"l8431_{ano_sel}", height=100)
                    
                    # SUPORTE MULTI-LINKS ATIVOS
                    links_8431_atuais = re.findall(r'(https?://[^\s]+)', l8431)
                    if links_8431_atuais:
                        botoes_8431 = " | ".join([f"🔗 [{u}]({u})" for u in links_8431_atuais])
                        st.markdown(f"**Links Ativos:** {botoes_8431}")
                
                # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 8.4.3.1
                if str(sel8431) != d8431["valor"] or l8431 != d8431["link"]:
                    save_resp("8.4.3.1", str(sel8431), pts8431, l8431)
                    
                    if links_8431_atuais:
                        links_8431_antigos = re.findall(r'(https?://[^\s]+)', d8431["link"])
                        if links_8431_atuais != links_8431_antigos:
                            modal_aviso_link("8.4.3.1", links_8431_atuais)
                        else:
                            st.rerun()
                    else:
                        st.rerun()
                        
                bloco_comentarios("8.4.3.1", res_data)
            st.divider()
            
            # --- SUBQUESITO 8.4.4 (ÚLTIMA REVISÃO) --------------------------------
            st.write("**8.4.4 Qual a data da última revisão do Plano Municipal ou Regional de Gestão Integrada de Resíduos Sólidos?**")
            st.caption("Se não houve revisão do plano de gestão integrada de resíduos sólidos, informe a data do início de vigência do plano.")

            d844 = res_data.get("8.4.4", {"valor": "01/01/2015", "pontos": 0.0, "link": ""})

            try:
                dia_salvo, mes_salvo, ano_salvo = map(int, d844["valor"].split("/"))
            except:
                dia_salvo, mes_salvo, ano_salvo = 1, 1, 2015

            col1_844, col2_844 = st.columns([1, 2])
            with col1_844:
                c_dia, c_mes, c_ano = st.columns(3)
                with c_dia:
                    dia844 = st.number_input("Dia", min_value=1, max_value=31, value=dia_salvo, key=f"q844_d_{ano_sel}")
                with c_mes:
                    mes844 = st.number_input("Mês", min_value=1, max_value=12, value=mes_salvo, key=f"q844_m_{ano_sel}")
                with c_ano:
                    ano844 = st.number_input("Ano", min_value=1900, max_value=2100, value=ano_salvo, key=f"q844_a_{ano_sel}")

                if ano844 < 2014 or (ano844 == 2014 and mes844 < 12) or (ano844 == 2014 and mes844 == 12 and dia844 <= 31):
                    pts844 = -30.0
                else:
                    pts844 = 0.0

                st.metric(label="Pontuação", value=f"{pts844:.1f} pts")

            with col2_844:
                l844 = st.text_area("Link/Evidência (8.4.4):", value=d844.get("link", ""), key=f"l844_{ano_sel}", height=120)
                
                # SUPORTE MULTI-LINKS ATIVOS
                links_844_atuais = re.findall(r'(https?://[^\s]+)', l844)
                if links_844_atuais:
                    botoes_844 = " | ".join([f"🔗 [{u}]({u})" for u in links_844_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_844}")

            data_formatada_844 = f"{dia844:02d}/{mes844:02d}/{ano844}"

            # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 8.4.4
            if d844["valor"] != "" or (dia844 != 1 or mes844 != 1 or ano844 != 2015):
                if data_formatada_844 != d844["valor"] or l844 != d844["link"]:
                    save_resp("8.4.4", data_formatada_844, float(pts844), l844)
                    
                    if links_844_atuais:
                        links_844_antigos = re.findall(r'(https?://[^\s]+)', d844["link"])
                        if links_844_atuais != links_844_antigos:
                            modal_aviso_link("8.4.4", links_844_atuais)
                        else:
                            st.rerun()
                    else:
                        st.rerun()

            bloco_comentarios("8.4.4", res_data)
            
        st.markdown('</div>', unsafe_allow_html=True)

        # --- QUESITO 9.0 ---------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 9.0")
        st.write("**A prefeitura municipal realiza a coleta seletiva de resíduos sólidos?**")
        
        d90 = res_data.get("9.0", {"valor": None, "pontos": 0, "link": ""})
        opc90 = ["Sim", "Não"]
        idx90 = opc90.index(d90["valor"]) if d90["valor"] in opc90 else None
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r90 = st.radio("Selecione 9.0:", opc90, index=idx90, key=f"q90_{ano_sel}")
        with col2:
            l90 = st.text_area("Link/Evidência (9.0):", value=d90.get("link", ""), key=f"l90_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_90_atuais = re.findall(r'(https?://[^\s]+)', l90)
            if links_90_atuais:
                botoes_90 = " | ".join([f"🔗 [{u}]({u})" for u in links_90_atuais])
                st.markdown(f"**Links Ativos:** {botoes_90}")
        
        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 9.0
        pts90 = 0 
        if r90 and (r90 != d90["valor"] or l90 != d90["link"]):
            save_resp("9.0", r90, pts90, l90)
            
            if links_90_atuais:
                links_90_antigos = re.findall(r'(https?://[^\s]+)', d90["link"])
                if links_90_atuais != links_90_antigos:
                    modal_aviso_link("9.0", links_90_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
                
        bloco_comentarios("9.0", res_data)

        # DEPENDÊNCIAS DO QUESITO 9.0 (CASO SEJA "SIM")
        if r90 == "Sim":
            st.divider()
            
            # --- SUBQUESITO 9.1 --------------------------------------------------
            st.write("**9.1 A coleta seletiva ocorre de forma programada (determinados os horários e dias da semana)?**")
            d91 = res_data.get("9.1", {"valor": None, "pontos": 0, "link": ""})
            opc91 = ["Sim – 00", "Não – -30 (perde 30 pontos)"]
            idx91 = opc91.index(d91["valor"]) if d91["valor"] in opc91 else None
            
            col1_91, col2_91 = st.columns([1, 2])
            with col1_91:
                r91 = st.radio("Selecione 9.1:", opc91, index=idx91, key=f"q91_{ano_sel}")
            with col2_91:
                l91 = st.text_area("Link/Evidência (9.1):", value=d91.get("link", ""), key=f"l91_{ano_sel}", height=100)
                
                # SUPORTE MULTI-LINKS ATIVOS
                links_91_atuais = re.findall(r'(https?://[^\s]+)', l91)
                if links_91_atuais:
                    botoes_91 = " | ".join([f"🔗 [{u}]({u})" for u in links_91_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_91}")
            
            # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 9.1
            pts91 = 0 if r91 and "Sim" in r91 else -30
            if r91 and (r91 != d91["valor"] or l91 != d91["link"]):
                save_resp("9.1", r91, pts91, l91)
                
                if links_91_atuais:
                    links_91_antigos = re.findall(r'(https?://[^\s]+)', d91["link"])
                    if links_91_atuais != links_91_antigos:
                        modal_aviso_link("9.1", links_91_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
                    
            bloco_comentarios("9.1", res_data)
            st.divider()

            # --- SUBQUESITO 9.2 --------------------------------------------------
            st.write("**9.2 Todas as regiões do município são atendidas pela coleta seletiva?**")
            d92 = res_data.get("9.2", {"valor": None, "pontos": 0, "link": ""})
            opc92 = ["Todos os bairros do município são atendidos – 100", "A maior parte dos bairros são atendidos – 50", "A menor parte dos bairros são atendidos – 10"]
            idx92 = opc92.index(d92["valor"]) if d92["valor"] in opc92 else None
            
            col1_92, col2_92 = st.columns([1, 2])
            with col1_92:
                r92 = st.radio("Selecione 9.2:", opc92, index=idx92, key=f"q92_{ano_sel}")
            with col2_92:
                l92 = st.text_area("Link/Evidência (9.2):", value=d92.get("link", ""), key=f"l92_{ano_sel}", height=100)
                
                # SUPORTE MULTI-LINKS ATIVOS
                links_92_atuais = re.findall(r'(https?://[^\s]+)', l92)
                if links_92_atuais:
                    botoes_92 = " | ".join([f"🔗 [{u}]({u})" for u in links_92_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_92}")
            
            pts92 = 0
            if r92:
                if "Todos" in r92: pts92 = 100
                elif "maior parte" in r92: pts92 = 50
                elif "menor parte" in r92: pts92 = 10

            # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 9.2
            if r92 and (r92 != d92["valor"] or l92 != d92["link"]):
                save_resp("9.2", r92, pts92, l92)
                
                if links_92_atuais:
                    links_92_antigos = re.findall(r'(https?://[^\s]+)', d92["link"])
                    if links_92_atuais != links_92_antigos:
                        modal_aviso_link("9.2", links_92_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
                    
            bloco_comentarios("9.2", res_data)
            st.divider()

            # --- SUBQUESITO 9.3 --------------------------------------------------
            st.write("**9.3 A Prefeitura incentiva e orienta a população por meio de Ações e/ou Campanhas sobre a importância da coleta seletiva?**")
            d93 = res_data.get("9.3", {"valor": None, "pontos": 0, "link": ""})
            opc93 = ["Sim – 05", "Não – 00"]
            idx93 = opc93.index(d93["valor"]) if d93["valor"] in opc93 else None
            
            col1_93, col2_93 = st.columns([1, 2])
            with col1_93:
                r93 = st.radio("Selecione 9.3:", opc93, index=idx93, key=f"q93_{ano_sel}")
            with col2_93:
                l93 = st.text_area("Link/Evidência (9.3):", value=d93.get("link", ""), key=f"l93_{ano_sel}", height=100)
                
                # SUPORTE MULTI-LINKS ATIVOS
                links_93_atuais = re.findall(r'(https?://[^\s]+)', l93)
                if links_93_atuais:
                    botoes_93 = " | ".join([f"🔗 [{u}]({u})" for u in links_93_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_93}")
            
            # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 9.3
            pts93 = 5 if r93 and "Sim" in r93 else 0
            if r93 and (r93 != d93["valor"] or l93 != d93["link"]):
                save_resp("9.3", r93, pts93, l93)
                
                if links_93_atuais:
                    links_93_antigos = re.findall(r'(https?://[^\s]+)', d93["link"])
                    if links_93_atuais != links_93_antigos:
                        modal_aviso_link("9.3", links_93_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
                    
            bloco_comentarios("9.3", res_data)

            # SUBQUESITO CONDICIONAL VIA 9.3 (QUAIS AÇÕES/CAMPANHAS)
            if r93 and "Sim" in r93:
                st.write("**9.3.1 Assinale quais Ações e/ou Campanhas foram realizadas:**")
                d931 = res_data.get("9.3.1", {"valor": "", "pontos": 0.0, "link": ""})
                
                col1_931, col2_931 = st.columns([1, 2])
                with col1_931:
                    opts931 = {
                        "Divulgações em redes sociais e/ou site da prefeitura – 01": 1.0, 
                        "Ações de educação ambiental – 0,5": 0.5, 
                        "Campanhas de conscientização por meio de sinalizações, folders, cartazes, propagandas e materiais impressos – 01": 1.0, 
                        "Projetos de incentivo – 01": 1.0, 
                        "Workshops / Palestras – 0,5": 0.5, 
                        "Instalação de lixeiras seletivas e distribuição de sacolas retornáveis para separação dos resíduos recicláveis – 01": 1.0
                    }
                    sel931 = []
                    pts931 = 0.0
                    texto_seguro_931 = str(d931["valor"]) if d931["valor"] not in ["", "[]"] else ""
                    for txt, pts in opts931.items():
                        marcado = (txt in texto_seguro_931) if texto_seguro_931 else False
                        if st.checkbox(txt, value=marcado, key=f"q931_{txt}_{ano_sel}"):
                            sel931.append(txt)
                            pts931 += pts
                with col2_931:
                    l931 = st.text_area("Link/Evidência (9.3.1):", value=d931.get("link", ""), key=f"l931_{ano_sel}", height=100)
                    
                    # SUPORTE MULTI-LINKS ATIVOS
                    links_931_atuais = re.findall(r'(https?://[^\s]+)', l931)
                    if links_931_atuais:
                        botoes_931 = " | ".join([f"🔗 [{u}]({u})" for u in links_931_atuais])
                        st.markdown(f"**Links Ativos:** {botoes_931}")
                
                # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 9.3.1
                if str(sel931) != d931["valor"] or l931 != d931["link"]:
                    save_resp("9.3.1", str(sel931), float(pts931), l931)
                    
                    if links_931_atuais:
                        links_931_antigos = re.findall(r'(https?://[^\s]+)', d931["link"])
                        if links_931_atuais != links_931_antigos:
                            modal_aviso_link("9.3.1", links_931_atuais)
                        else:
                            st.rerun()
                    else:
                        st.rerun()
                        
                bloco_comentarios("9.3.1", res_data)
                
        st.markdown('</div>', unsafe_allow_html=True)

       # --- QUESITO 10.0 ---------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 10.0")
        st.write("**É realizada a coleta de lixo doméstico (resíduos domiciliares)? Lixo doméstico (resíduos domiciliares) são os resíduos originários de atividades domésticas em residências urbanas**")
        
        d100 = res_data.get("10.0", {"valor": None, "pontos": 0, "link": ""})
        opc100 = ["Sim – 00", "Não – -100 (perde 100 pontos)"]
        idx100 = opc100.index(d100["valor"]) if d100["valor"] in opc100 else None
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r100 = st.radio("Selecione 10.0:", opc100, index=idx100, key=f"q100_{ano_sel}")
        with col2:
            l100 = st.text_area("Link/Evidência (10.0):", value=d100.get("link", ""), key=f"l100_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_100_atuais = re.findall(r'(https?://[^\s]+)', l100)
            if links_100_atuais:
                botoes_100 = " | ".join([f"🔗 [{u}]({u})" for u in links_100_atuais])
                st.markdown(f"**Links Ativos:** {botoes_100}")
        
        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 10.0
        pts100 = 0 if r100 and "Sim" in r100 else -100
        if r100 and (r100 != d100["valor"] or l100 != d100["link"]):
            save_resp("10.0", r100, pts100, l100)
            
            if links_100_atuais:
                links_100_antigos = re.findall(r'(https?://[^\s]+)', d100["link"])
                if links_100_atuais != links_100_antigos:
                    modal_aviso_link("10.0", links_100_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
                
        bloco_comentarios("10.0", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # --- QUESITO 10.1 ---------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 10.1")
        st.write("**A coleta de lixo doméstico (resíduos domiciliares) ocorre de forma programada (determinados os horários e dias da semana)?**")
        
        d101 = res_data.get("10.1", {"valor": None, "pontos": 0, "link": ""})
        opc101 = ["Sim – 00", "Não – -30 (perde 30 pontos)"]
        idx101 = opc101.index(d101["valor"]) if d101["valor"] in opc101 else None
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r101 = st.radio("Selecione 10.1:", opc101, index=idx101, key=f"q101_{ano_sel}")
        with col2:
            l101 = st.text_area("Link/Evidência (10.1):", value=d101.get("link", ""), key=f"l101_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_101_atuais = re.findall(r'(https?://[^\s]+)', l101)
            if links_101_atuais:
                botoes_101 = " | ".join([f"🔗 [{u}]({u})" for u in links_101_atuais])
                st.markdown(f"**Links Ativos:** {botoes_101}")
        
        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 10.1
        pts101 = 0 if r101 and "Sim" in r101 else -30
        if r101 and (r101 != d101["valor"] or l101 != d101["link"]):
            save_resp("10.1", r101, pts101, l101)
            
            if links_101_atuais:
                links_101_antigos = re.findall(r'(https?://[^\s]+)', d101["link"])
                if links_101_atuais != links_101_antigos:
                    modal_aviso_link("10.1", links_101_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
                
        bloco_comentarios("10.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # --- QUESITO 10.2 ---------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 10.2")
        st.write("**Todas as regiões do município são atendidas pela coleta de lixo doméstico (resíduos domiciliares)?** *Inclusive zona rural e periferia*")
        
        d102 = res_data.get("10.2", {"valor": None, "pontos": 0, "link": ""})
        opc102 = [
            "Todos os bairros do município são atendidos – 00", 
            "A maior parte dos bairros são atendidos – -10 (perde 10 pontos)", 
            "A menor parte dos bairros são atendidos – -30 (perde 30 pontos)"
        ]
        idx102 = opc102.index(d102["valor"]) if d102["valor"] in opc102 else None
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r102 = st.radio("Selecione 10.2:", opc102, index=idx102, key=f"q102_{ano_sel}")
        with col2:
            l102 = st.text_area("Link/Evidência (10.2):", value=d102.get("link", ""), key=f"l102_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_102_atuais = re.findall(r'(https?://[^\s]+)', l102)
            if links_102_atuais:
                botoes_102 = " | ".join([f"🔗 [{u}]({u})" for u in links_102_atuais])
                st.markdown(f"**Links Ativos:** {botoes_102}")
        
        if r102 and "Todos" in r102:
            pts102 = 0
        elif r102 and "maior parte" in r102:
            pts102 = -10
        else:
            pts102 = -30
            
        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 10.2
        if r102 and (r102 != d102["valor"] or l102 != d102["link"]):
            save_resp("10.2", r102, pts102, l102)
            
            if links_102_atuais:
                links_102_antigos = re.findall(r'(https?://[^\s]+)', d102["link"])
                if links_102_atuais != links_102_antigos:
                    modal_aviso_link("10.2", links_102_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
                
        bloco_comentarios("10.2", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # --- QUESITO 10.3 ---------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 10.3")
        st.write("**Existe Área de Transbordo e Triagem (ATT) para os Resíduos Sólidos Urbanos no município?**")
        
        d103 = res_data.get("10.3", {"valor": None, "pontos": 0, "link": ""})
        opc103 = ["Sim", "Não"]
        idx103 = opc103.index(d103["valor"]) if d103["valor"] in opc103 else None
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r103 = st.radio("Selecione 10.3:", opc103, index=idx103, key=f"q103_{ano_sel}")
        with col2:
            l103 = st.text_area("Link/Evidência (10.3):", value=d103.get("link", ""), key=f"l103_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_103_atuais = re.findall(r'(https?://[^\s]+)', l103)
            if links_103_atuais:
                botoes_103 = " | ".join([f"🔗 [{u}]({u})" for u in links_103_atuais])
                st.markdown(f"**Links Ativos:** {botoes_103}")
        
        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 10.3
        pts103 = 0 
        if r103 and (r103 != d103["valor"] or l103 != d103["link"]):
            save_resp("10.3", r103, pts103, l103)
            
            if links_103_atuais:
                links_103_antigos = re.findall(r'(https?://[^\s]+)', d103["link"])
                if links_103_atuais != links_103_antigos:
                    modal_aviso_link("10.3", links_103_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
                
        bloco_comentarios("10.3", res_data)

        # SUBQUESITOS CONDICIONAIS SE A ATT EXISTIR (10.3 == "Sim")
        if r103 == "Sim":
            st.divider()
            
            # --- SUBQUESITO 10.3.1 ------------------------------------------------
            st.write("**Existe licença de operação da CETESB para a Área de Transbordo e Triagem (ATT) de Resíduos Sólidos Urbanos?**")
            d1031 = res_data.get("10.3.1", {"valor": None, "pontos": 0, "link": ""})
            opc1031 = ["Sim – 00", "Não – -50 (perde 50 pontos)"]
            idx1031 = opc1031.index(d1031["valor"]) if d1031["valor"] in opc1031 else None
            
            col1_1031, col2_1031 = st.columns([1, 2])
            with col1_1031:
                r1031 = st.radio("Selecione 10.3.1:", opc1031, index=idx1031, key=f"q1031_{ano_sel}")
            with col2_1031:
                l1031 = st.text_area("Link/Evidência (10.3.1):", value=d1031.get("link", ""), key=f"l1031_{ano_sel}", height=100)
                
                # SUPORTE MULTI-LINKS ATIVOS
                links_1031_atuais = re.findall(r'(https?://[^\s]+)', l1031)
                if links_1031_atuais:
                    botoes_1031 = " | ".join([f"🔗 [{u}]({u})" for u in links_1031_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_1031}")
            
            # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 10.3.1
            pts1031 = 0 if r1031 and "Sim" in r1031 else -50
            if r1031 and (r1031 != d1031["valor"] or l1031 != d1031["link"]):
                save_resp("10.3.1", r1031, pts1031, l1031)
                
                if links_1031_atuais:
                    links_1031_antigos = re.findall(r'(https?://[^\s]+)', d1031["link"])
                    if links_1031_atuais != links_1031_antigos:
                        modal_aviso_link("10.3.1", links_1031_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
                    
            bloco_comentarios("10.3.1", res_data)
            st.divider()

            # --- SUBQUESITO 10.3.1.1 (VALIDADE DA LICENÇA) ------------------------
            st.write("**Informe o prazo de validade da licença:**")
            d10311 = res_data.get("10.3.1.1", {"valor": "31/12/2024", "pontos": 0.0, "link": ""})

            try:
                dia_salvo, mes_salvo, ano_salvo = map(int, d10311["valor"].split("/"))
            except:
                dia_salvo, mes_salvo, ano_salvo = 31, 12, 2024

            col1_10311, col2_10311 = st.columns([1, 2])
            with col1_10311:
                c_dia, c_mes, c_ano = st.columns(3)
                with c_dia:
                    dia10311 = st.number_input("Dia", min_value=1, max_value=31, value=dia_salvo, key=f"q10311_d_{ano_sel}")
                with c_mes:
                    mes10311 = st.number_input("Mês", min_value=1, max_value=12, value=mes_salvo, key=f"q10311_m_{ano_sel}")
                with c_ano:
                    ano10311 = st.number_input("Ano", min_value=1900, max_value=2100, value=ano_salvo, key=f"q10311_a_{ano_sel}")

                # Fórmula de cálculo: Se Data <= 31/12/2024 -> -50.0. Se maior -> 0.0 pontos.
                if ano10311 < 2024 or (ano10311 == 2024 and mes10311 < 12) or (ano10311 == 2024 and mes10311 == 12 and dia10311 <= 31):
                    pts10311 = -50.0
                else:
                    pts10311 = 0.0

                st.metric(label="Pontuação", value=f"{pts10311:.1f} pts")

            with col2_10311:
                l10311 = st.text_area("Link/Evidência (10.3.1.1):", value=d10311.get("link", ""), key=f"l10311_{ano_sel}", height=120)
                
                # SUPORTE MULTI-LINKS ATIVOS
                links_10311_atuais = re.findall(r'(https?://[^\s]+)', l10311)
                if links_10311_atuais:
                    botoes_10311 = " | ".join([f"🔗 [{u}]({u})" for u in links_10311_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_10311}")

            data_formatada_10311 = f"{dia10311:02d}/{mes10311:02d}/{ano10311}"

            # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 10.3.1.1
            if d10311["valor"] != "" or (dia10311 != 31 or mes10311 != 12 or ano10311 != 2024):
                if data_formatada_10311 != d10311["valor"] or l10311 != d10311["link"]:
                    save_resp("10.3.1.1", data_formatada_10311, float(pts10311), l10311)
                    
                    if links_10311_atuais:
                        links_10311_antigos = re.findall(r'(https?://[^\s]+)', d10311["link"])
                        if links_10311_atuais != links_10311_antigos:
                            modal_aviso_link("10.3.1.1", links_10311_atuais)
                        else:
                            st.rerun()
                    else:
                        st.rerun()

            bloco_comentarios("10.3.1.1", res_data)
            
        st.markdown('</div>', unsafe_allow_html=True)

        # --- QUESITO 11.0 ---------------------------------------------------------
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.subheader("QUESITO 11.0")
        st.write("**A prefeitura possui Plano de Gerenciamento de Resíduos da Construção Civil (PGRCC) elaborado e implantado de acordo com a resolução CONAMA 307/2002 e suas alterações?**")
        
        d110 = res_data.get("11.0", {"valor": None, "pontos": 0, "link": ""})
        opc110 = ["Sim", "Não"]
        idx110 = opc110.index(d110["valor"]) if d110["valor"] in opc110 else None
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r110 = st.radio("Selecione 11.0:", opc110, index=idx110, key=f"q110_{ano_sel}")
        with col2:
            l110 = st.text_area("Link/Evidência (11.0):", value=d110.get("link", ""), key=f"l110_{ano_sel}", height=100)
                
            # MOSTRA OS LINKS ATIVOS SE EXISTIREM NO CAMPO
            links_110_atuais = re.findall(r'(https?://[^\s]+)', l110)
            if links_110_atuais:
                botoes_110 = " | ".join([f"🔗 [{u}]({u})" for u in links_110_atuais])
                st.markdown(f"**Links Ativos:** {botoes_110}")
        
        # PROCESSAMENTO DE SALVAMENTO E TRAVA DO MODAL DO QUESITO 11.0
        pts110 = 0 
        if r110 and (r110 != d110["valor"] or l110 != d110["link"]):
            save_resp("11.0", r110, pts110, l110)
            
            if links_110_atuais:
                links_110_antigos = re.findall(r'(https?://[^\s]+)', d110["link"])
                if links_110_atuais != links_110_antigos:
                    if 'modal_aviso_link' in globals():
                        modal_aviso_link("11.0", links_110_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
            else:
                st.rerun()
                
        bloco_comentarios("11.0", res_data)
        st.markdown('</div>', unsafe_allow_html=True)
        st.divider()

        # SUBQUESITOS CONDICIONAIS SE O PGRCC EXISTIR (11.0 == "Sim")
        if r110 == "Sim":
            st.markdown('<div class="card_sub">', unsafe_allow_html=True)
                
            # --- SUBQUESITO 11.1 --------------------------------------------------
            st.write("**11.1 Informe o Instrumento normativo, Número e Data da publicação:**")
            d111 = res_data.get("11.1", {"valor": "", "link": ""})
            v111 = st.text_area("Instrumento normativo, Número e Data da publicação (11.1):", value=d111["valor"], key=f"q111_{ano_sel}", height=100)
                
            # MOSTRA OS LINKS ATIVOS SE EXISTIREM NO TEXTO DA RESPOSTA
            links_111_atuais = re.findall(r'(https?://[^\s]+)', v111)
            if links_111_atuais:
                botoes_111 = " | ".join([f"🔗 [{u}]({u})" for u in links_111_atuais])
                st.markdown(f"**Links Detectados:** {botoes_111}")

            if v111 != d111["valor"]:
                save_resp("11.1", v111, 0, "")
                    
                if links_111_atuais:
                    links_111_antigos = re.findall(r'(https?://[^\s]+)', d111["valor"])
                    if links_111_atuais != links_111_antigos:
                        if 'modal_aviso_link' in globals(): modal_aviso_link("11.1", links_111_atuais)
                        else: st.rerun()
                    else:
                        st.rerun()
                else:
                    st.rerun()
                        
            bloco_comentarios("11.1", res_data)
            st.divider()

            # --- SUBQUESITO 11.2 --------------------------------------------------
            st.write("**11.2 Informe a página eletrônica (link na internet) do Plano de Gerenciamento de Resíduos da Construção Civil (PGRCC):**")
            st.caption("Se não estiver disponível na internet, insira no campo de resposta o texto **XYZ**.")
                
            d112 = res_data.get("11.2", {"valor": "XYZ", "pontos": 0.0, "link": ""}) or {"valor": "XYZ", "pontos": 0.0, "link": ""}
                
            col1_112, col2_112 = st.columns([1, 2])
            with col1_112:
                val112 = st.text_input("Endereço eletrônico (Link) ou XYZ:", value=d112.get("valor", "XYZ"), key=f"q112_final_input_unique_{ano_sel}")
                        
                if val112.strip().upper() == "XYZ" or val112.strip() == "":
                    pts112 = 0.0
                else:
                    pts112 = 2.0
                st.metric(label="Pontuação", value=f"{pts112:.1f} pts")
                    
                # MOSTRA OS LINKS SE O VALOR DIGITADO FOR UM LINK VÁLIDO
                links_val112 = re.findall(r'(https?://[^\s]+)', val112)
                if links_val112:
                    botoes_val112 = " | ".join([f"🔗 [{u}]({u})" for u in links_val112])
                    st.markdown(f"**Links do Plano:** {botoes_val112}")
                                        
            with col2_112:
                l112 = st.text_area("Link/Evidência Adicional (11.2):", value=d112.get("link", ""), key=f"l112_final_evid_unique_{ano_sel}", height=100)
                                        
                links_112_atuais = re.findall(r'(https?://[^\s]+)', l112)
                if links_112_atuais:
                    botoes_112 = " | ".join([f"🔗 [{u}]({u})" for u in links_112_atuais])
                    st.markdown(f"**Links da Evidência:** {botoes_112}")
                                        
            if val112 != d112["valor"] or l112 != d112["link"]:
                save_resp("11.2", val112, float(pts112), l112)
                                        
                links_val112_antigos = re.findall(r'(https?://[^\s]+)', d112["valor"])
                links_112_antigos = re.findall(r'(https?://[^\s]+)', d112["link"])
                                        
                todos_links_112_atuais = links_val112 + links_112_atuais
                todos_links_112_antigos = links_val112_antigos + links_112_antigos
                                        
                if todos_links_112_atuais:
                    if todos_links_112_atuais != todos_links_112_antigos:
                        if 'modal_aviso_link' in globals(): modal_aviso_link("11.2", todos_links_112_atuais)
                        else: st.rerun()
                    else:
                        st.rerun()
                else:
                    st.rerun()
                                        
            bloco_comentarios("11.2", res_data)
            st.divider()

            # --- SUBQUESITO 11.3 --------------------------------------------------
            st.write("**11.3 Possui cronograma com as metas a serem cumpridas?**")
            d113 = res_data.get("11.3", {"valor": None, "pontos": 0, "link": ""})
            opc113 = ["Sim – 30", "Não – 00"]
            idx113 = opc113.index(d113["valor"]) if d113["valor"] in opc113 else None
            
            col1_113, col2_113 = st.columns([1, 2])
            with col1_113:
                r113 = st.radio("Selecione 11.3:", opc113, index=idx113, key=f"q113_{ano_sel}")
            with col2_113:
                l113 = st.text_area("Link/Evidência (11.3):", value=d113.get("link", ""), key=f"l113_evid_{ano_sel}", height=100)
                
                # SUPORTE MULTI-LINKS ATIVOS
                links_113_atuais = re.findall(r'(https?://[^\s]+)', l113)
                if links_113_atuais:
                    botoes_113 = " | ".join([f"🔗 [{u}]({u})" for u in links_113_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_113}")
            
            pts113 = 30 if "Sim" in (r113 or "") else 0
            if r113 and (r113 != d113["valor"] or l113 != d113["link"]):
                save_resp("11.3", r113, pts113, l113)
                
                if links_113_atuais:
                    links_113_antigos = re.findall(r'(https?://[^\s]+)', d113["link"])
                    if links_113_atuais != links_113_antigos:
                        if 'modal_aviso_link' in globals(): modal_aviso_link("11.3", links_113_atuais)
                        else: st.rerun()
                    else:
                        st.rerun()
                else:
                    st.rerun()
                    
            bloco_comentarios("11.3", res_data)

            # SUB-CONDICIONAL SE CRONOGRAMA DE METAS EXISTIR (11.3 == "Sim")
            if "Sim" in (r113 or ""):
                st.divider()
                
                # --- SUBQUESITO 11.3.1 --------------------------------------------
                st.write("**11.3.1 Informais quais metas estão previstas:**")
                d1131 = res_data.get("11.3.1", {"valor": "[]", "pontos": 0, "link": ""})
                
                col1_1131, col2_1131 = st.columns([1, 2])
                with col1_1131:
                    opts1131 = [
                        "Aumento/melhoria dos Pontos de Entrega Voluntária - PEV", 
                        "Aumento/melhoria de Áreas de Transbordo e Triagem - ATT", 
                        "Realização de operações de coleta de Resíduos da Construção Civil em “pontos viciados”", 
                        "Cadastro de transportadores de Resíduos da Construção Civil", 
                        "Outro"
                    ]
                    sel1131 = []
                    pts1131 = 0
                    texto_seguro_1131 = str(d1131["valor"]) if d1131["valor"] not in ["", "[]"] else ""
                    for opt in opts1131:
                        if st.checkbox(opt, value=opt in texto_seguro_1131, key=f"q1131_{opt}_{ano_sel}"):
                            sel1131.append(opt)
                with col2_1131:
                    l1131 = st.text_area("Link/Evidência (11.3.1):", value=d1131.get("link", ""), key=f"l1131_{ano_sel}", height=100)
                    
                    links_1131_atuais = re.findall(r'(https?://[^\s]+)', l1131)
                    if links_1131_atuais:
                        botoes_1131 = " | ".join([f"🔗 [{u}]({u})" for u in links_1131_atuais])
                        st.markdown(f"**Links Ativos:** {botoes_1131}")
                
                if str(sel1131) != d1131["valor"] or l1131 != d1131["link"]:
                    save_resp("11.3.1", str(sel1131), pts1131, l1131)
                    
                    if links_1131_atuais:
                        links_1131_antigos = re.findall(r'(https?://[^\s]+)', d1131["link"])
                        if links_1131_atuais != links_1131_antigos:
                            if 'modal_aviso_link' in globals(): modal_aviso_link("11.3.1", links_1131_atuais)
                            else: st.rerun()
                        else:
                            st.rerun()
                    else:
                        st.rerun()
                        
                bloco_comentarios("11.3.1", res_data)
                st.divider()

                # --- SUBQUESITO 11.3.2 --------------------------------------------
                st.write("**11.3.2 Realiza monitoramento e avaliação das ações e metas?**")
                d1132 = res_data.get("11.3.2", {"valor": None, "pontos": 0, "link": ""})
                opc1132 = ["Sim – 20", "Não – 00"]
                idx1132 = opc1132.index(d1132["valor"]) if d1132["valor"] in opc1132 else None
                
                col1_1132, col2_1132 = st.columns([1, 2])
                with col1_1132:
                    r1132 = st.radio("Selecione 11.3.2:", opc1132, index=idx1132, key=f"q1132_{ano_sel}")
                with col2_1132:
                    l1132 = st.text_area("Link/Evidência (11.3.2):", value=d1132.get("link", ""), key=f"l1132_{ano_sel}", height=100)
                    
                    links_1132_atuais = re.findall(r'(https?://[^\s]+)', l1132)
                    if links_1132_atuais:
                        botoes_1132 = " | ".join([f"🔗 [{u}]({u})" for u in links_1132_atuais])
                        st.markdown(f"**Links Ativos:** {botoes_1132}")
                
                pts1132 = 20 if "Sim" in (r1132 or "") else 0
                if r1132 and (r1132 != d1132["valor"] or l1132 != d1132["link"]):
                    save_resp("11.3.2", r1132, pts1132, l1132)
                    
                    if links_1132_atuais:
                        links_1132_antigos = re.findall(r'(https?://[^\s]+)', d1132["link"])
                        if links_1132_atuais != links_1132_antigos:
                            if 'modal_aviso_link' in globals(): modal_aviso_link("11.3.2", links_1132_atuais)
                            else: st.rerun()
                        else:
                            st.rerun()
                    else:
                        st.rerun()
                        
                bloco_comentarios("11.3.2", res_data)

                # SUB-CONDICIONAL SE MONITORAMENTO EXISTIR (11.3.2 == "Sim")
                if "Sim" in (r1132 or ""):
                    st.divider()
                    
                    # --- SUBQUESITO 11.3.2.1 --------------------------------------
                    st.write("**11.3.2.1 De que forma é realizado o monitoramento e avaliação?**")
                    d11321 = res_data.get("11.3.2.1", {"valor": "[]", "pontos": 0, "link": ""})
                    
                    col1_11321, col2_11321 = st.columns([1, 2])
                    with col1_11321:
                        opts11321 = ["Relatórios anuais discutidos e/ou publicados", "Indicadores de eficácia e eficiência", "Avaliação de recursos aplicados", "Outro"]
                        sel11321 = []
                        pts11321 = 0
                        texto_seguro_11321 = str(d11321["valor"]) if d11321["valor"] not in ["", "[]"] else ""
                        for opt in opts11321:
                            if st.checkbox(opt, value=opt in texto_seguro_11321, key=f"q11321_{opt}_{ano_sel}"):
                                sel11321.append(opt)
                    with col2_11321:
                        l11321 = st.text_area("Link/Evidência (11.3.2.1):", value=d11321.get("link", ""), key=f"l11321_{ano_sel}", height=100)
                        
                        links_11321_atuais = re.findall(r'(https?://[^\s]+)', l11321)
                        if links_11321_atuais:
                            botoes_11321 = " | ".join([f"🔗 [{u}]({u})" for u in links_11321_atuais])
                            st.markdown(f"**Links Ativos:** {botoes_11321}")
                    
                    if str(sel11321) != d11321["valor"] or l11321 != d11321["link"]:
                        save_resp("11.3.2.1", str(sel11321), pts11321, l11321)
                        
                        if links_11321_atuais:
                            links_11321_antigos = re.findall(r'(https?://[^\s]+)', d11321["link"])
                            if links_11321_atuais != links_11321_antigos:
                                if 'modal_aviso_link' in globals(): modal_aviso_link("11.3.2.1", links_11321_atuais)
                                else: st.rerun()
                            else:
                                st.rerun()
                        else:
                            st.rerun()
                            
                    bloco_comentarios("11.3.2.1", res_data)
                st.divider()

                # --- SUBQUESITO 11.3.3 --------------------------------------------
                st.write("**11.3.3 As metas do Plano estão sendo cumpridas no prazo estipulado?**")
                d1133 = res_data.get("11.3.3", {"valor": None, "pontos": 0, "link": ""})
                opc1133 = [
                    "Todas as metas foram cumpridas dentro do prazo – 40", 
                    "A maior parte das metas foram cumpridas dentro do prazo – 30", 
                    "A menor parte das metas foram cumpridas dentro do prazo – 10", 
                    "As metas não foram cumpridas dentro do prazo – 00"
                ]
                idx1133 = opc1133.index(d1133["valor"]) if d1133["valor"] in opc1133 else None
                
                col1_1133, col2_1133 = st.columns([1, 2])
                with col1_1133:
                    r1133 = st.radio("Selecione 11.3.3:", opc1133, index=idx1133, key=f"q1133_{ano_sel}")
                with col2_1133:
                    l1133 = st.text_area("Link/Evidência (11.3.3):", value=d1133.get("link", ""), key=f"l1133_{ano_sel}", height=100)
                    
                    links_1133_atuais = re.findall(r'(https?://[^\s]+)', l1133)
                    if links_1133_atuais:
                        botoes_1133 = " | ".join([f"🔗 [{u}]({u})" for u in links_1133_atuais])
                        st.markdown(f"**Links Ativos:** {botoes_1133}")
                
                if "Todas" in (r1133 or ""): pts1133 = 40
                elif "maior parte" in (r1133 or ""): pts1133 = 30
                elif "menor parte" in (r1133 or ""): pts1133 = 10
                else: pts1133 = 0

                if r1133 and (r1133 != d1133["valor"] or l1133 != d1133["link"]):
                    save_resp("11.3.3", r1133, pts1133, l1133)
                    
                    if links_1133_atuais:
                        links_1133_antigos = re.findall(r'(https?://[^\s]+)', d1133["link"])
                        if links_1133_atuais != links_1133_antigos:
                            if 'modal_aviso_link' in globals(): modal_aviso_link("11.3.3", links_1133_atuais)
                            else: st.rerun()
                        else:
                            st.rerun()
                    else:
                        st.rerun()
                        
                bloco_comentarios("11.3.3", res_data)

                # SUB-CONDICIONAL SE AS METAS NÃO FORAM CUMPRIDAS
                if "não foram cumpridas" in (r1133 or ""):
                    st.divider()
                    
                    # --- SUBQUESITO 11.3.3.1 --------------------------------------
                    st.write("**11.3.3.1 Assinale os motivos pelos quais as metas não estão sendo cumpridas:**")
                    d11331 = res_data.get("11.3.3.1", {"valor": "[]", "pontos": 0, "link": ""})
                    
                    col1_11331, col2_11331 = st.columns([1, 2])
                    with col1_11331:
                        opts11331 = ["Falta de recursos orçamentários", "Falta de aprovação legislativa", "Atraso na licitação", "Não realizou licitação necessária", "Falta de pessoal qualificado", "Falta de consenso no consórcio intermunicipal", "Outros"]
                        sel11331 = []
                        pts11331 = 0
                        texto_seguro_11331 = str(d11331["valor"]) if d11331["valor"] not in ["", "[]"] else ""
                        for opt in opts11331:
                            if st.checkbox(opt, value=opt in texto_seguro_11331, key=f"q11331_{opt}_{ano_sel}"):
                                sel11331.append(opt)
                    with col2_11331:
                        l11331 = st.text_area("Link/Evidência (11.3.3.1):", value=d11331.get("link", ""), key=f"l11331_{ano_sel}", height=100)
                        
                        links_11331_atuais = re.findall(r'(https?://[^\s]+)', l11331)
                        if links_11331_atuais:
                            botoes_11331 = " | ".join([f"🔗 [{u}]({u})" for u in links_11331_atuais])
                            st.markdown(f"**Links Ativos:** {botoes_11331}")
                    
                    if str(sel11331) != d11331["valor"] or l11331 != d11331["link"]:
                        save_resp("11.3.3.1", str(sel11331), pts11331, l11331)
                        
                        if links_11331_atuais:
                            links_11331_antigos = re.findall(r'(https?://[^\s]+)', d11331["link"])
                            if links_11331_atuais != links_11331_antigos:
                                if 'modal_aviso_link' in globals(): modal_aviso_link("11.3.3.1", links_11331_atuais)
                                else: st.rerun()
                            else:
                                st.rerun()
                        else:
                            st.rerun()
                            
                    bloco_comentarios("11.3.3.1", res_data)
            st.divider()

            # --- SUBQUESITO 11.4 --------------------------------------------------
            st.write("**11.4 Quem é o responsável pela triagem dos resíduos da construção civil?**")
            d114 = res_data.get("11.4", {"valor": None, "pontos": 0, "link": ""})
            opc114 = ["Gerador dos resíduos – 00", "Prefeitura – -10 (perde 10 pontos)", "Outros – -10 (perde 10 pontos)"]
            idx114 = opc114.index(d114["valor"]) if d114["valor"] in opc114 else None
            
            col1_114, col2_114 = st.columns([1, 2])
            with col1_114:
                r114 = st.radio("Selecione 11.4:", opc114, index=idx114, key=f"q114_{ano_sel}")
            with col2_114:
                l114 = st.text_area("Link/Evidência (11.4):", value=d114.get("link", ""), key=f"l114_{ano_sel}", height=100)
                
                # SUPORTE MULTI-LINKS ATIVOS
                links_114_atuais = re.findall(r'(https?://[^\s]+)', l114)
                if links_114_atuais:
                    botoes_114 = " | ".join([f"🔗 [{u}]({u})" for u in links_114_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_114}")
            
            if "Gerador" in (r114 or ""): pts114 = 0
            elif "Prefeitura" in (r114 or ""): pts114 = -10
            else: pts114 = -10

            if r114 and (r114 != d114["valor"] or l114 != d114["link"]):
                save_resp("11.4", r114, pts114, l114)
                
                if links_114_atuais:
                    links_114_antigos = re.findall(r'(https?://[^\s]+)', d114["link"])
                    if links_114_atuais != links_114_antigos:
                        if 'modal_aviso_link' in globals(): modal_aviso_link("11.4", links_114_atuais)
                        else: st.rerun()
                    else:
                        st.rerun()
                else:
                    st.rerun()
                    
            bloco_comentarios("11.4", res_data)
            st.divider()

            # --- SUBQUESITO 11.5 --------------------------------------------------
            st.write("**11.5 A Prefeitura realiza fiscalizações das atividades envolvidas no gerenciamento dos resíduos da construção civil?**")
            d115 = res_data.get("11.5", {"valor": None, "pontos": 0, "link": ""})
            opc115 = ["Sim – 10", "Não – 00"]
            idx115 = opc115.index(d115["valor"]) if d115["valor"] in opc115 else None
            
            col1_115, col2_115 = st.columns([1, 2])
            with col1_115:
                r115 = st.radio("Selecione 11.5:", opc115, index=idx115, key=f"q115_{ano_sel}")
            with col2_115:
                l115 = st.text_area("Link/Evidência (11.5):", value=d115.get("link", ""), key=f"l115_{ano_sel}", height=100)
                
                # SUPORTE MULTI-LINKS ATIVOS
                links_115_atuais = re.findall(r'(https?://[^\s]+)', l115)
                if links_115_atuais:
                    botoes_115 = " | ".join([f"🔗 [{u}]({u})" for u in links_115_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_115}")
            
            pts115 = 10 if "Sim" in (r115 or "") else 0
            if r115 and (r115 != d115["valor"] or l115 != d115["link"]):
                save_resp("11.5", r115, pts115, l115)
                
                if links_115_atuais:
                    links_115_antigos = re.findall(r'(https?://[^\s]+)', d115["link"])
                    if links_115_atuais != links_115_antigos:
                        if 'modal_aviso_link' in globals(): modal_aviso_link("11.5", links_115_atuais)
                        else: st.rerun()
                    else:
                        st.rerun()
                else:
                    st.rerun()
                    
            bloco_comentarios("11.5", res_data)

            # SUB-CONDICIONAL SE A FISCALIZAÇÃO EXISTIR (11.5 == "Sim")
            if "Sim" in (r115 or ""):
                st.divider()
                
                # --- SUBQUESITO 11.5.1 --------------------------------------------
                st.write("**11.5.1 Em quais atividades são realizadas essas fiscalizações?**")
                d1151 = res_data.get("11.5.1", {"valor": "[]", "pontos": 0, "link": ""})
                
                col1_1151, col2_1151 = st.columns([1, 2])
                with col1_1151:
                    opts1151 = ["Coleta", "Acondicionamento", "Transporte", "Destinação / disposição final"]
                    sel1151 = []
                    pts1151 = 0
                    texto_seguro_1151 = str(d1151["valor"]) if d1151["valor"] not in ["", "[]"] else ""
                    for opt in opts1151:
                        if st.checkbox(opt, value=opt in texto_seguro_1151, key=f"q1151_{opt}_{ano_sel}"):
                            sel1151.append(opt)
                with col2_1151:
                    l1151 = st.text_area("Link/Evidência (11.5.1):", value=d1151.get("link", ""), key=f"l1151_{ano_sel}", height=100)
                    
                    # SUPORTE MULTI-LINKS ATIVOS
                    links_1151_atuais = re.findall(r'(https?://[^\s]+)', l1151)
                    if links_1151_atuais:
                        botoes_1151 = " | ".join([f"🔗 [{u}]({u})" for u in links_1151_atuais])
                        st.markdown(f"**Links Ativos:** {botoes_1151}")
                
                if str(sel1151) != d1151["valor"] or l1151 != d1151["link"]:
                    save_resp("11.5.1", str(sel1151), pts1151, l1151)
                    
                    if links_1151_atuais:
                        links_1151_antigos = re.findall(r'(https?://[^\s]+)', d1151["link"])
                        if links_1151_atuais != links_1151_antigos:
                            if 'modal_aviso_link' in globals(): modal_aviso_link("11.5.1", links_1151_atuais)
                            else: st.rerun()
                        else:
                            st.rerun()
                    else:
                        st.rerun()
                        
                bloco_comentarios("11.5.1", res_data)
            st.divider()

            # --- SUBQUESITO 11.6 --------------------------------------------------
            st.write("**11.6 Existe Área de Transbordo e Triagem (ATT) para os Resíduos da Construção Civil no município?**")
            d116 = res_data.get("11.6", {"valor": None, "pontos": 0, "link": ""})
            opc116 = ["Sim", "Não"]
            idx116 = opc116.index(d116["valor"]) if d116["valor"] in opc116 else None
            
            col1_116, col2_116 = st.columns([1, 2])
            with col1_116:
                r116 = st.radio("Selecione 11.6:", opc116, index=idx116, key=f"q116_{ano_sel}")
            with col2_116:
                l116 = st.text_area("Link/Evidência (11.6):", value=d116.get("link", ""), key=f"l116_{ano_sel}", height=100)
                
                # SUPORTE MULTI-LINKS ATIVOS
                links_116_atuais = re.findall(r'(https?://[^\s]+)', l116)
                if links_116_atuais:
                    botoes_116 = " | ".join([f"🔗 [{u}]({u})" for u in links_116_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_116}")
            
            pts116 = 0
            if r116 and (r116 != d116["valor"] or l116 != d116["link"]):
                save_resp("11.6", r116, pts116, l116)
                
                if links_116_atuais:
                    links_116_antigos = re.findall(r'(https?://[^\s]+)', d116["link"])
                    if links_116_atuais != links_116_antigos:
                        if 'modal_aviso_link' in globals(): modal_aviso_link("11.6", links_116_atuais)
                        else: st.rerun()
                    else:
                        st.rerun()
                else:
                    st.rerun()
                    
            bloco_comentarios("11.6", res_data)

            # SUB-CONDICIONAL SE A ATT DA CONSTRUÇÃO CIVIL EXISTIR (11.6 == "Sim")
            if r116 == "Sim":
                st.divider()
                
                # --- SUBQUESITO 11.6.1 --------------------------------------------
                st.write("**11.6.1 Existe licença de operação da CETESB para a Área de Transbordo e Triagem (ATT) de Resíduos da Construção Civil?**")
                d1161 = res_data.get("11.6.1", {"valor": None, "pontos": 0, "link": ""})
                opc1161 = ["Sim", "Não"]
                idx1161 = opc1161.index(d1161["valor"]) if d1161["valor"] in opc1161 else None
                
                col1_1161, col2_1161 = st.columns([1, 2])
                with col1_1161:
                    r1161 = st.radio("Selecione 11.6.1:", opc1161, index=idx1161, key=f"q1161_{ano_sel}")
                with col2_1161:
                    l1161 = st.text_area("Link/Evidência (11.6.1):", value=d1161.get("link", ""), key=f"l1161_{ano_sel}", height=100)
                    
                    # SUPORTE MULTI-LINKS ATIVOS
                    links_1161_atuais = re.findall(r'(https?://[^\s]+)', l1161)
                    if links_1161_atuais:
                        botoes_1161 = " | ".join([f"🔗 [{u}]({u})" for u in links_1161_atuais])
                        st.markdown(f"**Links Ativos:** {botoes_1161}")
                
                pts1161 = 0
                if r1161 and (r1161 != d1161["valor"] or l1161 != d1161["link"]):
                    save_resp("11.6.1", r1161, pts1161, l1161)
                    
                    if links_1161_atuais:
                        links_1161_antigos = re.findall(r'(https?://[^\s]+)', d1161["link"])
                        if links_1161_atuais != links_1161_antigos:
                            if 'modal_aviso_link' in globals(): modal_aviso_link("11.6.1", links_1161_atuais)
                            else: st.rerun()
                        else:
                            st.rerun()
                    else:
                        st.rerun()
                        
                bloco_comentarios("11.6.1", res_data)
                
                # SÓ EXIBE A DATA SE HOUVER LICENÇA (11.6.1 == "Sim")
                if r1161 == "Sim":
                    st.divider()
                    
                    # --- SUBQUESITO 11.6.1.1 (ESTRUTURA DE DATA ADAPTADA) ---------
                    st.write("**11.6.1.1 Informe o prazo de validade da licença:**")
                    d11611 = res_data.get("11.6.1.1", {"valor": "31/12/2024", "pontos": 0, "link": ""})
                    
                    try:
                        dia_salvo, mes_salvo, ano_salvo = map(int, d11611["valor"].split("/"))
                    except:
                        dia_salvo, mes_salvo, ano_salvo = 31, 12, 2024
                        
                    col1_11611, col2_11611 = st.columns([1, 2])
                    with col1_11611:
                        c_dia, c_mes, c_ano = st.columns(3)
                        with c_dia:
                            dia11611 = st.number_input("Dia", min_value=1, max_value=31, value=dia_salvo, key=f"q11611_d_{ano_sel}")
                        with c_mes:
                            mes11611 = st.number_input("Mês", min_value=1, max_value=12, value=mes_salvo, key=f"q11611_m_{ano_sel}")
                        with c_ano:
                            ano11611 = st.number_input("Ano", min_value=1900, max_value=2100, value=ano_salvo, key=f"q11611_a_{ano_sel}")
                            
                        pts11611 = 0.0
                        st.metric(label="Pontuação", value=f"{pts11611:.1f} pts")
                        
                    with col2_11611:
                        l11611 = st.text_area("Link/Evidência (11.6.1.1):", value=d11611.get("link", ""), key=f"l11611_{ano_sel}", height=120)
                        
                        # SUPORTE MULTI-LINKS ATIVOS
                        links_11611_atuais = re.findall(r'(https?://[^\s]+)', l11611)
                        if links_11611_atuais:
                            botoes_11611 = " | ".join([f"🔗 [{u}]({u})" for u in links_11611_atuais])
                            st.markdown(f"**Links Ativos:** {botoes_11611}")
                            
                    data_formatada_11611 = f"{dia11611:02d}/{mes11611:02d}/{ano11611}"
                    
                    if d11611["valor"] != "" or (dia11611 != 31 or mes11611 != 12 or ano11611 != 2024):
                        if data_formatada_11611 != d11611["valor"] or l11611 != d11611["link"]:
                            save_resp("11.6.1.1", data_formatada_11611, pts11611, l11611)
                            
                            if links_11611_atuais:
                                links_11611_antigos = re.findall(r'(https?://[^\s]+)', d11611["link"])
                                if links_11611_atuais != links_11611_antigos:
                                    if 'modal_aviso_link' in globals(): modal_aviso_link("11.6.1.1", links_11611_atuais)
                                    else: st.rerun()
                                else:
                                    st.rerun()
                            else:
                                st.rerun()
                                
                    bloco_comentarios("11.6.1.1", res_data)
            st.markdown('</div>', unsafe_allow_html=True)
            st.divider()
 
        # =============================================================================
        # QUESITO 12.0 e 12.1 (PROCESSAMENTO DE RESÍDUOS)
        # =============================================================================
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 12.0")
        st.write("**Antes de aterrar o lixo, o município realiza algum tipo de processamento de resíduos?**")

        d120 = res_data.get("12.0", {"valor": None, "pontos": 0, "link": ""})
        opc120 = ["Sim", "Não"]
        idx120 = opc120.index(d120["valor"]) if d120["valor"] in opc120 else None

        col1, col2 = st.columns([1, 2])
        with col1:
            r120 = st.radio("Selecione 12.0:", opc120, index=idx120, key=f"q120_{ano_sel}")
        with col2:
            l120 = st.text_area("Link/Evidência (12.0):", value=d120.get("link", ""), key=f"l120_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_120_atuais = re.findall(r'(https?://[^\s]+)', l120)
            if links_120_atuais:
                botoes_120 = " | ".join([f"🔗 [{u}]({u})" for u in links_120_atuais])
                st.markdown(f"**Links Ativos:** {botoes_120}")

        pts120 = 0
        if r120 and (r120 != d120["valor"] or l120 != d120["link"]):
            save_resp("12.0", r120, pts120, l120)
            
            if r120 == "Não":
                save_resp("12.1", "[]", 0, "")
            
            if links_120_atuais:
                links_120_antigos = re.findall(r'(https?://[^\s]+)', d120["link"])
                if links_120_atuais != links_120_antigos:
                    if 'modal_aviso_link' in globals():
                        modal_aviso_link("12.0", links_120_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("12.0", res_data)

        # --- SUBQUESITO 12.1 ---
        if r120 == "Sim":
            st.write("**12.1 Assinale qual a forma realizada de processamento de resíduos:**")
            d121 = res_data.get("12.1", {"valor": "[]", "pontos": 0, "link": ""})
            
            col1_121, col2_121 = st.columns([1, 2])
            with col1_121:
                opts121 = {
                    "Reciclagem – 04": 4, 
                    "Compostagem – 20": 20, 
                    "Reutilização – 20": 20, 
                    "Sistema de Logística Reversa – 10": 10, 
                    "Outro – 00": 0
                }
                sel121 = []
                pts121 = 0
                texto_salvo_121 = str(d121["valor"])
                
                for txt, pts in opts121.items():
                    if st.checkbox(txt, value=txt in texto_salvo_121, key=f"q121_{txt}_{ano_sel}"):
                        sel121.append(txt)
                        pts121 += pts
                    
            with col2_121:
                l121 = st.text_area("Link/Evidência (12.1):", value=d121.get("link", ""), key=f"l121_{ano_sel}", height=100)
                
                # SUPORTE MULTI-LINKS ATIVOS
                links_121_atuais = re.findall(r'(https?://[^\s]+)', l121)
                if links_121_atuais:
                    botoes_121 = " | ".join([f"🔗 [{u}]({u})" for u in links_121_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_121}")
            
            if str(sel121) != d121["valor"] or l121 != d121["link"]:
                save_resp("12.1", str(sel121), pts121, l121)
                
                if links_121_atuais:
                    links_121_antigos = re.findall(r'(https?://[^\s]+)', d121["link"])
                    if links_121_atuais != links_121_antigos:
                        if 'modal_aviso_link' in globals():
                            modal_aviso_link("12.1", links_121_atuais)
                        else:
                            st.rerun()
                    else:
                        st.rerun()
                else:
                    st.rerun()
            
            bloco_comentarios("12.1", res_data)

        st.markdown('</div>', unsafe_allow_html=True)

        # =============================================================================
        # QUESITO 13.0 e 13.1 (LÓGICA DE PENALIDADE E RECUPERAÇÃO)
        # =============================================================================
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 13.0")
        st.write("**Existe aterro para os resíduos sólidos urbanos (lixo doméstico e limpeza urbana) no município?**")

        d130 = res_data.get("13.0", {"valor": None, "pontos": 0.0, "link": ""})
        opc130 = ["Sim", "Não"]
        idx130 = opc130.index(d130["valor"]) if d130["valor"] in opc130 else None

        col1, col2 = st.columns([1, 2])
        with col1:
            r130 = st.radio("Selecione 13.0:", opc130, index=idx130, key=f"q130_{ano_sel}")
            pts130 = 0.0
            st.metric(label="Pontuação 13.0", value=f"{pts130:.1f} pts")
        with col2:
            l130 = st.text_area("Link/Evidência (13.0):", value=d130.get("link", ""), key=f"l130_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_130_atuais = re.findall(r'(https?://[^\s]+)', l130)
            if links_130_atuais:
                botoes_130 = " | ".join([f"🔗 [{u}]({u})" for u in links_130_atuais])
                st.markdown(f"**Links Ativos:** {botoes_130}")

        if r130 != d130["valor"] or l130 != d130["link"]:
            save_resp("13.0", r130, float(pts130), l130)
            if r130 == "Não":
                save_resp("13.1", "[]", 0.0, "")
            
            if links_130_atuais:
                links_130_antigos = re.findall(r'(https?://[^\s]+)', d130["link"])
                if links_130_atuais != links_130_antigos:
                    if 'modal_aviso_link' in globals():
                        modal_aviso_link("13.0", links_130_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("13.0", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # --- QUESITO 13.1 ---
        if r130 == "Sim":
            st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
            st.subheader("QUESITO 13.1")
            st.write("**Assinale as características do local de destinação final dos resíduos sólidos urbanos do município (aterro):**")

            d131 = res_data.get("13.1", {"valor": "[]", "pontos": -110.0, "link": ""})

            opts131 = [
                "Local da instalação foi planejado", "Capacidade do local é definida", 
                "Há desenvolvimento de células individuais", "Impermeabilização do solo", 
                "Total gestão do chorume", "Total gestão dos gases", 
                "Aplicação diária de camadas intermediárias e finais - cobertura do solo", 
                "Há compactação dos resíduos", "Há proteção vegetal (manutenção do paisagismo sobre as células de resíduos)", 
                "Há desenvolvimento e manutenção das vias de acesso do aterro", "Há cercas/muros ao redor do local do aterro", 
                "Há controle de acesso ao local do aterro", "Controle total do quantitativo de resíduos que entram no aterro", 
                "Controle total da procedência dos resíduos que entram no aterro", "Controle total da composição dos resíduos que entram no aterro", 
                "Não há coleta de resíduos por catadores dentro do aterro", "Não há comércio de resíduos dentro do aterro", 
                "Não há presença de animais domésticos e/ou animais silvestres (urubus, garças, etc.)", 
                "Não há odores nem presença de moscas", "Não há queima de resíduos dentro do aterro", 
                "Conhecimento da data provável de fechamento do aterro", "Previsão de gerenciamento do aterro pós-fechamento", 
                "Outros"
            ]

            col1_131, col2_131 = st.columns([1, 2])
            with col1_131:
                sel131 = []
                texto_salvo_131 = str(d131["valor"])
                
                for opt in opts131:
                    if st.checkbox(opt, value=opt in texto_salvo_131, key=f"q131_direto_{opt}_{ano_sel}"):
                        sel131.append(opt)

                pts131 = -110.0
                for marcado in sel131:
                    if marcado != "Outros":
                        pts131 += 5.0

                pts131 = max(-110.0, min(0.0, pts131))
                st.metric(label="Penalidade Atual Aplicada", value=f"{pts131:.1f} pts")

            with col2_131:
                l131 = st.text_area("Link/Evidência (13.1):", value=d131.get("link", ""), key=f"l131_{ano_sel}", height=150)
                
                # SUPORTE MULTI-LINKS ATIVOS
                links_131_atuais = re.findall(r'(https?://[^\s]+)', l131)
                if links_131_atuais:
                    botoes_131 = " | ".join([f"🔗 [{u}]({u})" for u in links_131_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_131}")

            if str(sel131) != d131["valor"] or l131 != d131["link"] or float(d131["pontos"]) != pts131:
                save_resp("13.1", str(sel131), float(pts131), l131)
                
                if links_131_atuais:
                    links_131_antigos = re.findall(r'(https?://[^\s]+)', d131["link"])
                    if links_131_atuais != links_131_antigos:
                        if 'modal_aviso_link' in globals():
                            modal_aviso_link("13.1", links_131_atuais)
                        else:
                            st.rerun()
                    else:
                        st.rerun()
                else:
                    st.rerun()
            
            bloco_comentarios("13.1", res_data)
            st.markdown('</div>', unsafe_allow_html=True)          
        
        # =============================================================================
        # QUESITO 14.0 a 14.3 (PONTOS DE DESCARTE IRREGULAR)
        # =============================================================================
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 14.0")
        st.write("**Existem pontos de descarte irregular de lixo no munícipio?**")
        
        d140 = res_data.get("14.0", {"valor": None, "pontos": 0, "link": ""})
        opc140 = ["Sim – -30 (perde 30 pontos)", "Não – 00"]
        idx140 = opc140.index(d140["valor"]) if d140["valor"] in opc140 else None
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r140 = st.radio("Selecione 14.0:", opc140, index=idx140, key=f"q140_{ano_sel}")
        with col2:
            l140 = st.text_area("Link/Evidência (14.0):", value=d140.get("link", ""), key=f"l140_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_140_atuais = re.findall(r'(https?://[^\s]+)', l140)
            if links_140_atuais:
                botoes_140 = " | ".join([f"🔗 [{u}]({u})" for u in links_140_atuais])
                st.markdown(f"**Links Ativos:** {botoes_140}")
        
        pts140 = -30 if "Sim" in (r140 or "") else 0
        if r140 and (r140 != d140["valor"] or l140 != d140["link"]):
            save_resp("14.0", r140, pts140, l140)
            
            if "Não" in r140:
                save_resp("14.1", "", 0, "")
                save_resp("14.2", "", 0, "")
                save_resp("14.3", "[]", 0, "")
            
            if links_140_atuais:
                links_140_antigos = re.findall(r'(https?://[^\s]+)', d140["link"])
                if links_140_atuais != links_140_antigos:
                    if 'modal_aviso_link' in globals():
                        modal_aviso_link("14.0", links_140_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
            else:
                st.rerun()
                
        bloco_comentarios("14.0", res_data)

        # --- SUBQUESITOS CONDICIONAIS ---
        if "Sim" in (r140 or ""):
            st.write("**14.1 Informe a quantidade de pontos identificados:**")
            d141 = res_data.get("14.1", {"valor": "", "link": ""})
            v141 = st.text_area("Quantidade de pontos (14.1):", value=d141["valor"], key=f"q141_{ano_sel}", height=100)
            if v141 != d141["valor"]:
                save_resp("14.1", v141, 0, "")
            bloco_comentarios("14.1", res_data)

            st.write("**14.2 Informe o endereço dos locais identificados:**")
            d142 = res_data.get("14.2", {"valor": "", "link": ""})
            v142 = st.text_area("Endereço dos locais (14.2):", value=d142["valor"], key=f"q142_{ano_sel}", height=100)
            if v142 != d142["valor"]:
                save_resp("14.2", v142, 0, "")
            bloco_comentarios("14.2", res_data)

            st.write("**14.3 Assinale as ações promovidas pela Prefeitura para combater o descarte irregular de lixo no ano:**")
            d143 = res_data.get("14.3", {"valor": "[]", "pontos": 0, "link": ""})
            
            col1_143, col2_143 = st.columns([1, 2])
            with col1_143:
                opts143 = {
                    "Campanhas de conscientização – 05": 5, 
                    "Mobilização de grupos de bairro – 05": 5, 
                    "Retirada dos resíduos sólidos por caminhões – 05": 5, 
                    "Sinalização no local sobre a proibição de descarte naquele local – 05": 5, 
                    "Plantio de árvores em áreas que não deveriam receber lixo ou entulho – 05": 5, 
                    "Notificações e multas aos responsáveis – 05": 5
                }
                sel143 = []
                pts143 = 0
                texto_salvo_143 = str(d143["valor"])
                for txt, pts in opts143.items():
                    if st.checkbox(txt, value=txt in texto_salvo_143, key=f"q143_{txt}_{ano_sel}"):
                        sel143.append(txt)
                        pts143 += pts
            with col2_143:
                l143 = st.text_area("Link/Evidência (14.3):", value=d143.get("link", ""), key=f"l143_{ano_sel}", height=100)
                
                # SUPORTE MULTI-LINKS ATIVOS
                links_143_atuais = re.findall(r'(https?://[^\s]+)', l143)
                if links_143_atuais:
                    botoes_143 = " | ".join([f"🔗 [{u}]({u})" for u in links_143_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_143}")
                
            if str(sel143) != d143["valor"] or l143 != d143["link"]:
                save_resp("14.3", str(sel143), pts143, l143)
                
                if links_143_atuais:
                    links_143_antigos = re.findall(r'(https?://[^\s]+)', d143["link"])
                    if links_143_atuais != links_143_antigos:
                        if 'modal_aviso_link' in globals():
                            modal_aviso_link("14.3", links_143_atuais)
                        else:
                            st.rerun()
                    else:
                        st.rerun()
                else:
                    st.rerun()
                    
            bloco_comentarios("14.3", res_data)
            
        st.markdown('</div>', unsafe_allow_html=True)

        # =============================================================================
        # QUESITO 15.0 a 15.1.4 (ENTIDADE REGULADORA E FISCALIZADORA)
        # =============================================================================
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 15.0")
        st.write("**O Município definiu a entidade responsável pela regulação e fiscalização dos serviços públicos de saneamento básico?**")
        
        d150 = res_data.get("15.0", {"valor": None, "pontos": 0, "link": ""})
        opc150 = ["Sim – 02", "Não – 00"]
        idx150 = opc150.index(d150["valor"]) if d150["valor"] in opc150 else None
        
        col1, col2 = st.columns([1, 2])
        with col1:
            r150 = st.radio("Selecione 15.0:", opc150, index=idx150, key=f"q150_{ano_sel}")
        with col2:
            l150 = st.text_area("Link/Evidência (15.0):", value=d150.get("link", ""), key=f"l150_{ano_sel}", height=100)
            
            # SUPORTE MULTI-LINKS ATIVOS
            links_150_atuais = re.findall(r'(https?://[^\s]+)', l150)
            if links_150_atuais:
                botoes_150 = " | ".join([f"🔗 [{u}]({u})" for u in links_150_atuais])
                st.markdown(f"**Links Ativos:** {botoes_150}")
        
        pts150 = 2 if "Sim" in (r150 or "") else 0
        if r150 and (r150 != d150["valor"] or l150 != d150["link"]):
            save_resp("15.0", r150, pts150, l150)
            
            # Limpa dependentes se mudar para Não
            if "Não" in r150:
                save_resp("15.1", "[]", 0, "")
                save_resp("15.1.1", "", 0, "")
                save_resp("15.1.2", "", 0, "")
                save_resp("15.1.3", "", 0, "")
                save_resp("15.1.4", "", 0, "")
            
            if links_150_atuais:
                links_150_antigos = re.findall(r'(https?://[^\s]+)', d150["link"])
                if links_150_atuais != links_150_antigos:
                    if 'modal_aviso_link' in globals():
                        modal_aviso_link("15.0", links_150_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
            else:
                st.rerun()
                
        bloco_comentarios("15.0", res_data)

        # --- SUBQUESITOS CONDICIONAIS ---
        if "Sim" in (r150 or ""):
            st.write("**15.1 Assinale quais os serviços que possuem entidade responsável pela regulação e fiscalização:**")
            d151 = res_data.get("15.1", {"valor": "[]", "pontos": 0, "link": ""})
            
            col1_151, col2_151 = st.columns([1, 2])
            with col1_151:
                opts151 = {
                    "Abastecimento de água potável: – 01": 1, 
                    "Esgotamento sanitário: – 01": 1, 
                    "Limpeza urbana e manejo de resíduos sólidos: – 01": 1, 
                    "Drenagem e manejo das águas pluviais urbanas: – 00": 0
                }
                sel151 = []
                pts151 = 0
                texto_salvo_151 = str(d151["valor"])
                for txt, pts in opts151.items():
                    if st.checkbox(txt, value=txt in texto_salvo_151, key=f"q151_{txt}_{ano_sel}"):
                        sel151.append(txt)
                        pts151 += pts
            with col2_151:
                l151 = st.text_area("Link/Evidência (15.1):", value=d151.get("link", ""), key=f"l151_{ano_sel}", height=100)
                
                # SUPORTE MULTI-LINKS ATIVOS
                links_151_atuais = re.findall(r'(https?://[^\s]+)', l151)
                if links_151_atuais:
                    botoes_151 = " | ".join([f"🔗 [{u}]({u})" for u in links_151_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_151}")
                
            if str(sel151) != d151["valor"] or l151 != d151["link"]:
                save_resp("15.1", str(sel151), pts151, l151)
                
                # Limpeza cirúrgica de subdependentes desmarcados
                if "Abastecimento de água potável: – 01" not in sel151:
                    save_resp("15.1.1", "", 0, "")
                if "Esgotamento sanitário: – 01" not in sel151:
                    save_resp("15.1.2", "", 0, "")
                if "Limpeza urbana e manejo de resíduos sólidos: – 01" not in sel151:
                    save_resp("15.1.3", "", 0, "")
                if "Drenagem e manejo das águas pluviais urbanas: – 00" not in sel151:
                    save_resp("15.1.4", "", 0, "")
                    
                if links_151_atuais:
                    links_151_antigos = re.findall(r'(https?://[^\s]+)', d151["link"])
                    if links_151_atuais != links_151_antigos:
                        if 'modal_aviso_link' in globals():
                            modal_aviso_link("15.1", links_151_atuais)
                        else:
                            st.rerun()
                    else:
                        st.rerun()
                else:
                    st.rerun()
                    
            bloco_comentarios("15.1", res_data)

            # --- DEPENDÊNCIAS DO 15.1 ---
            if "Abastecimento de água potável: – 01" in sel151:
                st.write("**15.1.1 Informe a entidade responsável pela regulação e fiscalização do abastecimento de água potável do município:**")
                d1511 = res_data.get("15.1.1", {"valor": "", "link": ""})
                v1511 = st.text_area("Entidade responsável (15.1.1):", value=d1511["valor"], key=f"q1511_{ano_sel}", height=100)
                if v1511 != d1511["valor"]:
                    save_resp("15.1.1", v1511, 0, "")
                bloco_comentarios("15.1.1", res_data)

            if "Esgotamento sanitário: – 01" in sel151:
                st.write("**15.1.2 Informe a entidade responsável pela regulação e fiscalização do esgotamento sanitário do município:**")
                d1512 = res_data.get("15.1.2", {"valor": "", "link": ""})
                v1512 = st.text_area("Entidade responsável (15.1.2):", value=d1512["valor"], key=f"q1512_{ano_sel}", height=100)
                if v1512 != d1512["valor"]:
                    save_resp("15.1.2", v1512, 0, "")
                bloco_comentarios("15.1.2", res_data)

            if "Limpeza urbana e manejo de resíduos sólidos: – 01" in sel151:
                st.write("**15.1.3 Informe a entidade responsável pela regulação e fiscalização de limpeza urbana e manejo de resíduos sólidos do município:**")
                d1513 = res_data.get("15.1.3", {"valor": "", "link": ""})
                v1513 = st.text_area("Entidade responsável (15.1.3):", value=d1513["valor"], key=f"q1513_{ano_sel}", height=100)
                if v1513 != d1513["valor"]:
                    save_resp("15.1.3", v1513, 0, "")
                bloco_comentarios("15.1.3", res_data)

            if "Drenagem e manejo das águas pluviais urbanas: – 00" in sel151:
                st.write("**15.1.4 Informe a entidade responsável pela regulação e fiscalização de drenagem e manejo das águas pluviais urbanas do município:**")
                d1514 = res_data.get("15.1.4", {"valor": "", "link": ""})
                v1514 = st.text_area("Entidade responsável (15.1.4):", value=d1514["valor"], key=f"q1514_{ano_sel}", height=100)
                if v1514 != d1514["valor"]:
                    save_resp("15.1.4", v1514, 0, "")
                bloco_comentarios("15.1.4", res_data)
                
        st.markdown('</div>', unsafe_allow_html=True)

        # --- SEÇÃO 16: IMPRESSÕES ---
        st.divider()
        st.header("16.0 Impressões Finais")
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO 16.0")
        st.write("**Deixe suas impressões finais sobre o preenchimento do questionário:**")
        d160_valor = res_data.get("16.0_valor", {"valor": "", "link": ""})
        v160_valor = st.text_area("Impressões Finais (16.0):", value=d160_valor["valor"], key=f"q160_valor_{ano_sel}", height=200)
        if v160_valor != d160_valor["valor"]:
            save_resp("16.0_valor", v160_valor, 0, "")
            st.rerun()
        bloco_comentarios("16.0_valor", res_data)

        
    with aba_ext:
        st.header("📊 Dados Externos do Meio Ambiente")
        
        # A1: ICTEM
        st.markdown('<div class="externo-card">', unsafe_allow_html=True)
        st.subheader("A1 - ICTEM (Indicador de Coleta de Tratabilidade de Esgoto)- Dados da CETESB. Não sujeitos à validação. Fórmula de cálculo: Pontuação: se ICTEM >= 7,5 - 00 se 5,0 < ICTEM <= 7,5 - -50 (perde 50 pontos) se 2,5 < ICTEM <= 5,0 - -150 (perde 150 pontos) se ICTEM <= 2,5 - -200 (perde 200 pontos)")
        d_a1 = res_data.get("A1", {"valor": 10.0, "pontos": 0})
        v_a1 = st.number_input("Informe o ICTEM:", min_value=0.0, max_value=10.0, value=float(d_a1["valor"]), step=0.1, key=f"ext_a1_{ano_sel}")
        pts_a1 = 0
        if v_a1 >= 7.5: pts_a1 = 0
        elif 5.0 < v_a1 <= 7.5: pts_a1 = -50
        elif 2.5 < v_a1 <= 5.0: pts_a1 = -150
        else: pts_a1 = -200
        if v_a1 != float(d_a1["valor"]):
            save_resp("A1", v_a1, pts_a1, "Dados CETESB")
            st.rerun()
        st.write(f"**Pontuação:** {pts_a1}")
        st.markdown('</div>', unsafe_allow_html=True)

        # A2: IQR
        st.markdown('<div class="externo-card">', unsafe_allow_html=True)
        st.subheader("A2 - IQR (Índice de Qualidade de Aterro)- Dados da CETESB. Não sujeitos à avalidação. Fórmula de cálculo: Condições adequadas - 00 pontos Condições inadequadas - Rebaixar i-Amb 1 Faixa")
        d_a2 = res_data.get("A2", {"valor": "Condições adequadas", "pontos": 0})
        opc_a2 = ["Condições adequadas", "Condições inadequadas"]
        idx_a2 = opc_a2.index(d_a2["valor"]) if d_a2["valor"] in opc_a2 else 0
        v_a2 = st.selectbox("Utilização do IQR:", opc_a2, index=idx_a2, key=f"ext_a2_{ano_sel}")
        if v_a2 != d_a2["valor"]:
            save_resp("A2", v_a2, 0, "Dados CETESB")
            st.rerun()
        if v_a2 == "Condições inadequadas":
            st.warning("⚠️ Esta condição rebaixará o i-AMB em uma faixa no resultado final.")
        st.markdown('</div>', unsafe_allow_html=True)

        # A3: IQT
        st.markdown('<div class="externo-card">', unsafe_allow_html=True)
        st.subheader("A3 - IQT (Índice de Qualidade de Estações de Transbordo)Dados da CETESB. Não sujeitos à validação. Fórmula de cálculo: De 0,0 a 7,0 - Condições inadequadas De 7,1 a 10,0 - Condições adequadas Fórmula de cálculo: Condições adequadas - 00 pontos Condições inadequadas - -50 (perde 50 pontos)")
        d_a3 = res_data.get("A3", {"valor": 10.0, "pontos": 0})
        v_a3 = st.number_input("Informe o IQT:", min_value=0.0, max_value=10.0, value=float(d_a3["valor"]), step=0.1, key=f"ext_a3_{ano_sel}")
        pts_a3 = 0 if v_a3 > 7.0 else -50
        if v_a3 != float(d_a3["valor"]):
            save_resp("A3", v_a3, pts_a3, "Dados CETESB")
            st.rerun()
        st.write(f"**Status:** {'Adequado' if v_a3 > 7.0 else 'Inadequado'}")
        st.write(f"**Pontuação:** {pts_a3}")
        st.markdown('</div>', unsafe_allow_html=True)

        # --- QUESITO A4.1 ---
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO A4.1")
        st.write("**Informe quais dados foram enviados ao SINISA:**")
        st.caption("Dados do SINISA. Não sujeitos à validação.")

        # Busca dados salvos ou define o padrão limpo de segurança
        dA41 = res_data.get("A4.1", {"valor": "[]", "pontos": 0.0, "link": ""}) or {"valor": "[]", "pontos": 0.0, "link": ""}

        col1, col2 = st.columns([1, 2])

        with col1:
            # Definição das opções baseadas no enunciado
            optsA41 = [
                "Abastecimento de água e esgotamento sanitário",
                "Limpeza urbana e manejo de resíduos sólidos",
                "Drenagem e manejo de águas pluviais urbanas"
            ]
    
            selA41 = []
            ptsA41 = 0.0 # Não sujeito à validação/pontuação ativa
            texto_salvo_A41 = str(dA41["valor"])
    
            # Renderiza as caixas de seleção (Iniciam marcadas 'True' se o banco estiver vazio, conforme o ☒ do enunciado)
            for i, txt in enumerate(optsA41):
                # Se houver histórico, respeita o histórico. Se for a primeira vez, inicia como True (marcado)
                valor_inicial = txt in texto_salvo_A41 if dA41["valor"] != "[]" else True
        
                if st.checkbox(txt, value=valor_inicial, key=f"qA41_opt_{i}_{ano_sel}"):
                    selA41.append(txt)

            st.metric(label="Pontuação", value=f"{ptsA41:.1f} pts")

        with col2:
            # Campo para inserção de link ou comprovante de envio ao SINISA
            lA41 = st.text_area("Link/Evidência (A4.1):", value=dA41.get("link", ""), key=f"lA41_evid_unique_{ano_sel}", height=120)

        # Salva as alterações se o usuário marcar/desmarcar algo ou editar o link
        if str(selA41) != dA41["valor"] or lA41 != dA41["link"]:
            save_resp("A4.1", str(selA41), float(ptsA41), lA41)
            st.rerun()

        bloco_comentarios("A4.1", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # A4.1.1: Saneamento (SINISA)
        st.markdown('<div class="externo-card">', unsafe_allow_html=True)
        st.subheader("A4.1.1 - Abastecimento e Esgotamento (SINISA)")
        
        # Água
        d_agua = res_data.get("A4.1.1_agua", {"valor": 0.0, "pontos": 0})
        p_agua = st.number_input("% Percentual de população atendida com abastecimento de água:", 0.0, 100.0, float(d_agua["valor"]), key=f"ext_agua_{ano_sel}")
        pts_agua = 0
        if p_agua == 100: pts_agua = 20
        elif 99 < p_agua < 100: pts_agua = ((p_agua - 99) / 1 * 10) + 10
        elif 90 < p_agua <= 99: pts_agua = (p_agua - 90) / 9 * 10
        
        # Exibe a pontuação atualizada na tela
        st.markdown(f"**Pontuação obtida:** `{pts_agua:.2f} / 20.0 pts`")
        
        if p_agua != float(d_agua["valor"]):
            save_resp("A4.1.1_agua", p_agua, pts_agua, "SINISA")
            st.rerun()
            
        st.write("---") # Divisor simples entre subquestões
            
        # Perdas
        d_perda = res_data.get("A4.1.1_perdas", {"valor": 0.0, "pontos": 0})
        p_perda = st.number_input("% Percentual de perdas na distribuição de água:", 0.0, 100.0, float(d_perda["valor"]), key=f"ext_perda_{ano_sel}")
        pts_perda = 0
        if p_perda == 0: pts_perda = 0
        elif 0 < p_perda <= 10: pts_perda = (p_perda / 10) * (-5)
        elif 10 < p_perda <= 20: pts_perda = ((p_perda - 10) / 10 * (-2)) - 5
        else: pts_perda = -10
        
        # Exibe o impacto de perda (penalidade) na tela de forma direta
        if pts_perda < 0:
            st.markdown(f"⚠️ **Penalidade aplicada (Perdas):** :red[{pts_perda:.2f} pts]")
        else:
            st.markdown(f"**Penalidade aplicada (Perdas):** `0.00 pts (Sem perdas)`")
            
        if p_perda != float(d_perda["valor"]):
            save_resp("A4.1.1_perdas", p_perda, pts_perda, "SINISA")
            st.rerun()

        st.write("---")

        # Esgoto Coleta
        d_esg = res_data.get("A4.1.1_esgoto", {"valor": 0.0, "pontos": 0})
        p_esg = st.number_input("% Percentual de população atendida com coleta de esgoto:", 0.0, 100.0, float(d_esg["valor"]), key=f"ext_esg_{ano_sel}")
        pts_esg = 0
        if p_esg == 100: pts_esg = 20
        elif 90 < p_esg < 100: pts_esg = ((p_esg - 90) / 10 * 10) + 10
        elif 80 < p_esg <= 90: pts_esg = (p_esg - 80) / 10 * 10
        
        st.markdown(f"**Pontuação obtida:** `{pts_esg:.2f} / 20.0 pts`")
        
        if p_esg != float(d_esg["valor"]):
            save_resp("A4.1.1_esgoto", p_esg, pts_esg, "SINISA")
            st.rerun()

        st.write("---")

        # Tratamento Esgoto
        d_trat = res_data.get("A4.1.1_trat", {"valor": 0.0, "pontos": 0})
        p_trat = st.number_input("% Índice de tratamento de esgoto:", 0.0, 100.0, float(d_trat["valor"]), key=f"ext_trat_{ano_sel}")
        pts_trat = 0
        if p_trat == 100: pts_trat = 20
        elif 90 < p_trat < 100: pts_trat = ((p_trat - 90) / 10 * 10) + 10
        elif 80 < p_trat <= 90: pts_trat = (p_trat - 80) / 10 * 10
        
        st.markdown(f"**Pontuação obtida:** `{pts_trat:.2f} / 20.0 pts`")
        
        if p_trat != float(d_trat["valor"]):
            save_resp("A4.1.1_trat", p_trat, pts_trat, "SINISA")
            st.rerun()
            
        st.write("---")
            
        # Esgoto Tratado / Água Consumida
        d_trat_c = res_data.get("A4.1.1_trat_cons", {"valor": 0.0, "pontos": 0})
        p_trat_c = st.number_input("% Índice de esgoto tratado referido à água consumida:", 0.0, 100.0, float(d_trat_c["valor"]), key=f"ext_trat_c_{ano_sel}")
        pts_trat_c = 0
        if p_trat_c == 100: pts_trat_c = 30
        elif 90 < p_trat_c < 100: pts_trat_c = ((p_trat_c - 90) / 10 * 10) + 10
        elif 80 < p_trat_c <= 90: pts_trat_c = (p_trat_c - 80) / 10 * 10
        
        st.markdown(f"**Pontuação obtida:** `{pts_trat_c:.2f} / 30.0 pts`")
        
        if p_trat_c != float(d_trat_c["valor"]):
            save_resp("A4.1.1_trat_cons", p_trat_c, pts_trat_c, "SINISA")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        # A4.1.2: Resíduos Coleta
        st.markdown('<div class="externo-card">', unsafe_allow_html=True)
        st.subheader("A4.1.2 - Coleta de Resíduos (SINISA)")
        d_col_res = res_data.get("A4.1.2_coleta", {"valor": 0.0, "pontos": 0})
        p_col_res = st.number_input("% Cobertura coleta domiciliar (Pop. Total):", 0.0, 100.0, float(d_col_res["valor"]), key=f"ext_col_res_{ano_sel}")
        pts_col_res = 0
        if p_col_res == 100: pts_col_res = 20
        elif 99 < p_col_res < 100: pts_col_res = ((p_col_res - 99) / 1 * 10) + 10
        elif 90 < p_col_res <= 99: pts_col_res = (p_col_res - 90) / 9 * 10
        
        st.markdown(f"**Pontuação obtida:** `{pts_col_res:.2f} / 20.0 pts`")
        
        if p_col_res != float(d_col_res["valor"]):
            save_resp("A4.1.2_coleta", p_col_res, pts_col_res, "SINISA")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        # A4.1.3: Massa Resíduos
        st.markdown('<div class="externo-card">', unsafe_allow_html=True)
        st.subheader("A4.1.3 - Massa de Resíduos (SINISA)")
        
        # Massa Dia
        d_m_dia = res_data.get("A4.1.3_massa_dia", {"valor": 1.5, "pontos": 0})
        m_dia = st.number_input("Massa coletada de resíduos sólidos da população urbana por dia (em kg/hab/dia):", 0.0, 10.0, float(d_m_dia["valor"]), key=f"ext_m_dia_{ano_sel}")
        pts_m_dia = 0
        if m_dia > 1: pts_m_dia = 0
        elif 0.99 < m_dia <= 1: pts_m_dia = ((1 - m_dia) / 0.01 * 2) + 1
        elif 0.90 < m_dia <= 0.99: pts_m_dia = ((0.99 - m_dia) / 0.09 * 3) + 5
        elif 0.70 < m_dia <= 0.90: pts_m_dia = ((0.90 - m_dia) / 0.2 * 2) + 7
        else: pts_m_dia = 10
        
        st.markdown(f"**Pontuação obtida:** `{pts_m_dia:.2f} / 10.0 pts`")
        
        if m_dia != float(d_m_dia["valor"]):
            save_resp("A4.1.3_massa_dia", m_dia, pts_m_dia, "SINISA")
            st.rerun()

        st.write("---")

        # Massa Ano (Recicláveis)
        d_m_ano = res_data.get("A4.1.3_massa_ano", {"valor": 0.0, "pontos": 0})
        m_ano = st.number_input("Massa recuperada per capita de materiais recicláveis em relação a população urbana (em kg/hab/ano):", 0.0, 500.0, float(d_m_ano["valor"]), key=f"ext_m_ano_{ano_sel}")
        pts_m_ano = 0
        if m_ano > 73: pts_m_ano = 12
        elif 36.5 < m_ano <= 73: pts_m_ano = ((m_ano - 36.5) / 36.5 * 2) + 5
        elif 20 < m_ano <= 36.5: pts_m_ano = ((m_ano - 20) / 16.5 * 2) + 3
        elif 8 < m_ano <= 20: pts_m_ano = (m_ano - 8) / 12 * 3
        
        st.markdown(f"**Pontuação obtida:** `{pts_m_ano:.2f} / 12.0 pts`")
        
        if m_ano != float(d_m_ano["valor"]):
            save_resp("A4.1.3_massa_ano", m_ano, pts_m_ano, "SINISA")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

        # --- QUESITO A4.1.4 ---
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO A4.1.4")
        st.write("**Dados sobre drenagem e/ou manejo de águas pluviais urbanas:**")
        st.caption("Dados do SINISA. Não sujeitos à validação.")

        # Busca dados salvos ou define o padrão limpo de segurança
        dA414 = res_data.get("A4.1.4", {"valor": "0.0|0.0|0.0", "pontos": 0.0, "link": ""}) or {"valor": "0.0|0.0|0.0", "pontos": 0.0, "link": ""}

        # Tenta recuperar os 3 valores salvos na string "taxa1|taxa2|taxa3"
        try:
            t_pav, t_red, p_risco = map(float, dA414["valor"].split("|"))
        except:
            t_pav, t_red, p_risco = 0.0, 0.0, 0.0

        col1, col2 = st.columns([1, 2])

        with col1:
            v_pav = st.number_input(
                "Taxa de cobertura de pavimentação e meio-fio (%):", 
                min_value=0.0, max_value=100.0, value=t_pav, step=0.1, key=f"qA414_pav_{ano_sel}"
            )

            v_red = st.number_input(
            "Taxa de cobertura de vias públicas com redes/canais subterrâneos (%):", 
            min_value=0.0, max_value=100.0, value=t_red, step=0.1, key=f"qA414_red_{ano_sel}"
            )

            v_risco = st.number_input(
            "Parcela de domicílios em situação de risco de inundação (%):", 
            min_value=0.0, max_value=100.0, value=p_risco, step=0.1, key=f"qA414_risco_{ano_sel}"
            )

            ptsA414 = 0.0
            st.metric(label="Pontuação", value=f"{ptsA414:.1f} pts")

        with col2:
            lA414 = st.text_area("Link/Evidência (A4.1.4):", value=dA414.get("link", ""), key=f"lA414_evid_unique_{ano_sel}", height=180)

        valores_consolidados = f"{v_pav}|{v_red}|{v_risco}"

        if valores_consolidados != dA414["valor"] or lA414 != dA414["link"]:
            save_resp("A4.1.4", valores_consolidados, float(ptsA414), lA414)
            st.rerun()

        bloco_comentarios("A4.1.4", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # --- QUESITO A5 ---
        st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
        st.subheader("QUESITO A5")
        st.write("**Foi instituída taxa / tarifa de cobrança dos serviços de limpeza urbana e manejo de resíduos sólidos?**")
        st.caption("Dados do SINISA. Não sujeitos à validação.")

        # Busca dados salvos ou define o padrão limpo de segurança
        dA5 = res_data.get("A5", {"valor": "Não foi informado", "pontos": 0.0, "link": ""}) or {"valor": "Não foi informado", "pontos": 0.0, "link": ""}

        col1, col2 = st.columns([1, 2])

        with col1:
            # Opções textuais conforme o enunciado do SINISA
            optsA5 = [
                "Sim",
                "Não",
                "Não foi informado"
            ]
    
            # Identifica o índice salvo para manter o estado do botão
            idx_salvoA5 = optsA5.index(dA5["valor"]) if dA5["valor"] in optsA5 else 2
    
            # Renderiza o botão de escolha única
            selA5 = st.radio("Selecione uma opção:", options=optsA5, index=idx_salvoA5, key=f"qA5_radio_unique_{ano_sel}")
    
            # Pontuação neutra (Não sujeito à validação)
            ptsA5 = 0.0
            st.metric(label="Pontuação", value=f"{ptsA5:.1f} pts")

        with col2:
            # Campo para links, decretos ou comprovantes de instituição da taxa
            lA5 = st.text_area("Link/Evidência (A5):", value=dA5.get("link", ""), key=f"lA5_evid_unique_{ano_sel}", height=120)

        # Salva no banco de dados se houver alteração na resposta ou na evidência
        if selA5 != dA5["valor"] or lA5 != dA5["link"]:
            save_resp("A5", selA5, float(ptsA5), lA5)
            st.rerun()

        bloco_comentarios("A5", res_data)
        st.markdown('</div>', unsafe_allow_html=True)

        # A6: Balança
        st.markdown('<div class="externo-card">', unsafe_allow_html=True)
        st.subheader("A6 - Utilização de Balança")
        d_a6 = res_data.get("A6", {"valor": "Não", "pontos": 0})
        opc_a6 = ["Sim", "Não", "Não foi informado"]
        idx_a6 = opc_a6.index(d_a6["valor"]) if d_a6["valor"] in opc_a6 else 1
        v_a6 = st.selectbox("Utiliza balança para pesagem rotineira?", opc_a6, index=idx_a6, key=f"ext_a6_{ano_sel}")
        pts_a6 = 5 if v_a6 == "Sim" else 0
        if v_a6 != d_a6["valor"]:
            save_resp("A6", v_a6, pts_a6, "SINISA")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with aba_graf:
        st.header("📈 Evolução e Desempenho")
        all_data = get_all_years_data()
        if all_data:
            anos_lista = sorted(all_data.keys())
            totais = [sum(item.get("pontos", 0) for k, item in all_data[ano].items() if not k.startswith("COM_")) for ano in anos_lista]
            fig = px.bar(x=anos_lista, y=totais, labels={'x':'Ano', 'y':'Pontuação'}, title="Pontuação Total por Ano")
            st.plotly_chart(fig)
        else:
            st.info("Ainda não há dados para gerar gráficos.")

def main():
    st.set_page_config(page_title="i-AMB Auditoria Ambiental", layout="wide")
    mostrar_formulario_amb()

if __name__ == "__main__":
    main()
