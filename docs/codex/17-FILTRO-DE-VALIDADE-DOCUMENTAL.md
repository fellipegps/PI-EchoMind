# PR 17 — Filtro de validade documental

## Objetivo

Excluir documentos vencidos do contexto final e compensar o pós-filtro com overfetch controlado, preservando ranking e top K.

## Contexto

`valid_until` já está na metadata. Filtrar depois do retrieval pode reduzir candidatos; por isso a busca inicial precisa trazer mais resultados sem introduzir Hybrid Search.

## Pré-requisitos

- PR 16 mergeada.
- Datas em metadata serializadas de forma estável pela PR 12.

## Dependências

Obrigatórias: PR 16.

Não depende de: frontend, eval ou Hybrid Search.

Paralelização: deve ser sequencial à PR 16 porque altera o mesmo pipeline.

## Escopo desta PR

- Calcular `candidate_k = max(TOP_K_DOCS * 3, 10)` ou equivalente configurado/testado.
- Aplicar threshold existente, excluir somente `document_chunk` vencido, preservar candidatos válidos e ordenar por distância.
- Cortar nos primeiros `TOP_K_DOCS` após filtro.
- Definir comportamento de data igual a hoje e timezone/data local de forma explícita.
- Testar corpus misto com vencidos, vigentes, sem validade, FAQ e evento.

## Arquivos provavelmente envolvidos

- `echomind-backend/app/rag_engine.py`
- testes unitários de retrieval
- `echomind-backend/tests/integration/test_document_pgvector.py`

## Implementação

Usar uma fonte de “hoje” injetável/congelável nos testes. Metadata inválida deve ser tratada de forma segura e observável, sem derrubar chat nem aceitar silenciosamente como vigente sem política explícita.

## Regras técnicas

- Manter `SIMILARITY_THRESHOLD=0.45` até PR 23.
- Vencimento só se aplica quando `valid_until` existe e é anterior à data atual.
- FAQ/evento não são removidos por ausência desse campo.
- Ranking final respeita distância original.

## Não implementar nesta PR

- calibração de threshold;
- full-text/Hybrid Search;
- reranker;
- Parent-Child;
- mudanças de prompt/citação além de ajustes indispensáveis;
- frontend.

## Testes obrigatórios

- Documento ontem é excluído; hoje/futuro é mantido conforme regra.
- Documento sem validade é mantido.
- Overfetch repõe candidatos e top K final é respeitado.
- Ordenação por distância permanece.
- Tenant A/B continuam isolados.
- FAQ/evento continuam no contexto.

## Critérios de aceite

- Nenhum chunk vencido entra no contexto final.
- O pós-filtro não reduz desnecessariamente respostas quando há candidatos válidos.
- Integração real verde.

## Definition of Done

Filtro, overfetch e casos de data estão cobertos, sem técnica avançada antecipada.

## Riscos e cuidados

Comparar datetime e date pode gerar off-by-one/timezone. Metadata corrompida deve produzir log/decisão estável. Overfetch excessivo aumenta latência; manter limite previsto.

## Resultado esperado

O chat deixa de fundamentar resposta em documento explicitamente vencido.

## Instrução final ao Codex

Implemente apenas validade e overfetch. Rode os testes e pare.
