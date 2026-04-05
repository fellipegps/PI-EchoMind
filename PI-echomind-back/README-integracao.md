# EchoMind — Integração: Base de Conhecimento

Este documento descreve **o que foi integrado**, **o que foi alterado** e como
**rodar e testar** a integração entre o frontend Next.js e o backend FastAPI
para a página **Base de Conhecimento** (FAQs e Eventos).

---

## O que foi feito

### Backend (`PI-echomind-back`)

| Arquivo | Alteração |
|---|---|
| `app/api/v1/faq.py` | Adicionadas rotas `GET /{faq_id}`, `PUT /{faq_id}` e `DELETE /{faq_id}` |
| `app/services/faq_service.py` | Adicionados métodos `get_by_id`, `update_faq` e `delete_faq` |
| `app/main.py` | Corrigido registro duplicado do router de events (estava incluso 3×) |

O router de **Events** já possuía CRUD completo — nenhuma alteração foi necessária.

### Frontend (`PI-echomind-front`)

| Arquivo | Alteração |
|---|---|
| `lib/api.ts` | **Novo** — cliente HTTP centralizado (`faqApi` e `eventApi`) |
| `app/(admin)/base-de-conhecimento/hooks/use-faqs.ts` | Reescrito — integrado com `faqApi` (lista, cria, atualiza, deleta) |
| `app/(admin)/base-de-conhecimento/hooks/use-events.ts` | Reescrito — integrado com `eventApi` (lista, cria, atualiza, deleta) |
| `app/(admin)/base-de-conhecimento/types.ts` | Adicionado campo `category` no tipo `Faq` |
| `app/(admin)/base-de-conhecimento/constants.ts` | Removidos dados mockados; mantidas apenas as constantes de UI |
| `.env.local.example` | **Novo** — variável `NEXT_PUBLIC_API_URL` |

Os componentes de UI (`faq-tab.tsx`, `event-tab.tsx`, `page.tsx`) **não foram
alterados** — toda a mudança ficou nos hooks e na camada de API.

---

## Pré-requisitos

- **Docker** e **Docker Compose** (para o banco)
- **Python 3.11+** com `pip` (para o backend)
- **Node.js 18+** e **pnpm** (para o frontend)
- **Ollama** rodando localmente em `http://localhost:11434` com o modelo
  `nomic-embed-text` para geração de embeddings

  ```bash
  ollama pull nomic-embed-text
  ```

---

## 1. Subindo o banco de dados (PostgreSQL + pgvector)

```bash
cd PI-echomind-back
docker compose up -d db
```

Aguarde alguns segundos até o container estar saudável:

```bash
docker compose ps
```

---

## 2. Configurando o backend

```bash
cd PI-echomind-back

# Copie e edite o arquivo de variáveis de ambiente
cp .env.example .env
```

Edite `.env` com suas chaves. Para rodar **apenas** a integração de
Base de Conhecimento, os campos obrigatórios são:

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/totem_db
SECRET_KEY=qualquer_string_secreta
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Ollama local (embeddings)
# Não precisa de chave — apenas certifique-se que o Ollama está rodando

# Estas chaves são usadas por outros módulos; podem ficar em branco por ora:
OPENAI_API_KEY=
ELEVENLABS_API_KEY=
ELEVENLABS_VOICE_ID=
```

> **Nota:** o `docker-compose.yml` sobe o banco mapeando a porta `5432`
> para o host, por isso `DATABASE_URL` usa `localhost` ao rodar fora do Docker.

---

## 3. Instalando dependências e rodando as migrações

```bash
cd PI-echomind-back

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt

# Cria as tabelas no banco via Alembic
alembic upgrade head
```

---

## 4. Iniciando o backend

```bash
# Ainda dentro de PI-echomind-back com o venv ativo
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Confirme que está no ar:

```bash
curl http://localhost:8000/health
# {"status":"ok","service":"EchoMind API"}
```

A documentação interativa fica em:
- Swagger UI → http://localhost:8000/docs
- Redoc → http://localhost:8000/redoc

---

## 5. Configurando e rodando o frontend

```bash
cd PI-echomind-front

# Crie o arquivo de variáveis de ambiente
cp .env.local.example .env.local
# O valor padrão já aponta para http://localhost:8000 — não precisa editar

# Instale as dependências
pnpm install

# Inicie o servidor de desenvolvimento
pnpm dev
```

Acesse http://localhost:3000 no navegador.

---

## 6. Testando a integração

### Via interface (fluxo manual)

1. Acesse http://localhost:3000 e navegue até **Base de Conhecimento**.
2. **FAQs**:
   - Clique em **Nova FAQ** → preencha pergunta e resposta → **Salvar**.
   - A FAQ deve aparecer na tabela sem precisar recarregar a página.
   - Clique no ícone de **lápis** para editar → altere um campo → **Salvar**.
   - Clique no ícone de **lixeira** para deletar — a FAQ deve desaparecer.
   - Use a **barra de busca** para filtrar por texto (busca local no cliente).
