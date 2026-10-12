# DS-10 — Documentos, upload e processamento

**Versão:** 1.0.

**Status:** v1.0 aprovada pelo usuário em 12/10/2026; implementação concluída e verificação validada no escopo local disponível. Resultado aceito explicitamente em 12/10/2026.
**Fase original:** Prompt 10; etapa 8B do plano.
**Modelo sugerido:** GPT-6.1 Sol (`gpt-6.1-sol`) · High (`high`).
**Commit sugerido, somente após revisão e autorização:** `refactor(documents): padroniza upload e acompanhamento de documentos`.

## Contrato e dependências

Seguir o [índice](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/README.md>), o [CONTRATO](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/CONTRATO.md>) e o [STATUS](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/STATUS.md>).
Depende de DS-00 aprovada e DS-01, DS-07 e DS-09 implementadas, verificadas e revisadas: base visual, estrutura administrativa e composição das abas.
Não há preview exclusivo de documentos no arquivo UX Pilot auditado; herdar padrões aprovados e conservar contratos reais.
O roteiro anterior presumiu exclusão confirmada; o código atual exclui diretamente. Esta spec preserva a operação direta e seus bloqueios.

## Problema e resultado esperado

Upload, metadados e listagem já possuem validações e proteções assíncronas importantes; precisam de apresentação consistente sem simplificar esses mecanismos.
O resultado esperado é uma aba legível e responsiva para selecionar documento, acompanhar processamento e excluir itens permitidos.
Status e erros devem representar resultados reais, inclusive quando listagens antigas terminarem depois de uma mutação.

## Escopo

- Área de seleção/arraste, metadados opcionais, lista, status, chunks, ações e mensagens.
- Composição responsiva e acessível sobre tokens e primitivas aprovados.
- Extrações locais necessárias à apresentação, preservando o comportamento dos efeitos e referências.

## Fora do escopo

- Novos formatos, upload em lote, progresso percentual fictício, cancelamento de ingestão ou reprocessamento.
- Alterar limites, API, ingestão, indexação, status ou frequência de polling por preferência visual.
- Acrescentar confirmação de exclusão: melhoria futura fora desta migração, sem bloquear sua conclusão.
- Expor erro bruto do backend, conteúdo de documentos ou novas ações não suportadas.

## Requisitos observáveis

- **DS-10-R01:** seleção por controle e arraste deve continuar aceitando um único PDF, TXT ou DOCX válido; formato/MIME incompatível, quantidade inválida e excesso de tamanho não devem chamar upload.
- **DS-10-R02:** o limite deve continuar vindo de `uploadLimits`; carregamento/falha/valor inválido devem bloquear seleção/envio conforme hoje. Recarregar limite não deve bloquear exclusão permitida, e polling não deve habilitar envio por conta própria.
- **DS-10-R03:** metadados opcionais `document_type`, `document_number`, `department`, `published_at` e `valid_until` devem permanecer disponíveis; somente valores preenchidos/compactados devem ser enviados, preservando cancelamento da seleção.
- **DS-10-R04:** envio em curso deve bloquear repetição; sucesso deve incorporar o documento retornado, inclusive `pending`, sem aguardar listagem; falha deve gerar mensagem segura sem sucesso fictício.
- **DS-10-R05:** a lista deve manter os status `pending`, `processing`, `ready` e `error`, seus rótulos, `chunk_count`, informações já exibidas e ações por status; erros internos não devem aparecer no lugar da mensagem segura.
- **DS-10-R06:** polling deve continuar a cada dois segundos enquanto houver documento ativo, com no máximo uma leitura pendente, pausa durante mutações, retomada conforme os estados atuais e parada quando não houver ativos.
- **DS-10-R07:** desmontagem e repetição de efeitos em StrictMode devem limpar timers e cancelar/inutilizar leituras de documentos e limites; retornos antigos não podem publicar estado na montagem vigente.
- **DS-10-R08:** listagens iniciadas antes de upload/exclusão não devem reinserir snapshots antigos; abortos, versões de listagem, contagem de mutações e versões de feedback devem continuar protegendo lista e mensagens, mesmo se o transporte ignorar cancelamento.
- **DS-10-R09:** exclusão deve permanecer direta e bloqueada em `pending`/`processing` e durante exclusão vigente; remover o item somente após DELETE bem-sucedido, conservando-o e mostrando erro seguro em falha.
- **DS-10-R10:** carregamento inicial, atualização, vazio, falha de limite/listagem/polling/upload/exclusão devem continuar distinguíveis pelas mensagens atuais e controles disponíveis.
- **DS-10-R11:** nomes longos, metadados, formulários e ações devem ser utilizáveis em celular/desktop e ambos os temas; seleção por teclado deve continuar alternativa ao arraste e status devem permanecer acessíveis.

