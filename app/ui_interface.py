import streamlit as st
import pandas as pd
from datetime import datetime
from app.data_operations import (
    add_record, 
    update_exit_time, 
    delete_record_by_id, 
    check_blocked_records,
    is_entity_blocked,
    check_briefing_needed,
    update_schedule_status,
    load_data_from_supabase
)
# Importação segura de face_recognition_utils
try:
    from app.face_recognition_utils import (
        is_face_recognition_available,
        quick_face_verification
    )
except (ImportError, Exception) as e:
    # Se falhar, cria funções stub
    def is_face_recognition_available():
        return False
    
    def quick_face_verification(*args, **kwargs):
        return False, None, "Reconhecimento facial não disponível"
from app.supabase_db import SupabaseOperations
from app.utils import (
    format_cpf, 
    validate_cpf, 
    get_sao_paulo_time, 
    clear_access_cache, 
    validate_placa, 
    format_placa, 
    get_placa_tipo
)
from app.security import SecurityValidator, RateLimiter, SessionSecurity, show_security_alert
from app.widgets import aprovador_selector_with_confirmation
from auth.auth_utils import get_user_display_name, is_admin
from app.logger import log_action


def cleanup_all_exit_states():
    """Limpa todos os estados de saída para evitar loops."""
    keys_to_check = list(st.session_state.keys())
    for key in keys_to_check:
        if key.startswith('exit_') or key.startswith('material_') or key.startswith('mat_'):
            del st.session_state[key]
    
    # Reseta flag de processamento
    if 'processing' in st.session_state:
        st.session_state.processing = False


@st.dialog("Solicitar Liberação Excepcional")
def request_blocklist_override_dialog(name, company):
    """Um diálogo para solicitar a liberação de alguém na blocklist."""
    st.write(f"Você está solicitando uma liberação excepcional para **{name}** da empresa **{company}**.")
    st.warning("Esta pessoa/empresa está na lista de bloqueio permanente. A solicitação requer um motivo legítimo e será registrada para auditoria.")
    reason = st.text_area("**Motivo da Solicitação Excepcional (obrigatório):**", height=150)
    
    if st.button("Enviar Solicitação para Admin", type="primary"):
        if reason.strip():
            now = get_sao_paulo_time()
            requester_name = get_user_display_name()
            if add_record(
                name=name, cpf="", placa="", marca_carro="", 
                horario_entrada=now.strftime("%H:%M"), 
                data=now.strftime("%d/%m/%Y"), 
                empresa=company, 
                status="Pendente de Liberação da Blocklist", 
                motivo=f"EXCEPCIONAL: {reason.strip()}", 
                aprovador=requester_name, 
                first_reg_date=""
            ):
                log_action("REQUEST_BLOCKLIST_OVERRIDE", f"Solicitou liberação da blocklist para '{name}'. Motivo: {reason.strip()}")
                
                # NOVO: Notifica administradores sobre a solicitação urgente
                try:
                    from app.notifications import send_notification
                    import logging
                    send_notification(
                        "blocklist_override",
                        person_name=name,
                        company=company,
                        reason=reason.strip(),
                        requester=requester_name
                    )
                except Exception as e:
                    logging.error(f"Erro ao enviar notificação de desbloqueio: {e}")
                
                st.success("Sua solicitação excepcional foi enviada para o administrador.")
                clear_access_cache()
                st.rerun()
        else:
            st.error("O motivo é obrigatório para enviar a solicitação.")


def show_scheduled_today(db_ops):
    """
    Mostra uma lista de visitantes agendados APENAS PARA HOJE e que ainda
    não tiveram check-in. Agendamentos passados não aparecem.
    """
    st.header("Visitantes Agendados para Hoje")
    
    schedules_data = db_ops.load_schedules()
    if not schedules_data:
        st.info("Nenhum visitante agendado para hoje.")
        return

    df_schedules = pd.DataFrame(schedules_data)
    # Renomeia colunas para compatibilidade
    column_mapping = {
        'id': 'ID',
        'visitor_name': 'VisitorName',
        'visitor_cpf': 'VisitorCPF',
        'company': 'Company',
        'scheduled_date': 'ScheduledDate',
        'scheduled_time': 'ScheduledTime',
        'authorized_by': 'AuthorizedBy',
        'status': 'Status'
    }
    df_schedules = df_schedules.rename(columns=column_mapping)
    
    # Converte data para formato brasileiro
    if 'ScheduledDate' in df_schedules.columns:
        df_schedules['ScheduledDate'] = pd.to_datetime(df_schedules['ScheduledDate'], errors='coerce').dt.strftime('%d/%m/%Y')
    
    if 'ScheduledDate' not in df_schedules.columns or 'Status' not in df_schedules.columns:
        st.warning("A planilha 'schedules' não contém as colunas 'ScheduledDate' ou 'Status'.")
        return

    today_str = get_sao_paulo_time().strftime("%d/%m/%Y")
    
    today_schedules = df_schedules[
        (df_schedules['ScheduledDate'] == today_str) &
        (df_schedules['Status'] == 'Agendado')
    ].sort_values(by='ScheduledTime')

    if today_schedules.empty:
        st.info("Nenhum visitante pendente de chegada para hoje.")
        return

    st.write("Aguardando chegada:")
    for _, schedule in today_schedules.iterrows():
        schedule_id = schedule['ID']
        visitor_name = schedule['VisitorName']
        company = schedule['Company']
        time = schedule['ScheduledTime']
        
        with st.container(border=True):
            col1, col2, col3 = st.columns([2, 2, 2])
            with col1:
                st.write(f"**{visitor_name}**")
                st.caption(f"Empresa: {company}")
            with col2:
                st.write(f"Horário: **{time}**")
                st.caption(f"Autorizado por: {schedule['AuthorizedBy']}")
            with col3:
                if st.button("Registrar Chegada", key=f"checkin_{schedule_id}", use_container_width=True, type="primary"):
                    now = get_sao_paulo_time()
                    if add_record(
                        name=visitor_name,
                        cpf=schedule['VisitorCPF'],
                        placa="",
                        marca_carro="",
                        horario_entrada=now.strftime("%H:%M"),
                        data=now.strftime("%d/%m/%Y"),
                        empresa=company,
                        status="Autorizado",
                        motivo="Visita Agendada",
                        aprovador=schedule['AuthorizedBy'],
                        first_reg_date="" 
                    ):
                        if update_schedule_status(schedule_id, "Realizado", now.strftime("%H:%M")):
                            st.success(f"Chegada de {visitor_name} registrada com sucesso!")
                            log_action("CHECK_IN", f"Check-in realizado para a visita agendada de '{visitor_name}'.")
                            clear_access_cache()
                            st.rerun()
                            
