<<<<<<< HEAD
import streamlit as st
from database import verificar_login

def tela_login():
    st.title("🔐 Login - Sistema IEGM")
    
    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")
    
    if st.button("Entrar"):
        role = verificar_login(usuario, senha)
        if role:
            st.session_state.logged_in = True
            st.session_state.username = usuario
            st.session_state.role = role
            st.rerun()
        else:
=======
import streamlit as st
from database import verificar_login

def tela_login():
    st.title("🔐 Login - Sistema IEGM")
    
    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")
    
    if st.button("Entrar"):
        role = verificar_login(usuario, senha)
        if role:
            st.session_state.logged_in = True
            st.session_state.username = usuario
            st.session_state.role = role
            st.rerun()
        else:
>>>>>>> 0e8801fc2a4dfabd236ca0e127ce6d59d895f969
            st.error("Usuário ou senha incorretos")