-- Migration: Verificar Configuração do Storage
-- Script de verificação para confirmar que o bucket e políticas estão configurados

-- ============================================
-- VERIFICAÇÃO DO BUCKET
-- ============================================
SELECT 
    id,
    name,
    public,
    file_size_limit,
    allowed_mime_types,
    created_at
FROM storage.buckets
WHERE id = 'face-photos';

-- ============================================
-- VERIFICAÇÃO DAS POLÍTICAS RLS
-- ============================================
SELECT 
    schemaname,
    tablename,
    policyname,
    permissive,
    roles,
    cmd
FROM pg_policies
WHERE tablename = 'objects' 
AND schemaname = 'storage'
AND policyname IN (
    'Public Access',
    'Authenticated users can upload',
    'Authenticated users can update',
    'Admins can delete'
)
ORDER BY policyname;

-- ============================================
-- VERIFICAÇÃO DE RLS
-- ============================================
SELECT 
    tablename,
    rowsecurity
FROM pg_tables
WHERE schemaname = 'storage'
AND tablename = 'objects';

-- ============================================
-- RESUMO
-- ============================================
-- Se o bucket existe e as 4 políticas estão presentes, a configuração está correta!

