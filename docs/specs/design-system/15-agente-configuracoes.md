# DS-15 — Agente, configurações e QR do portal

**Versão:** 1.0.

## Identificação e estado

- **Status:** v1.0 aprovada em 12/10/2026; implementação concluída nas três áreas; verificação parcial (AC07: download pelo navegador; AC09: zoom nativo 200%); aguardando revisão do resultado. Commit local autorizado; identificação no histórico Git. Sem push ou DS-16.
- **Origem:** fase 15 do roteiro anterior; etapa 10 do plano de refatoração.
- **Modelo sugerido:** GPT-6.1 Sol (`gpt-6.1-sol`), esforço High (`high`).
- **Commit sugerido, após revisão e autorização:** `refactor(settings): padroniza agente configuracoes e portal publico`.
- **Governança:** [README](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/README.md>), [contrato comum](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/CONTRATO.md>) e [status](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/STATUS.md>).

## Problema e resultado esperado

O chat de teste, o formulário institucional e o cartão do portal têm composições próprias. Devem compartilhar identidade, hierarquia e estados com o painel, mantendo diferenças de função: testar respostas, configurar a instituição e compartilhar a URL pública. O QR precisa continuar legível também quando o entorno estiver em tema escuro.

Não existem mockups específicos das configurações e do QR entre os seis designs. Usar Styleguide `1Y8TYWWcoY7N8NBOJS1n` e padrões aprovados; chat público pode orientar identidade, mas não redefine o contrato do chat administrativo.

## Dependências e pré-condições

- DS-00 aprovada; DS-01 e DS-07 implementadas/revisadas.
- Se reutilizar composição de mensagens da DS-04, ela deve estar implementada/revisada e ser compatível com texto simples do agente. Reutilização é condicional, não motivo para trocar o comportamento administrativo.
- Conferir preservação do `public_slug` e da rota pública da DS-03, sem editar navegação do portal nesta fase.
- Conferir mudanças locais e preparar mocks de streaming, configuração, clipboard e QR.
- Se precisar dividir a fase, registrar subentregas coerentes e apresentar a divisão para aprovação antes de executar a parte seguinte; a primeira subentrega não conclui DS-15 inteira.

## Escopo

- `/agente`: composição do chat de teste, mensagens, vazio, espera/streaming, campo e ação de limpar.
- `/configuracoes`: cabeçalho, grupos de campos, carregamento, salvamento e feedback.
- Cartão público: URL, geração local do QR, copiar, abrir, baixar e estados.

Fora do escopo: mudanças no agente, sessão, backend, autenticação, política de retenção/histórico, voz/anexos novos, adoção de Markdown sem decisão específica, criação/edição manual de slug, hospedagem externa de QR ou mudanças no portal público.

## Contratos atuais a preservar

- Chat usa `streamChat` com contexto obtido do usuário autenticado; não substituir seu identificador/contexto por slug nem introduzir seletor de tenant.
- Envio ignora entrada vazia, aguarda contexto autenticado e bloqueia envio simultâneo. Enter sem Shift aciona o fluxo atual.
- Primeiro token não vazio cria a mensagem do assistente; os seguintes acumulam nessa mensagem. Conclusão/erro encerram loading. Erros são comunicados por toast sem virar mensagem da conversa.
- Mensagens administrativas são texto com quebra de linha, sem renderização de HTML/Markdown. Reuso visual deve conservar essa semântica e segurança.
- Ação limpar reinicia a conversa local conforme contrato atual; não redefine o agente, sua base ou dados persistidos.
- Configuração mantém `company_name`, `description`, `tone_of_voice`, `chat_voice_gender`, website, telefone, endereço e horários; `configApi.get/save` conserva contrato e retorno como fonte após salvar.
- Ausência/falha de configuração no carregamento mantém os defaults atuais; não criar novas regras de validação ou campos do mockup como detalhe visual.
- URL pública usa origem atual + `/p/` + slug aparado e codificado; não expõe identificador interno nem usa tenant como fallback.
- QR é gerado localmente por `qrcode`, com correção M, margem 2 e largura 256; fundo claro e contraste de leitura são funcionais. A interface ignora resultado antigo quando o slug muda.
- Copiar usa clipboard; abrir usa nova janela com `noopener,noreferrer`; baixar fornece PNG local e nome associado ao slug. Erro de geração comunica mensagem genérica sem detalhes internos.

