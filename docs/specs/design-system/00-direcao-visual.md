# DS-00 — Direção visual e decisões comuns

**Atualização autorizada em 13/10/2026:** o mapa esquemático e sua gestão foram retirados. As referências a esse recurso abaixo pertencem ao histórico da refatoração e não determinam sua manutenção ou restauração. O contrato atual desse escopo está na [retirada autorizada](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/ajustes/2026-10-13-retirada-mapa-antigo.md>); o mapa geográfico de campi permanece.

| Metadado | Valor |
| --- | --- |
| ID | DS-00 |
| Versão | 1.0 |
| Estado da especificação | Aprovada pelo usuário em 11/10/2026 — versão 1.0 |
| Estado da execução | Implementada — somente documentação |
| Estado da verificação | Validada no escopo documental; ver evidências DS-00 |
| Aceite do resultado | Aceito pelo usuário em 11/10/2026 |
| Origem no plano | Preparação |
| Modelo / esforço sugeridos | GPT-6 Astra / Medium |
| Commit sugerido | docs(design): consolida direcao visual da refatoracao |

## Contrato e dependências

Aplicam-se [CONTRATO.md](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/CONTRATO.md>), [README.md](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/README.md>) e [STATUS.md](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/STATUS.md>).

Dependências: Nenhuma fase de implementação. Usa o plano original e os seis designs recuperados do UX Pilot.

Autorização conferida em 11/10/2026: mensagem do usuário identificando **Fase: 00** e declarando “Aprovo a versão atual da especificação indicada e autorizo somente seu escopo.” Abrange esta versão 1.0 e o contrato comum 1.0. Não autoriza DS-01–DS-16, commit ou push. O aceite desta entrega documental permanece separado da aprovação da especificação.

Registro da revisão, referências observadas, método e resultados de contraste: [evidências DS-00](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/evidencias/DS-00.md>).

Após a apresentação da entrega, em 11/10/2026, o usuário declarou “Aprovado. Commite as alterações para seguirmos para o proximo passo (so commitar, sem push)”. Esta mensagem registra o aceite do resultado e autoriza somente seu commit, sem push e sem execução de outra fase.

## Problema e resultado esperado

Os previews definem uma direção clara, mas não resolvem tema escuro, marca única, escalas completas ou todas as versões móveis. Essas decisões precisam ser propostas e revisadas antes de alterar tokens que afetam o sistema inteiro.

Um contrato visual concreto e aprovado para DS-01–DS-16, distinguindo valores visíveis no Styleguide de complementos propostos. A fase 00 modifica somente documentação e registros de revisão.

## Escopo e limites

Paleta semântica, tipografia, espaçamento, raios, marca, estados, comportamento responsivo e limites funcionais. A implementação de qualquer componente ou tela fica fora desta fase.

## Requisitos

- **DS-00-R01:** A direção visual apresenta o azul #0B57D0 como ação principal do tema claro, conserva Geist e define uma família de tokens semânticos para ambos os temas conforme a proposta abaixo.
- **DS-00-R02:** A marca proposta usa o ícone Activity do Lucide em um quadrado azul de cantos arredondados e o nome EchoMind. O assistente usa Sparkles em um avatar circular. Esses símbolos têm papéis distintos e são propostas a aprovar, não assets extraídos dos previews.
- **DS-00-R03:** A escala de tipografia, espaço e raios tem valores documentados e usos explícitos. As medidas ausentes nos previews são identificadas como propostas, sem alegar extração exata da imagem.
- **DS-00-R04:** A navegação pública mantém Chat, Eventos e Locais. O contrato responsivo documenta lateral em desktop, inferior em larguras menores e coluna auxiliar somente quando houver espaço; nenhum recurso ilustrativo amplia o produto.
- **DS-00-R05:** Os estados normal, hover, foco visível, pressionado, desabilitado, carregando, vazio, erro e sucesso têm uma orientação visual comum. Os pares de texto/fundo têm contraste medido; o alvo do projeto é pelo menos 4,5:1 para texto de interface.
- **DS-00-R06:** As referências do UX Pilot têm título, ID e página registrados. Atualizações que mudem materialmente esta direção geram proposta de revisão antes de implementar a parte dependente.
- **DS-00-R07:** A saída da fase contém revisão documental, evidências e solicitação de aceite do resultado; nenhum arquivo da aplicação, design remoto, dependência ou dado real é alterado.

