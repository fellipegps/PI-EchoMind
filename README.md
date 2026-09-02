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

ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

CHAT_RATE_LIMIT_REQUESTS=20
CHAT_RATE_LIMIT_WINDOW_SECONDS=60
UPLOAD_RATE_LIMIT_REQUESTS=5
UPLOAD_RATE_LIMIT_WINDOW_SECONDS=60

GROQ_API_KEY=gsk_SUBSTITUA_PELA_SUA_CHAVE
GROQ_LLM_MODEL=openai/gpt-oss-120b

EMBED_MODEL=intfloat/multilingual-e5-small
EMBEDDING_DIM=384
SIMILARITY_THRESHOLD=0.35
TOP_K_DOCS=3
MAX_DOCUMENT_SIZE_MB=10
```

Nunca exponha `SUPABASE_SECRET_KEY` no frontend.

`ALLOWED_ORIGINS` recebe uma ou mais origens exatas separadas por virgula. O
exemplo libera apenas o frontend local em `localhost` e `127.0.0.1`. Para
staging ou producao, informe explicitamente os dominios definidos para aquele
ambiente, sem wildcard, path, credenciais ou secrets. Se a variavel for omitida,
o backend mantém somente essas duas origens locais como fallback restrito.

O rate limiting protege `/chat` e `/documents/upload` com limites independentes.
Os valores acima representam, respectivamente, quantidade de requisicoes e
duracao da janela em segundos. O chat, que permanece publico, usa um hash do IP
direto da conexao e nunca o `tenant_id` enviado no payload. O upload usa um hash
do ID do usuario autenticado pelo backend. Ao exceder o limite, a API responde
com HTTP `429` e `Retry-After`; `/health` nao consome quota.

O store e mantido apenas na memoria do processo FastAPI. Isso corresponde ao
ambiente atual sem topologia de deploy definida, mas nao compartilha quota entre
workers ou replicas. Antes de operar com multiplas instancias, a equipe deve
escolher explicitamente um store distribuido; esta PR nao adiciona Redis nem
outra infraestrutura.

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

## Reindexacao Manual Do RAG

O embedding padrao e `intfloat/multilingual-e5-small`, com exatamente 384
dimensoes. Depois de implantar essa troca, execute conscientemente uma
reindexacao para evitar misturar vetores do modelo anterior com o novo espaco
vetorial:

```bash
cd echomind-backend
# Confirme antes que o ambiente usa:
# EMBED_MODEL=intfloat/multilingual-e5-small
# EMBEDDING_DIM=384
python scripts/reindex_all.py --confirm
```

O script le a configuracao normal do backend, encontra tenants que possuem FAQs,
eventos ou documentos com status `ready` e processa um por vez. Para cada tenant,
somente a colecao `knowledge_<tenant>` correspondente e limpa e recriada; em
seguida, as FAQs, os eventos e os `document_chunks` ja persistidos dos documentos
`ready` desse tenant sao indexados novamente com os IDs deterministicos atuais.
Documentos `pending`, `processing` e `error` sao ignorados. O arquivo original
nao e reprocessado e os chunks nao sao recriados.

A operacao para no primeiro tenant que falhar e informa os tenants ja concluidos.
Como cada colecao e reconstruida de forma deterministica, corrija a causa e rode
o mesmo comando manual novamente. Nao execute duas reindexacoes em paralelo.
Nenhuma reindexacao e iniciada automaticamente em startup, deploy, endpoint,
scheduler ou importacao.

O contrato operacional completo do MVP, incluindo formatos, estados, limites,
OCR nao suportado, roteiro manual e branch protection recomendada, esta em
[`docs/MVP-DOCUMENTAL.md`](docs/MVP-DOCUMENTAL.md).

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
| `POST` | `/documents/upload` | Upload documental autenticado via multipart |
| `GET` | `/documents` | Lista documentos do tenant autenticado |
| `GET/DELETE` | `/documents/{id}` | Consulta ou exclui documento terminal do tenant |
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
8. Envie um TXT, PDF textual ou DOCX pela aba Documentos e aguarde `ready`.
9. Confirme que o chat usa a fonte documental e que a exclusao remove o item.
10. Copie a URL do totem em configuracoes e teste o atendimento publico.

## Avaliação RAG offline

O dataset em `echomind-backend/evals/rag_baseline_dataset.json` contém 20 casos
e um corpus inteiramente sintético, cobrindo datas, números, requisitos,
exceções, recusa, fontes e documentos vigentes/vencidos. Cada caso mantém a
expectativa, a observação baseline e um campo `human_review` para uma revisão
posterior; a métrica automática não a substitui.

O runner não importa o runtime de produção nem faz chamadas de rede, embedding
ou LLM. Ele mede recuperação (recall/precision de fontes), geração (F1 lexical
explícito, correção por regra e recusa), presença de citação e latência de cada
etapa observada. Para regenerar o relatório versionável:

```bash
cd echomind-backend
python scripts/eval_rag.py \
  --dataset evals/rag_baseline_dataset.json \
  --output evals/baseline_report.json
