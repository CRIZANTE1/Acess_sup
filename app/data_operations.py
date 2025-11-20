import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from app.supabase_db import SupabaseOperations
from app.logger import log_action
from app.utils import get_sao_paulo_time, validate_cpf


def load_data_from_supabase():
    """Carrega os dados do Supabase e armazena no estado da sessão."""
    try:
        db_ops = SupabaseOperations()
        records = db_ops.load_access_records()
        
        if records:
            # Converte para DataFrame com colunas compatíveis
            df = pd.DataFrame(records)
            
            # Renomeia colunas para compatibilidade com código existente
            column_mapping = {
                'id': 'ID',
                'name': 'Nome',
                'cpf': 'CPF',
                'placa': 'Placa',
                'marca_carro': 'Marca do Carro',
                'horario_entrada': 'Horário de Entrada',
                'horario_saida': 'Horário de Saída',
                'data': 'Data',
                'empresa': 'Empresa',
                'status_entrada': 'Status da Entrada',
                'motivo_bloqueio': 'Motivo do Bloqueio',
                'aprovador': 'Aprovador',
                'data_primeiro_registro': 'Data do Primeiro Registro'
            }
            
            # Renomeia colunas existentes
            df = df.rename(columns=column_mapping)
            
            # Converte datas para formato string brasileiro
            if 'Data' in df.columns:
                df['Data'] = pd.to_datetime(df['Data'], errors='coerce').dt.strftime('%d/%m/%Y')
            if 'Data do Primeiro Registro' in df.columns:
                df['Data do Primeiro Registro'] = pd.to_datetime(df['Data do Primeiro Registro'], errors='coerce').dt.strftime('%d/%m/%Y')
            
            # Preenche valores vazios
            df = df.fillna("")
            st.session_state.df_acesso_veiculos = df
        else:
            st.session_state.df_acesso_veiculos = pd.DataFrame()
    except Exception as e:
        st.error(f"Falha ao carregar dados iniciais do Supabase: {e}")
        st.session_state.df_acesso_veiculos = pd.DataFrame()

def add_record(name, cpf, placa, marca_carro, horario_entrada, data, empresa, status, motivo, aprovador, first_reg_date="", person_id=None):
    """Adiciona um novo registro de acesso no Supabase."""
    try:
        db_ops = SupabaseOperations()
        
        # Tenta encontrar ou criar pessoa
        if not person_id:
            if cpf and validate_cpf(cpf):
                person = db_ops.get_person_by_cpf(cpf)
                if person:
                    person_id = person['id']
                else:
                    # Cria nova pessoa
                    person_id = db_ops.create_person(name=name, cpf=cpf, company=empresa)
            else:
                # Tenta encontrar por nome
                person = db_ops.get_person_by_name(name)
                if person:
                    person_id = person['id']
                else:
                    # Cria nova pessoa sem CPF
                    person_id = db_ops.create_person(name=name, company=empresa)
        
        record_id = db_ops.add_access_record(
            name=name,
            cpf=cpf,
            placa=placa,
            marca_carro=marca_carro,
            horario_entrada=horario_entrada,
            data=data,
            empresa=empresa,
            status=status,
            motivo=motivo,
            aprovador=aprovador,
            first_reg_date=first_reg_date,
            person_id=person_id
        )
        
        if record_id:
            # Só mostra mensagem se não for chamado de contexto público
            if not hasattr(st.session_state, '_silent_mode'):
                st.success("Dados adicionados com sucesso!")
            return True
        else:
            # Só mostra mensagem se não for chamado de contexto público
            if not hasattr(st.session_state, '_silent_mode'):
                st.error("Falha ao adicionar dados no Supabase.")
            return False
    except Exception as e:
        # Só mostra mensagem se não for chamado de contexto público
        if not hasattr(st.session_state, '_silent_mode'):
            st.error(f"Erro ao adicionar registro: {e}")
        return False

