# PR 21 — Aceite integrado e documentação do MVP

## Objetivo

Fechar contratos transversais, cobertura, regressão e documentação do MVP sem adicionar nova funcionalidade de produto.

## Contexto

Testes unitários/componentes nasceram nas PRs anteriores. Esta fase não é um depósito tardio de testes: cobre apenas o fluxo integrado e lacunas observadas entre as camadas.

## Pré-requisitos

- PRs 02–20 relevantes mergeadas e CI verde.
- Três fixtures sintéticas finais: PDF textual, DOCX e TXT.

## Dependências

Obrigatórias: PRs 02 a 20.

Não depende de: staging/CD, eval ou retrieval avançado.

Paralelização: marco de fechamento; não paralelizar com mudanças funcionais no pipeline.

## Escopo desta PR

- Adicionar/ajustar testes de integração cross-layer estritamente necessários para upload → ready/error → retrieval → delete.
- Cobrir isolamento multi-tenant end-to-end no backend com PostgreSQL/pgvector e embedding fake.
- Confirmar regressão de FAQ/evento/chat.
- Consolidar cobertura dos módulos novos com meta mínima de 80% neles, sem manipular a métrica global.
- Documentar setup, limites, formatos, estados, comandos CI, migration, reindex e troubleshooting de OCR não suportado.
- Documentar branch protection recomendada com nomes estáveis; não alterar configuração remota sem solicitação.
- Registrar roteiro manual local com arquivos sintéticos, sem credenciais reais.

## Arquivos provavelmente envolvidos

- testes existentes de documentos/ingestão/RAG/frontend
- fixtures sintéticas
- configuração de cobertura/CI somente se lacuna comprovada
- `README.md` e documentação existente

## Implementação

Não duplicar casos já cobertos. Preferir um pequeno teste integrado determinístico e uma matriz de rastreabilidade entre requisito e teste. Toda dependência externa continua fake.

## Regras técnicas

- Nenhum teste destrutivo em staging/produção.
- Não chamar Groq/Supabase real.
- CI de PR usa PostgreSQL descartável.
- Falha cross-layer deve ser corrigida somente no menor escopo que restaura o contrato; mudança maior exige nova PR.

## Não implementar nesta PR

- novas rotas/campos/UX;
- Playwright em staging;
- deploy/CD;
- Hybrid Search/reranker/Parent-Child;
- hardening não relacionado;
- Dockerfile/Compose.

## Testes obrigatórios

- Suíte rápida backend com cobertura.
- `pytest -m integration` em PostgreSQL/pgvector real.
- Migration do zero/head.
- Frontend lint, typecheck, test:run e build.
- Fluxo integrado por tenant: criar/processar/recuperar/excluir e não recuperar após delete.
- Erro de parser termina em error sem vetor/chunk parcial.
- Documento vencido não participa; FAQ/evento continuam.

## Critérios de aceite

- Todos os itens MVP do plano geral são rastreáveis a teste ou roteiro manual justificado.
- Checks `Backend / unit-api`, `Database / migration-integration` e `Frontend / quality-build` verdes.
- Documentação permite reproduzir os gates.

## Definition of Done

MVP documental testado, documentado e revisado; cobertura nova atende gate; nenhuma feature pós-MVP entrou.

## Riscos e cuidados

Evitar “corrigir” lacuna com refactor amplo. Teste integrado não pode depender de timing real de BackgroundTasks/LLM; controlar execução deterministicamente.

## Resultado esperado

O MVP tem evidência automatizada suficiente para ser mergeado, operado e evoluído com segurança.

## Instrução final ao Codex

Feche apenas testes/documentação do MVP, relate qualquer lacuna fora do escopo e pare. Não inicie PR 22.
