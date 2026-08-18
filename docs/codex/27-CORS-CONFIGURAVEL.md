# PR 27 — CORS configurável e seguro

## Objetivo

Substituir CORS aberto por allowlist configurável por ambiente sem acoplar a um provedor de hospedagem.

## Contexto

O hardening pós-MVP lista CORS como prioridade. A mudança deve ser pequena, reversível e testada para origens permitidas/negadas.

## Pré-requisitos

- PR 21 mergeada.
- Inventariar origens locais atuais; origens de staging/produção precisam de decisão de ambiente, não chute.

## Dependências

Obrigatórias: PR 21.

Não depende de: PRs 22–26 ou CD.

Paralelização: pode ocorrer com PRs 22, 28–30 e 32 após o MVP.

## Escopo desta PR

- Adicionar `ALLOWED_ORIGINS`/config equivalente no padrão existente.
- Parsear e validar allowlist por ambiente.
- Manter configuração local documentada.
- Configurar middleware com credenciais/métodos/headers mínimos necessários.
- Testar preflight e request de origem permitida/negada.

## Arquivos provavelmente envolvidos

- config backend
- `app/main.py`/middleware
- `.env.example`
- testes de config/API
- README

## Implementação

Falhar cedo em configuração inválida sensível. Não inserir domínios de provedor não definido. Se compatibilidade local exigir default, ele deve ser restrito e documentado.

## Regras técnicas

- Wildcard com credentials não é permitido.
- Secrets não entram na allowlist.
- Testes não dependem de domínio real.
- Preservar rotas públicas/autenticadas.

## Não implementar nesta PR

- rate limiting;
- headers/CSP de frontend amplos;
- WAF/proxy;
- deploy/provedor;
- mudanças de RAG.

## Testes obrigatórios

- Parse de uma/múltiplas origens e whitespace.
- Origem permitida recebe headers esperados.
- Origem negada não recebe autorização CORS.
- Preflight válido/inválido.
- Config inválida falha de forma clara.

## Critérios de aceite

- CORS não está aberto por padrão de produção.
- Desenvolvimento continua configurável.
- Nenhum provedor foi presumido.

## Definition of Done

Config, testes e exemplos verdes, mudança restrita ao CORS.

## Riscos e cuidados

CORS não substitui autenticação. Uma allowlist errada pode bloquear frontend; documentar valores necessários sem commitá-los como produção.

## Resultado esperado

Somente origens explicitamente autorizadas acessam o backend via browser.

## Instrução final ao Codex

Implemente apenas CORS configurável, teste e pare.
