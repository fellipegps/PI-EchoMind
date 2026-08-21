# EchoMind - Totem de IA Institucional

EchoMind e um sistema multiusuario de totem interativo com IA para instituicoes de ensino e empresas. O backend usa FastAPI, SQLAlchemy, Alembic, pgvector, LangChain, Groq e FastEmbed para responder perguntas com base na base de conhecimento cadastrada por cada usuario/empresa.

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
GROQ_LLM_MODEL=openai/gpt-oss-120b

EMBED_MODEL=BAAI/bge-small-en-v1.5
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

## Importacao De Conhecimento Por JSON

Para carregar rapidamente uma base inicial de conhecimento sem voltar ao `seed.py`, use o importador JSON:

```bash
cd echomind-backend
python scripts/import_knowledge.py --tenant-id UUID_DO_USUARIO --file templates/unievangelica.json
```

O `tenant_id` e o `id` do usuario no Supabase Auth. Voce encontra esse valor no painel do Supabase em:

```text
Authentication > Users > selecione o usuario > User UID
```

O template de exemplo fica em:

```text
echomind-backend/templates/unievangelica.json
```

Ele contem configuracao institucional e 30 FAQs para uma instituicao de ensino superior, com ate 4 perguntas marcadas para aparecerem no totem publico.

O importador:

- atualiza ou cria a configuracao do tenant;
- cria FAQs que ainda nao existem;
- atualiza FAQs existentes quando a pergunta ja existe no mesmo tenant;
- evita duplicacao por pergunta;
- respeita o limite de 4 FAQs exibidas no totem;
- reindexa FAQs e eventos no RAG automaticamente.

Se quiser apenas validar a gravacao no banco sem reindexar o RAG, use:

```bash
python scripts/import_knowledge.py --tenant-id UUID_DO_USUARIO --file templates/unievangelica.json --skip-rag
```

Use `--skip-rag` somente para diagnostico. Para a IA responder com base nos dados importados, rode sem essa opcao.

## Autenticacao

As rotas administrativas usam Supabase Auth.

O cadastro pode ser feito pela tela `/registrar-conta`. O login e feito em `/login`.

O backend nao possui endpoint proprio de login/cadastro/senha. Essas operacoes sao feitas diretamente pelo Supabase Auth no frontend.

Para testar rotas protegidas no Swagger:

1. Entre pelo frontend em `/login`.
2. Use o access token da sessao Supabase.
3. Clique em `Authorize` no Swagger.
4. Informe o token no formato Bearer.

O backend valida esse `access_token` em `/auth/me` e nas rotas administrativas.

Nao existe mais tabela local `admin_users` para login. Usuarios administrativos sao usuarios do Supabase Auth.

## Rotas Principais

| Metodo | Rota | Descricao |
| --- | --- | --- |
| `GET` | `/auth/me` | Usuario autenticado e onboarding do tenant |
| `POST` | `/chat` | Chat publico com streaming e `tenant_id` |
| `GET/POST/PUT/DELETE` | `/faqs` | CRUD de FAQs autenticado |
| `GET` | `/faqs/totem` | FAQs publicas do totem por `tenant_id` |
| `GET/POST/PUT/DELETE` | `/events` | CRUD de eventos autenticado |
| `GET/PUT` | `/config` | Configuracoes autenticadas do tenant |
| `GET` | `/config/public` | Configuracao publica por `tenant_id` |
| `GET/DELETE` | `/unanswered` | Perguntas nao respondidas |
| `POST` | `/unanswered/{id}/convert` | Converter pergunta em FAQ |
| `GET` | `/dashboard` | Metricas do tenant |
| `POST` | `/feedback` | Feedback publico do totem |
| `GET` | `/health` | Health check |

## Fluxo Rapido De Teste

1. Rode `alembic upgrade head`.
2. Suba o backend em `http://localhost:8000`.
3. Suba o frontend em `http://localhost:3000`.
4. Crie uma conta em `/registrar-conta`.
5. Entre em `/login`.
6. Abra configuracoes e complete os dados da empresa.
7. Cadastre FAQs e marque ate 4 para aparecerem no totem.
8. Copie a URL do totem em configuracoes e teste o atendimento publico.

## CI Rapida E Baseline

O workflow `.github/workflows/ci.yml` executa em pull requests, pushes para
`main` e disparos manuais. Os checks estaveis sao `Backend / unit-api` e
`Frontend / quality-build`; execucoes anteriores da mesma branch ou PR sao
canceladas quando uma nova comeca.

A baseline do backend foi medida com Python 3.12.10, SQLite e mocks, sem Groq,
Supabase ou banco externo:

- 44 testes passando;
- 643 de 883 statements cobertos;
- 72,82% de cobertura real (73% no relatorio inteiro do coverage);
- gate fixado em 72%, o piso inteiro sem arredondamento para cima.

Para reproduzir o gate do backend:

```bash
cd echomind-backend
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -m "not integration and not e2e" --cov=app --cov-report=term-missing --cov-report=xml:coverage.xml --cov-fail-under=72
```

Para reproduzir o gate do frontend com Node.js 20+ e Corepack:

```bash
cd echomind-front
corepack pnpm install --frozen-lockfile
corepack pnpm lint
corepack pnpm exec tsc --noEmit
corepack pnpm build
```

O build de CI recebe somente placeholders publicos para
`NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SUPABASE_URL` e
`NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`. Nenhum segredo de producao e usado.