## Requisitos observáveis

| ID | Requisito |
| --- | --- |
| DS-15-R01 | As três áreas devem usar cabeçalhos, cards, campos, estados e identidade aprovados nos temas claro/escuro, com diferenças de função compreensíveis. |
| DS-15-R02 | Chat deve preservar contexto autenticado, bloqueios, envio por ação/Enter e streaming sem mensagem vazia, perda ou duplicação de tokens. |
| DS-15-R03 | Vazio, espera, streaming, término e erro devem ser reconhecíveis; mensagens longas e quebras de linha permanecem legíveis como texto seguro, sem novo interpretador de conteúdo. |
| DS-15-R04 | Limpar deve manter efeito local atual, sem ação de reiniciar agente/base; estado e rolagem do chat não podem se perder por mudança puramente visual de largura. |
| DS-15-R05 | Configuração deve manter campos, opções, defaults, regras atuais e contrato de carga/salvamento; sucesso reflete retorno da API e falha comunica erro sem descartar a edição. |
| DS-15-R06 | URL pública deve continuar derivada apenas da origem e do slug codificado, com campo somente leitura; ausência de slug não deve oferecer URL ou QR inventado. |
| DS-15-R07 | QR deve continuar local, escaneável e associado ao slug atual, com contraste/fundo claro preservados no tema escuro; mostrar geração, ausência e falha de forma compreensível. |
| DS-15-R08 | Copiar, abrir e baixar devem manter comportamento, proteção da nova janela e PNG local; falha de QR/clipboard deve comunicar estado sem detalhes internos. |
| DS-15-R09 | Em 1440, 1024, 768 e 390 px, campos, chat e ações devem caber/refluir; mensagens/URLs longas não devem impedir envio, edição ou compartilhamento. |
| DS-15-R10 | Campos devem ter rótulos associados, controles de ícone nomes acessíveis, feedback de envio/geração compreensível e foco visível; teclado/zoom devem permitir operação completa. |
| DS-15-R11 | Não alterar APIs, contexto institucional, autenticação ou permissões, nem introduzir ações ilustrativas, serviços externos de QR ou dependências para satisfazer aparência. |

## Arquivos afetados candidatos

- [Página do agente](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(admin)/agente/page.tsx>).
- [Configurações](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(admin)/configuracoes/page.tsx>).
- [PublicPortalCard](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(admin)/configuracoes/public-portal-card.tsx>) e [testes do cartão](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(admin)/configuracoes/public-portal-card.test.tsx>).
- [PageContainer](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/components/page-container.tsx>), primitivas e eventuais composições já aprovadas de mensagem.
- [API/streamChat/Config](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/lib/api.ts>) como contrato de referência; esta fase não autoriza reescrever autenticação ou backend.

## Critérios de aceitação

| ID / requisitos | Dado / Quando / Então |
| --- | --- |
| DS-15-AC01 · R01, R09 | **Dado** cada tema e largura de referência, **quando** abrir as três áreas com textos/URL longos, **então** a hierarquia aprovada fica visível e campos/ações permanecem acessíveis. |
| DS-15-AC02 · R02, R03 | **Dado** streaming simulado com token vazio e tokens parciais, **quando** enviar, **então** só o primeiro token real inicia o assistente, os demais acumulam uma vez e conclusão libera envio. |
| DS-15-AC03 · R02, R03 | **Dado** entrada vazia, contexto ausente, envio pendente ou erro simulado, **quando** tentar enviar, **então** os bloqueios atuais permanecem e erro encerra loading com feedback seguro. |
| DS-15-AC04 · R03, R04 | **Dado** conversa longa com texto semelhante a HTML, **quando** renderizar, mudar largura e limpar, **então** texto não é executado, resize mantém conversa e limpar afeta somente estado local. |
| DS-15-AC05 · R05 | **Dado** configuração carregada, defaults ou falha de envio em mock, **quando** editar/salvar, **então** campos/opções são preservados, sucesso adota retorno da API e falha mantém edição. |
| DS-15-AC06 · R06, R07 | **Dado** slug válido, ausente e alterado durante geração, **quando** gerar QR, **então** URL usa origem/slug codificado, ausência não inventa conteúdo e resultado antigo não é mostrado para o slug novo. |
| DS-15-AC07 · R07, R08 | **Dado** QR pronto em claro/escuro, **quando** ler/copiar/abrir/baixar, **então** o QR aponta à URL exibida, cópia coincide, abertura mantém proteção e download fornece PNG local. |
| DS-15-AC08 · R07, R08 | **Dado** geração/clipboard com falha simulada, **quando** ocorrer a ação, **então** feedback é legível e não expõe a mensagem interna da exceção. |
| DS-15-AC09 · R09, R10 | **Dado** teclado e zoom de 200%, **quando** enviar, editar e percorrer operações do QR, **então** nomes/foco/rolagem permitem completar as tarefas. |
| DS-15-AC10 · R02, R05, R06, R11 | **Dado** chamadas e interface inspecionadas em mocks, **quando** operar chat/configuração/QR, **então** contexto e APIs atuais permanecem e nenhuma função ilustrativa ou serviço externo é adicionado. |

