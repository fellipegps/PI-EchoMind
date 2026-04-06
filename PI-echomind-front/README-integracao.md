# EchoMind — Integração: Base de Conhecimento + Autenticação

Este documento descreve **o que foi integrado**, **o que foi alterado** e como
**rodar e testar** a integração entre o frontend Next.js e o backend FastAPI.

---

## O que foi integrado

### Backend (`PI-echomind-back`)

| Arquivo | Alteração |
|---|---|
| `app/api/v1/faq.py` | Adicionadas rotas `GET /{id}`, `PUT /{id}` e `DELETE /{id}` |
| `app/api/v1/events.py` | Removida autenticação obrigatória das rotas de escrita (alinhado com FAQs) |
| `app/services/faq_service.py` | Adicionados métodos `get_by_id`, `update_faq` e `delete_faq` |
| `app/main.py` | Corrigido registro duplicado do router de events; adicionado `import app.models` para garantir que as tabelas sejam criadas no startup |

### Frontend (`PI-echomind-front`)

| Arquivo | Alteração |
|---|---|
| `contexts/auth-context.tsx` | **Novo** — contexto global com `login()`, `register()`, `logout()`, `isAuthenticated` |
| `app/layout.tsx` | Adicionado `<AuthProvider>` envolvendo toda a aplicação |
| `app/page.tsx` | Redirect inteligente: logado → `/dashboard`, deslogado → `/login` |
| `app/(admin)/layout.tsx` | Proteção de rota: redireciona para `/login` se não autenticado |
| `app/(auth)/login/page.tsx` | Integrado com API real (campo `username`, não email) |
| `app/(auth)/registrar-conta/page.tsx` | Integrado com API real + confirmação de senha |
| `components/app-sidebar.tsx` | Logout funcional + exibe nome do usuário |
| `lib/api.ts` | **Novo** — cliente HTTP centralizado com `tokenStorage`, envio automático de `Bearer`, `authApi`, `faqApi` e `eventApi` |
| `hooks/use-faqs.ts` | Integrado com `faqApi` (lista, cria, atualiza, deleta) |
| `hooks/use-events.ts` | Integrado com `eventApi` (lista, cria, atualiza, deleta) |
| `types.ts` | Adicionado campo `category` no tipo `Faq` |
| `constants.ts` | Removidos dados mockados |
| `.env.local.example` | **Novo** — variável `NEXT_PUBLIC_API_URL` |

---

## Como rodar

O backend roda inteiramente via Docker Compose, conforme o README original do projeto.

### 1. Backend

```bash
cd PI-echomind-back

# Copie e edite o arquivo de variáveis de ambiente
cp .env.example .env

# Suba os containers (PostgreSQL + pgvector + API)
docker compose up --build -d

# Popule o banco com dados iniciais
docker exec -it totem_api python seed.py
```

O `seed.py` cria automaticamente:
- Admin padrão: usuário `admin`, senha `admin123`
- 8 FAQs de exemplo com embeddings
- 3 eventos de exemplo

Confirme que o backend está no ar:

```bash
curl http://localhost:8000/health
# {"status":"ok","service":"EchoMind API"}
```

Documentação interativa: http://localhost:8000/docs

### 2. Frontend

```bash
cd PI-echomind-front

# Crie o arquivo de variáveis (o valor padrão já aponta para localhost:8000)
cp .env.local.example .env.local

# Instale as dependências
pnpm install

# Inicie o servidor de desenvolvimento
pnpm dev
```

Acesse http://localhost:3000.

---

## Como fazer login

O campo de login é **Usuário** (não email), pois o backend usa `OAuth2PasswordRequestForm`.

**Com o usuário criado pelo seed:**
- Usuário: `admin`
- Senha: `admin123`

**Para criar uma conta nova:**
1. Acesse http://localhost:3000/registrar-conta
2. Preencha usuário e senha (mínimo 6 caracteres)
3. Após o registro, faça login normalmente

O token JWT fica salvo no `localStorage` e é enviado automaticamente em todas as requisições. O botão **Sair** na barra lateral limpa o token e redireciona para o login.

---

## Testando a integração

### FAQs

```bash
# Criar uma FAQ
curl -X POST http://localhost:8000/api/v1/faqs/ \
  -H "Content-Type: application/json" \
  -d '{"question":"Qual o horário da biblioteca?","answer":"Das 8h às 22h.","category":"Infraestrutura"}'

# Listar todas
curl http://localhost:8000/api/v1/faqs/
```

### Eventos

```bash
# Listar todos os eventos
curl http://localhost:8000/api/v1/events/

# Criar um evento
curl -X POST http://localhost:8000/api/v1/events/ \
  -H "Content-Type: application/json" \
  -d '{"title":"Workshop de IA","event_date":"2026-05-10T12:00:00","event_type":"workshop","description":"Introdução ao uso de LLMs"}'
```

---

## Observações

- **`show_on_totem`** é controlado localmente no frontend — o backend ainda não tem esse campo. O próximo passo é adicionar a coluna via migration e um endpoint `PATCH /api/v1/faqs/{id}/totem`.
- **Recuperação de senha** ainda não está integrada com o backend (o backend não implementa esse fluxo).
- Em produção, altere `NEXT_PUBLIC_API_URL` no `.env.local` para a URL do backend em produção.

---

## Troubleshooting

### "Credenciais inválidas" ao tentar logar com admin/admin123

O `seed.py` original do projeto **não criava o usuário admin**. O `seed.py` corrigido nesta integração já cria o admin, mas se você rodou o seed antigo antes, o usuário não existe no banco.

**Solução — rode o seed corrigido novamente:**

```bash
docker exec -it totem_api python seed.py
```

**Ou crie o admin via API** (sem precisar rodar o seed):

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

**Ou crie pelo Swagger:** acesse http://localhost:8000/docs → `POST /api/v1/auth/register`.

Após criar o usuário, faça login com `admin` / `admin123` em http://localhost:3000/login.
