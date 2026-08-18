# PR 03 — Embedding multilíngue de 384 dimensões

## Objetivo

Trocar o modelo padrão para `intfloat/multilingual-e5-small` e fornecer reindexação segura de FAQs/eventos, mantendo 384 dimensões.

## Contexto

O modelo inglês atual é inadequado como principal para PT-BR. Alterar a dimensão agora criaria migration vetorial desnecessária. Documentos ainda não existem nesta fase.

## Pré-requisitos

- PR 01 mergeada.
- Suíte atual verde ou falhas preexistentes registradas.
- Entender `_get_vector_store`, `_make_vector_id` e o isolamento de coleção atual.

## Dependências

Obrigatórias: PR 01.

Não depende de: PRs 02 e 04–35.

Paralelização: pode ocorrer em paralelo com PRs 02 e 04; PR 11 depende dela.

## Escopo desta PR

- Alterar o default de `EMBED_MODEL` para `intfloat/multilingual-e5-small`.
- Manter `EMBEDDING_DIM=384`.
- Atualizar `.env.example` e README.
- Criar `scripts/reindex_all.py` para iterar tenant por tenant, limpar apenas a coleção correspondente e reindexar FAQs/eventos existentes.
- Adicionar testes unitários do default, seleção de tenant, limpeza restrita e reindexação determinística com mocks.

## Arquivos provavelmente envolvidos

- `echomind-backend/app/rag_engine.py`
- `echomind-backend/.env.example`
- `echomind-backend/scripts/reindex_all.py` (novo)
- testes do RAG/scripts
- `README.md`

## Implementação

O script deve exigir configuração válida, processar tenants isoladamente e falhar de forma visível sem apagar outras coleções. Deve ser reexecutável para FAQ/evento. Não adicionar ramificações antecipadas para documents.

## Regras técnicas

- Preservar PGVector/LangChain e IDs atuais.
- Não alterar dimensão ou schema vetorial.
- Manter temporariamente `SIMILARITY_THRESHOLD=0.45`; calibração pertence à PR 23.
- Não executar reindexação destrutiva automaticamente em import/startup/deploy.

## Não implementar nesta PR

- documentos/chunks;
- reindexação de documentos;
- threshold novo;
- Hybrid Search/reranker;
- migration vetorial;
- chamada real ao embedding em CI;
- deploy.

## Testes obrigatórios

- Default do modelo e dimensão.
- Iteração tenant a tenant.
- Coleção de tenant A não é apagada ao processar B.
- FAQs/eventos mantêm IDs determinísticos e são reindexados.
- Suíte rápida completa.

## Critérios de aceite

- Aplicação configura o novo modelo sem mudança de dimensão.
- Script reindexa somente conteúdo existente e não toca em estrutura legada.
- Regressões de FAQ/evento não ocorrem.

## Definition of Done

Código, exemplos, documentação e testes desta troca estão verdes; nenhuma ingestão documental foi antecipada.

## Riscos e cuidados

Trocar o default sem reindexar mistura espaços vetoriais. O script deve exigir execução operacional consciente. A limpeza deve estar rigidamente limitada à coleção do tenant.

## Resultado esperado

O RAG fica preparado para PT-BR antes da indexação de documentos.

## Instrução final ao Codex

Implemente apenas a troca 384d e reindexação de FAQ/evento. Liste alterações/testes e pare.
