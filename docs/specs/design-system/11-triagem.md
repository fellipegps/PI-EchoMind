# DS-11 — Perguntas não respondidas e triagem

**Versão:** 1.0.

**Status:** Proposta — aguardando aprovação. Nenhuma implementação autorizada por este arquivo.
**Fase original:** Prompt 11; etapa 8C do plano.
**Modelo sugerido:** GPT-6.1 Sol (`gpt-6.1-sol`) · Medium (`medium`).
**Commit sugerido, somente após revisão e autorização:** `refactor(triage): padroniza perguntas nao respondidas e revisao`.

## Contrato e dependências

Seguir o [índice](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/README.md>), o [CONTRATO](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/CONTRATO.md>) e o [STATUS](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/STATUS.md>).
Depende de DS-00 aprovada, DS-01, DS-07 e DS-09 implementadas, verificadas e revisadas: estados, estrutura administrativa e padrões de FAQ/formulário.
DS-10 antecede esta fase na ordem geral, mas seu polling/upload não é dependência técnica da triagem.
Não existe preview exclusivo de triagem entre as referências auditadas; aplicar os padrões aprovados ao fluxo existente.

## Problema e resultado esperado

A página já separa pendentes, revisão e ignoradas, mostra agrupamentos e transforma respostas aprovadas em conhecimento.
Sua composição precisa acompanhar o design system sem mudar classificações, efeitos das ações ou destinos.
O resultado deve permitir compreender a pergunta, suas ocorrências/variações e o próximo passo apropriado em telas pequenas e grandes.
Falha de carga atualmente usa toast e não mantém estado persistente distinto da lista vazia; esta migração preserva essa política e registra sua limitação.

## Escopo

- Cabeçalho, filtros existentes, busca, cards, badges, detalhes, diálogos e mensagens atuais.
- Formulário de resposta/revisão da pergunta e confirmação já existente de ignorar.
- Apresentação responsiva, foco, rótulos e estados das operações existentes.

## Fora do escopo

- Novas regras de classificação, algoritmos de agrupamento, automação de aprovação ou alteração dos motivos de revisão.
- Trocar ignorar por exclusão definitiva, adicionar ações em lote ou mudar indexação/publicação da FAQ.
- Alterar endpoints, autorização, isolamento institucional ou destinos após conversão.
- Nova política de carga/retry/erro persistente como condição da migração visual.

## Requisitos observáveis

- **DS-11-R01:** a carga deve continuar consultando `pending`, `review` e `ignored`; filtros e contagens devem refletir o mesmo conjunto recebido, com seleção inicial em pendentes.
- **DS-11-R02:** a busca deve continuar considerando pergunta canônica e variações, sem distinção de maiúsculas/minúsculas e sem misturar os status selecionados.
- **DS-11-R03:** cards devem preservar pergunta canônica, ocorrências, primeira/última data em português, motivos de revisão/ignoradas e expansão das variações disponíveis; nenhuma reclassificação deve ocorrer pela mudança visual.
- **DS-11-R04:** em revisão deve permanecer “Enviar para pendentes”, sem “Responder”; aprovação deve chamar a operação atual e mover o item para pendentes somente após sucesso, atualizando contagens.
- **DS-11-R05:** “Responder” deve continuar disponível para pendentes; o diálogo deve permitir editar pergunta e resposta, manter validação de campos não vazios, limpeza atual e bloqueio do botão de salvamento durante conversão.
- **DS-11-R06:** conversão bem-sucedida deve chamar `unansweredApi.convert` com resposta e pergunta editada conforme contrato, remover o item da lista local e redirecionar para `/base-de-conhecimento`; falha deve manter item/conteúdo e feedback, sem FAQ fictícia.
- **DS-11-R07:** ignorar deve preservar confirmação com efeito descrito sobre repetições/variações, chamada a `ignore` e transição a `ignored` somente após sucesso; cancelamento não deve alterar dados.
- **DS-11-R08:** restaurar deve permanecer disponível em ignoradas, chamar `restore` e mover o item para pendentes somente após sucesso; não criar rota ou ação de exclusão nova.
- **DS-11-R09:** carregamento, ausência de itens por status, busca sem resultado e feedback de erro/sucesso existentes devem acompanhar os padrões aprovados. Preservar a política atual de toast de falha de carga seguido de lista vazia e registrar sua limitação; esta fase não exige novo estado persistente de erro.
- **DS-11-R10:** filtros, busca, expansão, ações e campos devem ter nomes/foco acessíveis e ordem de teclado coerente; texto longo, datas e ações devem caber nas larguras de referência nos dois temas.