## Direção visual da versão 1.0 — resultado aceito

Os valores abaixo integram a especificação aprovada e o resultado documental aceito pelo usuário em 11/10/2026; ainda não foram aplicados à aplicação. #0B57D0 e a hierarquia 36/24/16/14 px vêm do conteúdo observado; o tema escuro, ajustes semânticos, dimensões e símbolos completam as lacunas.

| Papel / token | Claro | Escuro |
| --- | --- | --- |
| background | #F8FAFC | #020617 |
| foreground | #0F172A | #F8FAFC |
| card / popover | #FFFFFF | #0F172A |
| card-foreground / popover-foreground | #0F172A | #F8FAFC |
| primary | #0B57D0 | #60A5FA |
| primary-foreground | #FFFFFF | #0F172A |
| primary-hover | #083E98 | #93C5FD |
| secondary / muted / accent | #F1F5F9 | #1E293B |
| secondary-foreground / accent-foreground | #0F172A | #F8FAFC |
| muted-foreground | #475569 | #CBD5E1 |
| border / input | #CBD5E1 | #475569 |
| ring | #0B57D0 | #93C5FD |
| success / success-foreground | #047857 / #FFFFFF | #34D399 / #022C22 |
| warning / warning-foreground | #B45309 / #FFFFFF | #FBBF24 / #451A03 |
| destructive / destructive-foreground | #DC2626 / #FFFFFF | #F87171 / #450A0A |
| sidebar / sidebar-foreground | #FFFFFF / #0F172A | #0F172A / #F8FAFC |
| sidebar-accent / sidebar-accent-foreground | #E8F0FE / #0B57D0 | #1E293B / #93C5FD |
| sidebar-primary / sidebar-primary-foreground | primary / primary-foreground | primary / primary-foreground |
| sidebar-border / sidebar-ring | border / ring | border / ring |
| chart-1 | primary | primary |
| chart-2 / chart-3 | #047857 / #B45309 | #34D399 / #FBBF24 |
| chart-4 / chart-5 | #7C3AED / #0369A1 | #C4B5FD / #7DD3FC |

A imagem indica Emerald 500 e Amber 500 como amostras de sucesso/aviso. Os pares semânticos acima usam tons ajustados para leitura; isso é uma proposta complementar explícita. Tokens de gráfico representam séries e não mudam o significado dos indicadores.

### Origem e uso das famílias

Revisão em 11/10/2026, com os seis previews e metadados recuperados pelo MCP em leitura. Os valores da versão 1.0 foram mantidos. “Observado” abaixo significa conteúdo legível ou composição visível no PNG, não extração de CSS ou medição de pixels.

| Família | Observação nas referências | Complemento da versão 1.0 e uso |
| --- | --- | --- |
| Ação principal | Styleguide imprime #0B57D0; ações primárias aparecem em azul. | primary-foreground, primary-hover, ring e toda a variante escura são escolhas semânticas documentadas; usar sempre o par do tema. |
| Superfícies, texto e bordas | Styleguide identifica Foreground como Slate 950 e Muted/Surface como Slate 100; telas usam fundos claros, cards brancos e bordas discretas. | Os HEX de background, foreground, card/popover, secondary/muted/accent, muted-foreground e border/input são a normalização proposta. #0F172A é uma escolha do contrato, não uma transcrição do rótulo Slate 950. |
| Sucesso, aviso e erro | Styleguide identifica Emerald 500, Amber 500 e Red 600. | Tons semânticos e respectivos foregrounds da tabela priorizam leitura; não copiar as amostras de sucesso/aviso como fundo de texto branco sem medir o par. |
| Sidebar | Chat desktop e painel mostram navegação lateral e item ativo em azul. | sidebar, sidebar-accent, sidebar-primary, borda e foco usam os pares documentados; o tema escuro é complementar. |
| Gráficos | Painel mostra séries em azul e hierarquia de métricas. | chart-1–chart-5 são a paleta complementar; rótulos usam foreground/muted-foreground sobre superfície, e as séries mantêm o significado dos dados reais. |
| Tipografia | Styleguide imprime 36, 24, 16 e 14 px. Geist já é carregada pelo projeto. | Fonte preservada; entrelinhas, título móvel de 28 px e legenda de 12 px são complementos. Títulos usam a hierarquia abaixo, sem impor 36 px a todas as páginas. |
| Espaço, raios, elevação e controles | Há respiro, cantos arredondados e relevo discreto, sem medidas editáveis no MCP. | Escalas, dimensões mínimas e sombras abaixo são propostas explícitas; não medidas do PNG. |
| Marca e avatar | As telas alternam símbolo de onda/quadro, raio e brilho. | Activity no quadrado azul identifica EchoMind; Sparkles no círculo identifica o assistente. São escolhas unificadoras da spec, não assets recuperados. |
| Estados e responsividade | Há estados normais/ativos e duas composições de chat; as seis imagens são claras. | Estados interativos, tema escuro, tablet, breakpoints e adaptação das demais telas seguem as regras abaixo; não há preview remoto que os comprove. |

