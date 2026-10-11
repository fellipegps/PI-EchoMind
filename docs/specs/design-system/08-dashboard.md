# DS-08 — Dashboard e gráficos

**Versão:** 1.0.

**Status:** Proposta — aguardando aprovação. Nenhuma implementação autorizada por este arquivo.
**Fase original:** Prompt 08; etapa 7 do plano.
**Modelo sugerido:** GPT-6.1 Sol (`gpt-6.1-sol`) · High (`high`).
**Commit sugerido, somente após revisão e autorização:** `refactor(dashboard): padroniza metricas graficos e estados`.

## Contrato e dependências

Seguir o [índice](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/README.md>), o [contrato](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/CONTRATO.md>) e o [STATUS](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/STATUS.md>).
Depende de DS-00 aprovada, DS-01 e DS-07 implementadas, verificadas e revisadas: tokens de gráficos, cards, estados e estrutura administrativa.
Referência: UX Pilot **EchoMind - Admin Dashboard Primal**, design `hldl1brk4q4O5f5XT8Nm`, página `ThHPmFvVAyXGKTItA3AZ`.
O mockup orienta hierarquia e densidade; os contratos `DashboardData` e `RagMetricsData` determinam os dados exibidos.

## Problema e resultado esperado

Os gráficos usam azul literal `#01a6fd`; cards e seção RAG precisam acompanhar a identidade aprovada e funcionar em ambos os temas.
O resultado esperado é uma visão clara de indicadores, séries e operação, sem mudar o significado das métricas para caber no mockup.
O dashboard principal atualmente usa fallback de zeros/listas vazias em falha; a seção RAG já distingue carregamento, vazio e erro com nova tentativa.
Essa diferença é uma limitação preexistente: esta fase preserva a política atual do dashboard principal e a distinção real existente no RAG.

## Escopo

- Cards de indicadores, gráficos de interações/FAQs, seção RAG e distribuição responsiva.
- Cores semânticas dos gráficos, rótulos, tooltips, tipografia, superfícies e estados atuais.
- Composição e legibilidade dos agregados operacionais sem expor conteúdo de perguntas no RAG.

## Fora do escopo

- Novas métricas, categorias no lugar de FAQs, comparativos, períodos selecionáveis ou valores do mockup.
- Indicador de disponibilidade, reinício do agente ou ações sem suporte atual.
- Mudanças de agregação, endpoints, modelo de dados e política de fallback do dashboard principal.
- Exibir campos apenas porque existem na API: conservar a cobertura atual; expansão de métricas exige escopo próprio.

## Requisitos observáveis

- **DS-08-R01:** cards, gráficos e seção operacional devem usar a base e os tokens aprovados, com eixos, tooltips e foco legíveis nos dois temas.
- **DS-08-R02:** os quatro indicadores devem manter `total_questions`, `unanswered_questions`, `avg_response_time` e `satisfaction_rate`, seus significados e unidades.
- **DS-08-R03:** o gráfico diário deve continuar usando `daily_interactions.date/count`; o de FAQs deve continuar usando `top_faqs.question/count`, sem mudar seu rótulo para categorias.
- **DS-08-R04:** valores e datas devem seguir as convenções existentes em português; truncamento visual não deve impedir identificar a FAQ completa pelo mecanismo de detalhe adequado.
- **DS-08-R05:** a seção RAG deve continuar consultando `getRagMetrics(30)` e preservar volume, falhas, média de resultados, latências, totais/sucessos/erros de retrieval e ingestão, taxa sem resposta e tipos de fonte já exibidos.
- **DS-08-R06:** carregamento RAG, `has_data: false` e falha devem permanecer distintos. Falha deve manter mensagem segura e “Tentar novamente”, sem zeros inventados nem detalhes internos de erro.
- **DS-08-R07:** o fallback preexistente do dashboard principal deve permanecer reconhecido e documentado; a migração visual não pode ser apresentada como correção da distinção erro/zero. Nenhum dado ilustrativo deve substituir os retornos atuais.
- **DS-08-R08:** consultas e estados das duas áreas devem continuar independentes, conservando proteção atual contra atualização após desmontagem no RAG; sua falha não deve ocultar os demais indicadores.
- **DS-08-R09:** gráficos vazios, números grandes, títulos longos e tipos de fonte devem caber em desktop/celular, sem perda de informação ou overflow do documento.

