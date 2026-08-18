# PR 23 — Calibração do threshold de similaridade

## Objetivo

Escolher e documentar um novo `SIMILARITY_THRESHOLD` com base no dataset da PR 22, equilibrando recuperação e falso positivo.

## Contexto

O valor 0.45 veio do embedding anterior e foi mantido deliberadamente até haver evidência. Esta PR altera apenas a calibração, não o método de retrieval.

## Pré-requisitos

- PR 22 mergeada com baseline reproduzível.
- Corpus/embedding da avaliação correspondem à configuração de produção planejada.

## Dependências

Obrigatórias: PR 22.

Não depende de: Hybrid Search, reranker ou CD.

Paralelização: não paralelizar com PR 24, que precisa do threshold calibrado.

## Escopo desta PR

- Executar sweep em faixa e passos declarados.
- Comparar recall/precisão, falso positivo e recusa correta, incluindo vigente/vencido.
- Selecionar valor por regra de decisão documentada.
- Atualizar default/config/example somente se o resultado justificar.
- Guardar relatório comparativo e teste de regressão dos casos críticos.

## Arquivos provavelmente envolvidos

- config/RAG onde threshold é definido
- `.env.example`
- script/dataset de eval
- relatório/documentação de calibração
- testes de retrieval

## Implementação

Automatizar a varredura sem treinar/trocar modelo. O relatório deve permitir reproduzir versão, valores e decisão. Se nenhum valor superar a base com segurança, manter 0.45 e registrar o resultado.

## Regras técnicas

- Não escolher olhando 1–2 perguntas.
- Não usar dados de produção sem autorização/anonimização.
- Manter top K e algoritmo constantes durante a comparação.
- Resultado “sem mudança” é válido.

## Não implementar nesta PR

- Hybrid Search;
- reranker;
- novo embedding;
- alteração de chunking;
- prompt tuning não relacionado;
- UI/deploy.

## Testes obrigatórios

- Sweep inclui limites e gera resultado determinístico sobre fixtures.
- Regra de seleção é testada.
- Casos críticos não regrediram além da tolerância documentada.
- Config/default e exemplos permanecem coerentes.

## Critérios de aceite

- Threshold escolhido ou mantido com evidência reproduzível.
- Relatório mostra trade-offs, não só média final.
- Nenhuma outra variável de retrieval mudou.

## Definition of Done

Calibração e testes documentados, eval comparativo arquivado e CI verde.

## Riscos e cuidados

Overfitting ao dataset pequeno é provável; documentar limite e reservar casos de validação quando viável. Não converter o eval em chamada externa obrigatória de CI.

## Resultado esperado

O limiar deixa de ser herança arbitrária do embedding antigo.

## Instrução final ao Codex

Calibre exclusivamente o threshold com o dataset existente e pare.