### Restrições de uso verificadas por contraste

O cálculo em sRGB foi executado sobre os HEX da tabela, sem opacidade, usando luminância relativa e razão de contraste da WCAG. As 52 combinações avaliadas e o método reproduzível estão nas evidências. Das combinações avaliadas, 51 atingem 4,5:1; uma não deve ser adotada:

- **destructive como texto sobre muted/secondary/accent no tema claro:** #DC2626 sobre #F1F5F9 resulta em **4,4083:1** e fica abaixo da meta. Apresentar a mensagem de erro sobre card/popover branco (**4,8294:1**) ou background (**4,6158:1**), mantendo o mesmo token e a associação textual ao campo/ação. Essa restrição esclarece o uso dos pares existentes; não muda a paleta nem os requisitos aprovados.
- O menor contraste das combinações de texto permitidas avaliadas é warning sobre muted no tema claro: **4,5838:1**. Não reduzir opacidade de textos/placeholders/estados para obter aparência discreta sem recalcular o resultado composto.
- Foco usa ring opaco com o afastamento sobre a superfície. border/input/sidebar-border não são cores de texto e não comprovam, isoladamente, contraste de limites de controles. A identificação de controles, o foco renderizado e a distinção das séries continuam sujeitos à verificação das fases de implementação; esta revisão não certifica a aplicação.

Não foi identificada atualização material dos previews que exija uma nova versão. Alterar esses valores, a marca, o escopo funcional ou as regras de composição exige revisão da spec antes de executar a parte dependente.

### Escalas e comportamento

- Fonte de interface: Geist; mono apenas para conteúdo que já demande leitura monoespaçada.
- Título de destaque: 36/40 px em desktop, 28/36 px em telas estreitas; cabeçalho comum de página: 24/32 px.
- Texto principal: 16/24 px; rótulos e texto denso administrativo: 14/20 px; legenda auxiliar proposta: 12/16 px.
- Espaçamento base: 4, 8, 12, 16, 24, 32 e 48 px; padding de página proposto: 16 px em telas estreitas e 24 px em desktop.
- Raio base: 12 px; controles 8 px, cards comuns 16 px, diálogos 20 px e card de autenticação 24 px. Preservar a relação dos aliases de raio do tema ao implementar.
- Sombras: discretas para elevação de card/dialog; evitar gradientes novos ou sombras fortes em cada componente.
- Foco: contorno/anel visível em ring, sem depender apenas de mudança de cor do texto. Erro mantém mensagem textual e associação ao campo.
- Movimento: transições curtas de cor/estado; sem movimento essencial à compreensão e com redução de movimento respeitada.

