# Prompt para Desenvolvimento React - Sistema de Controle de Acesso BAERI

## Visão Geral do Sistema

Sistema de controle de acesso de visitantes e veículos com reconhecimento facial, desenvolvido originalmente em Streamlit (Python) e que precisa ser reconstruído em React. O sistema gerencia entrada/saída de pessoas, verifica bloqueios, agendamentos, e utiliza reconhecimento facial para autenticação automática.

## Stack Tecnológica Atual (Backend)

- **Backend**: Python/Streamlit (será substituído por API)
- **Banco de Dados**: Supabase (PostgreSQL)
- **Storage**: Supabase Storage (para fotos faciais)
- **Autenticação**: Google OIDC (OpenID Connect)
- **Reconhecimento Facial**: DeepFace (Google FaceNet)
- **Segurança**: Row Level Security (RLS) com roles (admin, operacional, public)

## Stack Tecnológica Desejada (Frontend React)

- **Framework**: React (com TypeScript recomendado)
- **UI Library**: Material-UI, Ant Design, ou Tailwind CSS
- **Estado**: Redux, Zustand, ou Context API
- **Roteamento**: React Router
- **Autenticação**: Google OAuth 2.0 / OIDC
- **HTTP Client**: Axios ou Fetch API
- **Câmera**: react-webcam ou similar para captura de fotos
- **Imagens**: Para processamento e exibição de fotos

## Estrutura do Banco de Dados (Supabase)

### Tabelas Principais

1. **people** (Cadastro de Pessoas)
   - `id` (UUID, PK)
   - `name` (TEXT)
   - `cpf` (TEXT, único)
   - `company` (TEXT)
   - `face_encoding` (JSONB) - Embedding facial do DeepFace
   - `face_photo_url` (TEXT) - URL da foto no Supabase Storage
   - `is_active` (BOOLEAN)
   - `created_at`, `updated_at` (TIMESTAMP)

2. **access_records** (Registros de Acesso)
   - `id` (UUID, PK)
   - `person_id` (UUID, FK para people)
   - `name` (TEXT)
   - `cpf` (TEXT)
   - `placa` (TEXT) - Placa do veículo
   - `marca_carro` (TEXT)
   - `horario_entrada` (TIME)
   - `horario_saida` (TIME, nullable)
   - `data` (DATE)
   - `empresa` (TEXT)
   - `status_entrada` (TEXT) - "Autorizado", "Bloqueado", "Pendente"
   - `motivo_bloqueio` (TEXT, nullable)
   - `aprovador` (TEXT)
   - `data_primeiro_registro` (DATE, nullable)
   - `created_at`, `updated_at` (TIMESTAMP)

3. **users** (Usuários do Sistema)
   - `user_email` (TEXT, PK) - Email do Google
   - `role` (TEXT) - "admin" ou "operacional"
   - `created_at`, `updated_at` (TIMESTAMP)

4. **blocklist** (Lista de Bloqueios)
   - `id` (UUID, PK)
   - `type` (TEXT) - "Pessoa" ou "Empresa"
   - `value` (TEXT) - Nome da pessoa ou empresa
   - `reason` (TEXT) - Motivo do bloqueio
   - `blocked_by` (TEXT)
   - `created_at` (TIMESTAMP)

5. **schedules** (Agendamentos)
   - `id` (UUID, PK)
   - `visitor_name` (TEXT)
   - `visitor_cpf` (TEXT, nullable)
   - `company` (TEXT, nullable)
   - `scheduled_date` (DATE)
   - `scheduled_time` (TIME)
   - `authorized_by` (TEXT)
   - `status` (TEXT) - "Pendente", "Confirmado", "Cancelado"
   - `created_at`, `updated_at` (TIMESTAMP)

6. **access_requests** (Solicitações de Acesso ao Sistema)
   - `id` (UUID, PK)
   - `user_email` (TEXT)
   - `user_name` (TEXT)
   - `desired_role` (TEXT) - "admin" ou "operacional"
   - `department` (TEXT, nullable)
   - `justification` (TEXT)
   - `status` (TEXT) - "Pendente", "Aprovado", "Rejeitado"
   - `request_date` (TIMESTAMP)

