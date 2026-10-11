# DS-03 — Estrutura e navegação do portal

**Versão:** 1.0.

## Identificação e controle

- Status: **Proposta — aguardando aprovação; não implementada**.
- Fase original: 03 do roteiro, etapa 3A do plano.
- Modelo recomendado: **GPT-6.1 Sol**, esforço **High** (`high`).
- Commit sugerido após revisão e autorização: `refactor(portal): padroniza estrutura e navegacao responsiva`.
- Dependências obrigatórias: DS-00 aprovada com navegação e recolhimento definidos; DS-01 implementada/revisada com marca e tokens. DS-02 é a entrega anterior de validação visual, sem dependência funcional do portal.
- Autorização futura cobre esta estrutura; migração dos conteúdos pertence às DS-04, DS-05 e DS-06.

Consultar [README](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/README.md>), [CONTRATO](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/CONTRATO.md>) e [STATUS](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/STATUS.md>) para sequência, regras comuns e evidências de aprovação.

## Problema e resultado esperado

O portal possui estrutura visual própria em CSS Modules, com tokens paralelos à base Tailwind/shadcn. As referências do UX Pilot apresentam uma estrutura mais clara de navegação, conversa e conteúdo auxiliar para desktop, e navegação inferior no celular.

Esta fase deve produzir uma estrutura pública responsiva comum, consumindo os fundamentos aprovados, sem reescrever o conteúdo de Chat, Eventos ou Locais. O estado institucional e da conversa precisa sobreviver a mudanças puramente visuais.

## Referências e situação atual

- UX Pilot desktop: **EchoMind - Chat Portal**, `ktsYqLA8UvfGZe6riGsa`.
- UX Pilot celular: **EchoMind - Chat Portal**, `3Qj2y1kf1JY6tBztuJCd`.
- Ambos pertencem à página `ThHPmFvVAyXGKTItA3AZ`; dimensões das imagens não são breakpoints obrigatórios.
- [Plano original](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/plano-refatoracao-design-echomind.md>) define as três entradas e o recolhimento do conteúdo auxiliar.
- `PublicPortal` mantém `activeTab`, mensagens e consultas públicas; a rota `/p/[slug]` entrega o slug ao componente.
- A navegação atual usa botões Chat, Eventos e Locais com `aria-current="page"` no selecionado.
- Eventos e mapa possuem classes no mesmo módulo do portal; sua remoção ampla quebraria consumidores ainda não migrados.

## Escopo

- Estrutura externa, marca, cabeçalhos, navegação lateral/inferior e áreas de conteúdo/coluna auxiliar.
- Distribuição responsiva e limites de rolagem; adaptação de hierarquia visual e espaços externos.
- Substituição apenas das classes de estrutura cujos consumidores forem migrados nesta entrega.

Fora do escopo: bolhas de mensagem, Markdown, compositor e FAQs (DS-04); cards de eventos (DS-05); controles e algoritmos de mapas (DS-06); novas rotas públicas, autenticação do aluno e novos dados/API.

## Requisitos observáveis

- **DS-03-R01:** A navegação pública oferece exatamente Chat, Eventos e Locais, mantendo rótulo e identificação acessível inequívocos da entrada selecionada.
- **DS-03-R02:** Em desktop, a estrutura oferece navegação lateral; no celular, navegação inferior. Em cada largura há uma representação operável sem controles duplicados expostos ao teclado/leitor de tela.
- **DS-03-R03:** Nome e conteúdo institucional continuam derivados exclusivamente do slug público recebido pela rota; sem slug ou instituição válida, os estados seguros existentes continuam disponíveis.
- **DS-03-R04:** Mudança de largura e troca da apresentação da navegação não apagam mensagens, rascunho ou estado de envio, nem reiniciam consultas públicas por causa de remontagem visual.
- **DS-03-R05:** A seleção das três entradas continua mostrando o conteúdo atual e preserva os estados existentes; a estrutura não modifica cálculo de rota, eventos ou processamento do chat.
- **DS-03-R06:** A área auxiliar possui espaço conforme DS-00 em desktop largo e se recolhe nas larguras aprovadas, sem bloquear a área principal ou criar rolagem horizontal da página.
- **DS-03-R07:** Navegação inferior, cabeçalho e conteúdo consideram safe areas e rolagem; os controles existentes não ficam cobertos, inclusive ao final de listas extensas.
- **DS-03-R08:** Marca, superfícies, tipografia, bordas e foco da estrutura consomem a base DS-01 nos temas claro e escuro, mantendo legibilidade em 1440, 1024, 768 e 390 px.
- **DS-03-R09:** CSS ainda consumido por chat, eventos ou mapas permanece disponível. Apenas seletores sem consumidores após esta migração podem ser retirados.
- **DS-03-R10:** Cabeçalhos e regiões possuem hierarquia compreensível; navegação mantém foco visível, nomes e operação por teclado, inclusive em zoom e com nome institucional longo.

