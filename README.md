# EchoMind — Totem de IA Institucional

EchoMind é um sistema de **totem interativo com IA** para instituições de ensino e empresas. Ele permite que qualquer pessoa faça perguntas por voz ou texto e receba respostas baseadas exclusivamente nas informações cadastradas pela equipe administrativa — sem invenções, sem improviso.

```
┌─────────────────────────────────────────────────────────────┐
│                        EchoMind                             │
│                                                             │
│  Totem Público          Painel Admin         API + IA       │
│  ┌──────────────┐      ┌─────────────┐      ┌───────────┐  │
│  │ Voz / Texto  │─────▶│ FAQs        │─────▶│  Groq     │  │
│  │ Perguntas    │      │ Eventos     │      │  llama-3.3│  │
│  │ Streaming    │◀─────│ Config      │◀─────│  70b      │  │
│  └──────────────┘      └─────────────┘      └─────┬─────┘  │
│                                                    │        │
│                                             ┌──────▼──────┐ │
│                                             │  pgvector   │ │
│                                             │  PostgreSQL │ │
│                                             └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## Estrutura do projeto

```
echomind/
├── echomind-backend-perf/   ← API FastAPI (Python)
│   ├── app/
│   │   ├── main.py          → rotas FastAPI
│   │   ├── rag_engine.py    → LangChain + Groq + pgvector
│   │   ├── database.py      → modelos ORM (SQLAlchemy)
│   │   ├── schemas.py       → contratos Pydantic v2
│   │   ├── crud.py          → operações de banco
│   │   └── middleware.py    → métricas de latência
│   ├── docker-compose.yml
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
│
└── echomind-front-perf/     ← Interface Next.js (TypeScript)
    ├── app/
    │   ├── (admin)/         → painel administrativo
    │   └── (totem público)/ → interface de voz + chat
    └── lib/api.ts           → todas as chamadas ao backend
```

---

## Pré-requisitos

| Ferramenta     | Versão   | Para que serve                           |
|----------------|----------|------------------------------------------|
| Docker         | 24+      | rodar Postgres + API                     |
| Docker Compose | v2       | orquestrar os containers                 |
| Node.js        | 18+      | rodar o frontend Next.js                 |
| pnpm           | 8+       | gerenciador de pacotes do frontend       |
| Conta Groq     | gratuita | gerar respostas da IA via API            |

> **Instale o pnpm:** `npm install -g pnpm`  
> **Crie sua conta Groq:** [console.groq.com](https://console.groq.com) → API Keys → Create key

---

## Variáveis de ambiente

### Backend (`echomind-backend-perf/.env`)

Copie o arquivo de exemplo e preencha os valores:

```bash
cd echomind-backend-perf
cp .env.example .env
```

| Variável               | Obrigatório | Descrição                                             |
|------------------------|-------------|-------------------------------------------------------|
| `GROQ_API_KEY`         | ✅ Sim       | Chave da API Groq — obtenha em console.groq.com       |
| `GROQ_LLM_MODEL`       | Não         | Modelo Groq (padrão: `llama-3.3-70b-specdec`)         |
| `POSTGRES_USER`        | Não         | Usuário do banco (padrão: `echomind`)                 |
| `POSTGRES_PASSWORD`    | ✅ Sim       | Senha do banco — **troque em produção**               |
| `POSTGRES_DB`          | Não         | Nome do banco (padrão: `echomind`)                    |
| `EMBED_MODEL`          | Não         | Modelo de embeddings sentence-transformers (padrão: `paraphrase-multilingual-mpnet-base-v2`) |
| `EMBEDDING_DIM`        | Não         | Dimensão do vetor — 768 para o modelo padrão          |
| `SIMILARITY_THRESHOLD` | Não         | Distância coseno máxima aceita (padrão: `0.70`)       |
| `TOP_K_DOCS`           | Não         | Documentos recuperados por pergunta (padrão: `3`)     |

**Exemplo de `.env` mínimo funcional:**
```env
GROQ_API_KEY=gsk_sua_chave_aqui
POSTGRES_PASSWORD=uma_senha_forte
```

### Frontend (`echomind-front-perf/.env.local`)

O arquivo já existe com o valor padrão para desenvolvimento local:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Altere apenas se o backend estiver em outro endereço.

---

## Rodando o Backend

### 1. Configure o `.env`

```bash
cd echomind-backend-perf
cp .env.example .env
# Edite .env e preencha GROQ_API_KEY e POSTGRES_PASSWORD
```

### 2. Suba os containers

```bash
docker compose up -d
```

Aguarde os serviços ficarem prontos:

```bash
docker compose ps
# NAME               STATUS
# echomind_db        Up (healthy)
# echomind_api       Up (healthy)
```

> O modelo de embeddings (`sentence-transformers`) é baixado automaticamente
> pelo container da API na primeira inicialização (~420 MB). Não é necessário
> nenhum servidor externo de embeddings.

### 3. Popule com dados iniciais (opcional)

```bash
docker compose exec api python seed.py
```

Cria FAQs e eventos de exemplo prontos para o chat responder.

### 4. Verifique que está funcionando

```bash
# Health check
curl http://localhost:8000/health
# → {"status":"ok","service":"EchoMind API"}

