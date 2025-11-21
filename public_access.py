"""
Ponto de entrada para acesso público (sem login)
Execute este arquivo para acessar a página pública de reconhecimento facial
Por padrão, usa VÍDEO EM TEMPO REAL (stream)
Para usar foto, adicione ?video=false na URL
"""
import streamlit as st

# Configuração da página
st.set_page_config(
    page_title="Acesso BAERI",
    page_icon="🔐",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Verifica se deve usar vídeo ou foto
use_video = st.query_params.get("video", "true").lower() == "true"

if use_video:
    # Acesso por vídeo stream (PADRÃO - pessoa passa pela câmera)
    from app.public_face_access_stream import public_face_access_stream_page
    public_face_access_stream_page()
else:
    # Acesso por foto (pessoa tira foto manualmente)
    from app.public_face_access import public_face_access_page
    public_face_access_page()

