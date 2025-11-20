"""
Cliente Supabase limitado para acesso público
Usa apenas operações permitidas para usuários anônimos (RLS)
"""
import streamlit as st
import os
from supabase import create_client, Client
from typing import Optional, List, Dict
import logging

logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')


class SupabasePublicClient:
    """
    Cliente Supabase com permissões limitadas para acesso público.
    Usa a chave anon do Supabase que respeita as políticas RLS.
    """
    
    def __init__(self):
        """Inicializa a conexão com Supabase usando chave anon (pública)"""
        try:
            # Tenta obter do secrets do Streamlit primeiro
            if "supabase" in st.secrets:
                supabase_url = st.secrets["supabase"]["url"]
                # Usa a chave anon (não a service_role)
                supabase_key = st.secrets["supabase"].get("anon_key") or st.secrets["supabase"].get("key")
            else:
                # Fallback para variáveis de ambiente
                supabase_url = os.getenv('SUPABASE_URL')
                supabase_key = os.getenv('SUPABASE_ANON_KEY') or os.getenv('SUPABASE_KEY')
            
            if not supabase_url or not supabase_key:
                logging.error("Credenciais do Supabase não configuradas para acesso público.")
                self.client = None
                return
            
            # Cria cliente Supabase
            # Nota: Versões antigas do supabase-py podem ter problemas com proxy
            # A versão >=2.8.1 resolve esse problema
            try:
                self.client: Client = create_client(supabase_url, supabase_key)
                logging.info("Cliente público Supabase inicializado.")
            except (TypeError, ValueError) as e:
                # Se houver erro de argumentos (ex: proxy), tenta criar sem opções extras
                error_msg = str(e)
                if 'proxy' in error_msg.lower():
                    logging.warning(f"Erro relacionado a proxy detectado. Atualize supabase-py para >=2.8.1: {e}")
                else:
                    logging.warning(f"Erro ao criar cliente Supabase público: {e}")
                self.client = None
            
        except Exception as e:
            logging.error(f"Erro ao conectar ao Supabase (público): {e}")
            self.client = None
    
    def _check_connection(self) -> bool:
        """Verifica se a conexão está ativa"""
        if not self.client:
            return False
        return True
    
    # ========== OPERAÇÕES PERMITIDAS PARA PÚBLICO ==========
    
    def get_people_with_face_encoding(self) -> List[Dict]:
        """
        Busca pessoas com encoding facial (apenas campos necessários para reconhecimento).
        Respeita RLS: apenas pessoas ativas, apenas campos permitidos.
        """
        if not self._check_connection():
            return []
        try:
            # Seleciona apenas campos permitidos para público
            response = self.client.table('people').select(
                'id, name, face_encoding, face_photo_url, is_active'
            ).eq('is_active', True).not_.is_('face_encoding', 'null').execute()
            return response.data if response.data else []
        except Exception as e:
            logging.error(f"Erro ao buscar pessoas com encoding (público): {e}")
            return []
    
    def get_blocklist(self) -> List[Dict]:
        """
        Busca a blocklist (apenas leitura).
        Respeita RLS: público pode ler blocklist.
        """
        if not self._check_connection():
            return []
        try:
            response = self.client.table('blocklist').select('*').execute()
            return response.data if response.data else []
        except Exception as e:
            logging.error(f"Erro ao buscar blocklist (público): {e}")
            return []
    
    def check_blocked(self, name: str, company: str) -> tuple[bool, Optional[str]]:
        """
        Verifica se um nome ou empresa está na blocklist usando o cliente público.
        Returns: (is_blocked: bool, reason: Optional[str])
        """
        blocklist_data = self.get_blocklist()
        if not blocklist_data:
            return False, None

        for item in blocklist_data:
            if item.get('type') == 'Pessoa' and item.get('value', '').lower() == name.lower():
                return True, item.get('reason', 'Bloqueado por nome')
            if item.get('type') == 'Empresa' and item.get('value', '').lower() == company.lower():
                return True, item.get('reason', 'Bloqueado por empresa')
        return False, None
    
    def load_access_records(self) -> List[Dict]:
        """
        Carrega registros de acesso (apenas leitura).
        Respeita RLS: público pode ler registros de acesso.
        """
        if not self._check_connection():
            return []
        try:
            response = self.client.table('access_records').select('*').order('data', desc=True).order('horario_entrada', desc=True).execute()
            return response.data if response.data else []
        except Exception as e:
            logging.error(f"Erro ao carregar registros de acesso (público): {e}")
            return []
    
    def add_access_record(self, record_data: Dict) -> Optional[str]:
        """
        Adiciona registro de acesso.
        Respeita RLS: público pode inserir registros de acesso.
        Converte datas do formato brasileiro (DD/MM/YYYY) para ISO se necessário.
        """
        if not self._check_connection():
            return None
        try:
            from datetime import datetime
            
            # Prepara os dados convertendo datas se necessário
            prepared_data = record_data.copy()
            
            # Converte data de string brasileira para ISO se necessário
            if 'data' in prepared_data and prepared_data['data']:
                data_str = prepared_data['data']
                if isinstance(data_str, str) and '/' in data_str:
                    try:
                        # Formato brasileiro DD/MM/YYYY
                        data_date = datetime.strptime(data_str, "%d/%m/%Y").date()
                        prepared_data['data'] = data_date.isoformat()
                    except:
                        # Se falhar, mantém como está
                        pass
            
            # Converte data_primeiro_registro se necessário
            if 'data_primeiro_registro' in prepared_data and prepared_data['data_primeiro_registro']:
                first_reg_str = prepared_data['data_primeiro_registro']
                if isinstance(first_reg_str, str) and first_reg_str and '/' in first_reg_str:
                    try:
                        first_reg_date = datetime.strptime(first_reg_str, "%d/%m/%Y").date()
                        prepared_data['data_primeiro_registro'] = first_reg_date.isoformat()
                    except:
                        pass
                elif not first_reg_str or first_reg_str == '':
                    # Remove se vazio
                    prepared_data['data_primeiro_registro'] = None
            
            # Remove apenas strings vazias, mantém None para campos opcionais
            prepared_data = {k: v for k, v in prepared_data.items() if not (isinstance(v, str) and v == '')}
            
            # Insere o registro
            response = self.client.table('access_records').insert(prepared_data).execute()
            if response.data and len(response.data) > 0:
                return response.data[0].get('id')
            return None
        except Exception as e:
            logging.error(f"Erro ao adicionar registro de acesso (público): {e}")
            return None
    
    def add_log(self, action: str, details: str) -> bool:
        """
        Adiciona log.
        Respeita RLS: público pode inserir logs.
        """
        if not self._check_connection():
            return False
        try:
            from datetime import datetime
            data = {
                'action': action,
                'details': details,
                'timestamp': datetime.utcnow().isoformat()
            }
            self.client.table('logs').insert(data).execute()
            return True
        except Exception as e:
            logging.error(f"Erro ao adicionar log (público): {e}")
            return False