# Teste de chat com streaming
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Como faço minha matrícula?"}' \
  --no-buffer
```

### 5. Acesse a documentação interativa

👉 [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Rodando o Frontend

### 1. Instale as dependências

```bash
cd echomind-front-perf
pnpm install
```

### 2. Rode em modo desenvolvimento

```bash
pnpm dev
```

Acesse:
- **Painel Admin:** [http://localhost:3000/dashboard](http://localhost:3000/dashboard)
- **Totem Público:** [http://localhost:3000/agente-publico](http://localhost:3000/agente-publico)

### 3. Build para produção

```bash
pnpm build
pnpm start
```

---

## Como o streaming funciona

```
Frontend (Next.js)          Backend (FastAPI)         Groq API
      │                           │                       │
      │  POST /chat               │                       │
      │──────────────────────────▶│                       │
      │                           │  ChatGroq.astream()   │
      │                           │──────────────────────▶│
      │         token "Ol"        │◀── chunk ─────────────│
      │◀──────────────────────────│                       │
      │         token "á"         │◀── chunk ─────────────│
      │◀──────────────────────────│                       │
      │      stream encerrado     │◀── [DONE] ────────────│
      │◀──────────────────────────│                       │
```

---

## Telas e endpoints

| Tela                   | URL no frontend           | Endpoint no backend              |
|------------------------|---------------------------|----------------------------------|
| Dashboard              | `/dashboard`              | `GET /dashboard`                 |
| Testar Agente          | `/agente`                 | `POST /chat` (streaming)         |
| Base de Conhecimento   | `/base-de-conhecimento`   | `GET/POST/PUT/DELETE /faqs`      |
| Eventos                | `/base-de-conhecimento`   | `GET/POST/PUT/DELETE /events`    |
| Configurações          | `/configuracoes`          | `GET/PUT /config`                |
| Não Respondidas        | `/nao-respondidas`        | `GET /unanswered`                |
| Totem Público          | `/agente-publico`         | `POST /chat` + `GET /faqs/totem` |

---

## Comandos úteis

```bash
# ── Backend ──────────────────────────────────────────────────────────────────

# Ver logs em tempo real
docker compose -f echomind-backend-perf/docker-compose.yml logs api -f

# Reiniciar só a API (sem perder dados)
docker compose -f echomind-backend-perf/docker-compose.yml restart api

# Parar tudo sem apagar dados
docker compose -f echomind-backend-perf/docker-compose.yml stop

# Apagar tudo incluindo banco de dados
docker compose -f echomind-backend-perf/docker-compose.yml down -v

# ── Frontend ──────────────────────────────────────────────────────────────────

cd echomind-front-perf && pnpm install
pnpm dev
pnpm build && pnpm start
```

---

## Troubleshooting

**`RuntimeError: GROQ_API_KEY não definida`**
```bash
cat echomind-backend-perf/.env | grep GROQ_API_KEY
# Se estiver vazia, edite o .env e reinicie:
docker compose -f echomind-backend-perf/docker-compose.yml restart api
```

**IA responde "Não tenho informação" para tudo**
```bash
# Veja as distâncias nos logs — se estiverem acima do threshold, ajuste
docker compose -f echomind-backend-perf/docker-compose.yml logs api | grep "[RAG]"
# No .env: aumente SIMILARITY_THRESHOLD=0.80 e reinicie
```

**IA inventa informações**
```bash
# Diminua o threshold para aceitar apenas docs muito próximos da pergunta
# No .env: SIMILARITY_THRESHOLD=0.50
docker compose -f echomind-backend-perf/docker-compose.yml restart api
```

**Embeddings falham na primeira inicialização**
```bash
# O modelo sentence-transformers é baixado na primeira subida (~420 MB).
# Verifique se há conexão com a internet e espaço em disco, depois reinicie:
docker compose -f echomind-backend-perf/docker-compose.yml restart api
```

**Reconhecimento de voz não funciona no totem**  
O Web Speech API exige **HTTPS** ou `localhost`. Em produção, sirva o frontend com HTTPS (Caddy ou nginx + Let's Encrypt).
