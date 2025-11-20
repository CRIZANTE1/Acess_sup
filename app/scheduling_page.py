import streamlit as st
import pandas as pd
from datetime import datetime
from app.supabase_db import SupabaseOperations
from auth.auth_utils import get_user_display_name
from app.utils import get_sao_paulo_time, format_cpf, validate_cpf
from app.logger import log_action

def scheduling_page():
    st.title("Agendamento de Visitas")
    db_ops = SupabaseOperations()
    
    with st.form(key="scheduling_form"):
        st.write("Preencha os dados abaixo para agendar uma nova visita.")
        
        visitor_name = st.text_input("Nome Completo do Visitante:")
        visitor_cpf = st.text_input("CPF do Visitante:")
        company = st.text_input("Empresa do Visitante:")
        
        col1, col2 = st.columns(2)
        with col1:
            today = get_sao_paulo_time().date()
            scheduled_date = st.date_input("Data da Visita:", value=today, min_value=today)
        with col2:
            scheduled_time = st.time_input("Hora Estimada da Chegada:")
    
        # Aprovador com confirmação
        st.markdown("### 👤 Autorização da Visita")
        authorizer = get_user_display_name()
        st.text_input("Você (Responsável pelo Agendamento):", value=authorizer, disabled=True)
        
        confirmacao_agendamento = st.checkbox(
            "✓ Confirmo que estou ciente e autorizo este agendamento",
            help="Você está assumindo a responsabilidade por este agendamento"
        )
        
        if not confirmacao_agendamento:
            st.warning("⚠️ **Você deve confirmar a ciência do agendamento.**")
    
        submit_button = st.form_submit_button(
            "Agendar Visita",
            disabled=not confirmacao_agendamento
        )
    
    if submit_button:
        if not all([visitor_name, visitor_cpf, company, scheduled_date, scheduled_time]):
            st.error("Por favor, preencha todos os campos.")
        elif not validate_cpf(visitor_cpf):
            st.error("O CPF informado é inválido.")
        elif not confirmacao_agendamento:
            st.error("❌ Você deve confirmar que está ciente do agendamento.")
        else:
            formatted_cpf = format_cpf(visitor_cpf)
            date_str = scheduled_date.strftime("%d/%m/%Y")
            time_str = scheduled_time.strftime("%H:%M")
            status = "Agendado"
            
            schedule_id = db_ops.add_schedule(
                visitor_name=visitor_name.strip(),
                visitor_cpf=formatted_cpf,
                company=company.strip(),
                scheduled_date=date_str,
                scheduled_time=time_str,
                authorized_by=authorizer
            )
            
            if schedule_id:
                st.success(f"✅ Visita para '{visitor_name.strip()}' agendada com sucesso para {date_str} às {time_str}!")
                log_action("CREATE_SCHEDULE", f"Agendou visita para '{visitor_name.strip()}' em {date_str}. Confirmado ciente.")
            else:
                st.error("Ocorreu um erro ao salvar o agendamento. Tente novamente.")

    st.divider()
    
    st.header("Status dos Agendamentos")
    schedules_data = db_ops.load_schedules()
    
    if not schedules_data:
        st.info("Nenhum agendamento encontrado para exibir.")
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
        'status': 'Status',
        'checkin_time': 'CheckInTime'
    }
    df_schedules = df_schedules.rename(columns=column_mapping)
    
    # Converte data para formato brasileiro e depois para datetime
    if 'ScheduledDate' in df_schedules.columns:
        df_schedules['ScheduledDate'] = pd.to_datetime(df_schedules['ScheduledDate'], errors='coerce').dt.strftime('%d/%m/%Y')
    
    df_schedules['ScheduledDate_dt'] = pd.to_datetime(df_schedules['ScheduledDate'], format='%d/%m/%Y', errors='coerce')
  
    df_schedules.dropna(subset=['ScheduledDate_dt'], inplace=True)

    if df_schedules.empty:
        st.info("Nenhum agendamento com data válida encontrado.")
        return

    today_date = get_sao_paulo_time().date()

    # Filtra os DataFrames para cada categoria
    no_shows = df_schedules[
        (df_schedules['ScheduledDate_dt'].dt.date < today_date) &
        (df_schedules['Status'] == 'Agendado')
    ]

    pending_schedules = df_schedules[
        (df_schedules['ScheduledDate_dt'].dt.date >= today_date) &
        (df_schedules['Status'] == 'Agendado')
    ].sort_values(by='ScheduledDate_dt')

    completed_schedules = df_schedules[df_schedules['Status'] == 'Realizado'].sort_values(by='ScheduledDate_dt', ascending=False)

    tab1, tab2, tab3 = st.tabs([
        f"Pendentes ({len(pending_schedules)})", 
        f"Realizados ({len(completed_schedules)})", 
        f"Não Compareceram ({len(no_shows)})"
    ])

    with tab1:
        st.subheader("Visitas Agendadas Pendentes")
        if pending_schedules.empty:
            st.info("Nenhuma visita futura agendada.")
        else:
            st.dataframe(
                pending_schedules[['ScheduledDate', 'ScheduledTime', 'VisitorName', 'Company', 'AuthorizedBy']],
                hide_index=True, use_container_width=True
            )
    
    with tab2:
        st.subheader("Histórico de Visitas Realizadas")
        if completed_schedules.empty:
            st.info("Nenhuma visita foi marcada como realizada ainda.")
        else:
            st.dataframe(
                completed_schedules[['ScheduledDate', 'VisitorName', 'Company', 'CheckInTime', 'AuthorizedBy']],
                hide_index=True, use_container_width=True
            )

    with tab3:
        st.subheader("Agendamentos Não Comparecidos (No-Show)")
        if no_shows.empty:
            st.info("Nenhum agendamento marcado como não comparecido.")
        else:
            st.dataframe(
                no_shows[['ScheduledDate', 'VisitorName', 'Company', 'AuthorizedBy']],
                hide_index=True, use_container_width=True
            )