def update_exit_time(name, exit_date_str, exit_time_str):
    """
    Atualiza o horário de saída de um registro em aberto.
    Implementa a lógica de pernoite, criando novos registros para cada dia.
    """
    try:
        db_ops = SupabaseOperations()
        all_records = db_ops.load_access_records()
        
        if not all_records:
            return False, "Não foi possível carregar os dados do Supabase."
        
        # Converte para DataFrame para facilitar manipulação
        df = pd.DataFrame(all_records)
        
        # Encontra os registros em aberto (sem horário de saída) para a pessoa especificada
        open_records = df[
            (df["name"] == name) & 
            ((df["horario_saida"].isna()) | (df["horario_saida"] == "") | (df["horario_saida"].isnull()))
        ]
        
        if open_records.empty:
            return False, "Nenhum registro em aberto encontrado para esta pessoa."
        
        record_to_update = open_records.iloc[0]
        record_id = record_to_update["id"]
        
        # Converte as datas
        try:
            entry_date = pd.to_datetime(record_to_update["data"]).date()
            exit_date = datetime.strptime(exit_date_str, "%d/%m/%Y").date()
        except (ValueError, TypeError) as e:
            return False, f"Erro ao processar datas: {e}"
        
        # Caso 1: Saída no mesmo dia da entrada
        if entry_date == exit_date:
            if db_ops.update_access_record(record_id, horario_saida=exit_time_str):
                return True, "Horário de saída atualizado com sucesso."
            return False, "Falha ao atualizar o registro no Supabase."
        
        # Caso 2: Pernoite (saída em dia diferente)
        else:
            # Atualiza o primeiro registro para fechar às 23:59
            if not db_ops.update_access_record(record_id, horario_saida="23:59"):
                return False, "Falha ao atualizar registro de entrada."
            
            # Cria registros intermediários (00:00 - 23:59)
            current_date = entry_date + timedelta(days=1)
            while current_date < exit_date:
                intermediate_record_id = db_ops.add_access_record(
                    name=name,
                    cpf=record_to_update.get("cpf", ""),
                    placa="",
                    marca_carro="",
                    horario_entrada="00:00",
                    data=current_date.strftime("%d/%m/%Y"),
                    empresa=record_to_update.get("empresa", ""),
                    status="Autorizado",
                    motivo="",
                    aprovador=record_to_update.get("aprovador", ""),
                    person_id=record_to_update.get("person_id")
                )
                if intermediate_record_id:
                    db_ops.update_access_record(intermediate_record_id, horario_saida="23:59")
                current_date += timedelta(days=1)
            
            # Cria registro final com horário de saída real
            final_record_id = db_ops.add_access_record(
                name=name,
                cpf=record_to_update.get("cpf", ""),
                placa="",
                marca_carro="",
                horario_entrada="00:00",
                data=exit_date_str,
                empresa=record_to_update.get("empresa", ""),
                status="Autorizado",
                motivo="",
                aprovador=record_to_update.get("aprovador", ""),
                person_id=record_to_update.get("person_id")
            )
            if final_record_id:
                db_ops.update_access_record(final_record_id, horario_saida=exit_time_str)
            
            return True, "Registros de pernoite criados com sucesso."
            
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Erro detalhado em update_exit_time: {error_details}")
        return False, f"Erro ao atualizar horário de saída: {str(e)}"

def update_record_status(record_id, new_status, approver_name):
    """
    Função administrativa para atualizar o status e o aprovador de um registro.
    """
    try:
        db_ops = SupabaseOperations()
        record = db_ops.get_access_record_by_id(record_id)
        
        if not record:
            st.error(f"Registro com ID {record_id} não encontrado para atualização.")
            return False
        
        update_data = {
            'status_entrada': new_status,
            'aprovador': approver_name
        }
        
        if new_status == "Autorizado":
            current_cpf = record.get('cpf', '')
            
            # Só busca CPF anterior se o atual estiver vazio ou inválido
            if not current_cpf or str(current_cpf).strip() == '' or not validate_cpf(current_cpf):
                person_name = record.get('name', '')
                
                # Busca registros anteriores com CPF válido
                all_records = db_ops.load_access_records()
                df = pd.DataFrame(all_records)
                
                if not df.empty:
                    df_copy = df.copy()
                    df_copy['data_dt'] = pd.to_datetime(df_copy['data'], errors='coerce')
                    
                    previous_records_with_cpf = df_copy[
                        (df_copy['name'] == person_name) & 
                        (df_copy['cpf'].notna()) & 
                        (df_copy['cpf'] != '') &
                        (df_copy['cpf'].astype(str).str.match(r'^\d{3}\.\d{3}\.\d{3}-\d{2}$', na=False))
                    ].sort_values('data_dt', ascending=False)
                    
                    if not previous_records_with_cpf.empty:
                        last_valid_cpf = previous_records_with_cpf.iloc[0]['cpf']
                        
                        if validate_cpf(last_valid_cpf):
                            update_data['cpf'] = last_valid_cpf
                            log_action(
                                "ENRICH_DATA", 
                                f"CPF '{last_valid_cpf}' (do registro mais recente) adicionado ao registro {record_id} para '{person_name}' durante a aprovação."
                            )
        
        if db_ops.update_access_record(record_id, **update_data):
            st.success("Status do registro atualizado com sucesso!")
            return True
        else:
            st.error("Falha ao atualizar o status no Supabase.")
            return False
            
    except Exception as e:
        st.error(f"Erro ao atualizar o status do registro: {e}")
        return False

