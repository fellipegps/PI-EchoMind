# PR 35 — Promoção protegida de produção (bloqueada)

## Objetivo

Criar promoção explícita para produção de uma versão já validada em staging, com environment protegido, aprovação manual, migration e smoke não destrutivo.

## Contexto

Produção não deve receber automaticamente cada commit da `main`. O workflow depende do provedor real e de uma estratégia de release aprovada.

## Pré-requisitos

- PRs 33 e 34 mergeadas e staging estável.
- Decisão entre tag/release ou `workflow_dispatch`, versionamento, aprovadores e rollback.
- GitHub Environment `production` protegido e secrets configurados por administradores.
- Backup/restore e política de migration aprovados.

## Dependências

Obrigatórias: PR 33, PR 34 e decisões externas de release/produção.

Não depende de: PRs 22–32, salvo exigência formal da equipe.

Paralelização: não; é a etapa final da cadeia de CD.

## Escopo desta PR

- Criar `.github/workflows/deploy-production.yml` no gatilho aprovado.
- Verificar que a mesma versão passou staging/smoke/E2E.
- Exigir aprovação do Environment antes do job de produção.
- Validar configuração/secrets sem exibi-los.
- Executar migration backward-compatible, deploy backend/frontend e health/smoke não destrutivo.
- Registrar versão implantada e documentar rollback de aplicação.

## Arquivos provavelmente envolvidos

- `.github/workflows/deploy-production.yml`
- scripts provider-specific já introduzidos na PR 33
- documentação/release runbook

## Implementação

Se qualquer pré-requisito estiver ausente, encerrar como bloqueado sem criar workflow parcial. O deploy deve promover artifact/commit identificado, não rebuildar código diferente sem rastreabilidade.

## Regras técnicas

- Aprovação manual é obrigatória no início do projeto.
- Produção não reutiliza conta/secrets de staging.
- Smoke de produção é somente leitura/não destrutivo.
- Nunca usar downgrade automático como rollback.
- Privilégios mínimos e logs sem secrets.

## Não implementar nesta PR

- escolha de provedor/estratégia pelo Codex;
- alteração funcional;
- E2E destrutivo em produção;
- rollback destrutivo de banco;
- Dockerfile/Compose sem decisão explícita;
- relatório/analytics futuro.

## Testes obrigatórios

- Validação do workflow e condições de promoção.
- Versão sem staging aprovado é rejeitada.
- Falha de migration/health interrompe promoção.
- Approval gate e environment estão documentados/verificados por responsável.
- Smoke não destrutivo e ausência de secrets em output.

## Critérios de aceite

- Apenas versão validada e aprovada chega à produção.
- Deploy é auditável e rollback de aplicação está documentado.
- Banco não depende de downgrade automático.

## Definition of Done

Promoção protegida, testada no mecanismo aprovado e com runbook revisado.

## Riscos e cuidados

Workflow não cria proteção de Environment sozinho sem autoridade administrativa. Migrations destrutivas exigem release separado. Não afirmar produção pronta sem teste real autorizado.

## Resultado esperado

Produção recebe releases conscientes, rastreáveis e promovidas a partir de staging validado.

## Instrução final ao Codex

Sem todas as decisões e proteções, não edite arquivos: informe bloqueios e pare. Se liberada, implemente somente promoção protegida.
