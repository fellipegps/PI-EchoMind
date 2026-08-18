# PR 14 — API de consulta e exclusão de documentos

## Objetivo

Expor `GET /documents`, `GET /documents/{id}` e `DELETE /documents/{id}` autenticados, tenant-scoped e testados, sem endpoint de upload.

## Contexto

Separar leitura/exclusão do multipart reduz a superfície da PR e estabiliza contratos que o frontend consumirá.

## Pré-requisitos

- PRs 06 e 12 mergeadas.
- Inspecionar autenticação/router e convenções de erro reais.

## Dependências

Obrigatórias: PR 06 e PR 12.

Não depende de: PR 13 ou upload/background.

Paralelização: pode ocorrer em paralelo com PR 13; PRs 15 e 19 dependem dela.

## Escopo desta PR

- Criar router administrativo `/documents` no padrão existente.
- Listar documentos do usuário autenticado, mais recentes primeiro.
- Obter documento/status pelo par ID + tenant.
- Excluir documento não `pending/processing`, removendo vetores e registro/chunks com compensação/erro coerente.
- Mapear documento inexistente ou de outro tenant para o mesmo `404`.
- Testar autenticação, isolamento, ordenação, resposta e `409` em processamento.

## Arquivos provavelmente envolvidos

- `echomind-backend/app/main.py` ou router modular existente
- schemas/repository estritamente necessários
- `echomind-backend/tests/test_documents.py`
- `echomind-backend/tests/conftest.py` para FakeRAGEngine

## Implementação

Tenant vem exclusivamente de `current_user.id`. O DELETE coordena delete vetorial tenant-scoped e relacional; em erro, não informar sucesso falso. Seguir status codes/shape padrão do projeto.

## Regras técnicas

- Nunca aceitar tenant em query/body.
- Outro tenant é indistinguível de inexistente.
- Não excluir enquanto `pending` ou `processing`.
- FakeRAGEngine deve refletir somente métodos necessários desta PR.

## Não implementar nesta PR

- `POST /documents/upload`;
- multipart/validação de arquivo;
- BackgroundTasks/processamento;
- citações/validade;
- frontend;
- soft delete/job table.

## Testes obrigatórios

- Falta/invalidade de autenticação.
- Lista vazia, ordenada e isolada.
- GET próprio e 404 cross-tenant.
- DELETE próprio remove chunks/vetores/registro.
- DELETE cross-tenant retorna 404.
- DELETE pending/processing retorna 409.
- Erro vetorial não produz 2xx enganoso.

## Critérios de aceite

- Três endpoints funcionam sem upload.
- Contrato é estável e multi-tenant.
- Suíte rápida e integração vetorial aplicável verdes.

## Definition of Done

API de leitura/exclusão testada, documentação de contrato atualizada se o projeto a mantiver, sem funcionalidades futuras.

## Riscos e cuidados

Ordem de delete entre dois stores pode falhar parcialmente; usar idempotência/compensação existentes e testar retry. Não revelar ID válido de outro tenant.

## Resultado esperado

Backend oferece consulta/status e exclusão reais antes do upload.

## Instrução final ao Codex

Implemente somente GET/GET/DELETE e pare. Não crie upload.