def delete_record_by_id(record_id):
    """Função administrativa para deletar um registro com base no seu ID único."""
    try:
        db_ops = SupabaseOperations()
        if db_ops.delete_access_record(record_id):
            return True
        else:
            st.error(f"Não foi possível deletar o registro com ID {record_id}.")
            return False
    except Exception as e:
        st.error(f"Erro ao deletar registro por ID: {e}")
        return False

def delete_record(name, data_str):
    """Deleta o registro mais recente de uma pessoa em uma data específica."""
    try:
        db_ops = SupabaseOperations()
        all_records = db_ops.load_access_records()
        df = pd.DataFrame(all_records)
        
        # Converte data para comparar
        try:
            target_date = datetime.strptime(data_str, "%d/%m/%Y").date()
            df['data_dt'] = pd.to_datetime(df['data'], errors='coerce').dt.date
            records_to_delete = df[(df["name"] == name) & (df["data_dt"] == target_date)]
        except:
            # Fallback: compara como string
            df['data_str'] = pd.to_datetime(df['data'], errors='coerce').dt.strftime('%d/%m/%Y')
            records_to_delete = df[(df["name"] == name) & (df["data_str"] == data_str)]
        
        if records_to_delete.empty: 
            return False
        
        record_id = records_to_delete.iloc[0]['id']
        return db_ops.delete_access_record(record_id)
    except Exception as e:
        st.error(f"Erro ao deletar registro por nome e data: {e}")
        return False

def check_blocked_records(df):
    """Verifica os status mais recentes e alerta sobre 'Bloqueado' ou 'Pendente de Aprovação'."""
    try:
        if df.empty: return None
        df_copy = df.copy()
        df_copy['Data_dt'] = pd.to_datetime(df_copy['Data'], format='%d/%m/%Y', errors='coerce')
        df_sorted = df_copy.dropna(subset=['Data_dt']).sort_values(by=['Data_dt', 'Horário de Entrada'], ascending=False)
        
        latest_status_df = df_sorted.drop_duplicates(subset='Nome', keep='first')
        
        attention_statuses = ["Bloqueado", "Pendente de Aprovação", "Pendente de Liberação da Blocklist"]
        attention_df = latest_status_df[latest_status_df["Status da Entrada"].isin(attention_statuses)]
        
        if attention_df.empty: return None
        
        info = ""
        for _, row in attention_df.iterrows():
            status = row['Status da Entrada']
            if status == "Pendente de Liberação da Blocklist":
                motivo_display = f"AGUARDANDO APROVAÇÃO EXCEPCIONAL (Solicitante: {row.get('Aprovador', 'N/A')})"
            elif status == "Pendente de Aprovação":
                motivo_display = f"Aguardando aprovação do admin (Solicitante: {row.get('Aprovador', 'N/A')})"
            else: # Bloqueado
                motivo_display = f"Motivo: {row.get('Motivo do Bloqueio', 'N/A')}"
            
            info += f"- **{row['Nome']}**: {status} - {motivo_display}\n"
        return info
    except Exception as e:
        print(f"Erro em check_blocked_records: {e}")
        return "Ocorreu um erro ao verificar os status de bloqueio."


