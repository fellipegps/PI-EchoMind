# EchoMind — análise visual e plano de refatoração

Data: 11/10/2026. Status: **proposta para aprovação; implementação não iniciada**.

## 1. Recomendação

Planejar o conjunto agora e implementar em pequenas entregas, orientadas por especificações SDD versionadas. A base visual deve ser comum a todas as telas; a migração das telas deve acontecer aos poucos. Isso permite comparar cada resultado, corrigir a direção cedo e preservar os fluxos existentes.

Recomendo começar pelos tokens e componentes compartilhados, validar sua aplicação no login e depois migrar portal público, mapas e painel administrativo. Evitar uma reescrita completa em uma única entrega: mudanças nos tokens afetam diversas telas, enquanto chat, mapas e documentos possuem comportamentos que precisam de verificações próprias.

O envio deste plano e a criação das especificações não autorizam alterações na aplicação. A execução passa a ser orientada pelo [índice SDD](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/README.md>), seu contrato comum e a especificação de cada fase. Requisitos e critérios aprovados delimitam a entrega autorizada; implementação, verificação e aceite são registrados separadamente.

## 2. Referências examinadas

Arquivo do UX Pilot: [Untitled File](https://uxpilot.ai/a/ui-design?page=ThHPmFvVAyXGKTItA3AZ), página ThHPmFvVAyXGKTItA3AZ.

Os seis previews foram recuperados pelo MCP e inspecionados visualmente. Também foram lidos os arquivos de tema, layouts, componentes, telas, contratos de dados e testes do frontend atual. Esta é uma análise de imagens e código; não foi realizada uma comparação com a aplicação atual em execução. O conector fornece metadados e previews, sem HTML ou medidas editáveis desses designs.

| Referência | ID no UX Pilot | Evidência visual |
| --- | --- | --- |
| EchoMind - Styleguide | 1Y8TYWWcoY7N8NBOJS1n | Imagem 1440 × 2014; cores semânticas, tipografia, botões, formulários, cards, navegação, chat e métricas. |
| EchoMind - Chat Portal | 3Qj2y1kf1JY6tBztuJCd | Imagem 750 × 1680; composição para celular, conversa, sugestões e navegação inferior. |
| EchoMind - Chat Portal | ktsYqLA8UvfGZe6riGsa | Imagem 1440 × 1024; composição desktop com menu lateral, conversa e coluna de FAQs/eventos. |
| EchoMind - Events and Locations | k5WjrM3paBG7rWH7cnmR | Imagem 1440 × 1324; busca, cards com capa, data/local e categorias de lugares. |
| EchoMind - Admin Dashboard Primal | hldl1brk4q4O5f5XT8Nm | Imagem 1440 × 1187; sidebar, métricas, gráficos, pendências e controles do agente. |
| EchoMind - Login | zWCKHDtCGxmxEmkSl0pe | Imagem 1440 × 1024; marca, formulário centralizado e links auxiliares. |

As duas telas de Chat Portal são referências complementares de celular e desktop. Os tamanhos acima são dimensões das imagens exportadas, não breakpoints CSS aprovados.

## 3. Análise do design proposto

### Identidade e fundamentos

- A direção visual é coerente: azul de ação **#0B57D0**, fundos claros, cards brancos, bordas discretas, pouco relevo e hierarquia baseada em tamanho, peso e espaço.
- O styleguide indica Slate 950 para texto, Slate 100 para superfície suave, Emerald 500 para sucesso, Amber 500 para aviso e Red 600 para erro. Essas cores devem virar tokens semânticos, com pares de fundo/texto verificados por contraste.
- A escala tipográfica explícita apresenta título principal de 36 px, título secundário de 24 px, corpo de 16 px e legenda/rótulo de 14 px. O tamanho dos títulos precisa se adaptar ao celular; 36 px não deve ser obrigatório em toda página.
- Os botões propostos correspondem às variantes já existentes: primário, secundário, contornado, destrutivo e ícone. Não há motivo para substituir a biblioteca atual.
- Há símbolos de marca diferentes entre as telas: onda/quadro, raio e brilho do assistente. Recomendo uma marca única do EchoMind e um avatar próprio para o assistente, com papéis distintos.
- A fonte exata e as medidas completas de espaçamento, raios e sombras não estão disponíveis nos metadados. Recomendo manter Geist, já carregada pelo projeto, e formalizar uma escala curta de espaçamento e raios na primeira entrega. São decisões propostas, não valores extraídos automaticamente da imagem.

### Portal público e chat

O desktop organiza bem os três contextos: navegação, conversa e conteúdo auxiliar. No celular, a conversa ganha prioridade e a navegação desce para o rodapé. Recomendo adotar essa relação entre as duas composições, mantendo as três áreas já existentes: **Chat, Eventos e Locais**.

No desktop largo, FAQs e próximos eventos podem ocupar uma coluna auxiliar usando os dados públicos atuais. Em larguras intermediárias, essa coluna deve recolher; no celular, FAQs podem aparecer como sugestões e eventos continuam acessíveis pela navegação. O campo de mensagem precisa permanecer acessível com o teclado virtual aberto e não se sobrepor à navegação inferior.

O design contém perfil identificado, documentos públicos, horários, notas, atalhos acadêmicos, anexos, microfone e atendimento humano. Esses elementos dependem de capacidades que não estão implementadas nesse portal. A migração visual deve aproveitar o layout e os componentes, sem criar botões sem ação nem apresentar dados fictícios. A resposta atual do chat é texto/Markdown; cards estruturados dentro da resposta exigiriam uma decisão funcional separada.

### Eventos e locais

Os cards com imagem, data destacada, título e local são compatíveis com os dados existentes. A implementação deve acomodar também período de vários dias, curso, descrição, imagem ausente/quebrada e link relacionado opcional.

Recomendo aplicar o conteúdo visual da tela de eventos dentro da navegação pública existente. Adotar um cabeçalho completamente diferente apenas nessa aba fragmentaria o portal. Busca e filtros devem ser vinculados aos dados disponíveis; rótulos de destaque, ordenação especial e categorias não devem ser inventados para preencher o layout.

A referência mostra categorias de locais, mas não especifica a interface completa do mapa nem suas interações. A área de mapas precisa de uma composição complementar para busca, campus, origem, destino, acessibilidade, precisão do GPS e resumo da rota, construída sobre a funcionalidade atual.

### Administrativo

O dashboard oferece uma boa referência de densidade: métricas no topo, gráficos no meio e informações operacionais abaixo. A sidebar agrupada e os estados ativos em azul ajudam a orientar a navegação.

Os números e indicadores do mockup não correspondem diretamente ao contrato atual. Hoje existem total de perguntas, não respondidas, tempo médio, satisfação, interações diárias, FAQs mais acessadas e métricas operacionais do RAG. Recomendo manter seus significados e aproveitar a composição visual. Um gráfico de FAQs não deve ser renomeado para categorias; taxas, comparativos e controles como reiniciar agente precisam de suporte real antes de aparecerem.

Base de conhecimento, documentos, triagem, configurações, editor de campi e formulários de eventos/locais não têm telas próprias nesse arquivo do UX Pilot. Elas deverão herdar os padrões aprovados do sistema. O mesmo vale para versões móveis do painel, eventos e autenticação.

### Autenticação

O login proposto é um bom piloto: escopo pequeno, identidade clara e componentes reutilizáveis. Sua composição deve ser estendida a cadastro, recuperação e redefinição de senha.

O login atual oferece criação de conta; o mockup sugere solicitar acesso à TI. Recomendo preservar os fluxos atuais e adaptar a identidade. A opção “manter conectado por 30 dias” não deve ser adicionada como detalhe visual, pois implica uma política de sessão. Links de suporte, termos e privacidade precisam de destinos reais.

### Lacunas para resolver

1. Tema escuro: não há referência visual entre os seis designs, embora o projeto já tenha suporte a temas.
2. Estados: hover, foco, pressionado, desabilitado, carregamento, erro, vazio e sucesso precisam de uma especificação comum.
3. Responsividade: há uma referência de chat para celular; as demais telas precisam de regras responsivas próprias.
4. Acessibilidade: verificar contraste, navegação por teclado, nomes de botões, foco visível, mensagens de status e tamanho confortável dos alvos de toque. A imagem sozinha não comprova esses pontos.
5. Marca: aprovar símbolo e tratamento do avatar antes de reproduzir ícones diferentes em cada área.
6. Conteúdo: usar instituição, eventos, FAQs, locais e métricas reais; textos, pessoas e datas ilustrativas não são conteúdo de produção.

## 4. Diagnóstico do projeto atual

| Área | Situação verificada | Consequência para a migração |
| --- | --- | --- |
| Base visual | Tailwind 4, shadcn/Radix, Lucide, Geist e next-themes já instalados. | Evoluir a base atual e reutilizar as primitivas. |
| Tema global | Tokens semânticos claros/escuros; primário atual do painel é neutro escuro. | Alinhar ação, foco, sidebar e gráficos à identidade azul. |
| Portal público | CSS Modules com paleta local; 1078 linhas no portal e 254 no navegador de campus. | Migrar composição e componentes para Tailwind, removendo duplicação de tokens aos poucos. |
| CSS de mapa | Leaflet importado no layout raiz; há seletores locais para a classe do mapa. | Tratar a integração de terceiros como exceção controlada e verificar sua área de carregamento. |
| Componentes | Button, Input, Label, Card, Badge, Tabs, Dialog, Sheet, Skeleton, Table e outros já existem. | Evitar criar uma segunda coleção de componentes básicos. |
| Layout administrativo | PageContainer convive com wrappers diferentes de largura e padding. | Definir variantes explícitas de largura e um cabeçalho comum de página. |
| Autenticação | Quatro páginas repetem estrutura de card e fundo. | Criar uma composição compartilhada de autenticação. |
| Dashboard | Gráficos usam azul literal #01a6fd; existem métricas RAG adicionais. | Usar tokens de gráfico e preservar todos os dados e estados existentes. |
| Tema das notificações | Toaster está fora do ThemeProvider. | Rever a integração para acompanhar o tema ao consolidar a base. |

**Correção do diagnóstico inicial:** a maior parte do CSS específico da página pública está isolada em CSS Modules, não em seletores globais. O problema principal é a existência de um padrão visual paralelo ao Tailwind/shadcn, com tokens próprios. CSS global continua apropriado para tokens, base e estilos necessários de bibliotecas; a meta não é eliminar todo arquivo CSS.

## 5. Arquitetura visual proposta

- Uma fonte de tokens semânticos no tema: ação/primário, superfície, texto, borda, foco, sucesso, aviso, erro, sidebar e gráficos; todos com comportamento claro/escuro.
- Manter as APIs das primitivas shadcn. Adicionar variantes somente quando houver uma necessidade comum, evitando ajustes copiados em cada tela.
- Composições compartilhadas para marca, cabeçalho de página, estados de carregamento/erro/vazio e estrutura de autenticação. Componentes especializados para mensagem, campo de envio, FAQ, card de evento e controles do mapa.
- Layouts próprios para portal, painel e autenticação, consumindo a mesma base visual. Compartilhar identidade e componentes não exige usar a mesma navegação em contextos diferentes.
- Tailwind para layout, tipografia, espaçamento, estados e responsividade. Estilos específicos restantes devem ter escopo local e justificativa, como integração do Leaflet e renderização de conteúdo Markdown.
- Manter coordenadas e dimensões dinâmicas onde exigidas pelos mapas. Evitar converter dados calculados em classes artificiais.
- Não importar HTML gerado pelo UX Pilot como substituto da aplicação: reconstruir os padrões sobre os componentes e dados do projeto.

As primeiras decisões propostas para aprovação são: azul #0B57D0 como ação principal, manutenção de Geist, preservação do suporte a tema escuro, três entradas no portal público e aproveitamento das referências desktop/mobile do chat. A escolha definitiva da marca e a proposta visual do tema escuro serão apresentadas na primeira entrega.

## 6. Sequência de implementação

Cada entrega deve terminar com resumo do escopo, imagens do resultado, verificações relevantes e pendências. A entrega seguinte começa quando estiver abrangida pela autorização do usuário. Os nomes de componentes abaixo descrevem responsabilidades; não obrigam a criação de arquivos extras sem necessidade.

| Etapa original | Escopo | Resultado e critério de conclusão |
| --- | --- | --- |
| 1. Fundamentos | Tokens claros/escuros, marca, tipografia, raios, foco, primitivas e notificações. | Uma amostra visual revisável de botões, campos, cards e estados em ambos os temas; verificar o efeito dos tokens nas telas que ainda não migraram. |
| 2. Autenticação | Login, cadastro, recuperação e redefinição. | Composição comum, aparência alinhada ao UX Pilot e fluxos atuais preservados, inclusive erros e carregamento. |
| 3. Portal e chat | Navegação, estrutura desktop/mobile, mensagens, campo de envio e FAQs; coluna auxiliar quando couber. | Portal público em Tailwind, com streaming, Markdown, slug institucional e comportamento responsivo preservados. |
| 4. Eventos públicos | Cards, capa, data/período, metadados e estados. | Visual próximo à referência com os dados atuais; imagem quebrada/ausente, lista vazia e falha tratados. |
| 5. Locais e mapas públicos | Busca, seletor de campus, origem/destino, GPS, rota acessível e mapa esquemático alternativo. | Controles alinhados ao design system, mantendo cálculo de rota, acompanhamento de localização e alternativa sem GPS. |
| 6. Estrutura do painel | Sidebar, grupos, cabeçalho e PageContainer. | Navegação e conteúdo consistentes em desktop/celular; rotas e proteção de acesso atuais preservadas. |
| 7. Dashboard | Cards, gráficos e seção RAG. | Hierarquia da referência, usando as métricas atuais, cores semânticas e estados de carregamento/vazio/erro. |
| 8. Conhecimento e triagem | FAQs, documentos, upload e não respondidas. | Formulários, tabelas, filtros, diálogos e estados padronizados, sem alterar upload, processamento ou triagem. Subdividida nas specs de FAQs, documentos e triagem. |
| 9. Gestão de eventos e mapas | Eventos, locais e editor de campi no painel. | Mesmo padrão de formulários, ações e confirmações, preservando cadastro e edição. Separar o editor de campi se a mudança ficar extensa. |
| 10. Agente e configurações | Chat de teste, configurações da instituição e link/QR do portal. | Aparência consistente e todas as ações atuais funcionando. |
| 11. Consolidação | Remover estilos mortos, revisar temas, responsividade e regressões entre áreas. | Retirar CSS antigo somente após a migração dos consumidores e concluir a verificação do conjunto. |

As etapas originais 3, 8 e 9 foram subdivididas no [conjunto SDD](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/README.md>). A sequência detalhada é DS-00–DS-16; esta tabela mantém o agrupamento original para rastreabilidade. A unidade de trabalho é uma experiência revisável, não um número fixo de arquivos.

## 7. Verificação e preservação de comportamento

Durante a implementação:

- Executar lint e checagem de tipos em cada entrega; usar os testes existentes relacionados ao fluxo alterado. A mudança compartilhada de tokens/primitivas precisa de uma verificação visual mais ampla.
- Validar em desktop, largura intermediária e celular; propostas de larguras de referência: 1440, 1024, 768 e 390 px, com uma checagem adicional de overflow em 320 px. São tamanhos de teste, não breakpoints obrigatórios.
- Verificar ambos os temas, teclado, zoom, textos longos, conteúdo vazio, erro e carregamento. Testar o campo do chat com teclado virtual em dispositivo móvel quando disponível; viewport reduzido não substitui essa validação.
- Preservar no portal: slug institucional, acúmulo de tokens, Markdown seguro, estados de envio, dados reais de eventos, períodos de vários dias e validação de links/imagens.
- Preservar nos mapas: origem manual, localização somente após interação, precisão e cancelamento do acompanhamento, rotas acessíveis e alternativa esquemática.
- Preservar no painel: autenticação, CRUD, confirmações de exclusão nos fluxos que já as possuem, exclusão direta nos demais, upload e limites de documentos, acompanhamento de processamento, triagem, métricas RAG e geração de QR.
- Adaptar seletores de testes quando o elemento acessível mudar de forma legítima; manter a exigência de comportamento. Os testes atuais protegem, por exemplo, as três entradas do portal e a ausência de valores inventados nas métricas RAG.
- Executar build de produção e a suíte completa do frontend na consolidação; antecipar o build se uma etapa alterar importações, renderização ou configuração relevante. Registrar limitações de ambiente sem apresentá-las como verificações aprovadas.

Não é necessário adicionar testes que apenas confirmem classes Tailwind. Novos testes devem proteger interações ou comportamentos relevantes que surgirem da refatoração.

O retorno para a versão anterior deve ser possível por entrega, mantendo revisões pequenas e sem misturar alterações de API/backend. Não remover os estilos antigos antes que todos os seus consumidores tenham sido migrados. A troca de tokens terá efeitos também nas telas ainda não migradas, e esses efeitos devem ser mostrados na revisão da etapa 1.

## 8. Execução orientada por especificações (SDD)

O antigo roteiro de prompts foi substituído por arquivos .md de especificação em [docs/specs/design-system](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/README.md>).

- [README.md](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/README.md>): ordem, dependências gerais e prompt único reutilizável.
- [CONTRATO.md](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/CONTRATO.md>): regras compartilhadas, versionamento, aprovações e evidências.
- [STATUS.md](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/STATUS.md>): acompanhamento separado de spec, execução, verificação e aceite.
- DS-00: proposta de direção visual e revisão documental antes de implementar.
- DS-01–DS-16: especificações de cada alteração e da revisão integrada.

Cada spec contém problema, resultado esperado, escopo, requisitos identificados, critérios de aceitação rastreáveis, tarefas, arquivos candidatos, verificações e commit sugerido. A implementação segue os requisitos aprovados; os prompts servem somente para selecionar e autorizar a fase.

As specs são propostas e nenhuma implementação foi iniciada. O usuário deve aprovar a fase antes de sua aplicação. Mudanças materiais na spec exigem aprovação antes da implementação dependente, enquanto decisões rotineiras dentro do contrato podem ser resolvidas pelo executor.

Ao conferir os componentes atuais, foram corrigidas duas suposições do roteiro: FAQs e documentos excluem diretamente, e o dashboard principal mantém um fallback diferente da seção RAG. As specs respectivas descrevem o comportamento real e deixam mudanças funcionais adicionais fora do escopo.

Em caso de divergência, prevalece a versão mais recente da spec aprovada; este plano continua como contexto e diagnóstico de origem.

## 9. Arquivos principais de referência

- [Tema global](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/globals.css>) e [layout raiz](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/layout.tsx>).
- [Primitiva Button](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/components/ui/button.tsx>), [PageContainer](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/components/page-container.tsx>) e [sidebar](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/components/app-sidebar.tsx>).
- [Portal público](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(public)/components/public-portal.tsx>) e [CSS do portal](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(public)/components/public-portal.module.css>).
- [Navegador de campus](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(public)/components/public-campus-navigator.tsx>) e [CSS do navegador](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(public)/components/public-campus-navigator.module.css>).
- [Login](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(auth)/login/page.tsx>), [layout administrativo](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(admin)/layout.tsx>), [dashboard](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(admin)/dashboard/page.tsx>) e [métricas RAG](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(admin)/dashboard/rag-metrics-section.tsx>).
- [Contratos e cliente de API](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/lib/api.ts>) e [scripts do frontend](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/package.json>).

## 10. Situação desta entrega

Concluídos: leitura dos seis previews do UX Pilot, levantamento do frontend e de seus testes, análise de compatibilidade, identificação de lacunas e elaboração deste plano e sua conversão em especificações SDD por fase.

Alterações documentais: plano atualizado, conjunto SDD criado e roteiro antigo de prompts removido. Código, dependências, banco de dados e designs do UX Pilot não foram modificados. Não foram executados testes da aplicação nesta etapa de planejamento. O próximo passo depende da aprovação de uma especificação e de suas dependências.
