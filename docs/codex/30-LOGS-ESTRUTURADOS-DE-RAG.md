# PR 30 — Logs estruturados de RAG e ingestão

## Objetivo

Padronizar logs estruturados de eventos, tenant pseudonimizado, etapas, latência, candidatos e falhas sem conteúdo sensível.

## Contexto

Antes de criar métricas/dashboard, os eventos precisam de schema estável. Logs não devem registrar arquivos, prompts ou respostas integrais por padrão.

## Pré-requisitos

- PR 21 mergeada.
- Definir política de privacidade/retenção e destino atual de logs; se ausente, implementar apenas schema/local output seguro.

## Dependências

Obrigatórias: PR 21.

Não depende de: retrieval avançado ou CD.

Paralelização: pode ocorrer com PRs 22, 27–29 e 32; PR 31 depende dela.

## Escopo desta PR

- Definir eventos estruturados para ingestão, retrieval/chat e erros.
- Incluir correlation ID, tenant pseudonimizado/ID conforme política, source types, contagens e durações.
- Excluir conteúdo textual, tokens, nomes sensíveis e stack trace de resposta pública.
- Instrumentar fronteiras sem mudar comportamento.
- Testar schema, redaction e níveis.

## Arquivos provavelmente envolvidos

- módulo de logging/config
- ingestion/RAG/API em pontos mínimos
- testes de observabilidade
- `.env.example`/README

## Implementação

Usar logger existente se houver. Medição de tempo deve ser monotônica. Exceções internas podem incluir stack no sink autorizado, mas payload estruturado testado deve evitar dados do documento/pergunta.

## Regras técnicas

- Não registrar secrets, headers Authorization ou bytes.
- Não transformar tenant em dimensão sem limite no futuro sem política.
- Logging não pode quebrar request.
- Schema versionado/estável para PR 31.

## Não implementar nesta PR

- dashboard/métricas agregadas;
- provedor externo de logs/APM;
- tracing distribuído completo;
- analytics de conteúdo;
- mudança de retrieval.

## Testes obrigatórios

- Eventos sucesso/erro têm campos obrigatórios.
- Durações/contagens coerentes.
- Secrets, conteúdo e Authorization são redigidos/ausentes.
- Falha do logger não altera resposta principal.
- Tenant/correlation não cruzam requests.

## Critérios de aceite

- Operação consegue diagnosticar etapa/latência sem expor conteúdo.
- Schema é consumível por métricas futuras.
- Regressão funcional ausente.

## Definition of Done

Instrumentação mínima, testes de privacidade e documentação verdes.

## Riscos e cuidados

Logs estruturados podem virar vetor de vazamento/custo. Evitar alta cardinalidade e texto livre. Não presumir fornecedor externo.

## Resultado esperado

Falhas e latência do pipeline ficam observáveis de forma segura.

## Instrução final ao Codex

Implemente apenas logs estruturados e redaction. Não crie dashboard. Pare.
