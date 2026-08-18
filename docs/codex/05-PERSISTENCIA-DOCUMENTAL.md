# PR 05 — Persistência de documentos e chunks

## Objetivo

Criar a migration, models ORM e schemas de resposta para `documents` e `document_chunks`, com constraints, cascade e RLS multi-tenant.

## Contexto

O projeto não possui persistência documental. Os vetores continuam nas tabelas LangChain; as novas tabelas guardam estado, metadados e chunks auditáveis.

## Pré-requisitos

- PR 02 mergeada e migration smoke verde.
- Inspecionar os padrões reais de IDs, timestamps, RLS e migrations `0007`/`0008`.

## Dependências

Obrigatórias: PR 02.

Não depende de: extractors, RAG documental, API ou frontend.

Paralelização: não deve ocorrer com mudanças concorrentes no mesmo metadata/migration head.

## Escopo desta PR

- Criar revision após o head real (esperada `0009_documents.py` se ainda aplicável).
- Tabela `documents` com campos e estados definidos no plano geral.
- Tabela `document_chunks` com FK cascade e unicidade `(document_id, chunk_index)`.
- Índices para tenant e consultas necessárias; constraint de status e validações coerentes quando suportadas pelo padrão do projeto.
- RLS seguindo o padrão existente.
- Models ORM e schemas `DocumentStatus`, `DocumentResponse` e lista, sem rotas.
- Testes de migration do zero, constraints, relacionamentos, cascade, RLS e compatibilidade SQLite.

## Arquivos provavelmente envolvidos

- `echomind-backend/alembic/versions/0009_documents.py`
- `echomind-backend/app/database.py`
- `echomind-backend/app/schemas.py`
- `echomind-backend/tests/integration/test_migrations.py`
- testes unitários de models/schemas

## Implementação

Representar `pending | processing | ready | error` de forma consistente entre banco, ORM e schemas. `tenant_id`, filename, MIME, tamanho, SHA, status, contadores e timestamps seguem o documento original; metadados opcionais permanecem nulos. O downgrade pode remover apenas as estruturas criadas por esta revision e só é testado em CI se for seguro.

## Regras técnicas

- Não criar nova tabela vetorial.
- Não recriar `knowledge_documents`.
- Toda relação de chunk deve manter `tenant_id` explícito para defesa e consulta.
- Migrations de produção não dependem de `Base.metadata.create_all()`.
- Manter migration backward-compatible: apenas adicionar estruturas.

## Não implementar nesta PR

- funções CRUD/repository;
- extração/chunking;
- endpoints;
- background processing;
- indexação/exclusão PGVector;
- frontend;
- Docker/deploy.

## Testes obrigatórios

- `alembic upgrade head` em banco vazio.
- Revision == head, tabelas, colunas, índices, constraints e extensão presentes.
- FK/cascade e unicidade de chunk.
- Valores/estado inicial e serialização dos schemas.
- RLS/políticas conforme padrão do projeto.
- `Base.metadata.create_all()` continua funcionando em SQLite de testes.
- Suítes rápida e integration.

## Critérios de aceite

- Schema sobe limpo e isola a base para CRUD futuro.
- Nenhuma tabela vetorial paralela foi criada.
- Migration é pequena, aditiva e reversível em CI quando seguro.

## Definition of Done

Migration e models alinhados, testes de banco reais verdes e nenhum comportamento HTTP/RAG alterado.

## Riscos e cuidados

Tipos UUID/string e timezone devem seguir o projeto, não preferências novas. RLS mal copiada pode bloquear o backend ou vazar dados; testar com os papéis usados pelo projeto.

## Resultado esperado

Existe uma base relacional confiável para estado e chunks documentais, ainda sem ingestão.

## Instrução final ao Codex

Implemente somente schema/models/schemas e seus testes. Não crie CRUD, rotas ou parsers. Pare após validar.
