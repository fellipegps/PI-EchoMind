# PR 24 — Hybrid Search PostgreSQL + PGVector

## Objetivo

Combinar recuperação semântica atual com busca lexical PostgreSQL para termos exatos como números de edital, siglas e códigos, medindo ganho contra a PR 23.

## Contexto

O MVP e threshold já estão avaliados. Busca lexical só entra agora porque há corpus real e baseline comparável.

## Pré-requisitos

- PR 23 mergeada.
- Evidência no eval de falhas lexicais que justifiquem esta técnica.
- Desenho de full-text compatível com português e multi-tenancy.

## Dependências

Obrigatórias: PR 23.

Não depende de: reranker/Parent-Child/CD.

Paralelização: não paralelizar com PR 25; ela depende do conjunto de candidatos resultante.

## Escopo desta PR

- Adicionar estrutura/migration full-text mínima sobre conteúdo relacional adequado.
- Implementar consulta lexical tenant-scoped com `tsvector`/`ts_rank` ou padrão PostgreSQL equivalente.
- Fundir candidatos lexical/vetorial por algoritmo explícito e determinístico.
- Preservar filtro de validade, threshold/política semântica e fontes.
- Adicionar integration tests reais e comparar eval antes/depois.
- Documentar custo, índices e rollback aditivo.

## Arquivos provavelmente envolvidos

- migration Alembic nova
- models/repository/query RAG
- `echomind-backend/app/rag_engine.py`
- integration tests e eval reports

## Implementação

Manter PGVector como componente central; Hybrid Search não o substitui. Toda consulta lexical inclui tenant. A fusão deve deduplicar por source/chunk e manter metadata original.

## Regras técnicas

- Migration passa do zero em PostgreSQL descartável.
- Não criar mecanismo lexical global sem tenant.
- Ganho deve ser reportado por categoria, especialmente códigos/siglas.
- Sem novo provedor de busca.

## Não implementar nesta PR

- reranker;
- Parent-Child;
- context compression/query expansion/HyDE;
- troca de embedding/chunking;
- UI/CD.

## Testes obrigatórios

- Migration/índices/head.
- Termos exatos e reformulações semânticas.
- Deduplicação/fusão/ranking determinísticos.
- Isolamento tenant e validade.
- Regressão FAQ/evento/documento.
- Eval comparativo contra PR 23.

## Critérios de aceite

- Técnica melhora casos-alvo sem regressão global além da tolerância aprovada.
- CI real verde e query tenant-safe.
- Rollback da aplicação não depende de drop destrutivo imediato.

## Definition of Done

Hybrid Search testado, medido e documentado como uma mudança única.

## Riscos e cuidados

Configuração linguística e atualização do tsvector podem divergir. Medir latência e plano de consulta. Não duplicar o corpus em estrutura manual sem necessidade.

## Resultado esperado

Consultas exatas e semânticas coexistem com ganho mensurável.

## Instrução final ao Codex

Implemente somente Hybrid Search justificado pelos evals, compare resultados e pare.