def get_person_status(name, df):
    """Verifica o status mais recente, incluindo o novo status de liberação."""
    if not name or name == "--- Novo Cadastro ---": return "Novo", None
    if df.empty: return "Novo", None
    person_records = df[df["Nome"] == name].copy()
    if person_records.empty: return "Novo", None
    latest_record = person_records.iloc[0]
    status_entrada = latest_record.get("Status da Entrada", "")
    horario_saida = latest_record.get("Horário de Saída", "")
    if status_entrada in ["Bloqueado", "Pendente de Aprovação", "Pendente de Liberação da Blocklist"]:
        return "Bloqueado", latest_record
    if pd.isna(horario_saida) or str(horario_saida).strip() == "": return "Dentro", latest_record
    return "Fora", latest_record

def show_people_inside(df, db_ops):
    """Mostra uma lista de pessoas atualmente dentro com um botão de saída rápida."""
    st.subheader("Pessoas na Unidade")
    
    # Filtra pessoas com status Autorizado e sem horário de saída
    inside_df = df[
        (df["Status da Entrada"] == "Autorizado") & 
        ((df["Horário de Saída"] == "") | pd.isna(df["Horário de Saída"]))
    ].copy().sort_values("Nome")
    
    if inside_df.empty:
        st.info("Ninguém registrado na unidade no momento.")
        return
    
    for _, row in inside_df.iterrows():
        record_id = row.get('ID')
        person_name = row['Nome']
        
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1: 
            st.write(f"**{person_name}**")
        with col2: 
            st.caption(f"Entrada: {row['Data']} às {row['Horário de Entrada']}")
        with col3:
            # CORREÇÃO: Verifica se já está processando ANTES de mostrar o botão
            is_processing_this = st.session_state.get(f'exit_clicked_{record_id}', False)
            
            if st.button(
                "Sair", 
                key=f"exit_{record_id}", 
                use_container_width=True, 
                disabled=st.session_state.get('processing', False) or is_processing_this
            ):
                st.session_state[f'exit_clicked_{record_id}'] = True
                st.session_state[f'exit_person_name_{record_id}'] = person_name
                st.rerun()
        
        # CORREÇÃO: Só mostra o dialog se o botão foi clicado E ainda não foi processado
        if st.session_state.get(f'exit_clicked_{record_id}', False) and \
           not st.session_state.get(f'exit_processed_{record_id}', False):
            show_material_confirmation_dialog(record_id, person_name, row, db_ops)


@st.dialog("Saída de Material?")
def show_material_confirmation_dialog(record_id, person_name, row, db_ops):
    """Dialog que pergunta se a pessoa está levando material."""
    st.write(f"**{person_name}** está levando algum material?")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("✅ Sim, registrar material", type="primary", use_container_width=True, key=f"sim_{record_id}"):
            st.session_state[f'material_choice_{record_id}'] = 'sim'
            st.rerun()
    
    with col2:
        if st.button("❌ Não, apenas saída", use_container_width=True, key=f"nao_{record_id}"):
            st.session_state[f'material_choice_{record_id}'] = 'nao'
            st.rerun()
    
    # Processa a escolha
    material_choice = st.session_state.get(f'material_choice_{record_id}')
    
    if material_choice == 'sim':
        # Mostra formulário de material DENTRO do mesmo dialog
        st.divider()
        st.subheader("Dados do Material")
        
        lista_materiais_data = db_ops.load_materials()
        lista_materiais = [item['item'] for item in lista_materiais_data if item.get('item')] if lista_materiais_data else []
        
        if not lista_materiais:
            st.error("❌ Nenhum material cadastrado na aba 'materials'")
            if st.button("Fechar", key=f"close_{record_id}"):
                cleanup_exit_session_state(record_id)
                st.rerun()
            return
        
        material_item = st.selectbox(
            "Item:",
            options=[""] + lista_materiais,
            key=f"mat_item_{record_id}"
        )
        
        col_qtd, col_dest = st.columns(2)
        with col_qtd:
            material_qtd = st.number_input(
                "Quantidade:",
                min_value=1,
                value=1,
                key=f"mat_qtd_{record_id}"
            )
        
        with col_dest:
            material_destino = st.text_input(
                "Destino:",
                placeholder="Ex: Obra, Cliente, Matriz",
                key=f"mat_dest_{record_id}"
            )
        
        material_responsavel = st.text_input(
            "Responsável pela Saída:",
            value=person_name,
            key=f"mat_resp_{record_id}",
            help="Pessoa responsável por levar o material"
        )
        
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            if st.button("✅ Confirmar Saída com Material", type="primary", use_container_width=True, key=f"confirm_mat_{record_id}"):
                # Validações
                if not material_item or material_item == "":
                    st.error("❌ Selecione um item")
                    return
                if not material_destino or material_destino.strip() == "":
                    st.error("❌ Informe o destino do material")
                    return
                if not material_responsavel or material_responsavel.strip() == "":
                    st.error("❌ Informe o responsável pela saída")
                    return
                
                # Processa saída com material
                process_exit_with_material(
                    person_name, 
                    record_id,
                    sheet_operations,
                    material_item,
                    material_qtd,
                    material_destino.strip(),
                    material_responsavel.strip()
                )
        
        with col_btn2:
            if st.button("❌ Cancelar", use_container_width=True, key=f"cancel_mat_{record_id}"):
                cleanup_exit_session_state(record_id)
                st.rerun()
    
    elif material_choice == 'nao':
        # Processa saída sem material
        process_exit_without_material(person_name, record_id)