| Estado | Orientação visual proposta |
| --- | --- |
| Normal | Usar os pares semânticos do papel do componente e manter rótulo legível. |
| Hover | Ação primária usa primary-hover com primary-foreground; ações secundárias usam accent. Não deslocar conteúdo. |
| Pressionado | Manter a diferenciação de hover com indicação interna discreta de pressão; controles alternáveis expõem também seu estado selecionado. |
| Foco visível | Anel de 2 px em ring com afastamento de 2 px, sem substituir o rótulo ou depender de hover. |
| Desabilitado | Manter rótulo legível, distinguir indisponibilidade por aparência e semântica e impedir ativação; não depender apenas de baixa opacidade. |
| Carregando | Indicador e texto contextual, preservando espaço; bloquear duplicação apenas quando o fluxo atual exigir. |
| Vazio | Mensagem contextual e próxima ação somente quando ela já existir; preservar a política de erro de cada fluxo. |
| Erro | Mensagem textual com papel destructive, associada ao campo/ação quando aplicável; preservar a política atual do fluxo. |
| Sucesso | Mensagem/ícone com papel success e texto que indique o resultado, respeitando notificações existentes. |

| Contexto de controle | Dimensões propostas |
| --- | --- |
| Botões, campos e ações de toque no portal/autenticação | Altura ou área acionável mínima de 44 px; ações somente com ícone têm área de pelo menos 44 × 44 px. |
| Controles administrativos densos em desktop | Altura mínima visual de 36 px; em interfaces de toque, área acionável mínima de 44 × 44 px. |
| Controle compacto ou integrado ao mapa | Pode preservar a dimensão visual da biblioteca, garantindo área acionável adequada sem sobrepor outro controle; exceções essenciais devem ser identificadas e revisadas. |

Estas são propostas de contrato visual; sua adoção não constitui certificação de acessibilidade. Rótulos, contraste, semântica e operação devem ser verificados na implementação.

| Contexto | Regra responsiva proposta |
| --- | --- |
| Portal ≥ 1024 px | Navegação lateral de 224 px e conteúdo flexível com largura mínima zero. |
| Portal ≥ 1280 px | Coluna auxiliar de até 288 px para FAQs/eventos reais, se a conversa continuar utilizável. |
| Portal < 1024 px | Navegação inferior com espaço reservado e safe area; coluna auxiliar recolhida. |
| Chat móvel | Campo de envio e navegação não cobrem mensagens; conteúdo pode rolar; teclado virtual precisa de validação própria. |
| Autenticação | Conteúdo central até 448 px, com margens em telas estreitas. |
| Administrativo | Sidebar já existente adaptável; cabeçalho até 64 px; páginas padrão até 1200 px, formulários até 896 px; mapas podem ocupar a largura disponível. |
| Mapas públicos | Em desktop, controles em painel de até 320 px ao lado do mapa flexível; em telas estreitas, controles empilhados e mapa com altura mínima proposta de 320 px, sem cobrir ações, legenda ou créditos. |
| Cards/listas | Uma coluna quando necessário; número de colunas responde ao conteúdo, sem altura fixa que corte texto. |

São regras propostas, não dimensões extraídas do PNG. Coordenadas geográficas e esquemáticas mantêm seus modelos existentes. Nenhum breakpoint exige reescrita funcional.

Para deixar os contextos de revisão explícitos: 390 px (celular) e 768 px (tablet) seguem a navegação inferior sem coluna auxiliar; 1024 px usa lateral sem coluna auxiliar; 1440 px admite lateral e coluna auxiliar condicional. São leituras das regras aprovadas, não novos breakpoints nem validações da aplicação. Teclado virtual, safe area e interação por toque só poderão ser verificados nas fases correspondentes.

## Referências

Página UX Pilot: ThHPmFvVAyXGKTItA3AZ.

| Título retornado pelo MCP | design_id | Papel nesta revisão |
| --- | --- | --- |
| EchoMind - Styleguide | 1Y8TYWWcoY7N8NBOJS1n | Fundamentos e componentes |
| EchoMind - Chat Portal | 3Qj2y1kf1JY6tBztuJCd | Composição de celular |
| EchoMind - Chat Portal | ktsYqLA8UvfGZe6riGsa | Composição desktop |
| EchoMind - Events and Locations | k5WjrM3paBG7rWH7cnmR | Cards de eventos e categorias de locais |
| EchoMind - Admin Dashboard Primal | hldl1brk4q4O5f5XT8Nm | Densidade e hierarquia administrativa |
| EchoMind - Login | zWCKHDtCGxmxEmkSl0pe | Composição de autenticação |

