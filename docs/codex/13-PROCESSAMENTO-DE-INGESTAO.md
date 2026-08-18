# PR 13 — Serviço de processamento de ingestão

## Objetivo

Orquestrar extração, chunking, persistência e indexação com transições de estado, sessão própria e compensação de falha, sem expor endpoint.

## Contexto

As peças já existem isoladamente. O processamento assíncrono futuro precisa de uma função chamável e testável que não reutilize a sessão da request.

## Pré-requisitos

- PRs 06, 08, 09, 10 e 12 mergeadas.
- Definir quem possui commit/rollback em cada fronteira sem alterar arquitetura ampla.

## Dependências

Obrigatórias: PR 06, PR 08, PR 09, PR 10 e PR 12.

Não depende de: FastAPI BackgroundTasks, rotas ou frontend.

Paralelização: pode ocorrer em paralelo com PR 14 após PRs 06/12; PR 15 aguarda ambas.

## Escopo desta PR

- Implementar `process_document(...)` em módulo de serviço coerente com o projeto.
- Abrir e fechar sua própria `SessionLocal`.
- Fluxo `pending → processing → ready|error`.
- Extrair pelo MIME validado, chunkar, persistir chunks, indexar e preencher contagem/timestamps.
- Em falha, remover vetores/chunks parciais quando aplicável, persistir erro curto e marcar `error`.
- Tornar reexecução controlada/idempotente para o mesmo registro, sem criar job table.
- Testar sucesso por formato, falha em cada etapa, cleanup e fechamento de sessão.

## Arquivos provavelmente envolvidos

- `echomind-backend/app/document_ingestion.py` e/ou módulo de processamento dedicado
- repository/document CRUD
- `echomind-backend/tests/test_document_ingestion.py`
- `echomind-backend/tests/integration/test_document_pgvector.py` para compensação aplicável

## Implementação

Receber bytes ou referência temporária durável definida antes do fechamento da request; não receber `UploadFile` aberto como dependência de longo prazo. Separar mensagem persistida do log interno. Orquestração chama interfaces já testadas.

## Regras técnicas

- Sessão de request nunca atravessa background.
- Estado final deve refletir o resultado persistido.
- Cleanup é tenant-scoped e idempotente.
- Não vazar stack trace em `error_message`.
- Não introduzir Celery/Redis.

## Não implementar nesta PR

- endpoint de upload/list/delete;
- `BackgroundTasks`;
- polling/frontend;
- citações/validade;
- job table/fila distribuída;
- reindex_all.

## Testes obrigatórios

- Sucesso TXT, DOCX e PDF com mocks nas fronteiras adequadas.
- Ordem de estados e campos de sucesso.
- Falha de parser, persistência e vector upsert termina em `error`.
- Cleanup de chunks/vetores parciais.
- Sessão abre/fecha inclusive em exceção.
- Tenant incorreto não é processado.
- Integration aplicável com PGVector fake embedding.

## Critérios de aceite

- Função pode ser chamada fora de uma request e conclui de forma observável.
- Falha parcial não deixa documento falsamente `ready`.
- Nenhuma rota/fila externa foi criada.

## Definition of Done

Máquina de estados, recursos e compensação cobertos; CI rápida e integração verdes.

## Riscos e cuidados

Transação relacional não cobre PGVector de modo atômico; compensação e idempotência são obrigatórias. Cuidado com commits intermediários e retry concorrente.

## Resultado esperado

Existe um worker in-process confiável pronto para ser agendado pela API.

## Instrução final ao Codex

Implemente apenas o serviço de processamento, sem endpoint ou BackgroundTasks. Teste e pare.
