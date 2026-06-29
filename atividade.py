import math
import streamlit as st

def calcular_e_individual(A, B, C, D):
    """
    Calcula o valor de E para um programa individual.
    """
    E1 = 0
    if A is not None and A != 0:
        E1 = B / A

    E2 = 0
    if C is not None and C != 0:
        E2 = D / C

    return abs(E1 - E2)

def calcular_ef(programas):
    """
    Calcula o valor de Ef.
    """
    if not programas:
        return 0.0

    soma_A = sum(p['A'] for p in programas if p['A'] is not None)
    soma_C = sum(p['C'] for p in programas if p['C'] is not None)

    if soma_A == 0 or soma_C == 0:
        return 1.0

    valores_E = []
    for p in programas:
        A_val = p.get('A')
        B_val = p.get('B')
        C_val = p.get('C')
        D_val = p.get('D')

        if A_val is None or C_val is None:
            valores_E.append(1.0)
        else:
            valores_E.append(calcular_e_individual(A_val, B_val, C_val, D_val))

    if not valores_E:
        return 1.0

    return sum(valores_E) / len(valores_E)

def calcular_h_individual(C, D, F, G):
    """
    Calcula o valor de H para uma ação individual.
    """
    H1 = 0
    if C is not None and C != 0:
        H1 = D / C

    H2 = 0
    if F is not None and F != 0:
        H2 = G / F

    return abs(H1 - H2)

def calcular_hf(acoes):
    """
    Calcula o valor de Hf.
    """
    if not acoes:
        return 0.0

    soma_C = sum(a['C'] for a in acoes if a['C'] is not None)
    soma_F = sum(a['F'] for a in acoes if a['F'] is not None)

    if soma_C == 0 or soma_F == 0:
        return 1.0

    valores_H = []
    for a in acoes:
        C_val = a.get('C')
        D_val = a.get('D')
        F_val = a.get('F')
        G_val = a.get('G')

        if C_val is None or F_val is None:
            valores_H.append(1.0)
        else:
            valores_H.append(calcular_h_individual(C_val, D_val, F_val, G_val))

    if not valores_H:
        return 1.0

    return sum(valores_H) / len(valores_H)

def calcular_pontuacao(resultado_final):
    """
    Calcula a pontuação com base no resultado final (Ef ou Hf).
    """
    if resultado_final <= 0.2:
        return 250.0
    elif 0.2 < resultado_final < 0.4:
        return ((0.4 - resultado_final) / 0.2) * 250.0
    else:
        return 0.0