## Arquivos afetados candidatos

- [Página de não respondidas](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(admin)/nao-respondidas/page.tsx>).
- [Testes de triagem](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(admin)/nao-respondidas/page.test.tsx>).
- [UnansweredQuestion e unansweredApi](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/lib/api.ts>), referência sem alteração funcional prevista.
- Primitivas existentes de Dialog, AlertDialog, Badge, Button e campos; preferir composição local a alterações globais para um só consumidor.

## Critérios de aceitação

- **DS-11-AC01 — R01/R02:** Dados itens nos três status e variações, quando a página carregar e a busca/filtros forem usados, então contagens e resultados devem conservar status e filtragem atuais.
- **DS-11-AC02 — R03:** Dada pergunta com ocorrências, datas e variações, quando detalhes forem expandidos, então todos os dados disponíveis devem permanecer legíveis, com o motivo atual de revisão/ignorada.
- **DS-11-AC03 — R04:** Dado item em revisão, quando aprovação falhar ou tiver sucesso, então ele deve permanecer em revisão ou passar a pendentes respectivamente; “Responder” não deve aparecer antes da transição.
- **DS-11-AC04 — R05/R06:** Dado item pendente, quando o formulário receber campos vazios, falha ou sucesso, então validação deve impedir envio inválido, falha deve preservar contexto e sucesso deve criar via contrato atual e redirecionar ao destino existente.
- **DS-11-AC05 — R07:** Dada ação de ignorar, quando cancelada, então nenhuma mutação deve ocorrer; quando confirmada com sucesso, então item/variações devem seguir o efeito atual e a contagem de ignoradas deve atualizar.
- **DS-11-AC06 — R08:** Dado item ignorado, quando restauração falhar ou terminar com sucesso, então o item deve permanecer ignorado ou retornar a pendentes respectivamente.
- **DS-11-AC07 — R09/R10:** Dados carregamento, lista vazia, busca sem resultado, mensagens e perguntas longas em 1440, 1024, 768 e 390 px nos dois temas, quando a página for percorrida por teclado, então os estados/controles devem permanecer identificáveis e utilizáveis sem overflow do documento.

## Plano de implementação

- [ ] Confirmar aprovação, dependências e baseline de rotas/ações.
- [ ] Aplicar cabeçalho, filtros, busca e composição dos cards ao design system.
- [ ] Padronizar detalhes, expansão e diálogos mantendo condições de disponibilidade por status.
- [ ] Revisar feedback, nomes acessíveis, foco e layout com textos longos.
- [ ] Verificar transições e conversão usando mocks/dados de teste, sem mutar registros reais.
- [ ] Executar verificações e registrar evidências/limitações no STATUS.

## Verificação e evidências esperadas

- Executar `pnpm lint`, `pnpm typecheck` e `pnpm test:run "app/(admin)/nao-respondidas/page.test.tsx"` no frontend.
- Preservar testes atuais de revisão/aprovação humana e ignorar/restaurar.
- A suíte atual não cobre conversão completa, falhas e busca em variações; verificar esses caminhos com mocks e acrescentar testes somente se a mudança de interação justificar proteção adicional.
- Entregar imagens dos três filtros, detalhe expandido, formulário e confirmação em desktop/celular e ambos os temas.
- Registrar evidência de cancelamento de ignorar, falhas sem transição indevida e destino após conversão.
- Registrar separadamente a limitação preexistente do toast de carga, sem afirmar distinção persistente de erro não implementada.

## Conclusão e aprovação

Implementação/verificação exige critérios evidenciados e efeitos de triagem preservados; aprovação visual do usuário é registrada separadamente.
Mudanças materiais de escopo/spec exigem aprovação antes da implementação dependente.
Não avançar, criar commit ou publicar automaticamente. Estado inicial: **Proposta — aguardando aprovação**.
