"""
Aplicação principal Streamlit - IEG-M Francisco Morato
Sistema de gestão e análise de indicadores IEG-M
Integra o módulo icidade_original.py preservado
"""

import streamlit as st
import pandas as pd
from datetime import datetime

# Importar módulos
from constants import DIMENSIONS, ADMIN_USER, AVAILABLE_YEARS
from database import verify_user, init_database

# Importar o módulo icidade original preservado
import icidade_completo as icidade

# Configuração da página
st.set_page_config(
    page_title="IEG-M Francisco Morato",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS personalizado para design CAD
st.markdown(
    """
    <style>
    :root {
        --primary-color: #001A4D;
        --secondary-color: #003D99;
        --accent-color: #00BFFF;
        --success-color: #22C55E;
        --warning-color: #EAB308;
        --danger-color: #DC2626;
    }
    
    .main {
        background: linear-gradient(135deg, #001A4D 0%, #003D99 100%);
        color: #FFFFFF;
    }
    
    .stTitle {
        color: #FFFFFF;
        font-weight: bold;
        text-align: center;
    }
    
    .cad-frame {
        border: 3px solid #FFFFFF;
        border-radius: 2px;
        padding: 20px;
        background: rgba(0, 26, 77, 0.8);
        box-shadow: 0 0 20px rgba(0, 191, 255, 0.3);
        margin: 10px 0;
    }
    
    .dimension-card {
        border: 2px solid #00BFFF;
        border-radius: 2px;
        padding: 15px;
        background: rgba(0, 61, 153, 0.6);
        cursor: pointer;
        transition: all 0.3s ease;
        margin: 5px 0;
    }
    
    .dimension-card:hover {
        background: rgba(0, 191, 255, 0.2);
        box-shadow: 0 0 15px rgba(0, 191, 255, 0.5);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Inicializar banco de dados
init_database()

# Inicializar session state
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.username = None
    st.session_state.role = None
    st.session_state.current_page = "login"
    st.session_state.selected_dimension = None
    st.session_state.ano_referencia_global = 2026


def login_page():
    """Página de login."""
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown(
            """
            <div class="cad-frame">
                <h1 style="text-align: center; color: #FFFFFF;">IEG-M</h1>
                <h2 style="text-align: center; color: #FFFFFF;">Francisco Morato</h2>
                <p style="text-align: center; color: #00BFFF;">SISTEMA DE AUDITORIA MUNICIPAL</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("---")

        username = st.text_input(
            "👤 Usuário",
            placeholder="jefferson.espanha",
            key="login_username",
        )

        password = st.text_input(
            "🔐 Senha",
            type="password",
            placeholder="••••••••",
            key="login_password",
        )

        if st.button("🔓 ACESSAR SISTEMA", use_container_width=True):
            if username and password:
                success, role = verify_user(username, password)
                if success:
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    st.session_state.role = role
                    st.session_state.current_page = "dashboard"
                    st.success("✅ Login realizado com sucesso!")
                    st.rerun()
                else:
                    st.error("❌ Usuário ou senha incorretos!")
            else:
                st.warning("⚠️ Preencha todos os campos!")

        st.markdown("---")
        st.markdown(
            """
            <p style="text-align: center; color: #999999; font-size: 12px;">
            © 2026 IEG-M FRANCISCO MORATO | Versão 1.0 | Acesso Restrito
            </p>
            """,
            unsafe_allow_html=True,
        )


def dashboard_page():
    """Página de seleção de dimensão."""
    # Cabeçalho
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            f"""
            <div style="text-align: center; padding: 20px;">
                <h1 style="color: #FFFFFF;">IEG-M Francisco Morato</h1>
                <p style="color: #00BFFF;">Bem-vindo, {st.session_state.username}!</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Botão de logout
    col1, col2, col3 = st.columns([3, 1, 1])
    with col3:
        if st.button("🚪 Sair"):
            st.session_state.authenticated = False
            st.session_state.username = None
            st.session_state.role = None
            st.session_state.current_page = "login"
            st.rerun()

    st.markdown("---")

    # Seletor de ano
    st.markdown("### 📅 Selecione o Ano de Referência")
    selected_year = st.select_slider(
        "Ano",
        options=AVAILABLE_YEARS,
        value=st.session_state.ano_referencia_global,
        label_visibility="collapsed",
    )
    st.session_state.ano_referencia_global = selected_year

    st.markdown("---")

    # Seleção de dimensão
    st.markdown("### 📊 Selecione a Dimensão")

    cols = st.columns(2)
    for idx, dimension in enumerate(DIMENSIONS):
        with cols[idx % 2]:
            if st.button(
                f"📈 {dimension}",
                use_container_width=True,
                key=f"dim_{idx}",
            ):
                st.session_state.selected_dimension = dimension
                st.session_state.current_page = "dimension"
                st.rerun()

    st.markdown("---")

    # Informações do sistema
    st.markdown(
        """
        <div style="text-align: center; color: #999999; font-size: 12px; margin-top: 40px;">
            <p>Sistema de Gestão de Indicadores IEG-M Francisco Morato</p>
            <p>Versão 1.0 | © 2026</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def dimension_page():
    """Página de dimensão selecionada."""
    dimension = st.session_state.selected_dimension
    year = st.session_state.ano_referencia_global

    # Cabeçalho
    col1, col2, col3 = st.columns([1, 2, 1])
    with col1:
        if st.button("⬅️ Voltar"):
            st.session_state.current_page = "dashboard"
            st.rerun()

    with col2:
        st.markdown(
            f"""
            <div style="text-align: center;">
                <h2 style="color: #FFFFFF;">{dimension} - {year}</h2>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        if st.button("🚪 Sair"):
            st.session_state.authenticated = False
            st.session_state.username = None
            st.session_state.role = None
            st.session_state.current_page = "login"
            st.rerun()

    st.markdown("---")

    # Renderizar dimensão apropriada
    if dimension == "i-Cidade":
        # Usar o módulo icidade_original.py preservado
        icidade.init_db()
        icidade.mostrar_formulario_cidade()
    else:
        st.info(f"🔧 {dimension} - Em desenvolvimento")


# Lógica principal
if not st.session_state.authenticated:
    login_page()
else:
    if st.session_state.current_page == "dashboard":
        dashboard_page()
    elif st.session_state.current_page == "dimension":
        dimension_page()


if __name__ == "__main__":
    pass
