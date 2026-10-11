# DS-09 — FAQs da base de conhecimento

**Versão:** 1.0.

**Status:** Proposta — aguardando aprovação. Nenhuma implementação autorizada por este arquivo.
**Fase original:** Prompt 09; etapa 8A do plano.
**Modelo sugerido:** GPT-6.1 Sol (`gpt-6.1-sol`) · Medium (`medium`).
**Commit sugerido, somente após revisão e autorização:** `refactor(knowledge): padroniza gestao de perguntas frequentes`.

## Contrato e dependências

Seguir o [índice](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/README.md>), o [CONTRATO](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/CONTRATO.md>) e o [STATUS](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/STATUS.md>).
Depende de DS-00 aprovada, DS-01 e DS-07 implementadas, verificadas e revisadas: componentes, temas, formulários e estrutura administrativa.
DS-08 antecede esta fase na ordem geral, mas não fornece contrato técnico necessário às FAQs.
Não há tela específica de gestão de FAQs no arquivo UX Pilot auditado; esta fase herda os padrões aprovados, sem afirmar equivalência a um preview inexistente.

## Problema e resultado esperado

A tabela, busca e diálogo já usam primitivas compartilhadas, mas precisam de hierarquia, responsividade, nomes acessíveis e estados consistentes.
O hook `useFaqs` já expõe `loading`, hoje não consumido pelo componente; falha de listagem já gera toast, sem estado persistente distinto.
Excluir FAQ é atualmente uma ação direta, sem confirmação. O roteiro anterior presumiu confirmação existente; esta spec corrige essa suposição e preserva o fluxo atual.
O resultado deve manter a gestão de FAQs e seu limite de exibição pública, com apresentação coerente nos dois temas.

## Escopo

- Cabeçalho e abas da base; composição visual da área FAQs, busca, tabela/cards, formulário e ações.
- Apresentação de `loading` já fornecido pelo hook, lista vazia, busca sem resultado e feedback existente.
- Integração visual mínima comum à aba Documentos; upload/processamento pertencem a DS-10.

## Fora do escopo

- Novas abas/áreas, categorias, filtros adicionais, busca em respostas ou paginação sem comportamento atual.
- Alterar API, permissões, limite de FAQs no chatbot, indexação ou publicação.
- Adicionar confirmação de exclusão: melhoria futura fora desta migração, sem bloquear sua conclusão.
- Reescrever o hook ou introduzir novas políticas de erro/retry para uma necessidade apenas visual.

## Requisitos observáveis

- **DS-09-R01:** a página deve manter somente as abas FAQs e Documentos, com FAQs como seleção inicial, sem criar navegação nova.
- **DS-09-R02:** lista e busca devem preservar as FAQs recebidas e a filtragem atual por pergunta, sem distinção de maiúsculas/minúsculas.
- **DS-09-R03:** criar/editar deve preservar validação de pergunta/resposta não vazias; criar deve manter `show_in_chatbot: false` e editar deve manter o ID e campos do contrato atual.
- **DS-09-R04:** salvar deve impedir envios duplicados e manter campos/saída bloqueados durante a operação conforme hoje; falha deve manter diálogo e conteúdo aberto, sucesso deve atualizar a lista e fechar o diálogo.
- **DS-09-R05:** a alternância de exibição no chatbot deve manter o retorno real da API, badge correspondente e feedback do conflito de limite atual; não deve prometer ativação quando o backend recusar.
- **DS-09-R06:** excluir deve conservar a ação direta atual, remover o item somente após sucesso da API e conservar o item com feedback de erro em falha.
- **DS-09-R07:** o `loading` já exposto deve ser visível de forma acessível; vazio e busca sem resultado devem ter mensagens adequadas. O toast de falha existente deve ser preservado sem afirmar que a lista vazia comprova ausência de dados.
- **DS-09-R08:** busca, switches, botões de editar/excluir e campos devem ter nomes acessíveis ligados à sua função/item; diálogos devem preservar teclado, foco e retorno ao controle de origem.
- **DS-09-R09:** perguntas/respostas longas e ações devem ser utilizáveis em celular e desktop nos dois temas, seguindo tokens e componentes aprovados sem alterar os dados.
- **DS-09-R10:** ajustes na composição compartilhada da aba Documentos não devem alterar seleção de arquivos, upload, limites, processamento ou ciclos assíncronos.

