# PR 31 — Métricas RAG no dashboard

## Objetivo

Agregar e apresentar métricas operacionais essenciais de ingestão/retrieval usando o schema de eventos da PR 30, sem analytics avançado.

## Contexto

O dashboard atual existe. A mudança deve ser incremental e baseada em métricas aprovadas, não em armazenamento de prompts/respostas.

## Pré-requisitos

- PR 30 mergeada.
- Definir origem/retenção das agregações e quem pode vê-las.

## Dependências

Obrigatórias: PR 30.

Não depende de: PRs 24–26 ou CD.

Paralelização: pode ocorrer com PR 32, evitando conflitos de frontend/config.

## Escopo desta PR

- Definir métricas mínimas: volume/status de ingestão, erro, latência de processamento/retrieval, taxa sem resposta e source types.
- Criar agregação tenant-scoped e endpoint administrativo conforme arquitetura atual.
- Estender componentes existentes do dashboard com estados loading/empty/error.
- Limitar período/cardinalidade e não retornar dados de outro tenant.
- Testar agregação, autorização e visualização.

## Arquivos provavelmente envolvidos

- models/migration somente se armazenamento for aprovado
- repository/API dashboard
- componentes/tipos frontend existentes
- testes backend/frontend

## Implementação

Reutilizar padrões do dashboard. Se a arquitetura de armazenamento não estiver definida, parar antes de criar tabela/event store improvisado. Métricas devem ser agregadas e não conter texto de usuário/documento.

## Regras técnicas

- Tenant-scoping em cada agregação.
- Sem PII/conteúdo livre.
- Queries com limites/índices adequados.
- Não misturar eval offline com analytics operacional.

## Não implementar nesta PR

- A/B testing;
- relatórios por e-mail;
- funil avançado/BI externo;
- alertas/on-call;
- provedor de observabilidade;
- mudanças de retrieval.

## Testes obrigatórios

- Agregações conhecidas por período/status.
- Tenant A não vê B.
- Autenticação/autorização.
- Empty/loading/error e números no frontend.
- Migração/integration se houver nova persistência.
- Lint/typecheck/test/build.

## Critérios de aceite

- Administrador vê métricas operacionais mínimas e corretas.
- Privacidade/cardinalidade estão controladas.
- Dashboard atual não é redesenhado amplamente.

## Definition of Done

Backend/frontend e testes aplicáveis verdes, decisão de armazenamento documentada.

## Riscos e cuidados

Agregações sem índice degradam banco. Métricas podem reidentificar usuário em volume baixo; limitar granularidade. Não inventar infra externa.

## Resultado esperado

Operação acompanha saúde do RAG sem inspecionar conteúdo sensível.

## Instrução final ao Codex

Implemente apenas métricas operacionais aprovadas; se armazenamento não estiver definido, pare bloqueado.