Todos retornaram status completed e a página acima. Links dos seis previews, dimensões observadas no navegador e diferenças deliberadas em relação ao contrato estão no registro de evidências.

Limites funcionais: perfil/conta do aluno, voz, anexos, atendimento humano, notas/horários acadêmicos, documentos públicos, sessão fixa de 30 dias, reinício do agente e métricas ilustrativas dependem de escopos separados.

## Critérios de aceitação

- **DS-00-AC01** (DS-00-R01, DS-00-R03): Dado o conjunto de tokens proposto, quando a revisão documental é feita, então existem valores claro/escuro, papéis e indicação de origem para cada família usada pelas telas.
- **DS-00-AC02** (DS-00-R02, DS-00-R04): Dadas as seis referências, quando a direção é comparada entre telas, então há uma marca única, avatar distinto e três entradas públicas, com comportamento para desktop, tablet e celular explicitado.
- **DS-00-AC03** (DS-00-R03, DS-00-R05): Dados os estados, dimensões e pares de texto/fundo propostos, quando a revisão documental e o cálculo de contraste são feitos, então cada estado tem orientação verificável e cada contexto de controle tem dimensão mínima; valores e método de contraste são registrados, e pares abaixo da meta são corrigidos ou permanecem pendentes, nunca declarados aprovados.
- **DS-00-AC04** (DS-00-R06): Dado um preview atualizado que contradiz uma decisão aprovada, quando a diferença é material, então o impacto e a revisão da spec são apresentados antes da mudança dependente.
- **DS-00-AC05** (DS-00-R07): Dada a conclusão da revisão, quando o estado do repositório é conferido, então as mudanças desta fase são exclusivamente documentais e o aceite do usuário é registrado separadamente da verificação.

## Arquivos candidatos

- [Plano de origem](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/plano-refatoracao-design-echomind.md>)
- [Esta spec](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/00-direcao-visual.md>)
- [Andamento](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/STATUS.md>)

A lista orienta a implementação; não exige alterar todos os arquivos e não limita extrações necessárias dentro do escopo.

## Tarefas de implementação

- [x] Conferir metadados/previews dos seis designs em leitura e registrar data/limitações da observação.
- [x] Revisar a proposta de valores e layouts desta spec, medindo pares de contraste e identificando os complementos ao Styleguide.
- [x] Registrar somente ajustes documentais necessários; nenhuma revisão material foi necessária. Restrição de contraste documentada sem alterar tokens.
- [x] Criar o registro de evidências DS-00 e apresentar a direção para aceite do resultado.
- [x] Atualizar STATUS.md com autorização real, verificação documental e situação do aceite.

## Verificações e evidências

Revisão de conteúdo e links, cálculo de contraste dos pares propostos e rastreabilidade das decisões. Não executar testes/build da aplicação apenas para esta fase documental.

Criar o registro de evidências DS-00 apenas durante a execução, conforme o contrato comum. Mapear cada critério a um resultado observado ou pendência; não presumir verificação pela existência da spec.

## Condição de conclusão e revisão

Requisitos obrigatórios atendidos, critérios verificáveis com evidências reais, pendências registradas e entrega apresentada para aceite. Aprovação da spec, implementação, validação e aceite do resultado são estados separados. Commit e push não são automáticos.

## Histórico

- 11/10/2026 — versão 1.0: proposta documental inicial; execução não iniciada; nenhuma aprovação atribuída ao usuário.
- 11/10/2026 — execução autorizada pelo usuário para DS-00 v1.0. Revisados seis previews, origens, layouts e contraste; esclarecido uso de destructive sobre superfícies. Valores, requisitos e critérios mantidos. Entrega documental verificada; aceite do resultado aguardando revisão. Sem avanço de fase, commit ou push.
- 11/10/2026 — resultado documental aceito explicitamente pelo usuário; commit da entrega autorizado, sem push. DS-01–DS-16 permanecem não iniciadas.

