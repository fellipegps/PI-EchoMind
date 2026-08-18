# EchoMind — Regras globais para agentes

Estas regras são permanentes e valem para qualquer fase descrita em `docs/codex/`.

1. Nunca implementar mais de uma PR/fase por vez.
2. Sempre ler `docs/codex/00-PLANO-GERAL.md` antes de executar uma fase.
3. Executar somente o arquivo de fase explicitamente solicitado pelo usuário.
4. Nunca avançar automaticamente para a próxima fase.
5. Não implementar funcionalidades futuras por antecipação, nem criar stubs sem necessidade da fase atual.
6. Cada fase deve terminar com os testes previstos no arquivo da própria fase passando.
7. Se algum teste falhar, corrigir dentro do escopo da fase antes de finalizar; se a correção exigir ampliar o escopo, parar e informar o bloqueio.
8. Não realizar refatorações amplas não relacionadas ao objetivo da fase.
9. Preservar a arquitetura multi-tenant existente e aplicar `tenant_id` a toda consulta e mutação pertinente.
10. Preservar a estratégia atual de PGVector/LangChain, salvo quando uma fase explicitamente exigir alteração.
11. Não recriar estruturas legadas removidas do projeto, especialmente `knowledge_documents`.
12. Não dockerizar FastAPI.
13. Não dockerizar Next.js.
14. Não criar `Dockerfile` para backend ou frontend nesta etapa.
15. Não criar `docker-compose.yml` ou `compose.yaml`, salvo solicitação explícita futura.
16. Containers estão autorizados apenas quando necessários para PostgreSQL + pgvector descartável nos testes de integração/CI.
17. Nunca utilizar banco de staging ou produção para testes destrutivos.
18. Sempre listar os arquivos alterados e os testes executados ao concluir uma fase.
19. Parar ao final da fase solicitada.

Antes de editar código, confirmar que todos os pré-requisitos e dependências da fase estão satisfeitos. Não contornar decisões marcadas como bloqueadas. Manter FAQs, eventos, chat e contratos existentes compatíveis, salvo alteração expressamente exigida pela fase solicitada.
