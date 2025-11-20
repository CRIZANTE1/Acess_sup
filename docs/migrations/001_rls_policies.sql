-- Migration: Row Level Security (RLS) Policies
-- Aplica políticas de segurança baseadas em roles
-- Roles: 'admin', 'operacional', 'public'

-- ============================================
-- 1. HABILITAR RLS EM TODAS AS TABELAS
-- ============================================

ALTER TABLE people ENABLE ROW LEVEL SECURITY;
ALTER TABLE access_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE blocklist ENABLE ROW LEVEL SECURITY;
ALTER TABLE schedules ENABLE ROW LEVEL SECURITY;
ALTER TABLE access_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE authorizers ENABLE ROW LEVEL SECURITY;
ALTER TABLE materials ENABLE ROW LEVEL SECURITY;

-- ============================================
-- 2. FUNÇÃO HELPER PARA OBTER ROLE DO USUÁRIO
-- ============================================

-- Função para obter o role do usuário atual baseado no email
CREATE OR REPLACE FUNCTION get_user_role()
RETURNS TEXT AS $$
DECLARE
    user_email TEXT;
    user_role TEXT;
BEGIN
    -- Obtém o email do usuário atual (do JWT token ou contexto)
    user_email := current_setting('request.jwt.claims', true)::json->>'email';
    
    -- Se não houver email no JWT, retorna 'public'
    IF user_email IS NULL THEN
        RETURN 'public';
    END IF;
    
    -- Busca o role na tabela users
    SELECT role INTO user_role
    FROM users
    WHERE user_email = LOWER(user_email)
    LIMIT 1;
    
    -- Retorna o role encontrado ou 'public' como padrão
    RETURN COALESCE(user_role, 'public');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================
-- 3. POLÍTICAS PARA TABELA 'people'
-- ============================================

-- Admin: Acesso total
CREATE POLICY "admin_full_access_people"
ON people
FOR ALL
TO authenticated
USING (
    get_user_role() = 'admin'
)
WITH CHECK (
    get_user_role() = 'admin'
);

-- Operacional: Pode ler
CREATE POLICY "operacional_select_people"
ON people
FOR SELECT
TO authenticated
USING (
    get_user_role() = 'operacional' OR get_user_role() = 'admin'
);

-- Operacional: Pode inserir
CREATE POLICY "operacional_insert_people"
ON people
FOR INSERT
TO authenticated
WITH CHECK (
    get_user_role() = 'operacional' OR get_user_role() = 'admin'
);

-- Operacional: Pode atualizar
CREATE POLICY "operacional_update_people"
ON people
FOR UPDATE
TO authenticated
USING (
    get_user_role() = 'operacional' OR get_user_role() = 'admin'
)
WITH CHECK (
    get_user_role() = 'operacional' OR get_user_role() = 'admin'
);

-- Público: Apenas leitura limitada (apenas campos necessários para reconhecimento)
-- Nota: A política permite SELECT, mas apenas campos específicos são retornados pela query
CREATE POLICY "public_read_limited_people"
ON people
FOR SELECT
TO anon
USING (is_active = true);

-- ============================================
-- 4. POLÍTICAS PARA TABELA 'access_records'
-- ============================================

-- Admin: Acesso total
CREATE POLICY "admin_full_access_access_records"
ON access_records
FOR ALL
TO authenticated
USING (
    get_user_role() = 'admin'
)
WITH CHECK (
    get_user_role() = 'admin'
);

-- Operacional: Pode ler
CREATE POLICY "operacional_select_access_records"
ON access_records
FOR SELECT
TO authenticated
USING (
    get_user_role() = 'operacional' OR get_user_role() = 'admin'
);

-- Operacional: Pode inserir
CREATE POLICY "operacional_insert_access_records"
ON access_records
FOR INSERT
TO authenticated
WITH CHECK (
    get_user_role() = 'operacional' OR get_user_role() = 'admin'
);

