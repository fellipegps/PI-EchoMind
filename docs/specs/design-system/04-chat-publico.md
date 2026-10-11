# DS-04 — Chat, mensagens e FAQs públicas

**Versão:** 1.0.

## Identificação e controle

- Status: **Proposta — aguardando aprovação; não implementada**.
- Fase original: 04 do roteiro, etapa 3B do plano.
- Modelo recomendado: **GPT-6.1 Sol**, esforço **High** (`high`).
- Commit sugerido após revisão e autorização: `refactor(chat): aplica design system ao chat publico`.
- Dependências: DS-00 aprovada com avatar, comportamento móvel e coluna auxiliar; DS-01 implementada/revisada; DS-03 implementada/revisada com estrutura pública estável.
- A fase não autoriza novos recursos do assistente ou substituição do contrato textual de resposta.

Usar o [README](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/README.md>) para sequência, o [CONTRATO](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/CONTRATO.md>) para regras de execução e o [STATUS](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/STATUS.md>) para evidências e aprovações.

## Problema e resultado esperado

Mensagens, avatar, sugestões e campo de envio usam apresentação própria do portal. A migração precisa aproximá-los das referências desktop/celular mantendo a resposta incremental e a renderização segura; reproduzir apenas a imagem não protege esse comportamento.

O resultado esperado é uma conversa legível e responsiva, com compositor acessível e identidade compartilhada. A coluna auxiliar aproveita FAQs/eventos já consultados, sem acrescentar chamadas nem conteúdo ilustrativo.

## Referências e situação atual

- UX Pilot: desktop `ktsYqLA8UvfGZe6riGsa` e celular `3Qj2y1kf1JY6tBztuJCd`, ambos EchoMind - Chat Portal, página `ThHPmFvVAyXGKTItA3AZ`.
- [Plano original](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/plano-refatoracao-design-echomind.md>) distingue exemplos visuais de capacidades implementadas.
- `PublicPortal` mantém as mensagens e recebe tokens de `streamPublicChat(question, slug, ...)`; tokens seguintes são acumulados na mesma mensagem do assistente.
- O indicador inicial permanece até o primeiro token. Conclusão/erro encerram envio e indicador; envio vazio, simultâneo ou por portal inválido é bloqueado.
- `react-markdown` utiliza `skipHtml`, lista limitada de elementos e `unwrapDisallowed`; preservar essa proteção e o tratamento seguro de URLs.
- FAQs públicas são consultadas uma vez no fluxo atual e limitadas às quatro sugestões atuais; eventos já estão disponíveis no mesmo componente.

## Escopo

- Avatar, mensagem do usuário/assistente, Markdown, campo de envio, sugestões de FAQs e indicação de resposta/erro.
- Conteúdo auxiliar real de FAQs e eventos no espaço aprovado em DS-03.
- Migração seletiva dos estilos de chat e composição em Tailwind/componentes existentes.

Fora do escopo: voz, anexos, atendimento humano, perfil de aluno, cards estruturados inferidos da resposta, novos endpoints, persistência de histórico, novos limites de dados e mudanças no protocolo de streaming.

## Requisitos observáveis

- **DS-04-R01:** Mensagens, avatar, sugestões e compositor consomem identidade, tokens e estados aprovados, mantendo distinção perceptível entre autor usuário e assistente nos dois temas.
- **DS-04-R02:** Uma pergunta válida é enviada exatamente pelo fluxo atual com o slug institucional; tokens parciais continuam se acumulando na mesma resposta e não aparecem como mensagens independentes.
- **DS-04-R03:** Markdown permitido mantém semântica e formatação mesmo quando delimitadores chegam em partes; HTML cru e URLs inseguras não ganham capacidade de execução.
- **DS-04-R04:** Antes do primeiro token há indicação compreensível de espera; conclusão/erro encerram estado de envio e a falha mostra mensagem amigável sem detalhes internos.
- **DS-04-R05:** Envio vazio, simultâneo, durante carregamento institucional ou por link inválido continua bloqueado; nomes acessíveis de campo e ação permanecem inequívocos.
- **DS-04-R06:** Acionar uma FAQ usa a pergunta real dessa instituição e o mesmo fluxo de envio; não aparecem sugestões, eventos ou informações acadêmicas inventadas.
- **DS-04-R07:** A coluna auxiliar usa dados públicos já consultados e se recolhe conforme DS-00/03; apresentação duplicada não causa consultas adicionais nem controles focáveis ocultos.
- **DS-04-R08:** Conversa longa, links, código e textos extensos não provocam overflow horizontal da página nem ficam escondidos pelo compositor ou pela navegação inferior.
- **DS-04-R09:** Campo e ação de envio permanecem alcançáveis em celular; rolagem permite ler a conversa e enviar após a resposta. Teclado virtual deve ser verificado quando houver dispositivo disponível.
- **DS-04-R10:** Os estados de espera/erro e foco são perceptíveis por teclado e recursos assistivos; a resposta mantém atualização acessível sem tornar decorativos os controles operáveis.
- **DS-04-R11:** A remoção de CSS limita-se aos seletores do chat sem consumidores; apresentação de eventos/mapas ainda não migrada e contratos de API/backend permanecem preservados.

