-- Script de Verificação das Políticas RLS
-- Execute este script para verificar se todas as políticas foram criadas corretamente

-- ============================================
-- 1. VERIFICAR SE RLS ESTÁ HABILITADO
-- ============================================
SELECT 
    tablename,
    rowsecurity as rls_enabled
FROM pg_tables 
WHERE schemaname = 'public'
    AND tablename IN (
        'people', 'access_records', 'users', 'blocklist', 
        'schedules', 'access_requests', 'logs', 'authorizers', 'materials'
    )
ORDER BY tablename;

-- ============================================
-- 2. VERIFICAR POLÍTICAS CRIADAS
-- ============================================
SELECT 
    schemaname,
    tablename,
    policyname,
    permissive,
    roles,
    cmd as command,
    qual as using_expression,
    with_check as with_check_expression
FROM pg_policies 
WHERE schemaname = 'public'
ORDER BY tablename, policyname;

-- ============================================
-- 3. VERIFICAR FUNÇÃO get_user_role()
-- ============================================
SELECT 
    proname as function_name,
    prosrc as function_body
FROM pg_proc 
WHERE proname = 'get_user_role';

-- ============================================
-- 4. VERIFICAR COLUNA ROLE NA TABELA USERS
-- ============================================
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = 'public'
    AND table_name = 'users'
    AND column_name = 'role';

-- ============================================
-- 5. CONTAR POLÍTICAS POR TABELA
-- ============================================
SELECT 
    tablename,
    COUNT(*) as total_policies
FROM pg_policies
WHERE schemaname = 'public'
GROUP BY tablename
ORDER BY tablename;

-- ============================================
-- RESULTADO ESPERADO:
-- ============================================
-- - Todas as 9 tabelas devem ter RLS habilitado (true)
-- - Deve haver aproximadamente 30-35 políticas criadas
-- - Função get_user_role() deve existir
-- - Coluna 'role' deve existir na tabela 'users'
-- ============================================

