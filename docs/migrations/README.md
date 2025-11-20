# Migrations do Banco de Dados

Esta pasta contém as migrations SQL para o banco de dados Supabase.

## Aplicar Migrations

### Via SQL Editor do Supabase

1. Acesse o painel do Supabase
2. Vá em **SQL Editor**
3. Clique em **New Query**
4. Cole o conteúdo do arquivo de migration
5. Execute a query

### Via Supabase CLI

```bash
supabase db push
```

## Migrations Disponíveis

### 001_rls_policies.sql

Aplica políticas de Row Level Security (RLS) em todas as tabelas do sistema.

**O que faz:**
- Habilita RLS em todas as tabelas
- Cria função `get_user_role()` para obter role do usuário
- Cria políticas por role (admin, operacional, public)
- Adiciona coluna `role` na tabela `users` se não existir

**Importante:**
- Execute esta migration ANTES de usar o sistema em produção
- Teste todas as políticas após aplicar
- Verifique se a função `get_user_role()` está funcionando corretamente

**Ordem de execução:**
1. Execute primeiro as migrations de criação de tabelas (se houver)
2. Execute esta migration de RLS
3. Configure os usuários com roles apropriados

### 002_verify_rls.sql

Script de verificação para confirmar que todas as políticas RLS foram aplicadas corretamente.

**O que faz:**
- Verifica se RLS está habilitado em todas as tabelas
- Lista todas as políticas criadas
- Verifica se a função `get_user_role()` existe
- Verifica se a coluna `role` existe na tabela `users`
- Conta o total de políticas por tabela

**Quando usar:**
- Após executar `001_rls_policies.sql`
- Para diagnosticar problemas de permissão
- Para auditoria de segurança

### 003_add_admin_user.sql

Adiciona o usuário administrador inicial ao sistema.

**O que faz:**
- Adiciona ou atualiza o usuário com email `bboycrysforever@gmail.com`
- Define o role como `'admin'`
- Usa `ON CONFLICT` para atualizar se o usuário já existir

**Quando usar:**
- Após executar `001_rls_policies.sql`
- Para criar o primeiro administrador
- Para atualizar o role de um usuário existente para admin

**Personalização:**
- Edite o email no script antes de executar se necessário
- O email deve corresponder ao email usado no login Google OIDC

### 004_create_storage_bucket.sql

Cria políticas RLS para o bucket de storage de fotos faciais.

**Status:** ✅ Bucket criado e políticas aplicadas via MCP Supabase

**O que faz:**
- Habilita RLS na tabela `storage.objects`
- Cria política de leitura pública (public)
- Cria política de inserção para usuários autenticados
- Cria política de atualização para usuários autenticados
- Cria política de deleção apenas para admins

**Políticas criadas:**
- `Public Access` - Leitura pública de fotos
- `Authenticated users can upload` - Inserção para autenticados
- `Authenticated users can update` - Atualização para autenticados
- `Admins can delete` - Deleção apenas para admins

**Quando usar:**
- Após criar o bucket manualmente no painel (se necessário)
- Para aplicar políticas de segurança no storage

### 005_verify_storage_setup.sql

Script de verificação para confirmar que o bucket e políticas de storage estão configurados corretamente.

**O que faz:**
- Verifica se o bucket `face-photos` existe
- Lista todas as políticas RLS do storage
- Verifica se RLS está habilitado
- Fornece um resumo da configuração

**Quando usar:**
- Após executar `004_create_storage_bucket.sql`
- Para diagnosticar problemas com upload de fotos
- Para auditoria de segurança do storage

## Verificação

Após aplicar as migrations, execute o script de verificação:

```sql
-- Execute o arquivo 002_verify_rls.sql
```

Ou verifique manualmente:

1. **RLS está habilitado:**
   ```sql
   SELECT tablename, rowsecurity 
   FROM pg_tables 
   WHERE schemaname = 'public';
   ```

2. **Políticas foram criadas:**
   ```sql
   SELECT schemaname, tablename, policyname 
   FROM pg_policies 
   WHERE schemaname = 'public';
   ```

3. **Função get_user_role existe:**
   ```sql
   SELECT proname FROM pg_proc WHERE proname = 'get_user_role';
   ```

## Troubleshooting

### Erro: "permission denied"
- Verifique se RLS está habilitado
- Verifique se as políticas foram criadas
- Verifique se o role do usuário está correto

### Erro: "function get_user_role() does not exist"
- Execute a migration novamente
- Verifique se a função foi criada no schema correto

### Acesso público não funciona
- Verifique se a política `public_insert_access_records` existe
- Verifique se está usando a chave `anon` (não `service_role`)
- Verifique se RLS está habilitado na tabela `access_records`