def cleanup_exit_session_state(record_id):
    """Limpa as variáveis de session_state relacionadas à saída."""
    keys_to_delete = [
        f'exit_clicked_{record_id}',
        f'exit_person_name_{record_id}',
        f'material_choice_{record_id}',
        f'exit_processed_{record_id}',  # NOVO: flag de processamento
        # Limpa também os campos do formulário de material
        f'mat_item_{record_id}',
        f'mat_qtd_{record_id}',
        f'mat_dest_{record_id}',
        f'mat_resp_{record_id}'
    ]
    for key in keys_to_delete:
        if key in st.session_state:
            del st.session_state[key]


def process_exit_with_material(person_name, record_id, sheet_ops, item, qtd, destino, responsavel):
    """Processa a saída de uma pessoa com material."""
    # CORREÇÃO: Marca como processado ANTES de iniciar
    st.session_state[f'exit_processed_{record_id}'] = True
    st.session_state.processing = True
    
    now = get_sao_paulo_time()
    
    success, message = update_exit_time(
        person_name, 
        now.strftime("%d/%m/%Y"), 
        now.strftime("%H:%M")
    )
    
    if success:
        log_action("REGISTER_EXIT", f"Registrou saída para '{person_name}'.")
        
        # Registra o material
        material_registro = [item, str(qtd), destino, responsavel]
        
        if sheet_ops.adc_dados_aba(material_registro, 'materials'):
            log_action(
                "SAIDA_MATERIAL",
                f"{responsavel} levou {qtd}x {item} para {destino}"
            )
            st.success(f"✅ Saída de {person_name} registrada!")
            st.info(f" Material: {qtd}x {item} → {destino}")
        else:
            st.warning("⚠️ Saída registrada, mas houve erro ao registrar o material")
        
        # CORREÇÃO: Limpa TUDO antes de rerun
        cleanup_exit_session_state(record_id)
        clear_access_cache()
        st.session_state.processing = False
        
        # AGUARDA um momento antes do rerun para garantir que o estado foi limpo
        import time
        time.sleep(0.1)
        st.rerun()
    else:
        st.error(f"❌ {message}")
        st.session_state.processing = False
        st.session_state[f'exit_processed_{record_id}'] = False


def process_exit_without_material(person_name, record_id):
    """Processa a saída de uma pessoa sem material."""
    # CORREÇÃO: Marca como processado ANTES de iniciar
    st.session_state[f'exit_processed_{record_id}'] = True
    st.session_state.processing = True
    
    now = get_sao_paulo_time()
    
    success, message = update_exit_time(
        person_name, 
        now.strftime("%d/%m/%Y"), 
        now.strftime("%H:%M")
    )
    
    if success:
        log_action("REGISTER_EXIT", f"Registrou saída para '{person_name}'.")
        st.success(f"✅ Saída de {person_name} registrada!")
        
        # CORREÇÃO: Limpa TUDO antes de rerun
        cleanup_exit_session_state(record_id)
        clear_access_cache()
        st.session_state.processing = False
        
        # AGUARDA um momento antes do rerun
        import time
        time.sleep(0.1)
        st.rerun()
    else:
        st.error(f"❌ {message}")
        st.session_state.processing = False
        st.session_state[f'exit_processed_{record_id}'] = False