## Arquivos candidatos e limites

- [PublicPortal](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(public)/components/public-portal.tsx>) — mensagens, sugestões, compositor e dados já carregados.
- [CSS do portal](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(public)/components/public-portal.module.css>) — substituição seletiva de apresentação do chat.
- [Testes do portal](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(public)/components/public-portal.test.tsx>) — streaming, Markdown, slug e falhas.
- [Cliente de API](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/lib/api.ts>) e [testes do cliente](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/lib/api.test.ts>) — referência dos contratos, sem mudança prevista.
- [Button](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/components/ui/button.tsx>) e [Input](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/components/ui/input.tsx>) — consumo da base, preservando APIs.

Composições especializadas de mensagem/compositor podem ser extraídas se preservarem o estado e reduzirem a complexidade real. Não importar HTML gerado no UX Pilot como substituto do componente funcional.

## Critérios de aceitação

- **DS-04-AC01 — R01/R08/R09:** Dada conversa longa em ambos os temas, quando se inspecionam larguras previstas e conteúdo extenso, então mensagens são legíveis, o compositor é alcançável e não existe sobreposição ou overflow horizontal da página.
- **DS-04-AC02 — R02:** Dado streaming simulado com múltiplos tokens, quando a resposta chega, então a pergunta usa o slug correto e uma única mensagem do assistente contém os tokens na ordem original.
- **DS-04-AC03 — R03:** Dado Markdown com delimitadores separados entre tokens, quando o conteúdo é renderizado, então o negrito/listas/código permitidos funcionam e HTML cru ou link inseguro não executa conteúdo.
- **DS-04-AC04 — R04/R05/R10:** Dada solicitação pendente, quando ainda não houve token ou ocorre falha simulada, então o indicador/erro é perceptível, o bloqueio respeita o estado e uma falha não expõe o detalhe interno.
- **DS-04-AC05 — R05:** Dado campo vazio, portal em carga ou slug inválido, quando o usuário tenta enviar, então não ocorre uma solicitação indevida; campo e botão continuam corretamente identificados.
- **DS-04-AC06 — R06/R07:** Dadas FAQs e eventos de fixture institucional, quando se abre a coluna auxiliar e se aciona uma FAQ, então somente dados recebidos são apresentados e o envio segue o fluxo comum sem consultas extras de apresentação.
- **DS-04-AC07 — R08/R09/R10:** Dado uso por teclado e celular disponível, quando se percorre a conversa e se abre o teclado virtual, então conteúdo e envio permanecem acessíveis; sem dispositivo, a limitação é registrada sem presumir sucesso.
- **DS-04-AC08 — R11:** Dado o diff da fase, quando são conferidos consumidores e contratos, então CSS de eventos/mapas utilizado permanece e não há mudança de backend/protocolo.

## Plano de implementação

- [ ] Conferir aprovação, DS-00/01/03, estado local e referências desktop/celular.
- [ ] Mapear estado, callbacks, lista permitida de Markdown e classes ainda compartilhadas.
- [ ] Aplicar mensagem/avatar/compositor/FAQ com a base existente, mantendo fluxo de tokens.
- [ ] Compor conteúdo auxiliar com os dados já carregados e regras de recolhimento aprovadas.
- [ ] Conferir espera, falha, bloqueios, slug, conteúdo longo e proteção do Markdown/URLs.
- [ ] Remover apenas seletores comprovadamente substituídos e sem consumidores.
- [ ] Executar verificações; registrar imagens, resultados e limitações para revisão.

## Verificações e evidências esperadas

- Executar `pnpm lint`, `pnpm typecheck` e `public-portal.test.tsx`, mantendo testes de tokens parciais, Markdown, slug e erro de streaming.
- Usar mocks para cenários assíncronos; acrescentar cobertura somente para risco comportamental novo, como consulta duplicada ou preservação do compositor.
- Imagens esperadas: conversa curta/longa, primeiro token pendente, erro, sugestões e coluna auxiliar; desktop/celular e ambos os temas identificados.
- Registrar verificação de teclado, foco, nomes acessíveis, zoom e mensagens de status. Registrar separadamente a disponibilidade do teste de teclado virtual real.
- Demonstrar que a chamada por FAQ e a pergunta digitada usam o mesmo contrato institucional; não gerar conversas contra dados reais apenas para testar apresentação.
- Antecipar build caso a extração altere importações/renderização relevantes; limitações não contam como aprovação.

## Conclusão e aprovações

Pronta para revisão quando os critérios têm evidência e a suíte pertinente/verificações obrigatórias estão resolvidas, sem funções novas ou perdas do fluxo atual. STATUS mantém implementação, verificação e aprovação em campos distintos.

Não executar fase seguinte ou commit/push automaticamente. Alteração material do comportamento do compositor, conteúdo ou direção visual deve ser registrada na spec e aprovada antes da implementação dependente. Nenhuma tarefa está concluída nesta preparação.