@st.cache_data(ttl=60) 
def get_blocklist():
    """Carrega e retorna a blocklist como um DataFrame."""
    try:
        db_ops = SupabaseOperations()
        blocklist_data = db_ops.load_blocklist()
        if blocklist_data:
            df = pd.DataFrame(blocklist_data)
            # Renomeia para compatibilidade
            df = df.rename(columns={
                'id': 'ID',
                'type': 'Type',
                'value': 'Value',
                'reason': 'Reason',
                'blocked_by': 'BlockedBy',
                'created_at': 'Timestamp'
            })
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao carregar a lista de bloqueios: {e}")
        return pd.DataFrame()

def add_to_blocklist(block_type, values, reason, admin_name):
    """Adiciona uma ou mais entidades à blocklist."""
    try:
        db_ops = SupabaseOperations()
        for value in values:
            if db_ops.add_to_blocklist(block_type, value, reason, admin_name):
                log_action("ADD_TO_BLOCKLIST", f"Tipo: {block_type}, Valor: '{value}', Motivo: {reason}")
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar à blocklist: {e}")
        return False
    
def remove_from_blocklist(block_ids):
    """Remove uma ou mais entradas da blocklist pelo ID."""
    try:
        db_ops = SupabaseOperations()
        blocklist_df = get_blocklist()
        if blocklist_df.empty: return True

        for block_id in block_ids:
            value_to_log = "ID Desconhecido"
            if not blocklist_df[blocklist_df['ID'] == str(block_id)].empty:
                 value_to_log = blocklist_df[blocklist_df['ID'] == str(block_id)]['Value'].iloc[0]

            if not db_ops.remove_from_blocklist(block_id):
                st.error(f"Falha ao remover o bloqueio para '{value_to_log}' (ID: {block_id}). A operação foi interrompida.")
                return False
            else:
                log_action("REMOVE_FROM_BLOCKLIST", f"Liberado: '{value_to_log}' (ID do bloqueio: {block_id})")
        
        return True
        
    except Exception as e:
        st.error(f"Erro ao remover da blocklist: {e}")
        return False

def is_entity_blocked(name, company):
    """Verifica se um nome ou empresa está na blocklist."""
    blocklist_df = get_blocklist()
    if blocklist_df.empty:
        return False, None

    person_block = blocklist_df[
        (blocklist_df['Type'] == 'Pessoa') & 
        (blocklist_df['Value'].str.lower() == name.lower())
    ]
    if not person_block.empty:
        return True, person_block.iloc[0]['Reason']

    company_block = blocklist_df[
        (blocklist_df['Type'] == 'Empresa') & 
        (blocklist_df['Value'].str.lower() == company.lower())
    ]
    if not company_block.empty:
        return True, company_block.iloc[0]['Reason']
        
    return False, None


@st.cache_data(ttl=60)
def get_users():
    """Carrega e retorna a lista de usuários como um DataFrame."""
    try:
        db_ops = SupabaseOperations()
        users_data = db_ops.load_users()
        if users_data:
            df = pd.DataFrame(users_data)
            # Renomeia para compatibilidade
            df = df.rename(columns={
                'id': 'ID',
                'user_email': 'user_email',
                'role': 'role'
            })
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao carregar a lista de usuários: {e}")
        return pd.DataFrame()

def add_user(user_email, role):
    """Adiciona um novo usuário ao Supabase."""
    try:
        db_ops = SupabaseOperations()
        if db_ops.add_user(user_email.lower(), role):
            log_action("ADD_USER", f"Adicionou usuário '{user_email}' com o papel '{role}'.")
            return True
        return False
    except Exception as e:
        st.error(f"Erro ao adicionar usuário: {e}")
        return False

def remove_user(user_email):
    """Remove um usuário do Supabase pelo email."""
    try:
        db_ops = SupabaseOperations()
        if db_ops.remove_user(user_email.lower()):
            log_action("REMOVE_USER", f"Removeu o usuário '{user_email}'.")
            return True
        return False
    except Exception as e:
        st.error(f"Erro ao remover usuário: {e}")
        return False

