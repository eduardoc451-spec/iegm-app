import streamlit as st
import pandas as pd
import io
import sqlite3
import os
import re

# Importações do ReportLab com suporte a páginas em modo paisagem e quebras automáticas
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def higienizar_e_traduzir_quesito(id_quesito, texto_bruto):
    """
    Remove restos de código Python, variáveis (como pts131, str(sel)) 
    e substitui por enunciados limpos e legíveis para o relatório oficial.
    """
    id_limpo = str(id_quesito).strip().replace('.0', '')
    
    # 🎯 DICIONÁRIO DE TRADUÇÃO COMPORTAMENTAL (Cura definitiva para os lixos de código)
    PROVEDOR_DE_ENUNCIADOS = {
        "1": "Planejamento Estratégico de TI / Existência de Plano Diretor de TI (PDTI)",
        "1.1": "Alinhamento das metas de Tecnologia da Informação com os objetivos institucionais",
        "1.2": "Processo de planejamento orçamentário e investimentos para a área de TI",
        "1.3": "Existência e aplicação de metas e indicadores de desempenho para governança de TI",
        "1.3.1": "Detalhamento e acompanhamento das métricas de entrega e suporte de TI",
        "1.4": "Políticas e normativas vigentes para a gestão da segurança da informação",
        "1.4.1": "Mapeamento de processos de contratação e especificação técnica de softwares",
        "1.4.2": "Existência de inventário atualizado de ativos de hardware e licenças de software",
        "2": "Plano de Metas, Alocação de Recursos e Prazos Plurianuais",
        "2.1": "Divulgação dos planos e relatórios setoriais no Portal da Transparência",
        "2.2": "Mecanismos de alocação de recursos materiais, humanos e financeiros em TI",
        "2.3": "Acompanhamento de prazos, cronogramas de execução e auditorias de metas",
        "3": "Mecanismos de Segurança, Continuidade de Negócios e Backups",
        "3.1": "Rotinas de cópias de segurança (backups) para os sistemas críticos municipais",
        "3.1.1": "Testes periódicos de restauração de dados para garantia de contingência",
        "3.2": "Planos de segurança física de servidores e controle de acessos lógicos"
    }
    
    # Se o ID bater com o mapa amigável, usa ele e ignora o lixo do arquivo
    if id_limpo in PROVEDOR_DE_ENUNCIADOS:
        return PROVEDOR_DE_ENUNCIADOS[id_limpo]
        
    # Fallback caso venha lixo de código por varredura de arquivo
    if "qid" in texto_bruto or "str(" in texto_bruto or "pts" in texto_bruto or "sel" in texto_bruto:
        return f"Quesito de Auditoria Técnica — Referência {id_quesito}"
        
    return texto_bruto

def extrair_enunciado_bruto(nome_arquivo, id_procurado):
    """Varre o arquivo buscando linhas de texto que não contenham lixo de configuração."""
    if not nome_arquivo or not os.path.exists(nome_arquivo):
        return ""
        
    id_str = str(id_procurado).strip()
    id_alternativo = id_str[:-2] if id_str.endswith('.0') else id_str + '.0'
    padroes_busca = [id_str, id_alternativo]
    
    try:
        with open(nome_arquivo, 'r', encoding='utf-8') as f:
            for linha in f:
                linha_limpa = linha.strip()
                if linha_limpa.startswith('#') or 'selectbox' in linha_limpa or 'sidebar' in linha_limpa:
                    continue
                    
                for termo in padroes_busca:
                    if re.search(r'["\']?' + re.escape(termo) + r'["\']?\b', linha_limpa):
                        texto = linha_limpa
                        texto = re.sub(r'st\.\w+\s*\(', '', texto)
                        texto = texto.replace(termo, '').replace('"', '').replace("'", "").replace(":", "").strip()
                        if len(texto) > 10:
                            return texto
    except:
        pass
    return ""

