# DS-12 — Gestão administrativa de eventos

**Versão:** 1.0.

## Identificação e estado

- **Status:** Proposta / aguardando aprovação. Não aprovada nem implementada.
- **Origem:** fase 12 do roteiro anterior; etapa 9A do plano de refatoração.
- **Modelo sugerido:** GPT-6.1 Sol (`gpt-6.1-sol`), esforço Medium (`medium`).
- **Commit sugerido, após revisão e autorização:** `refactor(events): padroniza gestao administrativa de eventos`.
- **Governança:** [README](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/README.md>), [contrato comum](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/CONTRATO.md>) e [status](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/STATUS.md>).

## Problema e resultado esperado

A gestão de eventos já usa primitivas shadcn, mas tem composição própria de cabeçalho, tabela, estados e formulário longo. Deve consumir os padrões administrativos aprovados, com hierarquia consistente e ações legíveis em celular, preservando a operação que abastece os eventos públicos.

Não há mockup próprio do formulário administrativo no arquivo analisado do UX Pilot. A referência é o Styleguide `1Y8TYWWcoY7N8NBOJS1n` e a estrutura administrativa aprovada; a referência pública orienta apenas a coerência do conteúdo. Medidas ou interações complementares são decisões a revisar, não valores extraídos de um mockup inexistente.

## Dependências e pré-condições

- DS-00 aprovada: decisões visuais, marca, temas e estados definidos.
- DS-01 implementada e revisada: tokens, campos, botões, tabelas e diálogos utilizáveis.
- DS-07 implementada e revisada: cabeçalho e container administrativos definidos.
- Coordenar a semântica dos campos com DS-05; não alterar a tela pública nesta fase.
- Antes da implementação, ler os arquivos atuais e conferir mudanças locais. Esta proposta não autoriza a fase seguinte.

## Escopo

- Cabeçalho de `/eventos`, pesquisa, listagem, estados, ações de editar/excluir e formulário.
- Seleção de período, curso existente/novo, tipo, local, descrição, imagem e link opcionais.
- Prévia de capa, mensagens, confirmação de exclusão, responsividade e acessibilidade.

Fora do escopo: publicação/rascunho, inscrição, categorias novas, alteração de backend ou contrato, migração de dados, novos filtros persistidos, conteúdo ilustrativo do UX Pilot e mudanças no portal público.

## Contratos atuais a preservar

- `useEvents` consulta eventos e cursos; ordena por `event_date` e depois título em pt-BR.
- A pesquisa atual considera título, tipo, curso e local, sem diferenciar maiúsculas/minúsculas.
- O salvamento chama `eventApi.create` ou `update` uma vez; período usa `yyyy-MM-dd`, sem conversão para timestamp/UTC. Um dia preenche início e fim com a mesma data.
- `EventInput` mantém título, `event_date`, `event_end_date`, `event_type`, curso, descrição, local, `image_url` e `link_url`. Opcionais vazios continuam `null`.
- Capa aceita HTTPS; link relacionado aceita HTTP/HTTPS. A validação rejeita credenciais na URL, espaços/caracteres de controle e protocolos indevidos.
- Curso novo exige ao menos dois caracteres; o retorno da criação é selecionado para o evento.
- Uma imagem válida que falha na prévia gera aviso e não impede salvar. Uma URL inválida impede a chamada.

## Requisitos observáveis

| ID | Requisito |
| --- | --- |
| DS-12-R01 | Cabeçalho, busca, listagem e formulário devem usar tokens e composições aprovados, com hierarquia consistente nos temas claro/escuro. |
| DS-12-R02 | A pesquisa deve continuar encontrando os mesmos eventos pelos quatro campos atuais e preservar ordenação; o resultado vazio deve ser compreensível. |
| DS-12-R03 | Criação/edição devem conservar todos os campos, dados preenchidos, normalização e uma chamada de salvamento por envio; sucesso atualiza a lista e fecha o formulário, falha mantém o contexto para correção. |
| DS-12-R04 | O seletor de período deve permitir um dia e intervalo, mostrar a seleção em pt-BR e manter as datas civis enviadas, inclusive após reabrir uma edição. |
| DS-12-R05 | A criação de curso deve conservar validação, chamada, seleção do curso retornado e comportamento de falha, sem exigir que o usuário descarte o evento em edição. |
| DS-12-R06 | URLs opcionais devem conservar validação de protocolos e segurança; falha da prévia deve ter aviso legível sem bloquear um salvamento válido. |
| DS-12-R07 | A exclusão deve identificar o evento, exigir confirmação e manter cancelar sem mutação; a lista só remove o evento após sucesso da API. |
| DS-12-R08 | Carregamento, vazio, falha e salvamento devem ter feedback compreensível; estados de envio não podem ocultar as informações necessárias para corrigir dados. |
| DS-12-R09 | Em 1440, 1024, 768 e 390 px, busca e ações devem permanecer alcançáveis; o formulário longo deve rolar sem cortar rodapé, campos, calendário ou seleção de curso. |
| DS-12-R10 | Campos devem ter rótulos associados; botões de ícone devem identificar evento e ação; diálogos devem preservar foco, fechamento e retorno por teclado. |
| DS-12-R11 | A interface deve manter a autorização e o isolamento do cliente/API existentes e não introduzir payload de tenant, publicação, rascunho ou dado fictício. |

