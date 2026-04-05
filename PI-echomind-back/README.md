# EchoMind API 🧠

Assistente de IA para totem universitário, desenvolvido como Projeto de Final de Curso (PCC). Permite que alunos tirem dúvidas via voz ou texto sobre informações da universidade, como localização de blocos, horários e eventos.

## Funcionalidades

- 🎙️ **Consulta por voz** — transcrição com Whisper local e resposta em áudio via Edge TTS
- 💬 **Consulta por texto** — busca semântica via RAG com embeddings e Ollama
- 📚 **Base de conhecimento** — gerenciamento de FAQs com categorias e status ativo/inativo
- 📅 **Eventos** — cadastro e listagem de eventos universitários
- 📄 **Upload de documentos** — PDFs indexados automaticamente com embeddings
- 🔒 **Painel admin** — autenticação JWT para rotas administrativas
- 📊 **Métricas** — total de interações, tempo médio de resposta
- ❓ **Perguntas não respondidas** — registro e resolução de perguntas sem contexto

## Stack

| Camada | Tecnologia |
|--------|-----------|
| Backend | FastAPI + Python 3.11 |
| Banco de dados | PostgreSQL 16 + pgvector |
| ORM | SQLAlchemy (Async) |
| IA / LLM | LangChain + Ollama (llama3.2) |
| Embeddings | Ollama (mxbai-embed-large) |
| STT | faster-whisper (Whisper base, local) |
| TTS | Edge TTS (pt-BR-FranciscaNeural) |
| Infraestrutura | Docker + Docker Compose |

## Pré-requisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [Ollama](https://ollama.com/) rodando na máquina com os modelos:

```bash
ollama pull llama3.2
ollama pull mxbai-embed-large
```

## Como Rodar

**1. Configurar variáveis de ambiente**

```bash
cp .env.example .env
```

Edite o `.env` com suas credenciais:

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/totem_db
SECRET_KEY=sua_chave_secreta_aqui
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

OPENAI_API_KEY=sk-xxxx        # opcional
ELEVENLABS_API_KEY=xxxx       # opcional
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM

POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=totem_db
```

**2. Subir os containers**

```bash
docker compose up --build -d
```

**3. Popular o banco com dados iniciais**

```bash
docker exec -it totem_api python seed.py
```

O seed cria:
- Admin padrão (`admin` / `admin123`)
- 8 FAQs de exemplo com embeddings
- 3 eventos de exemplo

**4. Acessar a documentação**

```
http://localhost:8000/docs
```

## Endpoints Principais

### Autenticação
| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/api/v1/auth/login` | Login (retorna JWT) |
| POST | `/api/v1/auth/register` | Registrar novo admin |

### FAQs
| Método | Rota | Auth | Descrição |
|--------|------|------|-----------|
| GET | `/api/v1/faqs/` | Público | Listar todos |
| POST | `/api/v1/faqs/ask` | Público | Perguntar à IA |
| POST | `/api/v1/faqs/` | 🔒 JWT | Criar FAQ |
| PUT | `/api/v1/faqs/{id}` | 🔒 JWT | Editar FAQ |
| DELETE | `/api/v1/faqs/{id}` | 🔒 JWT | Deletar FAQ |

### Eventos
| Método | Rota | Auth | Descrição |
|--------|------|------|-----------|
| GET | `/api/v1/events/` | Público | Listar todos |
| GET | `/api/v1/events/upcoming` | Público | Apenas eventos futuros |
| POST | `/api/v1/events/` | 🔒 JWT | Criar evento |
| PUT | `/api/v1/events/{id}` | 🔒 JWT | Editar evento |
| DELETE | `/api/v1/events/{id}` | 🔒 JWT | Deletar evento |

### Voz
| Método | Rota | Auth | Descrição |
|--------|------|------|-----------|
| POST | `/api/v1/voice-query/` | Público | Enviar áudio, receber resposta em texto e áudio |

### Admin
| Método | Rota | Auth | Descrição |
|--------|------|------|-----------|
| GET | `/api/v1/metrics/overview` | 🔒 JWT | Métricas gerais |
| GET | `/api/v1/unanswered/` | 🔒 JWT | Perguntas sem resposta |
| PATCH | `/api/v1/unanswered/{id}/resolve` | 🔒 JWT | Marcar como resolvida |
| POST | `/api/v1/documents/upload` | 🔒 JWT | Upload de PDF |

## Estrutura do Projeto

```
app/
├── api/v1/          # Routers (endpoints)
├── core/            # Configurações, banco, segurança, dependências
├── models/          # Modelos SQLAlchemy
├── schemas/         # Schemas Pydantic
├── services/        # Lógica de negócio
└── utils/           # Utilitários (busca vetorial, file handler)
seed.py              # Script de população inicial do banco
```

## Fluxo de Voz

```
Áudio → Whisper (STT local) → Embedding → RAG (pgvector) → Ollama (llama3.2) → Edge TTS → MP3
```

## Comandos Úteis

```bash
# Reiniciar do zero (apaga o banco)
docker compose down -v
docker compose up --build -d
docker exec -it totem_api python seed.py

# Ver logs em tempo real
docker logs -f totem_api

# Acessar o banco diretamente
docker exec -it totem_db psql -U postgres -d totem_db
```