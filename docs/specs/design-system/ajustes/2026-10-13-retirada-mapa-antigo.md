# Retirada autorizada do mapa antigo

13/10/2026 · Baseline `3c6838d`. O usuário solicitou retirar “Locais (mapa antigo)” do administrador e do portal e remover suas referências do projeto.

## Contrato do ajuste

- Remover a página `/locais`, item administrativo, mapa esquemático público e seus estados, cálculo aproximado, CSS, tipos, chamadas HTTP, endpoints, schemas, CRUD/modelo e fixtures exclusivos.
- Preservar o mapa geográfico de campi, prédios, espaços e caminhos, origem manual/GPS, acessibilidade e rotas reais. A aba pública “Locais” continua oferecendo esse mapa atual. Sem dados geográficos, mostrar indisponibilidade; falha de leitura informa erro seguro, sem fallback retirado.
- Atualizar testes e documentação de uso. Specs/evidências anteriores ficam identificadas como histórico substituído neste escopo; não serão falsificadas nem tratadas como instruções atuais de manter o recurso.
- Preservar a cadeia Alembic já versionada; acrescentar retirada da tabela exclusiva em nova migração. Preparar/verificar SQL e reversão de estrutura sem aplicar em banco real. Reversão de schema não recupera registros excluídos; aplicação futura requer backup/avaliação próprios.
- Nenhuma alteração em autenticação, chat, eventos, documentos ou configurações. Sem commit ou push nesta solicitação.

## Critérios e tarefas

- [x] Administrador sem item/página; rota retirada retorna 404 e demais destinos funcionam.
- [x] Portal usa somente mapa geográfico; carga/vazio/erro explícitos, sem consultas à API retirada; navegação/rotas geográficas preservadas.
- [x] Código ativo/fixtures/documentação de uso sem dependências do recurso; referências residuais somente em migrações, testes de ausência e histórico identificado.
- [x] Backend sem endpoints/modelo/CRUD/schemas; migração encadeada e limitada à tabela retirada, sem CASCADE e sem execução em dados reais.
- [x] Lint, tipos, suíte frontend/backend relevante, build e revisão visual com dados sintéticos registrados.

Implementação e verificação local concluídas, aguardando revisão. A solicitação substitui somente os contratos anteriores que exigiam preservar o mapa retirado. Aceite deste ajuste ainda não recebido; pendências anteriores permanecem históricas. Sem commit/push.

## Evidências reais — 13/10/2026

Pasta: [evidencias-retirada-mapa-antigo](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/ajustes/evidencias-retirada-mapa-antigo>).

| Critério | Evidência e resultado |
| --- | --- |
| Administrador | Página/gerenciador/testes exclusivos removidos, item e import de ícone retirados. Testes da sidebar conferem os sete destinos, ativo, fechamento móvel e saída. `frontend-http.json`: `/locais` retorna 404; `/campi` retorna 200. Build lista 18 páginas e não oferece rota retirada. Capturas `admin-*` e `admin-campi-escuro-1440.png`; menu móvel com sete links. |
| Portal | Componente/CSS, consulta, estado, seletor de alternativa e cálculo aproximado removidos. Navegador geográfico passa a informar carregamento, ausência e erro seguro. Testes preservam origem manual, GPS/precisão/cancelamento, caminhos acessíveis, seleção de espaços, troca de campus e montagem Leaflet. `browser.json`: 12 observações, dois temas, 1440/390/320, sem UI retirada ou overflow; quatro vistas de ausência/erro em celular. `rota-geografica.txt`/PNG: Portaria → Bloco A, 16 m, calculada no navegador. |
| Dependências/referências | `active-reference-audit.json`: zero referências funcionais em app/componentes/lib/fixtures do frontend e app do backend. Tipos/API, schemas/CRUD/modelo/router removidos. Fixtures deixam de oferecer o endpoint e dados antigos; fixture exclusiva apagada. Todos os scripts de fixture passaram em `node --check`. Documentação de uso atualizada; histórico identificado nos contratos afetados. |
| Backend/dados | Três testes novos conferem OpenAPI/404, DROP limitado em SQLite em memória e SQL de downgrade com constraints/índices/RLS/grants. Três testes geográficos existentes passaram. `migration-offline.txt`: SQL somente de 0022→0023, DROP sem CASCADE e atualização da revisão. Cadeia anterior preservada. Teste de integração PostgreSQL foi atualizado para exigir ausência da tabela, mas sua execução PostgreSQL online não foi realizada. Nenhum banco real alterado. |
| Verificação | Lint e tipos: código 0. Suíte frontend final: 218 testes/24 arquivos, código 0. Backend final: 514 testes rápidos, código 0, oito avisos de rollback da fixture existente. Build final: código 0/18 páginas. Logs completos e `checks.json`. `git diff --check` passou. |

