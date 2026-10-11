# DS-01 — Fundamentos e componentes compartilhados

| Metadado | Valor |
| --- | --- |
| ID | DS-01 |
| Versão | 1.0 |
| Estado da especificação | Proposta — aguardando aprovação |
| Estado da execução | Não iniciada |
| Origem no plano | 1 |
| Modelo / esforço sugeridos | GPT-6.1 Sol / Extra High |
| Commit sugerido | refactor(ui): unifica tokens e componentes do design system |

## Contrato e dependências

Aplicam-se [CONTRATO.md](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/CONTRATO.md>), [README.md](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/README.md>) e [STATUS.md](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/STATUS.md>).

Dependências: DS-00 com direção visual e resultado documental aceitos pelo usuário.

## Problema e resultado esperado

O portal tem tokens locais e o painel usa a paleta padrão do shadcn. Componentes e notificações não compartilham integralmente a identidade e o contexto de tema.

Uma única base semântica clara/escura disponível para todas as fases, com componentes básicos coerentes e uma amostra visual verificável.

## Escopo e limites

Tema global, primitivas existentes, marca compartilhada e integração do Toaster. A migração dos layouts e conteúdos das telas pertence às próximas fases.

## Requisitos

- **DS-01-R01:** O tema global expõe os tokens de DS-00 por variáveis e aliases consumíveis pelo Tailwind, incluindo tokens de estado, sidebar, foco e gráficos; a duplicação de valores não cria uma segunda paleta pública.
- **DS-01-R02:** Button, Input, Label, Card, Badge e demais primitivas tocadas conservam suas props, variantes e semântica acessível. Consumidores existentes não precisam reescrever contratos de uso para continuar funcionando.
- **DS-01-R03:** Componentes básicos apresentam os estados aplicáveis de DS-00 nos dois temas. Botões, campos e ações de toque do portal/autenticação têm altura ou área acionável mínima de 44 px; controles administrativos densos podem ter altura visual de 36 px, com área acionável mínima de 44 × 44 px em interfaces de toque. Exceções de integração seguem a revisão prevista em DS-00.
- **DS-01-R04:** A fonte e os raios seguem DS-00 e os aliases existentes do tema mantêm uma relação consistente. Os novos componentes de marca/avatar cumprem os papéis distintos aprovados.
- **DS-01-R05:** O Toaster recebe o contexto do ThemeProvider e acompanha sua seleção; notificações mantêm o conteúdo e os estados atuais.
- **DS-01-R06:** A amostra visual de desenvolvimento ou artefato de revisão permite inspecionar primitivas e estados. Nenhuma galeria técnica é adicionada à navegação pública do produto.
- **DS-01-R07:** As telas ainda não migradas continuam funcionando; efeitos globais em login, portal e painel são documentados em imagens e não são confundidos com conclusão da migração dessas telas.

## Limites de migração

Componentes novos de composição podem ser criados dentro do frontend quando necessários. Seus nomes e arquivos são escolhas de implementação; a API das primitivas existentes é um contrato de preservação. CSS Modules do portal e do navegador de campus não são eliminados nesta fase.

## Critérios de aceitação

- **DS-01-AC01** (DS-01-R01, DS-01-R04): Dada a direção aprovada, quando os tokens e aliases são inspecionados, então os papéis claro/escuro existem e componentes tocados não introduzem uma paleta paralela.
- **DS-01-AC02** (DS-01-R02, DS-01-R03): Dados os consumidores de Button/Input/Card, quando ações, foco e validação são exercitados, então contratos e interações existentes funcionam com a nova aparência nos dois temas.
- **DS-01-AC03** (DS-01-R05): Dada a seleção de tema, quando uma notificação de teste é exibida, então o Toaster acompanha o contexto do tema e mantém mensagens/ícones esperados.
- **DS-01-AC04** (DS-01-R06): Dada a amostra de componentes, quando revisada, então mostra os estados essenciais e não cria uma nova entrada de navegação no produto.
- **DS-01-AC05** (DS-01-R07): Dadas telas ainda não migradas, quando executadas após a mudança de base, então não há perda funcional e os efeitos visuais indiretos estão registrados.

## Arquivos candidatos

- [Tema global](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/globals.css>)
- [Layout raiz](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/layout.tsx>)
- [Button](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/components/ui/button.tsx>)
- [Input](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/components/ui/input.tsx>)
- [Card](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/components/ui/card.tsx>)
- [Toaster](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/components/ui/sonner.tsx>)
- [ThemeProvider](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/components/theme-provider.tsx>)

A lista orienta a implementação; não exige alterar todos os arquivos e não limita extrações necessárias dentro do escopo.

## Tarefas de implementação

- [ ] Mapear tokens existentes e aliases exigidos por DS-00, mantendo compatibilidade de nomes e consumidores.
- [ ] Aplicar os valores aprovados e ajustes das primitivas sem migrar conteúdo de telas.
- [ ] Implementar composição compartilhada de marca/avatar somente onde a fase permite, sem forçar uso global antes das migrações.
- [ ] Corrigir o contexto de tema do Toaster preservando suas props.
- [ ] Produzir a amostra visual e verificar consumidores principais em ambos os temas.
- [ ] Registrar evidências e atualizar andamento para revisão.

## Verificações e evidências

pnpm lint; pnpm typecheck; teste existente components/ui/button.test.tsx. Inspeção visual de estados e consumidores em desktop/celular; build se a mudança de importação/renderização exigir. Não escrever testes que apenas enumerem classes.

Criar o registro de evidências DS-01 apenas durante a execução, conforme o contrato comum. Mapear cada critério a um resultado observado ou pendência; não presumir verificação pela existência da spec.

## Condição de conclusão e revisão

Requisitos obrigatórios atendidos, critérios verificáveis com evidências reais, pendências registradas e entrega apresentada para aceite. Aprovação da spec, implementação, validação e aceite do resultado são estados separados. Commit e push não são automáticos.

## Histórico

- 11/10/2026 — versão 1.0: proposta documental inicial; execução não iniciada; nenhuma aprovação atribuída ao usuário.