def vehicle_access_interface():
    """Renderiza a interface principal de controle de acesso."""
    
    # LIMPA CACHE E FORÇA RELOAD DOS DADOS AO ENTRAR NA PÁGINA
    if 'last_page' not in st.session_state or st.session_state.last_page != 'controle_acesso':
        # Primeira vez entrando nesta página ou voltando de outra
        from app.utils import clear_access_cache
        
        # Limpa todos os caches
        clear_access_cache()
        if 'df_acesso_veiculos' in st.session_state:
            del st.session_state['df_acesso_veiculos']
        if 'access_records_cache' in st.session_state:
            del st.session_state['access_records_cache']
        if 'last_cache_update' in st.session_state:
            del st.session_state['last_cache_update']
        
        # Marca que está nesta página
        st.session_state.last_page = 'controle_acesso'
        
        # Recarrega dados do zero
        load_data_from_supabase()
    
    st.title("Controle de Acesso BAERI")
    
    # NOVO: Limpa estados órfãos ao carregar a página
    if st.session_state.get('force_cleanup', False):
        cleanup_all_exit_states()
        st.session_state.force_cleanup = False
    
    if 'processing' not in st.session_state:
        st.session_state.processing = False

    db_ops = SupabaseOperations()
    
    with st.expander("Briefing de Segurança e Lembretes", expanded=False):
        st.write("""
        **ATENÇÃO:**
        1. O acesso de veículos deve ser controlado rigorosamente para garantir a segurança do local.
        2. Apenas pessoas autorizadas podem liberar o acesso.
        3. Em caso de dúvidas, entre em contato com o responsável pela segurança.
        4. Mantenha sempre os dados atualizados e verifique as informações antes de liberar o acesso.
        5. **Sempre que for a primeira vez do visitante ou um ano desde o último acesso, repassar o vídeo abaixo.**
        """)
        try:
            st.video("https://youtu.be/QqUkeTucwkI")
        except Exception as e:
            st.error(f"Erro ao carregar o vídeo: {e}")
    
    if 'df_acesso_veiculos' not in st.session_state:
        load_data_from_supabase()
        df = st.session_state.df_acesso_veiculos
    else:
        df = st.session_state.df_acesso_veiculos
    if not df.empty:
        df['Data_dt'] = pd.to_datetime(df['Data'], format='%d/%m/%Y', errors='coerce')
        df = df.sort_values(by=['Data_dt', 'Horário de Entrada'], ascending=[False, False]).drop(columns=['Data_dt'])
    st.session_state.df_acesso_veiculos = df
    aprovadores_autorizados = db_ops.load_authorizers()
    blocked_info = check_blocked_records(df)
    if blocked_info:
        st.error("Atenção! Pessoas com restrição de acesso:\n\n" + blocked_info)

    col_main, col_sidebar = st.columns([2, 1])
    with col_main:
        st.header("Painel de Registro")
        
        unique_names = sorted(df["Nome"].unique()) if "Nome" in df.columns else []
        search_options = ["--- Novo Cadastro ---"] + unique_names
        selected_name = st.selectbox("Busque por um nome ou selecione 'Novo Cadastro':", options=search_options, index=0, key="person_selector")
        
        status, latest_record = get_person_status(selected_name, df)

        if status == "Bloqueado":
            status_atual = latest_record.get('Status da Entrada', 'Bloqueado')
            if status_atual == "Pendente de Liberação da Blocklist":
                 st.error(f"**{selected_name}** possui uma **SOLICITAÇÃO EXCEPCIONAL PENDENTE**.")
                 st.info("Aguarde um administrador analisar o pedido de alta prioridade.")
            elif status_atual == "Pendente de Aprovação":
                st.warning(f"**{selected_name}** já possui uma solicitação de acesso **PENDENTE DE APROVAÇÃO**.")
                st.info("Aguarde um administrador analisar o pedido.")
            else:
                motivo = latest_record.get('Motivo do Bloqueio', 'Não especificado')
                st.error(f"**{selected_name}** possui status **BLOQUEADO**.")
                st.write(f"**Motivo:** {motivo}")
                st.write("Para permitir a entrada, uma solicitação deve ser enviada para aprovação de um administrador.")
                if st.button(f"⚠️ Solicitar Liberação de Acesso para {selected_name}", use_container_width=True, type="primary", disabled=st.session_state.processing):
                    st.session_state.processing = True
                    now = get_sao_paulo_time()
                    requester_name = get_user_display_name()
                    if add_record(name=selected_name, cpf=str(latest_record.get("CPF", "")), placa="", marca_carro="", horario_entrada=now.strftime("%H:%M"), data=now.strftime("%d/%m/%Y"), empresa=str(latest_record.get("Empresa", "")), status="Pendente de Aprovação", motivo=f"Solicitação para bloqueio: '{motivo}'", aprovador=requester_name, first_reg_date=""):
                        log_action("REQUEST_ACCESS", f"Solicitou liberação para '{selected_name}'. Motivo: {motivo}")
                        st.success(f"Solicitação para {selected_name} enviada para o administrador!")
                        clear_access_cache()
                    st.session_state.processing = False
                    st.rerun()

        elif status == "Dentro":
            st.info(f"**{selected_name}** está **DENTRO** da unidade.")
            st.write(f"**Entrada em:** {latest_record['Data']} às {latest_record['Horário de Entrada']}")
            
            if st.button(
                f"✅ Registrar Saída de {selected_name}", 
                use_container_width=True, 
                type="primary", 
                disabled=st.session_state.processing,
                key="btn_saida_individual"
            ):
                st.session_state['exit_clicked_individual'] = True
                st.session_state['exit_person_name_individual'] = selected_name
                st.rerun()

            # Verifica se o botão foi clicado
            if st.session_state.get('exit_clicked_individual', False):
                show_material_confirmation_dialog_individual(selected_name, latest_record, db_ops)

        elif status == "Fora":
            st.success(f"**{selected_name}** está **FORA** da unidade.")
            st.write(f"**Última saída em:** {latest_record.get('Data', 'N/A')} às {latest_record.get('Horário de Saída', 'N/A')}")
            
            # Verifica se precisa repassar o briefing
            needs_briefing, briefing_reason = check_briefing_needed(selected_name, df)
            if needs_briefing:
                st.warning(f"⚠️ **ATENÇÃO: Repassar Briefing de Segurança!**")
                st.info(f"Motivo: {briefing_reason}")
            
            # Verificação facial opcional
            if is_face_recognition_available():
                with st.expander("🔍 Verificação Facial (Opcional)", expanded=False):
                    face_photo = st.file_uploader(
                        "Envie uma foto para verificar identidade",
                        type=['jpg', 'jpeg', 'png'],
                        key="face_verify_fora",
                        help="Opcional: Verifica se a foto corresponde à pessoa cadastrada"
                    )
                    
                    if face_photo:
                        from PIL import Image
                        verify_image = Image.open(face_photo)
                        st.image(verify_image, caption="Foto para verificação", width=200)
                        
                        if st.button("🔍 Verificar Rosto", key="btn_verify_fora"):
                            with st.spinner("Verificando rosto..."):
                                is_verified, person_data, message = quick_face_verification(face_photo, db_ops)
                                
                                if is_verified and person_data:
                                    if person_data.get('name', '').lower() == selected_name.lower():
                                        st.success(f"✅ {message}")
                                        log_action("FACE_VERIFIED", f"Rosto verificado para '{selected_name}' no momento do acesso")
                                    else:
                                        st.warning(f"⚠️ Rosto verificado, mas corresponde a outra pessoa: {person_data.get('name', 'N/A')}")
                                        log_action("FACE_MISMATCH", f"Rosto verificado não corresponde a '{selected_name}'")
                                else:
                                    st.warning(f"⚠️ {message}")
            
            with st.container(border=True):
                st.write("Registrar nova entrada:")
                placa = st.text_input("Placa (Opcional)", value=latest_record.get("Placa", ""), key="fora_placa", max_chars=8, help="Formatos aceitos: ABC-1234 ou ABC1D23")
                
                # Validação em tempo real da placa
                if placa and placa.strip():
                    tipo_placa = get_placa_tipo(placa)
                    if tipo_placa == "Inválida":
                        st.error("❌ Placa inválida! Use o formato ABC-1234 (antiga) ou ABC1D23 (Mercosul)")
                    else:
                        st.success(f"✅ Placa válida - Formato: {tipo_placa}")
                
                empresa = st.text_input("Empresa", value=latest_record.get("Empresa", ""), key="fora_empresa", max_chars=100)
                
                # Usa o widget de aprovador
                aprovador, aprovador_ciente = aprovador_selector_with_confirmation(
                    aprovadores_autorizados,
                    key_prefix="fora"
                )
                
                # Botão desabilitado se não tiver aprovador ou confirmação
                button_disabled = st.session_state.processing or not aprovador or aprovador == "" or not aprovador_ciente
                
                if st.button(
                    f"▶️ Registrar Entrada de {selected_name}", 
                    use_container_width=True, 
                    type="primary", 
                    disabled=button_disabled
                ):
                    # Verifica rate limit
                    user_id = get_user_display_name()
                    is_allowed, remaining, reset_time = RateLimiter.check_rate_limit(
                        user_id, 'register_entry', max_attempts=15, time_window=60
                    )
                    
                    if not is_allowed:
                        show_security_alert(
                            f"Muitas tentativas de registro. Aguarde {reset_time} segundos.",
                            "error"
                        )
                        st.stop()
                    
                    # Valida empresa
                    is_valid_empresa, result_empresa = SecurityValidator.validate_empresa(empresa)
                    if not is_valid_empresa:
                        show_security_alert(f"Empresa inválida: {result_empresa}", "error")
                        SessionSecurity.record_failed_attempt(user_id, f"Invalid empresa: {result_empresa}")
                    elif placa and not validate_placa(placa):
                        st.error("❌ Placa inválida! Corrija antes de continuar.")
                        st.info("Formatos aceitos: ABC-1234 (antiga) ou ABC1D23 (Mercosul)")
                    else:
                        # >>> ADICIONE ESTA VERIFICAÇÃO AQUI <
                        is_blocked, reason = is_entity_blocked(selected_name, result_empresa)
                        if is_blocked:
                            st.error(f"🚫 **ACESSO BLOQUEADO**")
                            st.warning(f"**Motivo do bloqueio:** {reason}")
                            st.info("Esta pessoa/empresa está na lista de bloqueios permanentes.")
                            log_action("BLOCKED_ACCESS_ATTEMPT", f"Tentativa de '{selected_name}' da empresa '{result_empresa}' interceptada. Motivo: {reason}")
                            SessionSecurity.record_failed_attempt(user_id, f"Blocked entity: {selected_name}")
                            
                            # Oferece opção de solicitar liberação excepcional
                            if st.button("⚠️ Solicitar Liberação Excepcional", key="req_override_fora", use_container_width=True):
                                request_blocklist_override_dialog(selected_name, result_empresa)
                            st.stop()  # Impede continuar o registro
                        # >>> FIM DA ADIÇÃO <
                        
                        # Resto do código continua normal...
                        st.session_state.processing = True
                        now = get_sao_paulo_time()
                        placa_formatada = format_placa(placa) if placa else ""
                        
                        if add_record(
                            name=selected_name, 
                            cpf=str(latest_record.get("CPF", "")),
                            placa=placa_formatada, 
                            marca_carro=str(latest_record.get("Marca do Carro", "")),
                            horario_entrada=now.strftime("%H:%M"), 
                            data=now.strftime("%d/%m/%Y"), 
                            empresa=result_empresa, 
                            status="Autorizado", 
                            motivo="", 
                            aprovador=aprovador, 
                            first_reg_date=""
                        ):
                            log_action("REGISTER_ENTRY", f"Registrou nova entrada para '{selected_name}'. Placa: {placa_formatada}. Aprovador: {aprovador} (confirmado ciente)")
                            st.success(f"✅ Nova entrada de {selected_name} registrada e autorizada por {aprovador}!")
                            clear_access_cache()
                        
                        st.session_state.processing = False
                        st.rerun()
        
        elif status == "Novo":
            st.info("Pessoa não encontrada. Preencha o formulário.")
            
            # Verificação facial opcional para novo cadastro
            if is_face_recognition_available():
                with st.expander("🔍 Verificação Facial (Opcional)", expanded=False):
                    st.info("💡 Se a pessoa já estiver cadastrada com foto, você pode verificar aqui antes de criar um novo registro.")
                    face_photo = st.file_uploader(
                        "Envie uma foto para verificar se a pessoa já está cadastrada",
                        type=['jpg', 'jpeg', 'png'],
                        key="face_verify_novo",
                        help="Opcional: Verifica se a pessoa já está no sistema"
                    )
                    
                    if face_photo:
                        from PIL import Image
                        verify_image = Image.open(face_photo)
                        st.image(verify_image, caption="Foto para verificação", width=200)
                        
                        if st.button("🔍 Verificar Rosto", key="btn_verify_novo"):
                            with st.spinner("Verificando rosto..."):
                                is_verified, person_data, message = quick_face_verification(face_photo, db_ops)
                                
                                if is_verified and person_data:
                                    st.success(f"✅ {message}")
                                    st.info(f"💡 A pessoa '{person_data.get('name', 'N/A')}' já está cadastrada. Considere usar esse cadastro ao invés de criar um novo.")
                                    log_action("FACE_FOUND_NEW_REG", f"Rosto encontrado para '{person_data.get('name', 'N/A')}' durante tentativa de novo cadastro")
                                else:
                                    st.warning(f"⚠️ {message}")
            
            # Verifica timeout de sessão
            is_expired, minutes = SessionSecurity.check_session_timeout(timeout_minutes=30)
            if is_expired:
                show_security_alert("Sessão expirou por inatividade. Por favor, recarregue a página.", "warning")
                st.stop()
            
            with st.container(border=True):
                st.write("**Formulário de Primeiro Acesso**")
                st.warning("⚠️ **ATENÇÃO: Esta é a primeira visita. Repassar Briefing de Segurança obrigatoriamente!**")
                
                name = st.text_input("Nome Completo:", key="novo_nome", max_chars=100)
                cpf = st.text_input("CPF:", key="novo_cpf", max_chars=14)
                empresa = st.text_input("Empresa:", key="novo_empresa", max_chars=100)
                
                # Usa o widget de aprovador
                aprovador, aprovador_ciente = aprovador_selector_with_confirmation(
                    aprovadores_autorizados,
                    key_prefix="novo"
                )
                
                st.divider() 
                
                placa = st.text_input("Placa (Opcional):", key="novo_placa", max_chars=8, help="Formatos aceitos: ABC-1234 ou ABC1D23")
                
                # Validação em tempo real da placa
                if placa and placa.strip():
                    tipo_placa = get_placa_tipo(placa)
                    if tipo_placa == "Inválida":
                        st.error("❌ Placa inválida! Use o formato ABC-1234 (antiga) ou ABC1D23 (Mercosul)")
                    else:
                        st.success(f"✅ Placa válida - Formato: {tipo_placa}")
                
                marca_carro = st.text_input("Marca (Opcional):", key="novo_marca", max_chars=50)

                # Botão desabilitado se não tiver aprovador ou confirmação
                button_disabled = st.session_state.processing or not aprovador or aprovador == "" or not aprovador_ciente
                
                if st.button(
                    "➕ Cadastrar e Registrar Entrada", 
                    use_container_width=True, 
                    type="primary", 
                    disabled=button_disabled
                ):
                    
                    # Verifica rate limit
                    user_id = get_user_display_name()
                    is_allowed, remaining, reset_time = RateLimiter.check_rate_limit(
                        user_id, 'create_record', max_attempts=10, time_window=60
                    )
                    
                    if not is_allowed:
                        show_security_alert(
                            f"Muitas tentativas de cadastro. Aguarde {reset_time} segundos antes de tentar novamente.",
                            "error"
                        )
                        SessionSecurity.record_failed_attempt(user_id, "Rate limit exceeded on create_record")
                        st.stop()
                    
                    # Validação completa de segurança
                    is_valid, clean_data, errors = SecurityValidator.validate_all_fields(
                        name, cpf, empresa, placa, ""
                    )
                    
                    if not is_valid:
                        show_security_alert("Dados inválidos detectados:", "error")
                        for error in errors:
                            st.error(error)
                        SessionSecurity.record_failed_attempt(user_id, f"Invalid data: {'; '.join(errors)}")
                    elif not all([name, cpf, empresa, aprovador]):
                        st.error("❌ Preencha todos os campos obrigatórios, incluindo o aprovador.")
                    elif not aprovador_ciente:
                        st.error("❌ Você deve confirmar que o aprovador está ciente desta entrada.")
                    else:
                        # >>> VERIFICAÇÃO DE BLOCKLIST MELHORADA <
                        is_blocked, reason = is_entity_blocked(clean_data['name'], clean_data['empresa'])
                        if is_blocked:
                            st.error(f"🚫 **ACESSO BLOQUEADO**")
                            st.warning(f"**Motivo do bloqueio:** {reason}")
                            st.info("Esta pessoa/empresa está na lista de bloqueios permanentes e não pode ser cadastrada.")
                            log_action("BLOCKED_ACCESS_ATTEMPT", f"Tentativa de cadastro de '{clean_data['name']}' da empresa '{clean_data['empresa']}' interceptada. Motivo: {reason}")
                            SessionSecurity.record_failed_attempt(user_id, f"Blocked entity: {clean_data['name']}")
                            
                            # Oferece opção de solicitar liberação excepcional
                            st.divider()
                            st.write("**Para permitir o acesso desta pessoa/empresa, você precisa solicitar uma liberação excepcional.**")
                            if st.button("⚠️ Solicitar Liberação Excepcional ao Administrador", key="req_override_novo", use_container_width=True, type="secondary"):
                                request_blocklist_override_dialog(clean_data['name'], clean_data['empresa'])
                            st.stop()  # Impede continuar o cadastro
                        # >>> FIM DA MELHORIA <
                        
                        # Se não estiver bloqueado, continua normal
                        st.session_state.processing = True
                        now = get_sao_paulo_time()
                        
                        if add_record(
                            name=clean_data['name'], 
                            cpf=clean_data['cpf'], 
                            placa=clean_data['placa'], 
                            marca_carro=marca_carro.strip() if marca_carro else "", 
                            horario_entrada=now.strftime("%H:%M"), 
                            data=now.strftime("%d/%m/%Y"), 
                            empresa=clean_data['empresa'], 
                            status="Autorizado", 
                            motivo="", 
                            aprovador=aprovador, 
                            first_reg_date=now.strftime("%d/%m/%Y")
                        ):
                            log_action("CREATE_RECORD", f"Cadastrou novo visitante: '{clean_data['name']}'. Aprovador: {aprovador} (confirmado ciente)")
                            st.success(f"✅ Novo registro para {clean_data['name']} criado com sucesso e autorizado por {aprovador}!")
                            
                            # Reseta rate limit em caso de sucesso
                            RateLimiter.reset_rate_limit(user_id, 'create_record')
                            
                            clear_access_cache()
                        
                        st.session_state.processing = False
                        st.rerun()

    with col_sidebar:
        if not df.empty: 
            show_people_inside(df, db_ops)
    
    st.divider()

    if is_admin():
        with st.expander("Gerenciamento de Registros (Ações Administrativas)"):
            st.warning("Use com cuidado. As ações aqui são permanentes e afetam o histórico.")
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Bloquear Pessoa")
                person_to_block = st.selectbox("Selecione para bloquear:", options=[""] + unique_names, key="block_person", index=0)
                if person_to_block:
                    motivo = st.text_input("Motivo do Bloqueio:", key="block_reason")
                    if st.button("Aplicar Bloqueio", key="apply_block", type="primary", disabled=st.session_state.processing):
                        st.session_state.processing = True
                        if motivo and not df[df["Nome"] == person_to_block].empty:
                            now = get_sao_paulo_time()
                            last_record = df[df["Nome"] == person_to_block].iloc[0]
                            if add_record(name=str(person_to_block), cpf=str(last_record.get("CPF", "")), placa="", marca_carro="", horario_entrada=now.strftime("%H:%M"), data=now.strftime("%d/%m/%Y"), empresa=str(last_record.get("Empresa", "")), status="Bloqueado", motivo=motivo, aprovador="Admin", first_reg_date=""):
                                log_action("BLOCK_USER", f"Bloqueou o usuário '{person_to_block}'. Motivo: {motivo}.")
                                st.success(f"{person_to_block} foi bloqueado com sucesso.")
                                clear_access_cache()
                        else:
                            st.error("O motivo é obrigatório e a pessoa deve ter pelo menos um registro anterior.")
                        st.session_state.processing = False
                        st.rerun()
            with col2:
                st.subheader("Deletar Último Registro")
                person_to_delete = st.selectbox("Selecione a pessoa para deletar o último registro:", options=[""] + unique_names, key="delete_person", index=0)
                if person_to_delete:
                    if st.button("Deletar Último Registro", key="apply_delete", type="secondary", disabled=st.session_state.processing):
                        st.session_state.processing = True
                        records = df[df["Nome"] == person_to_delete].copy()
                        if not records.empty:
                            last_record_id = records.iloc[0]['ID']
                            if delete_record_by_id(last_record_id):
                                log_action("DELETE_RECORD", f"Deletou o último registro de '{person_to_delete}' (ID: {last_record_id}).")
                                st.success(f"Último registro de {person_to_delete} deletado com sucesso.")
                                clear_access_cache()
                            else: st.error("Falha ao deletar o registro.")
                        else: st.warning(f"Nenhum registro encontrado para {person_to_delete}.")
                        st.session_state.processing = False
                        st.rerun()
    
    with st.expander("Visualizar todos os registros"):
        if not df.empty:
            colunas_para_exibir = [
                "Data",
                "Horário de Entrada",
                "Horário de Saída",
                "Nome",
                "Empresa",
                "Placa",
                "Status da Entrada",
                "Aprovador"
            ]
            
            df_visualizacao = df[colunas_para_exibir].copy()

            st.dataframe(
                df_visualizacao.fillna(""), 
                use_container_width=True, 
                hide_index=True
            )
        else:
            st.info("Nenhum registro para exibir.")

        show_scheduled_today(db_ops)

