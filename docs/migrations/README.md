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

## Verificação

Após aplicar as migrations, verifique:

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

