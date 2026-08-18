# PR 01 — CI rápida e baseline de qualidade

## Objetivo

Criar a primeira esteira automatizada de Pull Request para backend e frontend, medir a cobertura atual sem inventar meta e estabelecer checks rápidos e estáveis.

## Contexto

O projeto não possui `.github/workflows`. O backend já tem pytest rápido com SQLite/mocks; o frontend já possui lint e build, mas ainda não tem testes. Esta PR deve refletir exatamente essa capacidade atual.

## Pré-requisitos

- Ler `AGENTS.md` e `docs/codex/00-PLANO-GERAL.md`.
- Confirmar Python 3.12, Node 20+ e o gerenciador/lockfile existentes.
- Rodar as suítes locais atuais e registrar falhas preexistentes.

## Dependências

Obrigatórias: nenhuma.

Não depende de: PRs 02–35.

Paralelização: é a fundação; deve ser mergeada antes das demais.

## Escopo desta PR

- Criar `.github/workflows/ci.yml` com triggers de PR, `main` e manual.
- Adicionar concorrência com cancelamento por branch/PR e `permissions: contents: read`.
- Criar jobs estáveis `Backend / unit-api` e `Frontend / quality-build`.
- Adicionar `pytest-cov`, medir a cobertura e fixar `--cov-fail-under` no baseline observado, sem arredondar para cima.
- Gerar `coverage.xml` e, se útil, artifact sem segredos.
- Executar frontend com install frozen, lint, `tsc --noEmit` e build.
- Documentar os comandos locais equivalentes e o baseline medido.

## Arquivos provavelmente envolvidos

- `.github/workflows/ci.yml` (novo)
- `echomind-backend/requirements-dev.txt`
- configuração pytest existente ou `echomind-backend/pytest.ini`
- `README.md`

## Implementação

Usar actions oficiais em majors suportados no momento da execução, cacheando pip pelas requirements e pnpm pelo lockfile. Usar variáveis dummy apenas quando o build exigir valores públicos. O workflow deve sempre executar os dois jobs inicialmente; otimização por paths fica para depois da estabilidade.

## Regras técnicas

- Não chamar Groq, Supabase ou banco externo.
- Não expor secrets a eventos de PR.
- O gate de cobertura impede regressão abaixo da base real; não exige 80% global arbitrário.
- Nomes dos jobs são contrato para futura branch protection.
- Build frontend nunca recebe chave secreta do Supabase.

## Não implementar nesta PR

- PostgreSQL/pgvector em CI;
- migrations de documentos;
- Vitest/Testing Library;
- ingestão, API ou frontend de documentos;
- branch protection externa;
- deploy/CD;
- Dockerfile ou Compose.

## Testes obrigatórios

- `pytest -m "not integration and not e2e"` com cobertura e gate medido.
- `corepack pnpm install --frozen-lockfile`.
- `corepack pnpm lint`.
- `corepack pnpm exec tsc --noEmit`.
- `corepack pnpm build`.
- Validação sintática do workflow disponível no projeto, quando houver ferramenta.

## Critérios de aceite

- Os dois jobs executam em PR e `main` com nomes estáveis.
- A base atual passa sem serviços externos.
- A cobertura está registrada e não pode cair abaixo do valor observado.
- Nenhum segredo, imagem de aplicação ou funcionalidade de documentos foi adicionado.

## Definition of Done

CI verde, documentação atualizada, comandos reproduzíveis localmente e lista final de arquivos/testes apresentada.

## Riscos e cuidados

Variáveis ausentes podem mascarar falhas do build; fornecer apenas dummies públicas e documentadas. Não aumentar o baseline de cobertura sem testes reais. Não copiar majors obsoletos de actions.

## Resultado esperado

Todo PR recebe feedback rápido de backend e qualidade/build do frontend antes de merge.

## Instrução final ao Codex

Implemente exclusivamente esta fase, execute os testes acima, liste arquivos alterados e resultados, e pare. Não inicie a PR 02.