@st.dialog("Saída de Material?")
def show_material_confirmation_dialog_individual(person_name, latest_record, db_ops):
    """Dialog que pergunta se a pessoa está levando material (saída individual)."""
    st.write(f"**{person_name}** está levando algum material?")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("✅ Sim, registrar material", type="primary", use_container_width=True, key="sim_individual"):
            st.session_state['material_choice_individual'] = 'sim'
            st.rerun()
    
    with col2:
        if st.button("❌ Não, apenas saída", use_container_width=True, key="nao_individual"):
            st.session_state['material_choice_individual'] = 'nao'
            st.rerun()
    
    material_choice = st.session_state.get('material_choice_individual')
    
    if material_choice == 'sim':
        st.divider()
        st.subheader("Dados do Material")
        
        lista_materiais_data = db_ops.load_materials()
        lista_materiais = [item['item'] for item in lista_materiais_data if item.get('item')] if lista_materiais_data else []
        
        if not lista_materiais:
            st.error("❌ Nenhum material cadastrado na aba 'materials'")
            if st.button("Fechar", key="close_individual"):
                cleanup_exit_session_state_individual()
                st.rerun()
            return
        
        material_item = st.selectbox(
            "Item:",
            options=[""] + lista_materiais,
            key="mat_item_individual"
        )
        
        col_qtd, col_dest = st.columns(2)
        with col_qtd:
            material_qtd = st.number_input(
                "Quantidade:",
                min_value=1,
                value=1,
                key="mat_qtd_individual"
            )
        
        with col_dest:
            material_destino = st.text_input(
                "Destino:",
                placeholder="Ex: Obra, Cliente, Matriz",
                key="mat_dest_individual"
            )
        
        material_responsavel = st.text_input(
            "Responsável pela Saída:",
            value=person_name,
            key="mat_resp_individual",
            help="Pessoa responsável por levar o material"
        )
        
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            if st.button("✅ Confirmar Saída com Material", type="primary", use_container_width=True, key="confirm_mat_individual"):
                if not material_item or material_item == "":
                    st.error("❌ Selecione um item")
                    return
                if not material_destino or material_destino.strip() == "":
                    st.error("❌ Informe o destino do material")
                    return
                if not material_responsavel or material_responsavel.strip() == "":
                    st.error("❌ Informe o responsável pela saída")
                    return
                
                process_exit_with_material_individual(
                    person_name,
                    sheet_operations,
                    material_item,
                    material_qtd,
                    material_destino.strip(),
                    material_responsavel.strip()
                )
        
        with col_btn2:
            if st.button("❌ Cancelar", use_container_width=True, key="cancel_mat_individual"):
                cleanup_exit_session_state_individual()
                st.rerun()
    
    elif material_choice == 'nao':
        process_exit_without_material_individual(person_name)

