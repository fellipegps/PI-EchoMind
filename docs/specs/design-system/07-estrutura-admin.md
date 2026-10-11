# DS-07 — Estrutura do painel administrativo

**Versão:** 1.0.

**Status:** Proposta — aguardando aprovação. Nenhuma implementação autorizada por este arquivo.
**Fase original:** Prompt 07; etapa 6 do plano.
**Modelo sugerido:** GPT-6.1 Sol (`gpt-6.1-sol`) · High (`high`).
**Commit sugerido, somente após revisão e autorização:** `refactor(admin): unifica sidebar cabecalhos e containers`.

## Contrato e dependências

Esta especificação segue o [índice](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/README.md>), o [contrato de execução](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/CONTRATO.md>) e o [registro de status](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/STATUS.md>).
Depende de DS-00 aprovada e DS-01 implementada, verificada e revisada: marca, tokens, temas, estados e primitivas.
As entregas públicas anteriores não são dependências técnicas do painel; a ordem geral e qualquer autorização continuam registradas no STATUS.
Referência visual: UX Pilot **EchoMind - Admin Dashboard Primal**, design `hldl1brk4q4O5f5XT8Nm`, página `ThHPmFvVAyXGKTItA3AZ`.
Larguras e grupos concretos devem seguir a especificação visual aprovada em DS-00; lacunas devem ser propostas antes da implementação dependente.

## Problema e resultado esperado

A sidebar possui um único grupo, enquanto as páginas usam wrappers com larguras e espaçamentos diferentes.
O layout administrativo já protege a sessão, oferece alternância de tema e navegação móvel por componentes existentes.
O resultado esperado é uma estrutura reconhecível e consistente para todas as páginas do painel, conservando seus fluxos e conteúdo.
Um mapa pode ocupar largura maior que um formulário sem criar regras arbitrárias em cada consumidor.

## Escopo

- Sidebar, marca, grupos, estado ativo, saída da conta e composição do cabeçalho existente.
- Variantes explícitas de PageContainer e padrão compartilhado de título, descrição e ações de página.
- Ajustes mínimos dos wrappers consumidores para integrar a estrutura aprovada.
- Navegação e distribuição do espaço em desktop, larguras intermediárias e celular.

## Fora do escopo

- Redesenhar conteúdo de dashboard, FAQs, documentos, triagem, mapas e configurações nesta fase.
- Busca global, notificações, perfil ou controles ilustrativos que não tenham função atual.
- Alterar Supabase/Auth, contratos de API, duração de sessão, permissões ou destinos de navegação.
- Reescrever o componente base da sidebar sem necessidade demonstrada.

## Requisitos observáveis

- **DS-07-R01:** a estrutura deve usar marca, superfícies, espaçamentos, textos e foco aprovados em DS-00/DS-01 nos dois temas.
- **DS-07-R02:** a navegação deve manter os destinos `/dashboard`, `/base-de-conhecimento`, `/campi`, `/locais`, `/eventos`, `/nao-respondidas`, `/agente` e `/configuracoes`, mesmo quando agrupados visualmente.
- **DS-07-R03:** a página atual deve permanecer identificável por estado ativo, incluindo teclado e contraste; agrupar os itens não deve criar destinos novos.
- **DS-07-R04:** o botão da sidebar deve continuar abrindo a navegação móvel; seus itens e a saída devem continuar alcançáveis e operáveis por teclado.
- **DS-07-R05:** a composição deve preservar verificação inicial da sessão, sincronização de token, redirecionamento ao login, assinatura de mudanças de sessão e sua limpeza. Conteúdo protegido não deve aparecer antes da autorização atual.
- **DS-07-R06:** alternar tema e sair da conta devem manter seus efeitos existentes; a reorganização não deve desmontar páginas por uma mudança puramente visual.
- **DS-07-R07:** PageContainer deve oferecer papéis explícitos para conteúdo padrão, formulário estreito e mapa/tabela largo, conservando compatibilidade com `children` e `className` dos consumidores.
- **DS-07-R08:** título, descrição e ações de página devem ter hierarquia comum; wrappers ajustados devem manter formulários, tabelas, mapas e ações existentes disponíveis.
- **DS-07-R09:** cabeçalho fixo, sidebar, rolagem e conteúdo devem coexistir sem sobreposição de controles ou overflow horizontal do documento nas larguras de referência.

