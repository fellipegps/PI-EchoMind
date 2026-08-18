# Backlog e decisões futuras

Este arquivo não autoriza implementação. Cada item deverá ganhar uma nova especificação de PR, critérios de aceite e solicitação explícita depois que suas condições forem atendidas.

## Melhorias de retrieval condicionais aos evals

- **Context compression:** considerar somente se PRs 22–26 mostrarem contexto excessivo ou custo/latência relevante.
- **Query expansion com histórico:** depende de política de memória, privacidade e avaliação; não introduzir memória de conversa implicitamente.
- **HyDE:** considerar apenas se os evals demonstrarem ganho sobre Hybrid Search + reranker + Parent-Child.

## Produto fora do escopo

- memória de sessão/conversa;
- seleção de múltiplos LLMs em runtime;
- WhatsApp Business;
- analytics avançado e A/B testing;
- relatório mensal por e-mail;
- onboarding guiado e preview do totem;
- filtros avançados e import/export da base;
- sugestão automática de FAQ.

## Infraestrutura sem decisão

- dockerização de FastAPI ou Next.js;
- Dockerfile de backend/frontend;
- Docker Compose completo;
- provedor de hospedagem;
- estratégia definitiva de backup, restore, observabilidade externa e rollback de banco.

Containers continuam permitidos somente como PostgreSQL + pgvector descartável em testes/CI, até solicitação explícita diferente.

## Critério de promoção do backlog

Um item só vira PR quando houver problema mensurado, proprietário, prioridade, dependências, desenho compatível com multi-tenancy e testes claros. A criação da especificação não autoriza sua implementação; o usuário ainda deve solicitar aquela fase nominalmente.
