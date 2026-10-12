# DS-06 — Mapas e locais públicos

**Versão:** 1.0.

## Identificação e controle

- Status: **Aprovada em 12/10/2026 — implementada, verificada no escopo disponível e aceita em 12/10/2026**.
- Fase original: 06 do roteiro, etapa 5 do plano.
- Modelo recomendado: **GPT-6 Astra**, esforço **High** (`high`).
- Commit sugerido após revisão e autorização: `refactor(maps): padroniza controles e estados dos mapas publicos`.
- Dependências: DS-00 aprovada com composição complementar de mapas; DS-01/03 implementadas/revisadas; DS-05 precede esta fase na sequência de migração seletiva do CSS público.
- Esta fase muda apresentação. Algoritmo, dados geográficos, regras de precisão e acompanhamento não são reescritos.

Consultar [README](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/README.md>), [CONTRATO](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/CONTRATO.md>) e [STATUS](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/STATUS.md>) para execução, dependências e registro das aprovações.

## Problema e resultado esperado

A área de locais reúne mapa geográfico, controles de rota e uma alternativa esquemática, com estilos próprios. A referência Events and Locations não especifica GPS, origem, acessibilidade ou todos os estados que o sistema já suporta.

O resultado esperado é uma experiência visual integrada ao design system, preservando a navegação real até a entrada de prédios e a seleção de espaços. A composição complementar dos controles deve ser aprovada sem fazer o usuário perder alternativas ao GPS.

## Referências e situação atual

- UX Pilot: **EchoMind - Events and Locations**, `k5WjrM3paBG7rWH7cnmR`, página `ThHPmFvVAyXGKTItA3AZ`; referência de identidade, não contrato completo de mapa.
- [Plano original](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/plano-refatoracao-design-echomind.md>) exige origem manual, precisão, cancelamento e mapa alternativo.
- `PublicCampusNavigator` consulta o mapa por slug, filtra campi/prédios/espaços ativos e calcula rotas pelo grafo cadastrado.
- Origem pode ser prédio cadastrado, ponto marcado no mapa ou GPS solicitado por ação explícita. Acompanhamento é interrompido ao parar, trocar para origem manual, falhar, chegar ou desmontar conforme o fluxo atual.
- Sinal impreciso e saltos de localização passam pela filtragem existente; recálculo e confirmação de chegada dependem das regras atuais, sem alteração de limiares nesta fase.
- Ausência de mapa geográfico utilizável mantém alternativa esquemática no portal; quando há mapa geográfico, existe ação para abrir/ocultar o esquemático.

## Escopo

- Busca, seletor de campus, origem/destino, acessibilidade, lista de prédios/espaços, GPS, resumo da rota e estados do mapa.
- Temas, controles Leaflet, marcadores e integração visual do mapa geográfico/esquemático.
- Migração de composição para Tailwind quando apropriada, preservando estilos locais/terceiros e dimensões/coordenadas dinâmicas necessárias.

Fora do escopo: reescrita de roteamento, novos limiares de GPS, geocodificação, novos provedores de mapa, registro de posição real, editor administrativo, novos endpoints e alteração do contrato geográfico.

## Requisitos observáveis

- **DS-06-R01:** Controles, lista, estados e resumo utilizam tokens/primitivas aprovados, com hierarquia legível nos dois temas e nas larguras 1440, 1024, 768 e 390 px.
- **DS-06-R02:** Busca continua encontrando prédios/espaços pelos campos disponíveis; seleção de campus mantém o isolamento dos dados ativos e dos caminhos daquele campus.
- **DS-06-R03:** Origem cadastrada e marcação no mapa continuam calculando a rota até a entrada vinculada do prédio; selecionar espaço preserva prédio, andar e descrição disponíveis.
- **DS-06-R04:** A opção de caminhos acessíveis continua restringindo o grafo cadastrado; ausência de caminho, entrada inválida ou origem distante não produz uma linha reta inventada como rota válida.
- **DS-06-R05:** Abrir o portal/aba não solicita localização. Acompanhamento começa somente após ação de usar localização e oferece indicação de espera, precisão e ação de parar.
- **DS-06-R06:** Negação, indisponibilidade, timeout ou sinal impreciso preservam mensagens compreensíveis e alternativa de origem manual; precisão baixa e saltos continuam sujeitos à filtragem atual.
- **DS-06-R07:** Acompanhamento é cancelado e o observador liberado nos eventos previstos atualmente, incluindo parada/desmontagem; renderização visual não cria observadores duplicados nem recria o mapa a cada posição.
- **DS-06-R08:** Recálculo, distância, estimativa, chegada e condições de rota mantêm as regras atuais e não apresentam como precisa a estimativa temporária do mapa esquemático.
- **DS-06-R09:** Mapa esquemático e seus dados/controles permanecem acessíveis quando o geográfico não está disponível e podem ser exibidos/ocultados quando o geográfico existe.
- **DS-06-R10:** Controles têm nomes, foco e estados acessíveis; mensagens de localização/rota são perceptíveis e controles não ficam encobertos em telas estreitas, zoom ou rolagem.
- **DS-06-R11:** Integração Leaflet conserva CSS necessário, montagem/limpeza e valores geográficos dinâmicos. Remoção de CSS limita-se a seletores substituídos sem consumidores.

## Arquivos candidatos e limites

