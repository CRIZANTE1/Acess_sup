"""
Página PÚBLICA de acesso por reconhecimento facial
Acesso sem login - pessoa tira foto e é liberada ou bloqueada automaticamente
"""
import streamlit as st
from app.supabase_public_client import SupabasePublicClient
from app.face_recognition_utils import (
    is_face_recognition_available,
    find_matching_person,
    process_uploaded_image
)
# is_entity_blocked será implementado no cliente público
from app.utils import get_sao_paulo_time, clear_access_cache
# Nota: log_action pode não funcionar sem login, então vamos usar try/except
try:
    from app.logger import log_action
    LOGGING_AVAILABLE = True
except:
    LOGGING_AVAILABLE = False
    def log_action(*args, **kwargs):
        pass  # Silencioso se não disponível
import time
import logging
from datetime import datetime

logging.basicConfig(level=logging.ERROR)


def public_face_access_page():
    """Página pública de acesso por reconhecimento facial - SEM LOGIN"""
    
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
        <p style='font-size: 1.2em; color: #666;'>Sistema de Reconhecimento Facial</p>
    </div>
    """, unsafe_allow_html=True)
    
    if not is_face_recognition_available():
        from app.face_recognition_utils import (
            DEEPFACE_AVAILABLE, CV2_AVAILABLE, 
            NUMPY_AVAILABLE, PIL_AVAILABLE
        )
        
        missing = []
        if not NUMPY_AVAILABLE:
            missing.append("numpy")
        if not PIL_AVAILABLE:
            missing.append("Pillow")
        if not CV2_AVAILABLE:
            missing.append("opencv-python-headless")
        if not DEEPFACE_AVAILABLE:
            missing.append("deepface")
        
        error_msg = "⚠️ **Bibliotecas de reconhecimento facial não estão instaladas.**\n\n"
        if missing:
            error_msg += f"**Bibliotecas faltando:** {', '.join(missing)}\n\n"
        error_msg += "**Para instalar, execute:**\n\n"
        error_msg += "```bash\n"
        error_msg += "pip install deepface opencv-python-headless tensorflow numpy Pillow\n"
        error_msg += "```\n\n"
        error_msg += "**Ou instale todas as dependências:**\n\n"
        error_msg += "```bash\n"
        error_msg += "pip install -r requirements.txt\n"
        error_msg += "```"
        
        st.error(error_msg)
        return
    
    # Usa cliente público com permissões limitadas (RLS)
    db_ops = SupabasePublicClient()
    
    # Instruções
    with st.container():
        st.markdown("""
        <div style='text-align: center; padding: 20px; background-color: #f0f2f6; border-radius: 10px; margin: 20px 0;'>
            <h3>📸 Como usar:</h3>
            <p>1. Clique no botão abaixo para tirar uma foto</p>
            <p>2. O sistema reconhecerá você automaticamente</p>
            <p>3. Você será liberado ou bloqueado conforme seu cadastro</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Captura de foto via câmera
    st.markdown("---")
    st.markdown("### 📷 Captura de Foto")
    
    # Botão para resetar processamento (se já foi processado)
    if st.session_state.get('access_processed', False):
        st.success("✅ **Acesso registrado com sucesso!**")
        if st.button("🔄 Tirar Nova Foto", type="primary", use_container_width=True):
            st.session_state['access_processed'] = False
            st.session_state.last_processed_image = None
            st.rerun()
    else:
        # Instruções visuais (apenas se não foi processado)
        st.info("""
        👆 **Posicione seu rosto bem iluminado e centralizado na câmera abaixo.**
        
        O sistema processará automaticamente quando você tirar a foto.
        """)
    
    # Usa camera_input do Streamlit para captura direta
    picture = st.camera_input(
        "📸 Tire uma foto para reconhecimento",
        key="face_camera",
        help="Posicione seu rosto bem iluminado e centralizado na câmera. O sistema processará automaticamente.",
        disabled=st.session_state.get('access_processed', False)
    )
    
    # Processa automaticamente quando a foto for capturada
    if picture:
        # Verifica se já processou esta foto (evita reprocessamento)
        # Também verifica se já foi processado com sucesso para evitar loop
        picture_bytes = picture.getvalue()
        if ('last_processed_image' not in st.session_state or st.session_state.last_processed_image != picture_bytes) and not st.session_state.get('access_processed', False):
            # Marca que esta foto foi processada
            st.session_state.last_processed_image = picture.getvalue()
            
            # Mostra a foto capturada
            st.image(picture, caption="Foto capturada - Processando...", width=400)
            # Processa automaticamente
            with st.spinner("🔄 Processando reconhecimento facial..."):
                # Busca pessoa correspondente
                result = find_matching_person(picture, db_ops, threshold=0.4)
                
                if result:
                    person, distance = result
                    person_name = person.get('name', 'N/A')
                    person_cpf = person.get('cpf', '')
                    person_company = person.get('company', '')
                    person_id = person.get('id')
                    
                    # Verifica se está bloqueado usando cliente público
                    is_blocked, block_reason = db_ops.check_blocked(person_name, person_company)
                    
                    if is_blocked:
                        # PESSOA BLOQUEADA
                        st.error("""
                        <div style='text-align: center; padding: 30px; background-color: #fee; border: 3px solid #f44; border-radius: 10px;'>
                            <h1 style='color: #c00; font-size: 3em;'>🚫</h1>
                            <h2 style='color: #c00;'>ACESSO NEGADO</h2>
                            <p style='font-size: 1.2em;'><strong>{}</strong></p>
                            <p style='font-size: 1.1em; color: #666;'>Motivo: {}</p>
                        </div>
                        """.format(person_name, block_reason), unsafe_allow_html=True)
                        
                        if LOGGING_AVAILABLE:
                            try:
                                log_action(
                                    "FACE_ACCESS_DENIED",
                                    f"Acesso negado via reconhecimento facial para '{person_name}' (ID: {person_id}). Motivo: {block_reason}"
                                )
                            except:
                                pass
                        
                        # Registra tentativa de acesso bloqueado (sem autenticação)
                        now = get_sao_paulo_time()
                        record_data = {
                            'name': person_name,
                            'cpf': person_cpf if person_cpf else None,
                            'placa': None,
                            'marca_carro': None,
                            'horario_entrada': now.strftime("%H:%M"),
                            'data': now.strftime("%d/%m/%Y"),  # Será convertido para ISO
                            'empresa': person_company if person_company else None,
                            'status_entrada': 'Bloqueado',
                            'motivo_bloqueio': f"Tentativa de acesso negada: {block_reason}",
                            'aprovador': 'Sistema Automático',
                            'data_primeiro_registro': None,
                            'person_id': person_id
                        }
                        try:
                            record_id = db_ops.add_access_record(record_data)
                            if record_id:
                                logging.info(f"Registro de acesso bloqueado criado: {record_id}")
                        except Exception as e:
                            logging.error(f"Erro ao registrar acesso bloqueado: {e}")
                            st.error(f"Erro ao registrar tentativa de acesso: {e}")
                        
                        st.info("💡 Se você acredita que isso é um erro, entre em contato com a administração.")
                        
                        # Limpa a foto processada para permitir nova tentativa
                        st.session_state.last_processed_image = None
                        st.session_state['access_processed'] = False
                    
                    else:
                        # PESSOA LIBERADA
                        st.success("""
                        <div style='text-align: center; padding: 30px; background-color: #efe; border: 3px solid #4f4; border-radius: 10px;'>
                            <h1 style='color: #0a0; font-size: 3em;'>✅</h1>
                            <h2 style='color: #0a0;'>ACESSO LIBERADO</h2>
                            <p style='font-size: 1.2em;'><strong>{}</strong></p>
                            <p style='font-size: 1.1em; color: #666;'>Bem-vindo(a)!</p>
                        </div>
                        """.format(person_name), unsafe_allow_html=True)
                        
                        # Registra entrada automaticamente
                        now = get_sao_paulo_time()
                        approver = "Sistema Automático (Reconhecimento Facial)"
                        
                        # Prepara dados para registro (público não pode ler registros anteriores)
                        placa = ''
                        marca_carro = ''
                        empresa = person_company or ''
                        
                        # Registra entrada usando cliente público (sem autenticação)
                        record_data = {
                            'name': person_name,
                            'cpf': person_cpf if person_cpf else None,
                            'placa': placa if placa else None,
                            'marca_carro': marca_carro if marca_carro else None,
                            'horario_entrada': now.strftime("%H:%M"),
                            'data': now.strftime("%d/%m/%Y"),  # Será convertido para ISO
                            'empresa': empresa if empresa else None,
                            'status_entrada': 'Autorizado',
                            'motivo_bloqueio': 'Acesso automático por reconhecimento facial',
                            'aprovador': approver,
                            'data_primeiro_registro': None,  # None ao invés de string vazia
                            'person_id': person_id
                        }
                        record_id = db_ops.add_access_record(record_data)
                        success = record_id is not None
                        
                        if success:
                            # Marca que o processamento foi concluído com sucesso
                            st.session_state['access_processed'] = True
                            st.session_state['processed_person_id'] = person_id
                            
                            # st.balloons()  # Comentado: animação de balões desabilitada
                            if LOGGING_AVAILABLE:
                                try:
                                    log_action(
                                        "FACE_ACCESS_GRANTED",
                                        f"Acesso concedido via reconhecimento facial para '{person_name}' (ID: {person_id}, Distância: {distance:.4f})"
                                    )
                                except:
                                    pass
                            
                            # Mostra informações do acesso
                            st.success(f"""
                            **✅ Entrada registrada com sucesso!**
                            
                            **Informações do Acesso:**
                            - **Nome:** {person_name}
                            - **Horário:** {now.strftime("%H:%M")}
                            - **Data:** {now.strftime("%d/%m/%Y")}
                            - **Empresa:** {empresa if empresa else 'Não informada'}
                            """)
                            
                            clear_access_cache()
                            
                            # Limpa a foto processada para permitir nova tentativa
                            st.session_state.last_processed_image = None
                            
                            st.info("🔄 Você pode tirar uma nova foto para outro acesso.")
                
                else:
                    # PESSOA NÃO RECONHECIDA
                    st.warning("""
                    <div style='text-align: center; padding: 30px; background-color: #ffe; border: 3px solid #fa4; border-radius: 10px;'>
                        <h1 style='color: #a60; font-size: 3em;'>⚠️</h1>
                        <h2 style='color: #a60;'>PESSOA NÃO RECONHECIDA</h2>
                        <p style='font-size: 1.1em;'>Você não está cadastrado no sistema.</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if LOGGING_AVAILABLE:
                        try:
                            log_action(
                                "FACE_ACCESS_UNKNOWN",
                                "Tentativa de acesso de pessoa não reconhecida via reconhecimento facial"
                            )
                        except:
                            pass
                    
                    st.info("""
                    **Opções:**
                    - Se você já está cadastrado, tente novamente com melhor iluminação
                    - Se é sua primeira vez, entre em contato com a portaria para cadastro
                    - Verifique se está olhando diretamente para a câmera
                    """)
                    
                    # Limpa a foto processada para permitir nova tentativa
                    st.session_state.last_processed_image = None
                    st.session_state['access_processed'] = False
    
    # Rodapé
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; padding: 20px; color: #666;'>
        <p>Sistema de Controle de Acesso BAERI</p>
        <p>Desenvolvido por Cristian Ferreira Carlos</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Dicas de uso (colapsável)
    with st.expander("💡 Dicas para melhor reconhecimento"):
        st.markdown("""
        - **Iluminação:** Use boa iluminação, evite sombras no rosto
        - **Posição:** Foto frontal, com o rosto centralizado na câmera
        - **Distância:** Mantenha uma distância adequada (não muito perto nem muito longe)
        - **Expressão:** Rosto neutro, sem óculos escuros ou máscaras
        - **Estabilidade:** Mantenha a câmera estável ao tirar a foto
        - **Único rosto:** Apenas uma pessoa na foto
        
        **Nota:** O sistema usa tecnologia de reconhecimento facial avançada. 
        Certifique-se de que sua foto cadastrada seja similar à foto que você está tirando agora.
        """)

