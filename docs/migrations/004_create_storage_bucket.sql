-- Migration: Criar Políticas RLS para Bucket de Storage de Fotos Faciais
-- Aplica políticas de segurança no bucket 'face-photos'
--
-- IMPORTANTE: O bucket 'face-photos' DEVE ser criado manualmente no painel do Supabase
-- antes de aplicar esta migração.
--
-- Como criar o bucket:
-- 1. Acesse https://app.supabase.com
-- 2. Vá em Storage > New bucket
-- 3. Nome: face-photos
-- 4. Public: ✅ Sim
-- 5. File size limit: 5242880 (5 MB)
-- 6. Allowed MIME types: image/jpeg, image/png, image/jpg
-- 7. Clique em Create bucket
--
-- ============================================
-- NOTA SOBRE CRIAÇÃO DE BUCKET
-- ============================================
-- A criação de bucket via SQL requer permissões de service_role que não estão
-- disponíveis via MCP. Portanto, o bucket deve ser criado manualmente no painel.

-- ============================================
-- POLÍTICAS RLS PARA STORAGE
-- ============================================

-- Habilita RLS na tabela storage.objects (se ainda não estiver habilitado)
ALTER TABLE storage.objects ENABLE ROW LEVEL SECURITY;

-- Remove políticas antigas se existirem (para evitar conflitos)
DROP POLICY IF EXISTS "Public Access" ON storage.objects;
DROP POLICY IF EXISTS "Authenticated users can upload" ON storage.objects;
DROP POLICY IF EXISTS "Authenticated users can update" ON storage.objects;
DROP POLICY IF EXISTS "Admins can delete" ON storage.objects;

-- Política para leitura pública de fotos
CREATE POLICY "Public Access"
ON storage.objects
FOR SELECT
TO public
USING (bucket_id = 'face-photos');

-- Política para inserção (apenas usuários autenticados)
CREATE POLICY "Authenticated users can upload"
ON storage.objects
FOR INSERT
TO authenticated
WITH CHECK (bucket_id = 'face-photos');

-- Política para atualização (apenas usuários autenticados)
CREATE POLICY "Authenticated users can update"
ON storage.objects
FOR UPDATE
TO authenticated
USING (bucket_id = 'face-photos')
WITH CHECK (bucket_id = 'face-photos');

-- Política para deleção (apenas admins)
CREATE POLICY "Admins can delete"
ON storage.objects
FOR DELETE
TO authenticated
USING (
    bucket_id = 'face-photos' AND
    EXISTS (
        SELECT 1 FROM users 
        WHERE user_email = auth.email() 
        AND role = 'admin'
    )
);

-- ============================================
-- VERIFICAÇÃO
-- ============================================
-- Verifica se o bucket foi criado
SELECT 
    id,
    name,
    public,
    file_size_limit,
    allowed_mime_types
FROM storage.buckets
WHERE id = 'face-photos';

-- Lista as políticas criadas
SELECT 
    schemaname,
    tablename,
    policyname,
    permissive,
    roles,
    cmd,
    qual
FROM pg_policies
WHERE tablename = 'objects' 
AND schemaname = 'storage'
AND policyname IN (
    'Public Access',
    'Authenticated users can upload',
    'Authenticated users can update',
    'Admins can delete'
);