## Plano de implementação

- [x] Confirmar aprovação, dependências e eventual divisão explícita da fase.
- [x] Padronizar composição do chat, avatar, estados e campo, preservando texto/streaming.
- [x] Padronizar grupos de configuração, rótulos, loading e ação de salvar sem alterar regras.
- [x] Alinhar cartão público e estados do QR, mantendo contraste funcional e slug atual.
- [x] Conferir fluxos com mocks de autenticação/contexto, streaming, configuração, QR e clipboard.
- [ ] Validar teclado, zoom, temas, mensagens/URLs longas e larguras; executar verificações. **Parcial:** teclado/temas/quatro larguras/testes/tipos/lint/build verificados; zoom nativo 200% e conclusão do download pelo navegador pendentes. PNG real ofertado decodificado nos dois temas.
- [x] Registrar evidências, partes concluídas/pendentes e limitações no STATUS para revisão.

## Verificações e evidências

- Executar `pnpm lint`, `pnpm typecheck` e `pnpm test:run "app/(admin)/configuracoes/public-portal-card.test.tsx"` no frontend.
- Testes atuais comprovam geração local, URL por slug, cópia/download e erro seguro de QR; não comprovam abertura real da janela nem leitura por câmera.
- Não há testes específicos atuais de página do agente/configurações no levantamento. Proteger com testes de comportamento relevantes se a extração afetar streaming/estado; complementar com mocks/manualmente e registrar o tipo de evidência.
- Conferir troca de slug com geração atrasada, slug ausente, falha de clipboard, nova janela e PNG; verificar leitura por câmera quando disponível, informando limitação caso não seja feita.
- Capturar chat vazio/streaming/conteúdo longo, configuração e cartão QR em claro/escuro/móvel/desktop. Não usar conta ou configuração real para testar salvamento.
- Executar `pnpm build` antecipadamente se extração/compartilhamento de componentes alterar importações ou fronteiras de renderização.

## Conclusão e aprovações

DS-15 só conclui tecnicamente quando as três áreas forem entregues e verificadas; uma subdivisão parcial continua pendente. Registrar implementação, verificação e aprovação visual separadamente, sem presumir aceite pela ausência de resposta.

A execução autoriza apenas esta fase. Mudanças materiais de contrato, escopo, semântica de mensagem ou direção visual exigem aprovação antes da implementação dependente. Não iniciar consolidação, criar commit ou fazer push automaticamente.

## Registro de execução — 12/10/2026

Autorização explícita da Fase: 15 recebida para v1.0 e contrato comum v1.0. Dependências conferidas e aceitas; baseline limpo `34512e1`. Entrega única, sem revisão material da especificação. Implementação concluída; oito critérios verificados e AC07/AC09 parciais. Resultado aguardando revisão, sem aceite, commit, push ou início da DS-16. Consulte [evidências DS-15](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/evidencias/DS-15.md>).

## Autorização de commit local — 12/10/2026

Após a apresentação do resultado, o usuário solicitou “faça commite das alterações”. Commit local autorizado para a entrega DS-15, com identificação no histórico Git; sem push ou DS-16. A verificação continua parcial em AC07/AC09 e o aceite do resultado permanece aguardando revisão. Os registros anteriores descrevem o estado na entrega, antes desta autorização.
