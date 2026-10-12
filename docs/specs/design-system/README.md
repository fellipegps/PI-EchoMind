# EchoMind — especificações da refatoração visual

Versão documental: 1.0 · Data: 11/10/2026.

Este conjunto adota **Specification Driven Development (SDD)**: a especificação define o resultado e as condições de aceitação; as tarefas orientam sua implementação; as evidências mostram o que foi verificado. Os textos são contratos de alteração, não uma sequência de prompts extensos.

**Situação atual (12/10/2026): DS-00–DS-06 v1.0 aceitas e registradas em commits locais; DS-06 em 0eab36b, com seus limites documentados. DS-07 v1.0 aprovada, implementada e verificada no escopo disponível, resultado aceito em 12/10/2026 pelo pedido de commit após apresentação da entrega e limitações. DS-08–DS-16 continuam propostas e não iniciadas.** DS-07 unifica sidebar, cabeçalho e containers das oito áreas administrativas, preservando sessão, navegação e conteúdo. Consulte STATUS.md e [DS-07](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/evidencias/DS-07.md>) para critérios, capturas e falha anterior do editor geográfico. Commit local da DS-07 autorizado; identificação no histórico Git. Sem push.

## Documentos de referência

- [Contrato comum](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/CONTRATO.md>): regras compartilhadas, preservações e fluxo de aprovação.
- [Andamento](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/STATUS.md>): status independente da especificação, implementação, evidências e revisão do usuário.
- [Plano e análise originais](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/plano-refatoracao-design-echomind.md>): contexto, diagnóstico e referências do UX Pilot.
- DS-00: direção visual revisada documentalmente, incluindo decisões que não estavam resolvidas pelas imagens; resultado aceito pelo usuário em 11/10/2026.
- DS-01–DS-16: especificações de alteração e de verificação por área.

## Ordem das fases

Cada arquivo contém problema, resultado esperado, limites, requisitos identificados, critérios de aceitação, tarefas, verificações e sugestão de commit. Os modelos/esforços abaixo preservam a recomendação do roteiro anterior; são orientações de trabalho, não requisitos de execução ou seleção automática.

| Ordem | Plano original | Especificação | Modelo sugerido | Esforço |
| --- | --- | --- | --- | --- |
| 00 | Preparação | [DS-00 — Fechar a especificação visual](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/00-direcao-visual.md>) | GPT-6 Astra | Medium |
| 01 | 1 | [DS-01 — Tokens, temas e componentes básicos](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/01-fundamentos.md>) | GPT-6.1 Sol | Extra High |
| 02 | 2 | [DS-02 — Autenticação](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/02-autenticacao.md>) | GPT-6.1 Sol | Medium |
| 03 | 3A | [DS-03 — Estrutura e navegação do portal](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/03-estrutura-portal.md>) | GPT-6.1 Sol | High |
| 04 | 3B | [DS-04 — Chat, mensagens e FAQs públicas](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/04-chat-publico.md>) | GPT-6.1 Sol | High |
| 05 | 4 | [DS-05 — Eventos públicos](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/05-eventos-publicos.md>) | GPT-6.1 Sol | Medium |
| 06 | 5 | [DS-06 — Mapas e locais públicos](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/06-mapas-publicos.md>) | GPT-6 Astra | High |
| 07 | 6 | [DS-07 — Estrutura do painel administrativo](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/07-estrutura-admin.md>) | GPT-6.1 Sol | High |
| 08 | 7 | [DS-08 — Dashboard e gráficos](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/08-dashboard.md>) | GPT-6.1 Sol | High |
| 09 | 8A | [DS-09 — FAQs da base de conhecimento](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/09-faqs.md>) | GPT-6.1 Sol | Medium |
| 10 | 8B | [DS-10 — Documentos, upload e processamento](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/10-documentos.md>) | GPT-6.1 Sol | High |
| 11 | 8C | [DS-11 — Perguntas não respondidas e triagem](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/11-triagem.md>) | GPT-6.1 Sol | Medium |
| 12 | 9A | [DS-12 — Gestão administrativa de eventos](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/12-eventos-admin.md>) | GPT-6.1 Sol | Medium |
| 13 | 9B | [DS-13 — Gestão administrativa de locais](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/13-locais-admin.md>) | GPT-6.1 Sol | Medium |
| 14 | 9C | [DS-14 — Editor de campi e edição geográfica](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/14-editor-campi.md>) | GPT-6 Astra | High |
| 15 | 10 | [DS-15 — Agente, configurações e QR do portal](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/15-agente-configuracoes.md>) | GPT-6.1 Sol | High |
| 16 | 11 | [DS-16 — Consolidação e revisão integrada](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/16-consolidacao.md>) | GPT-6 Astra | High |

## Fluxo de execução

1. Leia esta visão geral, o contrato e a especificação da fase desejada.
2. Autorize a fase por uma mensagem explícita que identifique seu número e aprove a versão da especificação. O prompt geral fornecido abaixo pode ser reutilizado para isso.
3. O executor confere as dependências e registra a autorização recebida. A fase 00 é documental; as demais só começam com a direção visual e as dependências obrigatórias aprovadas.
4. Implemente o escopo autorizado e verifique cada critério de aceitação. As tarefas podem ser ajustadas em detalhes de implementação; os requisitos e limites aprovados não podem ser alterados silenciosamente.
5. Registre evidências e apresente o resultado para revisão. Critério sem evidência permanece pendente; uma validação bloqueada não conta como aprovação.
6. Aguarde a revisão do usuário para avançar por dependências. Commit é opcional e exige autorização própria; não fazer push automaticamente.

Não há necessidade de copiar o conteúdo de cada spec na conversa. É suficiente identificar a fase e apontar para esta pasta. Em uma conversa nova, mantenha acesso ao repositório e ao UX Pilot. Consulte STATUS.md antes de retomar trabalho.

## Prompt geral para qualquer fase

Substitua NN pelo número da fase, de 00 a 16. Este texto só produz autorização quando enviado pelo usuário; sua presença neste arquivo não aprova as propostas.

```text
Fase: NN

Execute esta fase da refatoração do EchoMind usando SDD.

Leia o índice, o CONTRATO.md, o STATUS.md e a especificação DS-NN em:
C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system

Aprovo a versão atual da especificação da fase indicada e autorizo somente o escopo dela. Confira as aprovações e dependências obrigatórias antes de implementar.

Use os requisitos e critérios de aceitação como contrato. Implemente as tarefas necessárias, preserve os comportamentos definidos e valide os critérios com evidências reais. A fase 00 deve produzir somente revisão e documentação da direção visual.

Se surgir uma lacuna material ou uma divergência que exija mudar o resultado aprovado, apresente a alteração proposta antes de implementar a parte dependente. Resolva escolhas rotineiras dentro da especificação sem pedir nova autorização.

Atualize as tarefas, as evidências e o STATUS.md, distinguindo implementação, verificação e revisão. Apresente o resultado e as pendências. Não avance para outra fase, não crie commit e não faça push sem minha instrução.
```

## Como interpretar os estados

Aprovar uma especificação permite iniciar sua implementação, mas não comprova que o resultado foi verificado. “Validada” exige evidência para os critérios obrigatórios; “aceita” exige revisão explícita do usuário. A conclusão do conjunto depende das entregas e critérios obrigatórios, não de todas as caixas de tarefas estarem marcadas.

Detalhes de status, versionamento e evidência estão no CONTRATO.md. O plano original mantém o contexto histórico; em caso de divergência, prevalecem as especificações aprovadas mais recentes.
