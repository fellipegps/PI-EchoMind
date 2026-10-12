# DS-14 — Editor de campi e edição geográfica

**Versão:** 1.0.

## Identificação e estado

- **Status:** v1.0 aprovada pelo usuário em 12/10/2026; implementada; resultado aceito em 12/10/2026 pelo pedido “faça o commite dessas alterações”, com a pendência documentada. Commit local autorizado; identificação no histórico Git. Verificação local realizada; R10/AC09 parcial por zoom nativo de 200% não comprovado. [Evidências DS-14](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/evidencias/DS-14.md>).
- **Origem:** fase 14 do roteiro anterior; etapa 9C do plano de refatoração.
- **Modelo sugerido:** GPT-6 Astra (`gpt-6-astra`), esforço High (`high`).
- **Commit sugerido, após revisão e autorização:** `refactor(campus): aplica design system ao editor de campi`.
- **Governança:** [README](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/README.md>), [contrato comum](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/CONTRATO.md>) e [status](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/STATUS.md>).

## Problema e resultado esperado

O editor reúne mapa Leaflet, formulário contextual e listas de entidades relacionadas. A migração deve tornar claras seleção de campus, entidade em edição, ponto marcado, vínculos e salvamento, mantendo precisão geográfica e controles alcançáveis em telas pequenas.

Não existe mockup completo deste editor entre os seis designs analisados. Usar o Styleguide `1Y8TYWWcoY7N8NBOJS1n`, o padrão administrativo e a composição complementar aprovada. A apresentação de camadas e dados geográficos permanece vinculada à biblioteca de mapas.

## Dependências e pré-condições

- DS-00 aprovada, DS-01 e DS-07 implementadas/revisadas.
- Conferir decisões de controles e semântica de acessibilidade da DS-06; manter compatibilidade com o mapa público sem reescrevê-lo.
- Conferir DS-13 para manter separados locais esquemáticos X/Y e entidades geográficas latitude/longitude.
- Preparar fixtures de pelo menos dois campi, prédios, espaços, pontos e trechos acessíveis/não acessíveis.
- Conferir mudanças locais e limites do escopo antes de alterar o editor.

## Escopo

- Página `/campi`, seletor de campus, contexto e ações, formulário, abas/listas, estados e exclusão.
- Apresentação dos controles do mapa, ponto em edição, legenda e informações de acessibilidade.
- Adaptação responsiva dos painéis e uso da mesma base visual aprovada.

Fora do escopo: novo motor de rotas, geocodificação, reestruturação do banco/API, conversão de coordenadas, troca de provedor, novas funções de importação, redesenho do mapa público e mudança das relações entre entidades.

## Contratos atuais a preservar

- Entidades: `Campus`, `Building`, `IndoorSpace`, `PathNode` e `PathEdge`; IDs e associações seguem `geoCampusApi`.
- Campus conserva centro, zoom inteiro de 1–19, ativo e metadados; latitude fica entre -90/90 e longitude -180/180.
- Prédio conserva entrada geográfica e `entrance_node_id` opcional. Espaço interno pertence a um prédio do campus.
- Trecho conserva dois pontos distintos, distância opcional positiva, `accessible` e `active`. Não converter um trecho com barreira em acessível por aparência.
- O formulário recebe clique/arraste do marcador em campos com sete casas decimais; a exibição resumida com seis casas não deve reduzir o valor salvo.
- Trocar campus limpa edição e dados anteriores; respostas atrasadas não substituem os dados do campus selecionado.
- A instância do mapa é identificada por campus; editar campos não deve reiniciar pan/zoom. Posições e dimensões calculadas são dados dinâmicos, não classes Tailwind fixas.
- Localização administrativa usa `getCurrentPosition` somente após ação, com alta precisão e timeout atuais; pode focar mapa e preencher edição geográfica compatível. Não adicionar acompanhamento contínuo.
- O mapa carrega Leaflet no cliente, preserva limpeza da instância, atribuição de tiles e créditos/logo exigidos na camada configurada.