def update_access_request_status(request_id, new_status, reviewer_name):
    """
    Atualiza o status de uma solicitação de acesso.
    
    Args:
        request_id: ID da solicitação
        new_status: Novo status (Aprovado ou Rejeitado)
        reviewer_name: Nome do revisor
    
    Returns:
        bool: True se sucesso, False caso contrário
    """
    try:
        db_ops = SupabaseOperations()
        if db_ops.update_access_request(request_id, status=new_status, reviewed_by=reviewer_name):
            return True
        else:
            st.error("Falha ao atualizar solicitação de acesso.")
            return False
    except Exception as e:
        st.error(f"Erro ao atualizar status da solicitação: {e}")
        return False

def update_schedule_status(schedule_id, new_status, checkin_time):
    """Atualiza o status e a hora de check-in de um agendamento."""
    try:
        db_ops = SupabaseOperations()
        if db_ops.update_schedule(schedule_id, status=new_status, checkin_time=checkin_time):
            return True
        else:
            st.error("Falha ao atualizar agendamento.")
            return False
    except Exception as e:
        st.error(f"Erro ao atualizar status do agendamento: {e}")
        return False

def check_briefing_needed(person_name, df):
    """
    Verifica se o briefing de segurança precisa ser repassado.
    Retorna True se a pessoa não tem registro ou o último acesso foi há mais de 1 ano.
    """
    try:
        if df.empty:
            return True, "Primeira visita"
        
        person_records = df[df["Nome"] == person_name].copy()
        if person_records.empty:
            return True, "Primeira visita"
        
        # Procura pela data do primeiro registro
        first_reg_date = person_records.iloc[0].get("Data do Primeiro Registro", "")
        
        if not first_reg_date or pd.isna(first_reg_date) or str(first_reg_date).strip() == "":
            # Se não tem data do primeiro registro, usa a data mais antiga
            person_records['Data_dt'] = pd.to_datetime(person_records['Data'], format='%d/%m/%Y', errors='coerce')
            person_records = person_records.dropna(subset=['Data_dt']).sort_values('Data_dt')
            
            if person_records.empty:
                return True, "Sem histórico válido"
            
            first_date = person_records.iloc[0]['Data_dt']
        else:
            first_date = pd.to_datetime(first_reg_date, format='%d/%m/%Y', errors='coerce')
        
        if pd.isna(first_date):
            return True, "Data inválida no histórico"
        
        now = get_sao_paulo_time()
        days_since_first = (now - first_date).days
        
        if days_since_first > 365:
            return True, f"Último acesso há {days_since_first} dias (mais de 1 ano)"
        
        return False, f"Último acesso há {days_since_first} dias"
        
    except Exception as e:
        print(f"Erro em check_briefing_needed: {e}")
        return False, "Erro ao verificar briefing"


