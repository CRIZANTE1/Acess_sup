import streamlit as st
from datetime import datetime
import pytz
from app.supabase_db import SupabaseOperations
from auth.auth_utils import get_user_display_name, get_user_email, is_user_logged_in

def log_action(action: str, details: str = ""):
    """
    Registra uma ação do usuário no Supabase.
    É projetado para não quebrar a aplicação se o log falhar.
    """
    if not is_user_logged_in():
        return

    try:
        user_email = get_user_email()
        db_ops = SupabaseOperations()
        
        if db_ops.add_log(user_email=user_email, action=action, details=details):
            pass  # Log registrado com sucesso
        else:
            print(f"LOGGING FAILED: Não foi possível registrar log no Supabase.")

    except Exception as e:
        print(f"CRITICAL LOGGING ERROR: Falha ao escrever logs no Supabase. Erro: {e}")
