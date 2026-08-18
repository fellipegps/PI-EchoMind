# PR 11 — Contrato de metadata no PGVector

## Objetivo

Evoluir o upsert vetorial existente para aceitar metadata extra de forma segura, preservando integralmente FAQ/evento e campos protegidos.

## Contexto

Chunks exigirão fonte, página e metadados documentais. Antes de indexá-los, o primitivo genérico do RAG deve ter um contrato pequeno e testado.

## Pré-requisitos

- PR 03 mergeada.
- Inspecionar testes e assinaturas reais de `_upsert_document`, `_make_vector_id` e métodos de FAQ/evento.

## Dependências

Obrigatórias: PR 03.

Não depende de: PRs 05–10.

Paralelização: pode ocorrer em paralelo com persistência/extractors; PR 12 aguarda esta fase.

## Escopo desta PR

- Adicionar `extra_metadata` opcional ao upsert ou primitivo equivalente.
- Mesclar metadata sem permitir sobrescrever `source_id`, `source_type` e `tenant_id`.
- Normalizar/remover valores vazios ou não serializáveis conforme contrato explícito.
- Manter conteúdo, IDs, coleção e comportamento de FAQ/evento.
- Criar testes unitários de merge, campos protegidos, idempotência e regressão.

## Arquivos provavelmente envolvidos

- `echomind-backend/app/rag_engine.py`
- testes existentes de RAG/FAQ/evento
- `echomind-backend/tests/conftest.py` apenas se o fake precisar refletir a assinatura

## Implementação

A API interna deve continuar aceitando chamadas antigas. Definir precedência de metadata no próprio código/teste. Não introduzir ainda `document_chunk` nem conhecer models de documento.

## Regras técnicas

- IDs vetoriais e coleção por tenant não mudam.
- Campos de segurança sempre são produzidos internamente.
- Metadata deve ser aceita pelo backend JSON do PGVector.
- Compatibilidade de FAQ/evento é critério bloqueante.

## Não implementar nesta PR

- `index_document_chunk`;
- cabeçalho documental no conteúdo;
- exclusão/reindexação de chunks;
- filtering/validade/citações;
- API ou frontend;
- Hybrid Search.

## Testes obrigatórios

- Chamada sem metadata mantém resultado anterior.
- Metadata extra válida é mesclada.
- Tentativa de sobrescrever campos protegidos falha ou é ignorada conforme contrato testado.
- Valores vazios/não serializáveis seguem política definida.
- IDs e comportamento de FAQ/evento permanecem iguais.

## Critérios de aceite

- O upsert genérico suporta extensão futura sem quebrar consumidores atuais.
- Não há conhecimento antecipado de documento.
- Suíte rápida verde.

## Definition of Done

Contrato interno pequeno, compatível e testado, com regressão existente verde.

## Riscos e cuidados

Uma fusão ingênua de dicionários permite injetar tenant/source. Não alterar conteúdo vetorizado ou IDs incidentalmente.

## Resultado esperado

O RAG possui o primitivo seguro necessário à indexação documental da PR 12.

## Instrução final ao Codex

Implemente só a extensão segura de metadata e pare.
