# Políticas RLS (Row Level Security) - Documentação

## Visão Geral

O sistema implementa **Row Level Security (RLS)** no Supabase para proteger dados sensíveis e controlar acesso baseado em roles de usuário.

## Roles do Sistema

### 1. **admin**
- **Acesso:** Total (SELECT, INSERT, UPDATE, DELETE)
- **Uso:** Administradores do sistema
- **Permissões:**
  - Acesso completo a todas as tabelas
  - Pode gerenciar usuários
  - Pode modificar blocklist
  - Pode ver todos os logs

### 2. **operacional** (Editor)
- **Acesso:** Leitura e escrita (SELECT, INSERT, UPDATE)
- **Uso:** Operadores do sistema
- **Permissões:**
  - Pode ler e editar registros de acesso
  - Pode cadastrar pessoas
  - Pode criar agendamentos
  - **NÃO pode:**
    - Deletar registros
    - Gerenciar usuários
    - Modificar blocklist

### 3. **public** (Anônimo)
- **Acesso:** Limitado (apenas operações específicas)
- **Uso:** Página pública de reconhecimento facial
- **Permissões:**
  - Pode ler pessoas ativas (apenas campos necessários para reconhecimento)
  - Pode ler blocklist (para verificar bloqueios)
  - Pode inserir registros de acesso (após reconhecimento)
  - Pode inserir logs (de acesso)
  - **NÃO pode:**
    - Ver dados sensíveis (CPF completo, etc.)
    - Editar qualquer dado
    - Ver usuários
    - Ver logs completos

## Tabelas e Políticas

### `people` (Cadastro de Pessoas)

| Role | SELECT | INSERT | UPDATE | DELETE |
|------|--------|--------|--------|--------|
| admin | ✅ Completo | ✅ | ✅ | ✅ |
| operacional | ✅ Completo | ✅ | ✅ | ❌ |
| public | ✅ Limitado* | ❌ | ❌ | ❌ |

*Público vê apenas: `id`, `name`, `face_encoding`, `face_photo_url`, `is_active` (apenas pessoas ativas)

### `access_records` (Registros de Acesso)

| Role | SELECT | INSERT | UPDATE | DELETE |
|------|--------|--------|--------|--------|
| admin | ✅ | ✅ | ✅ | ✅ |
| operacional | ✅ | ✅ | ✅ | ❌ |
| public | ❌ | ✅ | ❌ | ❌ |

*Público pode apenas inserir (registrar acesso após reconhecimento)

### `users` (Usuários)

| Role | SELECT | INSERT | UPDATE | DELETE |
|------|--------|--------|--------|--------|
| admin | ✅ | ✅ | ✅ | ✅ |
| operacional | ✅ | ❌ | ❌ | ❌ |
| public | ❌ | ❌ | ❌ | ❌ |

### `blocklist` (Lista de Bloqueios)

| Role | SELECT | INSERT | UPDATE | DELETE |
|------|--------|--------|--------|--------|
| admin | ✅ | ✅ | ✅ | ✅ |
| operacional | ✅ | ❌ | ❌ | ❌ |
| public | ✅ | ❌ | ❌ | ❌ |

*Público pode ler para verificar se pessoa está bloqueada

### `schedules` (Agendamentos)

| Role | SELECT | INSERT | UPDATE | DELETE |
|------|--------|--------|--------|--------|
| admin | ✅ | ✅ | ✅ | ✅ |
| operacional | ✅ | ✅ | ✅ | ❌ |
| public | ❌ | ❌ | ❌ | ❌ |

### `access_requests` (Solicitações de Acesso)

| Role | SELECT | INSERT | UPDATE | DELETE |
|------|--------|--------|--------|--------|
| admin | ✅ | ✅ | ✅ | ✅ |
| operacional | ✅ | ❌ | ❌ | ❌ |
| public | ❌ | ✅ | ❌ | ❌ |

*Público pode inserir (solicitar acesso ao sistema)

### `logs` (Logs do Sistema)

