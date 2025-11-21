"""
Página de acesso por reconhecimento facial com STREAM DE VÍDEO em tempo real
A pessoa passa pela câmera e é reconhecida automaticamente
"""
import streamlit as st
import cv2
import numpy as np
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
import av
import threading
import time
from datetime import datetime
from app.supabase_db import SupabaseOperations
from app.face_recognition_utils import (
    is_face_recognition_available,
    find_person_in_frame,
    draw_face_boxes_on_frame,
    _get_insightface_app
)
from app.data_operations import add_record, can_register_new_entry
from app.utils import get_sao_paulo_time, clear_access_cache
from app.logger import log_action, log_system_action
from auth.auth_utils import get_user_display_name
import logging

# Configuração WebRTC para melhor compatibilidade
RTC_CONFIGURATION = RTCConfiguration(
    {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
)

# Variáveis globais para compartilhar dados entre threads
class FaceRecognitionState:
    def __init__(self):
        self.last_recognized_person = None
        self.last_recognized_person_id = None  # ID da última pessoa reconhecida
        self.last_recognition_time = 0
        self.last_unknown_time = 0  # Timestamp do último desconhecido detectado
        self.recognition_cooldown = 30  # AUMENTADO: 30 segundos entre reconhecimentos (era 5)
        self.lock = threading.Lock()
        self.frame_count = 0
        self.process_every_n_frames = 5  # Processa apenas a cada 5 frames (otimização)


def face_access_stream_page():
    """Página de monitoramento de acesso com stream de vídeo em tempo real"""
    
    # Marca que está na página de stream
    st.session_state.last_page = 'stream'
    
    st.title("🎥 Monitoramento de Acesso (Vídeo em Tempo Real)")
    st.markdown("### Sistema Automático - Monitoramento Contínuo")
    
    if not is_face_recognition_available():
        from app.face_recognition_utils import (
            INSIGHTFACE_AVAILABLE, CV2_AVAILABLE, 
            NUMPY_AVAILABLE, PIL_AVAILABLE
        )
        
        missing = []
        if not NUMPY_AVAILABLE:
            missing.append("numpy")
        if not PIL_AVAILABLE:
            missing.append("Pillow")
        if not CV2_AVAILABLE:
            missing.append("opencv-python-headless")
        if not INSIGHTFACE_AVAILABLE:
            missing.append("insightface")
        
        error_msg = "⚠️ **Bibliotecas de reconhecimento facial não estão instaladas.**\n\n"
        if missing:
            error_msg += f"**Bibliotecas faltando:** {', '.join(missing)}\n\n"
        error_msg += "**Para instalar, execute:**\n\n"
        error_msg += "```bash\n"
        error_msg += "pip install insightface onnxruntime opencv-python-headless numpy Pillow streamlit-webrtc\n"
        error_msg += "```"
        
        st.error(error_msg)
        return
    
    # Inicializa estado (persistente no session_state para evitar duplicações após rerun)
    if 'face_state' not in st.session_state:
        st.session_state.face_state = FaceRecognitionState()
    
    # Persiste informações de reconhecimento no session_state (sobrevive a reruns)
    if 'last_recognized_person_id_persistent' not in st.session_state:
        st.session_state.last_recognized_person_id_persistent = None
    if 'last_recognition_time_persistent' not in st.session_state:
        st.session_state.last_recognition_time_persistent = 0
    
    db_ops = SupabaseOperations()
    face_state = st.session_state.face_state
    
    # Sincroniza estado persistente com face_state (para manter compatibilidade)
    if st.session_state.last_recognized_person_id_persistent:
        face_state.last_recognized_person_id = st.session_state.last_recognized_person_id_persistent
    if st.session_state.last_recognition_time_persistent > 0:
        face_state.last_recognition_time = st.session_state.last_recognition_time_persistent
    
    st.markdown("""
    ### Como Funciona
    
    1. 🎥 **Monitore o vídeo** ao vivo da câmera de entrada
    2. 🚶 **Pessoas passam** pela câmera naturalmente
    3. 🤖 **Sistema identifica** automaticamente (caixa verde = reconhecido)
    4. ✅ **Acesso registrado** automaticamente para pessoas cadastradas
    5. 📝 **Cadastro rápido** disponível quando pessoa não for reconhecida
    
    ---
    """)
    
    # Área de status e últimas detecções com POPOVERS
    col_status, col_actions = st.columns([2, 1])
    
    with col_status:
        # AVISO DE ENTRADA REGISTRADA (cartão fixo, sem popover)
        if 'show_entry_popup' in st.session_state and st.session_state.show_entry_popup:
            popup = st.session_state.show_entry_popup
            
            with st.container(border=True):
                st.success("🟢 ✅ ENTRADA REGISTRADA")
                st.markdown(
                    f"**👤 Nome:** {popup['name']}  \n"
                    f"**🕐 Horário:** {popup['time']}  \n"
                    f"**🏢 Empresa:** {popup['company']}"
                )
                
                if st.button(
                    "✓ OK - Fechar Notificação",
                    key=f"close_popup_{popup.get('timestamp', 0)}",
                    type="primary",
                    use_container_width=True,
                ):
                    # Limpa apenas o popup, mantém stream ativo
                    st.session_state.show_entry_popup = None
                    # Limpa cache de dados para próxima atualização
                    clear_access_cache()
                    st.rerun()
        
        # AVISO DE PESSOA NÃO RECONHECIDA
        elif 'show_unknown_popup' in st.session_state and st.session_state.show_unknown_popup:
            with st.container(border=True):
                st.warning("🔴 ⚠️ PESSOA NÃO RECONHECIDA DETECTADA!")
                st.info("👤 Uma pessoa não cadastrada passou pela câmera.")
                
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("📝 Cadastrar Agora", key="register_unknown_now", type="primary", use_container_width=True):
                        st.session_state.show_quick_register = True
                        st.session_state.show_unknown_popup = None
                        st.rerun()
                with col_b:
                    if st.button("✓ Ignorar", key="ignore_unknown", use_container_width=True):
                        # Registra que a pessoa não identificada foi ignorada
                        now = get_sao_paulo_time()
                        log_system_action(
                            "UNKNOWN_PERSON_IGNORED",
                            f"Pessoa não identificada foi ignorada pelo operador em {now.strftime('%d/%m/%Y %H:%M:%S')}"
                        )
                        
                        # Limpa popup e dados temporários, mantém stream ativo
                        st.session_state.show_unknown_popup = None
                        st.session_state.last_unknown_frame = None
                        st.session_state.last_unknown_embedding = None
                        clear_access_cache()
                        st.rerun()
        
        # Exibe última mensagem de acesso (se houver)
        elif 'last_access_message' in st.session_state and st.session_state.last_access_message:
            msg = st.session_state.last_access_message
            msg_type = msg.get('type', 'info')
            title = msg.get('title', '')
            info = msg.get('info', '')
            
            # Determina ícone e cor
            icon = "ℹ️"
            if msg_type == 'success':
                icon = "✅"
            elif msg_type == 'warning':
                icon = "⚠️"
            elif msg_type == 'error':
                icon = "❌"
            
            with st.popover(f"{icon} **Notificação do Sistema** - Clique aqui", use_container_width=True):
                st.markdown(f"### {icon} {title}")
                if info:
                    st.info(info)
                
                if st.button("✓ OK - Fechar", key="close_last_msg", type="primary"):
                    st.session_state.last_access_message = None
                    st.rerun()
            
            # Mensagem visual abaixo do popover
            if msg_type == 'success':
                st.success(title)
            elif msg_type == 'warning':
                st.warning(title)
            elif msg_type == 'error':
                st.error(title)
        else:
            st.info("👁️ **Aguardando pessoas...**")
            st.caption("Sistema monitorando entrada em tempo real")
    
    with col_actions:
        st.markdown("### ⚡ Ações Rápidas")
        
        # Botão para pausar/retomar reconhecimento
        if 'stream_paused' not in st.session_state:
            st.session_state.stream_paused = False
        
        if st.button("⏸️ Pausar Reconhecimento" if not st.session_state.stream_paused else "▶️ Retomar Reconhecimento"):
            st.session_state.stream_paused = not st.session_state.stream_paused
            st.rerun()
        
        if st.session_state.stream_paused:
            st.warning("⏸️ Reconhecimento pausado")
        
        # Histórico de últimas entradas (expander)
        if 'entry_history' not in st.session_state:
            st.session_state.entry_history = []
        
        if st.session_state.entry_history:
            with st.expander("📋 Últimas Entradas", expanded=False):
                st.markdown("### 📊 Histórico Recente")
                for idx, entry in enumerate(st.session_state.entry_history[-5:]):
                    st.success(f"✅ **{entry['name']}**")
                    st.caption(f"🕐 {entry['time']} | 🏢 {entry['company']}")
                    if idx < len(st.session_state.entry_history[-5:]) - 1:
                        st.divider()
        
        # Área para cadastro rápido de última pessoa não reconhecida
        if 'last_unknown_frame' in st.session_state and st.session_state.last_unknown_frame is not None:
            st.info("👤 Pessoa não reconhecida detectada!")
            
            if st.button("📝 Cadastrar Última Pessoa", type="primary", use_container_width=True):
                st.session_state.show_quick_register = True
                st.rerun()
    
    # Pre-carrega o modelo antes de iniciar o stream
    with st.spinner("🔄 Carregando modelo de reconhecimento facial..."):
        app = _get_insightface_app()
        if app is None:
            st.error("❌ Erro ao carregar modelo de reconhecimento facial.")
            return
    
    st.success("✅ Modelo carregado! Inicie a câmera abaixo.")
    
    # Callback para processar cada frame do vídeo
    def video_frame_callback(frame: av.VideoFrame) -> av.VideoFrame:
        img = frame.to_ndarray(format="bgr24")
        
        # Incrementa contador de frames
        face_state.frame_count += 1
        
        # Processa apenas a cada N frames (otimização)
        if face_state.frame_count % face_state.process_every_n_frames != 0:
            return av.VideoFrame.from_ndarray(img, format="bgr24")
        
        try:
            # Verifica cooldown (evita reconhecimentos duplicados)
            current_time = time.time()
            with face_state.lock:
                time_since_last = current_time - face_state.last_recognition_time
                
                # Se passou tempo suficiente, tenta reconhecer
                if time_since_last > face_state.recognition_cooldown:
                    result = find_person_in_frame(img, db_ops, threshold=0.4)
                    
                    if result:
                        person, distance, bbox = result
                        person_id = person.get('id')
                        person_name = person.get('name', 'N/A')
                        
                        # VERIFICAÇÃO ADICIONAL: Não processa se for a mesma pessoa que acabou de reconhecer
                        # Usa estado persistente que sobrevive a reruns
                        last_id_persistent = st.session_state.get('last_recognized_person_id_persistent')
                        last_time_persistent = st.session_state.get('last_recognition_time_persistent', 0)
                        time_since_last_persistent = current_time - last_time_persistent
                        
                        # Verifica se é a mesma pessoa E se ainda está no cooldown (mesmo após rerun)
                        if (person_id == last_id_persistent and 
                            time_since_last_persistent < face_state.recognition_cooldown):
                            # Mesma pessoa recente, pula processamento mas desenha caixa
                            faces_info = [{
                                'bbox': bbox,
                                'name': f"{person_name} (Já registrado)",
                                'confidence': 1.0 - distance
                            }]
                            img = draw_face_boxes_on_frame(img, faces_info, show_names=True)
                        else:
                            # Pessoa diferente OU passou tempo suficiente, processa normalmente
                            # Atualiza estado (tanto face_state quanto session_state persistente)
                            face_state.last_recognized_person = person
                            face_state.last_recognized_person_id = person_id
                            face_state.last_recognition_time = current_time
                            
                            # PERSISTE no session_state para sobreviver a reruns
                            st.session_state.last_recognized_person_id_persistent = person_id
                            st.session_state.last_recognition_time_persistent = current_time

                            # Desenha caixa verde ao redor do rosto reconhecido
                            faces_info = [{
                                'bbox': bbox,
                                'name': person_name,
                                'confidence': 1.0 - distance
                            }]
                            img = draw_face_boxes_on_frame(img, faces_info, show_names=True)
                            
                            # Reseta popup de desconhecido (pessoa agora foi reconhecida)
                            if 'unknown_popup_shown' in st.session_state:
                                st.session_state.unknown_popup_shown = False
                            if 'show_unknown_popup' in st.session_state:
                                st.session_state.show_unknown_popup = None
                            
                            # Registra acesso (em thread separada para não travar o vídeo)
                            # Salva informações no session_state para atualização posterior
                            threading.Thread(
                                target=register_access_async,
                                args=(person, distance, db_ops, face_state)
                            ).start()
                    else:
                        # Detecta rostos mas não reconhece
                        from app.face_recognition_utils import process_video_frame
                        detected_faces = process_video_frame(img)
                        
                        if detected_faces:
                            # Salva último frame não reconhecido para cadastro rápido
                            st.session_state.last_unknown_frame = img.copy()
                            st.session_state.last_unknown_embedding = detected_faces[0]['embedding']
                            
                            # Marca que detectou pessoa desconhecida (ativa alerta)
                            if not st.session_state.get('unknown_popup_shown', False):
                                st.session_state.show_unknown_popup = True
                                st.session_state.unknown_popup_shown = True
                                face_state.last_unknown_time = current_time
                                
                                # REGISTRA LOG de pessoa não identificada
                                now = get_sao_paulo_time()
                                log_system_action(
                                    "UNKNOWN_PERSON_DETECTED",
                                    f"Pessoa não identificada detectada no stream em {now.strftime('%d/%m/%Y %H:%M:%S')} (Confidence: {detected_faces[0]['confidence']:.2f})"
                                )
                            
                            # Desenha caixas vermelhas para rostos não reconhecidos
                            faces_info = [{
                                'bbox': face['bbox'],
                                'name': 'Desconhecido',
                                'confidence': face['confidence']
                            } for face in detected_faces]
                            img = draw_face_boxes_on_frame(img, faces_info, show_names=True)
                        else:
                            # Nenhum rosto detectado, reseta flag após 10 segundos
                            if current_time - getattr(face_state, 'last_unknown_time', 0) > 10:
                                if 'unknown_popup_shown' in st.session_state:
                                    st.session_state.unknown_popup_shown = False
        
        except Exception as e:
            st.error(f"Erro no processamento: {e}")
        
        return av.VideoFrame.from_ndarray(img, format="bgr24")
    
    # Stream de vídeo
    st.markdown("### 📹 Câmera de Reconhecimento Facial")
    st.caption("▶️ Para iniciar a câmera, clique em **START** no componente de vídeo abaixo.")
    
    # Configura stream com chave estável (popovers não interferem com o vídeo)
    stream_key = "face-recognition-stream"
    
    webrtc_ctx = webrtc_streamer(
        key=stream_key,
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
    
    # Informação clara: o navegador exige um clique do usuário para iniciar a câmera
    if not webrtc_ctx.state.playing:
        st.info("▶️ Para iniciar o reconhecimento facial, clique em **START** no componente de vídeo acima.")
    else:
        st.success("✅ Câmera ativa - monitorando entrada em tempo real.")
    
    # Sistema de notificações com toasts (funcionam junto com popovers)
    if 'show_entry_popup' in st.session_state and st.session_state.show_entry_popup:
        popup = st.session_state.show_entry_popup
        # Verifica se já foi mostrado o toast (evita duplicação)
        toast_key = f"toast_shown_{popup.get('timestamp', 0)}"
        if not st.session_state.get(toast_key, False):
            st.toast(f"✅ ENTRADA REGISTRADA: {popup['name']} - {popup['time']}", icon="✅")
            st.session_state[toast_key] = True
    
    if 'show_unknown_popup' in st.session_state and st.session_state.show_unknown_popup:
        # Verifica se já foi mostrado o toast
        if not st.session_state.get('unknown_toast_shown', False):
            st.toast("⚠️ PESSOA NÃO RECONHECIDA - Clique no botão acima", icon="⚠️")
            st.session_state.unknown_toast_shown = True
    else:
        # Reseta flag quando popup é fechado
        if 'unknown_toast_shown' in st.session_state:
            del st.session_state.unknown_toast_shown
    
    # Formulário de cadastro rápido (se solicitado)
    if st.session_state.get('show_quick_register', False):
        st.markdown("---")
        st.markdown("### 📝 Cadastro Rápido - Pessoa Não Reconhecida")
        
        # Mostra a imagem capturada
        if 'last_unknown_frame' in st.session_state and st.session_state.last_unknown_frame is not None:
            from PIL import Image
            import cv2
            
            # Converte BGR para RGB para exibição
            frame_rgb = cv2.cvtColor(st.session_state.last_unknown_frame, cv2.COLOR_BGR2RGB)
            img_pil = Image.fromarray(frame_rgb)
            
            col1, col2 = st.columns([1, 2])
            
            with col1:
                st.image(img_pil, caption="Foto Capturada", width=300)
            
            with col2:
                with st.form("quick_register_stream"):
                    st.markdown("**Preencha os dados da pessoa:**")
                    
                    quick_name = st.text_input("Nome Completo *", key="quick_name_stream")
                    quick_cpf = st.text_input("CPF", key="quick_cpf_stream", placeholder="000.000.000-00")
                    quick_company = st.text_input("Empresa", key="quick_company_stream")
                    
                    col_btn1, col_btn2 = st.columns(2)
                    
                    with col_btn1:
                        submit_register = st.form_submit_button("✅ Cadastrar e Liberar Acesso", type="primary", use_container_width=True)
                    
                    with col_btn2:
                        cancel_register = st.form_submit_button("❌ Cancelar", use_container_width=True)
                    
                    if cancel_register:
                        # Limpa estado de cadastro rápido
                        st.session_state.show_quick_register = False
                        st.session_state.last_unknown_frame = None
                        st.session_state.last_unknown_embedding = None
                        clear_access_cache()
                        st.rerun()
                    
                    if submit_register:
                        if not quick_name or not quick_name.strip():
                            st.error("❌ O nome é obrigatório.")
                        else:
                            from app.face_recognition_utils import encoding_to_json
                            from app.utils import format_cpf, validate_cpf
                            
                            # Usa o embedding já capturado
                            embedding = st.session_state.last_unknown_embedding
                            encoding_json = encoding_to_json(embedding)
                            
                            formatted_cpf = format_cpf(quick_cpf) if quick_cpf and validate_cpf(quick_cpf) else None
                            
                            # Cria pessoa no banco
                            new_person_id = db_ops.create_person(
                                name=quick_name.strip(),
                                cpf=formatted_cpf if formatted_cpf else "",
                                company=quick_company.strip() if quick_company else "",
                                face_encoding=encoding_json,
                                face_photo_url=""
                            )
                            
                            if new_person_id:
                                # Salva foto no storage
                                try:
                                    # Converte frame para bytes (JPEG)
                                    _, buffer = cv2.imencode('.jpg', st.session_state.last_unknown_frame)
                                    image_bytes = buffer.tobytes()
                                    
                                    photo_url = db_ops.upload_face_photo(new_person_id, image_bytes, 'jpg')
                                    if photo_url:
                                        db_ops.update_person(new_person_id, face_photo_url=photo_url)
                                except Exception as e:
                                    st.warning(f"Pessoa cadastrada, mas erro ao salvar foto: {e}")
                                
                                # Registra acesso
                                now = get_sao_paulo_time()
                                approver = get_user_display_name()
                                
                                success = add_record(
                                    name=quick_name.strip(),
                                    cpf=formatted_cpf,
                                    placa="",
                                    marca_carro="",
                                    horario_entrada=now.strftime("%H:%M"),
                                    data=now.strftime("%d/%m/%Y"),
                                    empresa=quick_company.strip() if quick_company else "",
                                    status="Autorizado",
                                    motivo="Cadastro rápido via monitoramento (vídeo)",
                                    aprovador=approver,
                                    first_reg_date=now.strftime("%d/%m/%Y"),
                                    person_id=new_person_id
                                )
                                
                                if success:
                                    st.success(f"✅ **{quick_name.strip()} cadastrado(a) e acesso liberado!**")
                                    
                                    # Registra tanto o cadastro rápido quanto a resolução da pessoa desconhecida
                                    log_action(
                                        "FACE_STREAM_QUICK_REGISTER",
                                        f"Cadastro rápido via stream: '{quick_name.strip()}' (ID: {new_person_id})"
                                    )
                                    log_system_action(
                                        "UNKNOWN_PERSON_REGISTERED",
                                        f"Pessoa não identificada foi cadastrada como '{quick_name.strip()}' (ID: {new_person_id}) pelo operador"
                                    )
                                    
                                    # Limpa caches
                                    clear_access_cache()
                                    
                                    # Limpa estado de cadastro
                                    st.session_state.show_quick_register = False
                                    st.session_state.last_unknown_frame = None
                                    st.session_state.last_unknown_embedding = None
                                    st.session_state.force_data_reload = True
                                    
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("Pessoa cadastrada, mas erro ao registrar entrada.")
                            else:
                                st.error("Erro ao cadastrar pessoa.")
        else:
            st.warning("Nenhuma imagem capturada. Aguarde detecção de pessoa não reconhecida.")
            st.session_state.show_quick_register = False
    
    st.markdown("---")
    
    # Seção de Registro de Saída Manual
    st.markdown("### 🚪 Registro de Saída Manual")
    
    with st.expander("📋 Pessoas Presentes (Registrar Saída)", expanded=False):
        try:
            # Busca registros de hoje sem saída
            access_records = db_ops.load_access_records()
            today = get_sao_paulo_time().date()
            today_str = today.strftime("%d/%m/%Y")
            
            # Filtra pessoas que entraram hoje e ainda não saíram
            present_people = []
            for r in access_records:
                record_date = r.get('data')
                horario_saida = r.get('horario_saida')
                
                # Verifica se é de hoje
                is_today = False
                if record_date:
                    try:
                        from datetime import datetime
                        if isinstance(record_date, str):
                            if '/' in record_date:
                                record_date_obj = datetime.strptime(record_date, "%d/%m/%Y").date()
                            else:
                                record_date_obj = datetime.fromisoformat(record_date.split('T')[0]).date()
                        else:
                            record_date_obj = record_date
                        
                        is_today = (record_date_obj == today)
                    except:
                        is_today = (str(record_date) == today_str)
                
                # Se é de hoje e não tem saída, adiciona
                if is_today and (not horario_saida or horario_saida == '' or horario_saida == '-'):
                    present_people.append(r)
            
            if present_people:
                st.info(f"**{len(present_people)} pessoa(s) presente(s)** sem saída registrada")
                
                # Mostra lista de pessoas presentes
                for person in present_people:
                    person_id = person.get('id')
                    person_name = person.get('name', 'N/A')
                    entrada = person.get('horario_entrada', 'N/A')
                    empresa = person.get('empresa', 'N/A')
                    
                    col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
                    
                    with col1:
                        st.write(f"**{person_name}**")
                    with col2:
                        st.write(f"🕐 Entrada: {entrada}")
                    with col3:
                        st.write(f"🏢 {empresa}")
                    with col4:
                        if st.button(f"🚪 Registrar Saída", key=f"exit_{person_id}", type="secondary", use_container_width=True):
                            # Registra horário de saída
                            now = get_sao_paulo_time()
                            horario_saida = now.strftime("%H:%M")
                            exit_date = now.strftime("%d/%m/%Y")
                            
                            # Atualiza registro
                            from app.data_operations import update_exit_time
                            success = update_exit_time(name=person_name, exit_date_str=exit_date, exit_time_str=horario_saida)
                            
                            if success:
                                st.success(f"✅ Saída registrada para {person_name} às {horario_saida}")
                                
                                # Limpa cache e recarrega
                                clear_access_cache()
                                if 'df_acesso_veiculos' in st.session_state:
                                    del st.session_state['df_acesso_veiculos']
                                if 'access_records_cache' in st.session_state:
                                    del st.session_state['access_records_cache']
                                
                                log_action(
                                    "EXIT_REGISTERED_STREAM",
                                    f"Saída registrada manualmente via stream para '{person_name}' (ID: {person_id})"
                                )
                                
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(f"❌ Erro ao registrar saída para {person_name}")
                    
                    st.divider()
            else:
                st.info("✅ Nenhuma pessoa presente no momento (todos já registraram saída)")
        
        except Exception as e:
            st.error(f"Erro ao buscar pessoas presentes: {e}")
    
    st.markdown("---")
    
    # Estatísticas
    st.markdown("### 📊 Estatísticas do Sistema")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        people_count = len(db_ops.get_people_with_face_encoding())
        st.metric("Pessoas Cadastradas", people_count)
    
    with col2:
        all_people = db_ops.client.table('people').select('id', count='exact').execute()
        total_people = all_people.count if hasattr(all_people, 'count') else len(all_people.data) if all_people.data else 0
        st.metric("Total de Pessoas", total_people)
    
    with col3:
        try:
            # FORÇA RELOAD SEM CACHE
            access_records = db_ops.load_access_records()
            today = get_sao_paulo_time().date()
            today_str = today.strftime("%d/%m/%Y")
            today_records = []
            for r in access_records:
                record_date = r.get('data')
                if record_date:
                    try:
                        from datetime import datetime
                        if isinstance(record_date, str):
                            if '/' in record_date:
                                record_date_obj = datetime.strptime(record_date, "%d/%m/%Y").date()
                            else:
                                record_date_obj = datetime.fromisoformat(record_date.split('T')[0]).date()
                        else:
                            record_date_obj = record_date
                        
                        if record_date_obj == today:
                            today_records.append(r)
                    except:
                        if str(record_date) == today_str:
                            today_records.append(r)
        except:
            today_records = []
        st.metric("Acessos Hoje", len(today_records))
    
    # Dicas e instruções
    with st.expander("💡 Dicas para Operadores"):
        st.markdown("""
        ### Monitoramento
        - 📹 Mantenha a câmera posicionada na entrada principal
        - 👁️ Monitore o stream continuamente
        - 🟢 **Caixa Verde** = Pessoa reconhecida e acesso liberado
        - 🔴 **Caixa Vermelha** = Pessoa não reconhecida
        
        ### Cadastro Rápido
        - Quando aparecer pessoa não reconhecida (caixa vermelha)
        - Clique em "📝 Cadastrar Última Pessoa"
        - Preencha os dados e confirme
        - Sistema registra acesso automaticamente
        
        ### Melhores Práticas
        - **Iluminação:** Garanta boa iluminação na área de entrada
        - **Posicionamento:** Câmera na altura do rosto (1,5m-1,7m)
        - **Distância:** Pessoa deve passar a 50cm-1m da câmera
        - **Fluxo:** Oriente pessoas a passarem devagar
        
        ### Tecnologia
        - **Modelo:** InsightFace com ArcFace (buffalo_s)
        - **Processamento:** Otimizado para CPU (ONNX Runtime)
        - **Precisão:** ~95% em condições ideais
        - **Latência:** ~300ms por reconhecimento
        """)


def register_access_async(person, distance, db_ops, face_state):
    """Registra acesso de forma assíncrona (não trava o vídeo)"""
    try:
        person_name = person.get('name', 'N/A')
        person_cpf = person.get('cpf', '')
        person_company = person.get('company', '')
        person_id = person.get('id')
        
        # PROTEÇÃO EXTRA: Verifica última entrada no banco (últimos 2 minutos)
        try:
            access_records = db_ops.load_access_records()
            now = get_sao_paulo_time()
            
            # Filtra registros desta pessoa nas últimas 2 minutos
            recent_records = []
            for r in access_records:
                if r.get('person_id') == person_id or r.get('name', '').lower() == person_name.lower():
                    # Verifica se é recente (últimos 2 minutos)
                    record_time_str = r.get('horario_entrada')
                    record_date_str = r.get('data')
                    
                    if record_time_str and record_date_str:
                        try:
                            from datetime import datetime, timedelta
                            
                            # Converte string de data e hora para datetime
                            if '/' in record_date_str:
                                record_datetime_str = f"{record_date_str} {record_time_str}"
                                record_datetime = datetime.strptime(record_datetime_str, "%d/%m/%Y %H:%M")
                            else:
                                # Tenta formato ISO
                                record_datetime = datetime.fromisoformat(record_date_str.split('T')[0])
                            
                            # Calcula diferença
                            time_diff = (now - record_datetime.replace(tzinfo=now.tzinfo)).total_seconds()
                            
                            # Se foi nos últimos 2 minutos (120 segundos)
                            if time_diff < 120:
                                recent_records.append(r)
                        except:
                            pass
            
            if recent_records:
                # Salva mensagem em session_state para exibição
                st.session_state.last_access_message = {
                    'type': 'warning',
                    'title': f"⚠️ {person_name} já foi registrado há menos de 2 minutos",
                    'info': f"Aguarde {face_state.recognition_cooldown} segundos para novo registro."
                }
                logging.warning(f"{person_name} tentou registrar novamente muito cedo")
                return
                
        except Exception as e:
            logging.error(f"Erro ao verificar registros recentes: {e}")
        
        # Verifica se pode registrar nova entrada (validação padrão)
        pode_registrar, motivo = can_register_new_entry(
            person_id=person_id,
            person_name=person_name,
            db_ops=db_ops
        )
        
        if not pode_registrar:
            # Salva mensagem em session_state
            st.session_state.last_access_message = {
                'type': 'warning',
                'title': f"⚠️ Entrada não registrada para {person_name}",
                'info': motivo
            }
            logging.warning(f"Entrada não registrada para {person_name}: {motivo}")
            return
        
        # Registra entrada
        now = get_sao_paulo_time()
        approver = get_user_display_name()
        
        # Busca último registro para pegar dados como placa
        access_records = db_ops.load_access_records()
        last_record = None
        if access_records:
            person_records = [r for r in access_records if r.get('person_id') == person_id or r.get('name', '').lower() == person_name.lower()]
            if person_records:
                person_records.sort(key=lambda x: x.get('created_at', ''), reverse=True)
                last_record = person_records[0]
        
        placa = last_record.get('placa', '') if last_record else ''
        marca_carro = last_record.get('marca_carro', '') if last_record else ''
        empresa = person_company if person_company else (last_record.get('empresa', '') if last_record else '')
        
        # Registra entrada
        success = add_record(
            name=person_name,
            cpf=person_cpf,
            placa=placa,
            marca_carro=marca_carro,
            horario_entrada=now.strftime("%H:%M"),
            data=now.strftime("%d/%m/%Y"),
            empresa=empresa,
            status="Autorizado",
            motivo="Acesso automático por reconhecimento facial (vídeo)",
            aprovador=approver,
            first_reg_date="",
            person_id=person_id
        )
        
        if success:
            # Dados para exibição imediata na interface
            entry_data = {
                'name': person_name,
                'time': now.strftime("%H:%M"),
                'company': empresa if empresa else 'Não informada',
                'timestamp': time.time()
            }
            
            # Salva popup diretamente (sem fluxo de verificação extra)
            st.session_state.show_entry_popup = entry_data
            
            # Limpa mensagens antigas que podem interferir
            if 'last_access_message' in st.session_state:
                del st.session_state['last_access_message']
            
            # Adiciona ao histórico de entradas (mantém últimas 10)
            if 'entry_history' not in st.session_state:
                st.session_state.entry_history = []
            st.session_state.entry_history.append(
                {
                    'name': entry_data['name'],
                    'time': entry_data['time'],
                    'company': entry_data['company'],
                }
            )
            if len(st.session_state.entry_history) > 10:
                st.session_state.entry_history = st.session_state.entry_history[-10:]
            
            log_action(
                "FACE_ACCESS_STREAM_GRANTED",
                f"Acesso concedido via reconhecimento facial (stream) para '{person_name}' (ID: {person_id}, Distância: {distance:.4f})"
            )
            
            # LIMPA TODOS OS CACHES DE DADOS
            clear_access_cache()
            
            # Limpa cache do session_state para forçar reload
            keys_to_delete = ['df_acesso_veiculos', 'access_records_cache', 'last_cache_update']
            for key in keys_to_delete:
                if key in st.session_state:
                    del st.session_state[key]
            
            # Força flag de atualização para recarregar dados nas outras páginas
            st.session_state.force_data_reload = True
            
            # Log para debug
            logging.info(f"✅ Entrada registrada para {person_name} - popup preparado para exibição")
        else:
            # Salva erro em session_state
            st.session_state.last_access_message = {
                'type': 'error',
                'title': f"❌ Erro ao registrar entrada para {person_name}",
                'info': "Tente novamente ou registre manualmente"
            }
    
    except Exception as e:
        # Salva erro em session_state (não atualiza UI da thread)
        st.session_state.last_access_message = {
            'type': 'error',
            'title': "❌ Erro ao processar acesso",
            'info': str(e)
        }

