# PR 20 — Aba Documentos real

## Objetivo

Substituir dados simulados por listagem, upload, polling, erros e exclusão reais usando o cliente da PR 19.

## Contexto

A página/aba já existe e deve ser reaproveitada. Não criar página nova nem redesenhar a base de conhecimento inteira.

## Pré-requisitos

- PR 19 mergeada.
- Contratos backend disponíveis e testes frontend configurados.

## Dependências

Obrigatórias: PR 19.

Não depende de: eval, Hybrid Search ou CD.

Paralelização: não deve conflitar com outro redesenho de `document-tab.tsx`.

## Escopo desta PR

- Remover documento mock, estado como fonte definitiva e toast de teste.
- Buscar lista no carregamento/refresh.
- Aceitar `.pdf,.txt,.docx`, validar tipo/tamanho no cliente como conveniência e enviar metadata opcional.
- Mostrar estado de upload, `pending/processing/ready/error`, chunk count e erro seguro.
- Fazer polling ~2s apenas enquanto houver itens ativos; parar em ready/error e limpar timer em unmount.
- Excluir somente quando permitido e remover da UI após sucesso.
- Manter drag-and-drop e padrões visuais atuais.
- Testar estados, polling, retry, refresh lógico e exclusão.

## Arquivos provavelmente envolvidos

- `echomind-front/app/(admin)/base-de-conhecimento/components/document-tab.tsx`
- `document-tab.test.tsx`
- componentes/tipos locais estritamente necessários

## Implementação

Tratar loading inicial, upload e polling como estados distintos. Em erro, manter item/lista coerente e permitir retry da listagem. Metadata opcional pode usar diálogo/form pequeno sem bloquear campos vazios.

## Regras técnicas

- Servidor continua autoridade para validação.
- Não remover item antes do DELETE 2xx.
- Evitar timers duplicados, update após unmount e polling quando nada processa.
- Preservar acessibilidade de input/estado/erro.

## Não implementar nesta PR

- página nova ou redesign amplo;
- múltiplos uploads concorrentes se contrato é um por request;
- progress de processamento falso;
- edição/reprocessamento de documento;
- chat/citações visuais;
- E2E/deploy;
- backend.

## Testes obrigatórios

- Seleção e drag/drop PDF/TXT/DOCX.
- Rejeição cliente de formato/tamanho sem chamar API.
- Loading/lista vazia/erro e retry.
- Upload inclui metadata e mostra retorno 202.
- Badges pending/processing/ready/error e chunk count.
- Polling continua/para corretamente e limpa timer.
- DELETE só atualiza após sucesso; falha preserva item.
- Lint, typecheck, test:run e build.

## Critérios de aceite

- Nenhum mock documental permanece.
- Lista e exclusão sobrevivem a refresh por dependerem do backend.
- Todos os estados do contrato são visíveis e testados.

## Definition of Done

UI existente conectada, acessível e com gate frontend verde, sem mudança fora da aba.

## Riscos e cuidados

Fake timers e promises podem produzir testes frágeis; controlar ambos. Não misturar loading global e polling a ponto de piscar a tela inteira.

## Resultado esperado

Administrador opera o pipeline real pela aba já existente.

## Instrução final ao Codex

Conecte exclusivamente a aba existente ao cliente real, rode os testes e pare.