- [Navegador público](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(public)/components/public-campus-navigator.tsx>) e [controles compartilhados](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(public)/components/public-map-controls.tsx>). O CSS exclusivo anterior foi substituído nesta fase.
- [Mapa geográfico](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(public)/components/campus-map-view.tsx>) — apresentação e integração Leaflet, mantendo seu ciclo de vida.
- [Portal/mapa esquemático](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(public)/components/public-portal.tsx>) e [CSS do portal](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(public)/components/public-portal.module.css>).
- [Algoritmo de rota](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(public)/components/campus-routing.ts>) e [contrato geográfico](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/lib/geocampus-api.ts>) — referências de leitura, sem mudança prevista.
- [Testes do navegador](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(public)/components/public-campus-navigator.test.tsx>), [roteamento](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(public)/components/campus-routing.test.ts>) e [portal](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(public)/components/public-portal.test.tsx>).
- [Layout raiz](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/layout.tsx>) — verificar importação do CSS Leaflet; reposicioná-la somente com justificativa e build, sem remover estilos necessários.

## Critérios de aceitação

- **DS-06-AC01 — R01/R10:** Dado mapa e controles nos dois temas, quando percorridos em celular/desktop, teclado e zoom, então busca, origem, destino, acessibilidade e resumo continuam legíveis e operáveis sem sobreposição.
- **DS-06-AC02 — R02/R03:** Dados campi/prédios/espaços de fixture, quando se busca e seleciona origem manual/destino, então os dados do campus e detalhes do espaço permanecem corretos e a rota chega à entrada cadastrada.
- **DS-06-AC03 — R04/R08:** Dado grafo de teste com percurso comum e acessível, quando a opção é alternada, então os percursos esperados são mantidos; com grafo desconectado, não surge uma rota reta substituta.
- **DS-06-AC04 — R05/R07:** Dado GPS simulado, quando a aba abre, então não há acompanhamento; após ação explícita inicia um observador, e ao parar/desmontar ele é liberado sem duplicação.
- **DS-06-AC05 — R06/R08:** Dadas posições simuladas precisas, imprecisas, saltos e erros de permissão/timeout, quando recebidas, então filtragem, mensagens, recálculo e chegada conservam as regras atuais e a origem manual continua disponível.
- **DS-06-AC06 — R09:** Dada instituição sem prédios geográficos utilizáveis, quando Locais abre, então o mapa esquemático permanece; com geográfico disponível, a ação de alternância permite acessar o esquemático.
- **DS-06-AC07 — R08/R09/R10:** Dada rota esquemática e textos extensos, quando apresentados, então a estimativa continua identificada como temporária, status e resumo são acessíveis e não ficam cobertos pela navegação.
- **DS-06-AC08 — R07/R11:** Dado o diff e a inspeção do mapa em execução, quando tema/largura/posição mudam, então CSS necessário, ciclo de vida e coordenadas dinâmicas são preservados sem reconstrução por atualização de GPS.

## Plano de implementação

- [x] Conferir aprovações, composição complementar aprovada, dependências e estado local.
- [x] Mapear controles, estados, CSS Leaflet e ciclo de vida antes de alterar apresentação.
- [x] Aplicar tokens/primitivas aos controles/listas/resumo e integrar mapa nos dois temas.
- [x] Migrar o esquemático e manter coordenadas/dimensões dinâmicas e identificação de estimativa.
- [x] Conferir origem manual, marcação, campus, espaço, acessibilidade e ausência de rota.
- [x] Exercitar GPS exclusivamente com mocks/simulação, incluindo erro, precisão, parada e limpeza.
- [x] Remover somente CSS substituído, executar verificações e registrar imagens/evidências.

## Verificações e evidências esperadas

- Executar `pnpm lint`, `pnpm typecheck`, `public-portal.test.tsx`, `public-campus-navigator.test.tsx` e `campus-routing.test.ts` no frontend.
- Preservar expectativas existentes de caminhos 20 m/32 m da fixture, entrada do prédio, origem marcada, filtragem de GPS, cancelamento e fallback esquemático.
- Adicionar cobertura direcionada apenas a risco real da nova composição; não testar classes Tailwind nem reescrever testes para aceitar perda comportamental.
- Inspecionar o Leaflet real em navegador: testes unitários substituem `CampusMapView` por mock e não comprovam tiles, dimensionamento, marcadores ou contraste no mapa final.
- Imagens esperadas: geográfico/esquemático, controles estreitos/largos, rota acessível, sinal impreciso e alternativa após erro; identificar tema, viewport e uso de posições simuladas.
- Não solicitar nem transmitir posição real do usuário para validar aparência. Registrar cenários não exercitados como limitações.
- Antecipar `pnpm build` se imports de Leaflet, renderização ou carregamento do mapa forem alterados; registrar resultado e limitações no STATUS.

## Conclusão e aprovações

Pronta para revisão quando critérios possuem evidência, verificações obrigatórias estão resolvidas e mapas/controles mantêm comportamento e alternativas atuais. STATUS distingue implementação, verificação e aprovação; execução de testes não equivale ao aceite visual.

Não avançar para o painel nem criar commit/push automaticamente. Mudança de algoritmo, limiares, política de localização ou direção visual exige proposta e aprovação antes da implementação dependente. Implementação concluída em 12/10/2026; verificações e limitações registradas nas evidências. Resultado aceito em 12/10/2026 pelo pedido de commit após a apresentação da entrega.


## Resultado da execução — 12/10/2026

42 testes pertinentes, lint, tipos e build passaram. Mapas reais inspecionados nos dois temas e nas quatro larguras; GPS somente simulado. Zoom real permanece pendente; reflow, teclado e altura reduzida conferidos. [Registro de evidências DS-06](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/evidencias/DS-06.md>) detalha critérios, imagens e limites. Nenhum requisito material alterado; commit local autorizado após revisão, sem push e sem iniciar DS-07.
