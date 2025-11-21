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
from app.supabase_db import SupabaseOperations
from app.face_recognition_utils import (
    is_face_recognition_available,
    find_person_in_frame,
    draw_face_boxes_on_frame,
    _get_insightface_app
)
from app.data_operations import add_record, can_register_new_entry
from app.utils import get_sao_paulo_time, clear_access_cache
from app.logger import log_action
from auth.auth_utils import get_user_display_name

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
        self.recognition_cooldown = 30  # AUMENTADO: 30 segundos entre reconhecimentos (era 5)
        self.lock = threading.Lock()
        self.frame_count = 0
        self.process_every_n_frames = 5  # Processa apenas a cada 5 frames (otimização)


def face_access_stream_page():
    """Página de monitoramento de acesso com stream de vídeo em tempo real"""
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
    
    # Inicializa estado
    if 'face_state' not in st.session_state:
        st.session_state.face_state = FaceRecognitionState()
    
    db_ops = SupabaseOperations()
    face_state = st.session_state.face_state
    
    st.markdown("""
    ### Como Funciona
    
    1. 🎥 **Monitore o vídeo** ao vivo da câmera de entrada
    2. 🚶 **Pessoas passam** pela câmera naturalmente
    3. 🤖 **Sistema identifica** automaticamente (caixa verde = reconhecido)
    4. ✅ **Acesso registrado** automaticamente para pessoas cadastradas
    5. 📝 **Cadastro rápido** disponível quando pessoa não for reconhecida
    
    ---
    """)
    
    # Área de status e últimas detecções
    col_status, col_actions = st.columns([2, 1])
    
    with col_status:
        status_placeholder = st.empty()
        info_placeholder = st.empty()
    
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
                        if person_id == face_state.last_recognized_person_id:
                            # Mesma pessoa, pula processamento mas desenha caixa
                            faces_info = [{
                                'bbox': bbox,
                                'name': f"{person_name} (Já registrado)",
                                'confidence': 1.0 - distance
                            }]
                            img = draw_face_boxes_on_frame(img, faces_info, show_names=True)
                        else:
                            # Pessoa diferente da última, processa normalmente
                            # Atualiza estado
                            face_state.last_recognized_person = person
                            face_state.last_recognized_person_id = person_id
                            face_state.last_recognition_time = current_time

                            # Desenha caixa verde ao redor do rosto reconhecido
                            faces_info = [{
                                'bbox': bbox,
                                'name': person_name,
                                'confidence': 1.0 - distance
                            }]
                            img = draw_face_boxes_on_frame(img, faces_info, show_names=True)
                            
                            # Registra acesso (em thread separada para não travar o vídeo)
                            threading.Thread(
                                target=register_access_async,
                                args=(person, distance, db_ops, status_placeholder, info_placeholder, face_state)
                            ).start()
                    else:
                        # Detecta rostos mas não reconhece
                        from app.face_recognition_utils import process_video_frame
                        detected_faces = process_video_frame(img)
                        
                        if detected_faces:
                            # Salva último frame não reconhecido para cadastro rápido
                            st.session_state.last_unknown_frame = img.copy()
                            st.session_state.last_unknown_embedding = detected_faces[0]['embedding']
                            
                            # Desenha caixas vermelhas para rostos não reconhecidos
                            faces_info = [{
                                'bbox': face['bbox'],
                                'name': 'Desconhecido',
                                'confidence': face['confidence']
                            } for face in detected_faces]
                            img = draw_face_boxes_on_frame(img, faces_info, show_names=True)
        
        except Exception as e:
            st.error(f"Erro no processamento: {e}")
        
        return av.VideoFrame.from_ndarray(img, format="bgr24")
    
    # Stream de vídeo
    st.markdown("### 📹 Câmera de Reconhecimento Facial")
    
    webrtc_ctx = webrtc_streamer(
        key="face-recognition-stream",
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
                        st.session_state.show_quick_register = False
                        st.session_state.last_unknown_frame = None
                        st.session_state.last_unknown_embedding = None
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
                                cpf=formatted_cpf,
                                company=quick_company.strip() if quick_company else None,
                                face_encoding=encoding_json,
                                face_photo_url=None
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
                                    log_action(
                                        "FACE_STREAM_QUICK_REGISTER",
                                        f"Cadastro rápido via stream: '{quick_name.strip()}' (ID: {new_person_id})"
                                    )
                                    clear_access_cache()
                                    
                                    # Limpa estado
                                    st.session_state.show_quick_register = False
                                    st.session_state.last_unknown_frame = None
                                    st.session_state.last_unknown_embedding = None
                                    
                                    time.sleep(2)
                                    st.rerun()
                                else:
                                    st.error("Pessoa cadastrada, mas erro ao registrar entrada.")
                            else:
                                st.error("Erro ao cadastrar pessoa.")
        else:
            st.warning("Nenhuma imagem capturada. Aguarde detecção de pessoa não reconhecida.")
            st.session_state.show_quick_register = False
    
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


def register_access_async(person, distance, db_ops, status_placeholder, info_placeholder, face_state):
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
                status_placeholder.warning(f"⚠️ **{person_name} já foi registrado há menos de 2 minutos**")
                info_placeholder.info(f"**Aguarde** {face_state.recognition_cooldown} segundos para novo registro.")
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
            status_placeholder.warning(f"⚠️ **Entrada não registrada para {person_name}**")
            info_placeholder.info(f"**Motivo:** {motivo}")
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
            status_placeholder.success(f"✅ **ACESSO LIBERADO: {person_name}**")
            info_placeholder.info(f"""
            **Informações:**
            - **Horário:** {now.strftime("%H:%M")}
            - **Empresa:** {empresa if empresa else 'Não informada'}
            - **Similaridade:** {(1 - distance) * 100:.1f}%
            
            ⏱️ **Próximo registro:** Após {face_state.recognition_cooldown} segundos
            """)
            
            log_action(
                "FACE_ACCESS_STREAM_GRANTED",
                f"Acesso concedido via reconhecimento facial (stream) para '{person_name}' (ID: {person_id}, Distância: {distance:.4f})"
            )
            
            clear_access_cache()
        else:
            status_placeholder.error(f"❌ Erro ao registrar entrada para {person_name}")
    
    except Exception as e:
        status_placeholder.error(f"❌ Erro ao processar acesso: {e}")