-- Operacional: Pode atualizar
CREATE POLICY "operacional_update_access_records"
ON access_records
FOR UPDATE
TO authenticated
USING (
    get_user_role() = 'operacional' OR get_user_role() = 'admin'
)
WITH CHECK (
    get_user_role() = 'operacional' OR get_user_role() = 'admin'
);

-- Público: Pode apenas inserir (para registro de acesso)
CREATE POLICY "public_insert_access_records"
ON access_records
FOR INSERT
TO anon
WITH CHECK (true);

-- ============================================
-- 5. POLÍTICAS PARA TABELA 'users'
-- ============================================

-- Admin: Acesso total
CREATE POLICY "admin_full_access_users"
ON users
FOR ALL
TO authenticated
USING (
    get_user_role() = 'admin'
)
WITH CHECK (
    get_user_role() = 'admin'
);

-- Operacional: Apenas leitura
CREATE POLICY "operacional_read_users"
ON users
FOR SELECT
TO authenticated
USING (
    get_user_role() = 'operacional' OR get_user_role() = 'admin'
);

-- Público: Sem acesso
-- (Sem política = sem acesso)

-- ============================================
-- 6. POLÍTICAS PARA TABELA 'blocklist'
-- ============================================

-- Admin: Acesso total
CREATE POLICY "admin_full_access_blocklist"
ON blocklist
FOR ALL
TO authenticated
USING (
    get_user_role() = 'admin'
)
WITH CHECK (
    get_user_role() = 'admin'
);

-- Operacional: Apenas leitura
CREATE POLICY "operacional_read_blocklist"
ON blocklist
FOR SELECT
TO authenticated
USING (
    get_user_role() = 'operacional' OR get_user_role() = 'admin'
);

-- Público: Apenas leitura (para verificar bloqueios)
CREATE POLICY "public_read_blocklist"
ON blocklist
FOR SELECT
TO anon
USING (true);

-- ============================================
-- 7. POLÍTICAS PARA TABELA 'schedules'
-- ============================================

-- Admin: Acesso total
CREATE POLICY "admin_full_access_schedules"
ON schedules
FOR ALL
TO authenticated
USING (
    get_user_role() = 'admin'
)
WITH CHECK (
    get_user_role() = 'admin'
);

-- Operacional: Pode ler
CREATE POLICY "operacional_select_schedules"
ON schedules
FOR SELECT
TO authenticated
USING (
    get_user_role() = 'operacional' OR get_user_role() = 'admin'
);

-- Operacional: Pode inserir
CREATE POLICY "operacional_insert_schedules"
ON schedules
FOR INSERT
TO authenticated
WITH CHECK (
    get_user_role() = 'operacional' OR get_user_role() = 'admin'
);

-- Operacional: Pode atualizar
CREATE POLICY "operacional_update_schedules"
ON schedules
FOR UPDATE
TO authenticated
USING (
    get_user_role() = 'operacional' OR get_user_role() = 'admin'
)
WITH CHECK (
    get_user_role() = 'operacional' OR get_user_role() = 'admin'
);

-- Público: Sem acesso
-- (Sem política = sem acesso)

-- ============================================
-- 8. POLÍTICAS PARA TABELA 'access_requests'
-- ============================================

-- Admin: Acesso total
CREATE POLICY "admin_full_access_access_requests"
ON access_requests
FOR ALL
TO authenticated
USING (
    get_user_role() = 'admin'
)
WITH CHECK (
    get_user_role() = 'admin'
);

-- Operacional: Apenas leitura
CREATE POLICY "operacional_read_access_requests"
ON access_requests
FOR SELECT
TO authenticated
USING (
    get_user_role() = 'operacional' OR get_user_role() = 'admin'
);

-- Público: Pode inserir (para solicitar acesso)
CREATE POLICY "public_insert_access_requests"
ON access_requests
FOR INSERT
TO anon
WITH CHECK (true);

-- ============================================
-- 9. POLÍTICAS PARA TABELA 'logs'
-- ============================================

