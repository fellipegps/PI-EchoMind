# EchoMind - Totem de IA Institucional

EchoMind e um sistema de totem interativo com IA para instituicoes de ensino e empresas. O backend usa FastAPI, SQLAlchemy, pgvector, LangChain, Groq, FastEmbed e gTTS para responder perguntas com base na base de conhecimento cadastrada.

O banco de dados e o Supabase Auth sao usados via Supabase:

- PostgreSQL hospedado no Supabase por `DATABASE_URL`
- Login, cadastro e recuperacao de senha via Supabase Auth
- O frontend guarda o `access_token` do Supabase no `localStorage`
- O backend valida esse token nas rotas administrativas protegidas

## Estrutura do projeto

```text
PI-EchoMind-auth/
├── echomind-backend/   # API FastAPI
└── echomind-front/     # Frontend Next.js
```

## Como rodar localmente

### Pre-requisitos

- Python 3.12
- Node.js 20+
- Corepack/pnpm
- Conta no Supabase com projeto criado
- Chave de API do Groq em console.groq.com

> O backend deve ser executado com Python 3.12. Se sua maquina tiver outra
> versao do Python instalada, como Python 3.14, instale o Python 3.12 em
> paralelo e crie o ambiente virtual usando `py -3.12`.

### Configuracao

1. Entrar na pasta do backend:

```bash
cd echomind-backend
```

2. Criar um ambiente virtual com Python 3.12:

No Windows:

```powershell
py -3.12 -m venv .venv
```

No Linux/macOS:

```bash
python3.12 -m venv .venv
```

3. Ativar o ambiente virtual:

No Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

No Windows CMD:

```cmd
.venv\Scripts\activate.bat
```

No Linux/macOS:

```bash
source .venv/bin/activate
```

Depois de ativar, confira se a versao correta esta em uso:

```bash
python --version
```

O retorno deve ser `Python 3.12.x`.

4. Instalar dependencias:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

5. Copiar e preencher o `.env`:

```bash
cp .env.example .env
```

Preencha:

- `DATABASE_URL` com a connection string do banco PostgreSQL do Supabase
- `SUPABASE_URL` com a URL do projeto Supabase
- `SUPABASE_SECRET_KEY` com a Secret key do Supabase (`sb_secret_...`)
- `GROQ_API_KEY` com sua chave Groq

Exemplo:

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

> Nunca exponha `SUPABASE_SECRET_KEY` no frontend. Ela deve ficar somente no backend.

6. Rodar as migrations:

```bash
alembic upgrade head
```

7. Popular o banco com dados iniciais e reindexar o pgvector:

```bash
python seed.py
```

O seed cria configuracoes, FAQs, eventos e indices do RAG. Ele nao cria mais usuario administrador local; os usuarios agora sao criados no Supabase Auth.

8. Iniciar a API:

```bash
uvicorn app.main:app --reload
```

Por padrao, a API fica em [http://localhost:8000](http://localhost:8000).

### Endpoints

Acesse [http://localhost:8000/docs](http://localhost:8000/docs) para a documentacao interativa.

## Variaveis de ambiente principais

| Variavel | Descricao |
| --- | --- |
| `DATABASE_URL` | URI PostgreSQL do Supabase. O backend adiciona `sslmode=require` automaticamente quando ausente. |
| `SUPABASE_URL` | URL do projeto Supabase. |
| `SUPABASE_SECRET_KEY` | Secret key do Supabase (`sb_secret_...`) usada somente no backend para operacoes administrativas de auth. |
| `GROQ_API_KEY` | Chave da API Groq. |
| `GROQ_LLM_MODEL` | Modelo Groq usado no chat. |
| `EMBED_MODEL` | Modelo local de embeddings. |
| `EMBEDDING_DIM` | Dimensao do vetor no pgvector. |
| `SIMILARITY_THRESHOLD` | Distancia maxima aceita no retrieval. |
| `TOP_K_DOCS` | Quantidade de documentos recuperados por pergunta. |

## Autenticacao

As rotas administrativas usam Supabase Auth.

O login pode ser feito de duas formas:

- Pelo frontend em `/login`, usando `authApi.login`
- Pela API em `POST /auth/login`, enviando JSON:

```json
{
  "email": "usuario@email.com",
  "password": "sua-senha"
}
```

O backend retorna o `access_token` do Supabase:

```json
{
  "access_token": "...",
  "token_type": "bearer",
  "email": "usuario@email.com"
}
```

O cadastro usa Supabase Auth em `POST /auth/register` ou pela tela `/registrar-conta`.

A recuperacao de senha usa Supabase Auth em `POST /auth/reset-password` ou pela tela `/recuperar-senha`.

Nao existem mais credenciais padrao criadas pelo `seed.py`. Para acessar o painel, crie uma conta em `/registrar-conta` ou pelo painel do Supabase em Authentication > Users.

## Rotas principais

| Metodo | Rota | Descricao |
| --- | --- | --- |
| `POST` | `/auth/login` | Login administrativo |
| `POST` | `/auth/register` | Cadastro de usuario no Supabase Auth |
| `POST` | `/auth/reset-password` | Envio de email de recuperacao de senha |
| `GET` | `/auth/me` | Usuario autenticado |
| `POST` | `/chat` | Chat com streaming |
| `GET/POST/PUT/DELETE` | `/faqs` | CRUD de FAQs |
| `GET/POST/PUT/DELETE` | `/events` | CRUD de eventos |
| `GET/PUT` | `/config` | Configuracoes institucionais |
| `GET/DELETE` | `/unanswered` | Perguntas nao respondidas |
| `POST` | `/unanswered/{id}/convert` | Converter pergunta em FAQ |
| `POST` | `/unanswered/{id}/learn` | Ensinar resposta ao RAG |
| `GET` | `/dashboard` | Metricas e estatisticas |
| `GET` | `/tts` | Sintese de voz MP3 |
| `GET` | `/health` | Health check |
| `GET` | `/metrics` | Metricas internas |

## Frontend

```bash
cd echomind-front
corepack pnpm install
copy .env.local.example .env.local
corepack pnpm dev
```

O frontend espera a API em `http://localhost:8000` por padrao.

Preencha `echomind-front/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=https://[SEU_PROJECT_REF].supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
```

Depois acesse [http://localhost:3000/login](http://localhost:3000/login).

## Teste rapido da integracao Auth

1. Suba o backend em `http://localhost:8000`.
2. Suba o frontend em `http://localhost:3000`.
3. Acesse `/registrar-conta` e crie um usuario.
4. Acesse `/login` e entre com esse usuario.
5. Ao entrar no dashboard, o frontend tera salvo o token do Supabase.
6. Crie ou edite uma FAQ/evento para confirmar que as rotas protegidas aceitam o token.

Tambem e possivel testar pelo Swagger:

1. Acesse [http://localhost:8000/docs](http://localhost:8000/docs).
2. Execute `POST /auth/login` com email e senha de um usuario do Supabase Auth.
3. Copie o `access_token`.
4. Clique em `Authorize` e informe `Bearer SEU_ACCESS_TOKEN`.
5. Execute `GET /auth/me` ou alguma rota protegida.

## Ordem Recomendada Apos Atualizar Embeddings

```bash
cd echomind-backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
alembic upgrade head
python seed.py
uvicorn app.main:app --reload
```

Em outro terminal:

```bash
cd echomind-front
corepack pnpm dev
```
