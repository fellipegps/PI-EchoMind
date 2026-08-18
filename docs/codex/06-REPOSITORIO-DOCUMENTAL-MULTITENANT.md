# PR 06 — Repositório documental multi-tenant

## Objetivo

Encapsular operações relacionais de documentos/chunks, deduplicação e transições de status com filtro de tenant obrigatório, sem expor HTTP.

## Contexto

Models sozinhos não impedem consultas incompletas. A API e o processador devem consumir funções pequenas e testáveis que nunca busquem apenas por `document_id`.

## Pré-requisitos

- PR 05 mergeada.
- Entender o padrão real de `crud.py`, sessões e `current_user.id`.

## Dependências

Obrigatórias: PR 05.

Não depende de: extractors, PGVector, endpoints ou frontend.

Paralelização: deve mergear antes das PRs 07, 13 e 14.

## Escopo desta PR

- Criar funções tenant-scoped para criar, listar, obter e remover registros relacionais.
- Consultar duplicidade por `(tenant_id, sha256)` somente nos estados `pending`, `processing` ou `ready`.
- Persistir chunks em ordem e atualizar `chunk_count` de forma atômica.
- Definir transições permitidas `pending → processing → ready|error` e campos associados.
- Impedir exclusão relacional em `pending/processing` no contrato de domínio.
- Testar tenants distintos, transições, rollback de sessão e cascade.

## Arquivos provavelmente envolvidos

- `echomind-backend/app/crud.py` ou módulo de repository conforme padrão atual
- schemas/exceções de domínio estritamente necessárias
- testes unitários de CRUD/repository

## Implementação

Toda função que recebe ID também recebe tenant e filtra os dois. Mensagens de erro externas não fazem parte desta PR; retornar resultados/erros de domínio que a API poderá mapear. Não commitar parcialmente lista de chunks.

## Regras técnicas

- Nenhum `get(document_id)` sem tenant.
- Mesmo hash em tenants distintos é permitido.
- `error_message` deve ser curta e `processed_at` só refletir conclusão.
- Não acoplar repository a FastAPI, UploadFile ou RAGEngine.

## Não implementar nesta PR

- validação de arquivo;
- parser/chunking;
- PGVector;
- rotas e BackgroundTasks;
- frontend;
- RLS nova além do schema já criado.

## Testes obrigatórios

- create/list/get isolam tenants.
- Mesmo ID/hash não atravessa tenant.
- Duplicidade por estado segue a regra.
- Transições válidas funcionam; transições inválidas falham sem commit parcial.
- Persistência de chunks mantém ordem/unicidade e `chunk_count`.
- Exclusão em processamento é rejeitada; cascade relacional é exercitado.

## Critérios de aceite

- API futura pode usar o repository sem montar queries tenant-scoped próprias.
- Nenhuma mudança em vetores ou HTTP.
- Testes rápidos verdes.

## Definition of Done

Operações relacionais e invariantes multi-tenant estão cobertas e documentadas por testes.

## Riscos e cuidados

Evitar commits dentro de helpers quando o chamador precisa de transação maior. Não vazar existência de documento de outro tenant por exceções distintas.

## Resultado esperado

Uma camada relacional segura e reutilizável prepara validação, processamento e API.

## Instrução final ao Codex

Implemente só o repository e seus testes; não abra rotas nem toque no vector store. Pare.
