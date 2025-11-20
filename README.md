# Sistema de Controle de Acesso e Briefing

Este sistema gerencia o controle de acesso de visitantes e veículos, utilizando **Supabase** como banco de dados. Inclui verificação de briefing obrigatório para visitantes que não acessaram o local há mais de um ano, autenticação via Google OIDC e **reconhecimento facial** com DeepFace.

## Requisitos do Sistema

- Python 3.8 ou superior
- Conexão com internet para acesso ao Supabase e autenticação Google
- Credenciais do Supabase (URL e chave API)
- Configuração OIDC para login Google (opcional)

## Instalação e Uso

1. Clone este repositório para seu computador.

2. Instale as dependências necessárias:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure as credenciais do Supabase:
   - Crie um arquivo `.env` na raiz do projeto
   - Adicione suas credenciais do Supabase:
   ```env
   SUPABASE_URL=https://seu-projeto.supabase.co
   SUPABASE_KEY=sua-chave-anon-key
   ```
   - **Para implantação no Streamlit Cloud:** Adicione as credenciais no `secrets.toml`:
   ```toml
   [supabase]
   url = "https://seu-projeto.supabase.co"
   key = "sua-chave-anon-key"
   ```

4. Configure o Storage do Supabase (para fotos):
   - Acesse o painel do Supabase
   - Vá em Storage > Create bucket
   - Nome: `face-photos`
   - Public: `true`
   - Consulte [docs/migration-supabase.md](./docs/migration-supabase.md) para mais detalhes

5. Configure as credenciais OIDC para login Google (opcional):
   - Crie um arquivo `.streamlit/secrets.toml` na raiz do projeto (se ainda não existir).
   - Adicione as configurações OIDC obtidas do Google Cloud Console na seção `[auth]`.
   - Gere um `cookie_secret` forte e aleatório.
   - Certifique-se de que o `redirect_uri` no `secrets.toml` e no Google Cloud Console corresponda ao endereço onde a aplicação será executada (localmente `http://localhost:8501/oauth2callback`, ou o URL do Streamlit Cloud).

   Exemplo de `.streamlit/secrets.toml`:
   ```toml
   [auth]
   client_id = "YOUR_CLIENT_ID"
   client_secret = "YOUR_CLIENT_SECRET"
   server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
   redirect_uri = "YOUR_REDIRECT_URI"
   cookie_secret = "YOUR_COOKIE_SECRET"

   # Para Streamlit Cloud, configure as credenciais do Google Sheets aqui
   [connections.gsheets]
   spreadsheet = "YOUR_SPREADSHEET_URL"
   type = "service_account"
   project_id = "YOUR_PROJECT_ID"
   private_key_id = "YOUR_PRIVATE_KEY_ID"
   private_key = "YOUR_PRIVATE_KEY"
   client_email = "YOUR_CLIENT_EMAIL"
   client_id = "YOUR_CLIENT_ID"
   auth_uri = "https://accounts.google.com/o/oauth2/auth"
   token_uri = "https://oauth2.googleapis.com/token"
   auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
   client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/YOUR_CLIENT_EMAIL"
   universe_domain = "googleapis.com"
   ```

6. Execute o sistema:
   ```bash
   streamlit run main.py
   ```
   - O sistema será iniciado no seu navegador padrão.

## Funcionalidades

- Controle de acesso de visitantes e veículos usando Supabase
- Autenticação de usuário via Google OIDC
- Verificação automática de briefing
- **Reconhecimento facial** com DeepFace (Google FaceNet)
- **Acesso rápido por foto** - Reconhecimento automático e registro de entrada
- **Acesso público** - Página pública sem login para reconhecimento facial automático
- Cadastro de pessoas com foto
- Busca de pessoas por foto
- Verificação facial no momento do acesso


## Estrutura de Arquivos

```
.
├── app/
│   ├── admin_page.py          # Interface administrativa
│   ├── data_operations.py      # Operações com dados (Supabase)
│   ├── supabase_db.py          # Classe SupabaseOperations
│   ├── face_recognition_utils.py # Módulo de reconhecimento facial
│   ├── person_management.py    # Interface de cadastro de pessoas
│   ├── ui_interface.py         # Interface do usuário
│   └── ...
├── auth/                       # Módulo de autenticação
│   ├── __init__.py
│   ├── auth_utils.py           # Funções auxiliares de autenticação
│   └── login_page.py           # Página de login
├── docs/                       # Documentação técnica
│   ├── README.md               # Índice da documentação
│   └── migration-supabase.md # Documentação da migração
├── .streamlit/                 # Configurações do Streamlit
│   └── secrets.toml            # Segredos e configurações
├── main.py                     # Ponto de entrada da aplicação
├── requirements.txt            # Dependências do projeto
└── README.md                   # Este arquivo
```

## Suporte

Para suporte técnico ou dúvidas, entre em contato com o desenvolvedor.

## Documentação Adicional

Para documentação técnica detalhada, consulte a pasta [docs](./docs/):
- [Migração para Supabase e Reconhecimento Facial](./docs/migration-supabase.md)

## Notas de Segurança

- Mantenha suas credenciais do Supabase e `cookie_secret` em segurança.
- Não compartilhe os arquivos do sistema com pessoas não autorizadas.
- Faça backup regular dos dados no Supabase.
- As fotos são armazenadas no Supabase Storage com políticas RLS configuradas.
