"""
Página PÚBLICA de acesso por reconhecimento facial
Acesso sem login - pessoa tira foto e é liberada ou bloqueada automaticamente
"""
import streamlit as st
from app.supabase_db import SupabaseOperations
from app.face_recognition_utils import (
    is_face_recognition_available,
    find_matching_person,
    process_uploaded_image
)
from app.data_operations import add_record, is_entity_blocked
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
from datetime import datetime


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
        st.error("""
        ⚠️ **Sistema temporariamente indisponível.**
        
        Entre em contato com o administrador.
        """)
        return
    
    db_ops = SupabaseOperations()
    
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
    
    # Usa camera_input do Streamlit para captura direta
    picture = st.camera_input(
        "Tire uma foto para reconhecimento",
        key="face_camera",
        help="Posicione seu rosto bem iluminado e centralizado na câmera"
    )
    
    if picture:
        # Mostra a foto capturada
        st.image(picture, caption="Foto capturada", width=400)
        
        # Botão para processar
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            process_button = st.button(
                "🔍 VERIFICAR ACESSO",
                type="primary",
                use_container_width=True,
                key="process_face"
            )
        
        if process_button:
            with st.spinner("🔄 Processando reconhecimento facial..."):
                # Busca pessoa correspondente
                result = find_matching_person(picture, db_ops, threshold=0.4)
                
                if result:
                    person, distance = result
                    person_name = person.get('name', 'N/A')
                    person_cpf = person.get('cpf', '')
                    person_company = person.get('company', '')
                    person_id = person.get('id')
                    
                    # Verifica se está bloqueado
                    is_blocked, block_reason = is_entity_blocked(person_name, person_company)
                    
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
                        
                        # Registra tentativa de acesso bloqueado (modo silencioso)
                        now = get_sao_paulo_time()
                        st.session_state._silent_mode = True
                        try:
                            add_record(
                                name=person_name,
                                cpf=person_cpf,
                                placa="",
                                marca_carro="",
                                horario_entrada=now.strftime("%H:%M"),
                                data=now.strftime("%d/%m/%Y"),
                                empresa=person_company,
                                status="Bloqueado",
                                motivo=f"Tentativa de acesso negada: {block_reason}",
                                aprovador="Sistema Automático",
                                first_reg_date="",
                                person_id=person_id
                            )
                        finally:
                            if '_silent_mode' in st.session_state:
                                del st.session_state._silent_mode
                        
                        st.info("💡 Se você acredita que isso é um erro, entre em contato com a administração.")
                    
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
                        
                        # Busca último registro para pegar dados como placa, etc
                        access_records = db_ops.load_access_records()
                        last_record = None
                        if access_records:
                            # Filtra registros da mesma pessoa
                            person_records = [r for r in access_records 
                                            if r.get('person_id') == person_id or 
                                            r.get('name', '').lower() == person_name.lower()]
                            if person_records:
                                # Pega o mais recente
                                person_records.sort(key=lambda x: x.get('created_at', ''), reverse=True)
                                last_record = person_records[0]
                        
                        # Prepara dados para registro
                        placa = last_record.get('placa', '') if last_record else ''
                        marca_carro = last_record.get('marca_carro', '') if last_record else ''
                        empresa = person_company if person_company else (last_record.get('empresa', '') if last_record else '')
                        
                        # Registra entrada (modo silencioso para não mostrar mensagens duplicadas)
                        st.session_state._silent_mode = True
                        try:
                            success = add_record(
                                name=person_name,
                                cpf=person_cpf,
                                placa=placa,
                                marca_carro=marca_carro,
                                horario_entrada=now.strftime("%H:%M"),
                                data=now.strftime("%d/%m/%Y"),
                                empresa=empresa,
                                status="Autorizado",
                                motivo="Acesso automático por reconhecimento facial",
                                aprovador=approver,
                                first_reg_date="",
                                person_id=person_id
                            )
                        finally:
                            if '_silent_mode' in st.session_state:
                                del st.session_state._silent_mode
                        
                        if success:
                            st.balloons()
                            if LOGGING_AVAILABLE:
                                try:
                                    log_action(
                                        "FACE_ACCESS_GRANTED",
                                        f"Acesso concedido via reconhecimento facial para '{person_name}' (ID: {person_id}, Distância: {distance:.4f})"
                                    )
                                except:
                                    pass
                            
                            # Mostra informações do acesso
                            st.info(f"""
                            **Informações do Acesso:**
                            - **Horário:** {now.strftime("%H:%M")}
                            - **Data:** {now.strftime("%d/%m/%Y")}
                            - **Empresa:** {empresa if empresa else 'Não informada'}
                            """)
                            
                            clear_access_cache()
                            
                            # Aguarda antes de permitir nova tentativa
                            time.sleep(3)
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

