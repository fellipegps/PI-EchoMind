# PR 28 — Rate limiting de chat e upload

## Objetivo

Adicionar infraestrutura única e testável de rate limiting a `/chat` e `/documents/upload`, com chaves/limites coerentes e resposta 429.

## Contexto

Ambas as rotas são custosas. A mudança compartilha um único objetivo de proteção de capacidade, sem criar fila ou WAF.

## Pré-requisitos

- PR 21 mergeada.
- Definir backend/armazenamento do limiter compatível com a topologia real; se múltiplas instâncias exigirem store compartilhado não definido, parar e pedir decisão.

## Dependências

Obrigatórias: PR 21.

Não depende de: PR 27 ou retrieval avançado.

Paralelização: pode ocorrer com PRs 22, 27, 29–30 e 32, evitando conflito em `main.py`.

## Escopo desta PR

- Criar configuração separada de limites para chat e upload.
- Definir chave autenticada por tenant/usuário e fallback seguro para rota pública conforme contrato real do chat.
- Aplicar 429 com `Retry-After` quando possível.
- Garantir que requests cross-tenant não compartilhem quota indevidamente.
- Testar janela, reset, limites distintos e bypass apenas explícito de testes/health.

## Arquivos provavelmente envolvidos

- requirements/config backend
- middleware/dependencies/routers
- `.env.example`
- testes de API/config
- README

## Implementação

Escolher biblioteca/algoritmo após inspecionar a topologia. Um limiter apenas em memória deve ser documentado como single-instance; não fingir distribuição. Testes usam relógio/store controlável.

## Regras técnicas

- Healthcheck não deve consumir quota.
- Não usar dados pessoais crus como chave persistida/logada.
- 429 não executa LLM/parser.
- Limites são configuráveis, não hardcoded opacos.

## Não implementar nesta PR

- WAF/CDN;
- Celery/Redis apenas para ingestão;
- quotas/planos comerciais;
- analytics avançado;
- mudanças de retrieval/CORS.

## Testes obrigatórios

- Abaixo/acima do limite e reset de janela.
- Chat/upload com limites independentes.
- Tenants/usuários isolados.
- 429 seguro e `Retry-After`.
- Requisição rejeitada não chama serviço custoso.
- Config inválida.

## Critérios de aceite

- Rotas custosas têm limites explícitos e determinísticos.
- A solução corresponde à topologia aprovada.
- Funcionalidade normal não regride.

## Definition of Done

Limiter, configuração, testes e documentação verdes, sem infraestrutura presumida.

## Riscos e cuidados

IP atrás de proxy pode ser forjado se headers não forem confiáveis. Store em memória diverge entre réplicas. Resolver essas decisões antes de alegar proteção distribuída.

## Resultado esperado

Abuso simples não dispara processamento ilimitado de chat/upload.

## Instrução final ao Codex

Implemente somente rate limiting após confirmar topologia; se faltar decisão, pare bloqueado.