```

O JSON gerado lista falhas por caso e a configuração de retrieval registrada;
ele é uma baseline de infraestrutura sintética, não uma autorização para mudar
threshold, embeddings ou a estratégia de busca.

### Calibração do threshold

O default de `SIMILARITY_THRESHOLD` foi calibrado de `0.45` para `0.35` com o
mesmo dataset sintético. O sweep de `0.30` a `0.50`, em passos de `0.05`, está
arquivado em `echomind-backend/evals/threshold_calibration_report.json`: `0.35`
preserva recall de fontes de 100% e recusa correta de 100%, enquanto `0.45`
aceita contexto irrelevante em todos os casos sintéticos de recusa. O algoritmo,
embedding, top-K e filtro de validade não foram alterados.

Para reproduzir a decisão:

```bash
cd echomind-backend
python scripts/calibrate_similarity_threshold.py \
  --dataset evals/rag_baseline_dataset.json \
  --candidates evals/similarity_threshold_candidates.json \
  --output evals/threshold_calibration_report.json
```

### Busca híbrida PostgreSQL + PGVector

A recuperação agora preserva o PGVector e acrescenta candidatos lexicalmente
encontrados no PostgreSQL. As quatro consultas full-text usam `tenant_id`
explicitamente: FAQs, eventos, metadados de documentos e conteúdo dos chunks;
chunks também exigem documento `ready` e vigente. A migration `0010` adiciona
apenas índices GIN de expressão, sem tabela global ou cópia manual do corpus.

Os canais são fundidos com Reciprocal Rank Fusion (RRF): cada ocorrência soma
`1 / (60 + posição)`; fontes são deduplicadas por `(source_type, source_id)` e
empates usam posição vetorial, posição lexical, tipo e ID. O threshold de 0,35
continua valendo somente para o canal vetorial; a busca lexical permite que
códigos e siglas exatos sejam candidatos sem alterar embeddings, top-K ou a
estratégia semântica existente.

O custo adicional é de quatro consultas FTS curtas por pergunta, cobertas pelos
índices GIN. O rollback de aplicação é seguro porque a busca vetorial continua
autônoma; os índices da migration podem permanecer (ou ser removidos pelo
downgrade) sem apagar conteúdo nem vetores. A comparação sintética está em
`echomind-backend/evals/hybrid_search_report.json` e é reproduzida por:

```bash
cd echomind-backend
python scripts/eval_hybrid_search.py \
  --dataset evals/hybrid_search_eval.json \
  --output evals/hybrid_search_report.json
```

### Reranker de candidatos

O reranker é aplicado somente depois da recuperação e da fusão híbrida. Quando
ativado, reordena até 12 candidatos (configurável entre 10 e 15), limita cada
texto a 2.000 caracteres e entrega o `TOP_K_DOCS` existente. Conteúdo e metadata
dos objetos recuperados não são reconstruídos; tenant, fonte e validade já
filtrados permanecem inalterados.

A implementação usa o `TextCrossEncoder` do FastEmbed, já presente nas
dependências. O modelo operacional padrão é `BAAI/bge-reranker-base`, licença
MIT e tamanho aproximado de 1,04 GB. A sessão ONNX e os arquivos em `HF_HOME`
ficam em cache no processo. Como esse modelo não declara suporte amplo a PT-BR,
`RERANKER_ENABLED=false` é o default conservador; a ativação exige avaliação
controlada do corpus real. O modelo multilíngue listado pelo FastEmbed não foi
adotado porque sua licença é CC-BY-NC-4.0.

Timeout, erro, modelo ausente ou falha de download geram aviso com etapa,
quantidade de candidatos e latência, e retornam exatamente o ranking híbrido da
PR 24. Os testes usam fakes e não baixam modelo nem fazem chamadas externas.

O comparativo sintético versionado referencia as métricas das PRs 22 e 24 e é
reproduzido por:

```bash
cd echomind-backend
python scripts/eval_reranker.py \
  --dataset evals/reranker_eval.json \
  --baseline-pr22 evals/baseline_report.json \
  --baseline-pr24 evals/hybrid_search_report.json \
  --output evals/reranker_report.json
