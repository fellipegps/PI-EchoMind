# PR 22 — Dataset e runner de avaliação RAG

## Objetivo

Criar um dataset inicial versionado e um runner reproduzível que estabeleça baseline de qualidade, recusa, fonte e latência do RAG pós-MVP.

## Contexto

Técnicas avançadas só têm valor se comparadas a um corpus e perguntas reais/sintéticas representativas. Esta fase mede; não otimiza.

## Pré-requisitos

- PR 21 mergeada.
- Corpus de avaliação aprovado e anonimizado, sem dados pessoais/sigilosos.

## Dependências

Obrigatórias: PR 21.

Não depende de: CD ou hardening.

Paralelização: PRs 27–30/32 podem ocorrer em paralelo; PR 23 aguarda o baseline.

## Escopo desta PR

- Criar 20–30 casos iniciais de datas, números, requisitos, exceções, recusa, vigente/vencido e fonte.
- Definir formato com pergunta, resposta/regras esperadas, tenant/corpus de fixture e expectativa de recusa/citação.
- Criar `scripts/eval_rag.py` ou equivalente.
- Medir similaridade semântica, revisão/heurística explícita de correção, recusa correta, presença de fonte e latência.
- Produzir relatório versionável/máquina-legível e instruções de execução.
- Registrar baseline sem alterar threshold/retrieval.

## Arquivos provavelmente envolvidos

- `echomind-backend/scripts/eval_rag.py`
- `echomind-backend/evals/` com dataset sintético
- testes unitários do scorer/loader
- `README.md` ou docs de eval

## Implementação

Separar execução offline determinística de qualquer modo opcional com LLM. Se um serviço externo for necessário para avaliação humana/semântica, exigir configuração explícita e nunca rodá-lo na CI padrão.

## Regras técnicas

- ROUGE/BLEU não são métrica única.
- Dataset diferencia “deve responder” e “deve recusar”.
- Resultados incluem versão/configuração do retrieval.
- Não ajustar código para melhorar números nesta PR.

## Não implementar nesta PR

- novo threshold;
- Hybrid Search/reranker/Parent-Child;
- geração automática de resposta esperada;
- gate bloqueante sem baseline estável;
- CD/analytics de produto.

## Testes obrigatórios

- Validação de schema e duplicatas do dataset.
- Scorers em exemplos conhecidos.
- Runner sem rede com respostas/embeddings fake.
- Relatório contém todas as métricas e falhas por caso.
- Suíte rápida relevante.

## Critérios de aceite

- Baseline completo é reproduzível e não altera comportamento de produção.
- Casos cobrem fonte, validade e recusa.
- Dados são sintéticos/aprovados.

## Definition of Done

Dataset, runner, testes e baseline documentados; nenhuma otimização implementada.

## Riscos e cuidados

Métrica automática pode premiar texto parecido e incorreto. Manter campo de revisão humana e rastreabilidade. Evitar dataset contaminado por conteúdo sensível.

## Resultado esperado

Próximas mudanças de retrieval têm um ponto de comparação objetivo.

## Instrução final ao Codex

Implemente apenas infraestrutura/dataset de avaliação e registre o baseline. Pare.
