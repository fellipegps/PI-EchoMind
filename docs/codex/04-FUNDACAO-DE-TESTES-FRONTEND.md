# PR 04 — Fundação de testes do frontend

## Objetivo

Instalar e configurar Vitest, Testing Library, jest-dom e jsdom, incluindo o novo gate no job frontend, sem implementar a aba Documentos.

## Contexto

O frontend só possui lint/build. Os testes precisam existir antes do cliente multipart e dos estados da aba real.

## Pré-requisitos

- PR 01 mergeada.
- Confirmar versão React/Next, pnpm e convenções de aliases existentes.

## Dependências

Obrigatórias: PR 01.

Não depende de: backend documental.

Paralelização: pode ocorrer em paralelo com PRs 02–03 e 05–18; PR 19 aguarda esta fase.

## Escopo desta PR

- Adicionar dependências de teste compatíveis com o projeto.
- Configurar Vitest/jsdom, setup de jest-dom e resolução de aliases.
- Adicionar scripts `test`, `test:run`, `test:coverage` e `typecheck`.
- Criar um teste mínimo de infraestrutura sobre comportamento já existente, sem snapshot vazio.
- Atualizar `Frontend / quality-build` para lint, typecheck, `test:run` e build.

## Arquivos provavelmente envolvidos

- `echomind-front/package.json`
- lockfile pnpm
- configuração Vitest
- arquivo de setup de testes
- um teste mínimo de componente/utilitário existente
- `.github/workflows/ci.yml`

## Implementação

A configuração deve funcionar no modo não interativo da CI e não depender de navegador real, Supabase real ou backend. Reutilizar aliases/configuração TypeScript já existentes.

## Regras técnicas

- `test:run` deve terminar sozinho na CI.
- Evitar snapshots sem assertions de comportamento.
- Não relaxar lint/typecheck/build para acomodar o runner.
- Não adicionar cobertura bloqueante de frontend antes de medir a base.

## Não implementar nesta PR

- `documentApi`;
- `KnowledgeDocument`;
- upload multipart;
- alteração de `document-tab.tsx`;
- Playwright/E2E;
- backend ou deploy.

## Testes obrigatórios

- `corepack pnpm lint`.
- `corepack pnpm typecheck`.
- `corepack pnpm test:run`.
- `corepack pnpm build`.
- Jobs rápidos completos da CI.

## Critérios de aceite

- Runner funciona localmente e na CI.
- Teste mínimo prova renderização/interação real e é determinístico.
- Nenhuma funcionalidade documental foi introduzida.

## Definition of Done

Gate frontend verde com testes não interativos e documentação de comandos atualizada.

## Riscos e cuidados

Configuração ESM, aliases e APIs do Next podem exigir mocks mínimos. Não criar uma camada extensa de mocks antes de haver necessidade.

## Resultado esperado

As PRs de frontend posteriores conseguem nascer com testes próprios.

## Instrução final ao Codex

Implemente só o ambiente de testes, valide os quatro comandos e pare.
