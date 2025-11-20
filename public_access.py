"""
Ponto de entrada para acesso público (sem login)
Execute este arquivo para acessar a página pública de reconhecimento facial
"""
import streamlit as st
from app.public_face_access import public_face_access_page

# Configuração da página
st.set_page_config(
    page_title="Acesso BAERI",
    page_icon="🔐",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Executa a página pública
public_face_access_page()

