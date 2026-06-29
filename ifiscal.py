import streamlit as st
import sqlite3
import re
import json
from io import BytesIO
from datetime import datetime, date

# Importações essenciais do ReportLab para a geração do PDF do i-Fiscal
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# =============================================================================
# CONSTANTES GLOBAIS - MATRIZ DE QUESITOS OFICIAL DO I-FISCAL
# =============================================================================

FAIXA_CORES = {
    "C": "#ef4444", 
    "C+": "#f97316", 
    "B": "#eab308", 
    "B+": "#22c55e", 
    "A": "#16a34a"
}

CATEGORIAS_MAP = {
    "infraestrutura": {
        "label": "Infraestrutura e Setor Fiscal", 
        "qids": ["1.1", "1.2", "1.3", "1.4", "1.5", "1.5.1"]
    },
    "planejamento": {
        "label": "Planejamento e Diretrizes Orçamentárias", 
        "qids": ["2.0", "3.0", "4.3"]
    },
    "transparencia_gov": {
        "label": "Transparência Fiscal e Governo Digital", 
        "qids": ["5.0", "5.3", "5.4", "6.0"]
    },
    "sistemas_gestao": {
        "label": "Sistemas de Gestão Financeira e Operações", 
        "qids": ["8.0", "8.1", "8.2", "9.4", "9.4.1", "11.0", "13.0", "13.3"]
    },
    "seguranca_processos": {
        "label": "Segurança da Informação e Processos Fiscais", 
        "qids": ["18.1", "19.0", "19.1", "20.0", "20.1", "21.0", "22.0"]
    },
    "auditoria_final": {
        "label": "Quesitos de Auditoria Final (Bloco F)", 
        "qids": [
            "F1", "F2", "F3", "F4", "F5", "F8", "F10", 
            "F12", "F13", "F14", "F15", "F16", "F17", "F18", "F20"
        ]
    },
}

PONTUACOES_MAX = {
    # Quesitos Numéricos
    "1.1": 0.5, "1.2": 1.5, "1.3": 10.0, "1.4": 3.0, "1.5": 5.0, "1.5.1": 5.0,
    "2.0": 4.0, "3.0": 30.0, "4.3": 5.0, 
    "5.0": 3.0, "5.3": 3.0, "5.4": 6.0, "6.0": 2.0, 
    "8.0": 1.0, "8.1": 2.0, "8.2": 15.0, "9.4": 2.0, "9.4.1": 3.0, "11.0": 3.0, "13.0": 1.0, "13.3": 9.0, 
    "18.1": 15.0, "19.0": 3.0, "19.1": 3.0, "20.0": 3.0, "20.1": 6.0, "21.0": 3.0, "22.0": 3.0,
    
    # Quesitos de Bloco F
    "F1": 75.0, "F2": 75.0, "F3": 100.0, "F4": 25.0, "F5": 25.0, 
    "F8": 75.0, "F10": 75.0, "F12": 50.0, "F13": 50.0, "F14": 50.0, 
    "F15": 25.0, "F16": 25.0, "F17": 75.0, "F18": 75.0, "F20": 50.0
}

# TEXTOS ENXUTOS PARA OS CARD DE PERGUNTAS DO FORMULÁRIO
TEXTO_PERGUNTAS = {
    "1.1": "A estrutura de fiscalização tributária municipal conta com corpo técnico próprio?",
    "1.2": "As instalações e equipamentos do setor de arrecadação atendem à demanda operacional?",
    "1.3": "Percentual de incremento real na arrecadação de ISSQN em relação ao ano base.",
    "1.4": "Possui legislação específica atualizada sobre a planta genérica de valores (IPTU)?",
    "1.5": "Regularidade e tempestividade no envio de dados de receita ao portal da transparência.",
    "1.5.1": "Existem mecanismos informatizados de conciliação bancária de receitas automáticos?",
    "2.0": "Compatibilidade das metas da LDO com os limites fiscais da Lei de Responsabilidade Fiscal.",
    "3.0": "Cumprimento das metas fiscais anuais de resultado primário e nominal fixadas na LOA.",
    "4.3": "Evidências de audiências públicas realizadas para discussão das peças orçamentárias.",
    "5.0": "O portal institucional atende à Lei de Acesso à Informação (LAI) em sua totalidade?",
    "5.3": "Disponibilização de ferramentas de Governo Digital e serviços tributários ao cidadão.",
    "5.4": "Publicação tempestiva dos Relatórios de Gestão Fiscal (RGF) e Resumido de Execução (RREO).",
    "6.0": "Existência de canal ou ouvidoria ativa para denúncias sobre inconformidades fiscais.",
    "8.0": "O sistema contábil emite alertas automatizados sobre o atingimento de limites da LRF?",
    "8.1": "O sistema integrado de gestão permite rastreabilidade completa de restos a pagar?",
    "8.2": "Nível de aderência do plano de contas municipal às diretrizes da STN (PCASP).",
    "9.4": "Existência de rotinas formais para controle e inscrição de créditos em Dívida Ativa.",
    "9.4.1": "A cobrança administrativa ou judicial de créditos tributários possui fluxo normatizado?",
    "11.0": "Controle interno atua na verificação prévia de conformidade das despesas fiscais?",
    "13.0": "Rotinas automatizadas para validação cadastral de fornecedores integradas ao TCE.",
    "13.3": "Adoção preferencial de pregão eletrônico e nova lei de licitações para atos de gestão.",
    "18.1": "Aplicação de políticas rígidas de segurança da informação nos bancos de dados fiscais.",
    "19.0": "Plano de contingência operacional formalizado em caso de indisponibilidade de sistemas.",
    "19.1": "Periodicidade e segurança dos backups dos sistemas de arrecadação e contabilidade.",
    "20.0": "Treinamento técnico continuado oferecido aos servidores da área de gestão fiscal.",
    "20.1": "Metodologia estruturada para identificação de gargalos de sonegação fiscal no município.",
    "21.0": "Regulamentação municipal sobre o teto remuneratório constitucional de agentes públicos.",
    "22.0": "Ações de combate à renúncia ilegal de receitas e monitoramento de benefícios fiscais.",
    "F1": "Bloqueio Crítico TCE: Rejeição integral de contas do exercício anterior por descumprimento de metas?",
    "F2": "Gatilho de Alerta: Gastos com pessoal consolidado acima do limite prudencial estabelecido?",
    "F3": "Compromisso de Gestão: Ocorrência de déficit financeiro estrutural sem justificativa aceita?",
    "F4": "Irregularidade em Repasses: Retenção ou atraso sistemático de duodécimo ao Legislativo?",
    "F5": "Ordem Cronológica: Quebra injustificada na ordem cronológica de pagamentos a fornecedores?",
    "F8": "Inconsistência Patrimonial: Divergências graves não conciliadas entre o balanço e inventários?",
    "F10": "Mecanismos Anticorrupção: Falha grave na instituição ou atuação do sistema de controle interno?",
    "F12": "Transparência Omissa: Não disponibilização de dados fiscais no SICONFI nos prazos legais?",
    "F13": "Renúncia Injustificada: Concessão de isenções tributárias sem estimativa de impacto fiscal?",
    "F14": "Endividamento Extremo: Operações de crédito realizadas acima do limite autorizado pelo Senado?",
    "F15": "Precatórios Judiciais: Descumprimento do regime especial ou ordinário de pagamento de precatórios?",
    "F16": "Créditos Adicionais: Abertura de créditos suplementares sem a existência de recursos disponíveis?",
    "F17": "Fundo de Previdência: Existência de repasses atrasados ou insuficientes ao RPPS municipal?",
    "F18": "Educação/Saúde: Descumprimento das aplicações mínimas constitucionais em MDE ou ASPS?",
    "F20": "Dívida Ativa Inerte: Ausência absoluta de cobrança judicial que resulte em prescrição de débitos?"
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
    if st.button("Confirmo que o link está liberado para o público", key=f"btn_conf_{qid}_fiscal"):
        st.rerun()

# =============================================================================
# 1. FUNÇÕES DE APOIO E BANCO DE DADOS (IEGM - I-FISCAL)
# =============================================================================

def get_connection():
    # Conecta no banco de dados isolado e específico do I-FISCAL
    return sqlite3.connect("dados_ifiscal.db", check_same_thread=False)

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
        
        # 2. PRAGMA para checar quais colunas realmente existem no arquivo físico do banco do I-FISCAL
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
            st.error(f"Erro operacional no banco do I-FISCAL: {e}")
    except Exception as e:
        st.error(f"Erro ao salvar {qid}: {e}")

def bloco_comentarios(questao_id, res_data, sufixo="fiscal"):
    """
    Gera o diálogo interno avançado com histórico retrátil, status em realtime
    e controle individual de remoção por lixeira para o módulo I-FISCAL.
    """
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
# 2. GERADOR DO RELATÓRIO PDF
# =============================================================================

def gerar_relatorio_pdf(dados, ano, total, faixa, all_data=None):
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

    style_titulo_capa = ParagraphStyle(
        'TituloCapa', 
        parent=styles['Normal'], 
        fontName='Helvetica-Bold', 
        fontSize=24, 
        leading=28, 
        textColor=colors.HexColor("#001A4D"), 
        alignment=1
    )

    # FOLHA 1: CAPA
    elements.append(Spacer(1, 100))
    try:
        logo = Image("iegm.png", width=380, height=180)
        logo.hAlign = 'CENTER'
        elements.append(logo)
    except Exception:
        elements.append(Paragraph("[Logo: i-Fiscal / IEGM]", styles["Title"]))
        
    elements.append(Spacer(1, 50))
    elements.append(Paragraph("Relatório de Avaliação i-Fiscal", style_titulo_capa))
    elements.append(Spacer(1, 15))
    
    style_ano_capa = ParagraphStyle('AnoCapa', parent=styles['Normal'], fontName='Helvetica', fontSize=16, textColor=colors.HexColor("#7f8c8d"), alignment=1)
    elements.append(Paragraph(f"Exercício de Referência: {ano}", style_ano_capa))
    elements.append(PageBreak())

    # -------------------------------------------------------------------------
    # FOLHA 2: SUMÁRIO (Exatamente no seu padrão original de 6 itens)
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
    # FOLHA 3+: CONTEÚDO (Adaptado 100% para i-Fiscal)
    # -------------------------------------------------------------------------
    elements.append(Paragraph(f"RELATÓRIO DE AUDITORIA i-FISCAL - {ano}", styles["Title"]))
    elements.append(Spacer(1, 12))

    # --- TÓPICO 1 ---
    elements.append(Paragraph("<b>1. RESUMO EXECUTIVO (ANÁLISE COMPARATIVA)</b>", styles["h2"]))
    elements.append(Spacer(1, 8))

    nota_atual = float(total)
    ano_atual = int(str(ano).strip()[:4])
    ano_ant = ano_atual - 1

    def converter_pontos_em_faixa_ifiscal(pontos):
        pts = float(pontos)
        if pts < 500.0:              return "C"
        elif 500.0 <= pts <= 599.9:  return "C+"
        elif 600.0 <= pts <= 749.9:  return "B"
        elif 750.0 <= pts <= 899.9:  return "B+"
        else:                        return "A"

    if all_data is None:
        all_data = {}

    dados_ano_anterior = all_data.get(ano_ant, {})
    nota_anterior = 0.0
    if ano_ant in all_data:
        nota_anterior = float(sum(
            float(info_ant.get("pontos", 0)) 
            for qid_ant, info_ant in dados_ano_anterior.items() 
            if isinstance(info_ant, dict) and not qid_ant.startswith("COM_")
        ))

    faixa_anterior = converter_pontos_em_faixa_ifiscal(nota_anterior)
    faixa_real_atual = faixa if faixa else converter_pontos_em_faixa_ifiscal(nota_atual)

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
        texto_analise = f"<b>Análise de Tendência:</b> O município registrou uma evolução de desempenho com incremento de <b>{texto_percentual}</b> na sua pontuação global do i-Fiscal comparado ao exercício de {ano_ant}."
    elif variacao_pontos < 0:
        texto_analise = f"<b>Análise de Tendência:</b> <font color='#dc3545'><b>Alerta de Retrocesso:</b></font> Foi identificada uma redução de <b>{texto_percentual}</b> na eficiência dos indicadores do i-Fiscal em relação a {ano_ant}."
    else:
        texto_analise = f"<b>Análise de Tendência:</b> O município apresentou estagnação absoluta (0.00%) no seu índice geral de conformidade do i-Fiscal."

    elements.append(Paragraph(texto_analise, style_analise))
    elements.append(Spacer(1, 15))

    # --- TÓPICO 2 ---
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

    # Dicionário mapeado com os 20 quesitos e suas respectivas penalidades máximas
    PENALIDADES_MAX = {
        "7.2": -3.0,
        "8.3": -15.0,
        "9.6": -30.0,
        "10.3": -5.0,
        "12.1": -10.0,
        "12.2": -5.0,
        "12.3": -5.0,
        "12.3.1": -5.0,
        "12.5.2": -10.0,
        "16": -10.0,
        "16.3": -5.0,
        "17.0": -5.0,
        "23.0": -30.0,
        "24.1": -30.0,
        "25.1": -25.0,
        "F6": -20.0,
        "F7": -10.0,
        "F9": -10.0,
        "F21": -50.0,
        "F22": -5.0
    }

    lista_penalidades = []
    
    for qid, pen_max in PENALIDADES_MAX.items():
        info = dados.get(qid, {}) if isinstance(dados.get(qid), dict) else {"pontos": 0.0, "valor": "Não Respondido", "link": ""}
        
        try:
            nota_real = float(info.get("pontos", 0.0))
        except (ValueError, TypeError):
            nota_real = 0.0
        
        # Lógica de Eficiência Preventiva e Status de Risco baseado na nota negativa (penalidade)
        if nota_real < 0:
            if nota_real <= pen_max:
                eficiencia_preventiva = 0.0
                status_html = "<font color='#dc3545'><b>Impacto Máximo Aplicado</b></font>"
            else:
                # Caso haja uma penalidade parcial aplicada
                eficiencia_preventiva = ((pen_max - nota_real) / pen_max) * 100
                status_html = f"<font color='#e67e22'><b>Impacto Parcial ({nota_real:.1f} pts)</b></font>"
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
    
    # Ordena exibindo primeiro os quesitos onde a penalidade causou maior impacto (menor eficiência)
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
        
    tabela_pen = Table(data_penalidades, colWidths=[65, 95, 115, 115, 150])
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
    # 4. DIAGNÓSTICO DE REINCIDÊNCIAS (GARGALOS PERSISTENTES)
    # -------------------------------------------------------------------------
    elements.append(Paragraph("<b>4. DIAGNÓSTICO DE REINCIDÊNCIAS (GARGALOS PERSISTENTES)</b>", styles["h2"]))
    elements.append(Spacer(1, 6))
    
    reincidencias_detectadas = []
    
    # IMPORTANTE: Use o dicionário PONTUACOES_MAX definido globalmente no seu sistema i-Fiscal
    # para validar os tetos oficiais de cada quesito de nota real.
    tetos_referencia = PONTUACOES_MAX if 'PONTUACOES_MAX' in globals() else {}
    
    for qid, info_atual in dados.items():
        # Ignora comentários e chaves que não sejam dicionários válidos
        if qid.startswith("COM_") or not isinstance(info_atual, dict): 
            continue
            
        # Só avalia se o quesito pertencer à lista de pontuações oficiais do i-Fiscal
        if qid not in tetos_referencia:
            continue
            
        pts_maximo = float(tetos_referencia[qid])
        pts_obtidos_atual = float(info_atual.get("pontos", 0.0))
        
        # Só analisa se o teto for válido e se houve falha real no ano atual (eficiência menor que 50%)
        if pts_maximo > 0 and (pts_obtidos_atual / pts_maximo) * 100 < 50.0:
            # Busca o mesmo quesito no ano anterior
            info_ant = dados_ano_anterior.get(qid, {}) if isinstance(dados_ano_anterior, dict) else {}
            pts_obtidos_ant = float(info_ant.get("pontos", 0.0)) if isinstance(info_ant, dict) else 0.0
            
            # Se também falhou no ano anterior (eficiência menor que 50%), temos uma Reincidência Crônica
            if (pts_obtidos_ant / pts_maximo) * 100 < 50.0:
                # Define a categoria dinamicamente com base no perfil do quesito no i-Fiscal
                qid_str = str(qid).strip().upper()
                if qid_str.startswith("7") or qid_str.startswith("8") or qid_str.startswith("9"):
                    origem = "Gestão Orçamentária"
                elif qid_str.startswith("10") or qid_str.startswith("12") or qid_str.startswith("16"):
                    origem = "Planejamento e Execução"
                elif qid_str.startswith("F"):
                    origem = "Controle Fiscal / Receita"
                else:
                    origem = "Administração Financeira"
                    
                reincidencias_detectadas.append({
                    "qid": qid,
                    "tipo": origem,
                    "detalhe": "Ineficiência Crônica de Desempenho (Abaixo de 50% por 2 anos)",
                    "ant": f"{pts_obtidos_ant:.1f} pts",
                    "atual": f"{pts_obtidos_atual:.1f} pts"
                })

    if reincidencias_detectadas:
        data_reinc = [["Quesito", "Origem da Falha", "Impacto Histórico", "Exercício Anterior", "Exercício Atual"]]
        
        # Ordenação segura para o i-Fiscal (suporta quesitos numéricos como '7.2' e alfanuméricos como 'F6')
        def extrair_chave_ordenacao(item):
            partes = []
            for p in item["qid"].split('.'):
                if p.isdigit():
                    partes.append(int(p))
                else:
                    # Se for letra (ex: 'F6'), converte para ordinais para ordenar corretamente
                    partes.append(sum(ord(char) for char in p))
            return partes

        for reinc in sorted(reincidencias_detectadas, key=extrair_chave_ordenacao): 
            data_reinc.append([
                reinc["qid"], 
                reinc["tipo"], 
                Paragraph(f"<b>{reinc['detalhe']}</b>", styles["Normal"]), 
                reinc["ant"], 
                reinc["atual"]
            ])
            
        tabela_reinc = Table(data_reinc, colWidths=[65, 125, 160, 75, 65])
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
        elements.append(Paragraph("<font color='#28a745'><b>✅ Nenhuma reincidência ativa detectada. O município corrigiu ou mitigou os gargalos fiscais do ano anterior.</b></font>", styles["Normal"]))
        
    elements.append(Spacer(1, 15))

    # -------------------------------------------------------------------------
    # 5. ALINHAMENTO COM A AGENDA 2030 (METAS ODS / ONU)
    # -------------------------------------------------------------------------
    import reportlab.lib.colors as rl_colors

    elements.append(Paragraph("<b>5. ALINHAMENTO COM A AGENDA 2030 (METAS ODS / ONU)</b>", styles["h2"]))
    elements.append(Spacer(1, 6))

    def calcular_percentual_checklist(resposta_bruta, total_itens):
        if not resposta_bruta: 
            return 0.0
        
        # Trata estruturas de lista puras ou em formato string vindas do banco
        if str(resposta_bruta).startswith("["):
            try:
                import ast
                itens_lista = ast.literal_eval(str(resposta_bruta))
                if isinstance(itens_lista, list):
                    itens_validos = [str(i).strip().lower() for i in itens_lista if i and "outros" not in str(i).lower() and "não" not in str(i).lower()]
                    return min((len(itens_validos) / total_itens) * 100.0, 100.0) if total_itens > 0 else 0.0
            except Exception:
                pass
                
        # Fallback para strings separadas por vírgula
        itens = [i.strip().lower() for i in str(resposta_bruta).split(",") if i.strip()]
        itens_validos = [i for i in itens if "outros" not in i and "não" not in i]
        return min((len(itens_validos) / total_itens) * 100.0, 100.0) if total_itens > 0 else 0.0

    # Dicionário parametrizado estritamente com as regras fornecidas para o i-Fiscal
    REGRAS_ODS = {
        "1.0": {"metas": "17.1", "total_chk": 0},
        "1.1": {"metas": "Mapeada", "total_chk": 0},
        "1.3": {"metas": "17.1", "total_chk": 0},
        "1.4": {"metas": "16.5, 17.1", "total_chk": 0},
        "3.0": {"metas": "17.1", "total_chk": 0},
        "3.1": {"metas": "17.1", "total_chk": 8},   # Múltipla escolha (8 opções)
        "4.0": {"metas": "17.1", "total_chk": 0},
        "5.0": {"metas": "17.1", "total_chk": 0},
        "7.0": {"metas": "17.1", "total_chk": 0},
        "7.3": {"metas": "10.4, 17.1", "total_chk": 5}, # Múltipla escolha (5 opções)
        "8.0": {"metas": "17.1", "total_chk": 0},
        "8.1": {"metas": "17.1", "total_chk": 0},
        "8.2": {"metas": "17.1", "total_chk": 0},
        "9.0": {"metas": "17.1", "total_chk": 0},
        "9.4": {"metas": "17.1", "total_chk": 0},
        "9.5": {"metas": "17.1", "total_chk": 3},   # Múltipla escolha (3 opções)
        "9.6": {"metas": "10.4, 17.1", "total_chk": 0},
        "10.0": {"metas": "17.1", "total_chk": 0},
        "10.3": {"metas": "17.1", "total_chk": 0},
        "11.0": {"metas": "17.1", "total_chk": 0},
        "12.0": {"metas": "10.4, 16.6, 17.1", "total_chk": 0},
        "13.0": {"metas": "16.6, 16.7, 17.1", "total_chk": 0},
        "16": {"metas": "16.6, 17.1", "total_chk": 0},
        "17.0": {"metas": "17.1", "total_chk": 0},
        "23.0": {"metas": "17.1", "total_chk": 0},
        "25.0": {"metas": "17.1", "total_chk": 0}
    }

    analise_ods = []
    
    # Captura dinâmica do dicionário de dados do escopo para evitar NameError
    dados_reference = None
    for nome_var in ['dados', 'res_data', 'respostas', 'dados_municipio']:
        if nome_var in locals():
            dados_reference = locals()[nome_var]
            break

    if dados_reference is None:
        try: dados_reference = dados
        except NameError:
            try: dados_reference = res_data
            except NameError: dados_reference = {}

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
            # Regras de avaliação lógica customizadas para cada cenário do i-Fiscal
            if qid in ["9.6", "12.0"]:
                if "não" in resp_l:
                    status = "Atendido"
                else:
                    status = "Não Atendido"
            elif qid == "8.2":
                if "sistema automatizado" in resp_l or "manualmente" in resp_l:
                    status = "Atendido"
                else:
                    status = "Não Atendido"
            elif qid == "17.0":
                if "todas as ações" in resp_l:
                    status = "Atendido"
                else:
                    status = "Não Atendido"
            elif qid == "23.0":
                if "dentro do prazo" in resp_l:
                    status = "Atendido"
                else:
                    status = "Não Atendido"
            else:
                if "sim" in resp_l or "parcialmente" in resp_l or "integralmente" in resp_l:
                    status = "Atendido"
                else:
                    status = "Não Atendido"

        # Sanatização da visualização de listas salvas
        exibicao_resp = resp
        if exibicao_resp.startswith("["):
            exibicao_resp = exibicao_resp.replace("[", "").replace("]", "").replace("'", "").replace('"', '')

        analise_ods.append({
            "qid": qid,
            "status": status,
            "metas": config["metas"],
            "resp": exibicao_resp[:45] + "..." if len(exibicao_resp) > 45 else exibicao_resp
        })

    if analise_ods:
        data_ods = [["Quesito", "Resposta Informada", "Vínculo Metas ODS", "Status de Cumprimento"]]
        style_td_ods = ParagraphStyle('TdOds', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, alignment=1)
        
        # Algoritmo de ordenação alfanumérica robusto para i-Fiscal (Ordena corretamente '1.0', '16', 'F6')
        def chave_ordenacao_ods(item):
            partes = []
            for p in item["qid"].split('.'):
                if p.isdigit():
                    partes.append(int(p))
                else:
                    partes.append(sum(ord(char) for char in p))
            return partes
        
        for item in sorted(analise_ods, key=chave_ordenacao_ods):
            st_txt = item["status"]
            
            if "Não Atendido" in st_txt:
                st_p = Paragraph(f"<font color='#dc3545'><b>{st_txt}</b></font>", style_td_ods)
            elif "Atendido" in st_txt and "%" not in st_txt:
                st_p = Paragraph(f"<font color='#28a745'><b>{st_txt}</b></font>", style_td_ods)
            else:
                # Destaque em azul para os percentuais apurados via checklist
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
            ("ALIGN", (2, 0), (3, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, rl_colors.HexColor("#0f9d58")), 
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(tabela_ods)
        elements.append(Spacer(1, 15))

    # -------------------------------------------------------------------------
    # 📊 6. SÉRIE HISTÓRICA DO I-FISCAL (CONSOLIDADO FINAL)
    # -------------------------------------------------------------------------
    # IMPORTS LOCAIS SEGUROS (Evita conflitos de escopo global no ReportLab)
    from reportlab.graphics.shapes import Drawing, String
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    import reportlab.lib.colors as rl_colors

    elements.append(Spacer(1, 10))
    elements.append(Paragraph("<b>6. SÉRIE HISTÓRICA DO I-FISCAL (CONSOLIDADO FINAL)</b>", styles["h2"]))
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

    import streamlit as st

    # Função auxiliar interna para calcular a nota líquida real (Pontos Positivos + Penalidades Negativas)
    def calcular_nota_liquida_fiscal(dicionario_dados):
        if not dicionario_dados or not isinstance(dicionario_dados, dict):
            return 0.0
        soma_positivos = 0.0
        soma_penalidades = 0.0
        for qid_h, info_h in dicionario_dados.items():
            if isinstance(info_h, dict) and not qid_h.startswith("COM_"):
                try:
                    val = float(info_h.get("pontos", 0.0))
                    if val > 0:
                        soma_positivos += val
                    else:
                        soma_penalidades += val  # Acumula as penalidades do Tópico 3
                except (ValueError, TypeError):
                    continue
        # A nota final do i-Fiscal é a composição de suas entregas mitigada pelo impacto do risco
        return max(0.0, min(soma_positivos + soma_penalidades, 1000.0))

    # Montagem dos dados do gráfico integrando as fontes do i-Fiscal
    for a in anos_serie:
        # 1. Se for o ano selecionado atualmente no formulário
        if a == ano_reference: 
            if nota_reference > 0.0:
                valores_serie.append(min(nota_reference, 1000.0))
            elif 'dados_reference' in locals() and dados_reference:
                valores_serie.append(calcular_nota_liquida_fiscal(dados_reference))
            else:
                valores_serie.append(0.0)
                
        # 2. Se o ano estiver salvo no dicionário "all_data" passado por parâmetro
        elif 'all_data' in locals() and all_data and a in all_data:
            dados_ano = all_data[a]
            if isinstance(dados_ano, dict):
                valores_serie.append(calcular_nota_liquida_fiscal(dados_ano))
            else:
                valores_serie.append(min(max(float(dados_ano), 0.0), 1000.0))

        # 3. Fallback: Se o ano estiver salvo no histórico do session_state do Streamlit
        elif hasattr(st, 'session_state') and 'all_data' in st.session_state and a in st.session_state.all_data:
            dados_ano = st.session_state.all_data[a]
            if isinstance(dados_ano, dict):
                valores_serie.append(calcular_nota_liquida_fiscal(dados_ano))
            else:
                valores_serie.append(min(max(float(dados_ano), 0.0), 1000.0))
                
        # 4. Se não encontrar o histórico do exercício, deixa zerado
        else: 
            valores_serie.append(0.0)

    # Configuração da Área de Desenho do Gráfico
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
    
    # Escala baseada nas regras de pontuação do i-Fiscal (0 a 1000 pontos)
    bc.valueAxis.valueMin = 0
    bc.valueAxis.valueMax = 1000
    bc.valueAxis.valueStep = 200
    bc.valueAxis.labels.fontSize = 8
    
    # 🔥 ATIVAÇÃO DOS RÓTULOS (EXIBE A PONTUAÇÃO EXATA SOBRE CADA BARRA)
    bc.barLabels.nudge = 8
    bc.barLabels.fontSize = 8
    bc.barLabels.fontName = 'Helvetica-Bold'
    bc.barLabelFormat = '%.1f'
    
    # Customização visual alinhada à paleta corporativa de auditoria do i-Fiscal
    bc.bars[0].fillColor = rl_colors.HexColor("#1b4f72")
    bc.bars[0].strokeColor = rl_colors.HexColor("#2c3e50")
    bc.bars[0].strokeWidth = 0.5

    # Título do Gráfico
    desenho_grafico.add(String(240, 150, "Série Histórica do Desempenho i-Fiscal", textAnchor='middle', fontName='Helvetica-Bold', fontSize=12, fillColor=rl_colors.HexColor("#2c3e50")))
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
# 3. INTERFACE E PAINEL LATERAL (STREAMLIT)
# =============================================================================

def render_sidebar():
    st.sidebar.title("🛠️ Painel i-Fiscal")
    anos = [2023, 2024, 2025, 2026, 2027, 2028, 2029, 2030]
    
    if "reset_ctr" not in st.session_state:
        st.session_state["reset_ctr"] = 0
        
    ano_sel = st.sidebar.selectbox("Ano de Referência:", anos, key="ano_referencia_global")
    res_data = load_respostas(ano_sel)
    
    total_pts = sum(float(item.get("pontos", 0)) for k, item in res_data.items() if not k.startswith("COM_") and float(item.get("pontos", 0)) > -100)
    rebaixar = any(float(item.get("pontos", 0)) <= -100 for item in res_data.values())
    
    if total_pts <= 499:     faixa, cor = "C",  "#ef4444"
    elif total_pts <= 599:   faixa, cor = "C+", "#f97316"
    elif total_pts <= 749:   faixa, cor = "B",  "#eab308"
    elif total_pts <= 899:   faixa, cor = "B+", "#22c55e"
    else:                    faixa, cor = "A",  "#16a34a"

    if rebaixar:
        faixas_ordem = ["C", "C+", "B", "B+", "A"]
        idx_f = faixas_ordem.index(faixa)
        faixa = faixas_ordem[max(0, idx_f - 1)]
        cor = FAIXA_CORES[faixa]
        st.sidebar.warning("⚠️ Faixa rebaixada por critério eliminatório.")

    st.sidebar.metric("Pontuação Total", f"{total_pts:.1f} pts")
    st.sidebar.markdown(f"**Faixa:** <span style='color:{cor}; font-size:20px; font-weight:bold;'>{faixa}</span>", unsafe_allow_html=True)
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("📄 Relatórios")
    
    try:
        dados_historicos_brutos = get_all_years_data()
    except Exception:
        dados_historicos_brutos = {}
        
    historico_tratado = {}
    if isinstance(dados_historicos_brutos, dict):
        for ano_chave, valor_ano in dados_historicos_brutos.items():
            try:
                ano_int = int(str(ano_chave).strip()[:4])
                historico_tratado[ano_int] = valor_ano
            except (ValueError, TypeError):
                continue

    st.session_state.all_data = historico_tratado

    pdf_buffer = gerar_relatorio_pdf(res_data, ano_sel, total_pts, faixa, historico_tratado)
    
    st.sidebar.download_button(
        label="📥Relatório PDF i-Fiscal",
        data=pdf_buffer.getvalue(),
        file_name=f"Relatorio_i-Fiscal_{ano_sel}.pdf",
        mime="application/pdf"
    )
    
    st.sidebar.markdown("---")
    if st.sidebar.button("🔄 Zerar Questionário"):
        with get_connection() as conn:
            conn.execute("DELETE FROM respostas WHERE ano = ?", (ano_sel,))
            conn.commit()
            
        chaves_para_preservar = ["ano_referencia_global", "reset_ctr", "current_page", "selected_dimension"]
        for k in list(st.session_state.keys()):
            if k in chaves_para_preservar or any(termo in k.lower() for termo in ["login", "auth", "user"]):
                continue
            del st.session_state[k]
            
        st.session_state["reset_ctr"] += 1
        st.sidebar.success("Dados zerados com sucesso!")
        st.rerun()
        
    return total_pts, res_data, ano_sel

# =============================================================================
# 4. INTERFACE PRINCIPAL E FORMULÁRIO DINÂMICO (STREAMLIT)
# =============================================================================
def mostrar_formulario_ifiscal():
    init_db()
    total_pts, res_data, ano_sel = render_sidebar()
    
    # 🔍 Definição do CTR estático para as chaves do formulário
    ctr = "fiscal"
    
    # Estilização CSS mantendo o padrão i-Fiscal
    st.markdown("""
        <style>
        .quesito-card { 
            background-color: #f8f9fa;
            padding: 18px;
            border-left: 6px solid #001A4D;
            border-radius: 6px;
            margin-bottom: 15px;
            border: 1px solid #e0e0e0;
        }
        .section-header h3 {
            color: #001A4D;
            margin-top: 10px;
            margin-bottom: 15px;
        }
        </style>
    """, unsafe_allow_html=True)

    st.title(f"📋 Painel de Auditoria i-Fiscal - {ano_sel}")
    
    # 📑 Criação das abas estruturadas (Questionário e Gráficos)
    aba_quest, aba_graf = st.tabs(["📋 Questionário", "📈 Gráficos"])
    
    # --- CONTEÚDO DA ABA QUESTIONÁRIO ---
    with aba_quest:
        # -------------------------------------------------------------------------
        # SEÇÃO 1: ADMINISTRAÇÃO TRIBUTÁRIA
        # -------------------------------------------------------------------------
        st.markdown('<div class="section-header"><h3>1. Administração Tributária</h3></div>', unsafe_allow_html=True)
        
        # Insira abaixo os seus quesitos da Seção 1 (ex: Quesito 1.0, 1.1, etc.)
        # with st.container(border=True):
        #     ...

    # =============================================================================
    # QUESITO 1.0
    # =============================================================================
    with st.container(border=True):
        st.subheader("QUESITO 1.0")
        st.write("**Há estrutura administrativa voltada para a administração tributária?**")
        
        d10 = res_data.get("1.0", {"valor": None, "pontos": 0, "link": ""})
        if d10 is None: d10 = {"valor": None, "pontos": 0, "link": ""}
        
        opc10 = ["Sim", "Não"]
        idx10 = opc10.index(d10["valor"]) if d10.get("valor") in opc10 else None
        
        c1, c2 = st.columns([1, 2])
        with c1: 
            r10 = st.radio("Selecione 1.0:", opc10, index=idx10, key=f"rad_10_{ano_sel}_fiscal")
        with c2: 
            val_l10 = d10.get("link", "") if d10.get("link") is not None else ""
            l10 = st.text_area("Link/Evidência (1.0):", value=val_l10, key=f"txt_10_{ano_sel}_fiscal", height=100)
            
            links_10_atuais = re.findall(r'(https?://[^\s]+)', l10) if l10 else []
            if links_10_atuais:
                botoes_10 = " | ".join([f"🔗 [{u}]({u})" for u in links_10_atuais])
                st.markdown(f"**Links Ativos:** {botoes_10}")

        if r10 and (r10 != d10.get("valor") or l10 != d10.get("link")):
            save_resp("1.0", r10, 0, l10)
            if links_10_atuais:
                links_10_antigos = re.findall(r'(https?://[^\s]+)', d10.get("link", "")) if d10.get("link") else []
                if links_10_atuais != links_10_antigos:
                    modal_aviso_link("1.0", links_10_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
                
        bloco_comentarios("1.0", res_data, sufixo="fiscal")

    # =============================================================================
    # QUESITO 1.1
    # =============================================================================
    with st.container(border=True):
        st.subheader("QUESITO 1.1")
        st.write("**O Município possui lei que defina a estrutura organizacional da Administração Tributária?**")
        
        d11 = res_data.get("1.1", {"valor": None, "pontos": 0, "link": ""})
        if d11 is None: d11 = {"valor": None, "pontos": 0, "link": ""}
        
        opc11 = ["Sim – 0,5", "Não – 00"]
        idx11 = opc11.index(d11["valor"]) if d11.get("valor") in opc11 else None
        
        c1, c2 = st.columns([1, 2])
        with c1: 
            r11 = st.radio("Selecione 1.1:", opc11, index=idx11, key=f"rad_11_{ano_sel}_fiscal")
        with c2: 
            val_l11 = d11.get("link", "") if d11.get("link") is not None else ""
            l11 = st.text_area("Link/Evidência (1.1):", value=val_l11, key=f"txt_11_{ano_sel}_fiscal", height=100)
            
            links_11_atuais = re.findall(r'(https?://[^\s]+)', l11) if l11 else []
            if links_11_atuais:
                botoes_11 = " | ".join([f"🔗 [{u}]({u})" for u in links_11_atuais])
                st.markdown(f"**Links Ativos:** {botoes_11}")

        pts11 = 0.5 if "Sim" in (r11 or "") else 0
        if r11 and (r11 != d11.get("valor") or l11 != d11.get("link")):
            save_resp("1.1", r11, pts11, l11)
            if links_11_atuais:
                links_11_antigos = re.findall(r'(https?://[^\s]+)', d11.get("link", "")) if d11.get("link") else []
                if links_11_atuais != links_11_antigos:
                    modal_aviso_link("1.1", links_11_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
                
        bloco_comentarios("1.1", res_data, sufixo="fiscal")

    # =============================================================================
    # QUESITO 1.2
    # =============================================================================
    with st.container(border=True):
        st.subheader("QUESITO 1.2")
        st.write("**Qual o número de cargos de fiscais/auditores tributários preenchidos? Se efetivos > 0 E 'Em comissão' = 0 E Terceirizados = 0 -> 1,5 ponto Se 'Em comissão' <> 0 OU Terceirizados <> 0 -> 0 ponto**")
        
        d12 = res_data.get("1.2", {"valor": "0/0/0", "pontos": 0, "link": ""})
        if d12 is None: d12 = {"valor": "0/0/0", "pontos": 0, "link": ""}
        
        try: 
            ef, com, terc = map(int, d12["valor"].split("/"))
        except: 
            ef, com, terc = 0, 0, 0
            
        c1, c2 = st.columns([1, 2])
        with c1:
            v_ef = st.number_input("Efetivo:", value=ef, min_value=0, key=f"num_12_ef_{ano_sel}_fiscal")
            v_com = st.number_input("Em comissão:", value=com, min_value=0, key=f"num_12_com_{ano_sel}_fiscal")
            v_terc = st.number_input("Terceirizado:", value=terc, min_value=0, key=f"num_12_terc_{ano_sel}_fiscal")
            
        with c2: 
            val_l12 = d12.get("link", "") if d12.get("link") is not None else ""
            l12 = st.text_area("Link/Evidência (1.2):", value=val_l12, key=f"txt_12_{ano_sel}_fiscal", height=150)
            
            links_12_atuais = re.findall(r'(https?://[^\s]+)', l12) if l12 else []
            if links_12_atuais:
                botoes_12 = " | ".join([f"🔗 [{u}]({u})" for u in links_12_atuais])
                st.markdown(f"**Links Ativos:** {botoes_12}")
            
        pts12 = 1.5 if v_ef > 0 and v_com == 0 and v_terc == 0 else 0
        
        if f"{v_ef}/{v_com}/{v_terc}" != d12.get("valor") or l12 != d12.get("link"):
            save_resp("1.2", f"{v_ef}/{v_com}/{v_terc}", pts12, l12)
            if links_12_atuais:
                links_12_antigos = re.findall(r'(https?://[^\s]+)', d12.get("link", "")) if d12.get("link") else []
                if links_12_atuais != links_12_antigos:
                    modal_aviso_link("1.2", links_12_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
            
        bloco_comentarios("1.2", res_data, sufixo="fiscal")

    # =============================================================================
    # QUESITO 1.3
    # =============================================================================
    with st.container(border=True):
        st.subheader("QUESITO 1.3")
        st.write("**Os fiscais tributários recebem treinamento específico para execução das atividades inerentes ao cargo? Treinamento periódico pelo menos 1 vez ao ano**")
        
        d13 = res_data.get("1.3", {"valor": None, "pontos": 0, "link": ""})
        if d13 is None: d13 = {"valor": None, "pontos": 0, "link": ""}
        
        opc13 = ["Sim – 10", "Não – 00"]
        idx13 = opc13.index(d13["valor"]) if d13.get("valor") in opc13 else None
        
        c1, c2 = st.columns([1, 2])
        with c1: 
            r13 = st.radio("Selecione 1.3:", opc13, index=idx13, key=f"rad_13_{ano_sel}_fiscal")
        with c2: 
            val_l13 = d13.get("link", "") if d13.get("link") is not None else ""
            l13 = st.text_area("Link/Evidência (1.3):", value=val_l13, key=f"txt_13_{ano_sel}_fiscal", height=100)
            
            links_13_atuais = re.findall(r'(https?://[^\s]+)', l13) if l13 else []
            if links_13_atuais:
                botoes_13 = " | ".join([f"🔗 [{u}]({u})" for u in links_13_atuais])
                st.markdown(f"**Links Ativos:** {botoes_13}")

        pts13 = 10 if "Sim" in (r13 or "") else 0
        if r13 and (r13 != d13.get("valor") or l13 != d13.get("link")):
            save_resp("1.3", r13, pts13, l13)
            if links_13_atuais:
                links_13_antigos = re.findall(r'(https?://[^\s]+)', d13.get("link", "")) if d13.get("link") else []
                if links_13_atuais != links_13_antigos:
                    modal_aviso_link("1.3", links_13_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
                
        bloco_comentarios("1.3", res_data, sufixo="fiscal")

    # =============================================================================
    # QUESITO 1.4, 1.4.1 e 1.4.2
    # =============================================================================
    with st.container(border=True):
        st.subheader("QUESITO 1.4")
        st.write("**O Município possui Plano de Cargos e Salários específico para seus fiscais tributários?**")
        st.caption("⚠️ *Atenção: PCCS geral dos servidores públicos do município não é considerado PCCS específico para os fiscais tributários.*")
        
        d14 = res_data.get("1.4", {"valor": None, "pontos": 0, "link": ""})
        if d14 is None: d14 = {"valor": None, "pontos": 0, "link": ""}
        
        opc14 = ["Sim – 03", "Não – 00"]
        idx14 = opc14.index(d14["valor"]) if d14.get("valor") in opc14 else None
        
        c1, c2 = st.columns([1, 2])
        with c1: 
            r14 = st.radio("Selecione 1.4:", opc14, index=idx14, key=f"rad_14_{ano_sel}_fiscal")
        with c2: 
            val_l14 = d14.get("link", "") if d14.get("link") is not None else ""
            l14 = st.text_area("Link/Evidência Geral (1.4):", value=val_l14, key=f"txt_14_{ano_sel}_fiscal", height=100)
            
            links_14_atuais = re.findall(r'(https?://[^\s]+)', l14) if l14 else []
            if links_14_atuais:
                botoes_14 = " | ".join([f"🔗 [{u}]({u})" for u in links_14_atuais])
                st.markdown(f"**Links Ativos:** {botoes_14}")
        
        pts14 = 3 if "Sim" in (r14 or "") else 0
        
        # Monitoramento e disparo do ciclo de vida da questão principal 1.4
        if r14 and (r14 != d14.get("valor") or l14 != d14.get("link")):
            save_resp("1.4", r14, pts14, l14)
            if links_14_atuais:
                links_14_antigos = re.findall(r'(https?://[^\s]+)', d14.get("link", "")) if d14.get("link") else []
                if links_14_atuais != links_14_antigos:
                    modal_aviso_link("1.4", links_14_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        # Subquesitos Condicionais (Só aparecem se a resposta for Sim)
        if r14 and "Sim" in r14:
            st.markdown("---")
            st.write("📋 **Detalhamento do PCCS Específico:**")
            
            # QUESITO 1.4.1
            st.write("**1.4.1** Informe o instrumento normativo de regulamentação do Plano de Cargos e Salários específico para seus fiscais tributários, Número e Data da publicação:")
            st.caption("ℹ️ *Caso não esteja disponível na internet, recomendamos anexar o Plano de Cargos e Salários específico para seus fiscais tributários, conforme Instrução de Preenchimento (IP) no Sistema de Questionários.*")
            
            d141 = res_data.get("1.4.1", {"valor": "", "pontos": 0, "link": ""})
            if d141 is None: d141 = {"valor": "", "pontos": 0, "link": ""}
            
            v141 = st.text_input("Número e Data da publicação (Ex: Lei nº 1.234 de 10/05/2020):", value=d141.get("valor", ""), key=f"txt_141_val_{ano_sel}_fiscal")
            
            if v141 != d141.get("valor"):
                save_resp("1.4.1", v141, 0, "")
                st.rerun()
                
            # QUESITO 1.4.2
            st.write("**1.4.2** Informe a página eletrônica (link na internet) de divulgação do Plano de Cargos e Salários específico para os fiscais tributários:")
            st.caption("ℹ️ *Se não estiver disponível na internet, inserir no campo o texto **XYZ***")
            
            d142 = res_data.get("1.4.2", {"valor": "", "pontos": 0, "link": ""})
            if d142 is None: d142 = {"valor": "", "pontos": 0, "link": ""}
            
            v142 = st.text_input("Página eletrônica (ou XYZ):", value=d142.get("valor", ""), key=f"txt_142_val_{ano_sel}_fiscal")
            
            # Scanner de link ativo no valor digitado pelo usuário, já que este input é para uma URL externa
            links_142_atuais = re.findall(r'(https?://[^\s]+)', v142) if v142 else []
            if links_142_atuais:
                botoes_142 = " | ".join([f"🔗 [{u}]({u})" for u in links_142_atuais])
                st.markdown(f"**Links Ativos detectados no campo:** {botoes_142}")
            
            if v142 != d142.get("valor"):
                save_resp("1.4.2", v142, 0, "")
                if links_142_atuais:
                    links_142_antigos = re.findall(r'(https?://[^\s]+)', d142.get("valor", "")) if d142.get("valor") else []
                    if links_142_atuais != links_142_antigos:
                        modal_aviso_link("1.4.2", links_142_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()

        bloco_comentarios("1.4", res_data, sufixo="fiscal")

    # =============================================================================
    # QUESITO 1.5
    # =============================================================================
    with st.container(border=True):
        st.subheader("QUESITO 1.5")
        st.write("**Há segregação de funções entre os setores de lançadoria, arrecadação, fiscalização e contabilidade?**")
        
        d15 = res_data.get("1.5", {"valor": None, "pontos": 0, "link": ""})
        if d15 is None: d15 = {"valor": None, "pontos": 0, "link": ""}
        
        opc15 = ["Sim – 05", "Não – 00"]
        idx15 = opc15.index(d15["valor"]) if d15.get("valor") in opc15 else None
        
        c1, c2 = st.columns([1, 2])
        with c1: 
            r15 = st.radio("Selecione 1.5:", opc15, index=idx15, key=f"rad_15_{ano_sel}_segregacao")
        with c2: 
            val_l15 = d15.get("link", "") if d15.get("link") is not None else ""
            l15 = st.text_area("Link/Evidência (1.5):", value=val_l15, key=f"txt_15_{ano_sel}_segregacao", height=100)
            
            links_15_atuais = re.findall(r'(https?://[^\s]+)', l15) if l15 else []
            if links_15_atuais:
                botoes_15 = " | ".join([f"🔗 [{u}]({u})" for u in links_15_atuais])
                st.markdown(f"**Links Ativos:** {botoes_15}")
                
        pts15 = 5 if "Sim" in (r15 or "") else 0
        if r15 and (r15 != d15.get("valor") or l15 != d15.get("link")):
            save_resp("1.5", r15, pts15, l15)
            if links_15_atuais:
                links_15_antigos = re.findall(r'(https?://[^\s]+)', d15.get("link", "")) if d15.get("link") else []
                if links_15_atuais != links_15_antigos:
                    modal_aviso_link("1.5", links_15_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
                
        bloco_comentarios("1.5", res_data, sufixo="segregacao")

    # =============================================================================
    # QUESITO 1.5.1
    # =============================================================================
    with st.container(border=True):
        st.subheader("QUESITO 1.5.1")
        st.write("**Há segregação nas permissões de acesso do sistema, com identificação do usuário e registro das transações efetuadas?**")
        
        d151 = res_data.get("1.5.1", {"valor": None, "pontos": 0, "link": ""})
        if d151 is None: d151 = {"valor": None, "pontos": 0, "link": ""}
        
        opc151 = [
            "Sim – 05", 
            "Não – 00", 
            "para lançamento, arrecadação ou fiscalização dos tributos – -03(perde 03 pontos)"
        ]
        idx151 = opc151.index(d151["valor"]) if d151.get("valor") in opc151 else None
        
        c1, c2 = st.columns([1, 2])
        with c1: 
            r151 = st.radio("Selecione 1.5.1:", opc151, index=idx151, key=f"rad_151_{ano_sel}_permissao")
        with c2: 
            val_l151 = d151.get("link", "") if d151.get("link") is not None else ""
            l151 = st.text_area("Link/Evidência (1.5.1):", value=val_l151, key=f"txt_151_{ano_sel}_permissao", height=100)
            
            links_151_atuais = re.findall(r'(https?://[^\s]+)', l151) if l151 else []
            if links_151_atuais:
                botoes_151 = " | ".join([f"🔗 [{u}]({u})" for u in links_151_atuais])
                st.markdown(f"**Links Ativos:** {botoes_151}")
                
        if r151 and "Sim" in r151:
            pts151 = 5.0
        elif r151 and "-03" in r151:
            pts151 = -3.0
        else:
            pts151 = 0.0

        if r151 and (r151 != d151.get("valor") or l151 != d151.get("link")):
            save_resp("1.5.1", r151, pts151, l151)
            if links_151_atuais:
                links_151_antigos = re.findall(r'(https?://[^\s]+)', d151.get("link", "")) if d151.get("link") else []
                if links_151_atuais != links_151_antigos:
                    modal_aviso_link("1.5.1", links_151_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
                
        bloco_comentarios("1.5.1", res_data, sufixo="permissao")

    # =============================================================================
    # QUESITO 2.0
    # =============================================================================
    with st.container(border=True):
        st.subheader("QUESITO 2.0")
        st.write("**O servidor responsável pela contabilidade do município é ocupante de cargo de provimento efetivo?**")
        
        d20 = res_data.get("2.0", {"valor": None, "pontos": 0, "link": ""})
        if d20 is None: d20 = {"valor": None, "pontos": 0, "link": ""}
        
        opc20 = ["Sim – 04", "Não – 00"]
        idx20 = opc20.index(d20["valor"]) if d20.get("valor") in opc20 else None
        
        c1, c2 = st.columns([1, 2])
        with c1: 
            r20 = st.radio("Selecione 2.0:", opc20, index=idx20, key=f"rad_20_{ano_sel}_contab")
        with c2: 
            val_l20 = d20.get("link", "") if d20.get("link") is not None else ""
            l20 = st.text_area("Link/Evidência (2.0):", value=val_l20, key=f"txt_20_{ano_sel}_contab", height=100)
            
            links_20_atuais = re.findall(r'(https?://[^\s]+)', l20) if l20 else []
            if links_20_atuais:
                botoes_20 = " | ".join([f"🔗 [{u}]({u})" for u in links_20_atuais])
                st.markdown(f"**Links Ativos:** {botoes_20}")
                
        pts20 = 4 if "Sim" in (r20 or "") else 0
        if r20 and (r20 != d20.get("valor") or l20 != d20.get("link")):
            save_resp("2.0", r20, pts20, l20)
            if links_20_atuais:
                links_20_antigos = re.findall(r'(https?://[^\s]+)', d20.get("link", "")) if d20.get("link") else []
                if links_20_atuais != links_20_antigos:
                    modal_aviso_link("2.0", links_20_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
                
        bloco_comentarios("2.0", res_data, sufixo="contab")

    # -------------------------------------------------------------------------
    # SEÇÃO 2: MEDIDAS DE ARRECADAÇÃO
    # -------------------------------------------------------------------------
    st.markdown('<div class="section-header"><h3>2. Medidas de Arrecadação</h3></div>', unsafe_allow_html=True)

    # =============================================================================
    # QUESITO 3.0 e 3.1 (Formato Checklist Otimizado)
    # =============================================================================
    with st.container(border=True):
        st.subheader("QUESITO 3.0")
        st.write("**O Município adotou medidas efetivas para aumento da arrecadação?**")
        
        d30 = res_data.get("3.0", {"valor": None, "pontos": 0, "link": ""})
        if d30 is None: d30 = {"valor": None, "pontos": 0, "link": ""}
        
        opc30 = ["Sim – 30", "Não – 00"]
        idx30 = opc30.index(d30["valor"]) if d30.get("valor") in opc30 else None
        
        c1, c2 = st.columns([1, 2])
        with c1: 
            r30 = st.radio("Selecione 3.0:", opc30, index=idx30, key=f"rad_30_{ano_sel}_fiscal")
        with c2: 
            val_l30 = d30.get("link", "") if d30.get("link") is not None else ""
            l30 = st.text_area("Link/Evidência (3.0):", value=val_l30, key=f"txt_30_{ano_sel}_fiscal", height=100)
            
            links_30_atuais = re.findall(r'(https?://[^\s]+)', l30) if l30 else []
            if links_30_atuais:
                botoes_30 = " | ".join([f"🔗 [{u}]({u})" for u in links_30_atuais])
                st.markdown(f"**Links Ativos:** {botoes_30}")
        
        pts30 = 30 if "Sim" in (r30 or "") else 0
        if r30 and (r30 != d30.get("valor") or l30 != d30.get("link")):
            save_resp("3.0", r30, pts30, l30)
            if links_30_atuais:
                links_30_antigos = re.findall(r'(https?://[^\s]+)', d30.get("link", "")) if d30.get("link") else []
                if links_30_atuais != links_30_antigos:
                    modal_aviso_link("3.0", links_30_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
        
        # 3.1 - Renderizado em formato Checklist (Checkboxes)
        if r30 and "Sim" in r30:
            st.markdown("---")
            st.write("📋 **3.1 Assinale as medidas implementadas (Checklist):**")
            
            d31 = res_data.get("3.1", {"valor": "[]", "pontos": 0, "link": ""})
            if d31 is None: d31 = {"valor": "[]", "pontos": 0, "link": ""}
            
            opc31 = [
                "Recadastramento de Imóveis", 
                "Programas de Recuperação Fiscal", 
                "Implementação de Nota Fiscal Eletrônica", 
                "Convênios com a União e o Estado para compartilhamento de Informações", 
                "Parceria/Convênio com os tabelionatos de notas e Registros de Imóveis", 
                "Protesto da Certidão de Dívida Ativa", 
                "Convênios com órgãos de proteção ao crédito", 
                "Convênio com o Governo Federal para a cobrança do ITR (Imposto sobre a Propriedade Territorial Rural)", 
                "Outros"
            ]
            
            try:
                sel31 = json.loads(d31["valor"].replace("'", '"'))
                if not isinstance(sel31, list):
                    sel31 = []
            except:
                sel31 = []
                
            res31 = []
            col_chk1, col_chk2 = st.columns(2)
            
            for i, opcao in enumerate(opc31):
                target_col = col_chk1 if i % 2 == 0 else col_chk2
                with target_col:
                    pode_marcar = opcao in sel31
                    checado = st.checkbox(opcao, value=pode_marcar, key=f"chk_31_{i}_{ano_sel}_fiscal")
                    if checado:
                        res31.append(opcao)
            
            if set(res31) != set(sel31):
                save_resp("3.1", json.dumps(res31), 0, d31.get("link", ""))
                # Não aplicamos st.rerun imediato aqui para não quebrar a digitação fluida do fluxo

        bloco_comentarios("3.0", res_data, sufixo="fiscal")

    # -------------------------------------------------------------------------
    # SEÇÃO 3: CADASTRO E PGV
    # -------------------------------------------------------------------------
    st.markdown('<div class="section-header"><h3>3. Cadastro Imobiliário e PGV</h3></div>', unsafe_allow_html=True)

    # =============================================================================
    # QUESITO 4.0, 4.1 e 4.2
    # =============================================================================
    with st.container(border=True):
        st.subheader("QUESITO 4.0")
        st.write("**Foi instituído procedimento de revisão do cadastro imobiliário estabelecendo a sua periodicidade?**")
        st.caption("⚠️ **Obs.:** *A mera atualização cadastral por solicitação do contribuinte realizada de forma pontual e esporádica, sem qualquer convocação ou iniciativa por parte da Prefeitura Municipal, não será considerada na questão como revisão periódica e geral do Cadastro imobiliário.*")
        
        d40 = res_data.get("4.0", {"valor": None, "pontos": 0, "link": ""})
        if d40 is None: d40 = {"valor": None, "pontos": 0, "link": ""}
        
        opc40 = ["Sim", "Não"]
        idx40 = opc40.index(d40["valor"]) if d40.get("valor") in opc40 else None
        
        c1, c2 = st.columns([1, 2])
        with c1: 
            r40 = st.radio("Selecione 4.0:", opc40, index=idx40, key=f"rad_40_{ano_sel}_fiscal")
        with c2: 
            val_l40 = d40.get("link", "") if d40.get("link") is not None else ""
            l40 = st.text_area("Link/Evidência Geral (4.0):", value=val_l40, key=f"txt_40_{ano_sel}_fiscal", height=100)
            
            links_40_atuais = re.findall(r'(https?://[^\s]+)', l40) if l40 else []
            if links_40_atuais:
                botoes_40 = " | ".join([f"🔗 [{u}]({u})" for u in links_40_atuais])
                st.markdown(f"**Links Ativos:** {botoes_40}")
                
        if r40 and (r40 != d40.get("valor") or l40 != d40.get("link")):
            save_resp("4.0", r40, 0, l40)
            if links_40_atuais:
                links_40_antigos = re.findall(r'(https?://[^\s]+)', d40.get("link", "")) if d40.get("link") else []
                if links_40_atuais != links_40_antigos:
                    modal_aviso_link("4.0", links_40_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        # Subquesitos Condicionais (Aparecem se a resposta for Sim)
        if r40 and "Sim" in r40:
            st.markdown("---")
            st.write("📋 **Detalhamento da Revisão do Cadastro Imobiliário:**")
            
            # QUESITO 4.1
            st.write("**4.1** Informe o instrumento normativo (número e data da aprovação) e endereço eletrônico de divulgação do procedimento de revisão do cadastro imobiliário:")
            
            d41 = res_data.get("4.1", {"valor": " / ", "pontos": 0, "link": ""})
            if d41 is None: d41 = {"valor": " / ", "pontos": 0, "link": ""}
            
            try: 
                normativo_salvo, link_salvo = d41["valor"].split(" | ")
            except: 
                normativo_salvo, link_salvo = "", ""
                
            v41_normativo = st.text_input("Instrumento Normativo (Número e Data):", value=normativo_salvo, key=f"txt_41_norm_{ano_sel}_fiscal")
            v41_link = st.text_input("Endereço Eletrônico de Divulgação:", value=link_salvo, key=f"txt_41_link_{ano_sel}_fiscal")
            
            # Detector de Links para a URL informada dentro do próprio input de texto do 4.1
            links_41_atuais = re.findall(r'(https?://[^\s]+)', v41_link) if v41_link else []
            if links_41_atuais:
                botoes_41 = " | ".join([f"🔗 [{u}]({u})" for u in links_41_atuais])
                st.markdown(f"**Links Ativos detectados no campo:** {botoes_41}")
            
            novo_val_41 = f"{v41_normativo} | {v41_link}"
            if novo_val_41 != d41.get("valor"):
                save_resp("4.1", novo_val_41, 0, "")
                if links_41_atuais:
                    try:
                        antigo_link_41 = d41.get("valor", "").split(" | ")[1]
                        links_41_antigos = re.findall(r'(https?://[^\s]+)', antigo_link_41) if antigo_link_41 else []
                    except:
                        links_41_antigos = []
                        
                    if links_41_atuais != links_41_antigos:
                        modal_aviso_link("4.1", links_41_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()
                    
            # QUESITO 4.2
            st.write("**4.2** Qual a periodicidade da revisão geral do Cadastro Imobiliário?")
            
            d42 = res_data.get("4.2", {"valor": None, "pontos": 0, "link": ""})
            if d42 is None: d42 = {"valor": None, "pontos": 0, "link": ""}
            
            opc42 = [
                "Menor ou igual a 1 ano", 
                "Maior que 1 e menor ou igual a 4 anos", 
                "Maior que 4 e menor ou igual a 8 anos", 
                "Maior que 8 anos"
            ]
            idx42 = opc42.index(d42["valor"]) if d42.get("valor") in opc42 else None
            
            r42 = st.radio("Selecione a periodicidade (4.2):", opc42, index=idx42, key=f"rad_42_{ano_sel}_fiscal")
            if r42 and r42 != d42.get("valor"):
                save_resp("4.2", r42, 0, "")
                st.rerun()

        bloco_comentarios("4.0", res_data, sufixo="fiscal")

    # =============================================================================
    # QUESITO 4.3
    # =============================================================================
    with st.container(border=True):
        st.subheader("QUESITO 4.3")
        st.write("**O cadastro imobiliário está com a revisão periódica ou geral atualizada?**")
        st.caption("⚠️ **Obs.:** *A mera atualização cadastral por solicitação do contribuinte realizada de forma pontual e esporádica, sem qualquer convocação ou iniciativa por parte da Prefeitura Municipal, não será considerada na questão como revisão periódica e geral do Cadastro imobiliário.*")
        
        d43 = res_data.get("4.3", {"valor": None, "pontos": 0, "link": ""})
        if d43 is None: d43 = {"valor": None, "pontos": 0, "link": ""}
        
        opc43 = ["Sim – 05", "Não – 00"]
        idx43 = opc43.index(d43["valor"]) if d43.get("valor") in opc43 else None
        
        c1, c2 = st.columns([1, 2])
        with c1: 
            r43 = st.radio("Selecione 4.3:", opc43, index=idx43, key=f"rad_43_{ano_sel}_fiscal")
        with c2: 
            val_l43 = d43.get("link", "") if d43.get("link") is not None else ""
            l43 = st.text_area("Link/Evidência (4.3):", value=val_l43, key=f"txt_43_{ano_sel}_fiscal", height=100)
            
            links_43_atuais = re.findall(r'(https?://[^\s]+)', l43) if l43 else []
            if links_43_atuais:
                botoes_43 = " | ".join([f"🔗 [{u}]({u})" for u in links_43_atuais])
                st.markdown(f"**Links Ativos:** {botoes_43}")
        
        pts43 = 5 if "Sim" in (r43 or "") else 0
        if r43 and (r43 != d43.get("valor") or l43 != d43.get("link")):
            save_resp("4.3", r43, pts43, l43)
            if links_43_atuais:
                links_43_antigos = re.findall(r'(https?://[^\s]+)', d43.get("link", "")) if d43.get("link") else []
                if links_43_atuais != links_43_antigos:
                    modal_aviso_link("4.3", links_43_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
                
        bloco_comentarios("4.3", res_data, sufixo="fiscal")

    # =============================================================================
    # QUESITOS 5.0 A 5.4 (Planta Genérica de Valores - PGV)
    # =============================================================================
    with st.container(border=True):
        st.subheader("PLANTA GENÉRICA DE VALORES (PGV)")
        
        # QUESITO 5.0
        st.write("**5.0 O instrumento da Planta Genérica de Valores (PGV) foi aprovado por lei, conforme previsto no Código Tributário Nacional (CTN)?**")
        
        d50 = res_data.get("5.0", {"valor": None, "pontos": 0, "link": ""})
        if d50 is None: d50 = {"valor": None, "pontos": 0, "link": ""}
        
        opc50 = ["Sim – 03", "Não – 00"]
        idx50 = opc50.index(d50["valor"]) if d50.get("valor") in opc50 else None
        
        c1, c2 = st.columns([1, 2])
        with c1:
            r50 = st.radio("Selecione 5.0:", opc50, index=idx50, key=f"rad_50_{ano_sel}_fiscal")
        with c2:
            val_l50 = d50.get("link", "") if d50.get("link") is not None else ""
            l50 = st.text_area("Link/Evidência Geral (5.0):", value=val_l50, key=f"txt_50_{ano_sel}_fiscal", height=100)
            
            links_50_atuais = re.findall(r'(https?://[^\s]+)', l50) if l50 else []
            if links_50_atuais:
                botoes_50 = " | ".join([f"🔗 [{u}]({u})" for u in links_50_atuais])
                st.markdown(f"**Links Ativos:** {botoes_50}")
                
        pts50 = 3 if "Sim" in (r50 or "") else 0
        if r50 and (r50 != d50.get("valor") or l50 != d50.get("link")):
            save_resp("5.0", r50, pts50, l50)
            if links_50_atuais:
                links_50_antigos = re.findall(r'(https?://[^\s]+)', d50.get("link", "")) if d50.get("link") else []
                if links_50_atuais != links_50_antigos:
                    modal_aviso_link("5.0", links_50_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        # O detalhamento da PGV só abre dinamicamente se o município possuir a PGV aprovada por lei
        if r50 and "Sim" in r50:
            st.markdown("---")
            st.write("📋 **Detalhamento da PGV:**")
            
            # QUESITO 5.1
            st.write("**5.1** Informe o Instrumento normativo de aprovação da Planta Genérica de Valores (PGV), Número e Data da publicação:")
            st.caption("ℹ️ *Caso não esteja disponível na internet, recomendamos anexar o documento no Sistema de Questionários.*")
            
            d51 = res_data.get("5.1", {"valor": "", "pontos": 0, "link": ""})
            if d51 is None: d51 = {"valor": "", "pontos": 0, "link": ""}
            
            v51 = st.text_input("Instrumento normativo de aprovação (Nº e Data):", value=d51.get("valor", ""), key=f"txt_51_val_{ano_sel}_fiscal")
            if v51 != d51.get("valor"):
                save_resp("5.1", v51, 0, "")
                st.rerun()

            # QUESITO 5.2
            st.write("**5.2** Informe a página eletrônica (link na internet) de divulgação do Instrumento Normativo de aprovação da Planta Genérica de Valores (PGV):")
            st.caption("ℹ️ *Se não estiver disponível na internet, inserir no campo o texto **XYZ***")
            
            d52 = res_data.get("5.2", {"valor": "", "pontos": 0, "link": ""})
            if d52 is None: d52 = {"valor": "", "pontos": 0, "link": ""}
            
            v52 = st.text_input("Link de divulgação do instrumento (ou XYZ):", value=d52.get("valor", ""), key=f"txt_52_val_{ano_sel}_fiscal")
            
            # Extrator ativo para link inserido no input de texto do 5.2
            links_52_atuais = re.findall(r'(https?://[^\s]+)', v52) if v52 else []
            if links_52_atuais:
                botoes_52 = " | ".join([f"🔗 [{u}]({u})" for u in links_52_atuais])
                st.markdown(f"**Links Ativos detectados no campo:** {botoes_52}")
                
            if v52 != d52.get("valor"):
                save_resp("5.2", v52, 0, "")
                if links_52_atuais:
                    links_52_antigos = re.findall(r'(https?://[^\s]+)', d52.get("valor", "")) if d52.get("valor") else []
                    if links_52_atuais != links_52_antigos:
                        modal_aviso_link("5.2", links_52_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()

            st.markdown("---")

            # QUESITO 5.3
            st.write("**5.3** O Código Tributário Municipal ou Lei específica que tenha instituído o IPTU prevê a revisão periódica obrigatória da Planta Genérica de Valores (PGV)?")
            
            d53 = res_data.get("5.3", {"valor": None, "pontos": 0, "link": ""})
            if d53 is None: d53 = {"valor": None, "pontos": 0, "link": ""}
            
            opc53 = ["Sim – 03", "Não – 00"]
            idx53 = opc53.index(d53["valor"]) if d53.get("valor") in opc53 else None
            
            c3, c4 = st.columns([1, 2])
            with c3:
                r53 = st.radio("Selecione 5.3:", opc53, index=idx53, key=f"rad_53_{ano_sel}_fiscal")
            with c4:
                val_l53 = d53.get("link", "") if d53.get("link") is not None else ""
                l53 = st.text_area("Link/Evidência (5.3):", value=val_l53, key=f"txt_53_{ano_sel}_fiscal", height=100)
                
                links_53_atuais = re.findall(r'(https?://[^\s]+)', l53) if l53 else []
                if links_53_atuais:
                    botoes_53 = " | ".join([f"🔗 [{u}]({u})" for u in links_53_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_53}")
            
            pts53 = 3 if "Sim" in (r53 or "") else 0
            if r53 and (r53 != d53.get("valor") or l53 != d53.get("link")):
                save_resp("5.3", r53, pts53, l53)
                if links_53_atuais:
                    links_53_antigos = re.findall(r'(https?://[^\s]+)', d53.get("link", "")) if d53.get("link") else []
                    if links_53_atuais != links_53_antigos:
                        modal_aviso_link("5.3", links_53_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()

            # Subquesitos Condicionais do 5.3 (Recuo visual limpo usando containers nativos)
            if r53 and "Sim" in r53:
                with st.container(border=True):
                    st.write("📋 **Detalhamento da Revisão Obrigatória da PGV:**")
                    
                    # QUESITO 5.3.1
                    st.write("**5.3.1** Informe o instrumento normativo de revisão da Planta Genérica de Valores (PGV), Número e Data da publicação:")
                    d531 = res_data.get("5.3.1", {"valor": "", "pontos": 0, "link": ""})
                    if d531 is None: d531 = {"valor": "", "pontos": 0, "link": ""}
                    
                    v531 = st.text_input("Instrumento normativo de revisão (Nº e Data):", value=d531.get("valor", ""), key=f"txt_531_{ano_sel}_fiscal")
                    if v531 != d531["valor"]:
                        save_resp("5.3.1", v531, 0, "")
                        st.rerun()

                    # QUESITO 5.3.2
                    st.write("**5.3.2** Informe a página eletrônica (link na internet) de divulgação do Instrumento normativo de revisão da Planta Genérica de Valores (PGV):")
                    st.caption("ℹ️ *Se não estiver disponível na internet, inserir no campo o texto **XYZ***")
                    
                    d532 = res_data.get("5.3.2", {"valor": "", "pontos": 0, "link": ""})
                    if d532 is None: d532 = {"valor": "", "pontos": 0, "link": ""}
                    
                    v532 = st.text_input("Link de divulgação da revisão (ou XYZ):", value=d532.get("valor", ""), key=f"txt_532_{ano_sel}_fiscal")
                    
                    # Extrator ativo para link inserido no input de texto do 5.3.2
                    links_532_atuais = re.findall(r'(https?://[^\s]+)', v532) if v532 else []
                    if links_532_atuais:
                        botoes_532 = " | ".join([f"🔗 [{u}]({u})" for u in links_532_atuais])
                        st.markdown(f"**Links Ativos detectados no campo:** {botoes_532}")
                        
                    if v532 != d532["valor"]:
                        save_resp("5.3.2", v532, 0, "")
                        if links_532_atuais:
                            links_532_antigos = re.findall(r'(https?://[^\s]+)', d532.get("valor", "")) if d532.get("valor") else []
                            if links_532_atuais != links_532_antigos:
                                modal_aviso_link("5.3.2", links_532_atuais)
                            else:
                                st.rerun()
                        else:
                            st.rerun()

                    # QUESITO 5.3.3
                    st.write("**5.3.3** Informe a data da última revisão da PGV:")
                    d533 = res_data.get("5.3.3", {"valor": "", "pontos": 0, "link": ""})
                    if d533 is None: d533 = {"valor": "", "pontos": 0, "link": ""}
                    
                    v533 = st.text_input("Data da última revisão (Ex: DD/MM/AAAA):", value=d533.get("valor", ""), key=f"txt_533_{ano_sel}_fiscal")
                    if v533 != d533["valor"]:
                        save_resp("5.3.3", v533, 0, "")
                        st.rerun()

                    # QUESITO 5.3.4
                    st.write("**5.3.4** Informe a periodicidade de revisão da PGV:")
                    d534 = res_data.get("5.3.4", {"valor": "0", "pontos": 0, "link": ""})
                    if d534 is None: d534 = {"valor": "0", "pontos": 0, "link": ""}
                    
                    try: periodicidade_inicial = int(d534["valor"])
                    except: periodicidade_inicial = 0
                    
                    v534 = st.number_input("Periodicidade em anos:", value=periodicidade_inicial, min_value=0, key=f"num_534_{ano_sel}_fiscal")
                    if str(v534) != d534["valor"]:
                        save_resp("5.3.4", str(v534), 0, "")
                        st.rerun()

            st.markdown("---")

            # QUESITO 5.4
            st.write("**5.4** Os dados da Planta Genérica de Valores (PGV) e do Cadastro Imobiliário atualizam a base de cálculo do IPTU?")
            
            d54 = res_data.get("5.4", {"valor": None, "pontos": 0, "link": ""})
            if d54 is None: d54 = {"valor": None, "pontos": 0, "link": ""}
            
            opc54 = [
                "Sim, de forma automática no sistema – 06",
                "Sim, de forma manual – 02",
                "Não – 00"
            ]
            idx54 = opc54.index(d54["valor"]) if d54.get("valor") in opc54 else None
            
            c5, c6 = st.columns([1, 2])
            with c5:
                r54 = st.radio("Selecione 5.4:", opc54, index=idx54, key=f"rad_54_{ano_sel}_fiscal")
            with c6:
                val_l54 = d54.get("link", "") if d54.get("link") is not None else ""
                l54 = st.text_area("Link/Evidência (5.4):", value=val_l54, key=f"txt_54_{ano_sel}_fiscal", height=100)
                
                links_54_atuais = re.findall(r'(https?://[^\s]+)', l54) if l54 else []
                if links_54_atuais:
                    botoes_54 = " | ".join([f"🔗 [{u}]({u})" for u in links_54_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_54}")
            
            if r54 and "automática" in r54:
                pts54 = 6.0
            elif r54 and "manual" in r54:
                pts54 = 2.0
            else:
                pts54 = 0.0

            if r54 and (r54 != d54.get("valor") or l54 != d54.get("link")):
                save_resp("5.4", r54, pts54, l54)
                if links_54_atuais:
                    links_54_antigos = re.findall(r'(https?://[^\s]+)', d54.get("link", "")) if d54.get("link") else []
                    if links_54_atuais != links_54_antigos:
                        modal_aviso_link("5.4", links_54_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()

        bloco_comentarios("5.0", res_data, sufixo="fiscal")

   # =============================================================================
    # QUESITO 6.0 (Formato Checklist Otimizado com Lógica Excludente)
    # =============================================================================
    with st.container(border=True):
        st.subheader("QUESITO 6.0")
        st.write("**Sobre a alíquota do IPTU, quais critérios o município instituiu para a cobrança do imposto? (Checklist)**")
        
        # Busca dados anteriores do banco
        d60 = res_data.get("6.0", {"valor": "[]", "pontos": 0, "link": ""})
        if d60 is None: d60 = {"valor": "[]", "pontos": 0, "link": ""}
        
        # Garante que os dados recuperados sejam interpretados como uma lista pura Python
        try:
            val_banco = d60["valor"].replace("'", '"')
            sel60 = json.loads(val_banco)
            if not isinstance(sel60, list):
                sel60 = []
        except:
            sel60 = []

        opcoes_tela = [
            "Alíquotas progressivas em razão do valor do imóvel – 01",
            "Alíquotas diferenciadas em razão da localização do imóvel – 0,5",
            "Alíquotas diferenciadas em razão do uso do imóvel – 0,5",
            "Outros – 00",
            "Não há diferenciação nas alíquotas dos imóveis – -01 (perde 01 ponto)"
        ]

        c1, c2 = st.columns([1, 1])
        res60 = []

        # Renderiza os checkboxes e popula a lista em tempo real
        for idx, opcao in enumerate(opcoes_tela):
            target_col = c1 if idx % 2 == 0 else c2
            with target_col:
                pode_marcar = opcao in sel60
                if st.checkbox(opcao, value=pode_marcar, key=f"chk_60_{idx}_{ano_sel}_fiscal"):
                    res60.append(opcao)

        # 📋 CÁLCULO DA PONTUAÇÃO VIA FILTRO DIRETO
        pts60 = 0.0

        # Verifica se a opção excludente de penalidade está marcada
        if any("Não há diferenciação" in item for item in res60):
            res60 = ["Não há diferenciação nas alíquotas dos imóveis – -01 (perde 01 ponto)"]
            pts60 = -1.0
        else:
            for item in res60:
                if "progressivas" in item:
                    pts60 += 1.0
                elif "localização" in item:
                    pts60 += 0.5
                elif "uso" in item:
                    pts60 += 0.5

        # Campo de texto para as evidências
        val_l60 = d60.get("link", "") if d60.get("link") is not None else ""
        l60 = st.text_area("Link/Evidência (Legislação das Alíquotas do IPTU - 6.0):", value=val_l60, key=f"txt_60_{ano_sel}_fiscal", height=100)

        # Scanner de Links Ativos para a evidência informada
        links_60_atuais = re.findall(r'(https?://[^\s]+)', l60) if l60 else []
        if links_60_atuais:
            botoes_60 = " | ".join([f"🔗 [{u}]({u})" for u in links_60_atuais])
            st.markdown(f"**Links Ativos:** {botoes_60}")

        # Salva se houver qualquer mudança no checklist ou no link de texto
        if set(res60) != set(sel60) or l60 != d60.get("link"):
            save_resp("6.0", json.dumps(res60), pts60, l60)
            if links_60_atuais:
                links_60_antigos = re.findall(r'(https?://[^\s]+)', d60.get("link", "")) if d60.get("link") else []
                if links_60_atuais != links_60_antigos:
                    modal_aviso_link("6.0", links_60_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("6.0", res_data, sufixo="fiscal")

# =============================================================================
    # QUESITOS 7.0 A 7.3 (Programa de Isenção do IPTU)
    # =============================================================================
    with st.container(border=True):
        st.subheader("QUESITO 7.0")
        st.write("**O município adotou programa de isenção do IPTU?**")
        
        d70 = res_data.get("7.0", {"valor": None, "pontos": 0, "link": ""})
        if d70 is None: d70 = {"valor": None, "pontos": 0, "link": ""}
        
        opc70 = ["Sim", "Não"]
        idx70 = opc70.index(d70["valor"]) if d70.get("valor") in opc70 else None
        
        c1, c2 = st.columns([1, 2])
        with c1:
            r70 = st.radio("Selecione 7.0:", opc70, index=idx70, key=f"rad_70_{ano_sel}_fiscal")
        with c2:
            val_l70 = d70.get("link", "") if d70.get("link") is not None else ""
            l70 = st.text_area("Link/Evidência Geral (7.0):", value=val_l70, key=f"txt_70_{ano_sel}_fiscal", height=100)
            
            links_70_atuais = re.findall(r'(https?://[^\s]+)', l70) if l70 else []
            if links_70_atuais:
                botoes_70 = " | ".join([f"🔗 [{u}]({u})" for u in links_70_atuais])
                st.markdown(f"**Links Ativos:** {botoes_70}")
                
        if r70 and (r70 != d70.get("valor") or l70 != d70.get("link")):
            save_resp("7.0", r70, 0, l70)
            if links_70_atuais:
                links_70_antigos = re.findall(r'(https?://[^\s]+)', d70.get("link", "")) if d70.get("link") else []
                if links_70_atuais != links_70_antigos:
                    modal_aviso_link("7.0", links_70_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        # Subquesitos Condicionais (Exibidos de forma nativa e limpa se a resposta for SIM)
        if r70 and "Sim" in r70:
            st.markdown("---")
            st.write("📋 **Detalhamento do Programa de Isenção do IPTU:**")
            
            # QUESITO 7.1
            st.write("**7.1** Informe o instrumento normativo de regulamentação do programa de isenção do IPTU, Número e Data da publicação:")
            st.caption("ℹ️ *Caso não esteja disponível na internet, recomendamos anexar o documento no Sistema de Questionários.*")
            
            d71 = res_data.get("7.1", {"valor": "", "pontos": 0, "link": ""})
            if d71 is None: d71 = {"valor": "", "pontos": 0, "link": ""}
            
            v71 = st.text_input("Instrumento normativo (Nº e Data):", value=d71.get("valor", ""), key=f"txt_71_val_{ano_sel}_fiscal")
            if v71 != d71.get("valor"):
                save_resp("7.1", v71, 0, "")
                st.rerun()

            # --- QUESITO 7.2 (Com aplicação automática de penalidade para o texto "XYZ") ---
            st.write("**7.2** Informe a página eletrônica (link na internet) de divulgação do Instrumento normativo de regulamentação do programa de isenção do IPTU:")
            st.caption("⚠️ *Se não estiver disponível na internet, inserir no campo o texto **XYZ** (Aplica penalidade de -03 pontos).*")
            
            d72 = res_data.get("7.2", {"valor": "", "pontos": 0.0, "link": ""})
            if d72 is None: d72 = {"valor": "", "pontos": 0.0, "link": ""}
            
            v72 = st.text_input("Link de divulgação da isenção (ou XYZ):", value=d72.get("valor", ""), key=f"txt_72_val_{ano_sel}_fiscal")
            
            # 🛡️ Criamos um container fixo na interface para evitar a quebra do DOM no React
            container_links_72 = st.empty()
            
            # Extrator dinâmico para URLs informadas no campo de texto livre do 7.2
            links_72_atuais = re.findall(r'(https?://[^\s]+)', v72) if v72 else []
            if links_72_atuais:
                botoes_72 = " | ".join([f"🔗 [{u}]({u})" for u in links_72_atuais])
                # Renderiza com segurança dentro do espaço reservado fixo
                container_links_72.markdown(f"**Links Ativos detectados no campo:** {botoes_72}")
            
            pts72 = -3.0 if v72.strip().upper() == "XYZ" else 0.0
            
            if v72 != d72.get("valor"):
                save_resp("7.2", v72, float(pts72), "")
                if links_72_atuais:
                    links_72_antigos = re.findall(r'(https?://[^\s]+)', d72.get("valor", "")) if d72.get("valor") else []
                    if links_72_atuais != links_72_antigos:
                        modal_aviso_link("7.2", links_72_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()

            st.markdown("---")

            # QUESITO 7.3 - Checklist de Critérios
            st.write("**7.3 Assinale os critérios estabelecidos para a concessão de isenção total ou parcial do IPTU: (Checklist)**")
            
            d73 = res_data.get("7.3", {"valor": "[]", "pontos": 0, "link": ""})
            if d73 is None: d73 = {"valor": "[]", "pontos": 0, "link": ""}
            
            try:
                val_banco73 = d73["valor"].replace("'", '"')
                sel73 = json.loads(val_banco73)
                if not isinstance(sel73, list):
                    sel73 = []
            except:
                sel73 = []

            opc73 = [
                "Aposentado, pensionista ou beneficiário de renda mensal vitalícia",
                "Não possuir outro imóvel",
                "Utilizar o único imóvel como residência",
                "Rendimento mensal máximo",
                "Valor venal máximo do imóvel",
                "Outros"
            ]

            c3, c4 = st.columns([1, 1])
            res73 = []

            # Renderiza os checkboxes balanceados em duas colunas de forma síncrona
            for idx, opcao in enumerate(opc73):
                target_col = c3 if idx % 2 == 0 else c4
                with target_col:
                    pode_marcar = opcao in sel73
                    if st.checkbox(opcao, value=pode_marcar, key=f"chk_73_{idx}_{ano_sel}_fiscal"):
                        res73.append(opcao)

            if set(res73) != set(sel73):
                save_resp("7.3", json.dumps(res73), 0, d73.get("link", ""))
                st.rerun()

        bloco_comentarios("7.0", res_data, sufixo="fiscal")

   # -------------------------------------------------------------------------
    # SEÇÃO 4: ISSQN E ITBI
    # -------------------------------------------------------------------------
    st.markdown("### 4. ISSQN e ITBI")

    # =============================================================================
    # QUESITO 8.0
    # =============================================================================
    with st.container(border=True):
        st.subheader("QUESITO 8.0")
        st.write("**O Imposto sobre Serviços de Qualquer Natureza (ISSQN) foi instituído no município?**")
        
        d80 = res_data.get("8.0", {"valor": None, "pontos": 0, "link": ""})
        if d80 is None: d80 = {"valor": None, "pontos": 0, "link": ""}
        
        opc80 = ["Sim – 01", "Não – 00"]
        idx80 = opc80.index(d80["valor"]) if d80.get("valor") in opc80 else None
        
        c1, c2 = st.columns([1, 2])
        with c1: 
            r80 = st.radio("Selecione 8.0:", opc80, index=idx80, key=f"rad_80_{ano_sel}_fiscal")
        with c2: 
            val_l80 = d80.get("link", "") if d80.get("link") is not None else ""
            l80 = st.text_area("Link/Evidência (8.0):", value=val_l80, key=f"txt_80_{ano_sel}_fiscal", height=100)
            
            links_80_atuais = re.findall(r'(https?://[^\s]+)', l80) if l80 else []
            if links_80_atuais:
                botoes_80 = " | ".join([f"🔗 [{u}]({u})" for u in links_80_atuais])
                st.markdown(f"**Links Ativos:** {botoes_80}")
                
        pts80 = 1.0 if "Sim" in (r80 or "") else 0.0
        
        if r80 and (r80 != d80.get("valor") or l80 != d80.get("link")):
            save_resp("8.0", r80, pts80, l80)
            if links_80_atuais:
                links_80_antigos = re.findall(r'(https?://[^\s]+)', d80.get("link", "")) if d80.get("link") else []
                if links_80_atuais != links_80_antigos:
                    modal_aviso_link("8.0", links_80_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
                
        bloco_comentarios("8.0", res_data, sufixo="fiscal")

    # =============================================================================
    # QUESITO 8.1
    # =============================================================================
    with st.container(border=True):
        st.subheader("QUESITO 8.1")
        st.write("**O Município atualizou sua legislação conforme as novas hipóteses de incidência de ISS (LC 157/2016)?**")
        
        d81 = res_data.get("8.1", {"valor": None, "pontos": 0, "link": ""})
        if d81 is None: d81 = {"valor": None, "pontos": 0, "link": ""}
        
        opc81 = ["Sim – 02", "Não – 00"]
        idx81 = opc81.index(d81["valor"]) if d81.get("valor") in opc81 else None
        
        c1, c2 = st.columns([1, 2])
        with c1: 
            r81 = st.radio("Selecione 8.1:", opc81, index=idx81, key=f"rad_81_{ano_sel}_fiscal")
        with c2: 
            val_l81 = d81.get("link", "") if d81.get("link") is not None else ""
            l81 = st.text_area("Link/Evidência (8.1):", value=val_l81, key=f"txt_81_{ano_sel}_fiscal", height=100)
            
            links_81_atuais = re.findall(r'(https?://[^\s]+)', l81) if l81 else []
            if links_81_atuais:
                botoes_81 = " | ".join([f"🔗 [{u}]({u})" for u in links_81_atuais])
                st.markdown(f"**Links Ativos:** {botoes_81}")
                
        pts81 = 2.0 if "Sim" in (r81 or "") else 0.0
        
        if r81 and (r81 != d81.get("valor") or l81 != d81.get("link")):
            save_resp("8.1", r81, pts81, l81)
            if links_81_atuais:
                links_81_antigos = re.findall(r'(https?://[^\s]+)', d81.get("link", "")) if d81.get("link") else []
                if links_81_atuais != links_81_antigos:
                    modal_aviso_link("8.1", links_81_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
                
        bloco_comentarios("8.1", res_data, sufixo="fiscal")

    # =============================================================================
    # QUESITO 8.2
    # =============================================================================
    with st.container(border=True):
        st.subheader("QUESITO 8.2")
        st.write("**Houve rotina de fiscalização para detectar contribuintes que deixaram de emitir a Nota Fiscal de Serviços por determinado período ou que apresentaram queda acentuada em suas operações, a fim de detectar o fim das atividades ou a sonegação do ISSQN?**")
        
        d82 = res_data.get("8.2", {"valor": None, "pontos": 0, "link": ""})
        if d82 is None: d82 = {"valor": None, "pontos": 0, "link": ""}
        
        opc82 = ["Sim por meio de sistema automatizado – 15", "Sim, manualmente – 08", "Não – 00"]
        idx82 = opc82.index(d82["valor"]) if d82.get("valor") in opc82 else None
        
        c1, c2 = st.columns([1, 2])
        with c1: 
            r82 = st.radio("Selecione 8.2:", opc82, index=idx82, key=f"rad_82_{ano_sel}_fiscal")
        with c2: 
            val_l82 = d82.get("link", "") if d82.get("link") is not None else ""
            l82 = st.text_area("Link/Evidência (8.2):", value=val_l82, key=f"txt_82_{ano_sel}_fiscal", height=100)
            
            links_82_atuais = re.findall(r'(https?://[^\s]+)', l82) if l82 else []
            if links_82_atuais:
                botoes_82 = " | ".join([f"🔗 [{u}]({u})" for u in links_82_atuais])
                st.markdown(f"**Links Ativos:** {botoes_82}")
                
        pts82 = 15.0 if "automatizado" in (r82 or "") else (8.0 if "manualmente" in (r82 or "") else 0.0)
        
        if r82 and (r82 != d82.get("valor") or l82 != d82.get("link")):
            save_resp("8.2", r82, pts82, l82)
            if links_82_atuais:
                links_82_antigos = re.findall(r'(https?://[^\s]+)', d82.get("link", "")) if d82.get("link") else []
                if links_82_atuais != links_82_antigos:
                    modal_aviso_link("8.2", links_82_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
                
        bloco_comentarios("8.2", res_data, sufixo="fiscal")

    # =============================================================================
    # QUESITO 8.3
    # =============================================================================
    with st.container(border=True):
        st.subheader("QUESITO 8.3")
        st.write("**A pesquisa de autenticidade de notas fiscais eletrônicas está disponível ao público?**")
        
        d83 = res_data.get("8.3", {"valor": None, "pontos": 0, "link": ""})
        if d83 is None: d83 = {"valor": None, "pontos": 0, "link": ""}
        
        opc83 = [
            "Sim, sem restrição – 00", 
            "Sim, com restrição (Ex.: há necessidade de cadastro para acessar o resultado da pesquisa) – -09 (perde 09 pontos)", 
            "Serviço não disponibilizado – -15", 
            "Não implantou a NFS-e – -15"
        ]
        idx83 = opc83.index(d83["valor"]) if d83.get("valor") in opc83 else None
        
        c1, c2 = st.columns([1, 2])
        with c1: 
            r83 = st.radio("Selecione 8.3:", opc83, index=idx83, key=f"rad_83_{ano_sel}_fiscal")
        with c2: 
            val_l83 = d83.get("link", "") if d83.get("link") is not None else ""
            l83 = st.text_area("Link/Evidência (8.3):", value=val_l83, key=f"txt_83_{ano_sel}_fiscal", height=100)
            
            links_83_atuais = re.findall(r'(https?://[^\s]+)', l83) if l83 else []
            if links_83_atuais:
                botoes_83 = " | ".join([f"🔗 [{u}]({u})" for u in links_83_atuais])
                st.markdown(f"**Links Ativos:** {botoes_83}")
                
        if r83 == "Sim, sem restrição – 00":
            pts83 = 0.0
        elif "com restrição" in (r83 or ""):
            pts83 = -9.0
        else:
            pts83 = -15.0
            
        if r83 and (r83 != d83.get("valor") or l83 != d83.get("link")):
            save_resp("8.3", r83, pts83, l83)
            if links_83_atuais:
                links_83_antigos = re.findall(r'(https?://[^\s]+)', d83.get("link", "")) if d83.get("link") else []
                if links_83_atuais != links_83_antigos:
                    modal_aviso_link("8.3", links_83_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
                
        bloco_comentarios("8.3", res_data, sufixo="fiscal")

# =============================================================================
    # BLOCO UNIFICADO E ALINHADO: QUESITOS 9.0 A 9.6 (Regulamentação do ITBI)
    # =============================================================================
    with st.container(border=True):
        st.subheader("QUESITO 9.0")
        st.write("**O Imposto sobre Transmissão de Bens Imóveis (ITBI) foi regulamentado?**")
        
        d90 = res_data.get("9.0", {"valor": None, "pontos": 0, "link": ""})
        if d90 is None: d90 = {"valor": None, "pontos": 0, "link": ""}
        
        opc90 = ["Sim", "Não"]
        idx90 = opc90.index(d90["valor"]) if d90.get("valor") in opc90 else None
        
        c1, c2 = st.columns([1, 2])
        with c1:
            r90 = st.radio("Selecione 9.0:", opc90, index=idx90, key=f"rad_90_{ano_sel}_fiscal")
        with c2:
            val_l90 = d90.get("link", "") if d90.get("link") is not None else ""
            l90 = st.text_area("Link/Evidência Geral (9.0):", value=val_l90, key=f"txt_90_{ano_sel}_fiscal", height=100)
            
            links_90_atuais = re.findall(r'(https?://[^\s]+)', l90) if l90 else []
            if links_90_atuais:
                botoes_90 = " | ".join([f"🔗 [{u}]({u})" for u in links_90_atuais])
                st.markdown(f"**Links Ativos:** {botoes_90}")
            
        if r90 and (r90 != d90.get("valor") or l90 != d90.get("link")):
            save_resp("9.0", r90, 0.0, l90)
            if links_90_atuais:
                links_90_antigos = re.findall(r'(https?://[^\s]+)', d90.get("link", "")) if d90.get("link") else []
                if links_90_atuais != links_90_antigos:
                    modal_aviso_link("9.0", links_90_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        # Subquesitos Condicionais (Só abrem se o ITBI for regulamentado)
        if r90 and "Sim" in r90:
            st.markdown("---")
            st.write("📋 **Detalhamento da Regulamentação do ITBI:**")
            
            # QUESITO 9.1
            st.write("**9.1** Informe o instrumento normativo de regulamentação do ITBI, Número e Data da publicação:")
            st.caption("ℹ️ *Caso não esteja disponível na internet, recomendamos anexar o documento no Sistema de Questionários.*")
            
            d91 = res_data.get("9.1", {"valor": "", "pontos": 0, "link": ""})
            if d91 is None: d91 = {"valor": "", "pontos": 0, "link": ""}
            
            v91 = st.text_input("Instrumento normativo do ITBI (Nº e Data):", value=d91.get("valor", ""), key=f"txt_91_val_{ano_sel}_fiscal")
            if v91 != d91.get("valor"):
                save_resp("9.1", v91, 0.0, "")
                st.rerun()

            # QUESITO 9.2 (Fórmula de Cálculo com trava de Rerun instantâneo para o XYZ)
            st.write("**9.2** Informe a página eletrônica (link na internet) de divulgação da regulamentação do ITBI:")
            st.caption("⚠️ *Se não estiver disponível na internet, inserir no campo o texto **XYZ** (Aplica penalidade de -03 pontos).*")
            
            d92 = res_data.get("9.2", {"valor": "", "pontos": 0, "link": ""})
            if d92 is None: d92 = {"valor": "", "pontos": 0, "link": ""}
            
            v92 = st.text_input("Link de divulgação do ITBI (ou XYZ):", value=d92.get("valor", ""), key=f"txt_92_val_{ano_sel}_fiscal")
            
            links_92_atuais = re.findall(r'(https?://[^\s]+)', v92) if v92 else []
            if links_92_atuais:
                botoes_92 = " | ".join([f"🔗 [{u}]({u})" for u in links_92_atuais])
                st.markdown(f"**Links Ativos detectados no campo:** {botoes_92}")
            
            pts92 = -3.0 if v92.strip().upper() == "XYZ" else 0.0
            
            if v92 != d92.get("valor"):
                save_resp("9.2", v92, pts92, "")
                if links_92_atuais:
                    links_92_antigos = re.findall(r'(https?://[^\s]+)', d92.get("valor", "")) if d92.get("valor") else []
                    if links_92_atuais != links_92_antigos:
                        modal_aviso_link("9.2", links_92_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()

            st.markdown("---")

            # QUESITO 9.3 - Checklist de Emissão da Guia
            st.write("**9.3 Assinale a forma de registro e emissão da guia de recolhimento do ITBI: (Checklist)**")
            st.caption("🚨 *Nota: A mera impressão da guia de recolhimento do ITBI não é considerada forma de emissão.*")
            
            d93 = res_data.get("9.3", {"valor": "[]", "pontos": 0, "link": ""})
            if d93 is None: d93 = {"valor": "[]", "pontos": 0, "link": ""}
            
            try:
                val_banco93 = d93["valor"].replace("'", '"')
                sel93 = json.loads(val_banco93)
                if not isinstance(sel93, list): sel93 = []
            except:
                sel93 = []

            opc93 = ["Site da Prefeitura", "Órgão Fazendário", "Cartório autorizado", "Outros"]
            c3, c4 = st.columns([1, 1])
            res93 = []

            for idx, opcao in enumerate(opc93):
                target_col = c3 if idx % 2 == 0 else c4
                with target_col:
                    pode_marcar = opcao in sel93
                    if st.checkbox(opcao, value=pode_marcar, key=f"chk_93_{idx}_{ano_sel}_fiscal"):
                        res93.append(opcao)

            if set(res93) != set(sel93):
                save_resp("9.3", json.dumps(res93), 0.0, d93.get("link", ""))
                st.rerun()

        bloco_comentarios("9.0", res_data, sufixo="fiscal")

    # =============================================================================
    # QUESITO 9.4
    # =============================================================================
    with st.container(border=True):
        st.subheader("QUESITO 9.4")
        st.write("**O município instituiu normativo que obrigue o(s) Cartório(s) de Registro de Imóveis e Distribuidor(es) a informar periodicamente as transmissões imobiliárias realizadas no seu território, para fins de incidência do ITBI?**")
        
        d94 = res_data.get("9.4", {"valor": None, "pontos": 0, "link": ""})
        if d94 is None: d94 = {"valor": None, "pontos": 0, "link": ""}
        
        opc94 = ["Sim – 02", "Não – 00"]
        idx94 = opc94.index(d94["valor"]) if d94.get("valor") in opc94 else None
        
        c1, c2 = st.columns([1, 2])
        with c1: 
            r94 = st.radio("Selecione 9.4:", opc94, index=idx94, key=f"rad_94_{ano_sel}_fiscal")
        with c2: 
            val_l94 = d94.get("link", "") if d94.get("link") is not None else ""
            l94 = st.text_area("Link/Evidência (9.4):", value=val_l94, key=f"txt_94_{ano_sel}_fiscal", height=100)
            
            links_94_atuais = re.findall(r'(https?://[^\s]+)', l94) if l94 else []
            if links_94_atuais:
                botoes_94 = " | ".join([f"🔗 [{u}]({u})" for u in links_94_atuais])
                st.markdown(f"**Links Ativos:** {botoes_94}")
                
        pts94 = 2.0 if "Sim" in (r94 or "") else 0.0
        
        if r94 and (r94 != d94.get("valor") or l94 != d94.get("link")):
            save_resp("9.4", r94, pts94, l94)
            if links_94_atuais:
                links_94_antigos = re.findall(r'(https?://[^\s]+)', d94.get("link", "")) if d94.get("link") else []
                if links_94_atuais != links_94_antigos:
                    modal_aviso_link("9.4", links_94_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
                
        bloco_comentarios("9.4", res_data, sufixo="fiscal")

    # =============================================================================
    # QUESITO 9.4.1
    # =============================================================================
    with st.container(border=True):
        st.subheader("QUESITO 9.4.1")
        st.write("**O município aplica penalidade ou multa aos Cartórios, when não cumpridos os termos da lei mencionada na resposta do item anterior?**")
        
        d941 = res_data.get("9.4.1", {"valor": None, "pontos": 0, "link": ""})
        if d941 is None: d941 = {"valor": None, "pontos": 0, "link": ""}
        
        opc941 = ["Sim – 03", "Não – 00"]
        idx941 = opc941.index(d941["valor"]) if d941.get("valor") in opc941 else None
        
        c1, c2 = st.columns([1, 2])
        with c1: 
            r941 = st.radio("Selecione 9.4.1:", opc941, index=idx941, key=f"rad_941_{ano_sel}_fiscal")
        with c2: 
            val_l941 = d941.get("link", "") if d941.get("link") is not None else ""
            l941 = st.text_area("Link/Evidência (9.4.1):", value=val_l941, key=f"txt_941_{ano_sel}_fiscal", height=100)
            
            links_941_atuais = re.findall(r'(https?://[^\s]+)', l941) if l941 else []
            if links_941_atuais:
                botoes_941 = " | ".join([f"🔗 [{u}]({u})" for u in links_941_atuais])
                st.markdown(f"**Links Ativos:** {botoes_941}")
                
        pts941 = 3.0 if "Sim" in (r941 or "") else 0.0
        
        if r941 and (r941 != d941.get("valor") or l941 != d941.get("link")):
            save_resp("9.4.1", r941, pts941, l941)
            if links_941_atuais:
                links_941_antigos = re.findall(r'(https?://[^\s]+)', d941.get("link", "")) if d941.get("link") else []
                if links_941_atuais != links_941_antigos:
                    modal_aviso_link("9.4.1", links_941_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
                
        bloco_comentarios("9.4.1", res_data, sufixo="fiscal")

    # =============================================================================
    # QUESITO 9.5 (Formulário Múltipla Escolha Adaptado com Validador de Links)
    # =============================================================================
    with st.container(border=True):
        st.subheader("QUESITO 9.5")
        st.write("**Assinale a forma de recolhimento da guia do ITBI:**")
        
        d95 = res_data.get("9.5", {"valor": "", "pontos": 0, "link": ""})
        if d95 is None: d95 = {"valor": "", "pontos": 0, "link": ""}
        
        valor_salvo = d95["valor"] if d95.get("valor") else ""
        init_banco = "Sistema Bancário" in valor_salvo
        init_caixa = "Diretamente no Caixa da Prefeitura" in valor_salvo
        init_loterica = "Lotérica" in valor_salvo
        init_outros = "Outros" in valor_salvo

        c1, c2 = st.columns([1, 2])
        with c1:
            st.write("*Selecione todas as opções aplicáveis:*")
            chk_banco = st.checkbox("Sistema Bancário", value=init_banco, key=f"chk_95_banco_{ano_sel}_fiscal")
            chk_caixa = st.checkbox("Diretamente no Caixa da Prefeitura", value=init_caixa, key=f"chk_95_caixa_{ano_sel}_fiscal")
            chk_loterica = st.checkbox("Lotérica", value=init_loterica, key=f"chk_95_loterica_{ano_sel}_fiscal")
            chk_outros = st.checkbox("Outros", value=init_outros, key=f"chk_95_outros_{ano_sel}_fiscal")

        with c2:
            val_l95 = d95.get("link", "") if d95.get("link") is not None else ""
            l95 = st.text_area("Link/Evidência (9.5):", value=val_l95, key=f"txt_95_{ano_sel}_fiscal", height=150)
            
            links_95_atuais = re.findall(r'(https?://[^\s]+)', l95) if l95 else []
            if links_95_atuais:
                botoes_95 = " | ".join([f"🔗 [{u}]({u})" for u in links_95_atuais])
                st.markdown(f"**Links Ativos:** {botoes_95}")

        lista_selecionados = []
        if chk_banco: lista_selecionados.append("Sistema Bancário")
        if chk_caixa: lista_selecionados.append("Diretamente no Caixa da Prefeitura")
        if chk_loterica: lista_selecionados.append("Lotérica")
        if chk_outros: lista_selecionados.append("Outros")
        
        str_resultado = "/".join(lista_selecionados) if lista_selecionados else "Nenhuma"

        if str_resultado != d95.get("valor") or l95 != d95.get("link"):
            save_resp("9.5", str_resultado, 0.0, l95)
            if links_95_atuais:
                links_95_antigos = re.findall(r'(https?://[^\s]+)', d95.get("link", "")) if d95.get("link") else []
                if links_95_atuais != links_95_antigos:
                    modal_aviso_link("9.5", links_95_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("9.5", res_data, sufixo="fiscal")
 
    # =============================================================================
    # QUESITO 9.6
    # =============================================================================
    with st.container(border=True):
        st.subheader("QUESITO 9.6")
        st.write("**O município estabelece alíquotas progressivas para o ITBI, com base no valor venal? Súmula 656, do Supremo Tribunal Federal**")
        
        d96 = res_data.get("9.6", {"valor": None, "pontos": 0, "link": ""})
        if d96 is None: d96 = {"valor": None, "pontos": 0, "link": ""}
        
        opc96 = ["Sim – -30", "Não – 00"]
        idx96 = opc96.index(d96["valor"]) if d96.get("valor") in opc96 else None
        
        c1, c2 = st.columns([1, 2])
        with c1: 
            r96 = st.radio("Selecione 9.6:", opc96, index=idx96, key=f"rad_96_{ano_sel}_fiscal")
        with c2: 
            val_l96 = d96.get("link", "") if d96.get("link") is not None else ""
            l96 = st.text_area("Link/Evidência (9.6):", value=val_l96, key=f"txt_96_{ano_sel}_fiscal", height=100)
            
            links_96_atuais = re.findall(r'(https?://[^\s]+)', l96) if l96 else []
            if links_96_atuais:
                botoes_96 = " | ".join([f"🔗 [{u}]({u})" for u in links_96_atuais])
                st.markdown(f"**Links Ativos:** {botoes_96}")
                
        pts96 = -30.0 if "Sim" in (r96 or "") else 0.0
        
        if r96 and (r96 != d96.get("valor") or l96 != d96.get("link")):
            save_resp("9.6", r96, pts96, l96)
            if links_96_atuais:
                links_96_antigos = re.findall(r'(https?://[^\s]+)', d96.get("link", "")) if d96.get("link") else []
                if links_96_atuais != links_96_antigos:
                    modal_aviso_link("9.6", links_96_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
                
        bloco_comentarios("9.6", res_data, sufixo="fiscal")

    # -------------------------------------------------------------------------
    # SEÇÃO 5: CIP, IRRF E RENÚNCIA
    # -------------------------------------------------------------------------
    st.markdown("### 5. CIP, IRRF e Renúncia de Receita")

    # =============================================================================
    # BLOCO UNIFICADO: QUESITOS 10.0 A 10.3 (Contribuição de Iluminação Pública - CIP)
    # =============================================================================
    with st.container(border=True):
        st.subheader("QUESITO 10.0")
        st.write("**A Contribuição para Custeio do Serviço de Iluminação Pública (CIP) foi instituída?**")
        
        d100 = res_data.get("10.0", {"valor": None, "pontos": 0, "link": ""})
        if d100 is None: d100 = {"valor": None, "pontos": 0, "link": ""}
        
        opc100 = ["Sim", "Não"]
        idx100 = opc100.index(d100["valor"]) if d100.get("valor") in opc100 else None
        
        c1, c2 = st.columns([1, 2])
        with c1:
            r100 = st.radio("Selecione 10.0:", opc100, index=idx100, key=f"rad_100_{ano_sel}_fiscal")
        with c2:
            val_l100 = d100.get("link", "") if d100.get("link") is not None else ""
            l100 = st.text_area("Link/Evidência Geral (10.0):", value=val_l100, key=f"txt_100_{ano_sel}_fiscal", height=100)
            
            links_100_atuais = re.findall(r'(https?://[^\s]+)', l100) if l100 else []
            if links_100_atuais:
                botoes_100 = " | ".join([f"🔗 [{u}]({u})" for u in links_100_atuais])
                st.markdown(f"**Links Ativos:** {botoes_100}")
                
        if r100 and (r100 != d100.get("valor") or l100 != d100.get("link")):
            save_resp("10.0", r100, 0.0, l100)
            if links_100_atuais:
                links_100_antigos = re.findall(r'(https?://[^\s]+)', d100.get("link", "")) if d100.get("link") else []
                if links_100_atuais != links_100_antigos:
                    modal_aviso_link("10.0", links_100_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        # Subquesitos Condicionais (Só abrem se a CIP/COSIP for instituída)
        if r100 and "Sim" in r100:
            st.markdown("---")
            st.write("📋 **Detalhamento da Contribuição de Iluminação Pública (CIP):**")
            
            # QUESITO 10.1
            st.write("**10.1** Informe o instrumento normativo de instituição da Contribuição para Custeio do Serviço de Iluminação Pública (CIP), número e data da publicação:")
            st.caption("ℹ️ *Caso não esteja disponível na internet, recomendamos anexar o documento no Sistema de Questionários.*")
            
            d101 = res_data.get("10.1", {"valor": "", "pontos": 0, "link": ""})
            if d101 is None: d101 = {"valor": "", "pontos": 0, "link": ""}
            
            v101 = st.text_input("Instrumento normativo da CIP (Nº e Data):", value=d101.get("valor", ""), key=f"txt_101_val_{ano_sel}_fiscal")
            if v101 != d101.get("valor"):
                save_resp("10.1", v101, 0.0, "")
                st.rerun()

            # QUESITO 10.2 (Fórmula de Cálculo com trava de Rerun para o termo XYZ)
            st.write("**10.2** Informe a página eletrônica (link na internet) de divulgação do instrumento normativo de instituição da CIP:")
            st.caption("⚠️ *Se não estiver disponível na internet, inserir no campo o texto **XYZ** (Aplica penalidade de -03 pontos).*")
            
            d102 = res_data.get("10.2", {"valor": "", "pontos": 0, "link": ""})
            if d102 is None: d102 = {"valor": "", "pontos": 0, "link": ""}
            
            v102 = st.text_input("Link de divulgação da CIP (ou XYZ):", value=d102.get("valor", ""), key=f"txt_102_val_{ano_sel}_fiscal")
            
            links_102_atuais = re.findall(r'(https?://[^\s]+)', v102) if v102 else []
            if links_102_atuais:
                botoes_102 = " | ".join([f"🔗 [{u}]({u})" for u in links_102_atuais])
                st.markdown(f"**Links Ativos detectados no campo:** {botoes_102}")
                
            pts102 = -3.0 if v102.strip().upper() == "XYZ" else 0.0
            
            if v102 != d102.get("valor"):
                save_resp("10.2", v102, pts102, "")
                if links_102_atuais:
                    links_102_antigos = re.findall(r'(https?://[^\s]+)', d102.get("valor", "")) if d102.get("valor") else []
                    if links_102_atuais != links_102_antigos:
                        modal_aviso_link("10.2", links_102_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()

            st.markdown("---")

            # QUESITO 10.3 (Aplicação de Penalidade Crítica por ausência de Conta Específica)
            st.write("**10.3** Os recursos da Contribuição para Custeio do Serviço de Iluminação Pública (CIP) foram movimentados em contas específicas?")
            
            d103 = res_data.get("10.3", {"valor": None, "pontos": 0, "link": ""})
            if d103 is None: d103 = {"valor": None, "pontos": 0, "link": ""}
            
            opc103 = ["Sim – 00", "Não – -05 (perde 05 pontos)"]
            idx103 = opc103.index(d103["valor"]) if d103.get("valor") in opc103 else None
            
            c3, c4 = st.columns([1, 2])
            with c3:
                r103 = st.radio("Selecione 10.3:", opc103, index=idx103, key=f"rad_103_{ano_sel}_fiscal")
            with c4:
                val_l103 = d103.get("link", "") if d103.get("link") is not None else ""
                l103 = st.text_area("Link/Evidência de Conta Bancária Exclusiva (10.3):", value=val_l103, key=f"txt_103_{ano_sel}_fiscal", height=100)
                
                links_103_atuais = re.findall(r'(https?://[^\s]+)', l103) if l103 else []
                if links_103_atuais:
                    botoes_103 = " | ".join([f"🔗 [{u}]({u})" for u in links_103_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_103}")
            
            pts103 = -5.0 if "Não" in (r103 or "") else 0.0
            
            if r103 and (r103 != d103.get("valor") or l103 != d103.get("link")):
                save_resp("10.3", r103, pts103, l103)
                if links_103_atuais:
                    links_103_antigos = re.findall(r'(https?://[^\s]+)', d103.get("link", "")) if d103.get("link") else []
                    if links_103_atuais != links_103_antigos:
                        modal_aviso_link("10.3", links_103_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()

        bloco_comentarios("10.0", res_data, sufixo="fiscal")

    # =============================================================================
    # QUESITO 11.0
    # =============================================================================
    with st.container(border=True):
        st.subheader("QUESITO 11.0")
        st.write("**Houve regulamentação sobre a retenção de IRRF das contratações efetuadas pelo município nas compras de bens e serviços?**")
        
        d110 = res_data.get("11.0", {"valor": None, "pontos": 0, "link": ""})
        if d110 is None: d110 = {"valor": None, "pontos": 0, "link": ""}
        
        opc110 = ["Sim – 03", "Não – 00"]
        idx110 = opc110.index(d110["valor"]) if d110.get("valor") in opc110 else None
        
        c1, c2 = st.columns([1, 2])
        with c1: 
            r110 = st.radio("Selecione 11.0:", opc110, index=idx110, key=f"rad_110_{ano_sel}_fiscal")
        with c2: 
            val_l110 = d110.get("link", "") if d110.get("link") is not None else ""
            l110 = st.text_area("Link/Evidência (11.0):", value=val_l110, key=f"txt_110_{ano_sel}_fiscal", height=100)
            
            links_110_atuais = re.findall(r'(https?://[^\s]+)', l110) if l110 else []
            if links_110_atuais:
                botoes_110 = " | ".join([f"🔗 [{u}]({u})" for u in links_110_atuais])
                st.markdown(f"**Links Ativos:** {botoes_110}")
                
        pts110 = 3.0 if "Sim" in (r110 or "") else 0.0
        
        if r110 and (r110 != d110.get("valor") or l110 != d110.get("link")):
            save_resp("11.0", r110, pts110, l110)
            if links_110_atuais:
                links_110_antigos = re.findall(r'(https?://[^\s]+)', d110.get("link", "")) if d110.get("link") else []
                if links_110_atuais != links_110_antigos:
                    modal_aviso_link("11.0", links_110_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()
                
        bloco_comentarios("11.0", res_data, sufixo="fiscal")
    # =============================================================================
    # BLOCO INTEGRADO E DINÂMICO: QUESITOS 12.0 A 12.5.2 (Renúncia de Receitas)
    # =============================================================================
    with st.container(border=True):
        st.subheader("QUESITO 12.0")
        
        # Enunciado dinâmico atrelado ao ano selecionado no painel
        st.write(f"**No exercício de {ano_sel}, foram concedidos benefícios e incentivos de natureza tributária, financeira e creditícia da qual decorram em renúncia de receitas?**")
        st.caption(f"📌 *Nota do Sistema: Esta resposta será vinculada ao exercício selecionado atualmente: **{ano_sel}***")
        
        d120 = res_data.get("12.0", {"valor": None, "pontos": 0, "link": ""})
        if d120 is None: d120 = {"valor": None, "pontos": 0, "link": ""}
        
        opc120 = ["Sim", "Não"]
        valor_limpo_120 = d120["valor"].split(" | ")[0] if d120.get("valor") else None
        idx120 = opc120.index(valor_limpo_120) if valor_limpo_120 in opc120 else None
        
        c1, c2 = st.columns([1, 2])
        with c1:
            r120 = st.radio("Selecione 12.0:", opc120, index=idx120, key=f"rad_120_{ano_sel}_fiscal")
        with c2:
            val_l120 = d120.get("link", "") if d120.get("link") is not None else ""
            l120 = st.text_area(f"Link/Evidência Geral ({ano_sel}):", value=val_l120, key=f"txt_120_{ano_sel}_fiscal", height=100)
            
            links_120_atuais = re.findall(r'(https?://[^\s]+)', l120) if l120 else []
            if links_120_atuais:
                botoes_120 = " | ".join([f"🔗 [{u}]({u})" for u in links_120_atuais])
                st.markdown(f"**Links Ativos:** {botoes_120}")
            
        if r120:
            valor_com_ano = f"{r120} | Exercício Ref: {ano_sel}"
            if valor_com_ano != d120.get("valor") or l120 != d120.get("link"):
                save_resp("12.0", valor_com_ano, 0.0, l120)
                if links_120_atuais:
                    links_120_antigos = re.findall(r'(https?://[^\s]+)', d120.get("link", "")) if d120.get("link") else []
                    if links_120_atuais != links_120_antigos:
                        modal_aviso_link("12.0", links_120_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()

        # 🔓 TODOS OS SUBQUESITOS ABAIXO SÓ ABREM SE A 12.0 FOR "SIM"
        if r120 and "Sim" in r120:
            st.markdown("---")
            st.subheader("📋 DETALHAMENTO DA RENÚNCIA DE RECEITAS")
            
            # QUESITO 12.1 (Penalidade Crítica: -10 pontos)
            st.write("**12.1** Há normas e procedimentos relativos à renúncia de receita?")
            
            d121 = res_data.get("12.1", {"valor": None, "pontos": 0, "link": ""})
            if d121 is None: d121 = {"valor": None, "pontos": 0, "link": ""}
            
            opc121 = ["Sim – 00", "Não – -10 (perde 10 pontos)"]
            idx121 = opc121.index(d121["valor"]) if d121.get("valor") in opc121 else None
            
            r121 = st.radio("Selecione 12.1:", opc121, index=idx121, key=f"rad_121_{ano_sel}_fiscal")
            pts121 = -10.0 if "Não" in (r121 or "") else 0.0
            
            if r121 and r121 != d121["valor"]:
                save_resp("12.1", r121, pts121, "")
                st.rerun()

            # Subquesitos filhos do 12.1 (Abrem se 12.1 for Sim)
            if r121 and "Sim" in r121:
                # Substituído div por container interno com borda para destacar a hierarquia
                with st.container(border=True):
                    # QUESITO 12.1.1
                    st.write("**12.1.1** Informe o instrumento normativo de regulamentação dos procedimentos relativos à renúncia de receita, Número e Data da publicação:")
                    
                    d1211 = res_data.get("12.1.1", {"valor": "", "pontos": 0, "link": ""})
                    if d1211 is None: d1211 = {"valor": "", "pontos": 0, "link": ""}
                    
                    v1211 = st.text_input("Instrumento normativo (Nº e Data):", value=d1211.get("valor", ""), key=f"txt_1211_{ano_sel}_fiscal")
                    if v1211 != d1211["valor"]:
                        save_resp("12.1.1", v1211, 0.0, "")
                        st.rerun()

                    # QUESITO 12.1.2 (Fórmula XYZ = -3 pontos)
                    st.write("**12.1.2** Informe a página eletrônica (link na internet) de divulgação do instrumento normativo de regulamentação:")
                    st.caption("ℹ️ *Se não estiver disponível na internet, inserir no campo o texto **XYZ***")
                    
                    d1212 = res_data.get("12.1.2", {"valor": "", "pontos": 0, "link": ""})
                    if d1212 is None: d1212 = {"valor": "", "pontos": 0, "link": ""}
                    
                    v1212 = st.text_input("Página eletrônica (ou XYZ) - 12.1.2:", value=d1212.get("valor", ""), key=f"txt_1212_{ano_sel}_fiscal")
                    
                    links_1212_atuais = re.findall(r'(https?://[^\s]+)', v1212) if v1212 else []
                    if links_1212_atuais:
                        botoes_1212 = " | ".join([f"🔗 [{u}]({u})" for u in links_1212_atuais])
                        st.markdown(f"**Links Ativos detectados no campo:** {botoes_1212}")
                        
                    pts1212 = -3.0 if v1212.strip().upper() == "XYZ" else 0.0
                    
                    if v1212 != d1212["valor"]:
                        save_resp("12.1.2", v1212, pts1212, "")
                        if links_1212_atuais:
                            links_1212_antigos = re.findall(r'(https?://[^\s]+)', d1212.get("valor", "")) if d1212.get("valor") else []
                            if links_1212_atuais != links_1212_antigos:
                                modal_aviso_link("12.1.2", links_1212_atuais)
                            else:
                                st.rerun()
                        else:
                            st.rerun()

            st.markdown("---")

            # QUESITO 12.2
            st.write("**12.2** A Prefeitura Municipal realizou acompanhamento e (re)avaliação das renúncias de receita?")
            
            d122 = res_data.get("12.2", {"valor": None, "pontos": 0, "link": ""})
            if d122 is None: d122 = {"valor": None, "pontos": 0, "link": ""}
            
            opc122 = [
                "Sim, de todas as renúncias de receita – 00",
                "Sim, de parte das renúncias de receita – -02 (perde 02 pontos)",
                "Não – -05 (perde 05 pontos)"
            ]
            idx122 = opc122.index(d122["valor"]) if d122["valor"] in opc122 else None
            
            c3, c4 = st.columns([1, 2])
            with c3:
                r122 = st.radio("Selecione 12.2:", opc122, index=idx122, key=f"rad_122_{ano_sel}_fiscal")
            with c4:
                val_l122 = d122.get("link", "") if d122.get("link") is not None else ""
                l122 = st.text_area("Link/Evidência do Acompanhamento (12.2):", value=val_l122, key=f"txt_122_{ano_sel}_fiscal", height=100)
                
                links_122_atuais = re.findall(r'(https?://[^\s]+)', l122) if l122 else []
                if links_122_atuais:
                    botoes_122 = " | ".join([f"🔗 [{u}]({u})" for u in links_122_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_122}")
                
            if "todas" in (r122 or ""): pts122 = 0.0
            elif "parte" in (r122 or ""): pts122 = -2.0
            else: pts122 = -5.0

            if r122 and (r122 != d122["valor"] or l122 != d122["link"]):
                save_resp("12.2", r122, pts122, l122)
                if links_122_atuais:
                    links_122_antigos = re.findall(r'(https?://[^\s]+)', d122.get("link", "")) if d122.get("link") else []
                    if links_122_atuais != links_122_antigos:
                        modal_aviso_link("12.2", links_122_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()

            st.markdown("---")

            # QUESITO 12.3
            st.write(f"**12.3** O Anexo de Metas Fiscais, que integra a LDO, contém demonstrativo da estimativa e compensação da renúncia de receita para o respectivo exercício orçamentário?")
            
            d123 = res_data.get("12.3", {"valor": None, "pontos": 0, "link": ""})
            if d123 is None: d123 = {"valor": None, "pontos": 0, "link": ""}
            
            opc123 = [
                "Todas as renúncias concedidas estão contidas no demonstrativo – 00",
                "A maior parte das renúncias concedidas estão contidas no demonstrativo – -01 (perde 01 ponto)",
                "A menor parte das renúncias concedidas estão contidas no demonstrativo – -03 (perde 03 pontos)",
                "Não há demonstrativo – -05 (perde 05 pontos)"
            ]
            idx123 = opc123.index(d123["valor"]) if d123["valor"] in opc123 else None
            
            c5, c6 = st.columns([1, 2])
            with c5:
                r123 = st.radio("Selecione 12.3:", opc123, index=idx123, key=f"rad_123_{ano_sel}_fiscal")
            with c6:
                val_l123 = d123.get("link", "") if d123.get("link") is not None else ""
                l123 = st.text_area("Link/Evidência do AMF da LDO (12.3):", value=val_l123, key=f"txt_123_{ano_sel}_fiscal", height=100)
                
                links_123_atuais = re.findall(r'(https?://[^\s]+)', l123) if l123 else []
                if links_123_atuais:
                    botoes_123 = " | ".join([f"🔗 [{u}]({u})" for u in links_123_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_123}")
                
            if "Todas" in (r123 or ""): pts123 = 0.0
            elif "maior" in (r123 or ""): pts123 = -1.0
            elif "menor" in (r123 or ""): pts123 = -3.0
            else: pts123 = -5.0

            if r123 and (r123 != d123["valor"] or l123 != d123["link"]):
                save_resp("12.3", r123, pts123, l123)
                if links_123_atuais:
                    links_123_antigos = re.findall(r'(https?://[^\s]+)', d123.get("link", "")) if d123.get("link") else []
                    if links_123_atuais != links_123_antigos:
                        modal_aviso_link("12.3", links_123_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()

            st.markdown("---")

            # QUESITO 12.3.1 (Novo: Compatibilidade de Valores com Ano Dinâmico)
            st.write(f"**12.3.1** O valor da renúncia de receita de {ano_sel} está compatível com a estimativa constante no Anexo de Metas Fiscais da Lei de Diretrizes Orçamentárias?")
            
            d1231 = res_data.get("12.3.1", {"valor": None, "pontos": 0, "link": ""})
            if d1231 is None: d1231 = {"valor": None, "pontos": 0, "link": ""}
            
            opc1231 = ["Sim – 00", "Não – -05 (perde 05 pontos)"]
            idx1231 = opc1231.index(d1231["valor"]) if d1231["valor"] in opc1231 else None
            
            r1231 = st.radio("Selecione 12.3.1:", opc1231, index=idx1231, key=f"rad_1231_{ano_sel}_fiscal")
            pts1231 = -5.0 if "Não" in (r1231 or "") else 0.0
            
            if r1231 and r1231 != d1231["valor"]:
                save_resp("12.3.1", r1231, pts1231, "")
                st.rerun()

            st.markdown("---")

            # QUESITO 12.4 (Blindado contra retenção de estado do Streamlit)
            st.write(f"**12.4** Informe o valor das renúncias no exercício de {ano_sel}:")
            
            if f"v124_key_suffix_{ano_sel}" not in st.session_state:
                st.session_state[f"v124_key_suffix_{ano_sel}"] = 0

            d124 = res_data.get("12.4", {"valor": "R$ 0,00", "pontos": 0, "link": ""})
            if d124 is None: d124 = {"valor": "R$ 0,00", "pontos": 0, "link": ""}
            
            val_inicial = d124["valor"] if d124["valor"].startswith("R$") else f"R$ {d124['valor']}"

            sufixo_atual = st.session_state[f"v124_key_suffix_{ano_sel}"]
            v124_input = st.text_input(
                "Informe o Valor Total (R$):", 
                value=val_inicial, 
                placeholder="Ex: 100.000,00",
                key=f"txt_124_dinamico_{ano_sel}_{sufixo_atual}_fiscal"
            )

            if v124_input != d124["valor"]:
                num_limpo = v124_input.replace("R$", "").replace(" ", "")
                
                if "." in num_limpo and "," in num_limpo:
                    num_limpo = num_limpo.replace(".", "").replace(",", ".")
                elif "," in num_limpo:
                    num_limpo = num_limpo.replace(",", ".")
                    
                try:
                    valor_float = float(num_limpo)
                    valor_br = f"{valor_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                    v124_salvar = f"R$ {valor_br}"
                    
                    if v124_salvar != d124["valor"]:
                        save_resp("12.4", v124_salvar, 0.0, "")
                        st.session_state[f"v124_key_suffix_{ano_sel}"] += 1
                        st.rerun()
                        
                except ValueError:
                    st.error("⚠️ Digite apenas números. Use vírgula para os centavos (Ex: 100000 ou 100000,00).")

            st.markdown("---")

            # QUESITO 12.5 (Novo: Transparência com Penalidade Crítica de -10 pontos)
            st.write(f"**12.5** Houve publicidade e transparência dos benefícios concedidos por Renúncia de Receitas em {ano_sel}?")
            
            d125 = res_data.get("12.5", {"valor": None, "pontos": 0, "link": ""})
            if d125 is None: d125 = {"valor": None, "pontos": 0, "link": ""}
            
            opc125 = ["Sim – 00", "Não – -10 (perde 10 pontos)"]
            idx125 = opc125.index(d125["valor"]) if d125["valor"] in opc125 else None
            
            r125 = st.radio("Selecione 12.5:", opc125, index=idx125, key=f"rad_125_{ano_sel}_fiscal")
            pts125 = -10.0 if "Não" in (r125 or "") else 0.0
            
            if r125 and r125 != d125["valor"]:
                save_resp("12.5", r125, pts125, "")
                st.rerun()

            # Subquesitos de Transparência (Só abrem se a resposta do 12.5 for Sim)
            if r125 and "Sim" in r125:
                # Substituído div por container interno com borda para preservar indentação visual
                with st.container(border=True):
                    # QUESITO 12.5.1 (Novo: Checklist de Informações Divulgadas)
                    st.write(f"**12.5.1** Assinale as informações divulgadas referente aos benefícios concedidos por Renúncia de Receitas em {ano_sel}: (Checklist)**")
                    
                    d1251 = res_data.get("12.5.1", {"valor": "[]", "pontos": 0, "link": ""})
                    if d1251 is None: d1251 = {"valor": "[]", "pontos": 0, "link": ""}
                    
                    try:
                        val_banco1251 = d1251["valor"].replace("'", '"')
                        sel1251 = json.loads(val_banco1251)
                        if not isinstance(sel1251, list): sel1251 = []
                    except:
                        sel1251 = []

                    opc1251 = [
                        "Valor dos benefícios concedidos",
                        "Público beneficiado",
                        "Métodos utilizados na sua mensuração",
                        "Resultados socioeconômicos alcançados com a renúncia",
                        "Outros"
                    ]
                    c7, c8 = st.columns([1, 1])
                    res1251 = []

                    for idx, opcao in enumerate(opc1251):
                        target_col = c7 if idx % 2 == 0 else c8
                        with target_col:
                            pode_marcar = opcao in sel1251
                            if st.checkbox(opcao, value=pode_marcar, key=f"chk_1251_{idx}_{ano_sel}_fiscal"):
                                res1251.append(opcao)

                    if set(res1251) != set(sel1251):
                        save_resp("12.5.1", json.dumps(res1251), 0.0, "")
                        st.rerun()

                    # QUESITO 12.5.2 (Novo: Link de Transparência com Fórmula XYZ = -10 pontos)
                    st.write(f"**12.5.2** Informe a página eletrônica (link na internet) de divulgação das informações referente aos benefícios concedidos por Renúncia de Receitas em {ano_sel}:")
                    st.caption("⚠️ *Se não estiver disponível na internet, inserir no campo o texto **XYZ** (Aplica penalidade crítica de -10 pontos).*")
                    
                    d1252 = res_data.get("12.5.2", {"valor": "", "pontos": 0, "link": ""})
                    if d1252 is None: d1252 = {"valor": "", "pontos": 0, "link": ""}
                    
                    v1252 = st.text_input("Link de divulgação da transparência (ou XYZ):", value=d1252.get("valor", ""), key=f"txt_1252_val_{ano_sel}_fiscal")
                    
                    links_1252_atuais = re.findall(r'(https?://[^\s]+)', v1252) if v1252 else []
                    if links_1252_atuais:
                        botoes_1252 = " | ".join([f"🔗 [{u}]({u})" for u in links_1252_atuais])
                        st.markdown(f"**Links Ativos detectados no campo:** {botoes_1252}")
                        
                    pts1252 = -10.0 if v1252.strip().upper() == "XYZ" else 0.0
                    
                    if v1252 != d1252["valor"]:
                        save_resp("12.5.2", v1252, pts1252, "")
                        if links_1252_atuais:
                            links_1252_antigos = re.findall(r'(https?://[^\s]+)', d1252.get("valor", "")) if d1252.get("valor") else []
                            if links_1252_atuais != links_1252_antigos:
                                modal_aviso_link("12.5.2", links_1252_atuais)
                            else:
                                st.rerun()
                        else:
                            st.rerun()

        bloco_comentarios("12.0", res_data, sufixo="fiscal")    


    # -------------------------------------------------------------------------
    # SEÇÃO 6: DÍVIDA ATIVA
    # -------------------------------------------------------------------------
    st.markdown("### 6. Dívida Ativa")

    # =============================================================================
    # BLOCO INTEGRADO: QUESITOS 13.0 A 13.3 (Regulamentação sobre Dívida Ativa)
    # =============================================================================
    with st.container(border=True):
        st.subheader("QUESITO 13.0")
        st.write("**O município possui regulamentação sobre dívida ativa?**")
        
        d130 = res_data.get("13.0", {"valor": None, "pontos": 0, "link": ""})
        if d130 is None: d130 = {"valor": None, "pontos": 0, "link": ""}
        
        opc130 = ["Sim – 01", "Não – 00"]
        idx130 = opc130.index(d130["valor"]) if d130.get("valor") in opc130 else None
        
        c1, c2 = st.columns([1, 2])
        with c1:
            r130 = st.radio("Selecione 13.0:", opc130, index=idx130, key=f"rad_130_{ano_sel}_fiscal")
        with c2:
            val_l130 = d130.get("link", "") if d130.get("link") is not None else ""
            l130 = st.text_area("Link/Evidência Geral (13.0):", value=val_l130, key=f"txt_130_{ano_sel}_fiscal", height=100)
            
            links_130_atuais = re.findall(r'(https?://[^\s]+)', l130) if l130 else []
            if links_130_atuais:
                botoes_130 = " | ".join([f"🔗 [{u}]({u})" for u in links_130_atuais])
                st.markdown(f"**Links Ativos:** {botoes_130}")
            
        pts130 = 1.0 if "Sim" in (r130 or "") else 0.0
        
        if r130 and (r130 != d130.get("valor") or l130 != d130.get("link")):
            save_resp("13.0", r130, pts130, l130)
            if links_130_atuais:
                links_130_antigos = re.findall(r'(https?://[^\s]+)', d130.get("link", "")) if d130.get("link") else []
                if links_130_atuais != links_130_antigos:
                    modal_aviso_link("13.0", links_130_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        # 🔓 SUBQUESITOS CONDICIONAIS (Só abrem se a resposta do 13.0 for SIM)
        if r130 and "Sim" in r130:
            st.markdown("---")
            st.write("📋 **Detalhamento da Regulamentação da Dívida Ativa:**")
            
            # QUESITO 13.1
            st.write("**13.1** Instrumento normativo de regulamentação da dívida ativa, Número e Data da publicação:")
            st.caption("ℹ️ *Caso não esteja disponível na internet, recomendamos anexar o documento no Sistema de Questionários.*")
            
            d131 = res_data.get("13.1", {"valor": "", "pontos": 0, "link": ""})
            if d131 is None: d131 = {"valor": "", "pontos": 0, "link": ""}
            
            v131 = st.text_input("Instrumento normativo da Dívida Ativa (Nº e Data):", value=d131.get("valor", ""), key=f"txt_131_val_{ano_sel}_fiscal")
            if v131 != d131["valor"]:
                save_resp("13.1", v131, 0.0, "")
                st.rerun()

           # --- QUESITO 13.2 (Fórmula XYZ com trava de Rerun) ---
            st.write("**13.2** Informe a página eletrônica (link na internet) de divulgação da regulamentação da dívida ativa:")
            st.caption("ℹ️ *Se não estiver disponível na internet, inserir no campo o texto **XYZ***")
            
            d132 = res_data.get("13.2", {"valor": "", "pontos": 0, "link": ""})
            if d132 is None: d132 = {"valor": "", "pontos": 0, "link": ""}
            
            v132 = st.text_input("Link de divulgação da Dívida Ativa (ou XYZ):", value=d132.get("valor", ""), key=f"txt_132_val_{ano_sel}_fiscal")
            
            # 🛡️ Espaço reservado estático fixo para evitar quebra do DOM no React/Navegador
            container_links_132 = st.empty()
            
            links_132_atuais = re.findall(r'(https?://[^\s]+)', v132) if v132 else []
            if links_132_atuais:
                botoes_132 = " | ".join([f"🔗 [{u}]({u})" for u in links_132_atuais])
                # Atualiza com segurança apenas a parte interna do bloco reservado
                container_links_132.markdown(f"**Links Ativos detectados no campo:** {botoes_132}")
            
            pts132 = 0.0 
            if v132 != d132.get("valor", ""):
                save_resp("13.2", v132, float(pts132), "")
                if links_132_atuais:
                    links_132_antigos = re.findall(r'(https?://[^\s]+)', d132.get("valor", "")) if d132.get("valor") else []
                    if links_132_atuais != links_132_antigos:
                        modal_aviso_link("13.2", links_132_atuais)
                    else:
                        st.rerun()
                else:
                    st.rerun()

            st.markdown("---")

            # QUESITO 13.3 - Checklist de Critérios com soma garantida e blindada
            st.write("**13.3 Assinale os critérios estabelecidos na legislação sobre dívida ativa: (Checklist)**")
            
            d133 = res_data.get("13.3", {"valor": "[]", "pontos": 0, "link": ""})
            if d133 is None: d133 = {"valor": "[]", "pontos": 0, "link": ""}
            
            try:
                val_banco133 = d133["valor"].replace("'", '"')
                sel133 = json.loads(val_banco133)
                if not isinstance(sel133, list): sel133 = []
            except:
                sel133 = []

            opcoes_133 = [
                "Cobrança administrativa da dívida ativa – 1,5",
                "Parcelamento da dívida ativa – 1,5",
                "Restrição e controle da inadimplência nos parcelamentos da dívida ativa – 1,5",
                "Início do trâmite da execução judicial da dívida ativa – 1,5",
                "Anistia – 1,5",
                "Remissão – 1,5"
            ]

            c3, c4 = st.columns([1, 1])
            res133 = []

            for idx, opcao in enumerate(opcoes_133):
                target_col = c3 if idx % 2 == 0 else c4
                with target_col:
                    pode_marcar = opcao in sel133
                    if st.checkbox(opcao, value=pode_marcar, key=f"chk_133_{idx}_{ano_sel}_fiscal"):
                        res133.append(opcao)

            pts133 = 0.0
            for item in res133:
                if "Cobrança administrativa" in item: pts133 += 1.5
                if "Parcelamento" in item: pts133 += 1.5
                if "Restrição e controle" in item: pts133 += 1.5
                if "Início do trâmite" in item: pts133 += 1.5
                if "Anistia" in item: pts133 += 1.5
                if "Remissão" in item: pts133 += 1.5

            if set(res133) != set(sel133):
                save_resp("13.3", json.dumps(res133), pts133, d133.get("link", ""))
                st.rerun()

        bloco_comentarios("13.0", res_data, sufixo="fiscal")

# =============================================================================
    # BLOCO INTEGRADO: QUESITOS 14.0 A 15.1 (Dívida Ativa Judicial e Extrajudicial)
    # =============================================================================
    
    # --- QUESITOS 14.0 e 14.1 (Cobrança Judicial) ---
    with st.container(border=True):
        st.subheader("QUESITO 14.0")
        st.write(f"**O Município possui dívida ativa executada de forma judicial em {ano_sel}?**")
        
        d140 = res_data.get("14.0", {"valor": None, "pontos": 0, "link": ""})
        if d140 is None: d140 = {"valor": None, "pontos": 0, "link": ""}
        
        opc140 = ["Sim", "Não"]
        idx140 = opc140.index(d140["valor"]) if d140.get("valor") in opc140 else None
        
        c1, c2 = st.columns([1, 2])
        with c1:
            r140 = st.radio("Selecione 14.0:", opc140, index=idx140, key=f"rad_140_{ano_sel}_fiscal")
        with c2:
            val_l140 = d140.get("link", "") if d140.get("link") is not None else ""
            l140 = st.text_area(f"Link/Evidência Geral de Execuções ({ano_sel}):", value=val_l140, key=f"txt_140_{ano_sel}_fiscal", height=100)
            
            links_140_atuais = re.findall(r'(https?://[^\s]+)', l140) if l140 else []
            if links_140_atuais:
                botoes_140 = " | ".join([f"🔗 [{u}]({u})" for u in links_140_atuais])
                st.markdown(f"**Links Ativos:** {botoes_140}")
            
        if r140 and (r140 != d140.get("valor") or l140 != d140.get("link")):
            save_resp("14.0", r140, 0.0, l140)
            if links_140_atuais:
                links_140_antigos = re.findall(r'(https?://[^\s]+)', d140.get("link", "")) if d140.get("link") else []
                if links_140_atuais != links_140_antigos:
                    modal_aviso_link("14.0", links_140_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        # Subquesito Condicional 14.1 (Formato Monetário BR com Key-Toggle)
        if r140 and "Sim" in r140:
            with st.container(border=True):
                st.write(f"**14.1** Informe o valor total da dívida ativa executada de forma judicial no exercício de {ano_sel}:")
                
                if f"v141_key_suffix_{ano_sel}" not in st.session_state:
                    st.session_state[f"v141_key_suffix_{ano_sel}"] = 0

                d141 = res_data.get("14.1", {"valor": "R$ 0,00", "pontos": 0, "link": ""})
                if d141 is None: d141 = {"valor": "R$ 0,00", "pontos": 0, "link": ""}
                
                val_inicial_141 = d141["valor"] if d141["valor"].startswith("R$") else f"R$ {d141['valor']}"
                sufixo_141 = st.session_state[f"v141_key_suffix_{ano_sel}"]

                v141_input = st.text_input(
                    "Informe o Valor Judicial Total (R$):", 
                    value=val_inicial_141, 
                    placeholder="Ex: 150.000,00",
                    key=f"txt_141_dinamico_{ano_sel}_{sufixo_141}_fiscal"
                )

                if v141_input != d141["valor"]:
                    num_limpo = v141_input.replace("R$", "").replace(" ", "")
                    if "." in num_limpo and "," in num_limpo:
                        num_limpo = num_limpo.replace(".", "").replace(",", ".")
                    elif "," in num_limpo:
                        num_limpo = num_limpo.replace(",", ".")
                    try:
                        valor_float = float(num_limpo)
                        valor_br = f"{valor_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        v141_salvar = f"R$ {valor_br}"
                        if v141_salvar != d141["valor"]:
                            save_resp("14.1", v141_salvar, 0.0, "")
                            st.session_state[f"v141_key_suffix_{ano_sel}"] += 1
                            st.rerun()
                    except ValueError:
                        st.error("⚠️ Digite apenas números. Use vírgula para os centavos (Ex: 150000 ou 150000,00).")

        bloco_comentarios("14.0", res_data, sufixo="fiscal")


    # =============================================================================
    # BLOCO UNIFICADO: QUESITOS 15.0 A 15.2 (Cobrança Extrajudicial da Dívida Ativa)
    # =============================================================================
    with st.container(border=True):
        st.subheader("QUESITO 15.0")
        st.write(f"**A prefeitura realiza cobrança de dívida ativa de forma extrajudicial in {ano_sel}?**")
        
        d150 = res_data.get("15.0", {"valor": None, "pontos": 0, "link": ""})
        if d150 is None: d150 = {"valor": None, "pontos": 0, "link": ""}
        
        opc150 = ["Sim", "Não"]
        idx150 = opc150.index(d150["valor"]) if d150.get("valor") in opc150 else None
        
        c3, c4 = st.columns([1, 2])
        with c3:
            r150 = st.radio("Selecione 15.0:", opc150, index=idx150, key=f"rad_150_{ano_sel}_fiscal")
        with c4:
            val_l150 = d150.get("link", "") if d150.get("link") is not None else ""
            l150 = st.text_area(f"Link/Evidência de Cobranças Protestadas/Notificadas ({ano_sel}):", value=val_l150, key=f"txt_150_{ano_sel}_fiscal", height=100)
            
            links_150_atuais = re.findall(r'(https?://[^\s]+)', l150) if l150 else []
            if links_150_atuais:
                botoes_150 = " | ".join([f"🔗 [{u}]({u})" for u in links_150_atuais])
                st.markdown(f"**Links Ativos:** {botoes_150}")
            
        if r150 and (r150 != d150.get("valor") or l150 != d150.get("link")):
            save_resp("15.0", r150, 0.0, l150)
            if links_150_atuais:
                links_150_antigos = re.findall(r'(https?://[^\s]+)', d150.get("link", "")) if d150.get("link") else []
                if links_150_atuais != links_150_antigos:
                    modal_aviso_link("15.0", links_150_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        # 🔓 SUBQUESITOS CONDICIONAIS (Só abrem se a resposta do 15.0 for SIM)
        if r150 and "Sim" in r150:
            with st.container(border=True):
                # QUESITO 15.1 (Formato Monetário BR Automatizado com Key-Toggle)
                st.write(f"**15.1** Informe o valor total da dívida ativa cobrada de forma extrajudicial no exercício de {ano_sel}:")
                
                if f"v151_key_suffix_{ano_sel}" not in st.session_state:
                    st.session_state[f"v151_key_suffix_{ano_sel}"] = 0

                d151 = res_data.get("15.1", {"valor": "R$ 0,00", "pontos": 0, "link": ""})
                if d151 is None: d151 = {"valor": "R$ 0,00", "pontos": 0, "link": ""}
                
                val_inicial_151 = d151["valor"] if d151["valor"].startswith("R$") else f"R$ {d151['valor']}"
                sufixo_151 = st.session_state[f"v151_key_suffix_{ano_sel}"]

                v151_input = st.text_input(
                    "Informe o Valor Extrajudicial Total (R$):", 
                    value=val_inicial_151, 
                    placeholder="Ex: 85.300,50",
                    key=f"txt_151_dinamico_{ano_sel}_{sufixo_151}_fiscal"
                )

                if v151_input != d151["valor"]:
                    num_limpo = v151_input.replace("R$", "").replace(" ", "")
                    if "." in num_limpo and "," in num_limpo:
                        num_limpo = num_limpo.replace(".", "").replace(",", ".")
                    elif "," in num_limpo:
                        num_limpo = num_limpo.replace(",", ".")
                    try:
                        valor_float = float(num_limpo)
                        valor_br = f"{valor_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        v151_salvar = f"R$ {valor_br}"
                        if v151_salvar != d151["valor"]:
                            save_resp("15.1", v151_salvar, 0.0, "")
                            st.session_state[f"v151_key_suffix_{ano_sel}"] += 1
                            st.rerun()
                    except ValueError:
                        st.error("⚠️ Digite apenas números. Use vírgula para os centavos (Ex: 85300 ou 85300,00).")
                
                st.markdown("---")

                # QUESITO 15.2 (Checklist de Modalidades)
                st.write("**15.2 Assinale as modalidades de cobrança extrajudicial da dívida ativa: (Checklist)**")
                
                d152 = res_data.get("15.2", {"valor": "[]", "pontos": 0, "link": ""})
                if d152 is None: d152 = {"valor": "[]", "pontos": 0, "link": ""}
                
                try:
                    val_banco152 = d152["valor"].replace("'", '"')
                    sel152 = json.loads(val_banco152)
                    if not isinstance(sel152, list): sel152 = []
                except:
                    sel152 = []

                opcoes_152 = [
                    "Protesto Extrajudicial da CDA (Certidão da Dívida Ativa)",
                    "Parcelamento",
                    "Facilitação do Pagamento",
                    "Conciliação extrajudicial",
                    "Inclusão do nome do devedor em Cadastro (Ex. CADIN)",
                    "Inclusão do nome do devedor em serviços de proteção ao crédito",
                    "Outros"
                ]

                c5, c6 = st.columns([1, 1])
                res152 = []

                for idx, opcao in enumerate(opcoes_152):
                    target_col = c5 if idx % 2 == 0 else c6
                    with target_col:
                        pode_marcar = opcao in sel152
                        if st.checkbox(opcao, value=pode_marcar, key=f"chk_152_{idx}_{ano_sel}_fiscal"):
                            res152.append(opcao)

                if set(res152) != set(sel152):
                    save_resp("15.2", json.dumps(res152), 0.0, d152.get("link", ""))
                    st.rerun()

        bloco_comentarios("15.0", res_data, sufixo="fiscal")
       
   # =============================================================================
    # BLOCO UNIFICADO: QUESITOS 16.0 A 16.3 (Dívidas Prescritas e Provisão de Perdas)
    # =============================================================================
    with st.container(border=True):
        st.subheader("QUESITO 16.0")
        st.write(f"**No exercício de {ano_sel} houve dívidas prescritas?**")
        st.caption("ℹ️ *Considerar na prescrição ordinária apenas os valores passíveis de cobrança via judicial, conforme regulamento específico local.*")
        
        d160 = res_data.get("16.0", {"valor": None, "pontos": 0, "link": ""})
        if d160 is None: d160 = {"valor": None, "pontos": 0, "link": ""}
        
        opc160 = [
            "Sim, houve prescrição ordinária – -10 (perde 10 pontos)",
            "Sim, houve prescrição intercorrente – 00",
            f"Não houve prescrição de dívidas em {ano_sel} – 00"
        ]
        idx160 = opc160.index(d160["valor"]) if d160.get("valor") in opc160 else None
        
        c1, c2 = st.columns([1, 2])
        with c1:
            r160 = st.radio("Selecione 16.0:", opc160, index=idx160, key=f"rad_160_{ano_sel}_fiscal")
        with c2:
            val_l160 = d160.get("link", "") if d160.get("link") is not None else ""
            l160 = st.text_area(f"Link/Evidência Geral de Prescrições/Decretos ({ano_sel}):", value=val_l160, key=f"txt_160_{ano_sel}_fiscal", height=100)
            
            links_160_atuais = re.findall(r'(https?://[^\s]+)', l160) if l160 else []
            if links_160_atuais:
                botoes_160 = " | ".join([f"🔗 [{u}]({u})" for u in links_160_atuais])
                st.markdown(f"**Links Ativos:** {botoes_160}")
            
        # Lógica de pontos do 16.0: Ordinária aplica a penalidade crítica de -10 pontos
        pts160 = -10.0 if "ordinária" in (r160 or "") else 0.0
        
        if r160 and (r160 != d160.get("valor") or l160 != d160.get("link")):
            save_resp("16.0", r160, pts160, l160)
            if links_160_atuais:
                links_160_antigos = re.findall(r'(https?://[^\s]+)', d160.get("link", "")) if d160.get("link") else []
                if links_160_atuais != links_160_antigos:
                    modal_aviso_link("16.0", links_160_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        # 🔓 SUBQUESITOS CONDICIONAIS (Só abrem se houve QUALQUER tipo de prescrição)
        if r160 and "Sim" in r160:
            with st.container(border=True):
                st.write("📋 **Detalhamento dos Valores Prescritos e Provisões:**")
                
                # QUESITO 16.1 (Valor Judicial Prescrito - Formato Monetário BR)
                st.write(f"**16.1** Informe o valor da dívida ativa prescrita na execução judicial em {ano_sel}:")
                
                if f"v161_key_suffix_{ano_sel}" not in st.session_state:
                    st.session_state[f"v161_key_suffix_{ano_sel}"] = 0

                d161 = res_data.get("16.1", {"valor": "R$ 0,00", "pontos": 0, "link": ""})
                if d161 is None: d161 = {"valor": "R$ 0,00", "pontos": 0, "link": ""}
                
                val_inicial_161 = d161["valor"] if d161["valor"].startswith("R$") else f"R$ {d161['valor']}"
                sufixo_161 = st.session_state[f"v161_key_suffix_{ano_sel}"]

                v161_input = st.text_input(
                    "Informe o Valor Prescrito Judicial (R$):", 
                    value=val_inicial_161, 
                    placeholder="Ex: 50.000,00",
                    key=f"txt_161_dinamico_{ano_sel}_{sufixo_161}_fiscal"
                )

                if v161_input != d161["valor"]:
                    num_limpo = v161_input.replace("R$", "").replace(" ", "")
                    if "." in num_limpo and "," in num_limpo:
                        num_limpo = num_limpo.replace(".", "").replace(",", ".")
                    elif "," in num_limpo:
                        num_limpo = num_limpo.replace(",", ".")
                    try:
                        valor_float = float(num_limpo)
                        valor_br = f"{valor_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        v161_salvar = f"R$ {valor_br}"
                        if v161_salvar != d161["valor"]:
                            save_resp("16.1", v161_salvar, 0.0, "")
                            st.session_state[f"v161_key_suffix_{ano_sel}"] += 1
                            st.rerun()
                    except ValueError:
                        st.error("⚠️ Digite apenas números. Use vírgula para os centavos (Ex: 50000 ou 50000,00).")

                st.markdown("---")

                # QUESITO 16.2 (Valor Extrajudicial Prescrito - Formato Monetário BR)
                st.write(f"**16.2** Informe o valor da dívida ativa cobrada de forma extrajudicial prescrita no exercício de {ano_sel}:")
                
                if f"v162_key_suffix_{ano_sel}" not in st.session_state:
                    st.session_state[f"v162_key_suffix_{ano_sel}"] = 0

                d162 = res_data.get("16.2", {"valor": "R$ 0,00", "pontos": 0, "link": ""})
                if d162 is None: d162 = {"valor": "R$ 0,00", "pontos": 0, "link": ""}
                
                val_inicial_162 = d162["valor"] if d162["valor"].startswith("R$") else f"R$ {d162['valor']}"
                sufixo_162 = st.session_state[f"v162_key_suffix_{ano_sel}"]

                v162_input = st.text_input(
                    "Informe o Valor Prescrito Extrajudicial (R$):", 
                    value=val_inicial_162, 
                    placeholder="Ex: 25.400,00",
                    key=f"txt_162_dinamico_{ano_sel}_{sufixo_162}_fiscal"
                )

                if v162_input != d162["valor"]:
                    num_limpo = v162_input.replace("R$", "").replace(" ", "")
                    if "." in num_limpo and "," in num_limpo:
                        num_limpo = num_limpo.replace(".", "").replace(",", ".")
                    elif "," in num_limpo:
                        num_limpo = num_limpo.replace(",", ".")
                    try:
                        valor_float = float(num_limpo)
                        valor_br = f"{valor_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        v162_salvar = f"R$ {valor_br}"
                        if v162_salvar != d162["valor"]:
                            save_resp("16.2", v162_salvar, 0.0, "")
                            st.session_state[f"v162_key_suffix_{ano_sel}"] += 1
                            st.rerun()
                    except ValueError:
                        st.error("⚠️ Digite apenas números. Use vírgula para os centavos (Ex: 25400 ou 25400,00).")

                st.markdown("---")

                # QUESITO 16.3 (Registro Contábil da Provisão de Perdas - Lógica PCASP)
                st.write(f"**16.3** O montante da dívida ativa prescrita cobrada de forma judicial e extrajudicial estava registrado na conta de Provisão para Perdas de Dívida Ativa?")
                
                d163 = res_data.get("16.3", {"valor": None, "pontos": 0, "link": ""})
                if d163 is None: d163 = {"valor": None, "pontos": 0, "link": ""}
                
                opc163 = ["Sim – 00", "Não – -05 (perde 05 pontos)"]
                idx163 = opc163.index(d163["valor"]) if d163.get("valor") in opc163 else None
                
                c3, c4 = st.columns([1, 2])
                with c3:
                    r163 = st.radio("Selecione 16.3:", opc163, index=idx163, key=f"rad_163_{ano_sel}_fiscal")
                with c4:
                    val_l163 = d163.get("link", "") if d163.get("link") is not None else ""
                    l163 = st.text_area("Link/Evidência do Balanço Patrimonial / Razão Contábil (16.3):", value=val_l163, key=f"txt_163_{ano_sel}_fiscal", height=100)
                    
                    links_163_atuais = re.findall(r'(https?://[^\s]+)', l163) if l163 else []
                    if links_163_atuais:
                        botoes_163 = " | ".join([f"🔗 [{u}]({u})" for u in links_163_atuais])
                        st.markdown(f"**Links Ativos:** {botoes_163}")
                    
                pts163 = -5.0 if "Não" in (r163 or "") else 0.0
                
                if r163 and (r163 != d163.get("valor") or l163 != d163.get("link")):
                    save_resp("16.3", r163, pts163, l163)
                    if links_163_atuais:
                        links_163_antigos = re.findall(r'(https?://[^\s]+)', d163.get("link", "")) if d163.get("link") else []
                        if links_163_atuais != links_163_antigos:
                            modal_aviso_link("16.3", links_163_atuais)
                        else:
                            st.rerun()
                    else:
                        st.rerun()

        bloco_comentarios("16.0", res_data, sufixo="fiscal")
    # =============================================================================
    # BLOCO UNIFICADO: QUESITOS 17.0 A 17.2 (Controle de Ações Judiciais - Polo Passivo)
    # =============================================================================
    with st.container(border=True):
        st.subheader("QUESITO 17.0")
        st.write(f"**A Prefeitura possui controle das ações judiciais em que é parte (polo passivo)?**")
        
        d170 = res_data.get("17.0", {"valor": None, "pontos": 0, "link": ""})
        if d170 is None: d170 = {"valor": None, "pontos": 0, "link": ""}
        
        opc170 = [
            "Sim, de todas as ações – 00",
            "Sim, da maior parte das ações – -01 (perde 01 ponto)",
            "Sim, da menor parte das ações – -03 (perde 03 pontos)",
            "Não – -05 (perde 05 pontos)"
        ]
        idx170 = opc170.index(d170["valor"]) if d170.get("valor") in opc170 else None
        
        c1, c2 = st.columns([1, 2])
        with c1:
            r170 = st.radio("Selecione 17.0:", opc170, index=idx170, key=f"rad_170_{ano_sel}_fiscal")
        with c2:
            val_l170 = d170.get("link", "") if d170.get("link") is not None else ""
            l170 = st.text_area(f"Link/Evidência do Sistema ou Relatório de Controle Legal ({ano_sel}):", value=val_l170, key=f"txt_170_{ano_sel}_fiscal", height=100)
            
            # Extração e renderização de links ativos
            links_170_atuais = re.findall(r'(https?://[^\s]+)', l170) if l170 else []
            if links_170_atuais:
                botoes_170 = " | ".join([f"🔗 [{u}]({u})" for u in links_170_atuais])
                st.markdown(f"**Links Ativos:** {botoes_170}")
            
        # Lógica rigorosa de atribuição de pontos/penalidades do 17.0
        if r170:
            if "todas" in r170:
                pts170 = 0.0
            elif "maior" in r170:
                pts170 = -1.0
            elif "menor" in r170:
                pts170 = -3.0
            else:
                pts170 = -5.0
        else:
            pts170 = 0.0

        if r170 and (r170 != d170.get("valor") or l170 != d170.get("link")):
            save_resp("17.0", r170, pts170, l170)
            if links_170_atuais:
                links_170_antigos = re.findall(r'(https?://[^\s]+)', d170.get("link", "")) if d170.get("link") else []
                if links_170_atuais != links_170_antigos:
                    modal_aviso_link("17.0", links_170_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        # 🔓 SUBQUESITOS CONDICIONAIS (Ficam visíveis se houver qualquer nível de controle ou resposta)
        if r170 and "Não" not in r170:
            with st.container(border=True):
                # QUESITO 17.1 (Campo Descritivo)
                st.write("**17.1** Descreva de que forma é realizado o controle das ações judiciais em que é parte (polo passivo):")
                
                d171 = res_data.get("17.1", {"valor": "", "pontos": 0, "link": ""})
                if d171 is None: d171 = {"valor": "", "pontos": 0, "link": ""}
                
                v171_text = st.text_area(
                    "Descreva a metodologia/sistema de controle:",
                    value=d171.get("valor", ""),
                    placeholder="Ex: O controle é realizado via sistema informatizado da Procuradoria Geral do Município...",
                    key=f"txt_171_desc_{ano_sel}_fiscal",
                    height=120
                )
                if v171_text != d171.get("valor"):
                    save_resp("17.1", v171_text, 0.0, "")
                    st.rerun()

                st.markdown("---")

                # QUESITO 17.2 (Valor Atualizado - Formato Monetário BR com Key-Toggle)
                st.write(f"**17.2** Qual o valor atualizado em 31/12/{ano_sel} de todas as ações judiciais em que é parte (polo passivo)?")
                
                if f"v172_key_suffix_{ano_sel}" not in st.session_state:
                    st.session_state[f"v172_key_suffix_{ano_sel}"] = 0

                d172 = res_data.get("17.2", {"valor": "R$ 0,00", "pontos": 0, "link": ""})
                if d172 is None: d172 = {"valor": "R$ 0,00", "pontos": 0, "link": ""}
                
                val_inicial_172 = d172["valor"] if d172["valor"].startswith("R$") else f"R$ {d172['valor']}"
                sufixo_172 = st.session_state[f"v172_key_suffix_{ano_sel}"]

                v172_input = st.text_input(
                    "Informe o Valor Total do Polo Passivo (R$):", 
                    value=val_inicial_172, 
                    placeholder="Ex: 1.250.000,00",
                    key=f"txt_172_dinamico_{ano_sel}_{sufixo_172}_fiscal"
                )

                if v172_input != d172["valor"]:
                    num_limpo = v172_input.replace("R$", "").replace(" ", "")
                    if "." in num_limpo and "," in num_limpo:
                        num_limpo = num_limpo.replace(".", "").replace(",", ".")
                    elif "," in num_limpo:
                        num_limpo = num_limpo.replace(",", ".")
                    try:
                        valor_float = float(num_limpo)
                        valor_br = f"{valor_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        v172_salvar = f"R$ {valor_br}"
                        if v172_salvar != d172["valor"]:
                            save_resp("17.2", v172_salvar, 0.0, "")
                            st.session_state[f"v172_key_suffix_{ano_sel}"] += 1
                            st.rerun()
                    except ValueError:
                        st.error("⚠️ Digite apenas números. Use vírgula para identificar os centavos (Ex: 1250000 ou 1250000,00).")

        bloco_comentarios("17.0", res_data, sufixo="fiscal")

    # -------------------------------------------------------------------------
    # SEÇÃO 7: TRANSPARÊNCIA E PREVIDÊNCIA
    # -------------------------------------------------------------------------
    st.markdown("### 7. Transparência na Gestão Fiscal") 

    # =============================================================================
    # BLOCO UNIFICADO: QUESITOS 18.0 A 18.1 (Transparência na Gestão Fiscal)
    # =============================================================================
    with st.container(border=True):
        st.subheader("QUESITO 18.0")
        st.write(f"**Os dados relativos à transparência na gestão fiscal são divulgados na página eletrônica do Município em {ano_sel}?**")
        
        d180 = res_data.get("18.0", {"valor": None, "pontos": 0, "link": ""})
        if d180 is None: d180 = {"valor": None, "pontos": 0, "link": ""}
        
        opc180 = ["Sim", "Não"]
        idx180 = opc180.index(d180["valor"]) if d180.get("valor") in opc180 else None
        
        c1, c2 = st.columns([1, 2])
        with c1:
            r180 = st.radio("Selecione 18.0:", opc180, index=idx180, key=f"rad_180_{ano_sel}_fiscal")
        with c2:
            val_l180 = d180.get("link", "") if d180.get("link") is not None else ""
            l180 = st.text_area(f"Link do Portal da Transparência / Página Eletrônica ({ano_sel}):", value=val_l180, key=f"txt_180_{ano_sel}_fiscal", height=100)
            
            # Varredura e renderização dinâmica de links ativos
            links_180_atuais = re.findall(r'(https?://[^\s]+)', l180) if l180 else []
            if links_180_atuais:
                botoes_180 = " | ".join([f"🔗 [{u}]({u})" for u in links_180_atuais])
                st.markdown(f"**Links Ativos:** {botoes_180}")
                
        if r180 and (r180 != d180.get("valor") or l180 != d180.get("link")):
            save_resp("18.0", r180, 0.0, l180)
            if links_180_atuais:
                links_180_antigos = re.findall(r'(https?://[^\s]+)', d180.get("link", "")) if d180.get("link") else []
                if links_180_atuais != links_180_antigos:
                    modal_aviso_link("18.0", links_180_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        # 🔓 SUBQUESITOS CONDICIONAIS (Só abrem se a resposta do 18.0 for SIM)
        if r180 and "Sim" in r180:
            with st.container(border=True):
                # QUESITO 18.1 - Checklist de Itens Divulgados (2,5 pontos por item)
                st.write("**18.1 Assinale os itens que são divulgados na página eletrônica do Município: (Checklist)**")
                
                d181 = res_data.get("18.1", {"valor": "[]", "pontos": 0, "link": ""})
                if d181 is None: d181 = {"valor": "[]", "pontos": 0, "link": ""}
                
                try:
                    val_banco181 = d181["valor"].replace("'", '"')
                    sel181 = json.loads(val_banco181)
                    if not isinstance(sel181, list): sel181 = []
                except:
                    sel181 = []

                opcoes_181 = {
                    "PPA, LDO e LOA – 2,5": 2.5,
                    "Balanços de exercício – 2,5": 2.5,
                    "Prestação de contas do ano anterior – 2,5": 2.5,
                    "Parecer prévio do TCE – 2,5": 2.5,
                    "Relatório de Gestão Fiscal (RGF) – 2,5": 2.5,
                    "Relatório Resumido da Execução Orçamentária (RREO) – 2,5": 2.5
                }

                c3, c4 = st.columns([1, 1])
                res181 = []
                pts_acumulados_181 = 0.0

                for idx, (opcao, pontos_item) in enumerate(opcoes_181.items()):
                    target_col = c3 if idx % 2 == 0 else c4
                    with target_col:
                        pode_marcar = opcao in sel181
                        if st.checkbox(opcao, value=pode_marcar, key=f"chk_181_{idx}_{ano_sel}_fiscal"):
                            res181.append(opcao)
                            pts_acumulados_181 += pontos_item

                if set(res181) != set(sel181):
                    save_resp("18.1", json.dumps(res181), float(pts_acumulados_181), d181.get("link", ""))
                    st.rerun()

        bloco_comentarios("18.0", res_data, sufixo="fiscal")

    # =============================================================================
    # BLOCO UNIFICADO: QUESITOS 19.0 A 19.1 (Divulgação de Receitas em Tempo Real)
    # =============================================================================
    with st.container(border=True):
        st.subheader("QUESITO 19.0")
        st.write(f"**Houve divulgação das receitas arrecadadas em tempo real em {ano_sel}?**")
        st.caption("ℹ️ *Tempo real é considerado até o 1º dia útil que sucede o do registro contábil.*")
        
        d190 = res_data.get("19.0", {"valor": None, "pontos": 0, "link": ""})
        if d190 is None: d190 = {"valor": None, "pontos": 0, "link": ""}
        
        opc190 = ["Sim – 03", "Não – 00"]
        idx190 = opc190.index(d190["valor"]) if d190.get("valor") in opc190 else None
        
        c1, c2 = st.columns([1, 2])
        with c1:
            r190 = st.radio("Selecione 19.0:", opc190, index=idx190, key=f"rad_190_{ano_sel}_fiscal")
        with c2:
            val_l190 = d190.get("link", "") if d190.get("link") is not None else ""
            l190 = st.text_area(f"Link do Portal da Transparência / Tempo Real ({ano_sel}):", value=val_l190, key=f"txt_190_{ano_sel}_fiscal", height=100)
            
            # Varredura e renderização dinâmica de links ativos
            links_190_atuais = re.findall(r'(https?://[^\s]+)', l190) if l190 else []
            if links_190_atuais:
                botoes_190 = " | ".join([f"🔗 [{u}]({u})" for u in links_190_atuais])
                st.markdown(f"**Links Ativos:** {botoes_190}")
                
        pts190 = 3.0 if "Sim" in (r190 or "") else 0.0
        
        if r190 and (r190 != d190["valor"] or l190 != d190["link"]):
            save_resp("19.0", r190, pts190, l190)
            if links_190_atuais:
                links_190_antigos = re.findall(r'(https?://[^\s]+)', d190.get("link", "")) if d190.get("link") else []
                if links_190_atuais != links_190_antigos:
                    modal_aviso_link("19.0", links_190_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        # 🔓 SUBQUESITOS CONDICIONAIS (Só abrem se a resposta do 19.0 for SIM)
        if r190 and "Sim" in r190:
            with st.container(border=True):
                # QUESITO 19.1 - Checklist de Itens da Receita (0,3 pontos por item)
                st.write("**19.1 Assinale os itens da receita divulgados em tempo real: (Checklist)**")
                
                d191 = res_data.get("19.1", {"valor": "[]", "pontos": 0, "link": ""})
                if d191 is None: d191 = {"valor": "[]", "pontos": 0, "link": ""}
                
                try:
                    val_banco191 = d191["valor"].replace("'", '"')
                    sel191 = json.loads(val_banco191)
                    if not isinstance(sel191, list): sel191 = []
                except:
                    sel191 = []

                opcoes_191 = {
                    "Categoria econômica – 0,3": 0.3,
                    "Origem – 0,3": 0.3,
                    "Espécie – 0,3": 0.3,
                    "Desdobramento para identificação de peculiaridades – 0,3": 0.3,
                    "Tipo – 0,3": 0.3,
                    "Valor previsto – 0,3": 0.3,
                    "Valor arrecadado – 0,3": 0.3,
                    "Data de arrecadação – 0,3": 0.3,
                    "Recursos extraordinários – 0,3": 0.3,
                    "Outros – 0,3": 0.3
                }

                c3, c4 = st.columns([1, 1])
                res191 = []
                pts_acumulados_191 = 0.0

                for idx, (opcao, pontos_item) in enumerate(opcoes_191.items()):
                    target_col = c3 if idx % 2 == 0 else c4
                    with target_col:
                        pode_marcar = opcao in sel191
                        if st.checkbox(opcao, value=pode_marcar, key=f"chk_191_{idx}_{ano_sel}_fiscal"):
                            res191.append(opcao)
                            pts_acumulados_191 += pontos_item

                if set(res191) != set(sel191):
                    save_resp("19.1", json.dumps(res191), float(pts_acumulados_191), d191.get("link", ""))
                    st.rerun()

        bloco_comentarios("19.0", res_data, sufixo="fiscal")

    # =============================================================================
    # BLOCO UNIFICADO: QUESITOS 20.0 A 20.1 (Divulgação de Despesas em Tempo Real)
    # =============================================================================
    with st.container(border=True):
        st.subheader("QUESITO 20.0")
        st.write(f"**Houve divulgação das despesas executadas em tempo real em {ano_sel}?**")
        st.caption("ℹ️ *Tempo real é considerado até o 1º dia útil que sucede o do registro contábil.*")
        
        d200 = res_data.get("20.0", {"valor": None, "pontos": 0, "link": ""})
        if d200 is None: d200 = {"valor": None, "pontos": 0, "link": ""}
        
        opc200 = ["Sim – 03", "Não – 00"]
        idx200 = opc200.index(d200["valor"]) if d200.get("valor") in opc200 else None
        
        c1, c2 = st.columns([1, 2])
        with c1:
            r200 = st.radio("Selecione 20.0:", opc200, index=idx200, key=f"rad_200_{ano_sel}_fiscal")
        with c2:
            val_l200 = d200.get("link", "") if d200.get("link") is not None else ""
            l200 = st.text_area(f"Link do Portal da Transparência / Despesas Tempo Real ({ano_sel}):", value=val_l200, key=f"txt_200_{ano_sel}_fiscal", height=100)
            
            # Varredura e renderização dinâmica de links ativos
            links_200_atuais = re.findall(r'(https?://[^\s]+)', l200) if l200 else []
            if links_200_atuais:
                botoes_200 = " | ".join([f"🔗 [{u}]({u})" for u in links_200_atuais])
                st.markdown(f"**Links Ativos:** {botoes_200}")
                
        pts200 = 3.0 if "Sim" in (r200 or "") else 0.0
        if r200 and (r200 != d200["valor"] or l200 != d200["link"]):
            save_resp("20.0", r200, pts200, l200)
            if links_200_atuais:
                links_200_antigos = re.findall(r'(https?://[^\s]+)', d200.get("link", "")) if d200.get("link") else []
                if links_200_atuais != links_200_antigos:
                    modal_aviso_link("20.0", links_200_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        # 🔓 SUBQUESITOS CONDICIONAIS (Só abrem se a resposta do 20.0 for SIM)
        if r200 and "Sim" in r200:
            with st.container(border=True):
                # QUESITO 20.1 - Checklist de Itens da Despesa (Pesos variados: 0,3 e 0,6)
                st.write("**20.1 Assinale os itens das despesas divulgados em tempo real: (Checklist)**")
                
                d201 = res_data.get("20.1", {"valor": "[]", "pontos": 0, "link": ""})
                if d201 is None: d201 = {"valor": "[]", "pontos": 0, "link": ""}
                
                try:
                    val_banco201 = d201["valor"].replace("'", '"')
                    sel201 = json.loads(val_banco201)
                    if not isinstance(sel201, list): sel201 = []
                except:
                    sel201 = []

                # Dicionário mapeando as opções com suas respectivas pontuações (Atenção para Elemento e Subelemento)
                opcoes_201 = {
                    "Valor empenhado – 0,3": 0.3,
                    "Valor liquidado – 0,3": 0.3,
                    "Valor pago – 0,3": 0.3,
                    "Número do processo da execução - nº empenho – 0,3": 0.3,
                    "Unidade Orçamentária - UO – 0,3": 0.3,
                    "Função – 0,3": 0.3,
                    "Subfunção – 0,3": 0.3,
                    "Categoria Econômica da despesa – 0,3": 0.3,
                    "Grupo de Natureza da despesa – 0,3": 0.3,
                    "Modalidade de aplicação – 0,3": 0.3,
                    "Elemento – 0,6": 0.6,
                    "Subelemento – 0,6": 0.6,
                    "Fonte de recurso – 0,3": 0.3,
                    "Favorecido do pagamento – 0,3": 0.3,
                    "Modalidade da licitação – 0,3": 0.3,
                    "Número do processo licitatório – 0,3": 0.3,
                    "Bem fornecido ou serviço prestado – 0,3": 0.3,
                    "Outros – 0,3": 0.3
                }

                c3, c4 = st.columns([1, 1])
                res201 = []
                pts_acumulados_201 = 0.0

                # Distribui os checkboxes de forma organizada nas duas colunas e soma os pontos dinamicamente
                for idx, (opcao, pontos_item) in enumerate(opcoes_201.items()):
                    target_col = c3 if idx % 2 == 0 else c4
                    with target_col:
                        pode_marcar = opcao in sel201
                        if st.checkbox(opcao, value=pode_marcar, key=f"chk_201_{idx}_{ano_sel}_fiscal"):
                            res201.append(opcao)
                            pts_acumulados_201 += pontos_item

                # Gravação passiva balanceando o estado da lista selecionada e os pontos totais apurados
                if set(res201) != set(sel201):
                    save_resp("20.1", json.dumps(res201), float(pts_acumulados_201), d201.get("link", ""))
                    st.rerun()

        bloco_comentarios("20.0", res_data, sufixo="fiscal")

    # =============================================================================
    # BLOCO UNIFICADO: QUESITOS 21.0 A 22.1 (Remunerações, Diárias e Passagens)
    # =============================================================================
    
    # --- QUESITOS 21.0 e 21.1 (Remuneração Individualizada) ---
    with st.container(border=True):
        st.subheader("QUESITO 21.0")
        st.write(f"**Houve divulgação de remuneração individualizada por nome do agente público, contendo dados sobre os vencimentos, descontos, indenizações e valor líquido em {ano_sel}?**")
        
        d210 = res_data.get("21.0", {"valor": None, "pontos": 0, "link": ""})
        if d210 is None: d210 = {"valor": None, "pontos": 0, "link": ""}
        
        opc210 = ["Sim – 03", "Não – 00"]
        idx210 = opc210.index(d210["valor"]) if d210.get("valor") in opc210 else None
        
        c1, c2 = st.columns([1, 2])
        with c1:
            r210 = st.radio("Selecione 21.0:", opc210, index=idx210, key=f"rad_210_{ano_sel}_fiscal")
        with c2:
            val_l210 = d210.get("link", "") if d210.get("link") is not None else ""
            l210 = st.text_area(f"Link Geral do Portal de Transparência / Pessoal ({ano_sel}):", value=val_l210, key=f"txt_210_{ano_sel}_fiscal", height=100)
            
            # Varredura e renderização dinâmica de links ativos
            links_210_atuais = re.findall(r'(https?://[^\s]+)', l210) if l210 else []
            if links_210_atuais:
                botoes_210 = " | ".join([f"🔗 [{u}]({u})" for u in links_210_atuais])
                st.markdown(f"**Links Ativos:** {botoes_210}")
                
        pts210 = 3.0 if "Sim" in (r210 or "") else 0.0
        if r210 and (r210 != d210.get("valor") or l210 != d210.get("link")):
            save_resp("21.0", r210, pts210, l210)
            if links_210_atuais:
                links_210_antigos = re.findall(r'(https?://[^\s]+)', d210.get("link", "")) if d210.get("link") else []
                if links_210_atuais != links_210_antigos:
                    modal_aviso_link("21.0", links_210_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        # 🔓 SUBQUESITO CONDICIONAL 21.1 (Fórmula XYZ)
        if r210 and "Sim" in r210:
            with st.container(border=True):
                st.write("**21.1** Informe a página eletrônica (link na internet) de divulgação da remuneração individualizada por nome do agente público:")
                st.caption("ℹ️ *Se não estiver disponível na internet, inserir no campo o texto **XYZ***")
                
                d211 = res_data.get("21.1", {"valor": "", "pontos": 0, "link": ""})
                if d211 is None: d211 = {"valor": "", "pontos": 0, "link": ""}
                
                val_v211 = d211.get("valor", "") if d211.get("valor") is not None else ""
                v211 = st.text_input("Link de divulgação da folha de pagamento (ou XYZ):", value=val_v211, key=f"txt_211_val_{ano_sel}_fiscal")
                
                # Varredura e renderização dinâmica de links no valor do input (Subquesito tipo link)
                links_211_atuais = re.findall(r'(https?://[^\s]+)', v211) if v211 else []
                if links_211_atuais:
                    botoes_211 = " | ".join([f"🔗 [{u}]({u})" for u in links_211_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_211}")
                
                if v211 != d211.get("valor"):
                    save_resp("21.1", v211, 0.0, "")
                    if links_211_atuais:
                        links_211_antigos = re.findall(r'(https?://[^\s]+)', d211.get("valor", "")) if d211.get("valor") else []
                        if links_211_atuais != links_211_antigos:
                            modal_aviso_link("21.1", links_211_atuais)
                        else:
                            st.rerun()
                    else:
                        st.rerun()

        bloco_comentarios("21.0", res_data, sufixo="fiscal")


    # --- QUESITOS 22.0 e 22.1 (Diárias e Passagens) ---
    with st.container(border=True):
        st.subheader("QUESITO 22.0")
        st.write(f"**Houve divulgação de diárias e passagens por nome de favorecido e constando data, destino, cargo e motivo de viagem em {ano_sel}?**")
        
        d220 = res_data.get("22.0", {"valor": None, "pontos": 0, "link": ""})
        if d220 is None: d220 = {"valor": None, "pontos": 0, "link": ""}
        
        opc220 = ["Sim – 03", "Não – 00"]
        idx220 = opc220.index(d220["valor"]) if d220.get("valor") in opc220 else None
        
        c3, c4 = st.columns([1, 2])
        with c3:
            r220 = st.radio("Selecione 22.0:", opc220, index=idx220, key=f"rad_220_{ano_sel}_fiscal")
        with c4:
            val_l220 = d220.get("link", "") if d220.get("link") is not None else ""
            l220 = st.text_area(f"Link Geral do Portal de Transparência / Diárias ({ano_sel}):", value=val_l220, key=f"txt_220_{ano_sel}_fiscal", height=100)
            
            # Varredura e renderização dinâmica de links ativos
            links_220_atuais = re.findall(r'(https?://[^\s]+)', l220) if l220 else []
            if links_220_atuais:
                botoes_220 = " | ".join([f"🔗 [{u}]({u})" for u in links_220_atuais])
                st.markdown(f"**Links Ativos:** {botoes_220}")
                
        pts220 = 3.0 if "Sim" in (r220 or "") else 0.0
        if r220 and (r220 != d220["valor"] or l220 != d220["link"]):
            save_resp("22.0", r220, pts220, l220)
            if links_220_atuais:
                links_220_antigos = re.findall(r'(https?://[^\s]+)', d220.get("link", "")) if d220.get("link") else []
                if links_220_atuais != links_220_antigos:
                    modal_aviso_link("22.0", links_220_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        # 🔓 SUBQUESITO CONDICIONAIS 22.1 (Fórmula XYZ)
        if r220 and "Sim" in r220:
            with st.container(border=True):
                st.write("**22.1** Informe a página eletrônica (link na internet) de divulgação de diárias e passagens:")
                st.caption("ℹ️ *Se não estiver disponível na internet, inserir no campo o texto **XYZ***")
                
                d221 = res_data.get("22.1", {"valor": "", "pontos": 0, "link": ""})
                if d221 is None: d221 = {"valor": "", "pontos": 0, "link": ""}
                
                val_v221 = d221.get("valor", "") if d221.get("valor") is not None else ""
                v221 = st.text_input("Link de divulgação das diárias e passagens (ou XYZ):", value=val_v221, key=f"txt_221_val_{ano_sel}_fiscal")
                
                # Varredura e renderização dinâmica de links no valor do input
                links_221_atuais = re.findall(r'(https?://[^\s]+)', v221) if v221 else []
                if links_221_atuais:
                    botoes_221 = " | ".join([f"🔗 [{u}]({u})" for u in links_221_atuais])
                    st.markdown(f"**Links Ativos:** {botoes_221}")
                
                if v221 != d221["valor"]:
                    save_resp("22.1", v221, 0.0, "")
                    if links_221_atuais:
                        links_221_antigos = re.findall(r'(https?://[^\s]+)', d221.get("valor", "")) if d221.get("valor") else []
                        if links_221_atuais != links_221_antigos:
                            modal_aviso_link("22.1", links_221_atuais)
                        else:
                            st.rerun()
                    else:
                        st.rerun()

        bloco_comentarios("22.0", res_data, sufixo="fiscal")

    # =============================================================================
    # BLOCO UNIFICADO: QUESITOS 23.0 A 24.1 (Encargos Sociais e Parcelamentos - RGPS)
    # =============================================================================
    
    # --- QUESITO 23.0 (Repasses Correntes RGPS) ---
    with st.container(border=True):
        st.subheader("QUESITO 23.0")
        st.write(f"**Os repasses para o Regime Geral de Previdência Social (RGPS) da competência de {ano_sel} foram realizados em qual prazo?**")
        
        d230 = res_data.get("23.0", {"valor": None, "pontos": 0.0, "link": ""})
        if d230 is None: d230 = {"valor": None, "pontos": 0.0, "link": ""}
        
        opc230 = [
            "Todos os repasses foram dentro do prazo legal – 00",
            "A maior parte dos repasses recolhidos até 30 dias após o vencimento – -04 (perde 04 pontos)",
            "A maior parte dos repasses recolhidos de 31 a 90 dias do vencimento – -15 (perde 15 pontos)",
            "A maior parte dos repasses recolhidos acima de 90 dias do vencimento – -21 (perde 21 pontos)",
            "Os repasses não foram realizados – -30 (perde 30 pontos)"
        ]
        idx230 = opc230.index(d230["valor"]) if d230.get("valor") in opc230 else None
        
        c1, c2 = st.columns([1, 2])
        with c1:
            r230 = st.radio("Selecione 23.0:", opc230, index=idx230, key=f"rad_230_{ano_sel}_fiscal")
        with c2:
            val_l230 = d230.get("link", "") if d230.get("link") is not None else ""
            l230 = st.text_area(f"Link/Evidência de Comprovantes de Repasse / GFIP / GPS ({ano_sel}):", value=val_l230, key=f"txt_230_{ano_sel}_fiscal", height=100)
            
            # Varredura e renderização dinâmica de links ativos
            links_230_atuais = re.findall(r'(https?://[^\s]+)', l230) if l230 else []
            if links_230_atuais:
                botoes_230 = " | ".join([f"🔗 [{u}]({u})" for u in links_230_atuais])
                st.markdown(f"**Links Ativos:** {botoes_230}")
            
        # Lógica rigorosa de penalidades para o 23.0
        if r230:
            if "dentro do prazo" in r230: pts230 = 0.0
            elif "até 30 dias" in r230: pts230 = -4.0
            elif "31 a 90 dias" in r230: pts230 = -15.0
            elif "acima de 90 dias" in r230: pts230 = -21.0
            else: pts230 = -30.0
        else:
            pts230 = 0.0

        if r230 and (r230 != d230.get("valor") or l230 != d230.get("link")):
            save_resp("23.0", r230, float(pts230), l230)
            if links_230_atuais:
                links_230_antigos = re.findall(r'(https?://[^\s]+)', d230.get("link", "")) if d230.get("link") else []
                if links_230_atuais != links_230_antigos:
                    modal_aviso_link("23.0", links_230_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        bloco_comentarios("23.0", res_data, sufixo="fiscal")


    # --- QUESITOS 24.0 e 24.1 (Parcelamentos RGPS) ---
    with st.container(border=True):
        st.subheader("QUESITO 24.0")
        st.write(f"**A Prefeitura aderiu a algum parcelamento de encargos sociais (Regime Geral de Previdência Social - RGPS)?**")
        
        d240 = res_data.get("24.0", {"valor": None, "pontos": 0.0, "link": ""})
        if d240 is None: d240 = {"valor": None, "pontos": 0.0, "link": ""}
        
        opc240 = ["Sim", "Não"]
        idx240 = opc240.index(d240["valor"]) if d240.get("valor") in opc240 else None
        
        c3, c4 = st.columns([1, 2])
        with c3:
            r240 = st.radio("Selecione 24.0:", opc240, index=idx240, key=f"rad_240_{ano_sel}_fiscal")
        with c4:
            val_l240 = d240.get("link", "") if d240.get("link") is not None else ""
            l240 = st.text_area(f"Link/Evidência do Termo de Parcelamento / Extrato da RFB ({ano_sel}):", value=val_l240, key=f"txt_240_{ano_sel}_fiscal", height=100)
            
            # Varredura e renderização dinâmica de links ativos
            links_240_atuais = re.findall(r'(https?://[^\s]+)', l240) if l240 else []
            if links_240_atuais:
                botoes_240 = " | ".join([f"🔗 [{u}]({u})" for u in links_240_atuais])
                st.markdown(f"**Links Ativos:** {botoes_240}")
            
        if r240 and (r240 != d240.get("valor") or l240 != d240.get("link")):
            save_resp("24.0", r240, 0.0, l240)
            if links_240_atuais:
                links_240_antigos = re.findall(r'(https?://[^\s]+)', d240.get("link", "")) if d240.get("link") else []
                if links_240_atuais != links_240_antigos:
                    modal_aviso_link("24.0", links_240_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        # 🔓 SUBQUESITO CONDICIONAL 24.1 (Só abre se houver parcelamento ativo)
        if r240 and "Sim" in r240:
            with st.container(border=True):
                st.write(f"**24.1** As parcelas referentes ao parcelamento para o Regime Geral de Previdência Social (RGPS) com vencimento em {ano_sel} foram realizados em qual prazo?")
                
                d241 = res_data.get("24.1", {"valor": None, "pontos": 0.0, "link": ""})
                if d241 is None: d241 = {"valor": None, "pontos": 0.0, "link": ""}
                
                opc241 = [
                    "Todas as parcelas foram recolhidas dentro do prazo legal – 00",
                    "A maior parte das parcelas recolhidas até 30 dias após o vencimento – -04 (perde 04 pontos)",
                    "A maior parte das parcelas recolhidas de 31 a 90 dias do vencimento – -15 (perde 15 pontos)",
                    "A maior parte das parcelas recolhidas acima de 90 dias do vencimento – -21 (perde 21 pontos)",
                    "As parcelas não foram recolhidas – -30 (perde 30 pontos)"
                ]
                idx241 = opc241.index(d241["valor"]) if d241.get("valor") in opc241 else None
                
                r241 = st.radio("Selecione 24.1:", opc241, index=idx241, key=f"rad_241_{ano_sel}_fiscal")
                
                # Lógica rigorosa de penalidades para o 24.1
                if r241:
                    if "dentro do prazo" in r241: pts241 = 0.0
                    elif "até 30 dias" in r241: pts241 = -4.0
                    elif "31 a 90 dias" in r241: pts241 = -15.0
                    elif "acima de 90 dias" in r241: pts241 = -21.0
                    else: pts241 = -30.0
                else:
                    pts241 = 0.0

                if r241 and r241 != d241.get("valor"):
                    save_resp("24.1", r241, float(pts241), "")
                    st.rerun()

        bloco_comentarios("24.0", res_data, sufixo="fiscal")

# =============================================================================
    # BLOCO UNIFICADO: QUESITOS 25.0 A 26.0 (Compensações RFB e Impressões Finais)
    # =============================================================================
    
    # --- QUESITOS 25.0 e 25.1 (Compensação de Encargos Sociais) ---
    with st.container(border=True):
        st.subheader("QUESITO 25.0")
        st.write(f"**O Município efetuou, no exercício de {ano_sel}, compensação de encargos sociais junto à Receita Federal do Brasil?**")
        
        d250 = res_data.get("25.0", {"valor": None, "pontos": 0.0, "link": ""})
        if d250 is None: d250 = {"valor": None, "pontos": 0.0, "link": ""}
        
        opc250 = ["Sim", "Não"]
        idx250 = opc250.index(d250["valor"]) if d250.get("valor") in opc250 else None
        
        c1, c2 = st.columns([1, 2])
        with c1:
            r250 = st.radio("Selecione 25.0:", opc250, index=idx250, key=f"rad_250_{ano_sel}_fiscal")
        with c2:
            val_l250 = d250.get("link", "") if d250.get("link") is not None else ""
            l250 = st.text_area(f"Link/Evidência da Declaração de Compensação (PER/DCOMP) ({ano_sel}):", value=val_l250, key=f"txt_250_{ano_sel}_fiscal", height=100)
            
            # Varredura e renderização dinâmica de links ativos
            links_250_atuais = re.findall(r'(https?://[^\s]+)', l250) if l250 else []
            if links_250_atuais:
                botoes_250 = " | ".join([f"🔗 [{u}]({u})" for u in links_250_atuais])
                st.markdown(f"**Links Ativos:** {botoes_250}")
                
        if r250 and (r250 != d250.get("valor") or l250 != d250.get("link")):
            save_resp("25.0", r250, 0.0, l250)
            if links_250_atuais:
                links_250_antigos = re.findall(r'(https?://[^\s]+)', d250.get("link", "")) if d250.get("link") else []
                if links_250_atuais != links_250_antigos:
                    modal_aviso_link("25.0", links_250_atuais)
                else:
                    st.rerun()
            else:
                st.rerun()

        # 🔓 SUBQUESITO CONDICIONAL 25.1 (Penalidade gravíssima por falta de lastro formal)
        if r250 and "Sim" in r250:
            with st.container(border=True):
                st.write("**25.1** Houve autorização formal administrativa da Receita Federal do Brasil (RFB) ou decisão judicial para realizar as compensações?")
                
                d251 = res_data.get("25.1", {"valor": None, "pontos": 0.0, "link": ""})
                if d251 is None: d251 = {"valor": None, "pontos": 0.0, "link": ""}
                
                opc251 = [
                    "Sim – 00",
                    "Não – -25 (perde 25 pontos)"
                ]
                idx251 = opc251.index(d251["valor"]) if d251.get("valor") in opc251 else None
                
                r251 = st.radio("Selecione 25.1:", opc251, index=idx251, key=f"rad_251_{ano_sel}_fiscal")
                
                # Mapeamento rigoroso da perda de 25 pontos
                pts251 = 0.0 if (r251 and "Sim" in r251) else (-25.0 if r251 else 0.0)
                
                if r251 and r251 != d251.get("valor"):
                    save_resp("25.1", r251, float(pts251), "")
                    st.rerun()

        bloco_comentarios("25.0", res_data, sufixo="fiscal")


    # --- QUESITO 26.0 (Considerações Finais / Espaço de Ouvidoria do Sistema) ---
    with st.container(border=True):
        st.subheader("QUESITO 26.0")
        st.write("**Gostaria de registrar suas impressões, comentários e sugestões a respeito do presente questionário?**")
        st.caption("ℹ️ *Utilize o espaço abaixo de forma livre para documentar observações sobre a usabilidade, críticas ou pontos de melhoria.*")
        
        d260 = res_data.get("26.0", {"valor": "", "pontos": 0.0, "link": ""})
        if d260 is None: d260 = {"valor": "", "pontos": 0.0, "link": ""}
        
        val_v260 = d260.get("valor", "") if d260.get("valor") is not None else ""
        v260 = st.text_area("Impressões, comentários e sugestões:", value=val_v260, key=f"txt_260_val_{ano_sel}_fiscal", height=180)
        
        if v260 != d260.get("valor"):
            save_resp("26.0", v260, 0.0, "")
            st.rerun()
    # -------------------------------------------------------------------------
    # SEÇÃO 8: INDICADORES FINANCEIROS (F1 A F18)
    # -------------------------------------------------------------------------
    st.markdown('<div class="section-header"><h3>8. Indicadores Financeiros (AUDESP)</h3></div>', unsafe_allow_html=True)

    # F1 • Análise da Receita com Formatação BR, Critérios e Key-Toggle
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("F1 • Análise da Receita (Execução Orçamentária) – Resultado Consolidado")
    st.write("**Divisão da receita arrecadada pela receita prevista atualizada (O / P = Q)**")
    
    # Tabela Oficial de Parâmetros e Pontuações do Indicador
    st.markdown("""
    | Resultado de $Q$ | Pontuação do Indicador |
    | :--- | :--- |
    | Maior ou igual a 1,5 | 0 |
    | Maior que 1,15 e menor que 1,5 | Graduação entre 75 e 0 |
    | Maior ou igual a 0,85 e menor ou igual a 1,15 | 75 |
    | Maior que 0,5 e menor que 0,85 | Graduação entre 0 e 75 |
    | Menor ou igual a 0,5 | 0 |
    """)
    
    # 📝 Inclusão das memórias matemáticas oficiais solicitadas
    st.markdown("""
    <div style="background-color: #f8fafc; padding: 12px; border-radius: 4px; border-left: 3px solid #64748b; margin-bottom: 15px;">
        <p style="margin-bottom: 8px; font-size: 13px;">📊 <b>Regras de Distribuição Proporcional nos Intervalos:</b></p>
        <ul style="font-size: 13px; margin-left: 15px; padding-left: 0px;">
            <li><b>Para resultados maiores que 1,15 e menores que 1,5:</b> A graduação será distribuída igualitariamente no intervalo. Matematicamente, demonstrado por: <br><code style="background-color: #e2e8f0; padding: 2px 5px;">((Q – 1,5) * (-1) / 0,35) * 75</code> <br><i>Exemplo: se Q = 1,25, a nota do indicador será 53,57 pontos.</i></li>
            <li style="margin-top: 8px;"><b>Para resultados maiores que 0,5 e menores que 0,85:</b> A graduação será distribuída igualitariamente no intervalo. Matematicamente, demonstrado por: <br><code style="background-color: #e2e8f0; padding: 2px 5px;">((Q – 0,5) / 0,35) * 75</code> <br><i>Exemplo: se Q = 0,75, a nota do indicador será 53,57 pontos.</i></li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    # Inicializa os sufixos de controle no session_state para resetar o cache do Streamlit
    if f"f1_o_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f1_o_key_suffix_{ano_sel}"] = 0
    if f"f1_p_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f1_p_key_suffix_{ano_sel}"] = 0

    dF1 = res_data.get("F1", {"valor": "0.00/1.00", "pontos": 0, "link": ""})
    
    # Faz o parse seguro dos valores salvos no banco para exibição inicial
    try:
        val_salvo_o, val_salvo_p = dF1["valor"].split("/")
        float_o = float(val_salvo_o)
        float_p = float(val_salvo_p)
    except:
        float_o, float_p = 0.0, 1.0

    # Aplica a máscara visual brasileira de R$ para o valor inicial do input
    str_inicial_o = f"R$ {float_o:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    str_inicial_p = f"R$ {float_p:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    c1, c2 = st.columns([1, 2])
    
    with c1:
        # Input Inteligente 1: Receita Arrecadada (O)
        sufixo_o = st.session_state[f"f1_o_key_suffix_{ano_sel}"]
        input_o_str = st.text_input(
            "Receita Arrecadada (O) - R$:",
            value=str_inicial_o,
            placeholder="Ex: 1.500.000,00",
            key=f"txt_f1_o_dinamico_{ano_sel}_{sufixo_o}_{ctr}"
        )
        
        # Input Inteligente 2: Receita Prevista (P)
        sufixo_p = st.session_state[f"f1_p_key_suffix_{ano_sel}"]
        input_p_str = st.text_input(
            "Receita Prevista Atualizada (P) - R$:",
            value=str_inicial_p,
            placeholder="Ex: 1.250.000,00",
            key=f"txt_f1_p_dinamico_{ano_sel}_{sufixo_p}_{ctr}"
        )

        # 🧹 Função interna para limpar a string BR e converter em float puro
        def limpa_conversao_monetaria(texto):
            num_limpo = texto.replace("R$", "").replace(" ", "")
            if "." in num_limpo and "," in num_limpo:
                num_limpo = num_limpo.replace(".", "").replace(",", ".")
            elif "," in num_limpo:
                num_limpo = num_limpo.replace(",", ".")
            return float(num_limpo)

        # Processamento e reatividade ao alterar os campos textuais
        try:
            v_arr = limpa_conversao_monetaria(input_o_str)
            v_prev = max(limpa_conversao_monetaria(input_p_str), 0.01) # Evita divisão por zero
            
            # Cálculo matemático do Indicador Q
            Q = v_arr / v_prev
            
            # Aplicação estrita da tabela de pontuação e faixas de graduação
            if Q >= 1.5 or Q <= 0.5:
                ptsF1 = 0.0
            elif 0.85 <= Q <= 1.15:
                ptsF1 = 75.0
            elif 1.15 < Q < 1.5:
                ptsF1 = ((Q - 1.5) * (-1) / 0.35) * 75
            else: # Faixa entre 0.5 e 0.85
                ptsF1 = ((Q - 0.5) / 0.35) * 75
                
        except ValueError:
            st.error("⚠️ Formato numérico inválido. Digite utilizando o padrão brasileiro (Ex: 150.000,00).")
            v_arr, v_prev, Q, ptsF1 = float_o, float_p, (float_o / max(float_p, 0.01)), float(dF1.get("pontos", 0))

    with c2:
        lF1 = st.text_area("Link/Evidência (F1):", value=dF1.get("link", ""), key=f"txt_f1_{ano_sel}_{ctr}", height=150)

    # Exibição explícita do cálculo do Indicador Q e a Nota Resultante
    st.markdown(f"""
    <div style="padding: 12px; background-color: #f1f5f9; border-left: 5px solid #1e3a8a; border-radius: 4px; margin-top: 15px; margin-bottom: 15px;">
        📌 <b>Cálculo da Execução:</b> R$ {v_arr:,.2f} / R$ {v_prev:,.2f}<br>
        📊 <b>Resultado do Indicador (Q):</b> <code style="font-size: 15px; font-weight: bold; color: #b45309;">{Q:.4f}</code><br>
        🎯 <b>Pontuação Obtida:</b> <code style="font-size: 15px; font-weight: bold; color: #1e40af;">{ptsF1:.2f} pontos</code>
    </div>
    """.replace(", ", "X").replace(".", ",").replace("X", "."), unsafe_allow_html=True)

    # Identifica se houve mudança de dados para salvar no banco e forçar o Toggle das Chaves
    string_banco_atual = f"{v_arr:.2f}/{v_prev:.2f}"
    string_banco_salva = f"{float_o:.2f}/{float_p:.2f}"

    if string_banco_atual != string_banco_salva or lF1 != dF1["link"]:
        save_resp("F1", string_banco_atual, ptsF1, lF1)
        
        # Se alterou o valor Arrecadado, incrementa o sufixo O
        if f"{v_arr:.2f}" != f"{float_o:.2f}":
            st.session_state[f"f1_o_key_suffix_{ano_sel}"] += 1
        # Se alterou o valor Previsto, incrementa o sufixo P
        if f"{v_prev:.2f}" != f"{float_p:.2f}":
            st.session_state[f"f1_p_key_suffix_{ano_sel}"] += 1
            
        st.rerun()

    bloco_comentarios("F1", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # F2 • Análise da Despesa com Formatação BR, Critérios e Key-Toggle
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("F2 • Análise da Despesa (Execução Orçamentária) – Resultado Consolidado")
    st.write("**Divisão da despesa executada pela despesa fixada final (R / S = T)**")
    
    # Tabela Oficial de Parâmetros e Pontuações do Indicador F2
    st.markdown("""
    | Resultado de $T$ | Pontuação do Indicador |
    | :--- | :--- |
    | Maior ou igual a 1,1 | 0 |
    | Maior que 1,0 e menor que 1,1 | Graduação entre 75 e 0 |
    | Maior ou igual a 0,9 e menor ou igual a 1,0 | 75 |
    | Maior que 0,5 e menor que 0,9 | Graduação entre 0 e 75 |
    | Menor ou igual a 0,5 | 0 |
    """)
    
    # 📝 Inclusão das memórias matemáticas oficiais do indicador F2
    st.markdown("""
    <div style="background-color: #f8fafc; padding: 12px; border-radius: 4px; border-left: 3px solid #64748b; margin-bottom: 15px;">
        <p style="margin-bottom: 8px; font-size: 13px;">📊 <b>Regras de Distribuição Proporcional nos Intervalos (Despesa):</b></p>
        <ul style="font-size: 13px; margin-left: 15px; padding-left: 0px;">
            <li><b>Para resultados maiores que 1,0 e menores que 1,1:</b> A graduação será distribuída igualitariamente no intervalo. Matematicamente, demonstrado por: <br><code style="background-color: #e2e8f0; padding: 2px 5px;">((T – 1,1) * (-1) / 0,10) * 75</code> <br><i>Exemplo: se T = 1,05, a nota do indicador será 37,50 pontos.</i></li>
            <li style="margin-top: 8px;"><b>Para resultados maiores que 0,5 e menores que 0,9:</b> A graduação será distribuída igualitariamente no intervalo. Matematicamente, demonstrado por: <br><code style="background-color: #e2e8f0; padding: 2px 5px;">((T – 0,5) / 0,40) * 75</code> <br><i>Exemplo: se T = 0,75, a nota do indicador será 46,88 pontos.</i></li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    # Inicializa os sufixos de controle no session_state para desvincular o cache do Streamlit
    if f"f2_r_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f2_r_key_suffix_{ano_sel}"] = 0
    if f"f2_s_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f2_s_key_suffix_{ano_sel}"] = 0

    dF2 = res_data.get("F2", {"valor": "0.00/1.00", "pontos": 0, "link": ""})
    
    # Faz o parse seguro dos valores salvos no banco (R / S)
    try:
        val_salvo_r, val_salvo_s = dF2["valor"].split("/")
        float_r = float(val_salvo_r)
        float_s = float(val_salvo_s)
    except:
        float_r, float_s = 0.0, 1.0

    # Aplica a máscara visual brasileira (R$) para a renderização inicial
    str_inicial_r = f"R$ {float_r:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    str_inicial_s = f"R$ {float_s:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    c1, c2 = st.columns([1, 2])
    
    with c1:
        # Input Inteligente 1: Despesa Executada (R)
        sufixo_r = st.session_state[f"f2_r_key_suffix_{ano_sel}"]
        input_r_str = st.text_input(
            "Despesa Executada (R) - R$:",
            value=str_inicial_r,
            placeholder="Ex: 1.050.000,00",
            key=f"txt_f2_r_dinamico_{ano_sel}_{sufixo_r}_{ctr}"
        )
        
        # Input Inteligente 2: Despesa Fixada Final (S)
        sufixo_s = st.session_state[f"f2_s_key_suffix_{ano_sel}"]
        input_s_str = st.text_input(
            "Despesa Fixada Final (S) - R$:",
            value=str_inicial_s,
            placeholder="Ex: 1.000.000,00",
            key=f"txt_f2_s_dinamico_{ano_sel}_{sufixo_s}_{ctr}"
        )

        # 🧹 Função interna para higienizar strings monetárias do padrão BR
        def limpa_conversao_monetaria(texto):
            num_limpo = texto.replace("R$", "").replace(" ", "")
            if "." in num_limpo and "," in num_limpo:
                num_limpo = num_limpo.replace(".", "").replace(",", ".")
            elif "," in num_limpo:
                num_limpo = num_limpo.replace(",", ".")
            return float(num_limpo)

        # Processamento matemático reativo
        try:
            v_exec = limpa_conversao_monetaria(input_r_str)
            v_fix = max(limpa_conversao_monetaria(input_s_str), 0.01) # Evita divisão por zero
            
            # Cálculo matemático do Indicador T
            T = v_exec / v_fix
            
            # Regras de negócio e faixas específicas do indicador T
            if T >= 1.1 or T <= 0.5:
                ptsF2 = 0.0
            elif 0.9 <= T <= 1.0:
                ptsF2 = 75.0
            elif 1.0 < T < 1.1:
                ptsF2 = ((T - 1.1) * (-1) / 0.10) * 75
            else: # Faixa entre 0.5 e 0.9
                ptsF2 = ((T - 0.5) / 0.40) * 75
                
        except ValueError:
            st.error("⚠️ Formato numérico inválido. Digite utilizando o padrão brasileiro (Ex: 150.000,00).")
            v_exec, v_fix, T, ptsF2 = float_r, float_s, (float_r / max(float_s, 0.01)), float(dF2.get("pontos", 0))

    with c2:
        lF2 = st.text_area("Link/Evidência (F2):", value=dF2.get("link", ""), key=f"txt_f2_{ano_sel}_{ctr}", height=150)

    # Exibição do painel consolidador de resultados matemáticos
    st.markdown(f"""
    <div style="padding: 12px; background-color: #f1f5f9; border-left: 5px solid #1e3a8a; border-radius: 4px; margin-top: 15px; margin-bottom: 15px;">
        📌 <b>Cálculo da Execução:</b> R$ {v_exec:,.2f} / R$ {v_fix:,.2f}<br>
        📊 <b>Resultado do Indicador (T):</b> <code style="font-size: 15px; font-weight: bold; color: #b45309;">{T:.4f}</code><br>
        🎯 <b>Pontuação Obtida:</b> <code style="font-size: 15px; font-weight: bold; color: #1e40af;">{ptsF2:.2f} pontos</code>
    </div>
    """.replace(", ", "X").replace(".", ",").replace("X", "."), unsafe_allow_html=True)

    # Verificação de alteração de dados para gatilho de persistência e invalidação de chaves
    string_banco_atual = f"{v_exec:.2f}/{v_fix:.2f}"
    string_banco_salva = f"{float_r:.2f}/{float_s:.2f}"

    if string_banco_atual != string_banco_salva or lF2 != dF2["link"]:
        save_resp("F2", string_banco_atual, ptsF2, lF2)
        
        # Incrementa individualmente conforme a mudança detectada para não travar o foco
        if f"{v_exec:.2f}" != f"{float_r:.2f}":
            st.session_state[f"f2_r_key_suffix_{ano_sel}"] += 1
        if f"{v_fix:.2f}" != f"{float_s:.2f}":
            st.session_state[f"f2_s_key_suffix_{ano_sel}"] += 1
            
        st.rerun()

    bloco_comentarios("F2", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # F3 • Análise do Resultado da Execução Orçamentária com Formatação BR e Cobertura de Déficit
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("F3 • Análise do Resultado da Execução Orçamentária – Resultado Consolidado")
    st.write("**Razão entre a despesa executada e a receita arrecadada (R / O = V)**")
    
    # Tabela Oficial de Parâmetros e Pontuações do Indicador F3
    st.markdown("""
    | Resultado de $V$ | Condição de Cobertura Contábil | Pontuação do Indicador |
    | :--- | :--- | :--- |
    | Maior ou igual a 1,2 | Qualquer caso | 0 |
    | Maior que 1,1 e menor que 1,2 | **Com** cobertura do déficit por Superávit | Graduação entre 100 e 0 |
    | Maior que 1,0 e menor que 1,2 | **Sem** cobertura do déficit por Superávit | 0 |
    | Maior que 1,0 e menor ou igual a 1,1 | **Com** cobertura do déficit por Superávit | 100 |
    | Maior ou igual a 0,9 e menor ou igual a 1,0 | Qualquer caso | 100 |
    | Maior que 0,75 e menor que 0,9 | Qualquer caso | Graduação entre 0 e 100 |
    | Menor ou igual a 0,75 | Qualquer caso | 0 |
    """)
    
    # 📝 Inclusão das memórias matemáticas oficiais do indicador F3
    st.markdown("""
    <div style="background-color: #f8fafc; padding: 12px; border-radius: 4px; border-left: 3px solid #64748b; margin-bottom: 15px;">
        <p style="margin-bottom: 8px; font-size: 13px;">📊 <b>Fórmulas de Distribuição nos Intervalos e Regra de Cobertura ($X$):</b></p>
        <p style="font-size: 13px; margin-bottom: 8px;"><i>Déficit ($V > 1$): O módulo da diferença $|O - R| = X$ é comparado aos créditos abertos por superávit financeiro. Se o crédito for igual ou maior, há cobertura financeira.</i></p>
        <ul style="font-size: 13px; margin-left: 15px; padding-left: 0px;">
            <li><b>Se V está entre 1,1 e 1,2 (Com Cobertura):</b> <code style="background-color: #e2e8f0; padding: 2px 5px;">((V – 1,2) * (-1) / 0,10) * 100</code> <br><i>Exemplo: se V = 1,15, a nota será 50,00 pontos.</i></li>
            <li style="margin-top: 8px;"><b>Se V está entre 0,75 e 0,90:</b> <code style="background-color: #e2e8f0; padding: 2px 5px;">((V – 0,75) / 0,15) * 100</code> <br><i>Exemplo: se V = 0,80, a nota será 33,33 pontos.</i></li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    # Inicializa os sufixos de controle no session_state para desvincular o cache do Streamlit
    if f"f3_r_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f3_r_key_suffix_{ano_sel}"] = 0
    if f"f3_o_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f3_o_key_suffix_{ano_sel}"] = 0
    if f"f3_c_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f3_c_key_suffix_{ano_sel}"] = 0

    # Busca ou inicializa os dados salvos estruturados por barra (R/O/C)
    dF3 = res_data.get("F3", {"valor": "0.00/1.00/0.00", "pontos": 0, "link": ""})
    
    try:
        val_salvo_r, val_salvo_o, val_salvo_c = dF3["valor"].split("/")
        float_r = float(val_salvo_r)
        float_o = float(val_salvo_o)
        float_c = float(val_salvo_c)
    except:
        float_r, float_o, float_c = 0.0, 1.0, 0.0

    # Aplica as máscaras visuais no padrão brasileiro (R$) para os inputs textuais
    str_inicial_r = f"R$ {float_r:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    str_inicial_o = f"R$ {float_o:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    str_inicial_c = f"R$ {float_c:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    c1, c2 = st.columns([1, 2])
    
    with c1:
        # Input 1: Despesa Executada (R)
        sufixo_r = st.session_state[f"f3_r_key_suffix_{ano_sel}"]
        input_r_str = st.text_input(
            "Despesa Executada (R) - R$:",
            value=str_inicial_r,
            key=f"txt_f3_r_dinamico_{ano_sel}_{sufixo_r}_{ctr}"
        )
        
        # Input 2: Receita Arrecadada (O)
        sufixo_o = st.session_state[f"f3_o_key_suffix_{ano_sel}"]
        input_o_str = st.text_input(
            "Receita Arrecadada (O) - R$:",
            value=str_inicial_o,
            key=f"txt_f3_o_dinamico_{ano_sel}_{sufixo_o}_{ctr}"
        )

        # Input 3: Créditos por Superávit Financeiro (C)
        sufixo_c = st.session_state[f"f3_c_key_suffix_{ano_sel}"]
        input_c_str = st.text_input(
            "Créditos por Superávit Financeiro - R$:",
            value=str_inicial_c,
            key=f"txt_f3_c_dinamico_{ano_sel}_{sufixo_c}_{ctr}"
        )

        # 🧹 Função interna para higienizar strings monetárias do padrão BR
        def limpa_conversao_monetaria(texto):
            num_limpo = texto.replace("R$", "").replace(" ", "")
            if "." in num_limpo and "," in num_limpo:
                num_limpo = num_limpo.replace(".", "").replace(",", ".")
            elif "," in num_limpo:
                num_limpo = num_limpo.replace(",", ".")
            return float(num_limpo)

        # Processamento lógico-matemático reativo
        try:
            v_exec = limpa_conversao_monetaria(input_r_str)
            v_arrec = max(limpa_conversao_monetaria(input_o_str), 0.01) # Evita divisão por zero
            v_cred_superavit = limpa_conversao_monetaria(input_c_str)
            
            # Cálculo do Indicador V e do Módulo da Diferença X
            V = v_exec / v_arrec
            X = abs(v_arrec - v_exec)
            
            # Avaliação de Cobertura Financeira do Déficit
            tem_cobertura = v_cred_superavit >= X

            # Motor de Regras de Pontuação Oficial do Indicador V
            if V >= 1.2:
                ptsF3 = 0.0
            elif 1.1 < V < 1.2:
                ptsF3 = ((V - 1.2) * (-1) / 0.10) * 100 if tem_cobertura else 0.0
            elif 1.0 < V <= 1.1:
                ptsF3 = 100.0 if tem_cobertura else 0.0
            elif 0.9 <= V <= 1.0:
                ptsF3 = 100.0
            elif 0.75 < V < 0.9:
                ptsF3 = ((V - 0.75) / 0.15) * 100
            else: # V <= 0.75
                ptsF3 = 0.0
                
        except ValueError:
            st.error("⚠️ Formato numérico inválido. Digite utilizando o padrão brasileiro (Ex: 150.000,00).")
            v_exec, v_arrec, v_cred_superavit = float_r, float_o, float_c
            V = float_r / max(float_o, 0.01)
            X = abs(float_o - float_r)
            tem_cobertura = float_c >= X
            ptsF3 = float(dF3.get("pontos", 0))

    with c2:
        lF3 = st.text_area("Link/Evidência (F3):", value=dF3.get("link", ""), key=f"txt_f3_{ano_sel}_{ctr}", height=215)

    # Construção do quadro analítico de resultados contábeis
    status_cobertura = "🟢 Déficit Coberto por Superávit" if tem_cobertura else "🔴 Déficit Não Coberto"
    if V <= 1.0:
        status_cobertura = "🔵 Superávit Orçamentário Corrente"

    st.markdown(f"""
    <div style="padding: 12px; background-color: #f1f5f9; border-left: 5px solid #1e3a8a; border-radius: 4px; margin-top: 15px; margin-bottom: 15px;">
        📌 <b>Análise Contábil:</b> R$ {v_exec:,.2f} / R$ {v_arrec:,.2f}<br>
        📊 <b>Resultado do Indicador (V):</b> <code style="font-size: 15px; font-weight: bold; color: #b45309;">{V:.4f}</code><br>
        ⚖️ <b>Diferença em Módulo (X):</b> R$ {X:,.2f} | <b>Situação:</b> <i>{status_cobertura}</i><br>
        🎯 <b>Pontuação Obtida:</b> <code style="font-size: 15px; font-weight: bold; color: #1e40af;">{ptsF3:.2f} pontos</code>
    </div>
    """.replace(", ", "X").replace(".", ",").replace("X", "."), unsafe_allow_html=True)

    # Identificação de alterações para gravação em banco e incremento dos sufixos de input
    string_banco_atual = f"{v_exec:.2f}/{v_arrec:.2f}/{v_cred_superavit:.2f}"
    string_banco_salva = f"{float_r:.2f}/{float_o:.2f}/{float_c:.2f}"

    if string_banco_atual != string_banco_salva or lF3 != dF3["link"]:
        save_resp("F3", string_banco_atual, ptsF3, lF3)
        
        if f"{v_exec:.2f}" != f"{float_r:.2f}":
            st.session_state[f"f3_r_key_suffix_{ano_sel}"] += 1
        if f"{v_arrec:.2f}" != f"{float_o:.2f}":
            st.session_state[f"f3_o_key_suffix_{ano_sel}"] += 1
        if f"{v_cred_superavit:.2f}" != f"{float_c:.2f}":
            st.session_state[f"f3_c_key_suffix_{ano_sel}"] += 1
            
        st.rerun()

    bloco_comentarios("F3", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # F4 • Análise do Esforço para Pagamento de Restos a Pagar (Dívida Flutuante)
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("F4 • Análise do Esforço para Pagamento de Restos a Pagar até o Bimestre")
    st.write("**Divisão dos pagamentos realizados pela posição inicial líquida de cancelamentos [A / (B - C) = Z]**")
    
    # Tabela Oficial de Parâmetros e Pontuações do Indicador F4
    st.markdown("""
    | Resultado de $Z$ | Pontuação do Indicador |
    | :--- | :--- |
    | Maior ou igual a 0,95 | 25 |
    | Maior que 0,75 e menor que 0,95 | Graduação entre 0 e 25 |
    | Menor ou igual a 0,75 | 0 |
    """)
    
    # 📝 Inclusão das memórias matemáticas oficiais do indicador F4
    st.markdown("""
    <div style="background-color: #f8fafc; padding: 12px; border-radius: 4px; border-left: 3px solid #64748b; margin-bottom: 15px;">
        <p style="margin-bottom: 8px; font-size: 13px;">📊 <b>Regra de Distribuição Proporcional no Intervalo:</b></p>
        <ul style="font-size: 13px; margin-left: 15px; padding-left: 0px;">
            <li><b>Para resultados maiores que 0,75 e menores que 0,95:</b> A graduação será distribuída igualitariamente no intervalo. Matematicamente, demonstrado por: <br><code style="background-color: #e2e8f0; padding: 2px 5px;">((Z – 0,75) / 0,20) * 25</code> <br><i>Exemplo: se Z = 0,80, a nota do indicador será 6,25 pontos.</i></li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    # Inicializa os sufixos de controle no session_state para gerenciar de forma independente o cache do Streamlit
    if f"f4_a_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f4_a_key_suffix_{ano_sel}"] = 0
    if f"f4_b_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f4_b_key_suffix_{ano_sel}"] = 0
    if f"f4_c_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f4_c_key_suffix_{ano_sel}"] = 0

    # Carrega ou inicializa a string persistida no banco contendo a tripla de valores separada por barras (A/B/C)
    dF4 = res_data.get("F4", {"valor": "0.00/1.00/0.00", "pontos": 0, "link": ""})
    
    try:
        val_salvo_a, val_salvo_b, val_salvo_c = dF4["valor"].split("/")
        float_a = float(val_salvo_a)
        float_b = float(val_salvo_b)
        float_c = float(val_salvo_c)
    except:
        float_a, float_b, float_c = 0.0, 1.0, 0.0

    # Converte os números de ponto flutuante na máscara brasileira de apresentação (R$)
    str_inicial_a = f"R$ {float_a:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    str_inicial_b = f"R$ {float_b:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    str_inicial_c = f"R$ {float_c:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    c1, c2 = st.columns([1, 2])
    
    with c1:
        # Input 1: Pagamentos Realizados de RP (A)
        sufixo_a = st.session_state[f"f4_a_key_suffix_{ano_sel}"]
        input_a_str = st.text_input(
            "Pagamentos Realizados (A) - R$:",
            value=str_inicial_a,
            key=f"txt_f4_a_dinamico_{ano_sel}_{sufixo_a}_{ctr}"
        )
        
        # Input 2: Posição Inicial de RP (B)
        sufixo_b = st.session_state[f"f4_b_key_suffix_{ano_sel}"]
        input_b_str = st.text_input(
            "Posição Inicial de Restos a Pagar (B) - R$:",
            value=str_inicial_b,
            key=f"txt_f4_b_dinamico_{ano_sel}_{sufixo_b}_{ctr}"
        )

        # Input 3: Cancelamentos de RP no Exercício (C)
        sufixo_c = st.session_state[f"f4_c_key_suffix_{ano_sel}"]
        input_c_str = st.text_input(
            "Cancelamentos no Exercício (C) - R$:",
            value=str_inicial_c,
            key=f"txt_f4_c_dinamico_{ano_sel}_{sufixo_c}_{ctr}"
        )

        # 🧹 Função interna para higienizar strings monetárias do padrão BR
        def limpa_conversao_monetaria(texto):
            num_limpo = texto.replace("R$", "").replace(" ", "")
            if "." in num_limpo and "," in num_limpo:
                num_limpo = num_limpo.replace(".", "").replace(",", ".")
            elif "," in num_limpo:
                num_limpo = num_limpo.replace(",", ".")
            return float(num_limpo)

        # Tratamento lógico e cálculo dinâmico do indicador Z
        try:
            v_pago = limpa_conversao_monetaria(input_a_str)
            v_pos_inicial = limpa_conversao_monetaria(input_b_str)
            v_cancelado = limpa_conversao_monetaria(input_c_str)
            
            # Cálculo da posição líquida (B - C) evitando divisão por zero ou base negativa
            posicao_liquida = max(v_pos_inicial - v_cancelado, 0.01)
            
            # Cálculo do Indicador Z
            Z = v_pago / posicao_liquida
            
            # Motor de regras de pontuação oficial do Indicador Z
            if Z >= 0.95:
                ptsF4 = 25.0
            elif 0.75 < Z < 0.95:
                ptsF4 = ((Z - 0.75) / 0.20) * 25
            else: # Z <= 0.75
                ptsF4 = 0.0
                
        except ValueError:
            st.error("⚠️ Formato numérico inválido. Digite utilizando o padrão brasileiro (Ex: 150.000,00).")
            v_pago, v_pos_inicial, v_cancelado = float_a, float_b, float_c
            Z = float_a / max(float_b - float_c, 0.01)
            ptsF4 = float(dF4.get("pontos", 0))

    with c2:
        lF4 = st.text_area("Link/Evidência (F4 - Item GF26 AUDESP):", value=dF4.get("link", ""), key=f"txt_f4_{ano_sel}_{ctr}", height=215)

    # Exibição do painel consolidador de métricas fiscais
    st.markdown(f"""
    <div style="padding: 12px; background-color: #f1f5f9; border-left: 5px solid #1e3a8a; border-radius: 4px; margin-top: 15px; margin-bottom: 15px;">
        📌 <b>Cálculo do Esforço:</b> R$ {v_pago:,.2f} / (R$ {v_pos_inicial:,.2f} - R$ {v_cancelado:,.2f})<br>
        📊 <b>Resultado do Indicador (Z):</b> <code style="font-size: 15px; font-weight: bold; color: #b45309;">{Z:.4f}</code><br>
        🎯 <b>Pontuação Obtida:</b> <code style="font-size: 15px; font-weight: bold; color: #1e40af;">{ptsF4:.2f} pontos</code>
    </div>
    """.replace(", ", "X").replace(".", ",").replace("X", "."), unsafe_allow_html=True)

    # Verificação de alteração de dados para gatilho de persistência e invalidação de chaves textuais
    string_banco_atual = f"{v_pago:.2f}/{v_pos_inicial:.2f}/{v_cancelado:.2f}"
    string_banco_salva = f"{float_a:.2f}/{float_b:.2f}/{float_c:.2f}"

    if string_banco_atual != string_banco_salva or lF4 != dF4["link"]:
        save_resp("F4", string_banco_atual, ptsF4, lF4)
        
        # Incrementa individualmente as chaves correspondentes aos valores modificados
        if f"{v_pago:.2f}" != f"{float_a:.2f}":
            st.session_state[f"f4_a_key_suffix_{ano_sel}"] += 1
        if f"{v_pos_inicial:.2f}" != f"{float_b:.2f}":
            st.session_state[f"f4_b_key_suffix_{ano_sel}"] += 1
        if f"{v_cancelado:.2f}" != f"{float_c:.2f}":
            st.session_state[f"f4_c_key_suffix_{ano_sel}"] += 1
            
        st.rerun()

    bloco_comentarios("F4", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # F5 • Análise do Nível de Cancelamento de Restos a Pagar
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("F5 • Análise do Nível de Cancelamento de Restos a Pagar")
    st.write("**Divisão dos cancelamentos realizados pela posição inicial de restos a pagar (C / B = K)**")
    
    # Tabela Oficial de Parâmetros e Pontuações do Indicador F5
    st.markdown("""
    | Resultado de $K$ | Pontuação do Indicador |
    | :--- | :--- |
    | Maior ou igual a 0,20 | 0 |
    | Maior que 0,05 e menor que 0,20 | Graduação entre 0 e 25 |
    | Menor ou igual a 0,05 | 25 |
    """)
    
    # 📝 Inclusão das memórias matemáticas oficiais do indicador F5
    st.markdown("""
    <div style="background-color: #f8fafc; padding: 12px; border-radius: 4px; border-left: 3px solid #64748b; margin-bottom: 15px;">
        <p style="margin-bottom: 8px; font-size: 13px;">📊 <b>Regra de Distribuição Proporcional no Intervalo:</b></p>
        <ul style="font-size: 13px; margin-left: 15px; padding-left: 0px;">
            <li><b>Para resultados maiores que 0,05 e menores que 0,20:</b> A graduação será distribuída igualitariamente no intervalo. Matematicamente, demonstrado por: <br><code style="background-color: #e2e8f0; padding: 2px 5px;">((0,20 - K) / 0,15) * 25</code> <br><i>Exemplo: se K = 0,06, a nota do indicador será 23,33 pontos.</i></li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    # Inicializa os sufixos de controle no session_state para gerenciar de forma independente o cache do Streamlit
    if f"f5_c_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f5_c_key_suffix_{ano_sel}"] = 0
    if f"f5_b_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f5_b_key_suffix_{ano_sel}"] = 0

    # Carrega ou inicializa a string persistida no banco contendo a dupla de valores separada por barra (C/B)
    dF5 = res_data.get("F5", {"valor": "0.00/1.00", "pontos": 0, "link": ""})
    
    try:
        val_salvo_c, val_salvo_b = dF5["valor"].split("/")
        float_c = float(val_salvo_c)
        float_b = float(val_salvo_b)
    except:
        float_c, float_b = 0.0, 1.0

    # Converte os números de ponto flutuante na máscara brasileira de apresentação (R$)
    str_inicial_c = f"R$ {float_c:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    str_inicial_b = f"R$ {float_b:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    c1, c2 = st.columns([1, 2])
    
    with c1:
        # Input 1: Cancelamentos de RP no Exercício (C)
        sufixo_c = st.session_state[f"f5_c_key_suffix_{ano_sel}"]
        input_c_str = st.text_input(
            "Cancelamentos no Exercício (C) - R$:",
            value=str_inicial_c,
            key=f"txt_f5_c_dinamico_{ano_sel}_{sufixo_c}_{ctr}"
        )
        
        # Input 2: Posição Inicial de RP (B)
        sufixo_b = st.session_state[f"f5_b_key_suffix_{ano_sel}"]
        input_b_str = st.text_input(
            "Posição Inicial de Restos a Pagar (B) - R$:",
            value=str_inicial_b,
            key=f"txt_f5_b_dinamico_{ano_sel}_{sufixo_b}_{ctr}"
        )

        # 🧹 Função interna para higienizar strings monetárias do padrão BR
        def limpa_conversao_monetaria(texto):
            num_limpo = texto.replace("R$", "").replace(" ", "")
            if "." in num_limpo and "," in num_limpo:
                num_limpo = num_limpo.replace(".", "").replace(",", ".")
            elif "," in num_limpo:
                num_limpo = num_limpo.replace(",", ".")
            return float(num_limpo)

        # Tratamento lógico e cálculo dinâmico do indicador K
        try:
            v_cancelado = limpa_conversao_monetaria(input_c_str)
            v_pos_inicial = max(limpa_conversao_monetaria(input_b_str), 0.01) # Evita divisão por zero
            
            # Cálculo do Indicador K
            K = v_cancelado / v_pos_inicial
            
            # 🛑 TRAVA DE INICIALIZAÇÃO: Se os campos estiverem zerados/não editados, não pontua automático
            if v_cancelado == 0.0 and (dF5.get("link", "").strip() == ""):
                ptsF5 = 0.0
                texto_pontuacao = "⏳ Aguardando preenchimento para cálculo..."
            else:
                # Motor de regras de pontuação oficial do Indicador K
                if K >= 0.20:
                    ptsF5 = 0.0
                elif 0.05 < K < 0.20:
                    ptsF5 = ((0.20 - K) / 0.15) * 25
                else: # K <= 0.05
                    ptsF5 = 25.0
                texto_pontuacao = f"{ptsF5:.2f} pontos"
                
        except ValueError:
            st.error("⚠️ Formato numérico inválido. Digite utilizando o padrão brasileiro (Ex: 150.000,00).")
            v_cancelado, v_pos_inicial = float_c, float_b
            K = float_c / max(float_b, 0.01)
            ptsF5 = float(dF5.get("pontos", 0))
            texto_pontuacao = f"{ptsF5:.2f} pontos"

    with c2:
        lF5 = st.text_area("Link/Evidência (F5 - Item GF26 AUDESP):", value=dF5.get("link", ""), key=f"txt_f5_{ano_sel}_{ctr}", height=150)

    # Exibição do painel consolidador de métricas fiscais
    st.markdown(f"""
    <div style="padding: 12px; background-color: #f1f5f9; border-left: 5px solid #1e3a8a; border-radius: 4px; margin-top: 15px; margin-bottom: 15px;">
        📌 <b>Cálculo do Nível de Cancelamento:</b> R$ {v_cancelado:,.2f} / R$ {v_pos_inicial:,.2f}<br>
        📊 <b>Resultado do Indicador (K):</b> <code style="font-size: 15px; font-weight: bold; color: #b45309;">{K:.4f}</code><br>
        🎯 <b>Pontuação Obtida:</b> <code style="font-size: 15px; font-weight: bold; color: #1e40af;">{texto_pontuacao}</code>
    </div>
    """.replace(", ", "X").replace(".", ",").replace("X", "."), unsafe_allow_html=True)

    # Verificação de alteração de dados para gatilho de persistência e invalidação de chaves textuais
    string_banco_atual = f"{v_cancelado:.2f}/{v_pos_inicial:.2f}"
    string_banco_salva = f"{float_c:.2f}/{float_b:.2f}"

    if string_banco_atual != string_banco_salva or lF5 != dF5["link"]:
        save_resp("F5", string_banco_atual, ptsF5, lF5)
        
        # Incrementa individualmente as chaves correspondentes aos valores modificados
        if f"{v_cancelado:.2f}" != f"{float_c:.2f}":
            st.session_state[f"f5_c_key_suffix_{ano_sel}"] += 1
        if f"{v_pos_inicial:.2f}" != f"{float_b:.2f}":
            st.session_state[f"f5_b_key_suffix_{ano_sel}"] += 1
            
        st.rerun()

    bloco_comentarios("F5", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # F6 • Despesas com Pessoal – Poder Executivo
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("F6 • Despesas com Pessoal – Poder Executivo (LRF)")
    st.write("**Índice da Despesa Total com Pessoal do Executivo em relação à Receita Corrente Líquida (RCL)**")
    
    # Tabela Oficial de Parâmetros convertida para Percentual
    st.markdown("""
    | Resultado do Índice (%) | Impacto / Pontuação do Indicador |
    | :--- | :--- |
    | Maior que 54,00% (Acima do Limite Legal) | 🚨 Rebaixa 1 faixa do i-Fiscal |
    | Entre 51,30% e 54,00% (Acima do Limite de Alerta) | ⚠️ -20 (Perde 20 pontos) |
    | Menor que 51,30% (Dentro do Limite) | ✅ 00 (Sem penalidades) |
    """)
    st.caption("ℹ️ *Dados obtidos a partir do Relatório de Instrução, item GF27 do Sistema AUDESP.*")
    st.markdown("<br>", unsafe_allow_html=True)

    # Inicializa o sufixo de controle no session_state para o Key-Toggle
    if f"f6_pessoal_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f6_pessoal_key_suffix_{ano_sel}"] = 0

    dF6 = res_data.get("F6", {"valor": "0.00", "pontos": 0, "link": ""})
    
    # Faz o parse seguro do valor percentual salvo (armazenado como float decimal, ex: 0.513)
    try:
        float_f6 = float(dF6["valor"])
    except:
        float_f6 = 0.0

    # Converte o float decimal para string percentual formatada no padrão BR (ex: 51,30%)
    str_inicial_f6 = f"{float_f6 * 100:.2f}%".replace(".", ",")

    c1, c2 = st.columns([1, 2])
    
    with c1:
        # Input Inteligente de Texto para o Percentual de Pessoal
        sufixo_f6 = st.session_state[f"f6_pessoal_key_suffix_{ano_sel}"]
        input_f6_str = st.text_input(
            "Índice de Despesa com Pessoal (%):",
            value=str_inicial_f6,
            placeholder="Ex: 51,30%",
            key=f"txt_f6_dinamico_{ano_sel}_{sufixo_f6}_{ctr}"
        )

        # 🧹 Função interna para limpar o símbolo '%' e converter para float decimal puro
        try:
            num_limpo = input_f6_str.replace("%", "").replace(" ", "").replace(",", ".")
            v_indice = float(num_limpo) / 100.0  # Transforma 51.30 em 0.513
            
            # 🛑 TRAVA DE INICIALIZAÇÃO: Evita aplicar nota 0 ou rebaixamento sem preenchimento
            if v_indice == 0.0 and (dF6.get("link", "").strip() == ""):
                ptsF6 = 0.0
                texto_resultado = "⏳ Aguardando preenchimento do índice..."
                estilo_status = "color: #64748b;"
            else:
                # Motor de regras baseado nas faixas da AUDESP
                if v_indice > 0.54:
                    ptsF6 = 0.0  # O rebaixamento de faixa do i-Fiscal deve ser tratado no consolidado geral
                    texto_resultado = "🚨 CRÍTICO: Maior que 54,00% (Gera Rebaixamento de Faixa Geral)"
                    estilo_status = "color: #dc2626; font-weight: bold;"
                elif 0.513 <= v_indice <= 0.54:
                    ptsF6 = -20.0
                    texto_resultado = "⚠️ ALERTA: Entre 51,30% e 54,00% (Penalidade: -20,00 pontos)"
                    estilo_status = "color: #d97706; font-weight: bold;"
                else:
                    ptsF6 = 0.0
                    texto_resultado = "✅ REGULAR: Menor que 51,30% (Sem penalidades)"
                    estilo_status = "color: #16a34a; font-weight: bold;"
                    
        except ValueError:
            st.error("⚠️ Formato de percentual inválido. Digite utilizando o padrão brasileiro (Ex: 52,45%).")
            v_indice = float_f6
            ptsF6 = float(dF6.get("pontos", 0))
            texto_resultado = "Erro na leitura do campo"
            estilo_status = "color: #dc2626;"

    with c2:
        lF6 = st.text_area("Link/Evidência (F6 - Item GF27 AUDESP):", value=dF6.get("link", ""), key=f"txt_f6_{ano_sel}_{ctr}", height=150)

    # Exibição do painel consolidador formatado em percentual brasileiro
    st.markdown(f"""
    <div style="padding: 12px; background-color: #f1f5f9; border-left: 5px solid #1e3a8a; border-radius: 4px; margin-top: 15px; margin-bottom: 15px;">
        📊 <b>Índice Calculado:</b> <code style="font-size: 15px; font-weight: bold; color: #1e40af;">{v_indice * 100:.2f}%</code><br>
        ⚖️ <b>Status da LRF:</b> <span style="{estilo_status}">{texto_resultado}</span>
    </div>
    """.replace(".", ","), unsafe_allow_html=True)

    # Verificação de alteração de dados para gravação e recarga do componente
    string_banco_atual = f"{v_indice:.4f}"
    string_banco_salva = f"{float_f6:.4f}"

    if string_banco_atual != string_banco_salva or lF6 != dF6["link"]:
        save_resp("F6", string_banco_atual, ptsF6, lF6)
        st.session_state[f"f6_pessoal_key_suffix_{ano_sel}"] += 1
        st.rerun()

    bloco_comentarios("F6", res_data)
    st.markdown('</div>', unsafe_allow_html=True)
# F7 • Despesas com Pessoal – Poder Legislativo
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("F7 • Despesas com Pessoal – Poder Legislativo (LRF)")
    st.write("**Índice da Despesa Total com Pessoal do Legislativo em relação à Receita Corrente Líquida (DPPL / RCL = AB)**")
    
    # Adicionado o prefixo 'r' para corrigir os erros de SyntaxWarning (\ge e \le)
    st.markdown(r"""
    | Resultado do Índice $AB$ (%) | Impacto / Pontuação do Indicador |
    | :--- | :--- |
    | Maior que 6,00% ($> 0,06$) | 🚨 -10 (Perde 10 pontos) |
    | Entre 5,60% e 6,00% ($\ge 0,056$ e $\le 0,06$) | ⚠️ Graduação entre 0 e -10 pontos |
    | Menor que 5,60% ($< 0,056$) | ✅ 00 pontos (Sem penalidades) |
    """)
    
    # 📝 Inclusão das memórias matemáticas oficiais do indicador F7
    st.markdown("""
    <div style="background-color: #f8fafc; padding: 12px; border-radius: 4px; border-left: 3px solid #64748b; margin-bottom: 15px;">
        <p style="margin-bottom: 8px; font-size: 13px;">📊 <b>Regra de Distribuição Proporcional no Intervalo Crítico (Base Decimal):</b></p>
        <ul style="font-size: 13px; margin-left: 15px; padding-left: 0px;">
            <li><b>Para resultados maiores que 5,70% (0,057) e menores ou iguais a 6,00% (0,060):</b> A graduação de penalidade será calculada estritamente sobre a base decimal. Matematicamente: <br><code style="background-color: #e2e8f0; padding: 2px 5px;">((AB – 0,057) / 0,003) * (-10)</code> <br><i>Exemplo: se AB = 5,80% (0,058), a perda será de -3,33 pontos. Se AB = 6,00% (0,060), a fórmula processa o teto exato de -10,00 pontos.</i></li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    # Inicializa os sufixos de controle no session_state para gerenciar de forma independente o cache do Streamlit
    if f"f7_ab_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f7_ab_key_suffix_{ano_sel}"] = 0

    # Carrega ou inicializa a string persistida no banco contendo o valor decimal do índice
    dF7 = res_data.get("F7", {"valor": "0.00", "pontos": 0, "link": ""})
    
    try:
        float_ab = float(dF7["valor"])
    except:
        float_ab = 0.0

    # Converte o float decimal para string percentual formatada no padrão BR (ex: 5,80%)
    str_inicial_ab = f"{float_ab * 100:.2f}%".replace(".", ",")

    c1, c2 = st.columns([1, 2])
    
    with c1:
        # Input de Texto Inteligente (O auditor digita em % para facilidade, o código processa em decimal)
        sufixo_ab = st.session_state[f"f7_ab_key_suffix_{ano_sel}"]
        input_ab_str = st.text_input(
            "Índice de Pessoal do Legislativo (AB) - %:",
            value=str_inicial_ab,
            placeholder="Ex: 5,80%",
            key=f"txt_f7_dinamico_{ano_sel}_{sufixo_ab}_{ctr}"
        )

        # 🧹 Higienização e conversão do percentual da tela para número decimal puro
        try:
            num_limpo = input_ab_str.replace("%", "").replace(" ", "").replace(",", ".")
            v_indice = round(float(num_limpo) / 100.0, 4)  # Força o arredondamento em 4 casas decimais para evitar ruídos de ponto flutuante
            
            # 🛑 TRAVA DE INICIALIZAÇÃO: Se estiver zerado e sem link, não gera penalidade automática
            if v_indice == 0.0 and (dF7.get("link", "").strip() == ""):
                ptsF7 = 0.0
                texto_resultado = "Aguardando preenchimento..."
                texto_pontuacao = "⏳ 0,00 pontos"
                estilo_status = "color: #64748b;"
            else:
                # 🧮 Motor de Regras Oficiais ajustado para capturar o teto de 0,0600 na fórmula
                if v_indice > 0.0600:
                    ptsF7 = -10.0
                    texto_resultado = "🚨 CRÍTICO: Limite Máximo Estrapolado (> 6,00%)"
                    estilo_status = "color: #dc2626; font-weight: bold;"
                elif 0.0570 <= v_indice <= 0.0600:
                    # Agora o 0,0600 entra aqui e roda a fórmula: ((0,060 - 0,057) / 0,003) * -10 = -10,00
                    ptsF7 = ((v_indice - 0.0570) / 0.0030) * (-10.0)
                    texto_resultado = "⚠️ ALERTA DE GRADUAÇÃO (Fórmula Aplicada)"
                    estilo_status = "color: #d97706; font-weight: bold;"
                elif 0.0560 <= v_indice < 0.0570:
                    ptsF7 = 0.0  # Faixa prudencial que não pontua na fórmula, mas está na faixa de graduação inicial do manual
                    texto_resultado = "⚠️ Atenção: Faixa Prudencial de Alerta (Sem penalidade)"
                    estilo_status = "color: #b45309;"
                else:  # v_indice < 0.0560
                    ptsF7 = 0.0
                    texto_resultado = "✅ REGULAR: Menor que 5,60%"
                    estilo_status = "color: #16a34a; font-weight: bold;"
                
                texto_pontuacao = f"{ptsF7:.2f} pontos"
                
        except ValueError:
            st.error("⚠️ Formato numérico inválido. Digite utilizando o padrão brasileiro (Ex: 5,80%).")
            v_indice = float_ab
            ptsF7 = float(dF7.get("pontos", 0))
            texto_resultado = "Erro na leitura do campo"
            texto_pontuacao = f"{ptsF7:.2f} pontos"
            estilo_status = "color: #dc2626;"

    with c2:
        lF7 = st.text_area("Link/Evidência (F7 - Item GF27 AUDESP):", value=dF7.get("link", ""), key=f"txt_f7_{ano_sel}_{ctr}", height=150)

    # Exibição do painel consolidador de métricas fiscais
    st.markdown(f"""
    <div style="padding: 12px; background-color: #f1f5f9; border-left: 5px solid #1e3a8a; border-radius: 4px; margin-top: 15px; margin-bottom: 15px;">
        📊 <b>Índice Informado:</b> {v_indice * 100:.2f}% | 🕵️ <b>Base Decimal de Análise:</b> <code style="font-size: 14px; font-weight: bold; color: #b45309;">{v_indice:.4f}</code><br>
        ⚖️ <b>Situação do Poder Legislativo:</b> <span style="{estilo_status}">{texto_resultado}</span><br>
        🎯 <b>Impacto na Pontuação:</b> <code style="font-size: 15px; font-weight: bold; color: #1e40af;">{texto_pontuacao}</code>
    </div>
    """.replace(".", ","), unsafe_allow_html=True)

    # Verificação de alteração de dados para gatilho de persistência e invalidação de chaves textuais
    string_banco_atual = f"{v_indice:.4f}"
    string_banco_salva = f"{float_ab:.4f}"

    if string_banco_atual != string_banco_salva or lF7 != dF7["link"]:
        save_resp("F7", string_banco_atual, ptsF7, lF7)
        st.session_state[f"f7_ab_key_suffix_{ano_sel}"] += 1
        st.rerun()

    bloco_comentarios("F7", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # F8 • Apuração do Resultado Financeiro (Superávit/Déficit)
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("F8 • Apuração do Resultado Financeiro (Superávit/Déficit) – Resultado Consolidado")
    st.write("**Divisão entre o Ativo Financeiro e o Passivo Financeiro (AC / AD = AE)**")
    
    # Tabela Oficial de Parâmetros e Pontuações do Indicador F8
    st.markdown("""
    | Resultado de $AE$ | Pontuação do Indicador |
    | :--- | :--- |
    | Maior ou igual a 1,30 | 0 |
    | Maior que 1,10 e menor que 1,30 | Graduação entre 75 e 0 |
    | Maior ou igual a 1,00 e menor ou igual a 1,10 | 75 |
    | Maior que 0,75 e menor que 1,00 | Graduação entre 0 e 75 |
    | Menor ou igual a 0,75 | 0 |
    """)
    
    # 📝 Inclusão das memórias matemáticas oficiais do indicador F8
    st.markdown("""
    <div style="background-color: #f8fafc; padding: 12px; border-radius: 4px; border-left: 3px solid #64748b; margin-bottom: 15px;">
        <p style="margin-bottom: 8px; font-size: 13px;">📊 <b>Regras de Distribuição Proporcional nos Intervalos:</b></p>
        <ul style="font-size: 13px; margin-left: 15px; padding-left: 0px;">
            <li><b>Para resultados maiores que 1,10 e menores que 1,30 (Superávit Elevado):</b> A graduação será distribuída igualitariamente no intervalo. Matematicamente: <br><code style="background-color: #e2e8f0; padding: 2px 5px;">((AE – 1,30) * (-1) / 0,20) * 75</code> <br><i>Exemplo: se AE = 1,20, a nota do indicador será 37,50 pontos.</i></li>
            <li style="margin-top: 8px;"><b>Para resultados maiores que 0,75 e menores que 1,00 (Tendência a Déficit):</b> A graduação será distribuída igualitariamente no intervalo. Matematicamente: <br><code style="background-color: #e2e8f0; padding: 2px 5px;">((AE – 0,75) / 0,25) * 75</code> <br><i>Exemplo: se AE = 0,85, a nota do indicador será 30,00 pontos.</i></li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    # Inicializa os sufixos de controle no session_state para gerenciar de forma independente o cache do Streamlit
    if f"f8_ac_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f8_ac_key_suffix_{ano_sel}"] = 0
    if f"f8_ad_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f8_ad_key_suffix_{ano_sel}"] = 0

    # Carrega ou inicializa a string persistida no banco contendo a dupla de valores separada por barra (AC/AD)
    dF8 = res_data.get("F8", {"valor": "0.00/1.00", "pontos": 0, "link": ""})
    
    try:
        val_salvo_ac, val_salvo_ad = dF8["valor"].split("/")
        float_ac = float(val_salvo_ac)
        float_ad = float(val_salvo_ad)
    except:
        float_ac, float_ad = 0.0, 1.0

    # Converte os números de ponto flutuante na máscara brasileira de apresentação monetária (R$)
    str_inicial_ac = f"R$ {float_ac:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    str_inicial_ad = f"R$ {float_ad:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    c1, c2 = st.columns([1, 2])
    
    with c1:
        # Input 1: Ativo Financeiro (AC)
        sufixo_ac = st.session_state[f"f8_ac_key_suffix_{ano_sel}"]
        input_ac_str = st.text_input(
            "Ativo Financeiro (AC) - R$:",
            value=str_inicial_ac,
            placeholder="Ex: 1.200.000,00",
            key=f"txt_f8_ac_dinamico_{ano_sel}_{sufixo_ac}_{ctr}"
        )
        
        # Input 2: Passivo Financeiro (AD)
        sufixo_ad = st.session_state[f"f8_ad_key_suffix_{ano_sel}"]
        input_ad_str = st.text_input(
            "Passivo Financeiro (AD) - R$:",
            value=str_inicial_ad,
            placeholder="Ex: 1.000.000,00",
            key=f"txt_f8_ad_dinamico_{ano_sel}_{sufixo_ad}_{ctr}"
        )

        # 🧹 Função interna para higienizar strings monetárias do padrão BR
        def limpa_conversao_monetaria(texto):
            num_limpo = texto.replace("R$", "").replace(" ", "")
            if "." in num_limpo and "," in num_limpo:
                num_limpo = num_limpo.replace(".", "").replace(",", ".")
            elif "," in num_limpo:
                num_limpo = num_limpo.replace(",", ".")
            return float(num_limpo)

        # Tratamento lógico e cálculo dinâmico do indicador AE
        try:
            v_ativo = limpa_conversao_monetaria(input_ac_str)
            v_passivo = max(limpa_conversao_monetaria(input_ad_str), 0.01) # Evita divisão por zero
            
            # Cálculo do Indicador AE
            AE = v_ativo / v_passivo
            
            # 🛑 TRAVA DE INICIALIZAÇÃO: Se estiver zerado e sem link, não gera pontuação automática
            if v_ativo == 0.0 and (dF8.get("link", "").strip() == ""):
                ptsF8 = 0.0
                texto_pontuacao = "⏳ Aguardando preenchimento dos valores monetários..."
            else:
                # Motor de regras de pontuação oficial do Indicador AE
                if AE >= 1.30 or AE <= 0.75:
                    ptsF8 = 0.0
                elif 1.00 <= AE <= 1.10:
                    ptsF8 = 75.0
                elif 1.10 < AE < 1.30:
                    ptsF8 = ((AE - 1.30) * (-1) / 0.20) * 75
                else: # 0.75 < AE < 1.00
                    ptsF8 = ((AE - 0.75) / 0.25) * 75
                
                texto_pontuacao = f"{ptsF8:.2f} pontos"
                
        except ValueError:
            st.error("⚠️ Formato numérico inválido. Digite utilizando o padrão brasileiro (Ex: 150.000,00).")
            v_ativo, v_passivo = float_ac, float_ad
            AE = float_ac / max(float_ad, 0.01)
            ptsF8 = float(dF8.get("pontos", 0))
            texto_pontuacao = f"{ptsF8:.2f} pontos"

    with c2:
        lF8 = st.text_area("Link/Evidência (F8 - Balanço Patrimonial AUDESP):", value=dF8.get("link", ""), key=f"txt_f8_{ano_sel}_{ctr}", height=150)

    # Exibição do painel consolidador de métricas contábeis (padrão monetário BR)
    st.markdown(f"""
    <div style="padding: 12px; background-color: #f1f5f9; border-left: 5px solid #1e3a8a; border-radius: 4px; margin-top: 15px; margin-bottom: 15px;">
        📌 <b>Balanço Contábil:</b> R$ {v_ativo:,.2f} / R$ {v_passivo:,.2f}<br>
        📊 <b>Resultado do Indicador (AE):</b> <code style="font-size: 15px; font-weight: bold; color: #b45309;">{AE:.4f}</code><br>
        🎯 <b>Pontuação Obtida:</b> <code style="font-size: 15px; font-weight: bold; color: #1e40af;">{texto_pontuacao}</code>
    </div>
    """.replace(", ", "X").replace(".", ",").replace("X", "."), unsafe_allow_html=True)

    # Verificação de alteração de dados para gatilho de persistência e invalidação de chaves textuais
    string_banco_atual = f"{v_ativo:.2f}/{v_passivo:.2f}"
    string_banco_salva = f"{float_ac:.2f}/{float_ad:.2f}"

    if string_banco_atual != string_banco_salva or lF8 != dF8["link"]:
        save_resp("F8", string_banco_atual, ptsF8, lF8)
        
        # Incrementa individualmente as chaves correspondentes aos valores modificados
        if f"{v_ativo:.2f}" != f"{float_ac:.2f}":
            st.session_state[f"f8_ac_key_suffix_{ano_sel}"] += 1
        if f"{v_passivo:.2f}" != f"{float_ad:.2f}":
            st.session_state[f"f8_ad_key_suffix_{ano_sel}"] += 1
            
        st.rerun()

    bloco_comentarios("F8", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

   # F9 • Apuração da Dívida Fundada (Aumento/Redução)
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("F9 • Apuração da Dívida Fundada (DCL / RCL)")
    st.write("**Razão entre a Dívida Consolidada Líquida e a Receita Corrente Líquida [DCL / RCL = AF]**")
    
    # Adicionado o prefixo 'r' para corrigir os erros de SyntaxWarning (\ge e \le)
    st.markdown(r"""
    | Resultado do Índice $AF$ | Impacto / Pontuação do Indicador |
    | :--- | :--- |
    | Maior que 1,20 ($> 1,2$) | 🚨 -10 (Perde 10 pontos fixos) |
    | Entre 1,10 e 1,20 ($\ge 1,1$ e $\le 1,2$) | ⚠️ Graduação entre 0 e -10 pontos |
    | Menor que 1,10 ($< 1,1$) | ✅ 00 ponto (Sem penalidades) |
    """)
    st.caption("ℹ️ *Dados extraídos do Relatório de Instrução, item GF-28 do Sistema AUDESP.*")
    
    # 📝 Memória de cálculo oficial fornecida
    st.markdown("""
    <div style="background-color: #f8fafc; padding: 12px; border-radius: 4px; border-left: 3px solid #64748b; margin-bottom: 15px;">
        <p style="margin-bottom: 8px; font-size: 13px;">📊 <b>Regra de Distribuição Proporcional no Intervalo Crítico:</b></p>
        <ul style="font-size: 13px; margin-left: 15px; padding-left: 0px;">
            <li><b>Para resultados maiores que 1,10 e menores que 1,20:</b> A graduação será distribuída igualitariamente no intervalo através da fórmula: <br><code style="background-color: #e2e8f0; padding: 2px 5px;">((AF – 1,1) / 0,10) * (-10)</code> <br><i>Exemplo: se AF = 1,15, a nota do indicador será exatamente -5,00 pontos.</i></li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    # Inicializa os sufixos de controle no session_state para gerenciar o cache de forma isolada
    if f"f9_dcl_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f9_dcl_key_suffix_{ano_sel}"] = 0
    if f"f9_rcl_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f9_rcl_key_suffix_{ano_sel}"] = 0

    # Carrega ou inicializa a string persistida no banco contendo a dupla de valores (DCL/RCL)
    dF9 = res_data.get("F9", {"valor": "0.00/1.00", "pontos": 0, "link": ""})
    
    try:
        val_salvo_dcl, val_salvo_rcl = dF9["valor"].split("/")
        float_dcl = float(val_salvo_dcl)
        float_rcl = float(val_salvo_rcl)
    except:
        float_dcl, float_rcl = 0.0, 1.0

    # Converte os números salvos na máscara brasileira de apresentação monetária (R$)
    str_inicial_dcl = f"R$ {float_dcl:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    str_inicial_rcl = f"R$ {float_rcl:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    c1, c2 = st.columns([1, 2])
    
    with c1:
        # Input 1: Dívida Consolidada Líquida (DCL)
        sufixo_dcl = st.session_state[f"f9_dcl_key_suffix_{ano_sel}"]
        input_dcl_str = st.text_input(
            "Dívida Consolidada Líquida (DCL) - R$:",
            value=str_inicial_dcl,
            placeholder="Ex: 12.000.000,00",
            key=f"txt_f9_dcl_dinamico_{ano_sel}_{sufixo_dcl}_{ctr}"
        )
        
        # Input 2: Receita Corrente Líquida (RCL)
        sufixo_rcl = st.session_state[f"f9_rcl_key_suffix_{ano_sel}"]
        input_rcl_str = st.text_input(
            "Receita Corrente Líquida (RCL) - R$:",
            value=str_inicial_rcl,
            placeholder="Ex: 10.000.000,00",
            key=f"txt_f9_rcl_dinamico_{ano_sel}_{sufixo_rcl}_{ctr}"
        )

        # 🧹 Função interna para higienizar strings monetárias do padrão BR
        def limpa_conversao_monetaria(texto):
            num_limpo = texto.replace("R$", "").replace(" ", "")
            if "." in num_limpo and "," in num_limpo:
                num_limpo = num_limpo.replace(".", "").replace(",", ".")
            elif "," in num_limpo:
                num_limpo = num_limpo.replace(",", ".")
            return float(num_limpo)

        # Tratamento lógico e cálculo dinâmico do indicador AF
        try:
            v_dcl = limpa_conversao_monetaria(input_dcl_str)
            v_rcl = max(limpa_conversao_monetaria(input_rcl_str), 0.01) # Evita divisão por zero
            
            # Cálculo do Indicador AF (Decimal Puro)
            AF = round(v_dcl / v_rcl, 4)
            
            # 🛑 TRAVA DE INICIALIZAÇÃO: Se a DCL estiver zerada e sem link, não penaliza automaticamente
            if v_dcl == 0.0 and (dF9.get("link", "").strip() == ""):
                ptsF9 = 0.0
                texto_resultado = "Aguardando preenchimento..."
                texto_pontuacao = "⏳ 0,00 pontos"
                estilo_status = "color: #64748b;"
            else:
                # 🧮 MOTOR DE REGRAS: Baseado estritamente no enunciado da AUDESP
                if AF > 1.2000:
                    ptsF9 = -10.0
                    texto_resultado = "🚨 CRÍTICO: Índice Superior ao Teto (> 1,20)"
                    estilo_status = "color: #dc2626; font-weight: bold;"
                elif 1.1000 <= AF <= 1.2000:
                    # Aplicação exata da fórmula paramétrica fornecida
                    ptsF9 = ((AF - 1.1000) / 0.1000) * (-10.0)
                    texto_resultado = "⚠️ ALERTA DE GRADUAÇÃO (Fórmula Aplicada)"
                    estilo_status = "color: #d97706; font-weight: bold;"
                else:  # AF < 1.1000
                    ptsF9 = 0.0
                    texto_resultado = "✅ REGULAR: Menor que 1,10 (Sem penalidades)"
                    estilo_status = "color: #16a34a; font-weight: bold;"
                
                texto_pontuacao = f"{ptsF9:.2f} pontos"
                
        except ValueError:
            st.error("⚠️ Formato numérico inválido. Digite utilizando o padrão brasileiro (Ex: 150.000,00).")
            v_dcl, v_rcl = float_dcl, float_rcl
            AF = float_dcl / max(float_rcl, 0.01)
            ptsF9 = float(dF9.get("pontos", 0))
            texto_resultado = "Erro na leitura do campo"
            texto_pontuacao = f"{ptsF9:.2f} pontos"
            estilo_status = "color: #dc2626;"

    with c2:
        lF9 = st.text_area("Link/Evidência (F9 - Item GF-28 AUDESP):", value=dF9.get("link", ""), key=f"txt_f9_{ano_sel}_{ctr}", height=150)

    # Exibição do painel consolidador de métricas fiscais decimais
    st.markdown(f"""
    <div style="padding: 12px; background-color: #f1f5f9; border-left: 5px solid #1e3a8a; border-radius: 4px; margin-top: 15px; margin-bottom: 15px;">
        📌 <b>Cálculo da Razão:</b> R$ {v_dcl:,.2f} / R$ {v_rcl:,.2f}<br>
        📊 <b>Resultado do Indicador (AF):</b> <code style="font-size: 15px; font-weight: bold; color: #b45309;">{AF:.4f}</code><br>
        ⚖️ <b>Situação da Dívida Líquida:</b> <span style="{estilo_status}">{texto_resultado}</span><br>
        🎯 <b>Impacto na Pontuação:</b> <code style="font-size: 15px; font-weight: bold; color: #1e40af;">{texto_pontuacao}</code>
    </div>
    """.replace(", ", "X").replace(".", ",").replace("X", "."), unsafe_allow_html=True)

    # Verificação de alteração de dados para gatilho de persistência e invalidação de chaves textuais
    string_banco_atual = f"{v_dcl:.2f}/{v_rcl:.2f}"
    string_banco_salva = f"{float_dcl:.2f}/{float_rcl:.2f}"  # Corrigido aqui de float_ad para float_rcl

    if string_banco_atual != string_banco_salva or lF9 != dF9["link"]:
        save_resp("F9", string_banco_atual, ptsF9, lF9)
        
        # Incrementa individualmente as chaves correspondentes aos valores modificados
        if f"{v_dcl:.2f}" != f"{float_dcl:.2f}":
            st.session_state[f"f9_dcl_key_suffix_{ano_sel}"] += 1
        if f"{v_rcl:.2f}" != f"{float_rcl:.2f}":
            st.session_state[f"f9_rcl_key_suffix_{ano_sel}"] += 1
            
        st.rerun()

    bloco_comentarios("F9", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # F10 • Apuração dos Pagamentos dos Precatórios
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("F10 • Apuração dos Pagamentos dos Precatórios (AG / AH)")
    st.write("**Razão entre o Estoque Final e o Estoque Inicial de Precatórios [AG / AH = AI]**")

    # Tabela de Regras de Pontuação
    st.markdown(r"""
    | Resultado do Índice $AI$ | Impacto / Pontuação do Indicador |
    | :--- | :--- |
    | Menor ou igual a 0,9 ($\le 0,9$) | ✅ 75 pontos (Pontuação Máxima) |
    | Entre 0,9 e 1,0 ($> 0,9$ e $< 1,0$) | ⚠️ Graduação entre 0 e 75 pontos |
    | Maior ou igual a 1,0 ($\ge 1,0$) | 🚨 00 ponto (Sem bonificação) |
    """)
    st.caption("ℹ️ *Dados extraídos da contabilidade encaminhada pelo Sistema AUDESP.*")

    # 📝 Memória de cálculo oficial fornecida
    st.markdown("""
    <div style="background-color: #f8fafc; padding: 12px; border-radius: 4px; border-left: 3px solid #64748b; margin-bottom: 15px;">
        <p style="margin-bottom: 8px; font-size: 13px;">📊 <b>Regra de Distribuição Proporcional no Intervalo Crítico:</b></p>
        <ul style="font-size: 13px; margin-left: 15px; padding-left: 0px;">
            <li><b>Para resultados maiores que 0,90 e menores que 1,00:</b> A graduação será distribuída igualitariamente no intervalo através da fórmula: <br><code style="background-color: #e2e8f0; padding: 2px 5px;">((AI – 1,0) * (-1) / 0,10) * 75</code> <br><i>Exemplo: se AI = 0,95, a nota do indicador será exatamente 37,50 pontos.</i></li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    # Inicializa os sufixos de controle no session_state para gerenciar o cache de forma isolada
    if f"f10_ag_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f10_ag_key_suffix_{ano_sel}"] = 0
    if f"f10_ah_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f10_ah_key_suffix_{ano_sel}"] = 0

    # Carrega ou inicializa a string persistida no banco contendo a dupla de valores (AG/AH)
    dF10 = res_data.get("F10", {"valor": "0.00/1.00", "pontos": 0, "link": ""})

    try:
        val_salvo_ag, val_salvo_ah = dF10["valor"].split("/")
        float_ag = float(val_salvo_ag)
        float_ah = float(val_salvo_ah)
    except:
        float_ag, float_ah = 0.0, 1.0

    # Converte os números salvos na máscara brasileira de apresentação monetária (R$)
    str_inicial_ag = f"R$ {float_ag:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    str_inicial_ah = f"R$ {float_ah:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    c1, c2 = st.columns([1, 2])

    with c1:
        # Input 1: Estoque Final dos Precatórios (AG)
        sufixo_ag = st.session_state[f"f10_ag_key_suffix_{ano_sel}"]
        input_ag_str = st.text_input(
            "Estoque Final dos Precatórios (AG) - R$:",
            value=str_inicial_ag,
            placeholder="Ex: 950.000,00",
            key=f"txt_f10_ag_dinamico_{ano_sel}_{sufixo_ag}_{ctr}"
        )
        
        # Input 2: Estoque Inicial dos Precatórios (AH)
        sufixo_ah = st.session_state[f"f10_ah_key_suffix_{ano_sel}"]
        input_ah_str = st.text_input(
            "Estoque Inicial dos Precatórios (AH) - R$:",
            value=str_inicial_ah,
            placeholder="Ex: 1.000.000,00",
            key=f"txt_f10_ah_dinamico_{ano_sel}_{sufixo_ah}_{ctr}"
        )

        # 🧹 Função interna para higienizar strings monetárias do padrão BR
        def limpa_conversao_monetaria(texto):
            num_limpo = texto.replace("R$", "").replace(" ", "")
            if "." in num_limpo and "," in num_limpo:
                num_limpo = num_limpo.replace(".", "").replace(",", ".")
            elif "," in num_limpo:
                num_limpo = num_limpo.replace(",", ".")
            return float(num_limpo)

        # Tratamento lógico e cálculo dinâmico do indicador AI
        try:
            v_ag = limpa_conversao_monetaria(input_ag_str)
            v_ah = max(limpa_conversao_monetaria(input_ah_str), 0.01) # Evita divisão por zero
            
            # Cálculo do Indicador AI (Decimal Puro)
            AI = round(v_ag / v_ah, 4)
            
            # 🛑 TRAVA DE INICIALIZAÇÃO
            if v_ag == 0.0 and (dF10.get("link", "").strip() == ""):
                ptsF10 = 0.0
                texto_resultado = "Aguardando preenchimento..."
                texto_pontuacao = "⏳ 0,00 pontos"
                estilo_status = "color: #64748b;"
            else:
                # 🧮 MOTOR DE REGRAS
                if AI <= 0.9000:
                    ptsF10 = 75.0
                    texto_resultado = "✅ REGULAR: Redução Ótima do Estoque (≤ 0,90)"
                    estilo_status = "color: #16a34a; font-weight: bold;"
                elif 0.9000 < AI < 1.0000:
                    ptsF10 = ((AI - 1.0000) * (-1.0) / 0.1000) * 75.0
                    texto_resultado = "⚠️ ALERTA DE GRADUAÇÃO (Redução Parcial)"
                    estilo_status = "color: #d97706; font-weight: bold;"
                else: # AI >= 1.0000
                    ptsF10 = 0.0
                    texto_resultado = "🚨 CRÍTICO: Estoque Mantido ou Aumentado (≥ 1,00)"
                    estilo_status = "color: #dc2626; font-weight: bold;"
                
                texto_pontuacao = f"{ptsF10:.2f} pontos"
                
        except ValueError:
            st.error("⚠️ Formato numérico inválido. Digite utilizando o padrão brasileiro (Ex: 150.000,00).")
            v_ag, v_ah = float_ag, float_ah
            AI = float_ag / max(float_ah, 0.01)
            ptsF10 = float(dF10.get("pontos", 0))
            texto_resultado = "Erro na leitura do campo"
            texto_pontuacao = f"{ptsF10:.2f} pontos"
            estilo_status = "color: #dc2626;"

    with c2:
        lF10 = st.text_area("Link/Evidência (F10 - Precatórios AUDESP):", value=dF10.get("link", ""), key=f"txt_f10_{ano_sel}_{ctr}", height=150)

    # Exibição do painel consolidador de métricas fiscais decimais
    st.markdown(f"""
    <div style="padding: 12px; background-color: #f1f5f9; border-left: 5px solid #1e3a8a; border-radius: 4px; margin-top: 15px; margin-bottom: 15px;">
        📌 <b>Cálculo da Razão:</b> R$ {v_ag:,.2f} / R$ {v_ah:,.2f}<br>
        📊 <b>Resultado do Indicador (AI):</b> <code style="font-size: 15px; font-weight: bold; color: #b45309;">{AI:.4f}</code><br>
        ⚖️ <b>Situação do Estoque:</b> <span style="{estilo_status}">{texto_resultado}</span><br>
        🎯 <b>Impacto na Pontuação:</b> <code style="font-size: 15px; font-weight: bold; color: #1e40af;">{texto_pontuacao}</code>
    </div>
    """.replace(", ", "X").replace(".", ",").replace("X", "."), unsafe_allow_html=True)

    # Verificação de alteração de dados para gatilho de persistência
    string_banco_atual = f"{v_ag:.2f}/{v_ah:.2f}"
    string_banco_salva = f"{float_ag:.2f}/{float_ah:.2f}"

    if string_banco_atual != string_banco_salva or lF10 != dF10["link"]:
        save_resp("F10", string_banco_atual, ptsF10, lF10)
        
        if f"{v_ag:.2f}" != f"{float_ag:.2f}":
            st.session_state[f"f10_ag_key_suffix_{ano_sel}"] += 1
        if f"{v_ah:.2f}" != f"{float_ah:.2f}":
            st.session_state[f"f10_ah_key_suffix_{ano_sel}"] += 1
            
        st.rerun()

    bloco_comentarios("F10", res_data)
    st.markdown('</div>', unsafe_allow_html=True)
        
    # F11 • Repasse de Duodécimos às Câmaras
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("F11 • Repasse de Duodécimos às Câmaras (Valor Repassado / RCL)")
    st.write("**Razão entre as Transferências à Câmara e a Receita Corrente Líquida**")

    # Tabela de Regras de Pontuação
    st.markdown(r"""
    | Percentual de Repasse | Impacto / Pontuação do Indicador |
    | :--- | :--- |
    | Menor ou igual a 6,00% ($\le 6\%$) | ✅ 00 ponto (Sem penalidades / Regular) |
    | Maior que 6,00% ($> 6\%$) | 🚨 **REBAIXAR IEG-M PARA FAIXA C** (Nota Geral afetada) |
    """)
    st.caption("ℹ️ *Dados extraídos com base no item 'Transferências à Câmara dos Vereadores' do modelo de relatório de contas municipais do Sistema AUDESP.*")

    # Inicializa os sufixos de controle no session_state para gerenciar o cache de forma isolada
    if f"f11_rep_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f11_rep_key_suffix_{ano_sel}"] = 0
    if f"f11_rcl_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f11_rcl_key_suffix_{ano_sel}"] = 0

    # Carrega ou inicializa a string persistida no banco contendo a dupla de valores (Repasse/RCL)
    dF11 = res_data.get("F11", {"valor": "0.00/1.00", "pontos": 0, "link": ""})

    try:
        val_salvo_rep, val_salvo_rcl = dF11["valor"].split("/")
        float_rep = float(val_salvo_rep)
        float_rcl = float(val_salvo_rcl)
    except:
        float_rep, float_rcl = 0.0, 1.0

    # Converte os números salvos na máscara brasileira de apresentação monetária (R$)
    str_inicial_rep = f"R$ {float_rep:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    str_inicial_rcl = f"R$ {float_rcl:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    c1, c2 = st.columns([1, 2])

    with c1:
        # Input 1: Valor Repassado à Câmara
        sufixo_rep = st.session_state[f"f11_rep_key_suffix_{ano_sel}"]
        input_rep_str = st.text_input(
            "Transferências à Câmara dos Vereadores - R$:",
            value=str_inicial_rep,
            placeholder="Ex: 600.000,00",
            key=f"txt_f11_rep_dinamico_{ano_sel}_{sufixo_rep}_{ctr}"
        )
        
        # Input 2: Receita Corrente Líquida (RCL) - Reutilizada do contexto fiscal
        sufixo_rcl = st.session_state[f"f11_rcl_key_suffix_{ano_sel}"]
        input_rcl_str = st.text_input(
            "Receita Corrente Líquida (RCL) - R$ (F11):",
            value=str_inicial_rcl,
            placeholder="Ex: 10.000.000,00",
            key=f"txt_f11_rcl_dinamico_{ano_sel}_{sufixo_rcl}_{ctr}"
        )

        # 🧹 Função interna para higienizar strings monetárias do padrão BR
        def limpa_conversao_monetaria(texto):
            num_limpo = texto.replace("R$", "").replace(" ", "")
            if "." in num_limpo and "," in num_limpo:
                num_limpo = num_limpo.replace(".", "").replace(",", ".")
            elif "," in num_limpo:
                num_limpo = num_limpo.replace(",", ".")
            return float(num_limpo)

        # Tratamento lógico e cálculo dinâmico do percentual
        try:
            v_rep = limpa_conversao_monetaria(input_rep_str)
            v_rcl = max(limpa_conversao_monetaria(input_rcl_str), 0.01) # Evita divisão por zero
            
            # Cálculo do Percentual do Limite (Ex: 0.0540 = 5,40%)
            perc_repasse = round(v_rep / v_rcl, 4)
            perc_exibicao = perc_repasse * 100
            
            # 🛑 TRAVA DE INICIALIZAÇÃO
            if v_rep == 0.0 and (dF11.get("link", "").strip() == ""):
                ptsF11 = 0.0
                texto_resultado = "Aguardando preenchimento..."
                texto_pontuacao = "⏳ Verificar Limite"
                estilo_status = "color: #64748b;"
            else:
                # 🧮 MOTOR DE REGRAS: Limite Constitucional de 6%
                if perc_repasse > 0.0600:
                    ptsF11 = 0.0
                    texto_resultado = "🚨 CRÍTICO: Limite Excedido! Rebaixar IEG-M para Faixa C"
                    estilo_status = "color: #dc2626; font-weight: bold;"
                else:
                    ptsF11 = 0.0
                    texto_resultado = "✅ REGULAR: Dentro do teto constitucional de 6%"
                    estilo_status = "color: #16a34a; font-weight: bold;"
                
                texto_pontuacao = "0,00 pontos"
                
        except ValueError:
            st.error("⚠️ Formato numérico inválido. Digite utilizando o padrão brasileiro (Ex: 150.000,00).")
            v_rep, v_rcl = float_rep, float_rcl
            perc_exibicao = (float_rep / max(float_rcl, 0.01)) * 100
            ptsF11 = float(dF11.get("pontos", 0))
            texto_resultado = "Erro na leitura do campo"
            texto_pontuacao = f"{ptsF11:.2f} pontos"
            estilo_status = "color: #dc2626;"

    with c2:
        lF11 = st.text_area("Link/Evidência (F11 - Duodécimo Câmara):", value=dF11.get("link", ""), key=f"txt_f11_{ano_sel}_{ctr}", height=150)

    # Exibição do painel consolidador de métricas fiscais decimais
    st.markdown(f"""
    <div style="padding: 12px; background-color: #f1f5f9; border-left: 5px solid #1e3a8a; border-radius: 4px; margin-top: 15px; margin-bottom: 15px;">
        📌 <b>Cálculo do Repasse:</b> (R$ {v_rep:,.2f} / R$ {v_rcl:,.2f}) * 100<br>
        📊 <b>Percentual Apurado:</b> <code style="font-size: 15px; font-weight: bold; color: #b45309;">{perc_exibicao:.2f}%</code> (Limite: 6,00%)<br>
        ⚖️ <b>Situação Constitucional:</b> <span style="{estilo_status}">{texto_resultado}</span><br>
        🎯 <b>Impacto na Pontuação:</b> <code style="font-size: 15px; font-weight: bold; color: #1e40af;">{texto_pontuacao}</code>
    </div>
    """.replace(", ", "X").replace(".", ",").replace("X", "."), unsafe_allow_html=True)

    # Verificação de alteração de dados para gatilho de persistência
    string_banco_atual = f"{v_rep:.2f}/{v_rcl:.2f}"
    string_banco_salva = f"{float_rep:.2f}/{float_rcl:.2f}"

    if string_banco_atual != string_banco_salva or lF11 != dF11["link"]:
        save_resp("F11", string_banco_atual, ptsF11, lF11)
        
        if f"{v_rep:.2f}" != f"{float_rep:.2f}":
            st.session_state[f"f11_rep_key_suffix_{ano_sel}"] += 1
        if f"{v_rcl:.2f}" != f"{float_rcl:.2f}":
            st.session_state[f"f11_rcl_key_suffix_{ano_sel}"] += 1
            
        st.rerun()

    bloco_comentarios("F11", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # F12 • Pontualidade na Prestação de Contas
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("F12 • Pontualidade na Prestação de Contas")
    st.write("**Cumprimento dos prazos de envio de Atas, Pareceres, Balancetes, Mapas de Precatórios e Conciliações**")

    # Tabela de Regras de Pontuação
    st.markdown(r"""
    | Situação da Entrega | Impacto / Pontuação do Indicador |
    | :--- | :--- |
    | Encaminhou no prazo | ✅ 50 pontos (Pontuação Máxima) |
    | Encaminhou fora do prazo | ⚠️ 25 pontos (Penalidade Parcial) |
    | Não encaminhou | 🚨 00 ponto (Sem pontuação) |
    """)
    st.caption("ℹ️ *Informações extraídas do Sistema AUDESP – Relatório de Situação de Entrega.*")

    # Carrega ou inicializa a string persistida no banco contendo o status salvo
    dF12 = res_data.get("F12", {"valor": "Aguardando preenchimento...", "pontos": 0, "link": ""})
    val_salvo_status = dF12["valor"]

    c1, c2 = st.columns([1, 2])

    with c1:
        # Mapeamento de opções do Audesp
        opcoes_status = [
            "Aguardando preenchimento...",
            "Encaminhou no prazo",
            "Encaminhou fora do prazo",
            "Não encaminhou"
        ]
        
        # Define o índice inicial com base no que veio do banco de dados
        try:
            idx_inicial = opcoes_status.index(val_salvo_status)
        except ValueError:
            idx_inicial = 0

        # Input: Selectbox para escolha da situação observada no relatório
        status_selecionado = st.selectbox(
            "Situação da entrega dos documentos no AUDESP:",
            options=opcoes_status,
            index=idx_inicial,
            key=f"sb_f12_status_{ano_sel}_{ctr}"
        )

        # 🧮 MOTOR DE REGRAS: Aplicação direta da pontuação por status
        if status_selecionado == "Encaminhou no prazo":
            ptsF12 = 50.0
            texto_resultado = "✅ REGULAR: Documentação enviada tempestivamente"
            estilo_status = "color: #16a34a; font-weight: bold;"
            texto_pontuacao = "50,00 pontos"
        elif status_selecionado == "Encaminhou fora do prazo":
            ptsF12 = 25.0
            texto_resultado = "⚠️ ALERTA: Remessa em atraso apurada no relatório"
            estilo_status = "color: #d97706; font-weight: bold;"
            texto_pontuacao = "25,00 pontos"
        elif status_selecionado == "Não encaminhou":
            ptsF12 = 0.0
            texto_resultado = "🚨 CRÍTICO: Ausência de prestação de contas obrigatória"
            estilo_status = "color: #dc2626; font-weight: bold;"
            texto_pontuacao = "0,00 pontos"
        else:
            ptsF12 = 0.0
            texto_resultado = "Aguardando seleção do status..."
            estilo_status = "color: #64748b;"
            texto_pontuacao = "⏳ 0,00 pontos"

    with c2:
        lF12 = st.text_area("Link/Evidência (F12 - Situação de Entrega AUDESP):", value=dF12.get("link", ""), key=f"txt_f12_{ano_sel}_{ctr}", height=150)

    # Exibição do painel consolidador de métricas fiscais decimais
    st.markdown(f"""
    <div style="padding: 12px; background-color: #f1f5f9; border-left: 5px solid #1e3a8a; border-radius: 4px; margin-top: 15px; margin-bottom: 15px;">
        📌 <b>Critério Avaliado:</b> Atas, Pareceres, Balancetes, Precatórios, Conciliações e Questionário IEG-M<br>
        ⚖️ <b>Status da Prestação:</b> <span style="{estilo_status}">{texto_resultado}</span><br>
        🎯 <b>Impacto na Pontuação:</b> <code style="font-size: 15px; font-weight: bold; color: #1e40af;">{texto_pontuacao}</code>
    </div>
    """, unsafe_allow_html=True)

    # Verificação de alteração de dados para gatilho de persistência
    if status_selecionado != val_salvo_status or lF12 != dF12["link"]:
        save_resp("F12", status_selecionado, ptsF12, lF12)
        st.rerun()

    bloco_comentarios("F12", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # F13 • Dívida Ativa: Percentual de Recebimento
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("F13 • Dívida Ativa: Percentual de Recebimento (AL)")
    st.write("**Nível de recebimento da dívida em relação ao estoque inicial**")

    # Tabela de Regras de Pontuação
    st.markdown(r"""
    | Resultado do Índice $AL$ | Impacto / Pontuação do Indicador |
    | :--- | :--- |
    | Igual a 0 ($AL = 0$) | 🚨 00 ponto (Sem arrecadação) |
    | Entre 0,0 e 0,1 ($> 0,0$ e $< 0,1$) | ⚠️ Graduação entre 0 e 50 pontos |
    | Maior ou igual a 0,10 ($\ge 0,10$) | ✅ 50 pontos (Arrecadação Excelente) |
    """)
    st.caption("ℹ️ *Dados extraídos do Relatório de Análises Anuais Eletrônicas do Sistema AUDESP.*")

    # 📝 Memória de cálculo oficial fornecida
    st.markdown("""
    <div style="background-color: #f8fafc; padding: 12px; border-radius: 4px; border-left: 3px solid #64748b; margin-bottom: 15px;">
        <p style="margin-bottom: 8px; font-size: 13px;">📊 <b>Regra de Distribuição Proporcional no Intervalo Intermediário:</b></p>
        <ul style="font-size: 13px; margin-left: 15px; padding-left: 0px;">
            <li><b>Para resultados maiores que 0,00 e menores que 0,10:</b> A graduação será distribuída igualitariamente no intervalo através da fórmula: <br><code style="background-color: #e2e8f0; padding: 2px 5px;">(AL / 0,10) * 50</code> <br><i>Exemplo: se AL = 0,0500 (5% de recebimento), a nota do indicador será exatamente 25,00 pontos.</i></li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    # Inicializa os sufixos de controle no session_state para gerenciar o cache de forma isolada
    if f"f13_rec_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f13_rec_key_suffix_{ano_sel}"] = 0
    if f"f13_est_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f13_est_key_suffix_{ano_sel}"] = 0

    # Carrega ou inicializa a string persistida no banco contendo a dupla de valores (Arrecadado/Estoque)
    dF13 = res_data.get("F13", {"valor": "0.00/1.00", "pontos": 0, "link": ""})

    try:
        val_salvo_rec, val_salvo_est = dF13["valor"].split("/")
        float_rec = float(val_salvo_rec)
        float_est = float(val_salvo_est)
    except:
        float_rec, float_est = 0.0, 1.0

    # Converte os números salvos na máscara brasileira de apresentação monetária (R$)
    str_inicial_rec = f"R$ {float_rec:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    str_inicial_est = f"R$ {float_est:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    c1, c2 = st.columns([1, 2])

    with c1:
        # Input 1: Valor Recebido da Dívida Ativa
        sufixo_rec = st.session_state[f"f13_rec_key_suffix_{ano_sel}"]
        input_rec_str = st.text_input(
            "Valor Arrecadado de Dívida Ativa - R$:",
            value=str_inicial_rec,
            placeholder="Ex: 50.000,00",
            key=f"txt_f13_rec_dinamico_{ano_sel}_{sufixo_rec}_{ctr}"
        )
        
        # Input 2: Estoque Inicial da Dívida Ativa
        sufixo_est = st.session_state[f"f13_est_key_suffix_{ano_sel}"]
        input_est_str = st.text_input(
            "Estoque Inicial da Dívida Ativa - R$:",
            value=str_inicial_est,
            placeholder="Ex: 1.000.000,00",
            key=f"txt_f13_est_dinamico_{ano_sel}_{sufixo_est}_{ctr}"
        )

        # 🧹 Função interna para higienizar strings monetárias do padrão BR
        def limpa_conversao_monetaria(texto):
            num_limpo = texto.replace("R$", "").replace(" ", "")
            if "." in num_limpo and "," in num_limpo:
                num_limpo = num_limpo.replace(".", "").replace(",", ".")
            elif "," in num_limpo:
                num_limpo = num_limpo.replace(",", ".")
            return float(num_limpo)

        # Tratamento lógico e cálculo dinâmico do indicador AL
        try:
            v_rec = limpa_conversao_monetaria(input_rec_str)
            v_est = max(limpa_conversao_monetaria(input_est_str), 0.01) # Evita divisão por zero
            
            # Cálculo do Indicador AL (Decimal Puro)
            AL = round(v_rec / v_est, 4)
            
            # 🛑 TRAVA DE INICIALIZAÇÃO
            if v_rec == 0.0 and (dF13.get("link", "").strip() == ""):
                ptsF13 = 0.0
                texto_resultado = "Aguardando preenchimento..."
                texto_pontuacao = "⏳ 0,00 pontos"
                estilo_status = "color: #64748b;"
            else:
                # 🧮 MOTOR DE REGRAS
                if AL == 0.0000:
                    ptsF13 = 0.0
                    texto_resultado = "🚨 CRÍTICO: Nenhuma arrecadação apurada (= 0,00)"
                    estilo_status = "color: #dc2626; font-weight: bold;"
                elif 0.0000 < AL < 0.1000:
                    # Aplicação da fórmula (AL / 0,10) * 50
                    ptsF13 = (AL / 0.1000) * 50.0
                    texto_resultado = "⚠️ ALERTA DE GRADUAÇÃO (Recuperação Intermediária)"
                    estilo_status = "color: #d97706; font-weight: bold;"
                else: # AL >= 0.1000
                    ptsF13 = 50.0
                    texto_resultado = "✅ REGULAR: Índice de recebimento adequado (≥ 10%)"
                    estilo_status = "color: #16a34a; font-weight: bold;"
                
                texto_pontuacao = f"{ptsF13:.2f} pontos"
                
        except ValueError:
            st.error("⚠️ Formato numérico inválido. Digite utilizando o padrão brasileiro (Ex: 150.000,00).")
            v_rec, v_est = float_rec, float_est
            AL = float_rec / max(float_est, 0.01)
            ptsF13 = float(dF13.get("pontos", 0))
            texto_resultado = "Erro na leitura do campo"
            texto_pontuacao = f"{ptsF13:.2f} pontos"
            estilo_status = "color: #dc2626;"

    with c2:
        lF13 = st.text_area("Link/Evidência (F13 - Dívida Ativa AUDESP):", value=dF13.get("link", ""), key=f"txt_f13_{ano_sel}_{ctr}", height=150)

    # Exibição do painel consolidador de métricas fiscais decimais
    st.markdown(f"""
    <div style="padding: 12px; background-color: #f1f5f9; border-left: 5px solid #1e3a8a; border-radius: 4px; margin-top: 15px; margin-bottom: 15px;">
        📌 <b>Cálculo da Razão:</b> R$ {v_rec:,.2f} / R$ {v_est:,.2f}<br>
        📊 <b>Resultado do Indicador (AL):</b> <code style="font-size: 15px; font-weight: bold; color: #b45309;">{AL:.4f}</code> ({AL*100:.2f}% de recebimento)<br>
        ⚖️ <b>Situação da Arrecadação:</b> <span style="{estilo_status}">{texto_resultado}</span><br>
        🎯 <b>Impacto na Pontuação:</b> <code style="font-size: 15px; font-weight: bold; color: #1e40af;">{texto_pontuacao}</code>
    </div>
    """.replace(", ", "X").replace(".", ",").replace("X", "."), unsafe_allow_html=True)

    # Verificação de alteração de dados para gatilho de persistência
    string_banco_atual = f"{v_rec:.2f}/{v_est:.2f}"
    string_banco_salva = f"{float_rec:.2f}/{float_est:.2f}"

    if string_banco_atual != string_banco_salva or lF13 != dF13["link"]:
        save_resp("F13", string_banco_atual, ptsF13, lF13)
        
        if f"{v_rec:.2f}" != f"{float_rec:.2f}":
            st.session_state[f"f13_rec_key_suffix_{ano_sel}"] += 1
        if f"{v_est:.2f}" != f"{float_est:.2f}":
            st.session_state[f"f13_est_key_suffix_{ano_sel}"] += 1
            
        st.rerun()

    bloco_comentarios("F13", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # F14 • Dívida Ativa: Percentual de Cancelamento
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("F14 • Dívida Ativa: Percentual de Cancelamento (AM)")
    st.write("**Nível de cancelamento da dívida em relação ao estoque inicial**")

    # Tabela de Regras de Pontuação
    st.markdown(r"""
    | Resultado do Índice $AM$ | Impacto / Pontuação do Indicador |
    | :--- | :--- |
    | Igual a 0 ($AM = 0$) | ✅ 50 pontos (Pontuação Máxima) |
    | Entre 0,0 e 0,1 ($> 0,0$ e $< 0,1$) | ⚠️ Graduação entre 50 e 0 pontos |
    | Maior ou igual a 0,10 ($\ge 0,10$) | 🚨 00 ponto (Cancelamento Excessivo) |
    """)
    st.caption("ℹ️ *Dados extraídos do Relatório de Análises Anuais Eletrônicas do Sistema AUDESP.*")

    # 📝 Memória de cálculo oficial fornecida
    st.markdown("""
    <div style="background-color: #f8fafc; padding: 12px; border-radius: 4px; border-left: 3px solid #64748b; margin-bottom: 15px;">
        <p style="margin-bottom: 8px; font-size: 13px;">📊 <b>Regra de Distribuição Proporcional Regressiva no Intervalo:</b></p>
        <ul style="font-size: 13px; margin-left: 15px; padding-left: 0px;">
            <li><b>Para resultados maiores que 0,00 e menores que 0,10:</b> A graduação decrescerá igualitariamente no intervalo através da fórmula: <br><code style="background-color: #e2e8f0; padding: 2px 5px;">((AM – 0,10) * (-1) / 0,10) * 50</code> <br><i>Exemplo: se AM = 0,0500 (5% de cancelamento), a nota do indicador será exatamente 25,00 pontos.</i></li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    # Inicializa os sufixos de controle no session_state para gerenciar o cache de forma isolada
    if f"f14_can_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f14_can_key_suffix_{ano_sel}"] = 0
    if f"f14_est_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f14_est_key_suffix_{ano_sel}"] = 0

    # Carrega ou inicializa a string persistida no banco contendo a dupla de valores (Cancelado/Estoque)
    dF14 = res_data.get("F14", {"valor": "0.00/1.00", "pontos": 50, "link": ""})

    try:
        val_salvo_can, val_salvo_est = dF14["valor"].split("/")
        float_can = float(val_salvo_can)
        float_est = float(val_salvo_est)
    except:
        float_can, float_est = 0.0, 1.0

    # Converte os números salvos na máscara brasileira de apresentação monetária (R$)
    str_inicial_can = f"R$ {float_can:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    str_inicial_est = f"R$ {float_est:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    c1, c2 = st.columns([1, 2])

    with c1:
        # Input 1: Valor Cancelado da Dívida Ativa
        sufixo_can = st.session_state[f"f14_can_key_suffix_{ano_sel}"]
        input_can_str = st.text_input(
            "Valor Cancelado de Dívida Ativa - R$:",
            value=str_inicial_can,
            placeholder="Ex: 10.000,00",
            key=f"txt_f14_can_dinamico_{ano_sel}_{sufixo_can}_{ctr}"
        )
        
        # Input 2: Estoque Inicial da Dívida Ativa
        sufixo_est = st.session_state[f"f14_est_key_suffix_{ano_sel}"]
        input_est_str = st.text_input(
            "Estoque Inicial da Dívida Ativa - R$ (F14):",
            value=str_inicial_est,
            placeholder="Ex: 1.000.000,00",
            key=f"txt_f14_est_dinamico_{ano_sel}_{sufixo_est}_{ctr}"
        )

        # 🧹 Função interna para higienizar strings monetárias do padrão BR
        def limpa_conversao_monetaria(texto):
            num_limpo = texto.replace("R$", "").replace(" ", "")
            if "." in num_limpo and "," in num_limpo:
                num_limpo = num_limpo.replace(".", "").replace(",", ".")
            elif "," in num_limpo:
                num_limpo = num_limpo.replace(",", ".")
            return float(num_limpo)

        # Tratamento lógico e cálculo dinâmico do indicador AM
        try:
            v_can = limpa_conversao_monetaria(input_can_str)
            v_est = max(limpa_conversao_monetaria(input_est_str), 0.01) # Evita divisão por zero
            
            # Cálculo do Indicador AM (Decimal Puro)
            AM = round(v_can / v_est, 4)
            
            # 🛑 TRAVA DE INICIALIZAÇÃO: Se o cancelamento estiver zerado e sem link, não força 50 automático antes do preenchimento
            if v_can == 0.0 and (dF14.get("link", "").strip() == ""):
                ptsF14 = 0.0
                texto_resultado = "Aguardando preenchimento..."
                texto_pontuacao = "⏳ 0,00 pontos"
                estilo_status = "color: #64748b;"
            else:
                # 🧮 MOTOR DE REGRAS
                if AM == 0.0000:
                    ptsF14 = 50.0
                    texto_resultado = "✅ EXCELENTE: Nenhum cancelamento efetuado (= 0,00)"
                    estilo_status = "color: #16a34a; font-weight: bold;"
                elif 0.0000 < AM < 0.1000:
                    # Aplicação exata da fórmula ((AM - 0.10) * (-1) / 0.10) * 50
                    ptsF14 = ((AM - 0.1000) * (-1.0) / 0.1000) * 50.0
                    texto_resultado = "⚠️ ALERTA DE GRADUAÇÃO (Baixa Parcial do Estoque)"
                    estilo_status = "color: #d97706; font-weight: bold;"
                else: # AM >= 0.1000
                    ptsF14 = 0.0
                    texto_resultado = "🚨 CRÍTICO: Índice de cancelamento muito elevado (≥ 10%)"
                    estilo_status = "color: #dc2626; font-weight: bold;"
                
                texto_pontuacao = f"{ptsF14:.2f} pontos"
                
        except ValueError:
            st.error("⚠️ Formato numérico inválido. Digite utilizando o padrão brasileiro (Ex: 150.000,00).")
            v_can, v_est = float_can, float_est
            AM = float_can / max(float_est, 0.01)
            ptsF14 = float(dF14.get("pontos", 0))
            texto_resultado = "Erro na leitura do campo"
            texto_pontuacao = f"{ptsF14:.2f} pontos"
            estilo_status = "color: #dc2626;"

    with c2:
        lF14 = st.text_area("Link/Evidência (F14 - Cancelamento Dívida Ativa):", value=dF14.get("link", ""), key=f"txt_f14_{ano_sel}_{ctr}", height=150)

    # Exibição do painel consolidador de métricas fiscais decimais
    st.markdown(f"""
    <div style="padding: 12px; background-color: #f1f5f9; border-left: 5px solid #1e3a8a; border-radius: 4px; margin-top: 15px; margin-bottom: 15px;">
        📌 <b>Cálculo da Razão:</b> R$ {v_can:,.2f} / R$ {v_est:,.2f}<br>
        📊 <b>Resultado do Indicador (AM):</b> <code style="font-size: 15px; font-weight: bold; color: #b45309;">{AM:.4f}</code> ({AM*100:.2f}% de cancelamento)<br>
        ⚖️ <b>Situação do Estoque:</b> <span style="{estilo_status}">{texto_resultado}</span><br>
        🎯 <b>Impacto na Pontuação:</b> <code style="font-size: 15px; font-weight: bold; color: #1e40af;">{texto_pontuacao}</code>
    </div>
    """.replace(", ", "X").replace(".", ",").replace("X", "."), unsafe_allow_html=True)

    # Verificação de alteração de dados para gatilho de persistência
    string_banco_atual = f"{v_can:.2f}/{v_est:.2f}"
    string_banco_salva = f"{float_can:.2f}/{float_est:.2f}"

    if string_banco_atual != string_banco_salva or lF14 != dF14["link"]:
        save_resp("F14", string_banco_atual, ptsF14, lF14)
        
        if f"{v_can:.2f}" != f"{float_can:.2f}":
            st.session_state[f"f14_can_key_suffix_{ano_sel}"] += 1
        if f"{v_est:.2f}" != f"{float_est:.2f}":
            st.session_state[f"f14_est_key_suffix_{ano_sel}"] += 1
            
        st.rerun()

    bloco_comentarios("F14", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # F15 • Alertas do Sistema AUDESP
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("F15 • Alertas do Sistema AUDESP")
    st.write("**Quantidade total de alertas gerados pelo sistema eletrônico no exercício**")

    # Tabela de Regras de Pontuação
    st.markdown(r"""
    | Quantidade de Alertas | Impacto / Pontuação do Indicador |
    | :--- | :--- |
    | Menor ou igual a 20 ($\le 20$) | ✅ 25 pontos (Pontuação Máxima) |
    | Entre 21 e 40 ($> 20$ e $< 41$) | ⚠️ 10 pontos (Atenção / Nota Parcial) |
    | Maior ou igual a 41 ($\ge 41$) | 🚨 00 ponto (Volume Crítico de Alertas) |
    """)
    st.caption("ℹ *Informações extraídas do módulo de controle do Sistema AUDESP.*")

    # Carrega ou inicializa a string persistida no banco contendo o valor numérico
    dF15 = res_data.get("F15", {"valor": "0", "pontos": 0, "link": ""})
    
    try:
        val_salvo_alertas = int(float(dF15["valor"]))
    except:
        val_salvo_alertas = 0

    c1, c2 = st.columns([1, 2])

    with c1:
        # Input: Número inteiro para contagem absoluta dos alertas gerados
        qtd_alertas = st.number_input(
            "Quantidade total de alertas gerados no ano:",
            min_value=0,
            max_value=9999,
            value=val_salvo_alertas,
            step=1,
            format="%d",
            key=f"num_f15_alertas_{ano_sel}_{ctr}"
        )

        # 🧮 MOTOR DE REGRAS: Avaliação por faixas discretas de tolerância fiscal
        if qtd_alertas <= 20:
            ptsF15 = 25.0
            texto_resultado = f"✅ ADEQUADO: Baixo volume de alertas ({qtd_alertas})"
            estilo_status = "color: #16a34a; font-weight: bold;"
            texto_pontuacao = "25,00 pontos"
        elif 20 < qtd_alertas < 41:
            ptsF15 = 10.0
            texto_resultado = f"⚠️ ATENÇÃO: Volume moderado de inconformidades ({qtd_alertas})"
            estilo_status = "color: #d97706; font-weight: bold;"
            texto_pontuacao = "10,00 pontos"
        else: # qtd_alertas >= 41
            ptsF15 = 0.0
            texto_resultado = f"🚨 EXCESSO: Alto índice de ocorrências sistêmicas ({qtd_alertas})"
            estilo_status = "color: #dc2626; font-weight: bold;"
            texto_pontuacao = "0,00 pontos"

    with c2:
        lF15 = st.text_area("Link/Evidência (F15 - Painel de Alertas AUDESP):", value=dF15.get("link", ""), key=f"txt_f15_{ano_sel}_{ctr}", height=150)

    # Exibição do painel consolidador de métricas fiscais decimais
    st.markdown(f"""
    <div style="padding: 12px; background-color: #f1f5f9; border-left: 5px solid #1e3a8a; border-radius: 4px; margin-top: 15px; margin-bottom: 15px;">
        📌 <b>Métrica Avaliada:</b> Concentração de inconformidades contábeis e de gestão<br>
        ⚖️ <b>Situação Institucional:</b> <span style="{estilo_status}">{texto_resultado}</span><br>
        🎯 <b>Impacto na Pontuação:</b> <code style="font-size: 15px; font-weight: bold; color: #1e40af;">{texto_pontuacao}</code>
    </div>
    """, unsafe_allow_html=True)

    # Verificação de alteração de dados para gatilho de persistência
    if qtd_alertas != val_salvo_alertas or lF15 != dF15["link"]:
        save_resp("F15", str(qtd_alertas), ptsF15, lF15)
        st.rerun()

    bloco_comentarios("F15", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # F16 • Balancetes Rejeitados
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("F16 • Balancetes Rejeitados")
    st.write("**Quantidade total de balancetes mensais rejeitados no exercício**")

    # Tabela de Regras de Pontuação
    st.markdown(r"""
    | Balancetes Rejeitados | Impacto / Pontuação do Indicador |
    | :--- | :--- |
    | Menor ou igual a 1 ($\le 1$) | ✅ 25 pontos (Pontuação Máxima) |
    | Entre 2 e 17 ($> 1$ e $< 18$) | ⚠️ 10 pontos (Atenção / Nota Parcial) |
    | Maior ou igual a 18 ($\ge 18$) | 🚨 00 ponto (Volume Crítico de Rejeições) |
    """)
    st.caption("ℹ️ *Informações apuradas com base nas notificações de rejeição do Sistema AUDESP.*")

    # Carrega ou inicializa a string persistida no banco contendo o valor numérico
    dF16 = res_data.get("F16", {"valor": "0", "pontos": 0, "link": ""})
    
    try:
        val_salvo_rejeitados = int(float(dF16["valor"]))
    except:
        val_salvo_rejeitados = 0

    c1, c2 = st.columns([1, 2])

    with c1:
        # Input: Número inteiro para contagem absoluta das rejeições de balancetes
        qtd_rejeitados = st.number_input(
            "Quantidade de balancetes rejeitados no ano:",
            min_value=0,
            max_value=120,  # Margem segura considerando múltiplos órgãos/consórcios
            value=val_salvo_rejeitados,
            step=1,
            format="%d",
            key=f"num_f16_rejeitados_{ano_sel}_{ctr}"
        )

        # 🧮 MOTOR DE REGRAS: Avaliação por faixas de corte descritas
        if qtd_rejeitados <= 1:
            ptsF16 = 25.0
            texto_resultado = f"✅ ADEQUADO: Índice de rejeição mínimo ({qtd_rejeitados})"
            estilo_status = "color: #16a34a; font-weight: bold;"
            texto_pontuacao = "25,00 pontos"
        elif 1 < qtd_rejeitados < 18:
            ptsF16 = 10.0
            texto_resultado = f"⚠️ ATENÇÃO: Rejeições recorrentes identificadas ({qtd_rejeitados})"
            estilo_status = "color: #d97706; font-weight: bold;"
            texto_pontuacao = "10,00 pontos"
        else: # qtd_rejeitados >= 18
            ptsF16 = 0.0
            texto_resultado = f"🚨 EXCESSO: Volume crítico de inconsistências contábeis ({qtd_rejeitados})"
            estilo_status = "color: #dc2626; font-weight: bold;"
            texto_pontuacao = "0,00 pontos"

    with c2:
        lF16 = st.text_area("Link/Evidência (F16 - Histórico de Balancetes AUDESP):", value=dF16.get("link", ""), key=f"txt_f16_{ano_sel}_{ctr}", height=150)

    # Exibição do painel consolidador de métricas fiscais
    st.markdown(f"""
    <div style="padding: 12px; background-color: #f1f5f9; border-left: 5px solid #1e3a8a; border-radius: 4px; margin-top: 15px; margin-bottom: 15px;">
        📌 <b>Métrica Avaliada:</b> Qualidade e consistência das remessas contábeis mensais<br>
        ⚖️ <b>Situação Institucional:</b> <span style="{estilo_status}">{texto_resultado}</span><br>
        🎯 <b>Impacto na Pontuação:</b> <code style="font-size: 15px; font-weight: bold; color: #1e40af;">{texto_pontuacao}</code>
    </div>
    """, unsafe_allow_html=True)

    # Verificação de alteração de dados para gatilho de persistência
    if qtd_rejeitados != val_salvo_rejeitados or lF16 != dF16["link"]:
        save_resp("F16", str(qtd_rejeitados), ptsF16, lF16)
        st.rerun()

    bloco_comentarios("F16", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # F17 • Resultado Primário (Operacional)
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("F17 • Resultado Primário (Operacional) [RP = RR - DL]")
    st.write("**Mede a capacidade do município de reduzir seu endividamento estrutural**")

    # Tabela de Regras de Pontuação
    st.markdown(r"""
    | Resultado Primário ($RP$) | Impacto / Pontuação do Indicador |
    | :--- | :--- |
    | Acima de ZERO ($RP > 0$) | ✅ 75 pontos (Superávit Primário) |
    | Igual a ZERO ($RP = 0$) | ⚠️ 40 pontos (Equilíbrio Limite) |
    | Abaixo de ZERO ($RP < 0$) | 🚨 00 ponto (Déficit Primário) |
    """)
    st.caption("ℹ️ *Dados extraídos da linha 'RESULTADO PRIMÁRIO (VIII-XVII)' do Demonstrativo do Resultado Primário do 6º bimestre (Item GF20 - AUDESP).*")

    # Inicializa os sufixos de controle no session_state para gerenciar o cache de forma isolada
    if f"f17_rr_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f17_rr_key_suffix_{ano_sel}"] = 0
    if f"f17_dl_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f17_dl_key_suffix_{ano_sel}"] = 0

    # Carrega ou inicializa a string persistida no banco contendo a dupla de valores (Receitas/Despesas)
    dF17 = res_data.get("F17", {"valor": "0.00/0.00", "pontos": 40, "link": ""})
    
    try:
        val_salvo_rr, val_salvo_dl = dF17["valor"].split("/")
        float_rr = float(val_salvo_rr)
        float_dl = float(val_salvo_dl)
    except:
        float_rr, float_dl = 0.0, 0.0

    # Converte os números salvos na máscara brasileira de apresentação monetária (R$)
    str_inicial_rr = f"R$ {float_rr:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    str_inicial_dl = f"R$ {float_dl:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    c1, c2 = st.columns([1, 2])

    with c1:
        # Input 1: Receitas Realizadas (RR)
        sufixo_rr = st.session_state[f"f17_rr_key_suffix_{ano_sel}"]
        input_rr_str = st.text_input(
            "Receitas Realizadas (RR) - R$:",
            value=str_inicial_rr,
            placeholder="Ex: 1.500.000,00",
            key=f"txt_f17_rr_dinamico_{ano_sel}_{sufixo_rr}_{ctr}"
        )
        
        # Input 2: Despesas Liquidadas (DL)
        sufixo_dl = st.session_state[f"f17_dl_key_suffix_{ano_sel}"]
        input_dl_str = st.text_input(
            "Despesas Liquidadas (DL) - R$:",
            value=str_inicial_dl,
            placeholder="Ex: 1.400.000,00",
            key=f"txt_f17_dl_dinamico_{ano_sel}_{sufixo_dl}_{ctr}"
        )

        # 🧹 Função interna para higienizar strings monetárias do padrão BR
        def limpa_conversao_monetaria(texto):
            num_limpo = texto.replace("R$", "").replace(" ", "")
            if "." in num_limpo and "," in num_limpo:
                num_limpo = num_limpo.replace(".", "").replace(",", ".")
            elif "," in num_limpo:
                num_limpo = num_limpo.replace(",", ".")
            return float(num_limpo)

        # Tratamento lógico e cálculo dinâmico por subtração
        try:
            v_rr = limpa_conversao_monetaria(input_rr_str)
            v_dl = limpa_conversao_monetaria(input_dl_str)
            
            # Cálculo matemático oficial: RP = RR - DL
            v_rp = round(v_rr - v_dl, 2)
            
            # 🛑 TRAVA DE INICIALIZAÇÃO
            if v_rr == 0.0 and v_dl == 0.0 and (dF17.get("link", "").strip() == ""):
                ptsF17 = 40.0
                texto_resultado = "Aguardando preenchimento..."
                texto_pontuacao = "40,00 pontos"
                estilo_status = "color: #64748b;"
            else:
                # 🧮 MOTOR DE REGRAS OFICIAL
                if v_rp > 0.00:
                    ptsF17 = 75.0
                    texto_resultado = "✅ SUPERÁVIT: Capacidade de redução do endividamento"
                    estilo_status = "color: #16a34a; font-weight: bold;"
                elif v_rp == 0.00:
                    ptsF17 = 40.0
                    texto_resultado = "⚠️ EQUILÍBRIO: Receitas equivalentes às despesas liquidadas"
                    estilo_status = "color: #d97706; font-weight: bold;"
                else: # v_rp < 0.00
                    ptsF17 = 0.0
                    texto_resultado = "🚨 DÉFICIT: Tendência de aumento do endividamento municipal"
                    estilo_status = "color: #dc2626; font-weight: bold;"
                
                texto_pontuacao = f"{ptsF17:.2f} pontos"
                
        except ValueError:
            st.error("⚠️ Formato numérico inválido. Digite utilizando o padrão brasileiro (Ex: 150.000,00).")
            v_rr, v_dl = float_rr, float_dl
            v_rp = round(v_rr - v_dl, 2)
            ptsF17 = float(dF17.get("pontos", 40))
            texto_resultado = "Erro na leitura do campo"
            texto_pontuacao = f"{ptsF17:.2f} pontos"
            estilo_status = "color: #dc2626;"

    with c2:
        lF17 = st.text_area("Link/Evidência (F17 - Demonstrativo Primário AUDESP):", value=dF17.get("link", ""), key=f"txt_f17_{ano_sel}_{ctr}", height=150)

    # Exibição do painel consolidador de métricas fiscais decimais
    sinal_exibicao = "-" if v_rp < 0 else ""
    str_v_rp_formatado = f"{sinal_exibicao}R$ {abs(v_rp):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    st.markdown(f"""
    <div style="padding: 12px; background-color: #f1f5f9; border-left: 5px solid #1e3a8a; border-radius: 4px; margin-top: 15px; margin-bottom: 15px;">
        📌 <b>Cálculo da Fórmula (RP = RR - DL):</b> R$ {v_rr:,.2f} - R$ {v_dl:,.2f}<br>
        📊 <b>Resultado Primário Apurado (RP):</b> <code style="font-size: 15px; font-weight: bold; color: #b45309;">{str_v_rp_formatado}</code><br>
        ⚖ Rose <b>Situação Fiscal:</b> <span style="{estilo_status}">{texto_resultado}</span><br>
        🎯 <b>Impacto na Pontuação:</b> <code style="font-size: 15px; font-weight: bold; color: #1e40af;">{texto_pontuacao}</code>
    </div>
    """.replace(", ", "X").replace(".", ",").replace("X", "."), unsafe_allow_html=True)

    # Verificação de alteração de dados para gatilho de persistência
    string_banco_atual = f"{v_rr:.2f}/{v_dl:.2f}"
    string_banco_salva = f"{float_rr:.2f}/{float_dl:.2f}"

    if string_banco_atual != string_banco_salva or lF17 != dF17["link"]:
        save_resp("F17", string_banco_atual, ptsF17, lF17)
        
        if f"{v_rr:.2f}" != f"{float_rr:.2f}":
            st.session_state[f"f17_rr_key_suffix_{ano_sel}"] += 1
        if f"{v_dl:.2f}" != f"{float_dl:.2f}":
            st.session_state[f"f17_dl_key_suffix_{ano_sel}"] += 1
            
        st.rerun()

    bloco_comentarios("F17", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # F18 • Índice de Liquidez Imediata
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("F18 • Índice de Liquidez Imediata [IL = D / PC]")
    st.write("**Verifica a capacidade de pagamento com recursos do ativo disponível**")

    # Tabela de Regras de Pontuação
    st.markdown(r"""
    | Resultado do Índice $IL$ | Impacto / Pontuação do Indicador |
    | :--- | :--- |
    | Maior ou igual a 1 ($IL \ge 1,0$) | ✅ 75 pontos (Pontuação Máxima) |
    | Entre 0,8 e 1 ($> 0,8$ e $< 1,0$) | ⚠️ Graduação proporcional entre 0 e 75 pontos |
    | Menor ou igual a 0,8 ($IL \le 0,8$) | 🚨 00 ponto (Capacidade Crítica) |
    """)
    st.caption("ℹ️ *Dados extraídos do Relatório de Análises Anuais Eletrônicas – RAAE, item 4.1 (Capacidade de Pagamento com Recursos do Ativo Disponível).*")

    # 📝 Memória de cálculo oficial fornecida
    st.markdown("""
    <div style="background-color: #f8fafc; padding: 12px; border-radius: 4px; border-left: 3px solid #64748b; margin-bottom: 15px;">
        <p style="margin-bottom: 8px; font-size: 13px;">📊 <b>Regra de Distribuição Proporcional no Intervalo:</b></p>
        <ul style="font-size: 13px; margin-left: 15px; padding-left: 0px;">
            <li><b>Para resultados maiores que 0,80 e menores que 1,00:</b> A graduação será distribuída utilizando a fórmula: <br><code style="background-color: #e2e8f0; padding: 2px 5px;">P = ((IL - 0,80) * 75) / 0,20</code> <br><i>Exemplo: se IL = 0,8100, a nota do indicador será exatamente 3,75 pontos.</i></li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    # Inicializa os sufixos de controle no session_state para gerenciar o cache de forma isolada
    if f"f18_disp_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f18_disp_key_suffix_{ano_sel}"] = 0
    if f"f18_pc_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f18_pc_key_suffix_{ano_sel}"] = 0

    # Carrega ou inicializa a string persistida no banco contendo a dupla de valores (Disponível/Passivo Circulante)
    dF18 = res_data.get("F18", {"valor": "0.00/1.00", "pontos": 0, "link": ""})

    try:
        val_salvo_disp, val_salvo_pc = dF18["valor"].split("/")
        float_disp = float(val_salvo_disp)
        float_pc = float(val_salvo_pc)
    except:
        float_disp, float_pc = 0.0, 1.0

    # Converte os números salvos na máscara brasileira de apresentação monetária (R$)
    str_inicial_disp = f"R$ {float_disp:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    str_inicial_pc = f"R$ {float_pc:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    c1, c2 = st.columns([1, 2])

    with c1:
        # Input 1: Ativo Disponível (D)
        sufixo_disp = st.session_state[f"f18_disp_key_suffix_{ano_sel}"]
        input_disp_str = st.text_input(
            "Recursos do Ativo Disponível (D) - R$:",
            value=str_inicial_disp,
            placeholder="Ex: 81.000,00",
            key=f"txt_f18_disp_dinamico_{ano_sel}_{sufixo_disp}_{ctr}"
        )
        
        # Input 2: Passivo Circulante (PC)
        sufixo_pc = st.session_state[f"f18_pc_key_suffix_{ano_sel}"]
        input_pc_str = st.text_input(
            "Passivo Circulante (PC) - R$ (F18):",
            value=str_inicial_pc,
            placeholder="Ex: 100.000,00",
            key=f"txt_f18_pc_dinamico_{ano_sel}_{sufixo_pc}_{ctr}"
        )

        # 🧹 Função interna para higienizar strings monetárias do padrão BR
        def limpa_conversao_monetaria(texto):
            num_limpo = texto.replace("R$", "").replace(" ", "")
            if "." in num_limpo and "," in num_limpo:
                num_limpo = num_limpo.replace(".", "").replace(",", ".")
            elif "," in num_limpo:
                num_limpo = num_limpo.replace(",", ".")
            return float(num_limpo)

        # Tratamento lógico e cálculo dinâmico do índice IL
        try:
            v_disp = limpa_conversao_monetaria(input_disp_str)
            v_pc = max(limpa_conversao_monetaria(input_pc_str), 0.01) # Evita divisão por zero
            
            # Cálculo do Índice de Liquidez (Decimal Puro)
            IL = round(v_disp / v_pc, 4)
            
            # 🛑 TRAVA DE INICIALIZAÇÃO
            if v_disp == 0.0 and (dF18.get("link", "").strip() == ""):
                ptsF18 = 0.0
                texto_resultado = "Aguardando preenchimento..."
                texto_pontuacao = "⏳ 0,00 pontos"
                estilo_status = "color: #64748b;"
            else:
                # 🧮 MOTOR DE REGRAS OFICIAL
                if IL >= 1.0000:
                    ptsF18 = 75.0
                    texto_resultado = "✅ ADEQUADO: Disponível cobre totalmente o Passivo Circulante"
                    estilo_status = "color: #16a34a; font-weight: bold;"
                elif 0.8000 < IL < 1.0000:
                    # Aplicação exata da fórmula oficial: ((IL - 0.80) * 75) / 0.20
                    ptsF18 = ((IL - 0.8000) * 75.0) / 0.2000
                    texto_resultado = "⚠️ GRADUAÇÃO PROPORCIONAL: Cobertura parcial do passivo"
                    estilo_status = "color: #d97706; font-weight: bold;"
                else: # IL <= 0.8000
                    ptsF18 = 0.0
                    texto_resultado = "🚨 CRÍTICO: Índice de liquidez imediata muito baixo (≤ 0,80)"
                    estilo_status = "color: #dc2626; font-weight: bold;"
                
                texto_pontuacao = f"{ptsF18:.2f} pontos"
                
        except ValueError:
            st.error("⚠️ Formato numérico inválido. Digite utilizando o padrão brasileiro (Ex: 150.000,00).")
            v_disp, v_pc = float_disp, float_pc
            IL = float_disp / max(float_pc, 0.01)
            ptsF18 = float(dF18.get("pontos", 0))
            texto_resultado = "Erro na leitura do campo"
            texto_pontuacao = f"{ptsF18:.2f} pontos"
            estilo_status = "color: #dc2626;"

    with c2:
        lF18 = st.text_area("Link/Evidência (F18 - Liquidez Imediata RAAE):", value=dF18.get("link", ""), key=f"txt_f18_{ano_sel}_{ctr}", height=150)

    # Exibição do painel consolidador de métricas
    st.markdown(f"""
    <div style="padding: 12px; background-color: #f1f5f9; border-left: 5px solid #1e3a8a; border-radius: 4px; margin-top: 15px; margin-bottom: 15px;">
        📌 <b>Cálculo da Razão:</b> R$ {v_disp:,.2f} / R$ {v_pc:,.2f}<br>
        📊 <b>Resultado do Indicador (IL):</b> <code style="font-size: 15px; font-weight: bold; color: #b45309;">{IL:.4f}</code><br>
        ⚖️ <b>Situação de Liquidez:</b> <span style="{estilo_status}">{texto_resultado}</span><br>
        🎯 <b>Impacto na Pontuação:</b> <code style="font-size: 15px; font-weight: bold; color: #1e40af;">{texto_pontuacao}</code>
    </div>
    """.replace(", ", "X").replace(".", ",").replace("X", "."), unsafe_allow_html=True)

    # Verificação de alteração de dados para gatilho de persistência
    string_banco_atual = f"{v_disp:.2f}/{v_pc:.2f}"
    string_banco_salva = f"{float_disp:.2f}/{float_pc:.2f}"

    if string_banco_atual != string_banco_salva or lF18 != dF18["link"]:
        save_resp("F18", string_banco_atual, ptsF18, lF18)
        
        if f"{v_disp:.2f}" != f"{float_disp:.2f}":
            st.session_state[f"f18_disp_key_suffix_{ano_sel}"] += 1
        if f"{v_pc:.2f}" != f"{float_pc:.2f}":
            st.session_state[f"f18_pc_key_suffix_{ano_sel}"] += 1
            
        st.rerun()

    bloco_comentarios("F18", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

# F19 • Limite de Endividamento – Regra de Ouro
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("F19 • Limite de Endividamento – Regra de Ouro [RO = OC - DC - AL]")
    st.write("**Verifica se as operações de crédito ultrapassaram o volume de despesas de capital**")

    # Tabela de Regras de Pontuação
    st.markdown(r"""
    | Resultado da Regra de Ouro ($RO$) | Impacto / Pontuação do Indicador |
    | :--- | :--- |
    | Menor ou igual a ZERO ($RO \le 0$) | ✅ 00 ponto (Regra Cumprida / Sem Penalidade) |
    | Maior que ZERO ($RO > 0$) | 🚨 **REBAIXA 1 FAIXA DO I-FISCAL** (Descumprimento Crítico) |
    """)
    st.caption("ℹ️ *Variáveis extraídas dos demonstrativos fiscais e balanços anuais consolidados do município.*")

    # Inicializa os sufixos de controle no session_state para gerenciar o cache de forma isolada
    if f"f19_oc_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f19_oc_key_suffix_{ano_sel}"] = 0
    if f"f19_dc_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f19_dc_key_suffix_{ano_sel}"] = 0
    if f"f19_al_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f19_al_key_suffix_{ano_sel}"] = 0

    # Carrega ou inicializa a string persistida no banco contendo o trio de valores (OC/DC/AL)
    dF19 = res_data.get("F19", {"valor": "0.00/0.00/0.00", "pontos": 0, "link": ""})

    try:
        val_salvo_oc, val_salvo_dc, val_salvo_al = dF19["valor"].split("/")
        float_oc = float(val_salvo_oc)
        float_dc = float(val_salvo_dc)
        float_al = float(val_salvo_al)
    except:
        float_oc, float_dc, float_al = 0.0, 0.0, 0.0

    # Converte os números salvos na máscara brasileira de apresentação monetária (R$)
    str_inicial_oc = f"R$ {float_oc:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    str_inicial_dc = f"R$ {float_dc:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    str_inicial_al = f"R$ {float_al:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    c1, c2 = st.columns([1, 2])

    with c1:
        # Input 1: Operações de Crédito (OC)
        sufixo_oc = st.session_state[f"f19_oc_key_suffix_{ano_sel}"]
        input_oc_str = st.text_input(
            "Operações de Crédito Realizadas (OC) - R$:",
            value=str_inicial_oc,
            placeholder="Ex: 500.000,00",
            key=f"txt_f19_oc_dinamico_{ano_sel}_{sufixo_oc}_{ctr}"
        )
        
        # Input 2: Despesas de Capital (DC)
        sufixo_dc = st.session_state[f"f19_dc_key_suffix_{ano_sel}"]
        input_dc_str = st.text_input(
            "Despesas de Capital Liquidadas (DC) - R$:",
            value=str_inicial_dc,
            placeholder="Ex: 600.000,00",
            key=f"txt_f19_dc_dinamico_{ano_sel}_{sufixo_dc}_{ctr}"
        )

        # Input 3: Autorizações Legislativas (AL)
        sufixo_al = st.session_state[f"f19_al_key_suffix_{ano_sel}"]
        input_al_str = st.text_input(
            "Autorizações por Maioria Absoluta (AL) - R$:",
            value=str_inicial_al,
            placeholder="Ex: 50.000,00",
            key=f"txt_f19_al_dinamico_{ano_sel}_{sufixo_al}_{ctr}"
        )

        # 🧹 Função interna para higienizar strings monetárias do padrão BR
        def limpa_conversao_monetaria(texto):
            num_limpo = texto.replace("R$", "").replace(" ", "")
            if "." in num_limpo and "," in num_limpo:
                num_limpo = num_limpo.replace(".", "").replace(",", ".")
            elif "," in num_limpo:
                num_limpo = num_limpo.replace(",", ".")
            return float(num_limpo)

        # Tratamento lógico e cálculo da fórmula estrutural
        try:
            v_oc = limpa_conversao_monetaria(input_oc_str)
            v_dc = limpa_conversao_monetaria(input_dc_str)
            v_al = limpa_conversao_monetaria(input_al_str)
            
            # Execução matemática da fórmula: RO = OC - DC - AL
            v_ro = round(v_oc - v_dc - v_al, 2)
            
            # 🛑 TRAVA DE INICIALIZAÇÃO
            if v_oc == 0.0 and v_dc == 0.0 and v_al == 0.0 and (dF19.get("link", "").strip() == ""):
                ptsF19 = 0.0
                texto_resultado = "Aguardando preenchimento..."
                texto_pontuacao = "⏳ Verificar Regra"
                estilo_status = "color: #64748b;"
            else:
                # 🧮 MOTOR DE REGRAS
                if v_ro > 0.00:
                    ptsF19 = 0.0
                    texto_resultado = "🚨 CRÍTICO: Regra de Ouro Descumprida! Rebaixar 1 faixa do i-Fiscal"
                    estilo_status = "color: #dc2626; font-weight: bold;"
                else:
                    ptsF19 = 0.0
                    texto_resultado = "✅ REGULAR: Operações de crédito compatíveis com os investimentos"
                    estilo_status = "color: #16a34a; font-weight: bold;"
                
                texto_pontuacao = "0,00 pontos"
                
        except ValueError:
            st.error("⚠️ Formato numérico inválido. Digite utilizando o padrão brasileiro (Ex: 150.000,00).")
            v_oc, v_dc, v_al = float_oc, float_dc, float_al
            v_ro = round(v_oc - v_dc - v_al, 2)
            ptsF19 = float(dF19.get("pontos", 0))
            texto_resultado = "Erro na leitura do campo"
            texto_pontuacao = f"{ptsF19:.2f} pontos"
            estilo_status = "color: #dc2626;"

    with c2:
        lF19 = st.text_area("Link/Evidência (F19 - Regra de Ouro Balanços):", value=dF19.get("link", ""), key=f"txt_f19_{ano_sel}_{ctr}", height=210)

    # Exibição do painel consolidador de métricas fiscais
    sinal_exibicao = "-" if v_ro < 0 else ""
    str_v_ro_formatado = f"{sinal_exibicao}R$ {abs(v_ro):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    st.markdown(f"""
    <div style="padding: 12px; background-color: #f1f5f9; border-left: 5px solid #1e3a8a; border-radius: 4px; margin-top: 15px; margin-bottom: 15px;">
        📌 <b>Cálculo da Fórmula (RO = OC - DC - AL):</b> R$ {v_oc:,.2f} - R$ {v_dc:,.2f} - R$ {v_al:,.2f}<br>
        📊 <b>Resultado da Regra (RO):</b> <code style="font-size: 15px; font-weight: bold; color: #b45309;">{str_v_ro_formatado}</code><br>
        ⚖️ <b>Situação Constitucional:</b> <span style="{estilo_status}">{texto_resultado}</span><br>
        🎯 <b>Impacto na Pontuação:</b> <code style="font-size: 15px; font-weight: bold; color: #1e40af;">{texto_pontuacao}</code>
    </div>
    """.replace(", ", "X").replace(".", ",").replace("X", "."), unsafe_allow_html=True)

    # Verificação de alteração de dados para gatilho de persistência
    string_banco_atual = f"{v_oc:.2f}/{v_dc:.2f}/{v_al:.2f}"
    string_banco_salva = f"{float_oc:.2f}/{float_dc:.2f}/{float_al:.2f}"

    if string_banco_atual != string_banco_salva or lF19 != dF19["link"]:
        save_resp("F19", string_banco_atual, ptsF19, lF19)
        
        if f"{v_oc:.2f}" != f"{float_oc:.2f}":
            st.session_state[f"f19_oc_key_suffix_{ano_sel}"] += 1
        if f"{v_dc:.2f}" != f"{float_dc:.2f}":
            st.session_state[f"f19_dc_key_suffix_{ano_sel}"] += 1
        if f"{v_al:.2f}" != f"{float_al:.2f}":
            st.session_state[f"f19_al_key_suffix_{ano_sel}"] += 1
            
        st.rerun()

    bloco_comentarios("F19", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

# F20 • Percentual da Taxa de Investimento
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("F20 • Percentual da Taxa de Investimento [(L + F) / M = N]")
    st.write("**Mede a taxa de investimento real líquida em relação à receita total arrecadada**")

    # Tabela de Regras de Pontuação
    st.markdown(r"""
    | Resultado do Índice $N$ | Impacto / Pontuação do Indicador |
    | :--- | :--- |
    | Maior ou igual a 0,15 ($N \ge 0,15$) | ✅ 50 pontos (Pontuação Máxima) |
    | Entre 0,02 e 0,15 ($> 0,02$ e $< 0,15$) | ⚠️ Graduação proporcional entre 0 e 50 pontos |
    | Menor ou igual a 0,02 ($N \le 0,02$) | 🚨 00 ponto (Baixo Índice de Investimento) |
    """)
    st.caption("ℹ️ *Despesa classificada no elemento '44 - Investimentos' (Portaria MPOG nº 163/2001) via Sistema AUDESP.*")

    # 📝 Memória de cálculo oficial fornecida
    st.markdown("""
    <div style="background-color: #f8fafc; padding: 12px; border-radius: 4px; border-left: 3px solid #64748b; margin-bottom: 15px;">
        <p style="margin-bottom: 8px; font-size: 13px;">📊 <b>Regra de Distribuição Proporcional no Intervalo:</b></p>
        <ul style="font-size: 13px; margin-left: 15px; padding-left: 0px;">
            <li><b>Para resultados maiores que 0,02 e menores que 0,15:</b> A graduação será distribuída utilizando a fórmula: <br><code style="background-color: #e2e8f0; padding: 2px 5px;">P = ((N – 0,02) / 0,13) * 50</code> <br><i>Exemplo: se N = 0,1000 (10% de taxa), a nota do indicador será exatamente 30,77 pontos.</i></li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    # Inicializa os sufixos de controle no session_state para gerenciar o cache de forma isolada
    if f"f20_l_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f20_l_key_suffix_{ano_sel}"] = 0
    if f"f20_f_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f20_f_key_suffix_{ano_sel}"] = 0
    if f"f20_m_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f20_m_key_suffix_{ano_sel}"] = 0

    # Carrega ou inicializa a string persistida no banco contendo o trio de valores (L/F/M)
    dF20 = res_data.get("F20", {"valor": "0.00/0.00/1.00", "pontos": 0, "link": ""})

    try:
        val_salvo_l, val_salvo_f, val_salvo_m = dF20["valor"].split("/")
        float_l = float(val_salvo_l)
        float_f = float(val_salvo_f)
        float_m = float(val_salvo_m)
    except:
        float_l, float_f, float_m = 0.0, 0.0, 1.0

    # Converte os números salvos na máscara brasileira de apresentação monetária (R$)
    str_inicial_l = f"R$ {float_l:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    str_inicial_f = f"R$ {float_f:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    str_inicial_m = f"R$ {float_m:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    c1, c2 = st.columns([1, 2])

    with c1:
        # Input 1: Despesa Liquidada Total - Grupo 44 (L)
        sufixo_l = st.session_state[f"f20_l_key_suffix_{ano_sel}"]
        input_l_str = st.text_input(
            "Despesa Liquidada Total - Cat. 44 (L) - R$:",
            value=str_inicial_l,
            placeholder="Ex: 90.000,00",
            key=f"txt_f20_l_dinamico_{ano_sel}_{sufixo_l}_{ctr}"
        )
        
        # Input 2: Liquidação de Restos a Pagar Não Processados (F)
        sufixo_f = st.session_state[f"f20_f_key_suffix_{ano_sel}"]
        input_f_str = st.text_input(
            "Liq. Restos a Pagar Não Processados (F) - R$:",
            value=str_inicial_f,
            placeholder="Ex: 10.000,00",
            key=f"txt_f20_f_dinamico_{ano_sel}_{sufixo_f}_{ctr}"
        )

        # Input 3: Receita Total Arrecadada (M)
        sufixo_m = st.session_state[f"f20_m_key_suffix_{ano_sel}"]
        input_m_str = st.text_input(
            "Receita Total Arrecadada no Período (M) - R$:",
            value=str_inicial_m,
            placeholder="Ex: 1.000.000,00",
            key=f"txt_f20_m_dinamico_{ano_sel}_{sufixo_m}_{ctr}"
        )

        # 🧹 Função interna para higienizar strings monetárias do padrão BR
        def limpa_conversao_monetaria(texto):
            num_limpo = texto.replace("R$", "").replace(" ", "")
            if "." in num_limpo and "," in num_limpo:
                num_limpo = num_limpo.replace(".", "").replace(",", ".")
            elif "," in num_limpo:
                num_limpo = num_limpo.replace(",", ".")
            return float(num_limpo)

        # Tratamento lógico e cálculo dinâmico da Taxa de Investimento
        try:
            v_l = limpa_conversao_monetaria(input_l_str)
            v_f = limpa_conversao_monetaria(input_f_str)
            v_m = max(limpa_conversao_monetaria(input_m_str), 0.01) # Evita divisão por zero
            
            # Cálculo do Índice N (Decimal Puro)
            N = round((v_l + v_f) / v_m, 4)
            
            # 🛑 TRAVA DE INICIALIZAÇÃO
            if v_l == 0.0 and v_f == 0.0 and (dF20.get("link", "").strip() == ""):
                ptsF20 = 0.0
                texto_resultado = "Aguardando preenchimento..."
                texto_pontuacao = "⏳ 0,00 pontos"
                estilo_status = "color: #64748b;"
            else:
                # 🧮 MOTOR DE REGRAS OFICIAL
                if N >= 0.1500:
                    ptsF20 = 50.0
                    texto_resultado = "✅ EXCELENTE: Alto percentual de aplicação em investimentos"
                    estilo_status = "color: #16a34a; font-weight: bold;"
                elif 0.0200 < N < 0.1500:
                    # Aplicação exata da fórmula oficial: ((N - 0.02) / 0.13) * 50
                    ptsF20 = ((N - 0.0200) / 0.1300) * 50.0
                    texto_resultado = "⚠️ GRADUAÇÃO PROPORCIONAL: Nível intermediário de investimentos"
                    estilo_status = "color: #d97706; font-weight: bold;"
                else: # N <= 0.0200
                    ptsF20 = 0.0
                    texto_resultado = "🚨 CRÍTICO: Índice de investimento igual ou abaixo do limite de tolerância (≤ 2%)"
                    estilo_status = "color: #dc2626; font-weight: bold;"
                
                texto_pontuacao = f"{ptsF20:.2f} pontos"
                
        except ValueError:
            st.error("⚠️ Formato numérico inválido. Digite utilizando o padrão brasileiro (Ex: 150.000,00).")
            v_l, v_f, v_m = float_l, float_f, float_m
            N = (float_l + float_f) / max(float_m, 0.01)
            ptsF20 = float(dF20.get("pontos", 0))
            texto_resultado = "Erro na leitura do campo"
            texto_pontuacao = f"{ptsF20:.2f} pontos"
            estilo_status = "color: #dc2626;"

    with c2:
        lF20 = st.text_area("Link/Evidência (F20 - Taxa de Investimento AUDESP):", value=dF20.get("link", ""), key=f"txt_f20_{ano_sel}_{ctr}", height=210)

    # Exibição do painel consolidador de métricas fiscais
    st.markdown(f"""
    <div style="padding: 12px; background-color: #f1f5f9; border-left: 5px solid #1e3a8a; border-radius: 4px; margin-top: 15px; margin-bottom: 15px;">
        📌 <b>Cálculo da Equação [(L + F) / M]:</b> (R$ {v_l:,.2f} + R$ {v_f:,.2f}) / R$ {v_m:,.2f}<br>
        📊 <b>Resultado da Taxa (N):</b> <code style="font-size: 15px; font-weight: bold; color: #b45309;">{N:.4f}</code> ({N*100:.2f}% de aplicação)<br>
        ⚖️ <b>Situação de Alocação:</b> <span style="{estilo_status}">{texto_resultado}</span><br>
        🎯 <b>Impacto na Pontuação:</b> <code style="font-size: 15px; font-weight: bold; color: #1e40af;">{texto_pontuacao}</code>
    </div>
    """.replace(", ", "X").replace(".", ",").replace("X", "."), unsafe_allow_html=True)

    # Verificação de alteração de dados para gatilho de persistência
    string_banco_atual = f"{v_l:.2f}/{v_f:.2f}/{v_m:.2f}"
    string_banco_salva = f"{float_l:.2f}/{float_f:.2f}/{float_m:.2f}"

    if string_banco_atual != string_banco_salva or lF20 != dF20["link"]:
        save_resp("F20", string_banco_atual, ptsF20, lF20)
        
        if f"{v_l:.2f}" != f"{float_l:.2f}":
            st.session_state[f"f20_l_key_suffix_{ano_sel}"] += 1
        if f"{v_f:.2f}" != f"{float_f:.2f}":
            st.session_state[f"f20_f_key_suffix_{ano_sel}"] += 1
        if f"{v_m:.2f}" != f"{float_m:.2f}":
            st.session_state[f"f20_m_key_suffix_{ano_sel}"] += 1
            
        st.rerun()

    bloco_comentarios("F20", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

# F21 • Relação entre Despesas Correntes e Receitas Correntes
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("F21 • Relação Despesas Correntes / Receitas Correntes [LDC = DC / RC]")
    st.write("**Verifica o cumprimento do limite constitucional de gastos (Art. 167-A da CF)**")

    # Tabela de Regras de Pontuação (Penalidades)
    st.markdown(r"""
    | Resultado do Índice $LDC$ | Impacto / Pontuação do Indicador |
    | :--- | :--- |
    | Menor ou igual a 0,85 ($LDC \le 0,85$) | ✅ 00 ponto (Situação Confortável / Sem Penalidade) |
    | Entre 0,85 e 0,95 ($> 0,85$ e $\le 0,95$) | ⚠️ Graduação proporcional entre 0 e -50 pontos (Perda) |
    | Maior que 0,95 ($LDC > 0,95$) | 🚨 -50,00 pontos (Penalidade Máxima por Estouro de Teto) |
    """)
    st.caption("ℹ️ *Dados consolidados (Prefeitura, Câmara e Autarquias) com base no Relatório de Instrução AUDESP, item GF56.*")

    # 📝 Memória de cálculo oficial fornecida
    st.markdown("""
    <div style="background-color: #fff5f5; padding: 12px; border-radius: 4px; border-left: 3px solid #e53e3e; margin-bottom: 15px;">
        <p style="margin-bottom: 8px; font-size: 13px; color: #9b2c2c;">📊 <b>Regra de Penalização Proporcional no Intervalo:</b></p>
        <ul style="font-size: 13px; margin-left: 15px; padding-left: 0px; color: #9b2c2c;">
            <li><b>Para resultados maiores que 0,85 e menores ou iguais a 0,95:</b> A perda de pontos será distribuída utilizando a fórmula: <br><code style="background-color: #fed7d7; padding: 2px 5px; color: #9b2c2c;">P = ((LDC – 0,85) / 0,10) * (-50)</code> <br><i>Exemplo: se LDC = 0,9300 (93% de comprometimento), a nota do indicador será exatamente de -40,00 pontos.</i></li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    # Inicializa os sufixos de controle no session_state para gerenciar o cache de forma isolada
    if f"f21_dc_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f21_dc_key_suffix_{ano_sel}"] = 0
    if f"f21_rc_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f21_rc_key_suffix_{ano_sel}"] = 0

    # Carrega ou inicializa a string persistida no banco contendo a dupla de valores (Despesas/Receitas)
    dF21 = res_data.get("F21", {"valor": "0.00/1.00", "pontos": 0, "link": ""})

    try:
        val_salvo_dc, val_salvo_rc = dF21["valor"].split("/")
        float_dc = float(val_salvo_dc)
        float_rc = float(val_salvo_rc)
    except:
        float_dc, float_rc = 0.0, 1.0

    # Converte os números salvos na máscara brasileira de apresentação monetária (R$)
    str_inicial_dc = f"R$ {float_dc:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    str_inicial_rc = f"R$ {float_rc:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    c1, c2 = st.columns([1, 2])

    with c1:
        # Input 1: Despesa Corrente Liquidada (DC)
        sufixo_dc = st.session_state[f"f21_dc_key_suffix_{ano_sel}"]
        input_dc_str = st.text_input(
            "Despesa Corrente Liquidada (DC) - R$:",
            value=str_inicial_dc,
            placeholder="Ex: 850.000,00",
            key=f"txt_f21_dc_dinamico_{ano_sel}_{sufixo_dc}_{ctr}"
        )
        
        # Input 2: Receita Corrente Arrecadada (RC)
        sufixo_rc = st.session_state[f"f21_rc_key_suffix_{ano_sel}"]
        input_rc_str = st.text_input(
            "Receita Corrente Total (RC) - R$ (F21):",
            value=str_inicial_rc,
            placeholder="Ex: 1.000.000,00",
            key=f"txt_f21_rc_dinamico_{ano_sel}_{sufixo_rc}_{ctr}"
        )

        # 🧹 Função interna para higienizar strings monetárias do padrão BR
        def limpa_conversao_monetaria(texto):
            num_limpo = texto.replace("R$", "").replace(" ", "")
            if "." in num_limpo and "," in num_limpo:
                num_limpo = num_limpo.replace(".", "").replace(",", ".")
            elif "," in num_limpo:
                num_limpo = num_limpo.replace(",", ".")
            return float(num_limpo)

        # Tratamento lógico e cálculo dinâmico do índice LDC e penalidades
        try:
            v_dc = limpa_conversao_monetaria(input_dc_str)
            v_rc = max(limpa_conversao_monetaria(input_rc_str), 0.01) # Evita divisão por zero
            
            # Cálculo do Índice LDC (Decimal Puro)
            LDC = round(v_dc / v_rc, 4)
            
            # 🛑 TRAVA DE INICIALIZAÇÃO
            if v_dc == 0.0 and (dF21.get("link", "").strip() == ""):
                ptsF21 = 0.0
                texto_resultado = "Aguardando preenchimento..."
                texto_pontuacao = "⏳ 0,00 pontos"
                estilo_status = "color: #64748b;"
            else:
                # 🧮 MOTOR DE REGRAS (LÓGICA DE PENALIZAÇÃO)
                if LDC <= 0.8500:
                    ptsF21 = 0.0
                    texto_resultado = "✅ ADEQUADO: Gastos correntes equilibrados e sob controle"
                    estilo_status = "color: #16a34a; font-weight: bold;"
                elif 0.8500 < LDC <= 0.9500:
                    # Aplicação exata da fórmula paramétrica de decréscimo: ((LDC - 0.85) / 0.10) * (-50)
                    ptsF21 = round(((LDC - 0.8500) / 0.1000) * (-50.0), 2)
                    texto_resultado = "⚠️ ALERTA: Próximo ao limite prudencial (Incidência de Penalidade)"
                    estilo_status = "color: #d97706; font-weight: bold;"
                else: # LDC > 0.9500
                    ptsF21 = -50.0
                    texto_resultado = "🚨 CRÍTICO: Violação do teto do Art. 167-A da CF (> 95%)"
                    estilo_status = "color: #dc2626; font-weight: bold;"
                
                sinal_pontos = "" if ptsF21 >= 0 else " "
                texto_pontuacao = f"{sinal_pontos}{ptsF21:.2f} pontos".replace(".", ",")
                
        except ValueError:
            st.error("⚠️ Formato numérico inválido. Digite utilizando o padrão brasileiro (Ex: 150.000,00).")
            v_dc, v_rc = float_dc, float_rc
            LDC = float_dc / max(float_rc, 0.01)
            ptsF21 = float(dF21.get("pontos", 0))
            texto_resultado = "Erro na leitura do campo"
            texto_pontuacao = f"{ptsF21:.2f} pontos"
            estilo_status = "color: #dc2626;"

    with c2:
        lF21 = st.text_area("Link/Evidência (F21 - Relação Corrente AUDESP):", value=dF21.get("link", ""), key=f"txt_f21_{ano_sel}_{ctr}", height=150)

    # Exibição do painel consolidador de métricas fiscais decimais
    st.markdown(f"""
    <div style="padding: 12px; background-color: #f1f5f9; border-left: 5px solid #1e3a8a; border-radius: 4px; margin-top: 15px; margin-bottom: 15px;">
        📌 <b>Cálculo da Razão (DC / RC):</b> R$ {v_dc:,.2f} / R$ {v_rc:,.2f}<br>
        📊 <b>Resultado do Indicador (LDC):</b> <code style="font-size: 15px; font-weight: bold; color: #b45309;">{LDC:.4f}</code> ({LDC*100:.2f}% de comprometimento)<br>
        ⚖️ <b>Enquadramento Legal:</b> <span style="{estilo_status}">{texto_resultado}</span><br>
        🎯 <b>Glosa/Impacto na Pontuação:</b> <code style="font-size: 15px; font-weight: bold; color: #dc2626;">{texto_pontuacao}</code>
    </div>
    """.replace(", ", "X").replace(".", ",").replace("X", "."), unsafe_allow_html=True)

    # Verificação de alteração de dados para gatilho de persistência
    string_banco_atual = f"{v_dc:.2f}/{v_rc:.2f}"
    string_banco_salva = f"{float_dc:.2f}/{float_rc:.2f}"

    if string_banco_atual != string_banco_salva or lF21 != dF21["link"]:
        save_resp("F21", string_banco_atual, ptsF21, lF21)
        
        if f"{v_dc:.2f}" != f"{float_dc:.2f}":
            st.session_state[f"f21_dc_key_suffix_{ano_sel}"] += 1
        if f"{v_rc:.2f}" != f"{float_rc:.2f}":
            st.session_state[f"f21_rc_key_suffix_{ano_sel}"] += 1
            
        st.rerun()

    bloco_comentarios("F21", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

    # F22 • Liquidez dos Restos a Pagar
    st.markdown('<div class="quesito-card">', unsafe_allow_html=True)
    st.subheader("F22 • Liquidez dos Restos a Pagar [LRP = RPA / D]")
    st.write("**Mede a capacidade de pagamento do estoque de restos a pagar com base na disponibilidade de caixa**")

    # Tabela de Regras de Pontuação (Penalidades)
    st.markdown(r"""
    | Resultado do Índice $LRP$ | Impacto / Pontuação do Indicador |
    | :--- | :--- |
    | Menor ou igual a 1 ($LRP \le 1$) | ✅ 00 ponto (Cobertura de Caixa Suficiente / Sem Penalidade) |
    | Maior que 1 ($LRP > 1$) | 🚨 -5,00 pontos (Caixa Insuficiente para Cobrir Restos a Pagar) |
    """)
    st.caption("ℹ️ *Variáveis extraídas do Relatório de Análises Anuais Eletrônicas (RAAE) e do Relatório de Instrução (RI).*")

    # Inicializa os sufixos de controle no session_state para gerenciar o cache de forma isolada
    if f"f22_rpa_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f22_rpa_key_suffix_{ano_sel}"] = 0
    if f"f22_d_key_suffix_{ano_sel}" not in st.session_state:
        st.session_state[f"f22_d_key_suffix_{ano_sel}"] = 0

    # Carrega ou inicializa a string persistida no banco contendo a dupla de valores (RPA/D)
    dF22 = res_data.get("F22", {"valor": "0.00/1.00", "pontos": 0, "link": ""})

    try:
        val_salvo_rpa, val_salvo_d = dF22["valor"].split("/")
        float_rpa = float(val_salvo_rpa)
        float_d = float(val_salvo_d)
    except:
        float_rpa, float_d = 0.0, 1.0

    # Converte os números salvos na máscara brasileira de apresentação monetária (R$)
    str_inicial_rpa = f"R$ {float_rpa:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    str_inicial_d = f"R$ {float_d:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    c1, c2 = st.columns([1, 2])

    with c1:
        # Input 1: Estoque de Restos a Pagar (RPA)
        sufixo_rpa = st.session_state[f"f22_rpa_key_suffix_{ano_sel}"]
        input_rpa_str = st.text_input(
            "Estoque de Restos a Pagar - Proc. e Não Proc. (RPA) - R$:",
            value=str_inicial_rpa,
            placeholder="Ex: 150.000,00",
            key=f"txt_f22_rpa_dinamico_{ano_sel}_{sufixo_rpa}_{ctr}"
        )
        
        # Input 2: Disponibilidade de Caixa (D)
        sufixo_d = st.session_state[f"f22_d_key_suffix_{ano_sel}"]
        input_d_str = st.text_input(
            "Disponibilidade de Caixa / Disponível (D) - R$:",
            value=str_inicial_d,
            placeholder="Ex: 200.000,00",
            key=f"txt_f22_d_dinamico_{ano_sel}_{sufixo_d}_{ctr}"
        )

        # 🧹 Função interna para higienizar strings monetárias do padrão BR
        def limpa_conversao_monetaria(texto):
            num_limpo = texto.replace("R$", "").replace(" ", "")
            if "." in num_limpo and "," in num_limpo:
                num_limpo = num_limpo.replace(".", "").replace(",", ".")
            elif "," in num_limpo:
                num_limpo = num_limpo.replace(",", ".")
            return float(num_limpo)

        # Tratamento lógico e cálculo dinâmico do índice LRP e penalidades
        try:
            v_rpa = limpa_conversao_monetaria(input_rpa_str)
            v_d = max(limpa_conversao_monetaria(input_d_str), 0.01) # Evita divisão por zero
            
            # Cálculo do Índice LRP (Decimal Puro)
            LRP = round(v_rpa / v_d, 4)
            
            # 🛑 TRAVA DE INICIALIZAÇÃO
            if v_rpa == 0.0 and (dF22.get("link", "").strip() == ""):
                ptsF22 = 0.0
                texto_resultado = "Aguardando preenchimento..."
                texto_pontuacao = "⏳ 0,00 pontos"
                estilo_status = "color: #64748b;"
            else:
                # 🧮 MOTOR DE REGRAS (LÓGICA DE PENALIZAÇÃO DIRETA)
                if LRP <= 1.0000:
                    ptsF22 = 0.0
                    texto_resultado = "✅ ADEQUADO: O saldo em caixa cobre integralmente as obrigações de restos a pagar"
                    estilo_status = "color: #16a34a; font-weight: bold;"
                else: # LRP > 1.0000
                    ptsF22 = -5.0
                    texto_resultado = "🚨 CRÍTICO: Despesas postergadas sem suficiência de caixa financeira"
                    estilo_status = "color: #dc2626; font-weight: bold;"
                
                sinal_pontos = "" if ptsF22 >= 0 else " "
                texto_pontuacao = f"{sinal_pontos}{ptsF22:.2f} pontos".replace(".", ",")
                
        except ValueError:
            st.error("⚠️ Formato numérico inválido. Digite utilizando o padrão brasileiro (Ex: 150.000,00).")
            v_rpa, v_d = float_rpa, float_d
            LRP = float_rpa / max(float_d, 0.01)
            ptsF22 = float(dF22.get("pontos", 0))
            texto_resultado = "Erro na leitura do campo"
            texto_pontuacao = f"{ptsF22:.2f} pontos"
            estilo_status = "color: #dc2626;"

    with c2:
        lF22 = st.text_area("Link/Evidência (F22 - Liquidez Restos a Pagar RAAE/RI):", value=dF22.get("link", ""), key=f"txt_f22_{ano_sel}_{ctr}", height=150)

    # Exibição do painel consolidador de métricas fiscais decimais
    st.markdown(f"""
    <div style="padding: 12px; background-color: #f1f5f9; border-left: 5px solid #1e3a8a; border-radius: 4px; margin-top: 15px; margin-bottom: 15px;">
        📌 <b>Cálculo da Razão (RPA / D):</b> R$ {v_rpa:,.2f} / R$ {v_d:,.2f}<br>
        📊 <b>Resultado do Indicador (LRP):</b> <code style="font-size: 15px; font-weight: bold; color: #b45309;">{LRP:.4f}</code><br>
        ⚖️ <b>Suficiência de Caixa:</b> <span style="{estilo_status}">{texto_resultado}</span><br>
        🎯 <b>Glosa/Impacto na Pontuação:</b> <code style="font-size: 15px; font-weight: bold; color: #dc2626;">{texto_pontuacao}</code>
    </div>
    """.replace(", ", "X").replace(".", ",").replace("X", "."), unsafe_allow_html=True)

    # Verificação de alteração de dados para gatilho de persistência
    string_banco_atual = f"{v_rpa:.2f}/{v_d:.2f}"
    string_banco_salva = f"{float_rpa:.2f}/{float_d:.2f}"

    if string_banco_atual != string_banco_salva or lF22 != dF22["link"]:
        save_resp("F22", string_banco_atual, ptsF22, lF22)
        
        if f"{v_rpa:.2f}" != f"{float_rpa:.2f}":
            st.session_state[f"f22_rpa_key_suffix_{ano_sel}"] += 1
        if f"{v_d:.2f}" != f"{float_d:.2f}":
            st.session_state[f"f22_d_key_suffix_{ano_sel}"] += 1
            
        st.rerun()

    bloco_comentarios("F22", res_data)
    st.markdown('</div>', unsafe_allow_html=True)

