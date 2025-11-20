"""
Módulo para interação com Supabase Database
Substitui o uso de Google Sheets
"""
import streamlit as st
import os
from supabase import create_client, Client
from typing import Optional, List, Dict, Any
import logging
from datetime import datetime

logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

class SupabaseOperations:
    """Classe para encapsular operações com Supabase Database"""
    
    def __init__(self):
        """Inicializa a conexão com Supabase"""
        try:
            # Tenta obter do secrets do Streamlit primeiro
            if "supabase" in st.secrets:
                supabase_url = st.secrets["supabase"]["url"]
                supabase_key = st.secrets["supabase"]["key"]
            else:
                # Fallback para variáveis de ambiente
                supabase_url = os.getenv('SUPABASE_URL')
                supabase_key = os.getenv('SUPABASE_KEY')
            
            if not supabase_url or not supabase_key:
                logging.error("Credenciais do Supabase não configuradas.")
                st.error("Credenciais do Supabase não configuradas. Configure SUPABASE_URL e SUPABASE_KEY.")
                self.client = None
                return
            
            # Cria cliente Supabase
            # Nota: Versões antigas do supabase-py podem ter problemas com proxy
            # A versão >=2.8.1 resolve esse problema
            try:
                self.client: Client = create_client(supabase_url, supabase_key)
                logging.info("Conexão com Supabase estabelecida com sucesso.")
            except (TypeError, ValueError) as e:
                # Se houver erro de argumentos (ex: proxy), tenta criar sem opções extras
                error_msg = str(e)
                if 'proxy' in error_msg.lower():
                    logging.warning(f"Erro relacionado a proxy detectado. Atualize supabase-py para >=2.8.1: {e}")
                else:
                    logging.warning(f"Erro ao criar cliente Supabase: {e}")
                self.client = None
            
        except Exception as e:
            logging.error(f"Erro ao conectar ao Supabase: {e}")
            st.error(f"Erro ao conectar ao Supabase: {e}")
            self.client = None
    
    def _check_connection(self) -> bool:
        """Verifica se a conexão está ativa"""
        if not self.client:
            st.error("Conexão com Supabase não disponível.")
            return False
        return True
    
    # ========== OPERAÇÕES COM PESSOAS ==========
    
    def get_person_by_id(self, person_id: str) -> Optional[Dict]:
        """Busca uma pessoa pelo ID"""
        if not self._check_connection():
            return None
        try:
            response = self.client.table('people').select('*').eq('id', person_id).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logging.error(f"Erro ao buscar pessoa por ID: {e}")
            return None
    
    def get_person_by_cpf(self, cpf: str) -> Optional[Dict]:
        """Busca uma pessoa pelo CPF"""
        if not self._check_connection():
            return None
        try:
            response = self.client.table('people').select('*').eq('cpf', cpf).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logging.error(f"Erro ao buscar pessoa por CPF: {e}")
            return None
    
    def get_person_by_name(self, name: str) -> Optional[Dict]:
        """Busca uma pessoa pelo nome (primeira ocorrência)"""
        if not self._check_connection():
            return None
        try:
            response = self.client.table('people').select('*').ilike('name', f'%{name}%').limit(1).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logging.error(f"Erro ao buscar pessoa por nome: {e}")
            return None
    
    def get_people_with_face_encoding(self) -> List[Dict]:
        """Busca todas as pessoas que têm encoding facial cadastrado"""
        if not self._check_connection():
            return []
        try:
            response = self.client.table('people').select('*').not_.is_('face_encoding', 'null').execute()
            return response.data if response.data else []
        except Exception as e:
            logging.error(f"Erro ao buscar pessoas com encoding facial: {e}")
            return []
    
    def create_person(self, name: str, cpf: str = None, company: str = None, 
                     face_encoding: str = None, face_photo_url: str = None) -> Optional[str]:
        """Cria uma nova pessoa e retorna o ID"""
        if not self._check_connection():
            return None
        try:
            data = {
                'name': name,
                'cpf': cpf,
                'company': company,
                'face_encoding': face_encoding,
                'face_photo_url': face_photo_url
            }
            # Remove None values
            data = {k: v for k, v in data.items() if v is not None}
            
            response = self.client.table('people').insert(data).execute()
            if response.data:
                return response.data[0]['id']
            return None
        except Exception as e:
            logging.error(f"Erro ao criar pessoa: {e}")
            st.error(f"Erro ao criar pessoa: {e}")
            return None
    
    def update_person(self, person_id: str, **kwargs) -> bool:
        """Atualiza dados de uma pessoa"""
        if not self._check_connection():
            return False
        try:
            # Remove None values
            data = {k: v for k, v in kwargs.items() if v is not None}
            response = self.client.table('people').update(data).eq('id', person_id).execute()
            return True
        except Exception as e:
            logging.error(f"Erro ao atualizar pessoa: {e}")
            return False
    
    # ========== OPERAÇÕES COM REGISTROS DE ACESSO ==========
    
    def load_access_records(self) -> List[Dict]:
        """Carrega todos os registros de acesso"""
        if not self._check_connection():
            return []
        try:
            response = self.client.table('access_records').select('*').order('data', desc=True).order('horario_entrada', desc=True).execute()
            return response.data if response.data else []
        except Exception as e:
            logging.error(f"Erro ao carregar registros de acesso: {e}")
            return []
    
    def add_access_record(self, name: str, cpf: str = None, placa: str = None, 
                         marca_carro: str = None, horario_entrada: str = None,
                         data: str = None, empresa: str = None, status: str = None,
                         motivo: str = None, aprovador: str = None, 
                         first_reg_date: str = None, person_id: str = None) -> Optional[str]:
        """Adiciona um novo registro de acesso"""
        if not self._check_connection():
            return None
        try:
            # Converte data de string para date se necessário
            data_date = None
            if data:
                try:
                    data_date = datetime.strptime(data, "%d/%m/%Y").date()
                except:
                    pass
            
            first_reg_date_obj = None
            if first_reg_date:
                try:
                    first_reg_date_obj = datetime.strptime(first_reg_date, "%d/%m/%Y").date()
                except:
                    pass
            
            record_data = {
                'person_id': person_id,
                'name': name,
                'cpf': cpf,
                'placa': placa,
                'marca_carro': marca_carro,
                'horario_entrada': horario_entrada,
                'data': data_date.isoformat() if data_date else None,
                'empresa': empresa,
                'status_entrada': status or 'Pendente de Aprovação',
                'motivo_bloqueio': motivo,
                'aprovador': aprovador,
                'data_primeiro_registro': first_reg_date_obj.isoformat() if first_reg_date_obj else None
            }
            
            # Remove None values
            record_data = {k: v for k, v in record_data.items() if v is not None}
            
            response = self.client.table('access_records').insert(record_data).execute()
            if response.data:
                return response.data[0]['id']
            return None
        except Exception as e:
            logging.error(f"Erro ao adicionar registro de acesso: {e}")
            st.error(f"Erro ao adicionar registro de acesso: {e}")
            return None
    
    def update_access_record(self, record_id: str, **kwargs) -> bool:
        """Atualiza um registro de acesso"""
        if not self._check_connection():
            return False
        try:
            # Converte datas se necessário
            if 'data' in kwargs and kwargs['data']:
                try:
                    if isinstance(kwargs['data'], str):
                        kwargs['data'] = datetime.strptime(kwargs['data'], "%d/%m/%Y").date().isoformat()
                except:
                    pass
            
            if 'data_primeiro_registro' in kwargs and kwargs['data_primeiro_registro']:
                try:
                    if isinstance(kwargs['data_primeiro_registro'], str):
                        kwargs['data_primeiro_registro'] = datetime.strptime(kwargs['data_primeiro_registro'], "%d/%m/%Y").date().isoformat()
                except:
                    pass
            
            data = {k: v for k, v in kwargs.items() if v is not None}
            response = self.client.table('access_records').update(data).eq('id', record_id).execute()
            return True
        except Exception as e:
            logging.error(f"Erro ao atualizar registro de acesso: {e}")
            return False
    
    def delete_access_record(self, record_id: str) -> bool:
        """Deleta um registro de acesso"""
        if not self._check_connection():
            return False
        try:
            response = self.client.table('access_records').delete().eq('id', record_id).execute()
            return True
        except Exception as e:
            logging.error(f"Erro ao deletar registro de acesso: {e}")
            return False
    
    def get_access_record_by_id(self, record_id: str) -> Optional[Dict]:
        """Busca um registro de acesso pelo ID"""
        if not self._check_connection():
            return None
        try:
            response = self.client.table('access_records').select('*').eq('id', record_id).execute()
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            logging.error(f"Erro ao buscar registro por ID: {e}")
            return None
    
    # ========== OPERAÇÕES COM USUÁRIOS ==========
    
    def load_users(self) -> List[Dict]:
        """Carrega todos os usuários"""
        if not self._check_connection():
            return []
        try:
            response = self.client.table('users').select('*').execute()
            return response.data if response.data else []
        except Exception as e:
            logging.error(f"Erro ao carregar usuários: {e}")
            return []
    
    def add_user(self, user_email: str, role: str) -> bool:
        """Adiciona um novo usuário"""
        if not self._check_connection():
            return False
        try:
            data = {
                'user_email': user_email.lower(),
                'role': role
            }
            response = self.client.table('users').insert(data).execute()
            return True
        except Exception as e:
            logging.error(f"Erro ao adicionar usuário: {e}")
            return False
    
    def remove_user(self, user_email: str) -> bool:
        """Remove um usuário"""
        if not self._check_connection():
            return False
        try:
            response = self.client.table('users').delete().eq('user_email', user_email.lower()).execute()
            return True
        except Exception as e:
            logging.error(f"Erro ao remover usuário: {e}")
            return False
    
    # ========== OPERAÇÕES COM BLOCKLIST ==========
    
    def load_blocklist(self) -> List[Dict]:
        """Carrega a blocklist"""
        if not self._check_connection():
            return []
        try:
            response = self.client.table('blocklist').select('*').execute()
            return response.data if response.data else []
        except Exception as e:
            logging.error(f"Erro ao carregar blocklist: {e}")
            return []
    
    def add_to_blocklist(self, block_type: str, value: str, reason: str, blocked_by: str) -> bool:
        """Adiciona à blocklist"""
        if not self._check_connection():
            return False
        try:
            data = {
                'type': block_type,
                'value': value,
                'reason': reason,
                'blocked_by': blocked_by
            }
            response = self.client.table('blocklist').insert(data).execute()
            return True
        except Exception as e:
            logging.error(f"Erro ao adicionar à blocklist: {e}")
            return False
    
    def remove_from_blocklist(self, block_id: str) -> bool:
        """Remove da blocklist"""
        if not self._check_connection():
            return False
        try:
            response = self.client.table('blocklist').delete().eq('id', block_id).execute()
            return True
        except Exception as e:
            logging.error(f"Erro ao remover da blocklist: {e}")
            return False
    
    # ========== OPERAÇÕES COM AGENDAMENTOS ==========
    
    def load_schedules(self) -> List[Dict]:
        """Carrega todos os agendamentos"""
        if not self._check_connection():
            return []
        try:
            response = self.client.table('schedules').select('*').order('scheduled_date', desc=True).execute()
            return response.data if response.data else []
        except Exception as e:
            logging.error(f"Erro ao carregar agendamentos: {e}")
            return []
    
    def add_schedule(self, visitor_name: str, visitor_cpf: str = None, company: str = None,
                    scheduled_date: str = None, scheduled_time: str = None,
                    authorized_by: str = None) -> Optional[str]:
        """Adiciona um novo agendamento"""
        if not self._check_connection():
            return None
        try:
            scheduled_date_obj = None
            if scheduled_date:
                try:
                    scheduled_date_obj = datetime.strptime(scheduled_date, "%d/%m/%Y").date()
                except:
                    pass
            
            data = {
                'visitor_name': visitor_name,
                'visitor_cpf': visitor_cpf,
                'company': company,
                'scheduled_date': scheduled_date_obj.isoformat() if scheduled_date_obj else None,
                'scheduled_time': scheduled_time,
                'authorized_by': authorized_by,
                'status': 'Agendado'
            }
            
            data = {k: v for k, v in data.items() if v is not None}
            response = self.client.table('schedules').insert(data).execute()
            if response.data:
                return response.data[0]['id']
            return None
        except Exception as e:
            logging.error(f"Erro ao adicionar agendamento: {e}")
            return None
    
    def update_schedule(self, schedule_id: str, **kwargs) -> bool:
        """Atualiza um agendamento"""
        if not self._check_connection():
            return False
        try:
            if 'scheduled_date' in kwargs and kwargs['scheduled_date']:
                try:
                    if isinstance(kwargs['scheduled_date'], str):
                        kwargs['scheduled_date'] = datetime.strptime(kwargs['scheduled_date'], "%d/%m/%Y").date().isoformat()
                except:
                    pass
            
            data = {k: v for k, v in kwargs.items() if v is not None}
            response = self.client.table('schedules').update(data).eq('id', schedule_id).execute()
            return True
        except Exception as e:
            logging.error(f"Erro ao atualizar agendamento: {e}")
            return False
    
    # ========== OPERAÇÕES COM SOLICITAÇÕES DE ACESSO ==========
    
    def load_access_requests(self) -> List[Dict]:
        """Carrega todas as solicitações de acesso"""
        if not self._check_connection():
            return []
        try:
            response = self.client.table('access_requests').select('*').order('request_date', desc=True).execute()
            return response.data if response.data else []
        except Exception as e:
            logging.error(f"Erro ao carregar solicitações de acesso: {e}")
            return []
    
    def add_access_request(self, user_email: str, user_name: str, desired_role: str,
                          department: str = None, justification: str = None,
                          manager_email: str = None) -> Optional[str]:
        """Adiciona uma nova solicitação de acesso"""
        if not self._check_connection():
            return None
        try:
            data = {
                'user_email': user_email.lower(),
                'user_name': user_name,
                'desired_role': desired_role,
                'department': department,
                'justification': justification,
                'manager_email': manager_email,
                'status': 'Pendente'
            }
            
            data = {k: v for k, v in data.items() if v is not None}
            response = self.client.table('access_requests').insert(data).execute()
            if response.data:
                return response.data[0]['id']
            return None
        except Exception as e:
            logging.error(f"Erro ao adicionar solicitação de acesso: {e}")
            return None
    
    def update_access_request(self, request_id: str, **kwargs) -> bool:
        """Atualiza uma solicitação de acesso"""
        if not self._check_connection():
            return False
        try:
            data = {k: v for k, v in kwargs.items() if v is not None}
            response = self.client.table('access_requests').update(data).eq('id', request_id).execute()
            return True
        except Exception as e:
            logging.error(f"Erro ao atualizar solicitação de acesso: {e}")
            return False
    
    # ========== OPERAÇÕES COM APROVADORES ==========
    
    def load_authorizers(self) -> List[str]:
        """Carrega a lista de aprovadores"""
        if not self._check_connection():
            return []
        try:
            response = self.client.table('authorizers').select('name').execute()
            if response.data:
                return [row['name'] for row in response.data if row.get('name')]
            return []
        except Exception as e:
            logging.error(f"Erro ao carregar aprovadores: {e}")
            return []
    
    # ========== OPERAÇÕES COM MATERIAIS ==========
    
    def load_materials(self) -> List[Dict]:
        """Carrega a lista de materiais"""
        if not self._check_connection():
            return []
        try:
            response = self.client.table('materials').select('*').execute()
            return response.data if response.data else []
        except Exception as e:
            logging.error(f"Erro ao carregar materiais: {e}")
            return []
    
    # ========== OPERAÇÕES COM LOGS ==========
    
    def add_log(self, user_email: str, action: str, details: str = None) -> bool:
        """Adiciona um log"""
        if not self._check_connection():
            return False
        try:
            data = {
                'user_email': user_email,
                'action': action,
                'details': details
            }
            response = self.client.table('logs').insert(data).execute()
            return True
        except Exception as e:
            logging.error(f"Erro ao adicionar log: {e}")
            return False
    
    def load_logs(self) -> List[Dict]:
        """Carrega todos os logs"""
        if not self._check_connection():
            return []
        try:
            response = self.client.table('logs').select('*').order('timestamp', desc=True).execute()
            return response.data if response.data else []
        except Exception as e:
            logging.error(f"Erro ao carregar logs: {e}")
            return []
    
    # ========== OPERAÇÕES COM STORAGE (FOTOS) ==========
    
    def upload_face_photo(self, person_id: str, image_bytes: bytes, file_extension: str = 'jpg') -> Optional[str]:
        """
        Faz upload de uma foto para o Supabase Storage.
        
        Args:
            person_id: ID da pessoa
            image_bytes: Bytes da imagem
            file_extension: Extensão do arquivo (jpg, png, etc)
        
        Returns:
            URL pública da foto ou None em caso de erro
        """
        if not self._check_connection():
            return None
        
        try:
            bucket_name = 'face-photos'  # Nome do bucket no Supabase Storage
            file_path = f"{person_id}/photo.{file_extension}"
            
            # Faz upload do arquivo
            response = self.client.storage.from_(bucket_name).upload(
                path=file_path,
                file=image_bytes,
                file_options={"content-type": f"image/{file_extension}", "upsert": "true"}
            )
            
            # Obtém URL pública
            public_url = self.client.storage.from_(bucket_name).get_public_url(file_path)
            
            return public_url
            
        except Exception as e:
            logging.error(f"Erro ao fazer upload de foto: {e}")
            # Se o bucket não existir, tenta criar (requer permissões)
            try:
                # Nota: Criação de bucket requer permissões admin
                # O bucket deve ser criado manualmente no painel do Supabase
                logging.warning(f"Bucket 'face-photos' pode não existir. Crie-o no painel do Supabase.")
            except:
                pass
            return None
    
    def delete_face_photo(self, person_id: str, file_extension: str = 'jpg') -> bool:
        """
        Deleta uma foto do Supabase Storage.
        
        Args:
            person_id: ID da pessoa
            file_extension: Extensão do arquivo
        
        Returns:
            True se sucesso, False caso contrário
        """
        if not self._check_connection():
            return False
        
        try:
            bucket_name = 'face-photos'
            file_path = f"{person_id}/photo.{file_extension}"
            
            self.client.storage.from_(bucket_name).remove([file_path])
            return True
            
        except Exception as e:
            logging.error(f"Erro ao deletar foto: {e}")
            return False
    
    def get_face_photo_url(self, person_id: str, file_extension: str = 'jpg') -> Optional[str]:
        """
        Obtém a URL pública de uma foto.
        
        Args:
            person_id: ID da pessoa
            file_extension: Extensão do arquivo
        
        Returns:
            URL pública ou None
        """
        if not self._check_connection():
            return None
        
        try:
            bucket_name = 'face-photos'
            file_path = f"{person_id}/photo.{file_extension}"
            
            public_url = self.client.storage.from_(bucket_name).get_public_url(file_path)
            return public_url
            
        except Exception as e:
            logging.error(f"Erro ao obter URL da foto: {e}")
            return None

