# DS-02 — Autenticação

**Versão:** 1.0.

## Identificação e controle

- Status: **Proposta — aguardando aprovação; não implementada**.
- Fase original: 02 do roteiro, etapa 2 do plano.
- Modelo recomendado: **GPT-6.1 Sol**, esforço **Medium** (`medium`).
- Commit sugerido após revisão e autorização: `refactor(auth): aplica design system as telas de autenticacao`.
- Dependências: DS-00 com identidade, temas e composição responsiva aprovados; DS-01 implementada e revisada com primitivas e notificações disponíveis.
- A aprovação deste documento não foi registrada. A autorização futura abrange somente esta fase.

O fluxo de execução está no [README](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/README.md>), as regras comuns no [CONTRATO](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/CONTRATO.md>) e as evidências/aprovações no [STATUS](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/STATUS.md>).

## Problema e resultado esperado

As quatro páginas de autenticação repetem fundo, card, ícone e espaçamentos. O layout do grupo atualmente devolve apenas os filhos. Essa repetição dificulta manter uma identidade consistente e diverge da referência EchoMind - Login.

O resultado esperado é uma composição comum de autenticação, com marca e componentes aprovados, mantendo os quatro fluxos existentes. O usuário continua reconhecendo cada formulário, suas validações, ações, mensagens e destinos.

## Referências e situação atual

- UX Pilot: **EchoMind - Login**, design `zWCKHDtCGxmxEmkSl0pe`, página `ThHPmFvVAyXGKTItA3AZ`.
- Referência de análise: [plano original](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/plano-refatoracao-design-echomind.md>), seções de autenticação e preservação de comportamento.
- Login envia `authApi.login`, consulta `authApi.me` e redireciona para `/dashboard` após sucesso.
- Cadastro mantém empresa, nome, email e senha; valida mínimo atual de seis caracteres, solicita cadastro e retorna a `/login`.
- Recuperação apresenta confirmação após o pedido; redefinição valida comprimento e confirmação antes de atualizar a senha e apresentar sucesso.
- Login já possui autocomplete de email/senha; redefinição utiliza `new-password`. Não há testes específicos dessas páginas entre os arquivos inspecionados.

## Escopo

- Login, cadastro, recuperação e redefinição; marca, card, títulos, ações, campos e estados visuais.
- Extração da composição comum sem transferir indevidamente estado ou envio dos formulários para o layout.
- Uso dos tokens e primitivas da DS-01, com adaptação das quatro telas a ambos os temas e às larguras previstas.

Fora do escopo: política de sessão, autenticação, permissões, novos provedores, novos destinos de suporte/termos/privacidade, opção de conexão por 30 dias, remoção do cadastro, backend e dependências.

## Requisitos observáveis

- **DS-02-R01:** As quatro telas exibem a mesma identidade, tratamento de superfície, hierarquia e escala de espaçamento aprovados em DS-00/01; seus títulos continuam distinguindo os fluxos.
- **DS-02-R02:** A área do formulário permanece legível e utilizável em 1440, 1024, 768 e 390 px, nos temas claro e escuro, sem corte de campos ou ações por centralização vertical rígida.
- **DS-02-R03:** Login bem-sucedido preserva a sequência de autenticação, consulta de usuário e destino `/dashboard`; falhas permanecem perceptíveis e não causam redirecionamento de sucesso.
- **DS-02-R04:** Cadastro preserva os quatro campos, a validação mínima atual de senha, o pedido de confirmação de email e o retorno a `/login`.
- **DS-02-R05:** Recuperação mantém pedido por email, estado de envio, confirmação de sucesso e retorno ao login; redefinição mantém confirmação da senha, validações e estado de senha atualizada.
- **DS-02-R06:** Cada campo possui nome acessível associado, tipo apropriado, obrigatoriedade e semântica de autocomplete preservadas; foco e mensagens são perceptíveis com teclado.
- **DS-02-R07:** Durante uma solicitação, a ação principal conserva seu bloqueio e indicador de carregamento; erro encerra o carregamento e permite nova tentativa conforme o fluxo existente.
- **DS-02-R08:** Links entre login, cadastro e recuperação, e os retornos ao login, continuam levando às rotas reais existentes.
- **DS-02-R09:** Não aparecem controles sem implementação, políticas de sessão sugeridas pelo mockup ou links com destinos fictícios.
- **DS-02-R10:** A composição visual é compartilhada, mas os formulários preservam responsabilidade pelo estado, validação e envio; APIs/backend, contratos e regras de sessão permanecem inalterados.

