# EchoMind — Plano geral de execução por Pull Requests

## Objetivo geral da evolução

Transformar a aba **Documentos**, hoje apenas visual, em um pipeline real e multi-tenant de ingestão de PDF, TXT e DOCX, persistência de estado e chunks, indexação no PGVector já usado pelo LangChain e recuperação com fonte. A evolução deve manter o EchoMind utilizável a cada merge, com feedback rápido, integração real PostgreSQL/pgvector e mudanças reversíveis.

Este plano reorganiza integralmente o antigo `AGENTS(1).md`. Ele é uma fila controlada: uma fase só começa quando for explicitamente solicitada e suas dependências já estiverem mergeadas.

## Arquitetura atual relevante

- Backend FastAPI e frontend Next.js executam diretamente em seus ambientes; Docker não é requisito para nenhum deles.
- FAQs e eventos já participam do RAG, um vetor por item.
- O vector store é `PGVector` do LangChain, em coleção `knowledge_<tenant>` por tenant.
- IDs vetoriais são determinísticos por `_make_vector_id(...)`.
- As tabelas internas `langchain_pg_collection` e `langchain_pg_embedding` continuam responsáveis pelos vetores.
- A tabela legada `knowledge_documents` foi removida pelas migrations `0007`/`0008` e não deve ser recriada.
- Os testes rápidos usam SQLite, substituem `pgvector.Vector` por `Text` e mockam o `RAGEngine`; são úteis, mas não validam PostgreSQL, Alembic ou PGVector reais.
- A aba de documentos usa estado local e dados simulados; o helper HTTP JSON atual não serve para multipart.
- O embedding atual, `BAAI/bge-small-en-v1.5`, será trocado por `intfloat/multilingual-e5-small`, ainda com 384 dimensões.
- O provedor de hospedagem de backend/frontend não está definido. CD específico permanece bloqueado até essa decisão.

## Resultado esperado ao final do MVP

Um administrador autenticado envia um arquivo permitido; o backend valida, calcula SHA-256, registra `pending`, extrai e divide o texto, persiste chunks, indexa vetores determinísticos na coleção do tenant e conclui em `ready` ou `error`. O painel lista o estado real, acompanha o processamento e exclui documentos. O chat recupera FAQ, evento e chunks de documento, ignora documentos vencidos e identifica a fonte quando disponível.

O marco de MVP termina na PR 21. PRs 22–32 são evolução pós-MVP. PRs 33–35 são de entrega e estão bloqueadas por decisões externas. Itens ainda condicionais estão em `99-BACKLOG-E-DECISOES-FUTURAS.md`.

## Sequência oficial das PRs

