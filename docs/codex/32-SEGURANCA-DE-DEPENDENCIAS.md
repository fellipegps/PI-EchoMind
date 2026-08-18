# PR 32 — Segurança da cadeia de dependências

## Objetivo

Adicionar atualização automatizada e auditorias graduais para Python, pnpm e GitHub Actions sem tornar alertas transitivos não acionáveis um bloqueio cego.

## Contexto

A CI principal está estável após o MVP. Supply chain pode agora ganhar automação isolada do código de produto.

## Pré-requisitos

- PR 21 mergeada e checks estáveis.
- Escolher Dependabot ou Renovate conforme política do repositório; não instalar ambos sem motivo.

## Dependências

Obrigatórias: PR 21.

Não depende de: eval, retrieval avançado ou CD.

Paralelização: pode ocorrer com PRs 22, 27–31.

## Escopo desta PR

- Configurar updates de pip, pnpm e GitHub Actions com frequência/limites aprovados.
- Adicionar `pip-audit` e auditoria Node compatível ao CI, inicialmente em modo report quando necessário.
- Produzir artifacts/resumo sem lockfiles/secrets indevidos.
- Definir política documentada para promover alta/crítica aplicável a gate bloqueante.
- Testar/configurar majors de actions compatíveis com runner atual.

## Arquivos provavelmente envolvidos

- `.github/dependabot.yml` ou config Renovate
- `.github/workflows/ci.yml` ou workflow de security separado
- requirements-dev/package scripts se necessários
- README/docs de segurança

## Implementação

Separar falha de ferramenta de vulnerabilidade detectada. Pinning/lockfiles seguem padrões atuais. O primeiro merge estabelece visibilidade e política, não corrige todas as dependências do projeto no mesmo PR.

## Regras técnicas

- Sem auto-merge irrestrito.
- PRs de actions passam pelos mesmos checks.
- Não imprimir tokens/config privada.
- Severidade e aplicabilidade determinam gate, não contagem bruta.

## Não implementar nesta PR

- atualização massiva de todas as dependências;
- SAST/DAST amplo;
- assinatura de containers (não há containers da aplicação);
- provedor de segurança externo;
- mudanças de produto.

## Testes obrigatórios

- Validação da config de bot/workflow.
- Auditorias executam e produzem resultado interpretável.
- CI existente continua verde conforme política inicial.
- Lockfiles/install frozen permanecem reproduzíveis.

## Critérios de aceite

- Três ecossistemas recebem monitoramento controlado.
- Política de triagem/gate está documentada.
- Nenhum update massivo ou auto-merge inseguro entrou.

## Definition of Done

Automação e auditorias funcionam, com responsáveis/política claros e CI estável.

## Riscos e cuidados

Ruído excessivo faz alertas serem ignorados. Majors de actions podem exigir runner novo. Auditoria Node deve respeitar o gerenciador real.

## Resultado esperado

Dependências e actions passam a ter atualização e vulnerabilidades visíveis de modo sustentável.

## Instrução final ao Codex

Implemente somente automação/auditoria de supply chain e pare.
