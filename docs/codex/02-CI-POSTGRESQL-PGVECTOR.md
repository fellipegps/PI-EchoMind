# PR 02 — CI de integração PostgreSQL/pgvector

## Objetivo

Adicionar um gate de integração real que valide PostgreSQL, extensão pgvector, Alembic e testes marcados como `integration` em infraestrutura descartável.

## Contexto

SQLite e mocks não exercitam tipos, migrations ou PGVector reais. Esta PR cria a fundação do banco de CI antes da migration documental.

## Pré-requisitos

- PR 01 mergeada e verde.
- Confirmar o major PostgreSQL do projeto Supabase antes de escolher a tag pgvector.
- Se o major não puder ser confirmado no repositório/configuração autorizada, parar e pedir a decisão; não adivinhar.

## Dependências

Obrigatórias: PR 01.

Não depende de: schema ou ingestão de documentos.

Paralelização: pode ser preparada em paralelo à PR 03 após a PR 01, mas deve mergear antes da PR 05.

## Escopo desta PR

- Adicionar o check estável `Database / migration-integration`.
- Subir service container PostgreSQL + pgvector descartável com healthcheck e credenciais efêmeras.
- Executar `CREATE EXTENSION IF NOT EXISTS vector`, `alembic upgrade head` e validar revision=head.
- Declarar markers `integration` e `e2e` sem alterar a classificação dos testes rápidos existentes.
- Criar harness/fixtures de banco real e migration smoke para o head atual.
- Documentar reprodução local sem tornar Docker requisito da aplicação.

## Arquivos provavelmente envolvidos

- `.github/workflows/ci.yml` ou `.github/workflows/integration.yml`
- `echomind-backend/pytest.ini`
- `echomind-backend/tests/integration/conftest.py`
- `echomind-backend/tests/integration/test_migrations.py`
- `README.md`

## Implementação

O job deve aguardar o banco, instalar dependências, criar a extensão, migrar um banco vazio e executar apenas `pytest -m integration`. O teste inicial verifica head atual, extensão e tabelas já existentes; assertions de `documents` entram somente na PR 05.

## Regras técnicas

- Banco e credenciais são exclusivos da execução e destruídos ao final.
- Nunca usar `DATABASE_URL` de staging/produção.
- Não depender de `Base.metadata.create_all()` para validar migrations.
- Embeddings/LLM externos não são chamados.
- Docker é autorizado aqui apenas para o banco descartável.

## Não implementar nesta PR

- `documents`/`document_chunks`;
- indexação documental;
- downgrade automático de produção;
- Dockerfile de FastAPI/Next.js;
- Compose da aplicação;
- deploy ou E2E.

## Testes obrigatórios

- Banco vazio aceita `alembic upgrade head`.
- Revision após upgrade é exatamente head.
- Extensão `vector` está disponível.
- Marker rápido exclui integração; marker integration seleciona somente banco real.
- Jobs da PR 01 continuam verdes.

## Critérios de aceite

- `Database / migration-integration` passa de forma determinística.
- Nenhum serviço externo ou banco persistente foi usado.
- A versão PostgreSQL escolhida está justificada por evidência do projeto.

## Definition of Done

Três checks estáveis verdes, instruções locais documentadas e infraestrutura descartada ao fim do job.

## Riscos e cuidados

Tags erradas podem divergir do Supabase. Healthcheck frágil gera flakiness. Não transformar um downgrade de CI em política de rollback de produção.

## Resultado esperado

Migrations e integração vetorial futuras passam a ter um ambiente real e repetível.

## Instrução final ao Codex

Implemente somente a fundação de integração atual, sem schema de documentos. Rode os gates, relate os resultados e pare.