## Arquivos candidatos e limites

Os arquivos abaixo orientam o levantamento; não constituem obrigação de editar todos.

- [Layout de autenticação](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(auth)/layout.tsx>) — candidato à composição externa comum.
- [Login](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(auth)/login/page.tsx>).
- [Cadastro](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(auth)/registrar-conta/page.tsx>).
- [Recuperação](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(auth)/recuperar-senha/page.tsx>).
- [Redefinição](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/app/(auth)/redefinir-senha/page.tsx>).
- [Primitivas existentes](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/components/ui/button.tsx>) — preferir consumo, sem redefinir a base nesta fase.
- [Cliente de API](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-front/lib/api.ts>) — referência de leitura; seu contrato não integra o escopo de alteração.

Uma composição adicional poderá ficar junto ao grupo de autenticação ou em componentes compartilhados se houver necessidade concreta; seu nome não é imposto por esta spec.

## Critérios de aceitação

- **DS-02-AC01 — R01/R02:** Dado cada formulário nos dois temas, quando aberto em desktop e celular, então marca, card, campos e ações seguem a mesma base e permanecem visíveis sem overflow horizontal.
- **DS-02-AC02 — R03/R07:** Dado um login simulado, quando a resposta é sucesso ou erro, então a sequência e o redirecionamento atuais são preservados, o carregamento termina e a mensagem correspondente é perceptível.
- **DS-02-AC03 — R04:** Dado o cadastro, quando a senha tem menos de seis caracteres, então a validação atual impede o envio; quando a resposta simulada é sucesso, então há orientação de confirmação e retorno ao login.
- **DS-02-AC04 — R05/R07:** Dada a recuperação, quando o pedido simulado conclui ou falha, então são exibidos confirmação ou erro e os caminhos atuais de continuação permanecem disponíveis.
- **DS-02-AC05 — R05:** Dada a redefinição, quando as senhas divergem ou são curtas, então não ocorre atualização; quando uma atualização simulada conclui, então a confirmação e o retorno ao login aparecem.
- **DS-02-AC06 — R06/R08:** Dado uso apenas de teclado, quando se percorrem campos, envio e links, então nomes, foco, ordem e destinos são compreensíveis e operáveis.
- **DS-02-AC07 — R09/R10:** Dada a comparação do diff e das quatro telas, quando a entrega é revisada, então não há novas políticas, links fictícios, alteração de contrato ou duplicação de estrutura visual entre os formulários.

## Plano de implementação

- [ ] Conferir DS-00/01, aprovação, estado local e composição visual aprovada para autenticação.
- [ ] Recuperar a referência de login pelo MCP ou registrar a referência verificada disponível e qualquer limitação.
- [ ] Mapear a estrutura comum e manter os handlers dos formulários sob suas responsabilidades atuais.
- [ ] Aplicar composição, marca, tipografia, campos e ações utilizando a base compartilhada.
- [ ] Conferir sucesso, falha, carregamento e validação de cada fluxo com mocks ou dados de teste.
- [ ] Inspecionar quatro páginas, temas, larguras, teclado, zoom e conteúdo extenso.
- [ ] Executar verificações e registrar resultados/imagens no STATUS; entregar para revisão.

## Verificações e evidências esperadas

- Executar `pnpm lint` e `pnpm typecheck` no frontend; executar testes existentes relacionados que estiverem presentes no momento da implementação.
- Não há suíte dedicada de autenticação identificada nesta preparação. Caso a extração altere composição comportamental relevante, acrescentar teste dirigido ao comportamento afetado, sem testes de classes CSS.
- Registrar a matriz dos quatro fluxos com estados exercitados por mocks. Não modificar contas ou senhas reais para validar a aparência.
- Apresentar imagens dos quatro formulários e estados representativos de sucesso/erro/carregamento, identificando tema e viewport.
- Antecipar build se a extração alterar importação ou fronteira de renderização relevante; registrar falhas e limitações sem chamá-las de aprovação.

## Conclusão e aprovações

Concluída tecnicamente somente quando requisitos e critérios possuem evidência, verificações obrigatórias passam ou limitações são explicitamente encaminhadas, e o diff está restrito à fase. Implementação, verificação e revisão do usuário são registros distintos no STATUS.

Não avançar de fase nem criar commit/push automaticamente. Mudanças materiais de identidade, composição ou comportamento exigem atualizar a proposta e obter aprovação antes da implementação dependente. Todas as caixas acima permanecem pendentes nesta entrega documental.