7. **logs** (Logs do Sistema)
   - `id` (UUID, PK)
   - `user_email` (TEXT, nullable)
   - `action` (TEXT)
   - `details` (TEXT, nullable)
   - `timestamp` (TIMESTAMP)

8. **authorizers** (Aprovadores)
   - `id` (UUID, PK)
   - `name` (TEXT)

9. **materials** (Materiais)
   - `id` (UUID, PK)
   - `item` (TEXT)

## Políticas de Segurança (RLS)

### Roles e Permissões

1. **admin** (Administrador)
   - Acesso total: SELECT, INSERT, UPDATE, DELETE em todas as tabelas
   - Pode gerenciar usuários
   - Pode modificar blocklist
   - Pode ver todos os logs

2. **operacional** (Editor/Operador)
   - SELECT, INSERT, UPDATE (sem DELETE)
   - Pode ler e editar registros de acesso
   - Pode cadastrar pessoas
   - Pode criar agendamentos
   - **NÃO pode**: deletar registros, gerenciar usuários, modificar blocklist

3. **public** (Anônimo - Página Pública)
   - SELECT limitado em `people` (apenas campos: id, name, face_encoding, face_photo_url, is_active)
   - INSERT em `access_records` (para registrar acesso)
   - SELECT em `blocklist` (para verificar bloqueios)
   - INSERT em `logs` (para logar ações)
   - **NÃO pode**: ver dados sensíveis (CPF completo), editar qualquer dado, ver usuários

## Funcionalidades Principais

### 1. Página Pública de Acesso (Sem Login)
**URL**: `/public` ou `/access`

**Funcionalidades**:
- Captura de foto via câmera web
- Reconhecimento facial automático usando DeepFace
- Verificação de blocklist
- Registro automático de entrada (se liberado) ou bloqueio (se bloqueado)
- Interface minimalista e focada
- Mensagens claras: "ACESSO LIBERADO" ou "ACESSO NEGADO"

**Fluxo**:
1. Usuário acessa página pública
2. Permite acesso à câmera
3. Tira foto
4. Sistema processa com DeepFace
5. Busca pessoa no banco (compara embeddings faciais)
6. Verifica se está na blocklist
7. Se liberado: registra entrada automaticamente
8. Se bloqueado: mostra motivo e registra tentativa
9. Se não reconhecido: mostra mensagem orientativa

### 2. Controle de Acesso (Requer Login - Admin/Operacional)
**URL**: `/control` ou `/access-control`

**Funcionalidades**:
- Formulário de registro manual de entrada
- Campos: Nome, CPF, Placa, Marca do Carro, Empresa, Aprovador
- Verificação facial opcional no momento do registro
- Verificação automática de blocklist
- Verificação de briefing obrigatório (se não acessou há mais de 1 ano)
- Registro de saída
- Lista de registros do dia
- Filtros por data, status, nome

**Fluxo**:
1. Usuário preenche formulário
2. Sistema verifica se pessoa/empresa está bloqueada
3. Sistema verifica se precisa de briefing
4. (Opcional) Usuário pode fazer verificação facial
5. Registra entrada com status "Autorizado" ou "Bloqueado"
6. Mostra confirmação

### 3. Cadastro de Pessoas (Requer Login - Admin/Operacional)
**URL**: `/people` ou `/register`

**Funcionalidades**:
- Cadastro de nova pessoa com foto
- Upload de foto para reconhecimento facial
- Processamento automático com DeepFace (gera embedding)
- Upload da foto para Supabase Storage
- Busca de pessoa por foto
- Lista de pessoas cadastradas
- Edição de dados da pessoa

**Fluxo de Cadastro**:
1. Preenche: Nome, CPF (opcional), Empresa
2. Faz upload de foto
3. Sistema processa foto com DeepFace
4. Gera embedding facial
5. Faz upload da foto para storage
6. Salva pessoa no banco com embedding e URL da foto

