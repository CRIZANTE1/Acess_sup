"""
Módulo para gerenciamento de cadastro de pessoas com reconhecimento facial
"""
import streamlit as st
from app.supabase_db import SupabaseOperations
from app.face_recognition_utils import (
    process_uploaded_image,
    encoding_to_json,
    validate_face_image,
    is_face_recognition_available,
    find_matching_person
)
import io
from app.utils import validate_cpf, format_cpf
from app.logger import log_action
from auth.auth_utils import get_user_display_name


def person_registration_page():
    """Página para cadastro de pessoas com foto para reconhecimento facial"""
    st.title("📸 Cadastro de Pessoas com Reconhecimento Facial")
    
    if not is_face_recognition_available():
        st.error("""
        ⚠️ **Bibliotecas de reconhecimento facial não estão instaladas.**
        
        Para instalar, execute:
        ```bash
        pip install deepface opencv-python tensorflow
        ```
        """)
        return
    
    db_ops = SupabaseOperations()
    
    tab1, tab2 = st.tabs(["➕ Novo Cadastro", "🔍 Buscar Pessoa"])
    
    with tab1:
        st.subheader("Cadastrar Nova Pessoa")
        
        with st.form("person_registration_form"):
            col1, col2 = st.columns([1, 1])
            
            with col1:
                name = st.text_input("Nome Completo *", placeholder="João Silva")
                cpf = st.text_input("CPF", placeholder="000.000.000-00", help="Opcional, mas recomendado")
                company = st.text_input("Empresa", placeholder="Nome da Empresa")
            
            with col2:
                st.markdown("### Foto para Reconhecimento Facial")
                uploaded_file = st.file_uploader(
                    "Envie uma foto do rosto *",
                    type=['jpg', 'jpeg', 'png'],
                    help="Foto deve conter apenas um rosto, bem iluminado e frontal"
                )
                
                if uploaded_file:
                    from PIL import Image
                    image = Image.open(uploaded_file)
                    st.image(image, caption="Foto enviada", width=200)
            
            st.markdown("**Campos obrigatórios:** Nome e Foto")
            
            submitted = st.form_submit_button("Cadastrar Pessoa", type="primary")
            
            if submitted:
                # Validações
                if not name or not name.strip():
                    st.error("❌ O nome é obrigatório.")
                elif not uploaded_file:
                    st.error("❌ A foto é obrigatória.")
                elif cpf and not validate_cpf(cpf):
                    st.error("❌ CPF inválido.")
                else:
                    # Processa a imagem
                    result = process_uploaded_image(uploaded_file)
                    
                    if result is None:
                        st.error("❌ Não foi possível processar a foto. Verifique se há um rosto visível na imagem.")
                    else:
                        encoding, image = result
                        
                        # Converte encoding para JSON
                        encoding_json = encoding_to_json(encoding)
                        
                        # Formata CPF se fornecido
                        formatted_cpf = format_cpf(cpf) if cpf and cpf.strip() else None
                        
                        # Cria pessoa no banco primeiro (para obter o ID)
                        person_id = db_ops.create_person(
                            name=name.strip(),
                            cpf=formatted_cpf,
                            company=company.strip() if company else None,
                            face_encoding=encoding_json,
                            face_photo_url=None  # Será atualizado após upload
                        )
                        
                        if person_id:
                            # Faz upload da foto para o storage
                            uploaded_file.seek(0)  # Volta ao início do arquivo
                            image_bytes = uploaded_file.read()
                            
                            # Determina extensão do arquivo
                            file_extension = uploaded_file.name.split('.')[-1].lower() if '.' in uploaded_file.name else 'jpg'
                            if file_extension not in ['jpg', 'jpeg', 'png']:
                                file_extension = 'jpg'
                            
                            # Faz upload para o storage
                            photo_url = db_ops.upload_face_photo(person_id, image_bytes, file_extension)
                            
                            if photo_url:
                                # Atualiza a pessoa com a URL da foto
                                db_ops.update_person(person_id, face_photo_url=photo_url)
                                st.success(f"✅ Pessoa '{name.strip()}' cadastrada com sucesso!")
                                log_action("PERSON_REGISTERED", f"Cadastrou pessoa '{name.strip()}' com reconhecimento facial (ID: {person_id})")
                                
                                # Limpa o formulário
                                st.rerun()
                            else:
                                st.warning(f"⚠️ Pessoa cadastrada, mas houve erro ao fazer upload da foto. ID: {person_id}")
                                log_action("PERSON_REGISTERED_NO_PHOTO", f"Cadastrou pessoa '{name.strip()}' mas falhou upload da foto (ID: {person_id})")
                                st.rerun()
                        else:
                            st.error("❌ Erro ao cadastrar pessoa no banco de dados.")
    
    with tab2:
        st.subheader("Buscar Pessoa por Foto")
        
        uploaded_file_search = st.file_uploader(
            "Envie uma foto para buscar a pessoa",
            type=['jpg', 'jpeg', 'png'],
            key="search_photo"
        )
        
        if uploaded_file_search:
            from PIL import Image
            image = Image.open(uploaded_file_search)
            st.image(image, caption="Foto para busca", width=300)
            
            if st.button("🔍 Buscar Pessoa", type="primary"):
                with st.spinner("Processando imagem e buscando no banco de dados..."):
                    result = find_matching_person(uploaded_file_search, db_ops)
                    
                    if result:
                        person, distance = result
                        st.success("✅ Pessoa encontrada!")
                        
                        col1, col2 = st.columns([1, 1])
                        
                        with col1:
                            st.markdown("### Dados da Pessoa")
                            st.write(f"**Nome:** {person.get('name', 'N/A')}")
                            st.write(f"**CPF:** {person.get('cpf', 'N/A')}")
                            st.write(f"**Empresa:** {person.get('company', 'N/A')}")
                            st.write(f"**ID:** {person.get('id', 'N/A')}")
                            st.write(f"**Cadastrado em:** {person.get('created_at', 'N/A')}")
                            st.write(f"**Distância de similaridade:** {distance:.4f}")
                        
                        with col2:
                            if person.get('face_photo_url'):
                                try:
                                    # A URL já é uma URL pública do storage
                                    st.image(person['face_photo_url'], caption="Foto cadastrada", width=200)
                                except:
                                    st.info("Foto não disponível")
                    else:
                        st.warning("⚠️ Nenhuma pessoa correspondente encontrada no banco de dados.")
                        st.info("💡 Dica: A pessoa pode não estar cadastrada ou a foto pode ser muito diferente da cadastrada.")
        
        st.divider()
        st.subheader("Lista de Pessoas Cadastradas")
        
        # Lista todas as pessoas
        all_people = db_ops.client.table('people').select('*').order('created_at', desc=True).limit(50).execute()
        
        if all_people.data:
            import pandas as pd
            df = pd.DataFrame(all_people.data)
            
            # Filtra colunas relevantes
            display_cols = ['name', 'cpf', 'company', 'created_at', 'is_active']
            available_cols = [col for col in display_cols if col in df.columns]
            
            df_display = df[available_cols].copy()
            df_display = df_display.rename(columns={
                'name': 'Nome',
                'cpf': 'CPF',
                'company': 'Empresa',
                'created_at': 'Cadastrado em',
                'is_active': 'Ativo'
            })
            
            # Formata data
            if 'Cadastrado em' in df_display.columns:
                df_display['Cadastrado em'] = pd.to_datetime(df_display['Cadastrado em'], errors='coerce').dt.strftime('%d/%m/%Y %H:%M')
            
            st.dataframe(df_display, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma pessoa cadastrada ainda.")


def quick_face_verification(uploaded_file, db_ops, threshold: float = 0.4) -> tuple[bool, Optional[dict], str]:
    """
    Verificação rápida de rosto no momento do acesso.
    
    Returns:
        (is_verified, person_data, message)
    """
    if not is_face_recognition_available():
        return False, None, "Bibliotecas de reconhecimento facial não disponíveis."
    
    result = find_matching_person(uploaded_file, db_ops, threshold=threshold)
    
    if result:
        person, distance = result
        return True, person, f"Rosto verificado: {person.get('name', 'N/A')} (distância: {distance:.4f})"
    else:
        return False, None, "Rosto não reconhecido. A pessoa pode não estar cadastrada."