## Arquivos afetados candidatos

O conjunto final depende da implementação; caminhos de contrato são referências de preservação, não autorização para reescrever a API.

- [Página](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(admin)/eventos/page.tsx>) e [EventsManager](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(admin)/eventos/events-manager.tsx>).
- [useEvents](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(admin)/eventos/use-events.ts>), [tipos](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(admin)/eventos/types.ts>) e [constantes](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(admin)/eventos/constants.ts>).
- [Testes do manager](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(admin)/eventos/events-manager.test.tsx>).
- [PageContainer](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/components/page-container.tsx>), primitivas existentes e [API](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/lib/api.ts>) como referências.

## Critérios de aceitação

| ID / requisitos | Dado / Quando / Então |
| --- | --- |
| DS-12-AC01 · R01, R09 | **Dado** cada tema e largura de referência, **quando** abrir a lista e o formulário, **então** a hierarquia aprovada está presente e todas as ações essenciais ficam acessíveis. |
| DS-12-AC02 · R02, R08 | **Dado** eventos de teste com título, tipo, curso e local diferentes, **quando** pesquisar esses valores e um termo inexistente, **então** a filtragem mantém o contrato e comunica ausência de resultados. |
| DS-12-AC03 · R03, R04 | **Dado** um evento de um dia e outro de vários dias, **quando** criar e reabrir para editar, **então** datas e demais campos coincidem com o payload e cada envio usa uma chamada. |
| DS-12-AC04 · R05 | **Dado** um formulário em preenchimento, **quando** criar um curso válido ou tentar um nome curto, **então** o curso retornado é selecionado no primeiro caso e a chamada é impedida no segundo, preservando os outros campos. |
| DS-12-AC05 · R06 | **Dado** capa HTTP, link inválido e capa HTTPS com prévia quebrada, **quando** tentar salvar, **então** URLs inválidas bloqueiam a API e a prévia quebrada apenas avisa. |
| DS-12-AC06 · R07 | **Dado** um evento selecionado para exclusão, **quando** cancelar e depois confirmar em fixture, **então** cancelar não chama a API e a remoção visual ocorre após sucesso. |
| DS-12-AC07 · R03, R08 | **Dado** requisições pendentes ou com falha simulada, **quando** carregar/salvar, **então** há feedback de estado e o erro de envio conserva o formulário. |
| DS-12-AC08 · R09, R10 | **Dado** uso por teclado, zoom de 200% e textos longos, **quando** percorrer busca, calendário e diálogos, **então** foco é visível, controles têm nomes e rolagem permite concluir ou cancelar. |
| DS-12-AC09 · R11 | **Dado** mocks de criação/edição, **quando** inspecionar chamadas e interface, **então** não há tenant escolhido no formulário, nova política de publicação ou alteração de contrato. |

## Plano de implementação

- [ ] Confirmar aprovação, dependências e referência visual acessível; registrar lacunas.
- [ ] Ajustar página/cabeçalho e barra de pesquisa ao padrão administrativo.
- [ ] Padronizar listagem, badges, ações e feedback sem reescrever o hook de negócio.
- [ ] Reorganizar formulário, calendário, curso e prévia com rolagem e foco adequados.
- [ ] Conferir payloads, datas, URLs, exclusão e falhas com fixtures.
- [ ] Adaptar testes de comportamento apenas quando a mudança acessível exigir; executar verificações.
- [ ] Registrar evidências, desvios, limitações e resultado no STATUS; entregar para revisão.

## Verificações e evidências

- Executar `pnpm lint` e `pnpm typecheck` no frontend.
- Executar `pnpm test:run "app/(admin)/eventos/events-manager.test.tsx"`; os testes atuais cobrem salvamento único, período, URLs, prévia quebrada e curso novo.
- Confirmar exclusão/cancelamento e falhas por teste existente que vier a cobrir o caso ou verificação manual com mocks; não afirmar cobertura automatizada hoje inexistente.
- Capturar lista, formulário longo, calendário, alerta de prévia e confirmação em claro/escuro; registrar larguras e teclado/zoom conferidos.
- Não usar registros reais para operações; antecipar `pnpm build` se surgirem alterações relevantes de importação/renderização.

## Conclusão e aprovações

Concluída tecnicamente quando os requisitos estiverem verificados ou as limitações estiverem documentadas, sem regressão funcional conhecida. Implementação, verificação e aprovação visual são estados separados no STATUS. A fase permanece aguardando revisão até aceite explícito.

A autorização desta spec permite somente DS-12. Mudança material de escopo ou decisão visual deve ser revisada antes da implementação dependente. Não avançar, criar commit ou fazer push automaticamente.
