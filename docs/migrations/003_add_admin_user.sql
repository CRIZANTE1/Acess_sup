-- Migration: Adicionar Usuário Administrador
-- Adiciona o usuário admin inicial ao sistema

-- ============================================
-- ADICIONAR USUÁRIO ADMINISTRADOR
-- ============================================

-- Insere ou atualiza o usuário admin
-- Usa email em minúsculas para consistência
INSERT INTO users (user_email, role, created_at, updated_at)
VALUES (
    LOWER('bboycrysforever@gmail.com'),
    'admin',
    NOW(),
    NOW()
)
ON CONFLICT (user_email) 
DO UPDATE SET
    role = 'admin',
    updated_at = NOW();

-- ============================================
-- VERIFICAR SE FOI ADICIONADO
-- ============================================
SELECT 
    user_email,
    role,
    created_at,
    updated_at
FROM users
WHERE user_email = 'bboycrysforever@gmail.com';

-- ============================================
-- NOTA:
-- ============================================
-- Este usuário terá acesso total (admin) ao sistema.
-- Certifique-se de que o email corresponde ao email
-- usado no login via Google OIDC.
-- ============================================

