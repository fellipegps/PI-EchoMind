# PR 25 — Reranker de candidatos

## Objetivo

Adicionar reranking cross-encoder sobre um conjunto limitado de candidatos híbridos, medindo qualidade e latência.

## Contexto

Hybrid Search amplia candidatos. O reranker deve apenas reordená-los, sem alterar ingestão, schema documental ou prompt.

## Pré-requisitos

- PR 24 mergeada com eval comparativo.
- Aprovar modelo, licença, tamanho e estratégia de execução/cache antes de adicionar dependência.

## Dependências

Obrigatórias: PR 24.

Não depende de: Parent-Child/CD.

Paralelização: sequencial; PR 26 depende do ranking estabilizado.

## Escopo desta PR

- Criar interface de reranker injetável e implementação aprovada.
- Reordenar top 10–15 candidatos e retornar top K final.
- Configurar ativação/limites e fallback explícito em falha.
- Preservar tenant, metadata, validade e fontes.
- Mockar modelo na CI e testar ordenação; executar eval controlado real fora do gate quando necessário.
- Medir ganho e impacto de latência.

## Arquivos provavelmente envolvidos

- módulo RAG/reranker novo ou existente
- requirements/config/.env.example
- testes unitários/integration
- eval reports/documentação

## Implementação

A interface separa pontuação do restante do retrieval. O fallback deve manter ranking híbrido anterior e gerar observabilidade, sem derrubar chat.

## Regras técnicas

- Não baixar modelo/rede durante testes comuns.
- Limitar número/tamanho dos candidatos.
- Não alterar conteúdo/metadata ao reordenar.
- Toda decisão de dependência/licença fica registrada.

## Não implementar nesta PR

- Parent-Child;
- context compression/query expansion/HyDE;
- novo embedding;
- mudança de chunking/prompt;
- UI/CD.

## Testes obrigatórios

- Interface/fake ordena pontuações conhecidas.
- Fallback em timeout/erro.
- Limite de candidatos e top K.
- Validade/tenant/fonte preservados.
- Eval antes/depois e latência reportada.
- Suítes rápidas e integration aplicável.

## Critérios de aceite

- Ganho mensurável justifica custo/latência ou a mudança é revertida.
- Falha do reranker degrada para PR 24, não derruba o serviço.
- Nenhuma técnica futura incluída.

## Definition of Done

Reranker isolado, testado, observável e comparado ao baseline híbrido.

## Riscos e cuidados

Dependência pesada pode aumentar startup/memória. Licença e download são decisões de produção. Dataset pequeno pode superestimar ganho.

## Resultado esperado

Os melhores candidatos híbridos chegam ao contexto em ordem mais relevante.

## Instrução final ao Codex

Implemente exclusivamente o reranker aprovado, avalie e pare.
