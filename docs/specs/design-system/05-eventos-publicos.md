# DS-05 — Eventos públicos

**Versão:** 1.0.

## Identificação e controle

- Status: **Proposta — aguardando aprovação; não implementada**.
- Fase original: 05 do roteiro, etapa 4 do plano.
- Modelo recomendado: **GPT-6.1 Sol**, esforço **Medium** (`medium`).
- Commit sugerido após revisão e autorização: `refactor(events): padroniza apresentacao dos eventos publicos`.
- Dependências: DS-00 aprovada; DS-01 e DS-03 implementadas/revisadas. DS-04 deve estar revisada se a fase reutilizar a composição de eventos da coluna auxiliar.
- A fase mantém os contratos públicos de eventos, sem autorização de filtros ou ordenações novas.

Sequência no [README](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/README.md>), regras no [CONTRATO](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/CONTRATO.md>) e acompanhamento no [STATUS](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/STATUS.md>).

## Problema e resultado esperado

Os eventos públicos usam cards e estados próprios do portal. A referência do UX Pilot orienta hierarquia e uso de capas, mas simplifica dados que o sistema já exibe, como curso e período de vários dias.

O resultado esperado é uma agenda visualmente integrada ao portal, com dados completos, imagens opcionais e estados claros. A aparência do mockup não pode reduzir informação real nem introduzir categorias ou destaques editoriais inexistentes.

## Referências e situação atual

- UX Pilot: **EchoMind - Events and Locations**, `k5WjrM3paBG7rWH7cnmR`, página `ThHPmFvVAyXGKTItA3AZ`.
- [Plano original](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/plano-refatoracao-design-echomind.md>) define migração da área dentro da navegação pública existente.
- `PublicPortal` consulta `publicPortalApi.listEvents(slug)` e controla carregamento, erro e vazio; não há busca/filtros de eventos na implementação inspecionada.
- `EventCard` é composição local que exibe título, período, curso, local, descrição opcional, capa e link opcional.
- Datas usam UTC para evitar deslocamento do dia; o período contempla mesmo dia, mesmo mês, meses diferentes e anos diferentes.
- `safeEventUrl` aceita apenas HTTPS para capas, HTTP/HTTPS para links, rejeitando espaços, controles, credenciais e endereços inválidos. Capa falha é retirada preservando o card.

## Escopo

- Hierarquia, card, capa, data/período, metadados, descrição e link relacionado.
- Estados de carregamento, vazio e erro no portal; composição resumida para o chat quando adequada aos dados/consumidores existentes.
- Migração dos estilos de eventos para tokens e componentes aprovados.

Fora do escopo: criação/edição administrativa, contratos/API, novos filtros, novas categorias, destaques, ordenação editorial, métricas de participação, novas ações e conteúdo de exemplo em produção.

## Requisitos observáveis

- **DS-05-R01:** A agenda permanece dentro da estrutura DS-03, com título e navegação consistentes com Chat e Locais, e utiliza cores/tipografia/estados da DS-01 em ambos os temas.
- **DS-05-R02:** Cada card mantém título, curso, local, descrição quando existente e período completo dos dados recebidos; nenhum desses campos é suprimido para imitar o mockup.
- **DS-05-R03:** Eventos de um dia, vários dias, meses distintos ou anos distintos exibem datas corretas, sem deslocamento de dia por fuso horário.
- **DS-05-R04:** Capa é opcional e continua admitindo somente URL HTTPS validada; uma imagem quebrada deixa de ser exibida sem remover título, metadados, descrição ou ação válida.
- **DS-05-R05:** Link relacionado é opcional e continua aceitando apenas HTTP/HTTPS válidos, sem credenciais ou conteúdo inseguro; ao abrir nova aba, preserva a proteção `noopener noreferrer`.
- **DS-05-R06:** Carregamento, ausência de eventos e falha de consulta possuem apresentações distintas e compreensíveis; erro não revela detalhes internos.
- **DS-05-R07:** Conteúdo provém da instituição do slug atual; a fase preserva filtros/busca que eventualmente existirem ao iniciar a implementação, mas não cria categorias, destaques ou uma nova ordenação.
- **DS-05-R08:** Em 1440, 1024, 768 e 390 px, títulos/descrições longos, cards sem imagem e capas com proporções variadas permanecem utilizáveis sem overflow horizontal ou sobreposição da navegação.
- **DS-05-R09:** Cards e links mantêm hierarquia semântica, nome acessível, foco e leitura por teclado; imagens presentes preservam alternativa textual apropriada.
- **DS-05-R10:** Caso exista resumo na coluna auxiliar da DS-04, ele compartilha formatação/composição pertinente e os dados já carregados, sem uma segunda consulta motivada apenas pela apresentação.
- **DS-05-R11:** Apenas CSS de eventos substituído e sem consumidores é removido; estilos dos mapas e contratos públicos permanecem inalterados.

