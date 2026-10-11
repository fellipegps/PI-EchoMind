# DS-16 — Consolidação e revisão integrada

| Metadado | Valor |
| --- | --- |
| ID | DS-16 |
| Versão | 1.0 |
| Estado da especificação | Proposta — aguardando aprovação |
| Estado da execução | Não iniciada |
| Origem no plano | 11 |
| Modelo / esforço sugeridos | GPT-6 Astra / High |
| Commit sugerido | refactor(ui): consolida estilos e corrige inconsistencias visuais |

## Contrato e dependências

Aplicam-se [CONTRATO.md](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/CONTRATO.md>), [README.md](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/README.md>) e [STATUS.md](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/STATUS.md>).

Dependências: DS-00 a DS-15 com entregas obrigatórias implementadas, verificadas e aceitas. Exceções somente se explicitamente autorizadas e registradas; não equivalem à conclusão integral.

## Problema e resultado esperado

Migrações por partes podem deixar estilos sem consumidores, diferenças de tema e regressões entre áreas que não aparecem na verificação isolada.

Consistência visual e funcional verificada entre todas as áreas migradas, com remoção segura de resíduos e documentação do resultado final.

## Escopo e limites

Revisão transversal, correção de inconsistências da refatoração, limpeza comprovada e documentação/evidências. Novas funcionalidades e correção indiscriminada de problemas preexistentes ficam fora do escopo.

## Requisitos

- **DS-16-R01:** A revisão cobre todas as fases e verifica sua rastreabilidade entre requisitos, mudanças, evidências e aceite; uma etapa pendente permanece identificada e impede declarar conclusão integral.
- **DS-16-R02:** Marca, tokens, tipografia, raios, foco, componentes e estados são consistentes entre autenticação, portal, mapas e painel nos temas claro/escuro e larguras de referência.
- **DS-16-R03:** Cada remoção de CSS, token ou componente antigo tem ausência de consumidores demonstrada. Estilos necessários de terceiros, Markdown e coordenadas/dimensões dinâmicas permanecem quando justificados.
- **DS-16-R04:** Chat/streaming, eventos, mapas, autenticação, CRUD, documentos, triagem, métricas RAG e QR conservam seus contratos específicos após as migrações; verificações usam dados de teste.
- **DS-16-R05:** Lint, typecheck, suíte completa do frontend e build são executados e seus resultados reais registrados, distinguindo regressões introduzidas de limitações ou falhas preexistentes.
- **DS-16-R06:** A revisão registra teclado, zoom, foco, textos longos, ambos os temas e larguras 1440/1024/768/390 px, além de overflow em 320 px. Limitações de teclado virtual real permanecem explícitas.
- **DS-16-R07:** A documentação final lista exceções mantidas, pendências e critérios concluídos. O conjunto só é marcado como concluído quando não houver requisitos obrigatórios pendentes e o usuário aceitar o resultado.

## Commit desta fase

A mensagem sugerida só se aplica se houver limpeza ou correção de código. Se a revisão produzir apenas documentação, usar mensagem documental apropriada; se não houver mudanças, não criar commit vazio.

## Critérios de aceitação

- **DS-16-AC01** (DS-16-R01, DS-16-R07): Dado o andamento das fases, quando a conclusão do conjunto é avaliada, então todas as entregas/aceites obrigatórios e suas evidências estão identificados; pendências impedem conclusão integral.
- **DS-16-AC02** (DS-16-R02, DS-16-R06): Dadas as áreas migradas, quando revisadas nos temas/larguras e com teclado/zoom, então os padrões visuais são consistentes e não há obstrução essencial. Uma inconsistência obrigatória ou obstrução não corrigida mantém este critério pendente ou reprovado; registrá-la não equivale a validá-lo.
- **DS-16-AC03** (DS-16-R03): Dado um seletor ou componente candidato a remoção, quando seu uso é pesquisado, então só é removido se não houver consumidores; as exceções necessárias estão documentadas.
- **DS-16-AC04** (DS-16-R04, DS-16-R05): Dada a suíte e os fluxos de teste, quando a verificação integrada é executada, então os resultados reais e a preservação dos contratos estão ligados às evidências, sem apresentar bloqueios como sucesso.
- **DS-16-AC05** (DS-16-R07): Dado o relatório final, quando entregue ao usuário, então implementação, verificação, aceite e commit continuam separados, sem publicação ou avanço automático.

## Arquivos candidatos

- [Scripts e dependências](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/package.json>)
- [Tema global](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/globals.css>)
- [Índice](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/README.md>)
- [Andamento](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/STATUS.md>)

A lista orienta a implementação; não exige alterar todos os arquivos e não limita extrações necessárias dentro do escopo.

## Tarefas de implementação

- [ ] Revisar STATUS.md e evidências DS-00–DS-15, levantando pendências antes de concluir o conjunto.
- [ ] Pesquisar consumidores e remover apenas resíduos comprovados; documentar exceções de CSS/terceiros.
- [ ] Corrigir inconsistências atribuíveis à migração sem ampliar o escopo funcional.
- [ ] Executar verificação integrada e revisão visual nas larguras e temas exigidos.
- [ ] Registrar evidências DS-16, atualizar o índice/andamento e entregar para aceite final.

## Verificações e evidências

pnpm lint, pnpm typecheck, pnpm test:run e pnpm build no frontend; revisão visual e de interações dos fluxos de todas as specs. Não executar CRUD destrutivo em dados reais. Se o ambiente bloquear um critério obrigatório, registrá-lo como pendente; fase/conjunto não ficam integralmente validados.

Criar o registro de evidências DS-16 apenas durante a execução, conforme o contrato comum. Mapear cada critério a um resultado observado ou pendência; não presumir verificação pela existência da spec.

## Condição de conclusão e revisão

Requisitos obrigatórios atendidos, critérios verificáveis com evidências reais, pendências registradas e entrega apresentada para aceite. Aprovação da spec, implementação, validação e aceite do resultado são estados separados. Commit e push não são automáticos.

## Histórico

- 11/10/2026 — versão 1.0: proposta documental inicial; execução não iniciada; nenhuma aprovação atribuída ao usuário.