## Alterações e preservações

- Frontend: removidos `app/(admin)/locais/*`, componente/CSS público exclusivo, `CampusLocation`/tipos derivados, `locationApi` e `publicPortalApi.listLocations`. O portal mantém suas três áreas; Locais agora exibe exclusivamente a navegação geográfica atual.
- Backend: removidos modelo, quatro schemas, CRUD, router administrativo e endpoint público exclusivos. As APIs geográficas, grafo, autenticação, regras de tenant, chat/RAG, documentos, eventos e configurações não foram reescritos.
- Testes exclusivos do recurso foram retirados junto com ele; testes dos consumidores atualizados e regressões de ausência/estado/API acrescentadas. A redução de 227 para 218 testes frontend corresponde à retirada do gerenciador e cenários antigos, com novos cenários de navegação/estado. Nenhuma falha foi ocultada removendo teste de funcionalidade preservada.
- Logs contínuos da fixture integrada passaram ao cache `.next`, conservando snapshots históricos já versionados. A fixture atual suporta mapa vazio/falha para a prova; dados/API/tiles são sintéticos em loopback 4201, frontend compilado em 4220.
- Referências residuais permitidas: migração 0016 já versionada, retirada/reversão 0023, testes que exigem ausência do recurso e artefatos/specs históricos identificados. Não representam rotas, consumidores ou funcionalidades em execução. O histórico do Git e capturas de entregas anteriores não foram falsificados.

## Ocorrências e limites

A primeira execução backend sem ampliação de permissão não concluiu e foi interrompida. Nas duas tentativas seguintes, 492 casos passaram e 22 foram bloqueados pela permissão de `tmp_path` no diretório temporário global e no `.pytest_cache` antigo. Uma pasta nova em `echomind-front/.next` resolveu o bloqueio: os 36 testes dos três arquivos afetados passaram, seguidos pela suíte completa de 514. Logs das tentativas preservados; nenhum teste ou permissão do sistema foi alterado para aprovar a suíte.

Lint inicialmente identificou estado atualizado diretamente no efeito: corrigido derivando carregamento do slug efetivamente resolvido e mantendo atualizações nas respostas assíncronas. Tipos identificaram uma opção de matcher incompatível nos testes: removida. Lint/tipos, 29 testes dos componentes relacionados, suíte completa e build finais passaram.

Revisão React: estados/cálculos e componentes sem consumidores retirados; nenhuma nova biblioteca ou listener; carregamento derivado evita renderizações em cascata; resposta antiga continua cancelada; nomes, mensagens de status e foco dos controles atuais preservados. Orientações Supabase/Postgres aplicadas à revisão de grants/RLS e DDL limitado, com base na [documentação oficial de RLS](https://supabase.com/docs/guides/database/postgres/row-level-security). Consulta ao índice changelog.md foi bloqueada pelo tipo de conteúdo da ferramenta; nenhuma API Supabase nova foi introduzida. Não houve chamadas a projeto remoto, alteração de chaves, RLS de tabelas atuais ou dados reais.

Migração preparada e verificada em SQL/SQLite, **não aplicada a banco PostgreSQL real**. Ao aplicar futuramente, a tabela exclusiva e seus registros serão excluídos; backup é necessário se houver dados a conservar. Downgrade recupera estrutura/proteções, não registros. Sem teste de dispositivo físico, GPS real, provedor cartográfico, zoom nativo ou download; as limitações anteriores desses ambientes continuam explícitas.

![Administrador sem a entrada retirada, com campi preservados](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/ajustes/evidencias-retirada-mapa-antigo/admin-campi-escuro-1440.png>)