## Arquivos afetados candidatos

Os caminhos delimitam investigação; não autorizam modificar todos os arquivos nem alterar seus contratos.

- [Layout administrativo](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(admin)/layout.tsx>).
- [Sidebar da aplicação](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/components/app-sidebar.tsx>).
- [PageContainer](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/components/page-container.tsx>).
- [Primitiva Sidebar](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/components/ui/sidebar.tsx>) e [alternância de tema](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/components/mode-toggle.tsx>).
- Wrappers das páginas administrativas, somente quando necessário para adotar o container/cabeçalho; registrar a lista final no STATUS.
- [API/Auth como referência de contrato](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/lib/api.ts>), sem mudança funcional prevista.

## Critérios de aceitação

- **DS-07-AC01 — R01/R03:** Dado o painel em tema claro ou escuro, quando uma rota for aberta, então marca, foco e item ativo devem seguir a base aprovada e identificar a área atual.
- **DS-07-AC02 — R02/R04:** Dado desktop ou celular, quando o usuário percorrer a navegação e abrir cada item, então todos os oito destinos atuais devem permanecer acessíveis; o menu móvel deve abrir pelo controle existente.
- **DS-07-AC03 — R05:** Dada sessão ausente ou rejeitada, quando o layout verificar acesso, então deve ocorrer o redirecionamento atual ao login sem exibir conteúdo protegido; desmontar deve limpar a assinatura como antes.
- **DS-07-AC04 — R06:** Dada sessão válida, quando tema ou saída forem acionados, então os efeitos atuais devem ocorrer e a simples adaptação de largura não deve reiniciar o conteúdo da página.
- **DS-07-AC05 — R07/R08:** Dadas páginas padrão, formulário e mapa/tabela, quando renderizadas com a variante adequada, então a hierarquia deve ser comum e seus controles/conteúdo devem permanecer íntegros.
- **DS-07-AC06 — R09:** Dadas larguras de 1440, 1024, 768 e 390 px, quando conteúdo longo for percorrido, então cabeçalho, sidebar e ações devem permanecer utilizáveis sem sobreposição; tabelas podem ter rolagem local acessível.

## Plano de implementação

- [ ] Confirmar aprovação da spec e dependências no STATUS; conferir alterações locais e instruções do repositório.
- [ ] Recuperar a referência pertinente pelo MCP ou registrar a limitação e a referência verificada disponível.
- [ ] Inventariar wrappers atuais e propor a correspondência de cada um às variantes aprovadas.
- [ ] Compor sidebar, grupos, marca e cabeçalho sobre os componentes existentes.
- [ ] Integrar variantes/cabeçalho apenas nos consumidores necessários, sem migrar seu conteúdo interno.
- [ ] Revisar sessão, tema, saída, navegação móvel, rolagem e acesso por teclado.
- [ ] Executar verificações, capturar evidências e atualizar STATUS com arquivos e limitações reais.

## Verificação e evidências esperadas

- No frontend, executar `pnpm lint` e `pnpm typecheck`; executar testes existentes das páginas cujos wrappers mudarem.
- Exercitar acesso válido/inválido com mocks ou ambiente de teste; não alterar sessão/conta real para criar cenários.
- Anexar imagens de sidebar/cabeçalho em desktop e celular nos dois temas, incluindo página com tabela larga e página de mapa.
- Registrar a matriz de rotas preservadas e o resultado do percurso por teclado, alternância de tema e saída.
- Se houver alteração relevante de importação/renderização, antecipar `pnpm build` conforme CONTRATO.
- Testes novos só se necessários para proteger navegação/sessão relevante; não testar classes de espaçamento.

## Conclusão e aprovação

A fase só pode ser declarada implementada e verificada com os critérios acima evidenciados e as limitações registradas.
Revisão visual e aprovação do usuário são estados separados; checklist concluído não comprova aprovação.
Mudanças materiais de escopo ou especificação devem ser aprovadas antes da implementação dependente.
Não avançar, criar commit ou publicar automaticamente. Esta entrega permanece **Proposta — aguardando aprovação**.
