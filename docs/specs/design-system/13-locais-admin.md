# DS-13 — Gestão administrativa de locais

**Versão:** 1.0.

## Identificação e estado

- **Status:** Proposta / aguardando aprovação. Não aprovada nem implementada.
- **Origem:** fase 13 do roteiro anterior; etapa 9B do plano de refatoração.
- **Modelo sugerido:** GPT-6.1 Sol (`gpt-6.1-sol`), esforço Medium (`medium`).
- **Commit sugerido, após revisão e autorização:** `refactor(locations): padroniza gestao administrativa de locais`.
- **Governança:** [README](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/README.md>), [contrato comum](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/CONTRATO.md>) e [status](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/STATUS.md>).

## Problema e resultado esperado

A área de locais tem cards, busca, coordenadas e formulário próprios. Deve adotar o mesmo padrão visual do painel, deixando nome, categoria, bloco/piso, estado de visibilidade e ações fáceis de entender em qualquer largura. Ela continua sendo a gestão dos pontos do mapa esquemático, inclusive para instituições sem mapa geográfico.

O arquivo do UX Pilot não contém uma tela própria desta gestão. A referência é o Styleguide `1Y8TYWWcoY7N8NBOJS1n` e os padrões administrativos aprovados; qualquer composição complementar deve ser identificada como proposta.

## Dependências e pré-condições

- DS-00 aprovada e DS-01 implementada/revisada para tema, componentes e estados.
- DS-07 implementada/revisada para cabeçalho e container do painel.
- Conferir DS-06 para manter o significado dos dados no mapa público; isso não autoriza editar o mapa nesta fase.
- Coordenar com DS-14 a distinção entre locais esquemáticos e entidades geográficas, sem mesclar os dois cadastros.
- Conferir instruções e mudanças locais antes de implementar, preservando trabalho preexistente.

## Escopo

- Página `/locais`, pesquisa, cards/listagem, indicação de ativo/inativo, ações e estados.
- Formulário de criação/edição, posição X/Y, visibilidade, confirmação de exclusão e nova tentativa de carregar.
- Legibilidade, teclado, foco, responsividade e temas.

Fora do escopo: substituir o cadastro pelo editor de campi, converter X/Y para latitude/longitude, alterar banco ou APIs, novas regras de localização, geocodificação, importação em lote ou remoção da alternativa esquemática.

## Contratos atuais a preservar

- `CampusLocationInput` contém nome, descrição, categoria, piso, bloco, `x`, `y` e `active`; não recebe `tenant_id`.
- X/Y representam posição relativa no mapa esquemático. Campos numéricos atuais apresentam faixa 0–100, passo 0,1 e valor inicial 50/50. Não equivalem a latitude/longitude.
- Nome e categoria são obrigatórios; strings são aparadas; descrição, piso e bloco vazios tornam-se `null` no salvamento.
- A pesquisa considera nome, categoria, bloco e piso, em pt-BR sem diferença de caixa.
- Limites visuais atuais: nome 200, categoria/bloco 100, piso 50 e descrição 2000 caracteres; preservá-los sem inventar nova validação de negócio.
- `active` mantém o significado de exibir/ocultar do portal. Editar preserva todos os valores, inclusive coordenadas fracionárias.
- Falha de carregamento apresenta mensagem genérica e tentativa novamente; mensagens internas não devem ser expostas.

## Requisitos observáveis

| ID | Requisito |
| --- | --- |
| DS-13-R01 | Cabeçalho, busca, cards/listagem e formulário devem consumir os tokens e padrões aprovados em claro/escuro, com mesma hierarquia administrativa. |
| DS-13-R02 | Pesquisa deve manter os quatro campos atuais e conteúdo completo para editar; textos longos não podem ocultar permanentemente ações. |
| DS-13-R03 | Criação/edição devem manter todos os campos, limites e normalização atuais; o fechamento por sucesso ocorre após retorno da API, enquanto falha conserva o formulário. |
| DS-13-R04 | X/Y devem continuar identificados como posição do mapa esquemático, com os mesmos valores, faixa apresentada e passo; o layout não pode arredondar, recodificar ou substituir as coordenadas. |
| DS-13-R05 | A visibilidade deve ser comunicada por texto além de cor e conservar `active`; o switch deve ter nome acessível e explicação do efeito no portal. |
| DS-13-R06 | Exclusão deve identificar o local, pedir confirmação e permitir cancelar sem requisição; remoção da lista depende do sucesso. |
| DS-13-R07 | Carregamento, vazio, pesquisa sem resultado, erro de leitura e salvamento devem ser compreensíveis; a nova tentativa existente deve funcionar sem expor detalhes internos. |
| DS-13-R08 | Em 1440, 1024, 768 e 390 px e zoom de 200%, pesquisa, ações e todos os campos devem ser alcançáveis, com rolagem de diálogo sem cortes. |
| DS-13-R09 | Rótulos associados, nomes de ações por local, foco visível e retorno de foco dos diálogos devem permitir operar cadastro e exclusão pelo teclado. |
| DS-13-R10 | Endpoints, autorização e isolamento institucional devem permanecer; o cadastro deve continuar alimentando a alternativa pública esquemática sem exigir campus geográfico. |