## Requisitos observáveis

| ID | Requisito |
| --- | --- |
| DS-14-R01 | Cabeçalho, seletor, painéis, listas e formulário devem consumir os padrões aprovados em claro/escuro, mostrando campus e entidade em edição sem ambiguidade. |
| DS-14-R02 | Troca de campus deve preservar limpeza de estado e proteção contra respostas atrasadas; os vínculos apresentados devem pertencer ao campus atual. |
| DS-14-R03 | Clique/arraste do ponto e edição manual de coordenadas devem manter precisão, faixa e sincronização; mudanças apenas de apresentação não devem modificar coordenadas ou reiniciar pan/zoom. |
| DS-14-R04 | CRUD de campi, prédios, espaços, pontos e trechos deve conservar campos, validações, vínculos, salvamento e falhas; a aparência não deve introduzir novas regras geográficas. |
| DS-14-R05 | A ligação da entrada do prédio ao ponto e do espaço ao prédio deve continuar operável; estados como “Sem rota” e “Inativo” devem ser compreensíveis. |
| DS-14-R06 | Trechos devem conservar origem/destino distintos, distância opcional positiva, ativo e acessível; distinguir barreira/acessibilidade por descrição além de cor. |
| DS-14-R07 | A ação de localização deve preservar solicitação por interação e falhas seguras; ausência ou recusa de GPS não deve impedir entrada manual de coordenadas. |
| DS-14-R08 | Exclusões devem identificar entidade e pedir confirmação; cancelar não chama API, e vínculos impeditivos/falhas não podem ser apresentados como sucesso. |
| DS-14-R09 | Em 1440, 1024, 768 e 390 px, mapa, formulário e ações devem continuar utilizáveis, sem painel sobrepor controles essenciais ou créditos; reflow não pode deixar mapa com área inválida. |
| DS-14-R10 | Controles/formulários devem ter nomes, foco visível e operação por teclado; a entrada manual de coordenadas deve continuar disponível como alternativa à marcação no mapa. |
| DS-14-R11 | Preservar inicialização/limpeza do Leaflet, camadas configuradas, atribuição e logo aplicável; estilos locais de integração e valores dinâmicos permanecem permitidos. |
| DS-14-R12 | API, autorização e isolamento devem permanecer, sem tenant escolhido pela interface, novas dependências ou alteração do grafo/algoritmo público de rotas. |

## Arquivos afetados candidatos

- [Página de campi](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(admin)/campi/page.tsx>).
- [GeoCampusManager](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(admin)/campi/geo-campus-manager.tsx>) e [GeoCampusMap](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(admin)/campi/geo-campus-map.tsx>).
- [Testes do manager](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(admin)/campi/geo-campus-manager.test.tsx>).
- [Contrato da API geográfica](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/lib/geocampus-api.ts>) e [testes da API](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/lib/geocampus-api.test.ts>) como referências de preservação.
- [Navegador público](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(public)/components/public-campus-navigator.tsx>) e [roteamento](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(public)/components/campus-routing.ts>) para conferir impacto, sem reestruturar nesta fase.

## Critérios de aceitação

