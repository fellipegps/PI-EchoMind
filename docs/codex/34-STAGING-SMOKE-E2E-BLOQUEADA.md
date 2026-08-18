# PR 34 — Smoke e E2E de staging (bloqueada)

## Objetivo

Adicionar validação pós-deploy em staging com health checks e um cenário Playwright documental usando conta/tenant sintéticos próprios.

## Contexto

E2E administrativo não deve rodar em PR com credenciais reais. Ele pertence ao staging implantado e depende de ambiente estável.

## Pré-requisitos

- PRs 04, 20 e 33 mergeadas.
- URLs de staging, conta de teste, tenant/corpus sintético e secrets no GitHub Environment.
- Política de limpeza de dados de teste e autorização para mutações em staging.

## Dependências

Obrigatórias: PR 04, PR 20, PR 33 e infraestrutura/credenciais de staging.

Não depende de: PRs 22–32.

Paralelização: não iniciar antes de PR 33; PR 35 aguarda seu sucesso.

## Escopo desta PR

- Adicionar Playwright e configuração exclusiva de staging.
- Smoke: backend `/health`, frontend 2xx, totem e configuração pública do tenant de teste.
- E2E: login, abrir Documentos, upload sintético, aguardar ready, perguntar conteúdo exclusivo, validar fonte, excluir e confirmar que deixa de recuperar.
- Garantir cleanup idempotente e artifacts seguros em falha.
- Integrar após deploy de staging e permitir `workflow_dispatch` controlado.

## Arquivos provavelmente envolvidos

- dependências/config Playwright no frontend ou diretório E2E existente
- testes E2E/fixtures sintéticas
- `.github/workflows/deploy-staging.yml` ou workflow chamado
- documentação de staging

## Implementação

Usar seletores acessíveis/estáveis e polling com timeout explícito. Credenciais chegam apenas pelo Environment. Screenshots/traces devem ser revisados para não capturar tokens/dados sensíveis.

## Regras técnicas

- Nunca apontar para produção.
- Conta/tenant são exclusivos de teste.
- Cleanup usa IDs criados pelo cenário, nunca varredura ampla.
- Sem Groq/Supabase de produção.
- Falha E2E bloqueia promoção, não executa rollback destrutivo.

## Não implementar nesta PR

- deploy provider-specific novo;
- produção;
- testes destrutivos fora do tenant de teste;
- feature de produto;
- Dockerização da aplicação.

## Testes obrigatórios

- Smoke dos quatro endpoints/páginas previstos.
- Cenário E2E completo de upload → resposta/fonte → delete → ausência.
- Cleanup em sucesso e falha.
- Timeout/erro de processamento produz diagnóstico seguro.
- Lint/typecheck/test/build continuam verdes.

## Critérios de aceite

- Staging implantado passa smoke e E2E repetíveis.
- Artifacts não vazam secrets.
- O teste não toca em tenants/dados reais.

## Definition of Done

Gate pós-deploy estável, documentado e exigido antes da produção.

## Riscos e cuidados

LLM real pode tornar assertion textual instável; validar fatos/fonte por contrato robusto ou fixture controlada. Cleanup mal escopado é destrutivo; resolver IDs exatos.

## Resultado esperado

Cada versão de staging demonstra o fluxo documental real antes de promoção.

## Instrução final ao Codex

Sem staging/conta/secrets autorizados, não implemente: liste bloqueios e pare. Com eles, implemente somente smoke/E2E de staging.