## Arquivos afetados candidatos

- [Página de locais](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(admin)/locais/page.tsx>).
- [CampusLocationsManager](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(admin)/locais/campus-locations-manager.tsx>) e [testes](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(admin)/locais/campus-locations-manager.test.tsx>).
- [PageContainer](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/components/page-container.tsx>) e primitivas existentes, se houver necessidade de composição compatível.
- [Contratos e locationApi](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/lib/api.ts>) e [consumidor público](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(public)/components/public-portal.tsx>) são referências de preservação, fora da reestruturação desta fase.

## Critérios de aceitação

| ID / requisitos | Dado / Quando / Então |
| --- | --- |
| DS-13-AC01 · R01, R08 | **Dado** cada tema e largura de referência, **quando** abrir lista/formulário com conteúdo longo, **então** a composição segue o padrão aprovado e não corta campos ou ações. |
| DS-13-AC02 · R02, R07 | **Dado** fixtures com nomes, categorias, blocos e pisos distintos, **quando** pesquisar valores e termo inexistente, **então** os resultados mantêm a semântica atual e o vazio fica claro. |
| DS-13-AC03 · R03, R04 | **Dado** um local com X/Y fracionários e campos opcionais, **quando** editar apenas o nome e salvar, **então** as coordenadas e demais valores não alterados permanecem no payload. |
| DS-13-AC04 · R03 | **Dado** um novo local, **quando** salvar com obrigatório ausente e depois válido, **então** o primeiro envio é impedido e o segundo mantém normalização e limites existentes. |
| DS-13-AC05 · R05, R10 | **Dado** local ativo/inativo, **quando** abrir a edição e alternar visibilidade, **então** o estado é compreensível sem depender da cor e o payload preserva `active` e o contrato do portal. |
| DS-13-AC06 · R06 | **Dado** exclusão de um local de teste, **quando** cancelar e confirmar, **então** só confirmar chama a API e somente sucesso remove da lista. |
| DS-13-AC07 · R03, R07 | **Dado** falha simulada de leitura ou salvamento, **quando** ocorrer a operação, **então** há feedback seguro, nova tentativa de leitura funciona e falha de envio não descarta os dados. |
| DS-13-AC08 · R08, R09 | **Dado** navegação por teclado em celular e desktop, **quando** preencher campos e abrir/fechar diálogos, **então** os nomes são acessíveis e foco/rolagem permitem concluir as ações. |
| DS-13-AC09 · R04, R10 | **Dado** uma instituição sem mapa geográfico, **quando** cadastrar local em fixture, **então** não é exigido campus nem latitude/longitude e a chamada não inclui tenant fornecido pela interface. |

## Plano de implementação

- [ ] Confirmar aprovação e dependências, conferir contratos e dados de teste.
- [ ] Ajustar cabeçalho/container e busca ao padrão administrativo.
- [ ] Padronizar cards, badges, botões de ícone e estados, mantendo informações e pesquisa.
- [ ] Reorganizar formulário e visibilidade, preservando campos/valores e significado de X/Y.
- [ ] Conferir confirmação, cancelamento, falha, nova tentativa e payloads em mocks.
- [ ] Validar teclado, foco, textos longos, zoom, temas e larguras; adaptar testes pertinentes.
- [ ] Registrar verificações e pendências no STATUS e entregar para revisão.

## Verificações e evidências

- Executar `pnpm lint`, `pnpm typecheck` e `pnpm test:run "app/(admin)/locais/campus-locations-manager.test.tsx"` no frontend.
- Testes atuais cobrem listagem/pesquisa/cadastro sem tenant no payload, exclusão e falha de carregamento sem detalhes internos.
- Conferir edição, coordenadas fracionárias, ativo/inativo, cancelamento e falha de envio com mocks; registrar se a evidência é manual ou automatizada.
- Capturar lista e formulário em claro/escuro e larguras de referência, incluindo texto longo, vazio e erro com nova tentativa.
- Não alterar registros reais. Se uma mudança de importação/renderização justificar, executar também `pnpm build`.

## Conclusão e aprovações

Concluir tecnicamente após verificar requisitos e registrar limitações sem regressão conhecida. Manter implementação, verificação e aceite visual separados no STATUS; a revisão do usuário permanece pendente até manifestação explícita.

Executar somente DS-13 quando autorizada. Mudanças materiais de regra, escopo ou decisão visual exigem aprovação antes da implementação dependente. Não iniciar DS-14, criar commit ou fazer push automaticamente.