## Arquivos candidatos e limites

- [PublicPortal](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(public)/components/public-portal.tsx>) — estrutura, distribuição e navegação.
- [CSS do portal](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(public)/components/public-portal.module.css>) — migração seletiva da estrutura.
- [Layout público](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(public)/layout.tsx>) — somente se a composição comum justificar.
- [Rota por slug](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(public)/p/[slug]/page.tsx>) — referência de contrato e eventual composição, sem alterar o vínculo institucional.
- [Testes do portal](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(public)/components/public-portal.test.tsx>) — contrato de navegação, slug e regressão do conteúdo.

Uma composição de navegação pode ser extraída se reduzir repetição real. A extração não deve criar árvores independentes de conteúdo para desktop/celular nem mover estado para componentes remontados por breakpoint.

## Critérios de aceitação

- **DS-03-AC01 — R01/R02/R10:** Dada cada largura prevista, quando o usuário percorre a navegação por teclado, então encontra Chat, Eventos e Locais, identifica a seleção e consegue alternar as três áreas sem controles duplicados acessíveis.
- **DS-03-AC02 — R03:** Dado um slug válido, quando o portal carrega, então as consultas recebem esse slug e a instituição real é exibida; dado link inválido, então o erro seguro e o bloqueio atual do chat permanecem.
- **DS-03-AC03 — R04:** Dada conversa com mensagens e rascunho, quando a largura muda entre desktop/celular, então os dados permanecem e não há nova consulta causada somente pela mudança de estrutura.
- **DS-03-AC04 — R04/R05:** Dada resposta em andamento, quando a navegação muda e retorna ao chat, então o estado pertencente ao portal não é perdido; eventos e locais continuam com suas ações atuais.
- **DS-03-AC05 — R06/R07/R08:** Dado conteúdo longo nos dois temas, quando se testam larguras previstas e zoom, então coluna auxiliar se recolhe conforme DS-00, o conteúdo permanece legível e a navegação não encobre as últimas ações.
- **DS-03-AC06 — R09:** Dado o levantamento de seletores e o diff, quando a fase é revisada, então estilos dos consumidores não migrados continuam existentes e não há exclusão generalizada do módulo CSS.
- **DS-03-AC07 — R08/R10:** Dado nome institucional longo e navegação móvel, quando o foco e a hierarquia são inspecionados, então título, seleção, marca e foco permanecem legíveis e coerentes com DS-01.

## Plano de implementação

- [ ] Conferir decisões de DS-00, base DS-01, aprovação desta fase e estado local.
- [ ] Comparar referências desktop/celular e registrar regras concretas de recolhimento já aprovadas.
- [ ] Mapear classes de estrutura e consumidores compartilhados antes de remover seletores.
- [ ] Implementar a composição externa e navegação preservando a identidade do componente que mantém estado.
- [ ] Reservar a área auxiliar e manter o conteúdo interno atual para as próximas fases.
- [ ] Conferir troca de largura, navegação, conversa em andamento, slug inválido e listas extensas.
- [ ] Executar verificações, registrar imagens/evidências e entregar para revisão sem avançar.

## Verificações e evidências esperadas

- Executar `pnpm lint`, `pnpm typecheck` e a suíte `public-portal.test.tsx` no frontend.
- A suíte existente verifica consultas por slug, três entradas públicas, chat e conteúdo de eventos/mapa esquemático; manter essas expectativas de comportamento.
- Acrescentar teste direcionado somente se a nova composição introduzir risco de remontagem ou regressão de estado ainda não coberto.
- Registrar sequência de antes/depois de uma mudança de largura com conversa/rascunho preservados e contagem de consultas sob mocks.
- Apresentar imagens de Chat, Eventos e Locais em desktop/celular, nos dois temas, destacando a estrutura e o recolhimento.
- Conferir safe areas, teclado, zoom, nome longo e ausência de conteúdo encoberto; viewport reduzido não comprova teclado virtual.
- Antecipar build se houver alteração relevante da composição/importação entre layout e componentes; registrar limitações reais.

## Conclusão e aprovações

A fase está pronta para revisão quando requisitos e critérios possuem evidência, verificações passam ou limitações são tratadas explicitamente, e consumidores não migrados continuam funcionando. STATUS diferencia implementação, verificação e aprovação do usuário.

Nenhuma execução, commit/push ou próxima fase é autorizada pela criação desta spec. Mudança material de navegação ou comportamento exige revisão da spec e aprovação antes da implementação dependente. Todas as tarefas permanecem pendentes.
