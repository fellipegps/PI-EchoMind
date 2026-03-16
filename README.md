# EchoMind — Agente de IA para Totem Universitário

> Plataforma completa para gerenciar um assistente virtual inteligente instalado em totens físicos de instituições de ensino. Administradores cadastram FAQs e eventos; o totem responde perguntas de alunos por voz ou toque, usando busca vetorial com pgvector e IA generativa via Ollama/OpenAI.

---

## Índice

1. [Visão Geral da Arquitetura](#arquitetura)
2. [Pré-requisitos](#pré-requisitos)
3. [Configuração do Backend](#backend)
4. [Configuração do Frontend](#frontend)
5. [Rodando o Projeto Completo](#rodando)
6. [Variáveis de Ambiente](#variáveis-de-ambiente)
7. [Estrutura de Pastas](#estrutura-de-pastas)
8. [Fluxo de Autenticação](#autenticação)
9. [Rotas da API](#rotas-da-api)
10. [Funcionalidades](#funcionalidades)
11. [Solução de Problemas](#troubleshooting)

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                        ECHOMIND                             │
│                                                             │
│  ┌──────────────┐          ┌──────────────────────────┐    │
│  │   FRONTEND   │          │        BACKEND           │    │
│  │  Next.js 16  │◄────────►│      FastAPI + Python    │    │
│  │  React 19    │  HTTP/   │                          │    │
│  │  TypeScript  │  REST    │  ┌────────────────────┐  │    │
│  │  Tailwind    │          │  │  PostgreSQL+pgvector│  │    │
│  │  shadcn/ui   │          │  │  (busca semântica) │  │    │
│  └──────┬───────┘          │  └────────────────────┘  │    │
│         │                  │                           │    │
│  ┌──────┴───────┐          │  ┌────────────────────┐  │    │
│  │  /dashboard  │          │  │   Ollama (LLM local)│  │    │
│  │  /base-de-   │          │  │   ou OpenAI API    │  │    │
│  │  conhecimento│          │  └────────────────────┘  │    │
│  │  /nao-       │          │                          │    │
│  │  respondidas │          └──────────────────────────┘    │
│  │  /agente     │                                          │
│  │  (totem      │                                          │
│  │   público)   │                                          │
│  └──────────────┘                                          │
└─────────────────────────────────────────────────────────────┘
```

**Fluxo principal:**
1. Admin faz login → recebe JWT → acessa painel
2. Admin cadastra FAQs e eventos via painel
3. Totem público faz perguntas → backend busca FAQ por similaridade vetorial (pgvector) → IA humaniza a resposta (Ollama) → resposta exibida no totem
4. Perguntas sem resposta são salvas no banco → Admin visualiza no painel e converte em FAQ

---

## Pré-requisitos

| Ferramenta | Versão mínima | Observação |
|---|---|---|
| **Docker** | 24+ | Para rodar banco + API |
| **Docker Compose** | 2.x | Incluído no Docker Desktop |
| **Node.js** | 18+ | Para o frontend |
| **pnpm** | 8+ | Gerenciador de pacotes do frontend |
| **Ollama** *(opcional)* | latest | IA local. Alternativa: usar OpenAI |

### Instalando pnpm (se necessário)
```bash
npm install -g pnpm
```

### Instalando Ollama (opcional, para IA local)
```bash
# macOS / Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Após instalar, baixar o modelo
ollama pull llama3.2
```

---

## Backend

O backend é uma API FastAPI com PostgreSQL (pgvector) rodando via Docker.

### 1. Entrar na pasta

```bash
cd backend
```

### 2. Criar o arquivo `.env`

Copie o arquivo de exemplo:

```bash
cp .env.example .env
```

Edite o `.env` com suas configurações (veja a seção [Variáveis de Ambiente](#variáveis-de-ambiente) para detalhes):

```bash
# Exemplo mínimo para rodar localmente:
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/totem_db
SECRET_KEY=minha_chave_super_secreta_troque_isso_em_producao
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

OPENAI_API_KEY=sk-...        # Necessário para embeddings
ELEVENLABS_API_KEY=...       # Necessário para voz (opcional)
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM

POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=totem_db
```

> ⚠️ **Importante:** A `OPENAI_API_KEY` é necessária para gerar os embeddings vetoriais das FAQs. Sem ela, a busca semântica não funcionará.

### 3. Subir os containers

```bash
docker compose up -d
```

Isso irá:
- Subir o PostgreSQL com extensão `pgvector`
- Buildar e subir a API FastAPI na porta `8000`
- O banco sobe com healthcheck — a API só inicia quando o banco estiver pronto

### 4. Verificar se está rodando

```bash
# Ver logs
docker compose logs -f api

# Testar o health check
curl http://localhost:8000/health
# Esperado: {"status":"ok","service":"EchoMind API"}
```

### 5. Acessar a documentação interativa da API

Abra no navegador:
- **Swagger UI:** http://localhost:8000/docs
- **Redoc:** http://localhost:8000/redoc

### 6. Rodar as migrations (se necessário)

O banco é criado automaticamente no startup via `init_db()`. Se precisar rodar migrations manualmente com Alembic:

```bash
docker compose exec api alembic upgrade head
```

### 7. Popular com dados iniciais (seed)

```bash
docker compose exec api python seed.py
```

---

## Frontend

O frontend é um app Next.js 16 com React 19.

### 1. Entrar na pasta

```bash
cd frontend
```

### 2. Criar o arquivo `.env.local`

```bash
# Já vem criado com o valor padrão:
cat .env.local
# NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

Se o backend rodar em outra porta ou host, edite esse arquivo.

### 3. Instalar dependências

```bash
pnpm install
```

### 4. Rodar em desenvolvimento

```bash
pnpm dev
```

O frontend estará disponível em: **http://localhost:3000**

### 5. Build para produção

```bash
pnpm build
pnpm start
```

---

## Rodando o Projeto Completo

### Passo a passo completo (primeira vez)

```bash
# 1. Clone / extraia o projeto
cd echomind-project

# 2. Configurar e subir o backend
cd backend
cp .env.example .env
# Edite o .env com suas chaves de API
nano .env

docker compose up -d --build

# Aguardar ~30 segundos para o banco e API iniciarem
# Verificar:
curl http://localhost:8000/health

# 3. Em outro terminal, subir o frontend
cd ../frontend
pnpm install
pnpm dev

# 4. Abrir no navegador
# Admin: http://localhost:3000/login
# Totem: http://localhost:3000/agente-publico
```

### Sequência de inicialização após a primeira vez

```bash
# Backend (terminal 1)
cd backend && docker compose up -d

# Frontend (terminal 2)
cd frontend && pnpm dev
```

### Parar tudo

```bash
# Parar frontend: Ctrl+C no terminal

# Parar backend
cd backend && docker compose down

# Parar e remover volumes (apaga o banco!)
cd backend && docker compose down -v
```

---

## Variáveis de Ambiente

### Backend (`backend/.env`)

| Variável | Obrigatória | Padrão | Descrição |
|---|---|---|---|
| `DATABASE_URL` | ✅ | — | URL de conexão com o PostgreSQL. Use `postgresql+asyncpg://` |
| `SECRET_KEY` | ✅ | — | Chave secreta para assinar os JWTs. Use uma string longa e aleatória |
| `ALGORITHM` | ❌ | `HS256` | Algoritmo JWT |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | ❌ | `1440` | Expiração do token (1440 min = 24h) |
| `OPENAI_API_KEY` | ✅* | — | Chave da OpenAI para embeddings e geração de texto |
| `ELEVENLABS_API_KEY` | ❌ | — | Chave ElevenLabs para síntese de voz |
| `ELEVENLABS_VOICE_ID` | ❌ | `21m00Tcm4TlvDq8ikWAM` | ID da voz no ElevenLabs |
| `POSTGRES_USER` | ✅ | — | Usuário do PostgreSQL (usado pelo Docker) |
| `POSTGRES_PASSWORD` | ✅ | — | Senha do PostgreSQL |
| `POSTGRES_DB` | ✅ | — | Nome do banco de dados |

> *`OPENAI_API_KEY` é necessária para o funcionamento da busca semântica e respostas da IA.

**Gerar uma SECRET_KEY segura:**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### Frontend (`frontend/.env.local`)

| Variável | Obrigatória | Padrão | Descrição |
|---|---|---|---|
| `NEXT_PUBLIC_API_URL` | ✅ | `http://localhost:8000/api/v1` | URL base da API do backend |

---

## Estrutura de Pastas

```
echomind-project/
│
├── README.md                        ← Este arquivo
│
├── backend/                         ← API FastAPI
│   ├── .env.example                 ← Template de variáveis de ambiente
│   ├── .env                         ← Suas variáveis (NÃO commitar)
│   ├── docker-compose.yml           ← PostgreSQL + API
│   ├── Dockerfile                   ← Build da API
│   ├── requirements.txt             ← Dependências Python
│   ├── alembic.ini                  ← Config do Alembic (migrations)
│   ├── seed.py                      ← Script para popular dados iniciais
│   │
│   ├── alembic/                     ← Migrations do banco
│   │   └── env.py
│   │
│   └── app/
│       ├── main.py                  ← Entry point FastAPI + CORS
│       ├── api/v1/
│       │   ├── auth.py              ← POST /auth/login, /auth/register
│       │   ├── faq.py               ← CRUD FAQs + POST /faqs/ask
│       │   ├── events.py            ← CRUD Eventos
│       │   ├── metrics.py           ← GET /metrics/overview
│       │   ├── unanswered.py        ← GET /unanswered + PATCH /resolve
│       │   ├── documents.py         ← Upload de documentos
│       │   └── voice.py             ← Síntese/reconhecimento de voz
│       ├── core/
│       │   ├── config.py            ← Settings (pydantic-settings)
│       │   ├── database.py          ← Conexão async com PostgreSQL
│       │   ├── deps.py              ← get_current_admin (JWT guard)
│       │   └── security.py          ← Hash de senha + criar JWT
│       ├── models/                  ← Modelos SQLAlchemy
│       ├── schemas/                 ← Schemas Pydantic (request/response)
│       ├── services/                ← Lógica de negócio
│       └── utils/                   ← file_handler, vector_search
│
└── frontend/                        ← App Next.js
    ├── .env.local                   ← Variáveis do frontend
    ├── package.json
    ├── next.config.ts
    │
    ├── app/
    │   ├── layout.tsx               ← Root layout (AuthProvider)
    │   ├── (auth)/                  ← Páginas públicas de auth
    │   │   ├── login/page.tsx       ← Login integrado com API
    │   │   └── registrar-conta/     ← Registro integrado com API
    │   ├── (admin)/                 ← Área protegida (requer JWT)
    │   │   ├── layout.tsx           ← Layout com ProtectedRoute
    │   │   ├── dashboard/           ← Métricas reais via /metrics/overview
    │   │   ├── base-de-conhecimento/← CRUD de FAQs e Eventos
    │   │   ├── nao-respondidas/     ← Perguntas sem resposta + resolver
    │   │   ├── agente/              ← Chat de teste com a IA
    │   │   └── configuracoes/
    │   └── (totem público)/
    │       └── agente-publico/      ← Interface pública do totem
    │
    ├── components/
    │   ├── app-sidebar.tsx          ← Sidebar com logout real
    │   ├── protected-route.tsx      ← Guard de rota por JWT
    │   └── ui/                      ← Componentes shadcn/ui
    │
    ├── contexts/
    │   └── auth-context.tsx         ← Context global de autenticação
    │
    └── lib/
        └── api.ts                   ← Cliente HTTP centralizado
```

---

## Autenticação

O sistema usa **JWT Bearer Token** com armazenamento em `localStorage`.

### Fluxo completo

```
┌──────────┐         ┌──────────────┐       ┌──────────────┐
│ Usuário  │         │   Frontend   │       │   Backend    │
└──────────┘         └──────────────┘       └──────────────┘
     │                      │                      │
     │  POST /login         │                      │
     │─────────────────────►│  POST /auth/login    │
     │                      │─────────────────────►│
     │                      │  {access_token: ...} │
     │                      │◄─────────────────────│
     │                      │                      │
     │                      │  localStorage.set()  │
     │                      │  token salvo         │
     │                      │                      │
     │  Navega para /dash   │                      │
     │─────────────────────►│                      │
     │                      │  GET /metrics/overview│
     │                      │  Authorization: Bearer│
     │                      │─────────────────────►│
     │                      │  {total_interactions}│
     │                      │◄─────────────────────│
     │  Dados do dashboard  │                      │
     │◄─────────────────────│                      │
```

### Proteção de rotas

- Toda a área `/admin` usa o componente `<ProtectedRoute>` que verifica o token no `localStorage`
- Se o token expirou ou não existe, o usuário é redirecionado para `/login`
- Se o backend retornar `401`, o token é apagado automaticamente e o usuário é redirecionado

### Criar primeiro usuário admin

Via Swagger UI (http://localhost:8000/docs) ou curl:

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "minhasenha123"}'
```

---

## Rotas da API

### Autenticação
| Método | Rota | Auth | Descrição |
|---|---|---|---|
| POST | `/api/v1/auth/register` | ❌ | Cria novo admin |
| POST | `/api/v1/auth/login` | ❌ | Login, retorna JWT |

### FAQs
| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/api/v1/faqs` | ❌ | Lista todas as FAQs |
| POST | `/api/v1/faqs` | ✅ | Cria FAQ (gera embedding) |
| PUT | `/api/v1/faqs/{id}` | ✅ | Atualiza FAQ |
| DELETE | `/api/v1/faqs/{id}` | ✅ | Remove FAQ |
| POST | `/api/v1/faqs/ask` | ❌ | **Endpoint principal do totem** — busca por similaridade + IA |

### Eventos
| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/api/v1/events` | ❌ | Lista todos os eventos |
| GET | `/api/v1/events/upcoming` | ❌ | Apenas eventos futuros |
| GET | `/api/v1/events/{id}` | ❌ | Evento por ID |
| POST | `/api/v1/events` | ✅ | Cria evento |
| PUT | `/api/v1/events/{id}` | ✅ | Atualiza evento |
| DELETE | `/api/v1/events/{id}` | ✅ | Remove evento |

### Métricas
| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/api/v1/metrics/overview` | ✅ | Total de interações, FAQs, eventos, gráficos |

### Perguntas Não Respondidas
| Método | Rota | Auth | Descrição |
|---|---|---|---|
| GET | `/api/v1/unanswered` | ✅ | Lista perguntas sem resposta |
| PATCH | `/api/v1/unanswered/{id}/resolve` | ✅ | Marca como resolvida |

---

## Funcionalidades

### Painel Administrativo

**Dashboard**
- Total de interações com o agente
- Quantidade de perguntas sem resposta
- Total de FAQs e Eventos cadastrados
- Gráfico de interações por dia
- Ranking das FAQs mais consultadas

**Base de Conhecimento**
- Criar, editar e excluir FAQs com categorias personalizadas
- Criar, editar e excluir eventos com data, tipo e descrição
- Busca em tempo real por pergunta/categoria

**Perguntas Não Respondidas**
- Listagem de perguntas feitas no totem que não tiveram correspondência no banco vetorial
- Converter pergunta em FAQ diretamente do painel (preencher resposta → salva como FAQ + resolve a pergunta)
- Opção de ignorar/resolver sem criar FAQ

**Testar Agente**
- Interface de chat para testar o comportamento da IA antes de disponibilizar no totem
- Indicador visual de status de conexão com o backend
- Respostas em tempo real via `POST /faqs/ask`

### Totem Público (`/agente-publico`)

- Interface fullscreen sem autenticação
- Botão de microfone com reconhecimento de voz via Web Speech API (Chrome)
- FAQs recentes carregadas dinamicamente do banco
- Próximos eventos exibidos em tempo real
- Ao fazer uma pergunta (por voz ou clique nas FAQs), exibe a resposta da IA
- Tela de resposta com botão "Voltar ao início"

---

## Troubleshooting

### Backend não sobe

```bash
# Ver logs detalhados
docker compose logs api --tail=50

# Erro comum: banco ainda não está pronto
# Solução: aguardar ~30s e tentar novamente
docker compose restart api
```

### Erro "OPENAI_API_KEY not set"

Verifique se o arquivo `.env` está na pasta `backend/` e contém a chave correta:

```bash
cat backend/.env | grep OPENAI
```

### Frontend não conecta no backend (CORS ou network)

Verifique se o backend está rodando:
```bash
curl http://localhost:8000/health
```

Verifique se `NEXT_PUBLIC_API_URL` no `frontend/.env.local` aponta para o endereço correto.

### Erro 401 ao tentar acessar rotas protegidas

O token JWT pode ter expirado (padrão: 24h). Faça logout e login novamente no painel.

### Reconhecimento de voz não funciona no totem

A Web Speech API requer:
- **Navegador:** Chrome ou Edge (Firefox não suporta)
- **HTTPS ou localhost:** Não funciona em HTTP de outros hosts

### Erro ao criar FAQ ("embedding failed")

A geração de embeddings requer conexão com a OpenAI. Verifique:
1. `OPENAI_API_KEY` está correto no `.env`
2. Conexão com a internet disponível no container Docker

```bash
docker compose exec api python -c "from app.core.config import settings; print(settings.OPENAI_API_KEY[:10])"
```

### Resetar o banco de dados

```bash
cd backend
docker compose down -v   # Remove volumes (apaga todos os dados)
docker compose up -d     # Sobe novamente com banco limpo
```

---

## Tecnologias

| Camada | Tecnologia |
|---|---|
| Frontend | Next.js 16, React 19, TypeScript, Tailwind CSS v4, shadcn/ui |
| Backend | FastAPI, Python 3.11, SQLAlchemy async, Pydantic v2 |
| Banco de Dados | PostgreSQL 16 + pgvector (busca semântica) |
| Autenticação | JWT (python-jose) + bcrypt |
| IA — Embeddings | OpenAI `text-embedding-ada-002` |
| IA — Geração de texto | Ollama (LLaMA 3.2 local) / OpenAI GPT |
| IA — Voz | ElevenLabs (TTS) + faster-whisper (STT) |
| Containerização | Docker + Docker Compose |
| Gerenciador de pacotes | pnpm |

---

## Licença

Projeto desenvolvido para fins acadêmicos. Todos os direitos reservados.
