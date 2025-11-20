# Migração para Supabase - Documentação

## Resumo das Mudanças

O sistema foi refatorado para usar **Supabase** como banco de dados ao invés do Google Sheets. Esta mudança prepara o sistema para implementação de **reconhecimento facial**, onde cada pessoa terá um cadastro único com ID próprio.

## Estrutura do Banco de Dados

### Tabelas Criadas

1. **people** - Cadastro de pessoas (preparado para reconhecimento facial)
   - `id` (UUID) - ID único da pessoa
   - `name` - Nome completo
   - `cpf` - CPF (único)
   - `face_encoding` - Encoding facial (para reconhecimento)
   - `face_photo_url` - URL da foto
   - `company` - Empresa
   - `created_at`, `updated_at` - Timestamps
   - `is_active` - Status ativo/inativo

2. **access_records** - Registros de acesso
   - `id` (UUID) - ID único do registro
   - `person_id` (FK) - Referência à tabela people
   - Campos de acesso (nome, CPF, placa, horários, etc.)

3. **users** - Usuários do sistema
4. **blocklist** - Lista de bloqueios
5. **schedules** - Agendamentos
6. **access_requests** - Solicitações de acesso
7. **logs** - Logs do sistema
8. **authorizers** - Aprovadores
9. **materials** - Materiais

## Configuração

### 1. Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto com:

```env
SUPABASE_URL=************************************************
SUPABASE_KEY=**********************************************

### 2. Para Streamlit Cloud

Adicione as variáveis no `secrets.toml`:

```toml
[supabase]
url = "************************"
key = "**********"
```

### 3. Instalar Dependências

```bash
pip install -r requirements.txt
```

A biblioteca `supabase==2.3.4` foi adicionada ao `requirements.txt`.

**Nota sobre DeepFace:**
- DeepFace usa TensorFlow, que pode ser pesado na primeira execução (baixa modelos)
- O modelo padrão é **Google FaceNet** (melhor precisão)
- Outros modelos disponíveis: VGG-Face, OpenFace, DeepFace, ArcFace, etc.
- Configure via variável de ambiente: `DEEPFACE_MODEL=Facenet` (padrão)

## Arquivos Modificados

1. **app/supabase_db.py** (NOVO) - Módulo para interação com Supabase
2. **app/data_operations.py** - Refatorado para usar Supabase
3. **auth/auth_utils.py** - Atualizado para carregar usuários do Supabase
4. **app/ui_interface.py** - Atualizado para usar SupabaseOperations
5. **app/admin_page.py** - Atualizado para usar SupabaseOperations
6. **app/face_recognition_utils.py** (NOVO) - Módulo de reconhecimento facial com DeepFace
7. **app/person_management.py** (NOVO) - Interface de cadastro de pessoas
8. **requirements.txt** - Adicionadas dependências supabase, deepface, tensorflow

## Funcionalidades Mantidas

Todas as funcionalidades existentes foram mantidas:
- Controle de acesso
- Agendamentos
- Blocklist
- Gerenciamento de usuários
- Logs
- Briefing de segurança

## Preparação para Reconhecimento Facial

A tabela `people` foi criada com campos específicos para reconhecimento facial:
- `face_encoding`: Armazenará o embedding facial (JSON)
- `face_photo_url`: URL da foto no Supabase Storage

Cada pessoa agora tem um ID único (UUID) que será usado para:
- Vincular múltiplos registros de acesso à mesma pessoa
- Armazenar dados de reconhecimento facial
- Manter histórico completo por pessoa

## ✅ Funcionalidades de Reconhecimento Facial Implementadas

1. ✅ **Módulo de reconhecimento facial** (`app/face_recognition_utils.py`)
   - Processamento de imagens com DeepFace
   - Geração de embeddings faciais (Google FaceNet)
   - Comparação de rostos com múltiplas métricas
   - Validação de imagens

2. ✅ **Bibliotecas integradas**
   - `deepface==0.0.79` (com suporte a Google FaceNet e outros modelos)
   - `opencv-python==4.8.1.78`
   - `Pillow==10.1.0`
   - `numpy==1.24.3`
   - `tensorflow==2.15.0`

3. ✅ **Interface de cadastro de pessoas** (`app/person_management.py`)
   - Cadastro com foto e embedding facial
   - Upload de fotos para Supabase Storage
   - Busca de pessoas por foto
   - Lista de pessoas cadastradas
   - Validação de imagens

4. ✅ **Verificação facial no acesso**
   - Verificação opcional no momento do registro de entrada
   - Verificação para evitar duplicação de cadastros
   - Integrado na interface de controle de acesso

### Configuração do Storage

1. **Criar bucket no Supabase:**
   - Acesse o painel do Supabase
   - Vá em Storage > Create bucket
   - Nome: `face-photos`
   - Public: `true` (para URLs públicas)
   - File size limit: 5MB
   - Allowed MIME types: `image/jpeg, image/png`

2. **Configurar políticas RLS:**
   - As políticas já estão na migration `create_storage_policies`
   - Permitem leitura pública e upload autenticado

### Como Usar

1. **Cadastrar uma pessoa com foto:**
   - Acesse "Cadastro de Pessoas" no menu
   - Preencha nome, CPF (opcional) e empresa
   - Envie uma foto do rosto
   - O sistema processará com DeepFace (FaceNet) e fará upload para o storage
   - O embedding facial será armazenado no banco

2. **Verificar rosto no momento do acesso:**
   - Ao registrar entrada, use o expander "Verificação Facial"
   - Envie uma foto da pessoa
   - O sistema verificará se corresponde a alguém cadastrado

3. **Buscar pessoa por foto:**
   - Na página "Cadastro de Pessoas", use a aba "Buscar Pessoa"
   - Envie uma foto
   - O sistema buscará correspondências no banco

4. **Acesso rápido por foto (NOVO):**
   - Acesse "Acesso por Foto" no menu
   - Envie uma foto da pessoa
   - O sistema reconhecerá automaticamente e registrará a entrada
   - Se não reconhecer, oferece opção de cadastro rápido

## Notas Importantes

- O sistema mantém compatibilidade com o formato de dados anterior (DataFrames com colunas renomeadas)
- As datas são convertidas automaticamente entre formatos (ISO para DD/MM/YYYY)
- A migração de dados do Google Sheets para Supabase deve ser feita manualmente se necessário
- Fotos são armazenadas no Supabase Storage, não como base64 no banco
- Embeddings faciais são armazenados como JSON no campo `face_encoding`