| Role | SELECT | INSERT | UPDATE | DELETE |
|------|--------|--------|--------|--------|
| admin | ✅ | ✅ | ✅ | ✅ |
| operacional | ✅ | ❌ | ❌ | ❌ |
| public | ❌ | ✅ | ❌ | ❌ |

*Público pode inserir (logar ações de acesso)

### `authorizers` (Aprovadores)

| Role | SELECT | INSERT | UPDATE | DELETE |
|------|--------|--------|--------|--------|
| admin | ✅ | ✅ | ✅ | ✅ |
| operacional | ✅ | ✅ | ✅ | ❌ |
| public | ❌ | ❌ | ❌ | ❌ |

### `materials` (Materiais)

| Role | SELECT | INSERT | UPDATE | DELETE |
|------|--------|--------|--------|--------|
| admin | ✅ | ✅ | ✅ | ✅ |
| operacional | ✅ | ✅ | ✅ | ❌ |
| public | ❌ | ❌ | ❌ | ❌ |

## Implementação Técnica

### Função Helper: `get_user_role()`

A função SQL `get_user_role()` obtém o role do usuário atual:

```sql
CREATE OR REPLACE FUNCTION get_user_role()
RETURNS TEXT AS $$
DECLARE
    user_email TEXT;
    user_role TEXT;
BEGIN
    user_email := current_setting('request.jwt.claims', true)::json->>'email';
    
    IF user_email IS NULL THEN
        RETURN 'public';
    END IF;
    
    SELECT role INTO user_role
    FROM users
    WHERE user_email = LOWER(user_email)
    LIMIT 1;
    
    RETURN COALESCE(user_role, 'public');
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

### Clientes Supabase

#### 1. `SupabaseOperations` (Autenticado)
- Usa chave `service_role` ou chave autenticada
- Respeita RLS baseado no JWT token do usuário
- Usado em páginas que requerem login

#### 2. `SupabasePublicClient` (Público)
- Usa chave `anon` (pública)
- Respeita RLS para usuários anônimos
- Usado na página pública de reconhecimento facial
- Operações limitadas às políticas públicas

## Aplicando as Políticas

### Via SQL Editor do Supabase

1. Acesse o SQL Editor no painel do Supabase
2. Execute o arquivo `docs/migrations/001_rls_policies.sql`
3. Execute o arquivo `docs/migrations/002_verify_rls.sql` para verificar
4. Confirme que todas as políticas foram criadas corretamente

### Via Supabase CLI

```bash
supabase db push
```

## Verificação

Após aplicar as políticas, teste:

1. **Como admin:**
   - Deve conseguir todas as operações
   - Verificar logs completos
   - Gerenciar usuários

2. **Como operacional:**
   - Deve conseguir ler e editar
   - Não deve conseguir deletar
   - Não deve conseguir gerenciar usuários

3. **Como público (anon):**
   - Deve conseguir apenas operações permitidas
   - Não deve ver dados sensíveis
   - Deve conseguir inserir registros de acesso

## Segurança

### Boas Práticas

1. **Nunca exponha a chave `service_role`** no frontend
2. **Use chave `anon`** para acesso público
3. **Configure JWT** corretamente para autenticação
4. **Teste todas as políticas** após mudanças
5. **Monitore logs** de acesso não autorizado

### Dados Sensíveis Protegidos

- CPF completo (público não vê)
- Dados de usuários (apenas admin)
- Logs completos (apenas admin e operacional)
- Histórico completo de acessos (apenas autenticados)

## Troubleshooting

### Erro: "permission denied for table"
- Verifique se RLS está habilitado
- Verifique se a política existe
- Verifique se o role do usuário está correto

### Erro: "function get_user_role() does not exist"
- Execute a migration completa
- Verifique se a função foi criada

### Acesso público não funciona
- Verifique se está usando `SupabasePublicClient`
- Verifique se está usando chave `anon`
- Verifique se as políticas públicas existem

## Atualizações Futuras

Para adicionar novas políticas:

1. Crie uma nova migration SQL
2. Defina políticas para a nova tabela
3. Teste com todos os roles
4. Documente as mudanças