## Arquivos afetados candidatos

- [Dashboard](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(admin)/dashboard/page.tsx>).
- [Seção RAG](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(admin)/dashboard/rag-metrics-section.tsx>).
- [Testes RAG](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(admin)/dashboard/rag-metrics-section.test.tsx>).
- [Tokens globais](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/globals.css>), somente se houver necessidade semântica comum aprovada, sem repintar outras telas incidentalmente.
- [Contratos DashboardData/RagMetricsData](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/lib/api.ts>), referência sem alteração prevista.

## Critérios de aceitação

- **DS-08-AC01 — R01/R09:** Dados temas claro/escuro e larguras de 1440, 1024, 768 e 390 px, quando o dashboard renderizar, então cards, eixos, tooltips e fonte devem permanecer legíveis e sem overflow do documento.
- **DS-08-AC02 — R02/R03/R04:** Dada fixture com indicadores e perguntas longas, quando os gráficos e cards forem exibidos, então valores, unidades, significados e identificação completa das FAQs devem corresponder aos dados recebidos.
- **DS-08-AC03 — R05:** Dado retorno RAG conhecido, quando carregado, então todos os agregados já exibidos devem permanecer presentes e a chamada deve continuar usando 30 dias.
- **DS-08-AC04 — R06:** Dado RAG carregando, vazio ou com falha, quando cada estado ocorrer, então deve haver o estado correto; vazio não deve inventar valores e falha deve oferecer nova tentativa sem expor erro interno.
- **DS-08-AC05 — R07:** Dada falha do dashboard principal, quando aplicado o fallback atual, então nenhum número do mockup deve surgir; a evidência deve registrar que os zeros de fallback não representam distinção implementada de indisponibilidade.
- **DS-08-AC06 — R08:** Dada falha ou desmontagem da seção RAG, quando uma consulta terminar, então os demais dados devem continuar disponíveis e a proteção atual da montagem deve permanecer preservada.

## Plano de implementação

- [ ] Conferir aprovação, dependências, baseline e alterações preexistentes.
- [ ] Conferir preview pertinente e mapear cada região visual às métricas atuais.
- [ ] Aplicar composição de cards/gráficos e tokens, mantendo contratos e consultas.
- [ ] Padronizar apresentação dos estados existentes, preservando a diferença de fallback entre as áreas.
- [ ] Adaptar tooltips, rótulos e disposição móvel a conteúdo longo/sem dados.
- [ ] Executar verificações, registrar evidências por critério e limitações no STATUS.

## Verificação e evidências esperadas

- Executar `pnpm lint`, `pnpm typecheck` e `pnpm test:run "app/(admin)/dashboard/rag-metrics-section.test.tsx"` no frontend.
- Os testes RAG devem continuar cobrindo período limitado, vazio sem números, erro seguro/nova tentativa e todos os agregados já exibidos.
- Inspecionar gráficos vazios, tooltip em ambos os temas, perguntas longas, números grandes e rolagem móvel usando fixtures.
- Entregar imagens de dashboard desktop/celular e registros de carregamento, vazio e falha do RAG.
- Apresentar separadamente a limitação do fallback do dashboard principal, sem marcar essa política como corrigida.
- Novos testes são justificados apenas para comportamento relevante afetado; não criar testes que espelhem classes ou cores.

## Conclusão e aprovação

Concluir implementação/verificação exige evidências dos critérios e preservação dos contratos; revisar aparência é uma etapa separada.
A aprovação não é inferida de screenshots, execução de testes ou ausência de resposta.
Alterações materiais desta spec exigem aprovação antes da implementação dependente.
Não avançar, criar commit ou publicar automaticamente. Estado inicial: **Proposta — aguardando aprovação**.
