# PR 12 — Ciclo vetorial de chunks documentais

## Objetivo

Indexar, reindexar e excluir chunks no PGVector existente com IDs determinísticos, metadata de fonte e isolamento real por tenant.

## Contexto

Models/chunks e contrato de metadata já existem. Esta PR conecta somente o ciclo vetorial, não a API nem a orquestração completa.

## Pré-requisitos

- PRs 02, 05, 10 e 11 mergeadas.
- Harness PostgreSQL/pgvector real verde.

## Dependências

Obrigatórias: PR 02, PR 05, PR 10 e PR 11.

Não depende de: API, BackgroundTasks, frontend, citações.

Paralelização: bloqueia PRs 13–18; não paralelizar alterações no mesmo RAGEngine.

## Escopo desta PR

- Implementar `index_document_chunk(document, chunk)` ou equivalente.
- Usar `source_type=document_chunk` e `source_id=chunk.id`.
- Montar conteúdo de embedding com cabeçalho curto somente para metadados presentes.
- Incluir document ID, arquivo, tipo/número, datas, departamento, índice e páginas na metadata.
- Implementar delete de vetores para todos os chunks de um documento/tenant.
- Garantir upsert idempotente e cleanup de órfãos em reindexação do mesmo conjunto.
- Criar integração real com embedding fake determinístico.

## Arquivos provavelmente envolvidos

- `echomind-backend/app/rag_engine.py`
- `echomind-backend/tests/integration/test_document_pgvector.py`
- `echomind-backend/tests/conftest.py`/fixtures de embedding fake

## Implementação

Calcular IDs pelo mecanismo existente. A exclusão recebe chunks já resolvidos com tenant e nunca busca/delete por source não escopado. A integração deve passar pelo PGVector real, não por lista fake.

## Regras técnicas

- Um chunk corresponde a exatamente um vetor determinístico.
- Coleção continua `knowledge_<tenant>`.
- Não criar tabela/index vetorial manual.
- Datas em metadata usam forma serializável e consistente.
- FAQ/evento continuam recuperáveis.

## Não implementar nesta PR

- `process_document` e estados;
- endpoints/background;
- filtro de validade no retrieval;
- prompt/citações;
- reindex_all de documentos;
- frontend;
- Hybrid Search/reranker.

## Testes obrigatórios

- Indexação no tenant/coleção corretos.
- `source_type`, metadata e cabeçalho de conteúdo.
- Reindexar não duplica nem muda ID.
- Remoção apaga todos e somente os vetores do documento.
- Tenant A nunca aparece no retrieval de B.
- FAQ/evento continuam indexáveis/recuperáveis.
- Suítes rápida e integration.

## Critérios de aceite

- Ciclo vetorial completo é idempotente e multi-tenant.
- Nenhum endpoint ou mudança de prompt.
- Integração real verde sem serviços externos.

## Definition of Done

Testes PGVector cobrem metadata, idempotência, cleanup e isolamento; CI completa verde.

## Riscos e cuidados

Falha no meio de múltiplos upserts pode deixar parcial; a PR 13 implementará compensação. Esta PR deve fornecer operações idempotentes utilizáveis por ela.

## Resultado esperado

Chunks persistidos podem ganhar e perder vetores de forma segura e testável.

## Instrução final ao Codex

Implemente exclusivamente o ciclo vetorial e seus testes. Não orquestre upload/processamento. Pare.