-- Admin: Acesso total
CREATE POLICY "admin_full_access_logs"
ON logs
FOR ALL
TO authenticated
USING (
    get_user_role() = 'admin'
)
WITH CHECK (
    get_user_role() = 'admin'
);

-- Operacional: Apenas leitura
CREATE POLICY "operacional_read_logs"
ON logs
FOR SELECT
TO authenticated
USING (
    get_user_role() = 'operacional' OR get_user_role() = 'admin'
);

-- Público: Pode inserir (para logs de acesso)
CREATE POLICY "public_insert_logs"
ON logs
FOR INSERT
TO anon
WITH CHECK (true);

-- ============================================
-- 10. POLÍTICAS PARA TABELA 'authorizers'
-- ============================================

-- Admin: Acesso total
CREATE POLICY "admin_full_access_authorizers"
ON authorizers
FOR ALL
TO authenticated
USING (
    get_user_role() = 'admin'
)
WITH CHECK (
    get_user_role() = 'admin'
);

-- Operacional: Pode ler
CREATE POLICY "operacional_select_authorizers"
ON authorizers
FOR SELECT
TO authenticated
USING (
    get_user_role() = 'operacional' OR get_user_role() = 'admin'
);

-- Operacional: Pode inserir
CREATE POLICY "operacional_insert_authorizers"
ON authorizers
FOR INSERT
TO authenticated
WITH CHECK (
    get_user_role() = 'operacional' OR get_user_role() = 'admin'
);

-- Operacional: Pode atualizar
CREATE POLICY "operacional_update_authorizers"
ON authorizers
FOR UPDATE
TO authenticated
USING (
    get_user_role() = 'operacional' OR get_user_role() = 'admin'
)
WITH CHECK (
    get_user_role() = 'operacional' OR get_user_role() = 'admin'
);

-- Público: Sem acesso
-- (Sem política = sem acesso)

-- ============================================
-- 11. POLÍTICAS PARA TABELA 'materials'
-- ============================================

-- Admin: Acesso total
CREATE POLICY "admin_full_access_materials"
ON materials
FOR ALL
TO authenticated
USING (
    get_user_role() = 'admin'
)
WITH CHECK (
    get_user_role() = 'admin'
);

-- Operacional: Pode ler
CREATE POLICY "operacional_select_materials"
ON materials
FOR SELECT
TO authenticated
USING (
    get_user_role() = 'operacional' OR get_user_role() = 'admin'
);

-- Operacional: Pode inserir
CREATE POLICY "operacional_insert_materials"
ON materials
FOR INSERT
TO authenticated
WITH CHECK (
    get_user_role() = 'operacional' OR get_user_role() = 'admin'
);

-- Operacional: Pode atualizar
CREATE POLICY "operacional_update_materials"
ON materials
FOR UPDATE
TO authenticated
USING (
    get_user_role() = 'operacional' OR get_user_role() = 'admin'
)
WITH CHECK (
    get_user_role() = 'operacional' OR get_user_role() = 'admin'
);

-- Público: Sem acesso
-- (Sem política = sem acesso)

-- ============================================
-- 12. GARANTIR QUE TABELA USERS TEM COLUNA ROLE
-- ============================================

-- Adiciona coluna role se não existir
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'users' AND column_name = 'role'
    ) THEN
        ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'operacional';
        -- Atualiza usuários existentes sem role
        UPDATE users SET role = 'operacional' WHERE role IS NULL;
        -- Adiciona constraint
        ALTER TABLE users ADD CONSTRAINT users_role_check 
            CHECK (role IN ('admin', 'operacional'));
    END IF;
END $$;

-- ============================================
-- NOTAS IMPORTANTES
-- ============================================
-- 
-- 1. A função get_user_role() obtém o email do JWT token
-- 2. Para funcionar com autenticação, configure o Supabase Auth
-- 3. Para acesso público (anon), use a service_role key com cuidado
-- 4. As políticas são aplicadas automaticamente pelo Supabase
-- 5. Teste todas as políticas após aplicar esta migration
-- 
-- ============================================

