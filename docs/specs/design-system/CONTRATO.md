# Contrato comum — SDD do design system EchoMind

ID: DS-CONTRATO · Versão: 1.0 · Estado: proposta incorporada à aprovação de cada fase.

Aplica-se às especificações DS-00–DS-16. A versão de uma fase e este contrato devem ser conhecidos antes da autorização. Este contrato não atribui aprovação ao usuário.

## Fonte de verdade e versionamento

- A spec aprovada é a fonte de verdade do resultado esperado. O plano de origem fornece contexto; notas históricas não substituem a observação do código nem os contratos vigentes.
- Requisitos têm IDs DS-NN-Rxx; critérios têm IDs DS-NN-ACxx e indicam os requisitos cobertos. Tarefas são uma decomposição editável do trabalho, não substituem os critérios.
- Uma mudança material de resultado, comportamento, escopo ou critério obrigatório cria nova versão da spec, com motivo e impacto. A parte dependente espera aprovação dessa mudança.
- Detalhes rotineiros de implementação, organização de arquivos e correções dentro do resultado aprovado podem ser resolvidos pelo executor e registrados nas evidências. Não requerem nova autorização.
- A autorização explícita do usuário para uma fase aprova somente a versão identificada dessa fase. Não aprova automaticamente fases anteriores, o conjunto inteiro nem mudanças futuras.

## Requisitos compartilhados

| ID | Contrato observável |
| --- | --- |
| DS-G01 | A entrega altera somente o escopo autorizado e preserva mudanças locais preexistentes; arquivos candidatos não são uma autorização para mudanças alheias ao resultado. |
| DS-G02 | Rotas, contratos de API, dados, autorização e isolamento institucional mantêm sua semântica atual. Backend, banco e regras de sessão ficam fora da refatoração visual. |
| DS-G03 | Next.js/React, Tailwind 4, shadcn/Radix, Geist e Lucide continuam sendo a base. Não há nova biblioteca apenas para reproduzir uma aparência. |
| DS-G04 | Componentes migrados consomem os tokens aprovados de DS-00/DS-01 nos temas claro e escuro. Estilos locais e de bibliotecas necessários continuam permitidos. |
| DS-G05 | A interface mantém nomes acessíveis, foco visível, navegação por teclado, mensagens de status e suporte a redução de movimento quando aplicável. Dados e textos longos não impedem ações essenciais. |
| DS-G06 | Previews e metadados do UX Pilot são consultados em modo de leitura. A refatoração não gera, modifica, apaga ou solicita avaliações pagas de designs. |
| DS-G07 | Conteúdo e ações dos mockups só aparecem quando apoiados em funções e dados reais do sistema. Não há números ilustrativos, botões sem efeito ou links sem destino. |
| DS-G08 | CSS, variáveis ou componentes antigos só são removidos depois que não houver consumidores. Estilos de Leaflet, coordenadas e dimensões calculadas não precisam virar classes estáticas. |
| DS-G09 | Streaming, Markdown seguro, validação de URLs, fluxos de documentos, mapas, triagem e QR mantêm os contratos específicos definidos em cada fase. |
| DS-G10 | Verificações usam mocks, fixtures e dados de teste adequados. Registros, credenciais ou localização real do usuário não são alterados ou transmitidos apenas para demonstrar aparência. |
| DS-G11 | Cada critério obrigatório tem evidência ou pendência explícita. Limitação de ambiente, falha preexistente e regressão introduzida são registradas separadamente. |
| DS-G12 | Implementar, validar, aceitar, fazer commit e publicar são ações distintas. Uma fase não avança sozinha, e commit/push não acontecem automaticamente. |

Estas regras preservam comportamentos existentes. Por exemplo, “preservar confirmações de exclusão” significa manter as que existem; não acrescentar confirmação aos fluxos que hoje excluem diretamente. As specs de FAQs e documentos registram essa distinção.

## Aprovação e dependências