**Fluxo de Busca**:
1. Faz upload de foto
2. Sistema processa e gera embedding
3. Compara com todos os embeddings no banco
4. Retorna pessoa mais similar (se distância < threshold)

### 4. Agendamento de Visitas (Requer Login - Admin/Operacional)
**URL**: `/schedule` ou `/appointments`

**Funcionalidades**:
- Criar agendamento
- Listar agendamentos
- Confirmar/Cancelar agendamento
- Verificar agendamentos do dia

### 5. Gerenciamento de Blocklist (Requer Login - Admin)
**URL**: `/blocklist` ou `/admin/blocklist`

**Funcionalidades**:
- Adicionar pessoa/empresa à blocklist
- Remover da blocklist
- Ver lista de bloqueios
- Solicitar liberação excepcional (para operacional)

### 6. Painel Administrativo (Requer Login - Admin)
**URL**: `/admin`

**Funcionalidades**:
- Gerenciar usuários (adicionar, remover, alterar role)
- Aprovar/rejeitar solicitações de acesso ao sistema
- Ver logs do sistema
- Gerenciar blocklist
- Ver estatísticas

### 7. Acesso por Foto (Requer Login - Admin/Operacional)
**URL**: `/face-access`

**Funcionalidades**:
- Upload de foto
- Reconhecimento automático
- Registro automático de entrada
- Opção de cadastro rápido se não reconhecido

## Requisitos de Interface