```

Nesse conjunto controlado, Hit@3 passa de 0,833 para 1,000 e MRR@3 de
0,556 para 1,000. A sobrecarga simulada média é 3,667 ms (p95 5 ms), levando a
latência controlada média de 15,000 para 18,667 ms. A baseline PR 22 continua em
recall/precision de fontes 1,000/1,000 e retrieval médio de 14,05 ms (p95 18
ms). Esses tempos de fake não substituem um benchmark do modelo real no host de
produção.

## CI Rapida E Baseline

O workflow `.github/workflows/ci.yml` executa em pull requests, pushes para
`main` e disparos manuais. Os checks estaveis sao `Backend / unit-api`,
`Database / migration-integration` e `Frontend / quality-build`; execucoes
anteriores da mesma branch ou PR sao canceladas quando uma nova comeca.

No aceite do MVP, a suite rapida permanece baseada em SQLite e mocks, sem Groq,
Supabase ou banco externo. O gate global continua em 72%, sem elevar ou manipular
a baseline historica. Os modulos documentais novos devem permanecer com pelo
menos 80% de cobertura; o relatorio `term-missing` e a fonte dos percentuais.

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
corepack pnpm typecheck
corepack pnpm test:run
corepack pnpm build
```

Durante o desenvolvimento, `corepack pnpm test` mantem o Vitest em modo watch.
Para gerar o relatorio de cobertura sem impor um limite bloqueante, use
`corepack pnpm test:coverage`.

O build de CI recebe somente placeholders publicos para
`NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SUPABASE_URL` e
`NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`. Nenhum segredo de producao e usado.

## CI PostgreSQL E pgvector

O check `Database / migration-integration` usa o container descartavel
`pgvector/pgvector:0.8.6-pg17`. O major PostgreSQL 17 corresponde ao projeto
Supabase, cuja versao informada e 17.6; a tag do pgvector fica fixa para evitar
mudancas silenciosas no ambiente de CI.

As suites permanecem separadas:

- `tests/quick` usa SQLite e FakeVector, sem banco ou servico externo;
- `tests/integration` aceita somente o banco local descartavel chamado
  `echomind_integration` e usa PostgreSQL/pgvector reais.

O gate rapido continua sendo reproduzido pelo comando da secao anterior. Para
reproduzir apenas a integracao no PowerShell, tenha Docker em execucao e rode:

```powershell
cd echomind-backend
python -m pip install -r requirements.txt -r requirements-dev.txt

docker run --name echomind-pgvector-integration --rm -d `
  -e POSTGRES_USER=echomind_ci `
  -e POSTGRES_PASSWORD=echomind_ci `
  -e POSTGRES_DB=echomind_integration `
  -p 55432:5432 `
  --health-cmd "pg_isready -U echomind_ci -d echomind_integration" `
  --health-interval 5s --health-timeout 5s --health-retries 10 `
  pgvector/pgvector:0.8.6-pg17

while ((docker inspect --format '{{.State.Health.Status}}' echomind-pgvector-integration) -ne 'healthy') {
  Start-Sleep -Seconds 1
}

$env:DATABASE_URL = 'postgresql://echomind_ci:echomind_ci@127.0.0.1:55432/echomind_integration?sslmode=disable'
docker exec echomind-pgvector-integration psql -U echomind_ci -d echomind_integration -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS vector"
python -m alembic upgrade head
python -m pytest -m integration

docker stop echomind-pgvector-integration
Remove-Item Env:DATABASE_URL
```

O `--rm` remove o container e o banco quando `docker stop` e executado. Essa
infraestrutura serve somente aos testes; Docker nao e requisito para executar a
API ou o frontend, e nenhuma URL de staging/producao deve ser usada.