## Arquivos afetados candidatos

- [DocumentTab](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(admin)/base-de-conhecimento/components/document-tab.tsx>).
- [Testes de documentos](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(admin)/base-de-conhecimento/components/document-tab.test.tsx>).
- [Composição da base](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(admin)/base-de-conhecimento/page.tsx>), somente integração visual necessária.
- [Contratos DocumentStatus/KnowledgeDocument e documentApi](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/lib/api.ts>), referência sem alteração funcional prevista.

## Critérios de aceitação

- **DS-10-AC01 — R01/R02:** Dados limite carregando, inválido ou com falha e arquivos válidos/inválidos, quando seleção/envio forem tentados, então somente um arquivo permitido dentro do limite carregado deve poder ser enviado.
- **DS-10-AC02 — R03/R04:** Dado arquivo com metadados opcionais, quando enviado, então valores compactados devem preservar o contrato; repetição deve ser bloqueada e o retorno real deve aparecer imediatamente após sucesso.
- **DS-10-AC03 — R05/R10:** Dadas fixtures dos quatro status e falhas, quando a lista renderizar, então rótulos, chunks, ações e mensagens seguras devem refletir o estado real sem detalhes internos.
- **DS-10-AC04 — R06:** Dado documento ativo, quando o tempo avançar, então deve haver polling de dois segundos sem leituras sobrepostas; mutação deve pausar leituras e status final deve encerrar polling.
- **DS-10-AC05 — R07:** Dada desmontagem ou repetição de efeitos em StrictMode, quando timer ou resposta antiga terminar, então consultas devem ser canceladas/inutilizadas e não alterar a montagem atual.
- **DS-10-AC06 — R08:** Dada listagem lenta iniciada antes de upload/exclusão, quando resolver depois da mutação mesmo ignorando abort, então não deve sobrescrever lista atual nem apagar feedback mais recente.
- **DS-10-AC07 — R09/R02:** Dados itens ativos e prontos/com erro, quando exclusão for tentada, então ativos devem permanecer bloqueados; DELETE com falha deve preservar o item e sucesso deve removê-lo, mesmo quando limite de upload falhar.
- **DS-10-AC08 — R11:** Dados nomes longos e 1440, 1024, 768 e 390 px nos dois temas, quando seleção, metadados e ações forem usados por teclado, então conteúdo e controles devem permanecer identificáveis sem overflow do documento.

## Plano de implementação

- [x] Confirmar aprovação/dependências e registrar baseline dos testes assíncronos existentes.
- [x] Mapear composição atual a componentes/tokens, mantendo efeitos e referências intactos.
- [x] Adaptar seleção, formulário, mensagens e lista sem mudar limites/status/ações.
- [x] Revisar nomes acessíveis, foco e alternativa de teclado ao arraste.
- [x] Executar a suíte de documentos, inclusive corridas, polling, desmontagem e StrictMode.
- [x] Inspecionar os estados visuais com fixtures e registrar evidências/limitações no STATUS.

## Verificação e evidências esperadas

- Executar `pnpm lint`, `pnpm typecheck` e `pnpm test:run "app/(admin)/base-de-conhecimento/components/document-tab.test.tsx"` no frontend.
- Preservar cobertura de arquivo único, formatos/MIME/tamanho, metadados, quatro badges/chunks, exclusão não otimista e mensagem segura.
- Preservar todos os cenários existentes de respostas tardias, limite independente, leituras pendentes, polling, desmontagem e StrictMode; não reduzir testes para facilitar layout.
- Usar arquivos sintéticos e mocks; não excluir documentos reais nem consumir processamento do usuário para validar aparência.
- Entregar imagens de seleção/metadados, status, falhas e lista vazia em desktop/celular e ambos os temas, com resultados associados aos critérios.

## Conclusão e aprovação

Implementação/verificação só termina com critérios evidenciados e sem perda dos contratos assíncronos; aparência deve ser apresentada para revisão separada.
Adição futura de confirmação não condiciona esta fase. Mudanças materiais de escopo/spec exigem aprovação antes da implementação dependente.
Não avançar, criar commit ou publicar automaticamente. Estado atual: **Implementada, verificada no escopo local disponível e aceita pelo usuário em 12/10/2026**.

Autorização explícita recebida na mensagem Fase: 10 de 12/10/2026. A dependência DS-09 foi confirmada antes de implementar: “Confirmo o aceite da DS-09 e prossiga com a DS-10”. Nenhuma revisão material da v1.0 necessária. Consulte [evidências DS-10](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/evidencias/DS-10.md>) para os oito critérios, registros reais e limites. Após apresentação da entrega e limitações, o usuário declarou “aprovado. faça commite das alterações”. Aceite registrado; commit local autorizado com a mensagem sugerida, identificação no histórico Git. Sem push ou avanço à DS-11.
