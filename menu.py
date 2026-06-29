<<<<<<< HEAD
import streamlit as st
# Aqui fazemos a importação correta do outro arquivo
from icidade import mostrar_formulario_cidade

# Configuração da página (DEVE ficar no menu.py, que é o arquivo principal)
st.set_page_config(page_title="Sistema i-Cidade", layout="wide")

st.sidebar.title("Navegação")
opcao = st.sidebar.selectbox("Selecione a página:", ["Início", "IEGM"])

if opcao == "Início":
    st.title("Bem-vindo ao i-Cidade")
    st.write("Use o menu lateral para navegar.")

elif opcao == "IEGM":
    # Chama a função que está dentro do arquivo icidade.py
=======
import streamlit as st
# Aqui fazemos a importação correta do outro arquivo
from icidade import mostrar_formulario_cidade

# Configuração da página (DEVE ficar no menu.py, que é o arquivo principal)
st.set_page_config(page_title="Sistema i-Cidade", layout="wide")

st.sidebar.title("Navegação")
opcao = st.sidebar.selectbox("Selecione a página:", ["Início", "IEGM"])

if opcao == "Início":
    st.title("Bem-vindo ao i-Cidade")
    st.write("Use o menu lateral para navegar.")

elif opcao == "IEGM":
    # Chama a função que está dentro do arquivo icidade.py
>>>>>>> 0e8801fc2a4dfabd236ca0e127ce6d59d895f969
    mostrar_formulario_cidade()