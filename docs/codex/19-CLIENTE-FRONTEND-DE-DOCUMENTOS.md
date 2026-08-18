# PR 19 — Cliente frontend de documentos

## Objetivo

Criar tipos e cliente HTTP para list/get/upload/delete, incluindo multipart sem `Content-Type` manual, antes de alterar a UI.

## Contexto

O helper `request()` atual força JSON. O contrato backend está estável; separar o cliente permite testar autenticação, FormData e erros sem estados visuais.

## Pré-requisitos

- PRs 04, 14 e 15 mergeadas.
- Confirmar forma atual de obter token e tratar 401.

## Dependências

Obrigatórias: PR 04, PR 14 e PR 15.

Não depende de: PRs 16–18 para a UI administrativa básica.

Paralelização: pode ocorrer em paralelo com PR 18; PR 20 aguarda esta fase.

## Escopo desta PR

- Definir `KnowledgeDocument`, status e metadata alinhados ao OpenAPI real.
- Criar `documentApi.list`, `get`, `upload` e `delete`.
- Implementar helper multipart que adiciona Bearer, não define `Content-Type` e preserva 401/erros seguros.
- Montar `FormData` com arquivo e metadata opcional no formato esperado.
- Testar requests, headers, serialização e mensagens de erro.

## Arquivos provavelmente envolvidos

- `echomind-front/lib/api.ts`
- arquivo de tipos existente ou `base-de-conhecimento/types.ts`
- `echomind-front/lib/api.test.ts`

## Implementação

Reutilizar tratamento comum de resposta/autenticação sem fazer o helper JSON aceitar FormData por hacks. O browser deve definir boundary. Não iniciar polling no cliente de baixo nível.

## Regras técnicas

- Tipos refletem nullability e status reais.
- Nunca enviar tenant ID.
- Nunca expor detalhes brutos inseguros de erro.
- Não definir `multipart/form-data` manualmente.

## Não implementar nesta PR

- alteração de `document-tab.tsx`;
- polling/drag-and-drop/toasts;
- validação visual de formato/tamanho;
- frontend de fontes do chat;
- mudança backend;
- E2E.

## Testes obrigatórios

- List/get/delete usam método, URL e Authorization corretos.
- Upload cria FormData com arquivo/metadata.
- Header `Content-Type` não é definido no upload.
- 401 segue tratamento atual.
- 4xx/5xx viram mensagem segura.
- Lint, typecheck, test:run e build.

## Critérios de aceite

- Cliente representa exatamente o contrato backend.
- Multipart deixa boundary ao browser.
- Nenhuma UI foi alterada.

## Definition of Done

Tipos/cliente e testes verdes em todos os gates do frontend.

## Riscos e cuidados

Objetos `File/FormData` no jsdom precisam de mocks realistas. Não testar detalhes internos irrelevantes; testar request observável.

## Resultado esperado

A aba existente pode consumir uma API pequena, segura e já testada.

## Instrução final ao Codex

Implemente somente tipos e cliente API. Não conecte a UI. Pare.
