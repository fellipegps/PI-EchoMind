# PR 26 — Parent-Child Retrieval

## Objetivo

Recuperar por chunks precisos e fornecer ao contexto a seção/artigo pai necessário para preservar exceções e regras completas.

## Contexto

Chunking plano já foi avaliado com Hybrid Search e reranker. Parent-Child implica mudança de persistência/reindexação e deve ocorrer isoladamente.

## Pré-requisitos

- PR 25 mergeada.
- Evals demonstram perda de contexto por fragmentação.
- Desenho de parentesco e migration aditiva aprovado.

## Dependências

Obrigatórias: PR 25.

Não depende de: context compression/query expansion/HyDE/CD.

Paralelização: não paralelizar com outras mudanças de chunk/schema/reindex.

## Escopo desta PR

- Adicionar representação mínima de parent/child por migration/model.
- Produzir parents/children de forma determinística no processamento/reindexação.
- Indexar children para busca e resolver parent tenant-scoped para contexto.
- Preservar fonte/página/validade e cleanup completo.
- Criar backfill/reindex explícito e reversível operacionalmente.
- Comparar eval e latência com PR 25.

## Arquivos provavelmente envolvidos

- migration/models/repository de chunks
- ingestion/chunking
- RAG/reindex script
- integration tests/evals/docs

## Implementação

Usar mudanças aditivas e compatibilidade transitória; não remover estrutura plana no mesmo deploy. Parent lookup nunca usa ID sem tenant. IDs continuam determinísticos.

## Regras técnicas

- Reindex/backfill não roda automaticamente sem controle.
- Delete remove filhos, pais e vetores correspondentes.
- Contexto não duplica parents repetidos.
- Migração sobe do zero em CI real.

## Não implementar nesta PR

- context compression;
- query expansion/memória;
- HyDE;
- alteração de modelo/reranker;
- UI/CD.

## Testes obrigatórios

- Migration/compatibilidade.
- Parent/child determinísticos, ordem e páginas.
- Retrieval de child retorna parent correto.
- Deduplicação de parent, validade e tenant.
- Reprocessamento/delete sem órfãos.
- Eval antes/depois e regressão FAQ/evento.

## Critérios de aceite

- Casos de exceção/seção melhoram com custo aceitável.
- Transição é aditiva e rollback de aplicação é possível.
- Isolamento e cleanup completos.

## Definition of Done

Parent-Child medido, migrável e testado sem técnicas condicionais adicionais.

## Riscos e cuidados

É a melhoria mais invasiva pós-MVP: risco de duplicação, contexto grande e backfill. Se o eval não justificar, não implementar.

## Resultado esperado

O retrieval mantém precisão de child e coerência normativa do parent.

## Operação implementada

- A migration `0011` cria `document_chunk_parents` e adiciona `parent_id`
  opcional aos chunks; chunks legados continuam válidos sem parent.
- Novos processamentos persistem parents compostos por até três children
  contíguos. Somente os children são indexados no PGVector.
- O backfill é explícito e nunca roda durante migration ou startup:
  `python scripts/reindex_all.py --confirm --parent-child-backfill`.
- O rollback de aplicação também é explícito e reindexa a coleção plana:
  `python scripts/reindex_all.py --confirm --parent-child-rollback`.
- Antes de executar `alembic downgrade 0010`, executar o rollback de aplicação
  para manter os vetores compatíveis com chunks sem parent.

## Instrução final ao Codex

Implemente somente Parent-Child se pré-requisitos/evidência existirem. Caso contrário, pare como bloqueado.
