# Configuração do Bucket de Storage para Fotos

## Problema

Se você receber o erro **"bucket not found"** ou **"Bucket 'face-photos' não encontrado"**, significa que o bucket de storage não foi criado no Supabase.

## Solução: Criar o Bucket

### Passo a Passo

1. **Acesse o Painel do Supabase**
   - Vá para: https://app.supabase.com
   - Faça login na sua conta
   - Selecione o projeto correto

2. **Navegue até Storage**
   - No menu lateral esquerdo, clique em **Storage**
   - Você verá a lista de buckets (pode estar vazia)

3. **Criar Novo Bucket**
   - Clique no botão **"New bucket"** ou **"Create bucket"**
   - Preencha os campos:
     - **Name:** `face-photos` (exatamente este nome, sem espaços)
     - **Public bucket:** ✅ **Marque esta opção** (importante!)
     - **File size limit:** `5242880` (5 MB) ou mais
     - **Allowed MIME types:** `image/jpeg, image/png, image/jpg` (opcional, mas recomendado)

4. **Criar o Bucket**
   - Clique em **"Create bucket"** ou **"Create"**

5. **Configurar Políticas RLS (Opcional mas Recomendado)**

   Após criar o bucket, configure as políticas de segurança:

   - Clique no bucket `face-photos`
   - Vá na aba **"Policies"**
   - Adicione políticas conforme necessário:

   **Política para leitura pública (se o bucket for público):**
   ```sql
   -- Permite leitura pública de fotos
   CREATE POLICY "Public Access"
   ON storage.objects
   FOR SELECT
   TO public
   USING (bucket_id = 'face-photos');
   ```

   **Política para inserção (apenas usuários autenticados):**
   ```sql
   -- Permite inserção apenas para usuários autenticados
   CREATE POLICY "Authenticated users can upload"
   ON storage.objects
   FOR INSERT
   TO authenticated
   WITH CHECK (bucket_id = 'face-photos');
   ```

   **Política para atualização (apenas usuários autenticados):**
   ```sql
   -- Permite atualização apenas para usuários autenticados
   CREATE POLICY "Authenticated users can update"
   ON storage.objects
   FOR UPDATE
   TO authenticated
   USING (bucket_id = 'face-photos');
   ```

   **Política para deleção (apenas admins):**
   ```sql
   -- Permite deleção apenas para admins
   CREATE POLICY "Admins can delete"
   ON storage.objects
   FOR DELETE
   TO authenticated
   USING (
     bucket_id = 'face-photos' AND
     (SELECT role FROM users WHERE user_email = auth.email()) = 'admin'
   );
   ```

## Verificação

Após criar o bucket, teste fazendo upload de uma foto:

1. Acesse a página "Cadastro de Pessoas"
2. Tente cadastrar uma pessoa com foto
3. Se o upload funcionar, o bucket está configurado corretamente

## Troubleshooting

### Erro: "Bucket not found"
- Verifique se o nome do bucket é exatamente `face-photos` (sem espaços, minúsculas)
- Verifique se você está no projeto correto do Supabase

### Erro: "Permission denied"
- Verifique se o bucket está marcado como **público** (se quiser acesso público)
- Verifique as políticas RLS do bucket
- Verifique se a chave de API tem permissões adequadas

### Erro: "File size limit exceeded"
- Aumente o limite de tamanho do arquivo nas configurações do bucket
- Ou comprima as imagens antes do upload

## Nota Importante

- O bucket **deve** ser público se você quiser que as fotos sejam acessíveis via URL pública
- Se preferir manter privado, ajuste as políticas RLS adequadamente
- O nome do bucket (`face-photos`) está hardcoded no código - se mudar, atualize também em `app/supabase_db.py`