programas_e_indicadores_iplan = {
    1: {
        'programa': 'GESTÃO DO LEGISLATIVO',
        'indicadores': [
            'Proposituras apresentadas', 'Quantidade de acessos ao sitio da Câmara',
            'Quantidade de acessos as mídias sociais da câmara', 'Quantidade de atendimentos na ouvidoria',
            'Quantidade de audiências publicas realizadas', 'Quantidade de pedidos de informações via sic',
            'Quantidade de reuniões de comissões permanentes', 'Quantidade de sessões realizadas',
            'Quantidade de sessões transmitidas ao vivo'
        ]
    },
    2: {
        'programa': 'GESTÃO E GOVERNANÇA',
        'indicadores': [
            'Índice de Efetividade da Gestão Municipal', 'Número mensal de acessos ao Portal de Transparência',
            'Quantidade de canais de comunicação e divulgação das ações governamentais'
        ]
    },
    3: {
        'programa': 'CIDADE SOLIDÁRIA',
        'indicadores': ['Famílias atendidas no fundo Social de Solidariedade', 'Número de idosos atendidos no fundo Social de Solidariedade']
    },
    4: {
        'programa': 'GESTÃO DO JURÍDICO E DA CIDADANIA',
        'indicadores': ['Departamento Atendido']
    },
    5: {
        'programa': 'DESENVOLVIMENTO ECONÔMICO',
        'indicadores': ['Departamento Atendido', 'Abertura de novas empresas', 'Fiscalização nas empresas e comércios', 'Índice de Efetividade da Gestão Municipal (I-EGM Fiscal)', 'Índice de Efetividade da Gestão Municipal (I-EGM Planejamento)']
    },
    6: {
        'programa': 'GESTÃO ORÇAMENTÁRIA, ADMINISTRATIVA E FISCAL',
        'indicadores': ['Departamento Atendido', 'Índice de Efetividade da Gestão Municipal (I-EGM Fiscal)', 'Índice de Efetividade da Gestão Municipal (I-EGM GOV TI)', 'Índice de Efetividade da Gestão Municipal (I-EGM Planejamento)']
    },
    7: {
        'programa': 'DESENVOLVIMENTO URBANO SUSTENTÁVEL',
        'indicadores': ['Déficit de vias pavimentadas', 'Mortes no trânsito (INFOSIGA-SP)', 'Índice de Efetividade da Gestão Municipal (I-EGM Cidade)', 'Coleta seletiva de resíduos sólidos', 'Déficit de iluminação pública/ pontos luminosos', 'Frota do Transporte Coletivo Adaptado (percentual)', 'Número de castrações de cães e gatos', 'Revitalização de praças e vielas', 'Índice de Efetividade de Gestão Municipal (I-EGM AMB)', 'Índice de atendimento urbano de esgoto (SEADE)', 'Índice de esgoto tratado (SEADE)']
    },
    8: {
        'programa': 'EDUCAÇÃO COM EQUIDADE E QUALIDADE',
        'indicadores': ['Alunos com Atendimento Educacional Especializado (AEE)', 'Alunos matriculados na rede municipal - Ensino Fundamental', 'Alunos matriculados na rede municipal - Pré-escola', 'Escolas com programas em tempo integral (Ensino Fundamental 1)', 'Indicador nutricional (resto ingestão)/ percentual', 'Número de alunos beneficiados pelo Programa de Alimentação Escolar.', 'Índice de Efetividade da Gestão Municipal (I-EGM Educação)', 'Alunos em atividade complementar (contraturno)', 'Alunos matriculados na rede municipal - Creche', 'Alunos matriculados na rede municipal - EJA', 'Índice de Desenvolvimento da Educação Básica - IDEB nos anos iniciais do Ensino Fundamental', 'Índice de aprendizado em Matemática / média proficiência Prova Brasil', 'Índice de aprendizado em Português/ média proficiência Prova Brasil']
    },
    9: {
        'programa': 'ESPORTE, LAZER E QUALIDADE DE VIDA',
        'indicadores': ['Número de Centros Esportivos', 'Número de modalidades esportivas ofertadas', 'Número de cidadãos idosos atendidos', 'Número de crianças, adolescentes e jovens atendidos']
    },
    10: {
        'programa': 'CULTURA E CIDADANIA',
        'indicadores': ['Apoiar projetos culturais/ oficineiros', 'Número de Equipamentos Culturais', 'Número de alunos nas Oficinas Culturais', 'Lançar editais de fomento cultural', 'Número de livros no acervo da Secretaria de Cultura e Turismo', 'Visitantes nos equipamentos culturais']
    },
    11: {
        'programa': 'GESTÃO DO SISTEMA ÚNICO DE ASSISTÊNCIA SOCIAL - SUAS',
        'indicadores': ['Adolescentes em Cumprimento de Medidas Sócio-Educativas (LA e ou PSC)', 'Benefício de Prestação Continuada - Idoso', 'Benefício de Prestação Continuada - PCD USUÁRIO', 'Benefícios Eventuais', 'Famílias beneficiárias - Programa Bolsa Família', 'Programa Criança Feliz', 'Rede Socioassistencial Privada - Organização da Sociedade Civil (OSC)', 'Serviço de Convivência e Fortalecimento de Vínculos - SCFV', 'Serviço de Proteção e Atendimento Especializado a Famílias e Indivíduos - PAEFI', 'Famílias cadastradas - Cadastro Único', 'Quantidade de Pessoas em Situação de Rua no CadÚnico', 'Segurança Alimentar e Nutricional', 'Serviço da Proteção e Atendimento Integral à Família - PAIF']
    },
    12: {
        'programa': 'FORTALECIMENTO DO SISTEMA ÚNICO DE SAÚDE - SUS',
        'indicadores': ['Cobertura de consultas pré-natal', 'Cobertura populacional estimada de saúde bucal na atenção básica', 'Cobertura populacional estimada pelas equipes de Atenção Básica', 'Cobertura vacinal da tríplice viral no primeiro ano', 'Incidência de sífilis congênita /casos / 100 mil habitantes', 'Percentual de óbitos investigados de mulheres em idade fértil', 'Taxa de mortalidade infantil / óbitos/ 1 mil', 'Taxa de mortalidade materna / óbitos', 'Índice de Efetividade da Gestão Municipal (I-EGM Saúde)', 'Consultas médicas SUS / habitantes', 'Incidência de dengue/ casos/ 100 mil habitantes']
    },
    13: {
        'programa': 'SEGURIDADE SOCIAL E BENEFÍCIOS DOS FUNCIONÁRIOS PÚBLICOS - FUSBEMO',
        'indicadores': ['Quantidade de aposentados e pensionistas do Regime Próprio de Previdência BENEFÍCIOS']
    },
    14: {
        'programa': 'CIDADE SEGURA, INCLUSIVA, RESILIENTE E SUSTENTÁVEL',
        'indicadores': ['Mortes no trânsito (INFOSIGA-SP)', 'Quantidade de intervenções realizadas em áreas de riscos', 'Índice de Efetividade de Gestão Municipal', 'Índice de Efetividade da Gestão Municipal (I-EGM Cidade)']
    },
    15: {
        'programa': 'GESTÃO INTEGRADA URBANA SUSTENTÁVEL',
        'indicadores': ['COLETA SELETIVA RESÍDUOS SÓLIDOS (PGRNS)', 'NÚMERO AUXÍLIO ALUGUEL (PDHS)', 'NÚMERO DE CASTRAÇÃO E IDENTIFICAÇÃO DE CÃES E GATOS (PBEA)', 'NÚMERO DE LICENCIAMENTO AMBIENTAL - BAIXO E MÉDIO IMPACTO (PGRNS)', 'NÚMERO DE OCORRÊNCIAS / MCE', 'OCORRÊNCIAS DE CAPTURA DE ANIMAIS SILVESTRES (PBEA)', 'QUANTIDADE DE AÇÕES DE EDUCAÇÃO AMBIENTAL (PEA)', 'QUANTIDADE DE CONSTRUÇÃO DE HIS', 'RF. MORATO, MEU LAR LEGAL (PDHS)']
    },
    16: {
        'programa': 'CONTROLE INTERNO',
        'indicadores': ['Número de Acessos ao Portal da Transparência', 'Número de Ações do Controle Externo - TCE SP', 'Percentual de Recomendações Implementadas', 'Percentual de Respostas da Ouvidoria dentro do Prazo E-SIC', 'Número de Auditorias Realizadas', 'Número de Ações e Fiscalização de Serviços ao Usuário', 'Número de Ações e Fiscalização do E-SIC', 'Número de Ações e Fiscalização ao Portal da Transparência']
    }
}

