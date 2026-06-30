import streamlit as st
import psycopg2

def conectar():
    return psycopg2.connect(
        st.secrets["DATABASE_URL"]
    )
