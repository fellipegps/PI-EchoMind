# EchoMind - Totem de IA Institucional

EchoMind e um sistema multiusuario de totem interativo com IA para instituicoes de ensino e empresas. O backend usa FastAPI, SQLAlchemy, Alembic, pgvector, LangChain, Groq, FastEmbed e TTS para responder perguntas com base na base de conhecimento cadastrada por cada usuario/empresa.

O projeto usa Supabase para:

- PostgreSQL hospedado, acessado pelo backend via `DATABASE_URL`
- Login, cadastro e recuperacao de senha via Supabase Auth
- Validacao de sessoes administrativas no backend
- Chaves opacas atuais do Supabase: `sb_secret_...` no backend e `sb_publishable_...` no frontend

## Estrutura

```text
EchoMind-main/
|-- echomind-backend/   # API FastAPI
`-- echomind-front/     # Frontend Next.js
```

## Como Rodar Localmente

### Pre-requisitos

- Python 3.12
- Node.js 20+
- Corepack/pnpm
- Projeto criado no Supabase
- Chave da API Groq

> O backend deve ser executado com Python 3.12. Se sua maquina tiver outra versao instalada, crie o ambiente virtual com `py -3.12`.

### Backend

```bash
cd echomind-backend
```

No Windows:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

No Linux/macOS:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

Instale as dependencias:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Crie o `.env` do backend e preencha:

```env
DATABASE_URL=postgresql://postgres:[SUA_SENHA]@db.[SEU_PROJECT_REF].supabase.co:5432/postgres

SUPABASE_URL=https://[SEU_PROJECT_REF].supabase.co
SUPABASE_SECRET_KEY=sb_secret_...

GROQ_API_KEY=gsk_SUBSTITUA_PELA_SUA_CHAVE
GROQ_LLM_MODEL=llama-3.3-70b-versatile

EMBED_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_DIM=384
SIMILARITY_THRESHOLD=0.45
TOP_K_DOCS=3
```

Nunca exponha `SUPABASE_SECRET_KEY` no frontend.

Crie/atualize o schema do banco com Alembic:

```bash
alembic upgrade head
```

Inicie a API:

```bash
uvicorn app.main:app --reload
```

A API fica em [http://localhost:8000](http://localhost:8000).

### Frontend

```bash
cd echomind-front
corepack pnpm install
copy .env.local.example .env.local
```

Preencha `echomind-front/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=https://[SEU_PROJECT_REF].supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
```

Inicie o frontend:

```bash
corepack pnpm dev
```

Depois acesse [http://localhost:3000/login](http://localhost:3000/login).

## Banco De Dados

O schema do banco e gerenciado somente por migrations Alembic. O backend nao cria tabelas automaticamente no startup.

Fluxo correto apos alterar schema:

```bash
cd echomind-backend
alembic upgrade head
```

O arquivo `seed.py` foi removido. Dados iniciais globais nao sao mais usados, porque o projeto agora e multiusuario.

Cada usuario/empresa tem dados isolados por `tenant_id`. Quando um usuario autenticado acessa rotas administrativas, o backend executa o onboarding daquele tenant e cria uma configuracao inicial se ela ainda nao existir.

As FAQs, eventos e demais dados devem ser cadastrados pelo painel administrativo ou por endpoints autenticados.

## Autenticacao

As rotas administrativas usam Supabase Auth.

O cadastro pode ser feito pela tela `/registrar-conta`. O login e feito em `/login`.

Para testar pela API:

```json
{
  "email": "usuario@email.com",
  "password": "sua-senha"
}
```

O backend retorna ou valida o `access_token` emitido pelo Supabase:

```json
{
  "access_token": "...",
  "token_type": "bearer",
  "email": "usuario@email.com"
}
```

Nao existe mais tabela local `admin_users` para login. Usuarios administrativos sao usuarios do Supabase Auth.

## Totem Publico

O totem publico precisa receber o tenant na URL:

```text
http://localhost:3000/agente-publico?tenant=UUID_DO_USUARIO
```

Esse UUID e o `id` do usuario no Supabase Auth. O painel de configuracoes gera essa URL.

O totem mostra apenas FAQs marcadas para exibicao no totem daquele tenant.

## Rotas Principais

| Metodo | Rota | Descricao |
| --- | --- | --- |
| `POST` | `/auth/login` | Login administrativo |
| `POST` | `/auth/register` | Cadastro via Supabase Auth |
| `POST` | `/auth/reset-password` | Envio de email de recuperacao |
| `GET` | `/auth/me` | Usuario autenticado e onboarding do tenant |
| `POST` | `/chat` | Chat publico com streaming e `tenant_id` |
| `GET/POST/PUT/DELETE` | `/faqs` | CRUD de FAQs autenticado |
| `GET` | `/faqs/totem` | FAQs publicas do totem por `tenant_id` |
| `GET/POST/PUT/DELETE` | `/events` | CRUD de eventos autenticado |
| `GET/PUT` | `/config` | Configuracoes autenticadas do tenant |
| `GET` | `/config/public` | Configuracao publica por `tenant_id` |
| `GET/DELETE` | `/unanswered` | Perguntas nao respondidas |
| `POST` | `/unanswered/{id}/convert` | Converter pergunta em FAQ |
| `POST` | `/unanswered/{id}/learn` | Ensinar resposta ao RAG |
| `GET` | `/dashboard` | Metricas do tenant |
| `POST` | `/feedback` | Feedback publico do totem |
| `GET` | `/tts` | Sintese de voz |
| `GET` | `/health` | Health check |
| `GET` | `/metrics` | Metricas internas |

## RLS No Supabase

Como o frontend usa a FastAPI para acessar os dados do app, as tabelas principais nao precisam ser consultadas diretamente pela API publica do Supabase.

Mesmo assim, em producao e recomendado habilitar RLS nas tabelas do schema `public` para bloquear acesso direto via PostgREST/Publishable Key. O backend continua sendo a camada responsavel por validar usuario e filtrar por `tenant_id`.

## Fluxo Rapido De Teste

1. Rode `alembic upgrade head`.
2. Suba o backend em `http://localhost:8000`.
3. Suba o frontend em `http://localhost:3000`.
4. Crie uma conta em `/registrar-conta`.
5. Entre em `/login`.
6. Abra configuracoes e complete os dados da empresa.
7. Cadastre FAQs e marque ate 4 para aparecerem no totem.
8. Copie a URL do totem em configuracoes e teste o atendimento publico.