| PR | Nome | Objetivo | Depende de | Área |
|---:|---|---|---|---|
| 01 | CI rápida e baseline | Criar gates rápidos e medir cobertura atual | — | DevOps |
| 02 | CI PostgreSQL/pgvector | Validar Alembic e banco vetorial descartável | 01 | DevOps/DB |
| 03 | Embedding multilíngue 384d | Melhorar retrieval PT-BR sem mudar dimensão | 01 | RAG |
| 04 | Testes de frontend | Instalar Vitest/Testing Library e ligar o gate | 01 | Frontend/CI |
| 05 | Persistência documental | Criar models, migration, constraints e RLS | 02 | DB/Backend |
| 06 | Repositório documental | Isolar CRUD e transições por tenant | 05 | Backend |
| 07 | Validação de upload | Validar arquivo, nome, tamanho, MIME e hash | 06 | Backend/Security |
| 08 | Extração TXT/DOCX | Extrair texto e tabelas com contrato comum | 07 | Ingestão |
| 09 | Extração PDF | Extrair por página e tratar PDF/OCR inválido | 07 | Ingestão |
| 10 | Chunking determinístico | Criar chunks 800/100 page-aware | 08, 09 | Ingestão |
| 11 | Contrato de metadata PGVector | Evoluir upsert sem quebrar FAQ/evento | 03 | RAG |
| 12 | Ciclo vetorial de chunks | Indexar, reindexar e excluir chunks por tenant | 02, 05, 10, 11 | RAG/DB |
| 13 | Processamento de ingestão | Orquestrar estados, sessão e compensação | 06, 08, 09, 10, 12 | Backend |
| 14 | API de consulta e exclusão | Expor list/get/delete autenticados | 06, 12 | API |
| 15 | API de upload e background | Expor multipart 202 e agendar processamento | 07, 13, 14 | API |
| 16 | Contexto com fonte | Formatar fontes, ajustar prompt e citações | 12, 15 | RAG |
| 17 | Validade documental | Filtrar vencidos com overfetch controlado | 16 | RAG |
| 18 | Reindexação de documentos | Estender reindex para chunks `ready` | 03, 12, 13, 17 | RAG/Ops |
| 19 | Cliente frontend de documentos | Criar tipos e cliente multipart testado | 04, 14, 15 | Frontend |
| 20 | Aba Documentos real | Trocar mock por listagem, polling e ações reais | 19 | Frontend |
| 21 | Aceite integrado do MVP | Fechar contratos, gates, regressão e documentação | 02–20 | QA/Docs |
| 22 | Dataset e runner de eval RAG | Medir qualidade, recusa, fonte e latência | 21 | RAG/QA |
| 23 | Calibração do threshold | Escolher limiar com dados, sem chute | 22 | RAG |
| 24 | Hybrid Search | Combinar PGVector e full-text PostgreSQL | 23 | RAG/DB |
| 25 | Reranker | Reordenar candidatos sobre baseline medido | 24 | RAG |
| 26 | Parent-Child Retrieval | Recuperar seção completa preservando precisão | 25 | RAG/DB |
| 27 | CORS configurável | Remover política aberta com configuração segura | 21 | Security |
| 28 | Rate limiting de APIs | Limitar `/chat` e upload com política testada | 21 | Security/API |
| 29 | Cache de FAQ seguro | Substituir matching por substring | 21 | RAG |
| 30 | Logs estruturados de RAG | Registrar tenant, etapa, latência e retrieval | 21 | Observability |
| 31 | Métricas RAG no dashboard | Agregar e exibir métricas sem dados sensíveis | 30 | Observability |
| 32 | Segurança de dependências | Automatizar updates e auditorias graduais | 21 | Supply chain |
| 33 | Integração do provedor de CD | Implementar deploy somente após escolha formal | 21 + decisão externa | DevOps — bloqueada |
| 34 | Staging smoke/E2E | Validar ambiente implantado com conta sintética | 04, 20, 33 + staging | QA/CD — bloqueada |
| 35 | Promoção protegida de produção | Promover release validada com aprovação manual | 33, 34 + estratégia de release | CD — bloqueada |

## Dependências e paralelização

A numeração é a ordem recomendada de merge, não autorização para avanço automático. Duas equipes podem trabalhar em paralelo apenas se mantiverem branches independentes, não anteciparem contratos e validarem novamente após rebase.

- PR 04 pode ocorrer em paralelo com 02–03 depois da PR 01.
- PRs 08 e 09 podem ocorrer em paralelo porque implementam extractors distintos sobre o contrato da PR 07.
- PR 11 pode ocorrer em paralelo com 05–10 depois da PR 03; PR 12 aguarda ambas as trilhas.
- PR 14 pode avançar em paralelo com 13 depois de 06 e 12.
- PRs 27–30 e 32 podem ocorrer em paralelo após 21. PR 31 aguarda 30.
- PRs 22–26 formam uma cadeia experimental e não devem ser paralelizadas entre si: cada técnica precisa do baseline anterior.
- PRs 33–35 não bloqueiam eval ou hardening, mas não podem começar sem as decisões externas indicadas.
- PRs 19–20 não devem adivinhar contratos: dependem da API mergeada.

## Definition of Done global

Uma PR está concluída somente quando:

- implementa um único objetivo principal e nada listado em **Não implementar nesta PR**;
- preserva autenticação, isolamento por tenant, FAQ, eventos e chat existentes;
- inclui os testes diretamente relacionados à mudança;
- executa lint, typecheck, testes rápidos e integração aplicável;
- não usa Groq, Supabase, staging ou produção reais em CI de Pull Request;
- migrations sobem em PostgreSQL descartável quando aplicável;
- CI está verde, revisão foi concluída e a PR foi mergeada antes da próxima fase dependente;
- documentação/configuração de exemplo é atualizada somente quando necessária à fase;
- o encerramento lista arquivos alterados e comandos/testes executados;
- nenhuma funcionalidade futura, Dockerfile ou Compose foi introduzido.

## Critério para avançar

```text
PR N solicitada
  ↓
implementação no escopo
  ↓
lint e typecheck aplicáveis
  ↓
unit/API tests
  ↓
integration tests aplicáveis
  ↓
CI verde
  ↓
review e merge
  ↓
parar
  ↓
PR N+1 somente após nova solicitação do usuário
```