| ID / requisitos | Dado / Quando / Então |
| --- | --- |
| DS-14-AC01 · R01, R09 | **Dado** dois temas e larguras de referência, **quando** abrir editor/listas, **então** campus/edição ficam claros, os controles essenciais são alcançáveis e créditos continuam visíveis. |
| DS-14-AC02 · R02 | **Dado** dois campi com respostas de fixture fora de ordem, **quando** trocar campus, **então** a edição anterior é limpa e resposta antiga não substitui entidades do campus atual. |
| DS-14-AC03 · R03, R10 | **Dado** coordenadas precisas, **quando** marcar/arrastar e ajustar manualmente o ponto, **então** valor e marcador coincidem sem arredondamento adicional ao contrato atual (sete casas para clique/arraste; valor manual preservado) e sem reiniciar o mapa por editar texto. |
| DS-14-AC04 · R04, R05 | **Dado** prédio e ponto existentes, **quando** vincular a entrada e cadastrar espaço interno, **então** payloads e relações continuam iguais aos contratos atuais. |
| DS-14-AC05 · R04, R06 | **Dado** dois pontos distintos, **quando** criar trecho não acessível e testar validação de distância/pontos iguais, **então** a barreira é preservada e entradas inválidas seguem bloqueadas. |
| DS-14-AC06 · R07, R10 | **Dado** GPS aceito, negado ou indisponível, **quando** acionar localização, **então** a chamada ocorre por interação, falhas são comunicadas e cadastro manual permanece possível. |
| DS-14-AC07 · R08 | **Dado** entidade de teste, **quando** cancelar/confirmar exclusão e simular vínculo impeditivo, **então** apenas confirmação chama API e falha não remove a entidade como se houvesse sucesso. |
| DS-14-AC08 · R09, R11 | **Dado** reflow e camada configurada, **quando** mudar largura ou camada, **então** o mapa permanece visível/usável, com atribuição e logo quando aplicável. |
| DS-14-AC09 · R10 | **Dado** teclado e zoom de 200%, **quando** percorrer seletor, abas, campos e confirmação, **então** nomes, foco e rolagem permitem operar sem depender só de gesto no mapa. |
| DS-14-AC10 · R04, R12 | **Dado** mocks de CRUD autenticado, **quando** salvar entidades, **então** endpoints/payloads mantêm contrato e nenhum tenant é informado pelo formulário. |

## Plano de implementação

- [x] Confirmar aprovação, decisões complementares do editor e dependências.
- [x] Ajustar cabeçalho, seletor e painéis sem alterar estado/consultas geográficas.
- [x] Padronizar formulário contextual, vínculos, abas/listas e feedback.
- [x] Alinhar marcadores/legenda e controles com tokens, conservando descrições e geometria.
- [x] Verificar GPS por ação, coordenadas, vínculos, validações e exclusões em fixtures.
- [x] Conferir reflow do Leaflet, pan/zoom, atribuição, camada e limpeza da instância.
- [x] Executar verificações, reunir evidências e atualizar STATUS para revisão.
- [ ] Comprovar zoom nativo de 200% em navegador que exponha esse controle; tentativa e limite registrados em R10/AC09. Viewport reduzido não substitui essa verificação.

## Verificações e evidências

- Executar `pnpm lint`, `pnpm typecheck` e `pnpm test:run "app/(admin)/campi/geo-campus-manager.test.tsx" lib/geocampus-api.test.ts` no frontend.
- Os testes atuais cobrem entrada ligada ao ponto sem tenant, espaço interno, trecho não acessível, confirmação de prédio e autenticação/isolamento da API.
- Conferir manualmente ou acrescentar teste relevante para troca rápida de campus, precisão, pan/zoom, arraste, GPS e reflow quando forem afetados; testes do manager usam mapa simulado e não comprovam Leaflet real.
- Usar testes públicos de roteamento/navegador como regressão se dados ou representação compartilhada forem atingidos; registrar o motivo e o resultado.
- Capturar editor/lista em claro/escuro, móvel/desktop, legenda e confirmação. Usar GPS simulado/mocks, sem posição real; registrar a simulação e limitações de tiles/rede.
- Antecipar `pnpm build` se alterar integração cliente/SSR ou importação do mapa; não editar registros reais.

## Conclusão e aprovações

A fase está concluída tecnicamente após validar preservação geográfica e requisitos visuais, com limitações de ambiente registradas. O STATUS distingue implementação, verificação e aceite; evidência de teste com mapa simulado não substitui inspeção da integração real.

Somente DS-14 é autorizada por sua execução. Mudanças materiais de escopo, comportamento ou decisão visual exigem revisão antes da implementação dependente. Não avançar, criar commit ou fazer push automaticamente.