# --- FUNÇÃO PRINCIPAL DE RENDERIZAÇÃO NO STREAMLIT ---
def mostrar_formulario_atividade():
    st.subheader("📋 Painel de Controle de Programas e Atividades (i-PLAN)")
    
    # Abas para separar os cálculos de Ef e Hf
    tab1, tab2, tab3 = st.tabs(["📊 Coerência de Indicadores (Ef)", "💰 Recursos vs Metas (Hf)", "🔍 Visualizar Lista de Programas"])
    
    with tab1:
        st.markdown("#### Cálculo de Coerência entre Indicadores e Metas (Ef)")
        st.write("Insira os valores correspondentes para simular o cálculo:")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            a_val = st.number_input("A: Indicador Previsto Inicialmente", value=100.0, key="ef_a")
        with col2:
            b_val = st.number_input("B: Indicador Realizado", value=90.0, key="ef_b")
        with col3:
            c_val = st.number_input("C: Valor da Meta da Ação", value=50.0, key="ef_c")
        with col4:
            d_val = st.number_input("D: Resultado da Meta Realizado", value=45.0, key="ef_d")
            
        programas_simulados = [{'A': a_val, 'B': b_val, 'C': c_val, 'D': d_val}]
        ef_res = calcular_ef(programas_simulados)
        pontos_ef = calcular_pontuacao(ef_res)
        
        st.metric(label="Ef Calculado", value=f"{ef_res:.4f}")
        st.metric(label="Pontuação do Ef (Máx 250)", value=f"{pontos_ef:.2f}")

    with tab2:
        st.markdown("#### Confronto de Metas Físicas vs Recursos Financeiros (Hf)")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            c_hf = st.number_input("C: Valor da Meta da Ação", value=50.0, key="hf_c")
        with col2:
            d_hf = st.number_input("D: Resultado da Meta Realizado", value=25.0, key="hf_d")
        with col3:
            f_hf = st.number_input("F: Orçamento Fixado Final", value=100.0, key="hf_f")
        with col4:
            g_hf = st.number_input("G: Valor Liquidado", value=100.0, key="hf_g")
            
        acoes_simuladas = [{'C': c_hf, 'D': d_hf, 'F': f_hf, 'G': g_hf}]
        hf_res = calcular_hf(acoes_simuladas)
        pontos_hf = calcular_pontuacao(hf_res)
        
        st.metric(label="Hf Calculado", value=f"{hf_res:.4f}")
        st.metric(label="Pontuação do Hf (Máx 250)", value=f"{pontos_hf:.2f}")

    with tab3:
        st.markdown("#### Programas Estruturados no Plano")
        
        # Seleção Dinâmica de Programa
        nomes_programas = [data['programa'] for data in programas_e_indicadores_iplan.values()]
        programa_selecionado = st.selectbox("Selecione um programa para listar seus indicadores:", nomes_programas)
        
        for chave, data in programas_e_indicadores_iplan.items():
            if data['programa'] == programa_selecionado:
                st.info(f"**Programa {chave}:** {data['programa']}")
                st.write("**Indicadores associados:**")
                for ind in data['indicadores']:
                    st.markdown(f"- {ind}")

# Mantém o bloco de teste original caso o arquivo seja executado diretamente
if __name__ == "__main__":
    print("Executando como script de teste...")
    ef_teste = 0.25
    print(f"Teste de Validação (Ef=0.25): {calcular_pontuacao(ef_teste)}")