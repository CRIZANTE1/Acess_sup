"""
Página de acesso rápido por reconhecimento facial
Permite que pessoas sejam reconhecidas automaticamente e tenham entrada registrada
"""
import streamlit as st
from app.supabase_db import SupabaseOperations
from app.face_recognition_utils import (
    is_face_recognition_available,
    find_matching_person,
    process_uploaded_image
)
from app.data_operations import add_record
from app.utils import get_sao_paulo_time
from app.logger import log_action
from auth.auth_utils import get_user_display_name
from app.utils import clear_access_cache
import time


def face_access_page():
    """Página principal de acesso por reconhecimento facial"""
    st.title("🔐 Acesso por Reconhecimento Facial")
    st.markdown("### Acesso Rápido e Automatizado")
    
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
    
    db_ops = SupabaseOperations()
    
    st.markdown("""
    ### Como Funciona
    
    1. 📸 **Tire uma foto** da pessoa usando a câmera abaixo
    2. 🤖 **O sistema reconhecerá** automaticamente se a pessoa está cadastrada
    3. ✅ **Se reconhecida**, a entrada será registrada automaticamente
    4. ❌ **Se não reconhecida**, você poderá registrar manualmente
    
    ---
    """)
    
    # Instruções visuais
    st.info("""
    👆 **Posicione a pessoa bem iluminada e centralizada na câmera abaixo.**
    
    O sistema processará automaticamente quando você tirar a foto.
    """)
    
    # Captura de foto via câmera
    st.markdown("### 📷 Captura de Foto")
    
    # Botão para resetar processamento (se já foi processado)
    if st.session_state.get('access_processed', False):
        st.success("✅ **Entrada registrada com sucesso!**")
        if st.button("🔄 Tirar Nova Foto", type="primary", use_container_width=True):
            st.session_state['access_processed'] = False
            st.session_state.last_processed_image_access = None
            st.rerun()
    else:
        # Instruções visuais (apenas se não foi processado)
        st.info("""
        👆 **Posicione a pessoa bem iluminada e centralizada na câmera abaixo.**
        
        O sistema processará automaticamente quando você tirar a foto.
        """)
    
    picture = st.camera_input(
        "📸 Tire uma foto para reconhecimento",
        key="face_camera_access",
        help="Posicione o rosto bem iluminado e centralizado na câmera. O sistema processará automaticamente.",
        disabled=st.session_state.get('access_processed', False)
    )
    
    # Processa automaticamente quando a foto for capturada
    if picture:
        # Verifica se já processou esta foto (evita reprocessamento)
        # Também verifica se já foi processado com sucesso para evitar loop
        picture_bytes = picture.getvalue()
        if ('last_processed_image_access' not in st.session_state or st.session_state.last_processed_image_access != picture_bytes) and not st.session_state.get('access_processed', False):
            # Marca que esta foto foi processada
            st.session_state.last_processed_image_access = picture_bytes
            
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
                        
                        st.success(f"✅ **Pessoa Reconhecida!**")
                        st.info(f"**Nome:** {person_name}")
                        if person_cpf:
                            st.info(f"**CPF:** {person_cpf}")
                        if person_company:
                            st.info(f"**Empresa:** {person_company}")
                        st.info(f"**Distância de similaridade:** {distance:.4f}")
                        
                        # Registra entrada automaticamente
                        now = get_sao_paulo_time()
                        approver = get_user_display_name()
                        
                        # Busca último registro para pegar dados como placa, etc
                        access_records = db_ops.load_access_records()
                        last_record = None
                        if access_records:
                            # Filtra registros da mesma pessoa
                            person_records = [r for r in access_records if r.get('person_id') == person_id or r.get('name', '').lower() == person_name.lower()]
                            if person_records:
                                # Pega o mais recente
                                person_records.sort(key=lambda x: x.get('created_at', ''), reverse=True)
                                last_record = person_records[0]
                        
                        # Prepara dados para registro
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
                            motivo="Acesso por reconhecimento facial",
                            aprovador=approver,
                            first_reg_date="",
                            person_id=person_id
                        )
                        
                        if success:
                            # Marca que o processamento foi concluído com sucesso
                            st.session_state['access_processed'] = True
                            st.session_state['processed_person_id'] = person_id
                            
                            # st.balloons()  # Comentado: animação de balões desabilitada
                            st.success(f"🎉 **Entrada registrada com sucesso para {person_name}!**")
                            log_action(
                                "FACE_ACCESS_GRANTED",
                                f"Acesso concedido via reconhecimento facial para '{person_name}' (ID: {person_id}, Distância: {distance:.4f})"
                            )
                            
                            # Limpa cache
                            clear_access_cache()
                            
                            # Limpa a foto processada para permitir nova tentativa
                            st.session_state.last_processed_image_access = None
                        else:
                            st.error("❌ Erro ao registrar entrada. Tente novamente.")
                            st.session_state['access_processed'] = False
                else:
                    st.warning("⚠️ **Pessoa não reconhecida**")
                    st.info("""
                    A pessoa pode não estar cadastrada no sistema ou a foto pode ser muito diferente.
                    
                    **Opções:**
                    - Verifique se a pessoa está cadastrada na página "Cadastro de Pessoas"
                    - Use a página "Controle de Acesso" para registro manual
                    - Tente com outra foto (melhor iluminação, mais frontal)
                    """)
                    
                    # Opção de cadastro rápido
                    st.divider()
                    st.markdown("### Cadastrar Pessoa Agora")
                    
                    with st.form("quick_register_form"):
                        col_a, col_b = st.columns(2)
                        
                        with col_a:
                            new_name = st.text_input("Nome Completo *", key="quick_name")
                            new_cpf = st.text_input("CPF", key="quick_cpf", placeholder="000.000.000-00")
                            new_company = st.text_input("Empresa", key="quick_company")
                        
                        with col_b:
                            st.write("**Foto já capturada acima**")
                            st.caption("A mesma foto será usada para cadastro")
                        
                        if st.form_submit_button("📝 Cadastrar e Registrar Entrada", type="primary"):
                                if not new_name or not new_name.strip():
                                    st.error("❌ O nome é obrigatório.")
                                else:
                                    # Processa a foto novamente para cadastro
                                    result = process_uploaded_image(picture)
                                    
                                    if result:
                                        from app.face_recognition_utils import encoding_to_json
                                        from app.utils import format_cpf, validate_cpf
                                        
                                        encoding, _ = result
                                        encoding_json = encoding_to_json(encoding)
                                        
                                        formatted_cpf = format_cpf(new_cpf) if new_cpf and validate_cpf(new_cpf) else None
                                        
                                        # Cria pessoa
                                        new_person_id = db_ops.create_person(
                                            name=new_name.strip(),
                                            cpf=formatted_cpf,
                                            company=new_company.strip() if new_company else None,
                                            face_encoding=encoding_json,
                                            face_photo_url=None
                                        )
                                        
                                        if new_person_id:
                                            # Faz upload da foto
                                            picture.seek(0)
                                            image_bytes = picture.read()
                                            file_extension = 'jpg'  # Câmera sempre retorna JPEG
                                            
                                            photo_url = db_ops.upload_face_photo(new_person_id, image_bytes, file_extension)
                                            if photo_url:
                                                db_ops.update_person(new_person_id, face_photo_url=photo_url)
                                            
                                            # Registra entrada
                                            now = get_sao_paulo_time()
                                            success = add_record(
                                                name=new_name.strip(),
                                                cpf=formatted_cpf,
                                                placa="",
                                                marca_carro="",
                                                horario_entrada=now.strftime("%H:%M"),
                                                data=now.strftime("%d/%m/%Y"),
                                                empresa=new_company.strip() if new_company else "",
                                                status="Autorizado",
                                                motivo="Acesso por reconhecimento facial (novo cadastro)",
                                                aprovador=approver,
                                                first_reg_date=now.strftime("%d/%m/%Y"),
                                                person_id=new_person_id
                                            )
                                            
                                            if success:
                                                # Marca que o processamento foi concluído com sucesso
                                                st.session_state['access_processed'] = True
                                                st.session_state['processed_person_id'] = new_person_id
                                                
                                                # st.balloons()  # Comentado: animação de balões desabilitada
                                                st.success(f"🎉 **Pessoa cadastrada e entrada registrada com sucesso!**")
                                                log_action(
                                                    "FACE_ACCESS_NEW_PERSON",
                                                    f"Nova pessoa '{new_name.strip()}' cadastrada e entrada registrada via reconhecimento facial"
                                                )
                                                clear_access_cache()
                                                
                                                # Limpa a foto processada para permitir nova tentativa
                                                st.session_state.last_processed_image_access = None
                                            else:
                                                st.error("Pessoa cadastrada, mas erro ao registrar entrada.")
                                        else:
                                            st.error("Erro ao cadastrar pessoa.")
                                    else:
                                        st.error("Erro ao processar foto para cadastro.")
    
    st.divider()
    
    # Estatísticas rápidas
    st.markdown("### 📊 Estatísticas")
    
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
                    # Tenta converter data para comparar
                    try:
                        from datetime import datetime
                        if isinstance(record_date, str):
                            # Formato brasileiro
                            if '/' in record_date:
                                record_date_obj = datetime.strptime(record_date, "%d/%m/%Y").date()
                            else:
                                # Formato ISO
                                record_date_obj = datetime.fromisoformat(record_date.split('T')[0]).date()
                        else:
                            record_date_obj = record_date
                        
                        if record_date_obj == today:
                            today_records.append(r)
                    except:
                        # Fallback: compara como string
                        if str(record_date) == today_str:
                            today_records.append(r)
        except:
            today_records = []
        st.metric("Acessos Hoje", len(today_records))
    
    # Dicas
    with st.expander("💡 Dicas para Melhor Reconhecimento"):
        st.markdown("""
        - **Iluminação:** Use boa iluminação, evite sombras no rosto
        - **Posição:** Foto frontal, com o rosto centralizado
        - **Qualidade:** Foto nítida, sem borrões
        - **Expressão:** Rosto neutro, sem óculos escuros ou máscaras
        - **Distância:** Rosto ocupando boa parte da foto (não muito longe)
        - **Único rosto:** Apenas uma pessoa na foto
        
        **Nota:** O sistema usa Google FaceNet, que é muito preciso, mas precisa de fotos de qualidade similar às cadastradas.
        """)