- Aprovação da spec: registrar fase, versão, data e mensagem de autorização realmente recebida. Não preencher com inferência baseada em silêncio ou na criação destes documentos.
- DS-00 define a direção visual. Uma aprovação para implementar DS-01 não dispensa o aceite obrigatório do resultado documental de DS-00.
- Dependências de uma fase devem ter seus resultados aceitos quando a spec assim exigir. Se faltar evidência de aceite, apresente a dependência concreta e continue somente verificações independentes.
- Implementação termina como “aguardando revisão”, não como “aceita”. Aceite de resultado exige manifestação explícita do usuário.
- As exceções de dependência ou escopo autorizadas pelo usuário devem ser registradas com motivo e limite; não são inferidas automaticamente.

## Verificação compartilhada

Diretório do frontend: C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front.

- Entregas de código: pnpm lint e pnpm typecheck, mais os testes existentes relacionados aos fluxos alterados.
- Entregas exclusivamente documentais: verificar consistência, links, requisitos e decisões; não é necessário executar testes da aplicação.
- Mudança de tokens/primitivas: verificar visualmente os consumidores ainda não migrados.
- Conferir pelo menos desktop e celular nos dois temas por fase visual. Conforme o escopo, usar 1440, 1024, 768 e 390 px; na DS-16 verificar também overflow em 320 px.
- Tamanhos de teste não definem breakpoints. As propostas de layout estão em DS-00.
- Viewport reduzido não valida o teclado virtual real. Quando não for possível validar um dispositivo real, manter esse item como limitação.
- Não adicionar testes que apenas espelhem classes CSS. Atualizar testes de comportamento quando a representação acessível mudar legitimamente.
- Build quando houver mudança relevante em importações, renderização ou configuração; na DS-16, pnpm test:run e pnpm build completos.
- Falhas preexistentes não podem ser apagadas nem declaradas aprovadas. Registrar seu impacto nos critérios e a evidência de que antecedem a mudança.

## Evidências por fase

Durante a execução, criar o registro de evidências em C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/evidencias/DS-NN.md. A pasta e os arquivos serão criados quando houver trabalho real; não há evidências fabricadas nesta preparação.

Formato mínimo do registro:

| Campo | Conteúdo esperado |
| --- | --- |
| Spec | ID, versão aprovada, autorização recebida e dependências verificadas. |
| Alterações | Arquivos e ligação entre a mudança e seus requisitos. |
| Critérios | ID do critério, resultado: passou/pendente/falhou/não aplicável justificado; teste, observação ou imagem que sustenta o resultado. |
| Testes | Comando/escopo, data, resultado, falhas e limitações. Não expor segredos ou conteúdo sensível. |
| Imagens | Evidências das telas nos temas/larguras relevantes e contexto suficiente para revisão. |
| Desvios | Mudanças propostas na spec, problemas preexistentes e requisitos fora do escopo. |
| Entrega | Implementação concluída ou parcial, validação concluída ou pendente, aguardando revisão ou aceita. |
| Git | Mensagem sugerida e, somente se autorizado/criado, hash do commit. |

Não usar uma imagem do UX Pilot como prova de que a aplicação implementada corresponde ao design. Uma imagem de referência e uma imagem do resultado cumprem papéis diferentes.

## Andamento e conclusão

STATUS.md registra estados separados:

- Especificação: proposta → aprovada; revisada quando houver nova versão pendente.
- Execução: não iniciada → em andamento → implementada; bloqueada/parcial quando aplicável.
- Verificação: não iniciada → parcial → validada; falhou/bloqueada conforme as evidências.
- Aceite: aguardando revisão → aceito pelo usuário.
- Commit: não criado, opcional; nunca prova de aceite ou de validação.

Para concluir uma fase, cumprir os requisitos obrigatórios, justificar cada critério não aplicável, fornecer evidências e registrar a revisão necessária. Na DS-16, o conjunto só é concluído sem requisitos obrigatórios pendentes.

## Commits

Mensagens sugeridas estão nas specs. Criar commit apenas após instrução explícita, conferindo que o conjunto preparado inclui somente alterações da entrega e documentação correspondente. Preservar alterações alheias. Não criar commit vazio nem fazer push automaticamente.

A documentação atual pode receber, se autorizado, um commit próprio: docs(design): organiza especificacoes SDD da refatoracao visual.

