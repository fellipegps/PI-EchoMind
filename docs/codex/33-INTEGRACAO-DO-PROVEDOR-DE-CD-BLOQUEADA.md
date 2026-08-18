# PR 33 — Integração do provedor de CD (bloqueada)

## Objetivo

Implementar os passos específicos de deploy de backend/frontend somente depois que provedor, comandos, ambientes, secrets e rollback forem formalmente definidos.

## Contexto

O repositório não identifica hospedagem. Inventar Vercel, Railway, Render, AWS, Fly.io ou outro geraria lock-in e workflow inexequível.

## Pré-requisitos

- PR 21 mergeada e CI verde.
- Decisão registrada: provedor(es), projeto/serviço alvo, regiões, comandos, health URLs, estratégia de migration/rollback e responsáveis.
- Credenciais configuradas em GitHub Environments por administradores, nunca fornecidas em chat/código.

## Dependências

Obrigatórias: PR 21 e decisão externa de infraestrutura.

Não depende de: PRs 22–32.

Paralelização: não bloqueia eval/hardening; PR 34 depende desta fase.

## Escopo desta PR

- Criar a integração mínima e provider-specific aprovada para staging.
- Usar GitHub Environment `staging`, permissões mínimas e secrets por referência.
- Condicionar deploy a CI verde.
- Executar migration check/backward-compatible conforme estratégia aprovada.
- Deployar backend/frontend na ordem aprovada e executar health checks básicos.
- Documentar rollback de aplicação e limite do rollback de banco.

## Arquivos provavelmente envolvidos

- `.github/workflows/deploy-staging.yml`
- scripts/config oficiais do provedor aprovado
- documentação operacional

## Implementação

Enquanto qualquer pré-requisito externo estiver ausente, não criar YAML genérico nem placeholders que aparentem funcionar: encerrar como bloqueado com lista das decisões faltantes. Quando liberada, usar APIs/actions oficiais e pinning/política aprovados.

## Regras técnicas

- Produção não faz parte desta PR.
- `alembic downgrade` não é rollback automático.
- Migrations preferem expansão backward-compatible.
- Secrets nunca são commitados ou exibidos em artifacts.
- FastAPI/Next.js não precisam ser dockerizados; só usar imagem se a decisão futura explicitamente exigir.

## Não implementar nesta PR

- escolha de provedor pelo Codex;
- produção;
- smoke/E2E completo da PR 34;
- Dockerfile/Compose sem decisão explícita;
- mudança funcional de produto.

## Testes obrigatórios

- Validação/lint do workflow.
- Dry-run ou ambiente sandbox oficialmente suportado, se disponível.
- CI continua obrigatória antes do deploy.
- Migration/health failure interrompe o fluxo.
- Nenhum secret aparece em log/artifact.

## Critérios de aceite

- Provedor e comandos correspondem à decisão formal.
- Deploy de staging é reproduzível e falha fechado.
- Não existe suposição de infraestrutura.

## Definition of Done

Workflow aprovado, seguro e documentado; staging recebe versão identificável após CI.

## Riscos e cuidados

Esta PR está bloqueada por design. Credenciais, domínios e comandos variam por provedor; não preencher por inferência. Migration pode tornar rollback impossível se não for aditiva.

## Resultado esperado

Uma versão mergeada consegue chegar a staging pelo provedor escolhido, pronta para smoke/E2E.

## Instrução final ao Codex

Se a decisão de infraestrutura não estiver completa, não edite arquivos: liste bloqueios e pare. Se estiver, implemente somente staging provider integration e pare.
