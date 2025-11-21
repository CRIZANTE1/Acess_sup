"""
Página PÚBLICA de acesso por reconhecimento facial com STREAM DE VÍDEO
Acesso sem login - pessoa passa pela câmera e é liberada/bloqueada automaticamente
"""
import streamlit as st
import cv2
import numpy as np
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
import av
import threading
import time
from app.supabase_public_client import SupabasePublicClient
from app.face_recognition_utils import (
    is_face_recognition_available,
    find_person_in_frame,
    draw_face_boxes_on_frame,
    _get_insightface_app
)
from app.data_operations import can_register_new_entry
from app.utils import get_sao_paulo_time, clear_access_cache
from app.logger import log_system_action
import logging

logging.basicConfig(level=logging.ERROR)

# Configuração WebRTC
RTC_CONFIGURATION = RTCConfiguration(
    {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
)

# Variáveis globais para compartilhar dados entre threads
class PublicFaceRecognitionState:
    def __init__(self):
        self.last_recognized_person = None
        self.last_recognition_time = 0
        self.recognition_cooldown = 5  # segundos entre reconhecimentos
        self.lock = threading.Lock()
        self.frame_count = 0
        self.process_every_n_frames = 5  # Processa apenas a cada 5 frames


def public_face_access_stream_page():
    """Página pública de acesso com stream de vídeo - SEM LOGIN"""
    
    # Configuração da página
    st.set_page_config(
        page_title="Acesso BAERI",
        page_icon="🔐",
        layout="centered",
        initial_sidebar_state="collapsed"
    )
    
    # Esconde o menu do Streamlit
    hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
    """
    st.markdown(hide_streamlit_style, unsafe_allow_html=True)
    
    # Título principal
    st.markdown("""
    <div style='text-align: center; padding: 20px;'>
        <h1 style='font-size: 3em; margin-bottom: 10px;'>🔐</h1>
        <h1 style='font-size: 2.5em; margin-bottom: 20px;'>ACESSO BAERI</h1>
        <p style='font-size: 1.2em; color: #666;'>Sistema de Reconhecimento Facial Automático</p>
    </div>
    """, unsafe_allow_html=True)
    
    if not is_face_recognition_available():
        st.error("⚠️ Sistema de reconhecimento facial não está disponível.")
        return
    
    # Inicializa estado
    if 'public_face_state' not in st.session_state:
        st.session_state.public_face_state = PublicFaceRecognitionState()
    
    db_ops = SupabasePublicClient()
    face_state = st.session_state.public_face_state
    
    # Instruções
    with st.container():
        st.markdown("""
        <div style='text-align: center; padding: 20px; background-color: #f0f2f6; border-radius: 10px; margin: 20px 0;'>
            <h3>🎥 Como usar:</h3>
            <p>1. Clique em "START" para ativar a câmera</p>
            <p>2. Posicione-se em frente à câmera</p>
            <p>3. Aguarde o reconhecimento automático</p>
            <p>4. Você será liberado ou bloqueado conforme seu cadastro</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Área de status
    status_placeholder = st.empty()
    info_placeholder = st.empty()
    
    # Pre-carrega o modelo
    with st.spinner("🔄 Inicializando sistema..."):
        app = _get_insightface_app()
        if app is None:
            st.error("❌ Erro ao inicializar sistema de reconhecimento.")
            return
    
    st.success("✅ Sistema pronto! Inicie a câmera abaixo.")
    
    # Callback para processar cada frame
    def video_frame_callback(frame: av.VideoFrame) -> av.VideoFrame:
        img = frame.to_ndarray(format="bgr24")
        
        face_state.frame_count += 1
        
        # Processa apenas a cada N frames
        if face_state.frame_count % face_state.process_every_n_frames != 0:
            return av.VideoFrame.from_ndarray(img, format="bgr24")
        
        try:
            current_time = time.time()
            with face_state.lock:
                time_since_last = current_time - face_state.last_recognition_time
                
                if time_since_last > face_state.recognition_cooldown:
                    result = find_person_in_frame(img, db_ops, threshold=0.4)
                    
                    if result:
                        person, distance, bbox = result
                        person_id = person.get('id')
                        person_name = person.get('name', 'N/A')
                        person_company = person.get('company', '')
                        
                        # Verifica se está bloqueado
                        is_blocked, block_reason = db_ops.check_blocked(person_name, person_company)
                        
                        # Atualiza estado
                        face_state.last_recognized_person = person
                        face_state.last_recognition_time = current_time
                        
                        # Define cor da caixa (verde = liberado, vermelho = bloqueado)
                        color = 'green' if not is_blocked else 'red'
                        
                        # Desenha caixa ao redor do rosto
                        faces_info = [{
                            'bbox': bbox,
                            'name': person_name,
                            'confidence': 1.0 - distance
                        }]
                        img = draw_face_boxes_on_frame(img, faces_info, show_names=True)
                        
                        # Registra acesso (em thread separada)
                        threading.Thread(
                            target=register_public_access_async,
                            args=(person, distance, is_blocked, block_reason, db_ops, status_placeholder, info_placeholder)
                        ).start()
                    else:
                        # Detecta rostos mas não reconhece
                        from app.face_recognition_utils import process_video_frame
                        detected_faces = process_video_frame(img)
                        
                        if detected_faces:
                            # REGISTRA LOG de pessoa não identificada (apenas uma vez por detecção)
                            if not hasattr(face_state, 'last_unknown_log_time'):
                                face_state.last_unknown_log_time = 0
                            
                            # Registra log apenas a cada 30 segundos (evita spam)
                            if current_time - face_state.last_unknown_log_time > 30:
                                now = get_sao_paulo_time()
                                log_system_action(
                                    "UNKNOWN_PERSON_DETECTED_PUBLIC",
                                    f"Pessoa não identificada detectada no acesso público em {now.strftime('%d/%m/%Y %H:%M:%S')} (Confidence: {detected_faces[0]['confidence']:.2f})"
                                )
                                face_state.last_unknown_log_time = current_time
                            
                            faces_info = [{
                                'bbox': face['bbox'],
                                'name': 'Não Cadastrado',
                                'confidence': face['confidence']
                            } for face in detected_faces]
                            img = draw_face_boxes_on_frame(img, faces_info, show_names=True)
        
        except Exception as e:
            logging.error(f"Erro no processamento: {e}")
        
        return av.VideoFrame.from_ndarray(img, format="bgr24")
    
    # Stream de vídeo
    st.markdown("---")
    st.markdown("### 📹 Câmera de Reconhecimento")
    
    webrtc_ctx = webrtc_streamer(
        key="public-face-recognition-stream",
        mode=WebRtcMode.SENDRECV,
        rtc_configuration=RTC_CONFIGURATION,
        video_frame_callback=video_frame_callback,
        media_stream_constraints={
            "video": {
                "width": {"ideal": 1280},
                "height": {"ideal": 720},
            },
            "audio": False,
        },
        async_processing=True,
    )
    
    # Rodapé
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; padding: 20px; color: #666;'>
        <p>Sistema de Controle de Acesso BAERI</p>
        <p>Reconhecimento Facial em Tempo Real</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Dicas
    with st.expander("💡 Dicas para melhor reconhecimento"):
        st.markdown("""
        - **Iluminação:** Use boa iluminação, evite sombras no rosto
        - **Posição:** Olhe diretamente para a câmera
        - **Distância:** Mantenha distância de 50cm a 1m da câmera
        - **Movimento:** Passe devagar pela câmera
        - **Expressão:** Rosto neutro, sem óculos escuros ou máscaras
        
        **Tecnologia:** InsightFace com ArcFace (buffalo_s) otimizado para CPU.
        """)


def register_public_access_async(person, distance, is_blocked, block_reason, db_ops, status_placeholder, info_placeholder):
    """Registra acesso público de forma assíncrona"""
    try:
        person_name = person.get('name', 'N/A')
        person_cpf = person.get('cpf', '')
        person_company = person.get('company', '')
        person_id = person.get('id')
        now = get_sao_paulo_time()
        
        if is_blocked:
            # PESSOA BLOQUEADA
            status_placeholder.error(f"🚫 **ACESSO NEGADO: {person_name}**")
            info_placeholder.warning(f"**Motivo:** {block_reason}")
            
            # Registra tentativa de acesso bloqueado
            record_data = {
                'name': person_name,
                'cpf': person_cpf if person_cpf else None,
                'placa': None,
                'marca_carro': None,
                'horario_entrada': now.strftime("%H:%M"),
                'data': now.strftime("%d/%m/%Y"),
                'empresa': person_company if person_company else None,
                'status_entrada': 'Bloqueado',
                'motivo_bloqueio': f"Acesso negado (vídeo): {block_reason}",
                'aprovador': 'Sistema Automático (Vídeo)',
                'data_primeiro_registro': None,
                'person_id': person_id
            }
            try:
                db_ops.add_access_record(record_data)
            except Exception as e:
                logging.error(f"Erro ao registrar acesso bloqueado: {e}")
        
        else:
            # PESSOA LIBERADA
            # Verifica se pode registrar nova entrada
            pode_registrar, motivo = can_register_new_entry(
                person_id=person_id,
                person_name=person_name,
                db_ops=db_ops
            )
            
            if not pode_registrar:
                status_placeholder.warning(f"⚠️ **Entrada não registrada para {person_name}**")
                info_placeholder.info(f"**Motivo:** {motivo}")
                return
            
            # Registra entrada
            record_data = {
                'name': person_name,
                'cpf': person_cpf if person_cpf else None,
                'placa': None,
                'marca_carro': None,
                'horario_entrada': now.strftime("%H:%M"),
                'data': now.strftime("%d/%m/%Y"),
                'empresa': person_company if person_company else None,
                'status_entrada': 'Autorizado',
                'motivo_bloqueio': 'Acesso automático por reconhecimento facial (vídeo)',
                'aprovador': 'Sistema Automático (Vídeo)',
                'data_primeiro_registro': None,
                'person_id': person_id
            }
            record_id = db_ops.add_access_record(record_data)
            success = record_id is not None
            
            if success:
                status_placeholder.success(f"""
                <div style='text-align: center; padding: 20px; background-color: #efe; border: 3px solid #4f4; border-radius: 10px;'>
                    <h1 style='color: #0a0; font-size: 2.5em;'>✅</h1>
                    <h2 style='color: #0a0;'>ACESSO LIBERADO</h2>
                    <p style='font-size: 1.2em;'><strong>{person_name}</strong></p>
                </div>
                """, unsafe_allow_html=True)
                
                info_placeholder.info(f"""
                **Informações do Acesso:**
                - **Horário:** {now.strftime("%H:%M")}
                - **Data:** {now.strftime("%d/%m/%Y")}
                - **Empresa:** {person_company if person_company else 'Não informada'}
                - **Similaridade:** {(1 - distance) * 100:.1f}%
                """)
                
                clear_access_cache()
            else:
                status_placeholder.error(f"❌ Erro ao registrar entrada para {person_name}")
    
    except Exception as e:
        status_placeholder.error(f"❌ Erro ao processar acesso: {e}")
        logging.error(f"Erro ao processar acesso público: {e}")