Falha preexistente deve ser registrada. Ela só pode ser corrigida na fase se bloquear seu objetivo e a correção continuar pequena e relacionada; do contrário, a fase para com o bloqueio documentado.

## Estratégia de CI/CD

### CI rápida

- `Backend / unit-api`: Python 3.12, dependências frozen conforme o projeto, suíte sem markers `integration`/`e2e`, cobertura medida e baseline sem regressão.
- `Frontend / quality-build`: Node 20+ conforme README/lockfile, pnpm frozen, lint, typecheck e build; testes entram na PR 04.
- Triggers: Pull Request, push em `main` e `workflow_dispatch`; concorrência cancela execução anterior da mesma branch/PR.
- Permissão padrão `contents: read`; nenhum segredo de produção em PR.
- Branch protection deve usar nomes estáveis desses checks e de `Database / migration-integration` depois que os três estiverem verdes na `main`.

### CI de integração

O único container autorizado nesta etapa é PostgreSQL + pgvector descartável:

```text
GitHub Actions
      ↓
PostgreSQL + pgvector descartável
      ↓
CREATE EXTENSION vector
      ↓
Alembic upgrade head
      ↓
integration tests multi-tenant/ingestão/RAG
      ↓
container destruído
```

O major do PostgreSQL deve corresponder ao Supabase do projeto e ser confirmado antes de fixar a imagem. Credenciais do container são efêmeras. Nunca executar teste destrutivo contra staging ou produção.

Docker **não** é requisito para executar FastAPI. Docker **não** é requisito para executar Next.js. Não criar Dockerfile para backend/frontend nem `docker-compose.yml`/`compose.yaml` neste plano.

### CD

As PRs 33–35 ficam bloqueadas até a equipe definir provedor, comandos, ambientes e estratégia de release. Não presumir Vercel, Railway, Render, AWS, Fly.io ou qualquer outro. Quando liberado, staging deve usar secrets próprios, migration backward-compatible, health check, smoke e E2E. Produção deve exigir versão já validada, ambiente protegido e aprovação manual. `alembic downgrade` não é rollback automático de produção.

## Estratégia de testes

- **Nível 1 — rápido:** SQLite + mocks para regras de domínio/API; sem rede.
- **Nível 2 — integração:** PostgreSQL/pgvector real + Alembic + embedding determinístico; sem Groq/Supabase externos.
- **Nível 3 — frontend:** Vitest + Testing Library + jsdom para cliente, estados, polling e exclusão.
- **Nível 4 — staging:** Playwright/smoke apenas após infraestrutura e conta de teste próprias.

Fixtures documentais devem ser mínimas, sintéticas e sem dados pessoais/sigilosos. Os markers oficiais são `integration` e `e2e`. Cada fase adiciona seus testes; PR 21 apenas fecha contratos transversais e não serve como depósito tardio de testes.

## Riscos arquiteturais

- vazamento entre tenants por filtro ausente em banco, API, coleção ou cleanup vetorial;
- divergência entre `documents`/`document_chunks` e vetores após falha parcial;
- duplicação/órfãos se IDs deixarem de ser determinísticos;
- mudança de embedding sem reindexação consistente;
- threshold antigo inadequado ao novo embedding;
- PDF sem camada textual ser confundido com documento vazio; OCR não faz parte do MVP;
- fechamento de `UploadFile` antes do background consumir os bytes;
- sessão SQLAlchemy compartilhada indevidamente com `BackgroundTasks`;
- exclusão concorrente com processamento;
- metadados não serializáveis ou campos protegidos sobrescritos no PGVector;
- prompt injection contida em documentos recuperados;
- CI falsa-verde se usar apenas SQLite ou mocks;
- CD inseguro se provedor, secrets, migration e rollback forem presumidos.

## Funcionalidades explicitamente fora do escopo inicial

Até a PR 21, não implementar Hybrid Search, reranker, Parent-Child Retrieval, context compression, query expansion, HyDE, OCR, Celery/Redis, memória de conversa, multi-LLM, WhatsApp, analytics avançado, A/B testing, relatórios automáticos, import/export, onboarding, preview de totem, sugestão automática de FAQ ou dockerização completa.

As decisões condicionais e o backlog após a PR 35 estão detalhados em `99-BACKLOG-E-DECISOES-FUTURAS.md`.