def can_register_new_entry(person_id=None, person_name=None, db_ops=None):
    """
    Verifica se é possível registrar uma nova entrada por reconhecimento facial.
    
    Regras:
    - Se não há registro anterior, pode registrar
    - Se o último registro tem saída registrada, pode registrar
    - Se o último registro não tem saída, só pode registrar se passaram 12 horas desde a entrada
    
    Args:
        person_id: ID da pessoa (opcional)
        person_name: Nome da pessoa (opcional)
        db_ops: Instância de SupabaseOperations ou SupabasePublicClient
    
    Returns:
        Tuple (pode_registrar: bool, motivo: str)
    """
    if not db_ops:
        return True, "Sistema não disponível - permitindo registro"
    
    try:
        # Busca todos os registros
        all_records = db_ops.load_access_records()
        
        if not all_records:
            return True, "Primeira entrada"
        
        # Filtra registros da pessoa
        person_records = []
        for record in all_records:
            if person_id and record.get('person_id') == person_id:
                person_records.append(record)
            elif person_name and record.get('name', '').lower() == person_name.lower():
                person_records.append(record)
        
        if not person_records:
            return True, "Primeira entrada"
        
        # Ordena por data e horário de entrada (mais recente primeiro)
        def get_sort_key(record):
            try:
                data_str = record.get('data', '')
                horario = record.get('horario_entrada', '00:00')
                created_at = record.get('created_at', '')
                
                # Tenta usar created_at se disponível (mais preciso)
                if created_at:
                    try:
                        if isinstance(created_at, str):
                            return datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        return created_at
                    except:
                        pass
                
                # Fallback: combina data e horário
                if isinstance(data_str, str) and '/' in data_str:
                    data_obj = datetime.strptime(data_str, "%d/%m/%Y").date()
                elif isinstance(data_str, str):
                    data_obj = datetime.fromisoformat(data_str.split('T')[0]).date()
                else:
                    data_obj = data_str if hasattr(data_str, 'date') else datetime.now().date()
                
                hora, minuto = map(int, horario.split(':')) if ':' in str(horario) else (0, 0)
                return datetime.combine(data_obj, datetime.min.time().replace(hour=hora, minute=minuto))
            except:
                return datetime.min
        
        person_records.sort(key=get_sort_key, reverse=True)
        last_record = person_records[0]
        
        # Verifica se tem horário de saída
        horario_saida = last_record.get('horario_saida')
        if horario_saida and str(horario_saida).strip() and str(horario_saida) != 'None':
            return True, "Última entrada já tem saída registrada"
        
        # Se não tem saída, verifica se passaram 12 horas
        try:
            # Tenta obter data e horário da entrada
            data_entrada = last_record.get('data')
            horario_entrada = last_record.get('horario_entrada', '00:00')
            created_at = last_record.get('created_at')
            
            # Usa created_at se disponível (mais preciso)
            if created_at:
                try:
                    if isinstance(created_at, str):
                        entrada_datetime = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    else:
                        entrada_datetime = created_at
                    
                    # Converte para timezone de São Paulo se necessário
                    if entrada_datetime.tzinfo is None:
                        from app.utils import get_sao_paulo_time
                        now = get_sao_paulo_time()
                        entrada_datetime = entrada_datetime.replace(tzinfo=now.tzinfo)
                    
                    now = get_sao_paulo_time()
                    time_diff = now - entrada_datetime
                    
                    if time_diff.total_seconds() >= 12 * 3600:  # 12 horas em segundos
                        return True, f"Passaram {int(time_diff.total_seconds() / 3600)} horas desde a última entrada"
                    else:
                        horas_restantes = 12 - (time_diff.total_seconds() / 3600)
                        return False, f"Última entrada ainda está aberta. Aguarde {horas_restantes:.1f} horas ou registre a saída primeiro"
                except Exception as e:
                    # Se falhar, tenta método alternativo
                    pass
            
            # Método alternativo: combina data e horário
            if isinstance(data_entrada, str) and '/' in data_entrada:
                data_obj = datetime.strptime(data_entrada, "%d/%m/%Y").date()
            elif isinstance(data_entrada, str):
                data_obj = datetime.fromisoformat(data_entrada.split('T')[0]).date()
            else:
                data_obj = data_entrada if hasattr(data_entrada, 'date') else datetime.now().date()
            
            hora, minuto = map(int, horario_entrada.split(':')) if ':' in str(horario_entrada) else (0, 0)
            entrada_datetime = datetime.combine(data_obj, datetime.min.time().replace(hour=hora, minute=minuto))
            
            # Adiciona timezone de São Paulo
            from app.utils import get_sao_paulo_time
            sao_paulo_tz = get_sao_paulo_time().tzinfo
            entrada_datetime = sao_paulo_tz.localize(entrada_datetime) if entrada_datetime.tzinfo is None else entrada_datetime
            
            now = get_sao_paulo_time()
            time_diff = now - entrada_datetime
            
            if time_diff.total_seconds() >= 12 * 3600:  # 12 horas em segundos
                return True, f"Passaram {int(time_diff.total_seconds() / 3600)} horas desde a última entrada"
            else:
                horas_restantes = 12 - (time_diff.total_seconds() / 3600)
                return False, f"Última entrada ainda está aberta. Aguarde {horas_restantes:.1f} horas ou registre a saída primeiro"
                
        except Exception as e:
            # Em caso de erro, permite o registro mas registra o erro
            print(f"Erro ao verificar tempo desde última entrada: {e}")
            return True, f"Erro ao verificar - permitindo registro (erro: {str(e)})"
        
    except Exception as e:
        print(f"Erro em can_register_new_entry: {e}")
        # Em caso de erro, permite o registro
        return True, f"Erro ao verificar - permitindo registro"