## Arquivos afetados candidatos

- [Página da base](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(admin)/base-de-conhecimento/page.tsx>).
- [FaqTab](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(admin)/base-de-conhecimento/components/faq-tab.tsx>).
- [useFaqs](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(admin)/base-de-conhecimento/hooks/use-faqs.ts>), referência de comportamento; extração não deve alterar seus contratos.
- [Teste de abas](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(admin)/base-de-conhecimento/page.test.tsx>).
- [faqApi e Faq](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/lib/api.ts>), referência sem alteração prevista.

## Critérios de aceitação

- **DS-09-AC01 — R01/R10:** Dada a página aberta, quando as abas forem percorridas, então somente FAQs/Documentos devem existir e os fluxos de documentos devem permanecer íntegros.
- **DS-09-AC02 — R02:** Dadas FAQs com perguntas conhecidas, quando uma busca variar a capitalização, então o resultado deve continuar seguindo a busca atual por pergunta.
- **DS-09-AC03 — R03/R04:** Dado diálogo novo ou de edição, quando dados inválidos ou submissão repetida forem enviados, então validação/bloqueio devem atuar; falha deve manter conteúdo e sucesso deve atualizar a FAQ correta e fechar.
- **DS-09-AC04 — R05:** Dado backend recusando ativação por limite, quando o switch for acionado, então o estado recebido deve ser conservado e o erro deve ser comunicado sem ativação fictícia.
- **DS-09-AC05 — R06:** Dada FAQ existente, quando a exclusão direta falhar ou terminar com sucesso, então o item deve permanecer ou desaparecer respectivamente, sem antecipar resultado.
- **DS-09-AC06 — R07:** Dado carregamento pendente, lista vazia, busca sem resultado ou falha, quando cada condição ocorrer, então carregamento/mensagens/feedback disponíveis devem permanecer reconhecíveis, com a limitação de erro documentada.
- **DS-09-AC07 — R08/R09:** Dadas perguntas/respostas longas e celular/desktop nos dois temas, quando a gestão for usada por teclado, então texto, ações, switch e diálogo devem ser alcançáveis e identificáveis sem overflow do documento.

## Plano de implementação

- [ ] Conferir aprovação, dependências, baseline e contratos atuais.
- [ ] Aplicar cabeçalho/abas comuns e compor a área de FAQs sobre a base aprovada.
- [ ] Expor `loading` existente e mensagens de vazio/busca, conservando feedback de erro atual.
- [ ] Padronizar tabela/cards e diálogo sem mudar operações nem exclusão direta.
- [ ] Associar nomes/rótulos acessíveis a campos, switches e ações.
- [ ] Validar regressões da aba Documentos e operações com fixtures/mocks.
- [ ] Executar verificações e registrar evidências, limitações e arquivos no STATUS.

## Verificação e evidências esperadas

- Executar `pnpm lint`, `pnpm typecheck` e `pnpm test:run "app/(admin)/base-de-conhecimento/page.test.tsx"` no frontend.
- O teste atual protege somente composição das abas; não reportá-lo como cobertura do CRUD.
- Verificar criação, edição com falha, bloqueio em salvamento, exclusão com sucesso/falha e conflito do switch com mocks/dados de teste.
- Se a adaptação alterar interação relevante sem cobertura, adicionar testes de comportamento adequados; não criar testes de classes.
- Entregar imagens de lista, diálogo, carregamento e vazio em desktop/celular e ambos os temas; registrar percurso de foco/teclado.

## Conclusão e aprovação

Os critérios, evidências e limitações devem ser registrados antes de declarar implementação/verificação concluídas.
Revisão e aprovação do usuário continuam separadas; confirmação futura de exclusão não é pré-requisito desta fase.
Mudanças materiais de escopo/spec exigem aprovação antes da implementação dependente.
Não avançar, criar commit ou publicar automaticamente. Estado inicial: **Proposta — aguardando aprovação**.