def cleanup_exit_session_state_individual():
    """Limpa session_state para saída individual."""
    keys_to_delete = [
        'exit_clicked_individual',
        'exit_person_name_individual',
        'material_choice_individual',
        'exit_processed_individual',  # NOVO
        # Limpa campos do formulário
        'mat_item_individual',
        'mat_qtd_individual',
        'mat_dest_individual',
        'mat_resp_individual'
    ]
    for key in keys_to_delete:
        if key in st.session_state:
            del st.session_state[key]

def process_exit_with_material_individual(person_name, sheet_ops, item, qtd, destino, responsavel):
    """Processa saída individual com material."""
    st.session_state.exit_processed_individual = True  # NOVO
    st.session_state.processing = True
    now = get_sao_paulo_time()
    
    success, message = update_exit_time(
        person_name,
        now.strftime("%d/%m/%Y"),
        now.strftime("%H:%M")
    )
    
    if success:
        log_action("REGISTER_EXIT", f"Registrou saída para '{person_name}'.")
        
        material_registro = [item, str(qtd), destino, responsavel]
        
        if sheet_ops.adc_dados_aba(material_registro, 'materials'):
            log_action(
                "SAIDA_MATERIAL",
                f"{responsavel} levou {qtd}x {item} para {destino}"
            )
            st.success(f"✅ Saída de {person_name} registrada!")
            st.info(f" Material: {qtd}x {item} → {destino}")
        else:
            st.warning("⚠️ Saída registrada, mas houve erro ao registrar o material")
        
        cleanup_exit_session_state_individual()
        clear_access_cache()
        st.session_state.processing = False
        
        import time
        time.sleep(0.1)
        st.rerun()
    else:
        st.error(f"❌ {message}")
        st.session_state.processing = False
        st.session_state.exit_processed_individual = False


def process_exit_without_material_individual(person_name):
    """Processa saída individual sem material."""
    st.session_state.exit_processed_individual = True # NOVO
    st.session_state.processing = True
    now = get_sao_paulo_time()
    
    success, message = update_exit_time(
        person_name,
        now.strftime("%d/%m/%Y"),
        now.strftime("%H:%M")
    )
    
    if success:
        log_action("REGISTER_EXIT", f"Registrou saída para '{person_name}'.")
        st.success(f"✅ Saída de {person_name} registrada!")
        
        cleanup_exit_session_state_individual()
        clear_access_cache()
        st.session_state.processing = False
        
        import time
        time.sleep(0.1)
        st.rerun()
    else:
        st.error(f"❌ {message}")
        st.session_state.processing = False
        st.session_state.exit_processed_individual = False