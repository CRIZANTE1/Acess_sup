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
            
            self.client: Client = create_client(supabase_url, supabase_key)
            logging.info("Cliente público Supabase inicializado.")
            
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
    
    def add_access_record(self, record_data: Dict) -> Optional[str]:
        """
        Adiciona registro de acesso.
        Respeita RLS: público pode inserir registros de acesso.
        """
        if not self._check_connection():
            return None
        try:
            response = self.client.table('access_records').insert(record_data).execute()
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