def obter_banco_respostas_real(ano, dimensão):
    """Conecta diretamente no arquivo .db real da dimensão selecionada."""
    mapeamento_bancos = {
        "i-Gov TI": "dados_igov_ti.db",
        "i-Educ": "dados_ieduc.db",
        "i-Saúde": "dados_isaude.db",
        "i-Plan": "dados_iplan.db",
        "i-Amb": "dados_iamb.db",
        "i-Cidade": "dados_iegm.db",
        "i-Fiscal": "dados_ifiscal.db"
    }
    
    arquivo_db = mapeamento_bancos.get(dimensão)
    if not arquivo_db or not os.path.exists(arquivo_db):
        return pd.DataFrame()
        
    try:
        conn = sqlite3.connect(arquivo_db)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tabelas = [row[0] for row in cursor.fetchall()]
        if not tabelas:
            conn.close()
            return pd.DataFrame()
            
        tabela_real = tabelas[0]
        query = f"SELECT * FROM {tabela_real}"
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        coluna_ano = [col for col in df.columns if 'ano' in col.lower()]
        if coluna_ano:
            df[coluna_ano[0]] = df[coluna_ano[0]].astype(str)
            df = df[df[coluna_ano[0]].str.contains(str(ano))]
            
        return df
    except Exception as e:
        st.error(f"Erro ao ler o banco {arquivo_db}: {e}")
        return pd.DataFrame()

def localizar_colunas_exatas(df):
    """Identifica dinamicamente as colunas do banco de dados de respostas."""
    colunas = list(df.columns)
    col_codigo, col_resposta, col_nota, col_usuario = None, None, None, None
    
    for c in colunas:
        nome = str(c).lower()
        if nome in ['id', 'codigo', 'cod', 'id_quesito', 'quesito']:
            col_codigo = c
        elif 'nota' in nome or 'ponto' in nome or 'score' in nome:
            col_nota = c
        elif 'user' in nome or 'quem' in nome or 'usuario' in nome or 'login' in nome:
            col_usuario = c
            
    for c in colunas:
        nome = str(c).lower()
        if c not in [col_codigo, col_nota, col_usuario] and 'ano' not in nome and 'dimen' not in nome:
            if 'resp' in nome or 'situa' in nome or 'alt' in nome or 'opc' in nome or 'valor' in nome:
                col_resposta = c
                break
                
    if not col_codigo: col_codigo = colunas[0]
    if not col_resposta: col_resposta = colunas[1] if len(colunas) > 1 else colunas[0]
    if not col_nota: col_nota = colunas[-2] if len(colunas) > 2 else colunas[0]
    if not col_usuario: col_usuario = colunas[-1] if len(colunas) > 1 else colunas[0]
    
    return col_codigo, col_resposta, col_nota, col_usuario

def aplicar_ordenacao_natural(df, col_codigo):
    """Ordena o DataFrame de forma natural (1.0, 1.1, 1.2, 2.0)."""
    df_copia = df.copy()
    def extrair_valores(texto):
        numeros = re.findall(r'\d+\.\d+|\d+', str(texto))
        return float(numeros[0]) if numeros else 9999.0

    df_copia['temp_ordem_num'] = df_copia[col_codigo].apply(extrair_valores)
    df_copia = df_copia.sort_values(by='temp_ordem_num', ascending=True)
    df_copia = df_copia.drop(columns=['temp_ordem_num'])
    return df_copia