### Design
- Interface moderna e limpa
- Cores: Azul (#0066cc) para elementos principais, Verde para sucesso, Vermelho para erro/bloqueio
- Responsivo (mobile-first)
- Acessibilidade (WCAG 2.1)

### Componentes Principais

1. **Header/Navbar**
   - Logo/Nome do sistema
   - Menu de navegação (baseado no role)
   - Nome do usuário logado
   - Botão de logout

2. **Página Pública**
   - Título grande: "ACESSO BAERI"
   - Câmera web para captura
   - Botão "VERIFICAR ACESSO"
   - Mensagens grandes e claras (liberado/bloqueado)
   - Sem menu/sidebar

3. **Formulário de Controle de Acesso**
   - Campos: Nome*, CPF, Placa, Marca, Empresa, Aprovador*
   - Botão de verificação facial (opcional)
   - Botão "Registrar Entrada"
   - Lista de registros abaixo

4. **Cadastro de Pessoas**
   - Abas: "Novo Cadastro" e "Buscar Pessoa"
   - Upload de foto com preview
   - Validação de imagem (rosto detectado)
   - Lista de pessoas cadastradas

5. **Tabelas/Listas**
   - Paginação
   - Filtros
   - Ordenação
   - Exportação (opcional)

## Integrações Necessárias

### 1. Supabase Client
```javascript
// Configuração
const supabaseUrl = process.env.REACT_APP_SUPABASE_URL
const supabaseAnonKey = process.env.REACT_APP_SUPABASE_ANON_KEY
const supabaseServiceKey = process.env.REACT_APP_SUPABASE_SERVICE_KEY // Para admin
```

### 2. Google OAuth 2.0
- Login com Google
- Obter email do usuário
- Verificar role no banco (tabela users)

### 3. DeepFace API
- **IMPORTANTE**: DeepFace é Python, precisa de API backend
- Opções:
  - Criar API Python (FastAPI/Flask) que expõe DeepFace
  - Ou usar serviço de reconhecimento facial em nuvem
  - Ou processar no frontend com TensorFlow.js (mais complexo)

### 4. Supabase Storage
- Upload de fotos para bucket `face-photos`
- URLs públicas para exibição

## Fluxos de Dados

### Fluxo de Reconhecimento Facial (Página Pública)

```
1. Usuário tira foto → Blob/File
2. Frontend envia foto para API backend
3. Backend processa com DeepFace:
   - Gera embedding facial
   - Busca pessoas no banco (Supabase)
   - Compara embeddings (distância cosseno)
   - Retorna pessoa mais similar (se < threshold)
4. Backend verifica blocklist
5. Backend registra acesso (INSERT em access_records)
6. Frontend mostra resultado
```

### Fluxo de Cadastro de Pessoa

```
1. Usuário preenche dados + upload foto
2. Frontend envia para API backend
3. Backend processa foto com DeepFace:
   - Gera embedding
   - Valida qualidade da imagem
4. Backend faz upload da foto para Supabase Storage
5. Backend salva pessoa no banco:
   - INSERT em people (com embedding e photo_url)
6. Frontend mostra sucesso
```

### Fluxo de Autenticação

```
1. Usuário clica "Login com Google"
2. Redireciona para Google OAuth
3. Google retorna token
4. Frontend obtém email do token
5. Frontend busca role no Supabase (tabela users)
6. Frontend armazena role no estado/sessão
7. Frontend redireciona baseado no role
```

## Variáveis de Ambiente Necessárias

```env
REACT_APP_SUPABASE_URL=https://seu-projeto.supabase.co
REACT_APP_SUPABASE_ANON_KEY=sua-chave-anon
REACT_APP_SUPABASE_SERVICE_KEY=sua-chave-service (apenas para admin, não expor no frontend)
REACT_APP_GOOGLE_CLIENT_ID=seu-client-id
REACT_APP_API_URL=http://localhost:8000 (URL da API backend para DeepFace)
```

## Endpoints de API Backend Necessários (Python)

Se criar API backend para DeepFace:

1. `POST /api/recognize` - Reconhece pessoa na foto
   - Input: foto (multipart/form-data)
   - Output: { person: {...}, distance: 0.3, is_blocked: false }

2. `POST /api/process-face` - Processa foto e gera embedding
   - Input: foto
   - Output: { embedding: [...], photo_url: "..." }

3. `POST /api/compare-faces` - Compara duas fotos
   - Input: foto1, foto2
   - Output: { is_match: true, distance: 0.2 }

## Regras de Negócio Importantes

1. **Blocklist**: Se pessoa OU empresa está bloqueada, acesso negado
2. **Briefing**: Se pessoa não acessou há mais de 1 ano, precisa de briefing
3. **Reconhecimento Facial**: Threshold padrão 0.4 (distância cosseno), menor = mais rigoroso
4. **CPF**: Opcional, mas se fornecido deve ser válido e único
5. **Placa**: Formato brasileiro (ABC-1234 ou ABC1D23)
6. **Horários**: Timezone São Paulo (America/Sao_Paulo)
7. **Fotos**: Apenas JPG/PNG, mínimo 200x200px, apenas um rosto

## Componentes React Sugeridos

1. `PublicAccessPage` - Página pública de acesso
2. `AccessControlForm` - Formulário de controle de acesso
3. `PersonRegistration` - Cadastro de pessoas
4. `FaceVerification` - Componente de verificação facial
5. `CameraCapture` - Componente de captura de câmera
6. `AccessRecordsList` - Lista de registros
7. `BlocklistManager` - Gerenciamento de blocklist
8. `AdminPanel` - Painel administrativo
9. `ScheduleManager` - Gerenciamento de agendamentos
10. `LoginPage` - Página de login com Google

## Estados da Aplicação

### Estados Globais (Redux/Context)
- `user`: { email, role, name }
- `isAuthenticated`: boolean
- `accessRecords`: array
- `people`: array
- `blocklist`: array

### Estados Locais
- Formulários (dados do formulário atual)
- Upload de fotos (preview, processando)
- Câmera (streaming, capturado)

## Mensagens e Feedback

### Sucesso
- "✅ ACESSO LIBERADO" (verde, grande)
- "✅ Pessoa cadastrada com sucesso"
- "✅ Entrada registrada"

### Erro
- "🚫 ACESSO NEGADO" (vermelho, grande)
- "⚠️ Pessoa não reconhecida"
- "❌ Erro ao processar foto"

### Informação
- "💡 Dicas para melhor reconhecimento"
- "📊 Estatísticas do dia"

## Validações Necessárias

1. **CPF**: Formato e dígitos verificadores
2. **Placa**: Formato brasileiro
3. **Email**: Formato válido
4. **Foto**: Tipo (JPG/PNG), tamanho, rosto detectado
5. **Data**: Formato brasileiro (DD/MM/YYYY)
6. **Horário**: Formato (HH:MM)

## Performance e Otimizações

1. **Lazy Loading**: Carregar componentes sob demanda
2. **Caching**: Cache de pessoas, blocklist (TTL: 60s)
3. **Debounce**: Em campos de busca
4. **Pagination**: Listas grandes
5. **Image Optimization**: Compressão de fotos antes de upload
6. **Web Workers**: Para processamento pesado (se processar no frontend)

## Segurança no Frontend

1. **Não expor service_role key** no frontend
2. **Validar inputs** antes de enviar
3. **Sanitizar dados** exibidos
4. **HTTPS obrigatório** em produção
5. **CSP Headers** para prevenir XSS
6. **Rate Limiting** no backend

## Testes Sugeridos

1. Testes unitários de componentes
2. Testes de integração com Supabase
3. Testes E2E dos fluxos principais
4. Testes de acessibilidade
5. Testes de performance

## Prioridades de Implementação

### Fase 1 (MVP)
1. Autenticação Google OAuth
2. Página pública de acesso (sem reconhecimento facial ainda)
3. Controle de acesso básico (formulário manual)
4. Lista de registros

### Fase 2
1. Integração com API de reconhecimento facial
2. Cadastro de pessoas com foto
3. Verificação facial no acesso

### Fase 3
1. Agendamentos
2. Blocklist
3. Painel administrativo completo

## Notas Técnicas

- **DeepFace**: Requer backend Python, não pode rodar diretamente no React
- **Supabase RLS**: Funciona automaticamente, apenas use as chaves corretas (anon para público, service para admin)
- **Fotos**: Armazenar no Supabase Storage, não como base64 no banco
- **Embeddings**: Armazenar como JSON no banco (array de números)
- **Timezone**: Sempre usar timezone de São Paulo

## Exemplo de Estrutura de Pastas React

```
src/
├── components/
│   ├── common/
│   │   ├── Header.tsx
│   │   ├── Sidebar.tsx
│   │   └── CameraCapture.tsx
│   ├── access/
│   │   ├── PublicAccessPage.tsx
│   │   ├── AccessControlForm.tsx
│   │   └── AccessRecordsList.tsx
│   ├── people/
│   │   ├── PersonRegistration.tsx
│   │   └── PersonSearch.tsx
│   └── admin/
│       ├── AdminPanel.tsx
│       └── UserManagement.tsx
├── services/
│   ├── supabase.ts
│   ├── auth.ts
│   ├── api.ts (para chamadas ao backend DeepFace)
│   └── storage.ts
├── hooks/
│   ├── useAuth.ts
│   ├── useFaceRecognition.ts
│   └── useAccessRecords.ts
├── store/ (Redux/Zustand)
│   ├── authSlice.ts
│   └── accessSlice.ts
├── utils/
│   ├── validators.ts
│   ├── formatters.ts
│   └── constants.ts
└── types/
    └── index.ts
```

## Referências de Código

- Ver arquivos em `app/` para entender a lógica de negócio
- Ver `docs/migrations/001_rls_policies.sql` para entender as políticas de segurança
- Ver `app/face_recognition_utils.py` para entender o processamento facial
- Ver `app/supabase_db.py` para entender as operações no banco

---

**IMPORTANTE**: Este sistema é crítico para segurança. Garanta que:
- Todas as validações sejam feitas
- RLS esteja funcionando corretamente
- Dados sensíveis não sejam expostos
- Logs sejam mantidos para auditoria
- Testes sejam abrangentes antes de produção