3. **Eventos**:
   - Clique em **Novo Evento** → preencha título, data, tipo e descrição → **Salvar**.
   - Edite e delete da mesma forma que as FAQs.

### Via Swagger (teste direto na API)

Acesse http://localhost:8000/docs e teste os endpoints:

**FAQs**

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/api/v1/faqs/` | Lista todas as FAQs |
| `POST` | `/api/v1/faqs/` | Cria uma FAQ |
| `GET` | `/api/v1/faqs/{faq_id}` | Busca por ID |
| `PUT` | `/api/v1/faqs/{faq_id}` | Atualiza campos |
| `DELETE` | `/api/v1/faqs/{faq_id}` | Remove |

Exemplo de payload para `POST /api/v1/faqs/`:

```json
{
  "question": "Qual o horário da biblioteca?",
  "answer": "A biblioteca funciona de segunda a sexta, das 8h às 22h.",
  "category": "Infraestrutura"
}
```

**Eventos**

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/api/v1/events/` | Lista todos os eventos |
| `GET` | `/api/v1/events/upcoming` | Lista eventos futuros |
| `POST` | `/api/v1/events/` | Cria um evento (requer token JWT) |
| `PUT` | `/api/v1/events/{event_id}` | Atualiza (requer token JWT) |
| `DELETE` | `/api/v1/events/{event_id}` | Remove (requer token JWT) |

> **Atenção:** as rotas de escrita de Eventos exigem autenticação JWT.
> Para obter um token, faça `POST /api/v1/auth/login` com as credenciais
> de um admin cadastrado, copie o `access_token` e clique em
> **Authorize** no topo do Swagger.

### Via curl (rápido)

```bash
# Criar uma FAQ
curl -X POST http://localhost:8000/api/v1/faqs/ \
  -H "Content-Type: application/json" \
  -d '{"question":"O RU serve café da manhã?","answer":"Sim, das 7h às 9h.","category":"Alimentação"}'

# Listar todas as FAQs
curl http://localhost:8000/api/v1/faqs/

# Listar todos os eventos
curl http://localhost:8000/api/v1/events/
```

---

## Estrutura dos arquivos integrados

```
PI-echomind-back/
├── app/
│   ├── api/v1/
│   │   ├── faq.py           ← CRUD completo (GET, POST, PUT, DELETE)
│   │   └── events.py        ← CRUD completo (sem alterações)
│   └── services/
│       └── faq_service.py   ← get_by_id, update_faq, delete_faq adicionados

PI-echomind-front/
├── lib/
│   └── api.ts               ← Cliente HTTP centralizado (NOVO)
└── app/(admin)/base-de-conhecimento/
    ├── hooks/
    │   ├── use-faqs.ts      ← Integrado com faqApi
    │   └── use-events.ts    ← Integrado com eventApi
    ├── types.ts             ← Campo category adicionado
    └── constants.ts         ← Dados mock removidos
```

---

## Observações e próximos passos

- **`show_on_totem`** ainda é controlado **localmente** no frontend — o
  backend não possui esse campo na tabela `faqs`. O próximo passo natural é
  adicionar a coluna via migration Alembic e criar um endpoint
  `PATCH /api/v1/faqs/{id}/totem` para persistir esse estado.

- **Autenticação nas FAQs:** atualmente as rotas de criação/edição/deleção de
  FAQs não exigem token JWT (ao contrário dos Eventos). Recomenda-se adicionar
  a dependência `get_current_admin` nas rotas de escrita assim que o fluxo de
  login do admin estiver integrado ao frontend.

- **Variável de ambiente:** em produção, altere `NEXT_PUBLIC_API_URL` no
  `.env.local` para apontar para a URL do backend em produção.

---

## Diagnóstico: FAQ sumia ao sair da página

Três causas combinadas foram corrigidas:

### 1. Modelos não importados antes do `create_all` (backend)
O `main.py` não importava os modelos SQLAlchemy antes de chamar `init_db()`.
O `Base.metadata.create_all` precisa "ver" os modelos para criar as tabelas.
Se as tabelas não existissem, todo `INSERT` retornava erro 500 — e a FAQ nunca era salva.

**Correção:** adicionado `import app.models` no topo do `main.py`.

### 2. Erro silencioso no frontend (frontend)
O hook anterior atualizava o estado React localmente **antes** de confirmar
que a API salvou. Se a API falhasse, o `toast.error` aparecia, mas a FAQ
ficava visível na tela — e desaparecia ao recarregar porque nunca foi ao banco.

**Correção:** o estado só é atualizado após confirmação da API. Se falhar,
nada muda na tela e o toast mostra a mensagem real do erro.

### 3. Mensagem de erro engolida (frontend)
O cliente HTTP original capturava o erro mas mostrava só `"Erro 500"` sem
o detalhe do FastAPI (`{ detail: "..." }`), dificultando o diagnóstico.

**Correção:** o `lib/api.ts` agora extrai e propaga a mensagem do campo
`detail` do corpo da resposta, e também detecta quando o backend está fora
do ar (erro de rede).