## Arquivos candidatos e limites

- [PublicPortal e EventCard](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(public)/components/public-portal.tsx>) — composição e estados atuais.
- [CSS do portal](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(public)/components/public-portal.module.css>) — substituir apenas a apresentação de eventos migrada.
- [Testes do portal](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(public)/components/public-portal.test.tsx>) — período, curso, links, imagem quebrada, vazio e erro.
- [Tipos/cliente público](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/lib/api.ts>) — referência de leitura para `PublicEvent`, sem alteração contratual.
- [Card](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/components/ui/card.tsx>) e [Skeleton](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/components/ui/skeleton.tsx>) — reutilização da base existente.

A composição de card pode ser extraída para consumo principal/resumido quando houver benefício real. Preservar a mesma regra de validação de URL e formatação do período, sem duplicá-las de maneira divergente.

## Critérios de aceitação

- **DS-05-AC01 — R01/R02/R08:** Dado evento com todos os campos e textos longos, quando exibido na agenda nos dois temas e larguras previstas, então a hierarquia segue a base e todos os dados continuam legíveis sem sobreposição.
- **DS-05-AC02 — R03:** Dados eventos de um dia, intervalo no mesmo mês, entre meses e entre anos, quando renderizados, então os períodos refletem as datas de origem sem mudança do dia por timezone.
- **DS-05-AC03 — R04/R09:** Dado card sem capa, com capa HTTPS válida ou capa quebrada, quando renderizado ou a imagem falha, então a agenda continua utilizável e o restante do card permanece disponível.
- **DS-05-AC04 — R04/R05:** Dados URLs de capa/link válidos e inválidos, quando o card é renderizado, então apenas os protocolos admitidos são usados e links externos válidos conservam proteção de nova aba.
- **DS-05-AC05 — R06:** Dadas consultas pendente, vazia e rejeitada em mocks, quando a aba Eventos abre, então cada estado é distinguível e a falha não mostra mensagem técnica interna.
- **DS-05-AC06 — R07/R10:** Dados eventos institucionais e coluna auxiliar existente, quando ambos os consumidores aparecem, então usam o mesmo conjunto consultado e não inventam categorias/destaques ou consultas de apresentação.
- **DS-05-AC07 — R08/R09:** Dado uso de teclado, zoom e conteúdo extenso, quando se percorrem os links, então foco, nomes e texto permanecem compreensíveis e ações não ficam cobertas.
- **DS-05-AC08 — R11:** Dado o diff e o levantamento de consumidores, quando revisados, então a limpeza não remove estilos ainda usados pelos mapas nem altera os contratos de eventos.

## Plano de implementação

- [ ] Conferir aprovações e dependências, estado local e consumidores de eventos/coluna auxiliar.
- [ ] Consultar a referência visual e confrontar os dados completos do contrato atual.
- [ ] Aplicar hierarquia/card/capa/estados com a base aprovada, preservando período e validação de URLs.
- [ ] Compartilhar composição com resumo existente quando útil, sem novas consultas.
- [ ] Conferir matrizes de período, URLs, imagem ausente/quebrada, textos extensos e estados assíncronos.
- [ ] Remover somente seletores de eventos substituídos e sem consumidores.
- [ ] Executar verificações e registrar imagens/evidências para revisão no STATUS.

## Verificações e evidências esperadas

- Executar `pnpm lint`, `pnpm typecheck` e `public-portal.test.tsx` no frontend, mantendo cobertura de curso, período, link externo, capa quebrada, vazio e falha.
- Cobrir com fixtures os formatos de período e protocolos relevantes que não estiverem protegidos pela suíte existente; evitar teste que apenas confira classes.
- Mostrar imagens da agenda nos temas claro/escuro, desktop/celular, incluindo um card completo, outro sem capa e estados vazio/erro/carregamento.
- Registrar preservação do slug e ausência de consultas duplicadas caso exista apresentação auxiliar.
- Usar fixtures/mocks para falha e conteúdo extremo. Não editar ou excluir eventos reais para produzir estados de demonstração.
- Antecipar build se a extração alterar importações/renderização de forma relevante; registrar limitações sem presumir aprovação.

## Conclusão e aprovações

Pronta para revisão quando os critérios têm evidência, as verificações obrigatórias estão resolvidas e a agenda preserva os dados/estados atuais. STATUS distingue implementação, verificação e aprovação pelo usuário.

Não avançar, criar commit ou fazer push automaticamente. Novos filtros, ocultação de campos ou mudança material da direção visual exigem proposta revisada e aprovação antes da implementação dependente. Todas as tarefas desta spec estão pendentes.
