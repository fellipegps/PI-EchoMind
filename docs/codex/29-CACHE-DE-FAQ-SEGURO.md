# PR 29 — Matching seguro do cache de FAQ

## Objetivo

Substituir o matching por substring de `find_cached_faq_answer` por uma estratégia mais segura e mensurada, sem alterar o retrieval principal.

## Contexto

Substring pode retornar FAQ errada por coincidência parcial. O hardening deve isolar essa correção do restante do RAG.

## Pré-requisitos

- PR 21 mergeada.
- Catalogar testes/comportamento atual do cache e falsos positivos representativos.

## Dependências

Obrigatórias: PR 21.

Não depende de: PRs 22–28 ou CD.

Paralelização: pode ocorrer com PRs 22, 27–28, 30 e 32.

## Escopo desta PR

- Definir normalização e estratégia de match aprovada (exata/fuzzy limitada ou equivalente).
- Estabelecer threshold apenas para cache com dataset de casos positivo/negativo.
- Manter tenant-scoping e fallback para pipeline RAG quando não houver confiança.
- Testar acentos, caixa, pontuação, substrings perigosas e perguntas distintas.
- Medir impacto de hit/falso positivo.

## Arquivos provavelmente envolvidos

- CRUD/serviço que contém `find_cached_faq_answer`
- config se necessária
- testes de FAQ/chat
- documentação de decisão

## Implementação

Preferir “não usar cache” em caso ambíguo. Não incorporar biblioteca pesada sem evidência. O fallback não deve duplicar resposta ou registrar hit falso.

## Regras técnicas

- Tenant é sempre parte da consulta.
- Cache nunca atravessa tenants.
- Estratégia é determinística/testável.
- Não reutilizar `SIMILARITY_THRESHOLD` vetorial sem justificativa.

## Não implementar nesta PR

- Hybrid Search/reranker;
- novo cache distribuído;
- analytics/dashboard;
- mudança de prompt/embedding;
- UI/CD.

## Testes obrigatórios

- Match exato normalizado.
- Variações aceitáveis definidas.
- Substring curta/ambígua não retorna resposta.
- Acentos, caixa e pontuação.
- Tenant isolado.
- Miss cai no RAG atual.

## Critérios de aceite

- Falsos positivos conhecidos deixam de ocorrer.
- Hits válidos essenciais permanecem dentro da tolerância.
- Nenhuma outra etapa do RAG muda.

## Definition of Done

Matching, testes e métricas de comparação documentados com CI verde.

## Riscos e cuidados

Fuzzy excessivo repete o problema; estrito excessivo reduz cache, mas é mais seguro que resposta errada. Não otimizar sem casos reais/sintéticos.

## Resultado esperado

O cache só responde quando a correspondência é suficientemente confiável.

## Instrução final ao Codex

Implemente apenas o matching seguro de cache, compare e pare.