def gerar_pdf_reportlab(ano, dimensão, df_filtrado):
    """Gera o arquivo PDF higienizando as strings brutas do banco de dados."""
    buffer = io.BytesIO()
    
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=landscape(letter), 
        rightMargin=20, 
        leftMargin=20, 
        topMargin=30, 
        bottomMargin=30
    )
    story = []
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=18, leading=22, textColor=colors.HexColor('#001A4D'), alignment=1)
    subtitle_style = ParagraphStyle('SubTitleStyle', parent=styles['Normal'], fontSize=12, leading=16, textColor=colors.HexColor('#64748B'), alignment=1, spaceAfter=20)
    
    cell_text_style = ParagraphStyle('CellTextStyle', parent=styles['Normal'], fontSize=8, leading=11, textColor=colors.black)
    cell_header_style = ParagraphStyle('CellHeaderStyle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=colors.HexColor('#001A4D'))

    story.append(Paragraph("IEG-M Francisco Morato", title_style))
    story.append(Paragraph("EXTRATO OFICIAL DE AUDITORIA E RASTREABILIDADE", subtitle_style))
    story.append(Spacer(1, 10))
    
    story.append(Paragraph(f"<b>Ano de Referência:</b> {ano}", cell_text_style))
    story.append(Paragraph(f"<b>Dimensão Selecionada:</b> {dimensão}", cell_text_style))
    story.append(Spacer(1, 15))
    
    mapeamento_arquivos_py = {
        "i-Gov TI": "igov.py",
        "i-Educ": "ieduc.py",
        "i-Saúde": "isaude.py",
        "i-Plan": "iplan.py",
        "i-Amb": "iamb.py",
        "i-Cidade": "icidade_completo.py",
        "i-Fiscal": "ifiscal.py"
    }
    
    arquivo_da_dimensao = mapeamento_arquivos_py.get(dimensão)
    
    col_codigo, col_resposta, col_nota, col_usuario = localizar_colunas_exatas(df_filtrado)
    df_ordenado = aplicar_ordenacao_natural(df_filtrado, col_codigo)

    data_tabela = [[
        Paragraph("Nº Quesito", cell_header_style),
        Paragraph("Descrição do Quesito", cell_header_style), 
        Paragraph("Resposta / Situação", cell_header_style), 
        Paragraph("Nota", cell_header_style), 
        Paragraph("Usuário Responsável", cell_header_style)
    ]]
    
    for _, linha in df_ordenado.iterrows():
        id_original = str(linha[col_codigo]).strip()
        
        # Pega do arquivo físico se houver texto limpo
        texto_extraido = extrair_enunciado_bruto(arquivo_da_dimensao, id_original)
        
        # 🎯 Passa pelo motor de higienização estrita para remover os lixos de código do log
        texto_final = higienizar_e_traduzir_quesito(id_original, texto_extraido)
            
        data_tabela.append([
            Paragraph(id_original, cell_text_style),
            Paragraph(texto_final, cell_text_style),
            Paragraph(str(linha[col_resposta]), cell_text_style),
            Paragraph(str(linha[col_nota]), cell_text_style),
            Paragraph(str(linha[col_usuario]), cell_text_style)
        ])
    
    larguras = [62, 235, 235, 40, 180]
    
    t = Table(data_tabela, colWidths=larguras, repeatRows=1, splitByRow=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E6F0FF')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),  
        ('ALIGN', (3, 0), (3, -1), 'CENTER'),  
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    
    story.append(t)
    
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

def mostrar_painel_admin(ano_global):
    """Painel do Administrador focado na emissão e exportação direta do PDF de auditoria."""
    st.subheader("🔒 Painel de Controle de Governança")
    
    senha_mestra = st.text_input("🔑 Digite a senha master para desbloquear as informações:", type="password", key="admin_page_password")
    
    if senha_mestra != "fodasse":
        if senha_mestra:
            st.error("❌ Senha Mestra incorreta. Acesso negado.")
        else:
            st.info("💡 Digite a senha master do administrador para liberar a emissão de relatórios.")
        return

    st.success("🔓 Acesso Concedido!")
    
    with st.expander("👥 Visualizar Usuários do Sistema e Atualizar Cadastros"):
        lista_usuarios = []
        for usuario, infos in st.session_state.users_db.items():
            lista_usuarios.append({
                "Nome de Usuário": usuario,
                "E-mail": infos.get("email", "Não cadastrado"),
                "Senha Atual": infos.get("senha", "")
            })
        st.dataframe(pd.DataFrame(lista_usuarios), use_container_width=True)

    st.markdown("---")

    st.markdown("### 📄 Emissão de Relatório Oficial (PDF)")
    
    col_ano, col_dim = st.columns(2)
    with col_ano:
        ano_busca = st.selectbox("1. Selecione o Ano de Auditoria", options=[2024, 2025, 2026, 2027, 2028], index=2)
    with col_dim:
        dim_busca = st.selectbox("2. Selecione a Dimensão para o Extrato", options=["i-Gov TI", "i-Educ", "i-Saúde", "i-Plan", "i-Amb", "i-Cidade", "i-Fiscal"])

    df_filtrado = obter_banco_respostas_real(ano_busca, dim_busca)

    st.markdown("---")
    
    if df_filtrado is not None and not df_filtrado.empty:
        st.info(f"✨ Foram encontrados **{len(df_filtrado)}** quesitos estruturados com sucesso para `{dim_busca}`.")
        
        pdf_oficial = gerar_pdf_reportlab(ano_busca, dim_busca, df_filtrado)
        
        chave_botao = f"btn_final_pdf_{dim_busca.lower().replace(' ', '').replace('-', '')}_{ano_busca}"
        
        st.download_button(
            label=f"📥 Gerar e Baixar PDF Oficial — {dim_busca} ({ano_busca})",
            data=pdf_oficial,
            file_name=f"Extrato_IEGM_{dim_busca.replace(' ', '_')}_{ano_busca}.pdf",
            mime="application/pdf",
            key=chave_botao, 
            use_container_width=True
        )
    else:
        st.warning(f"⚠️ Nenhum dado localizado nos arquivos de banco de dados para `{dim_busca}` no ano `{ano_busca}`.")