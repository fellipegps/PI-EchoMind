# Ajuste autorizado — configurações simplificadas

13/10/2026 · Baseline `d9c0547`. Solicitação posterior à DS-16, sem nova fase, commit ou push autorizados.

O usuário pediu verificar a funcionalidade e retirar de `/configuracoes` as opções “Personalidade da IA” e “Voz do Chatbot”. Esta solicitação substitui, somente para esses controles, a preservação de opções de DS-15-R05/v1.0. As evidências históricas das fases não são reescritas como se os controles nunca tivessem existido.

## Verificação de uso e decisão

- `tone_of_voice` é funcional: `app/rag_engine.py` carrega o valor institucional, substitui `{tone}` no prompt e envia esse prompt ao modelo. O pedido será atendido retirando o seletor; o tom existente continuará preservado no backend.
- `chat_voice_gender` aparece em persistência, schemas, onboarding e importação, mas não tem consumidor de áudio no código da aplicação. Retirar seu seletor não elimina uma função atual de síntese de voz.
- Remover o grupo “Comportamento do agente”, imports/defaults dos seletores e atualizar a descrição da página. Salvar somente nome, descrição, website, telefone, endereço e horários; omitir os campos ocultos evita reenviar valores antigos ou redefini-los após falha de carregamento.
- Manter banco/migrações/API/RAG, valores já armazenados e cartão de URL/QR. A API usa atualização parcial (`exclude_unset=True`), conservando os campos omitidos. Não há exclusão de dados ou mudança do tom efetivo das instituições.

## Critérios e tarefas

- [x] Os dois seletores e o grupo não aparecem na página, nos dois temas e em desktop/celular.
- [x] Os seis campos restantes carregam, editam e salvam; payload exclui `tone_of_voice`, `chat_voice_gender` e metadados somente de leitura, inclusive após falha da carga.
- [x] Sucesso usa o retorno da API/slug; falha mantém edição e permite repetir; QR/portal preservados.
- [x] Lint, tipos e testes relacionados aprovados; registrar revisão visual e evidências reais.

Implementação e verificação do ajuste concluídas; aguardando revisão. Aceite do ajuste ainda não recebido. Pendências de zoom/download das fases anteriores continuam abertas. Sem commit ou push.

## Evidências — 13/10/2026

Pasta: [evidencias-configuracoes-simplificadas](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/ajustes/evidencias-configuracoes-simplificadas>).

| Critério | Resultado observado |
| --- | --- |
| Remoção visual | Teste da página confirma ausência dos seletores e grupo; seis medições no navegador real em 1440/390/320, claro/escuro, confirmam seis campos editáveis, nenhum controle removido, QR presente e documento sem overflow horizontal. `browser.json` e seis capturas `config-{claro,escuro}-{1440,390,320}.png`. |
| Salvamento parcial | Testes conferem payload exato com seis campos após carga válida e falha de carregamento. `save-request.jsonl` registra PUT /config autenticado, status 200, somente seis campos; nenhum campo oculto ou metadado. `backend-preservado.json` confirma tom/voz mantidos na fixture após salvar. |
| Retorno, erro e portal | Testes preservam loading, bloqueio, erro/repetição, retorno normalizado e slug. Navegador salvou o nome, recebeu valor normalizado/slug novo e atualizou URL/QR; `save-result.json` e `config-salva-escuro-390.png`. Os seis testes do cartão passaram; não foi afirmada nova homologação do download pelo navegador. |
| Verificações | `pnpm lint`, `pnpm typecheck` e `pnpm build`: código 0; build com 19 páginas. `pnpm test:run "app/(admin)/configuracoes/page.test.tsx" "app/(admin)/configuracoes/public-portal-card.test.tsx" lib/api.test.ts`: 20 testes em três arquivos, código 0. Logs reais na pasta. `git diff --check` passou. |

Uso funcional confirmado por leitura de [rag_engine.py](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-backend/app/rag_engine.py:495>) e envio do prompt ao modelo em [rag_engine.py](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-backend/app/rag_engine.py:1230>). Atualização parcial existente em [crud.py](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/echomind-backend/app/crud.py:578>). Busca em app/componentes/backend não encontrou síntese/reprodução de áudio consumindo `chat_voice_gender`; referências são de persistência/importação/schema. Bibliotecas instaladas não foram confundidas com consumidores da aplicação.

Código alterado somente na página e seus testes. Backend, tipos/contratos compartilhados, dados existentes e cartão de portal não foram alterados. Revisão de React: nenhum novo efeito/listener/dependência; rótulos e handlers dos seis campos preservados.

Ambiente: frontend compilado em 4210, fixture já existente da DS-15 em 4191; sessão/dados exclusivamente sintéticos. A primeira tentativa de navegador expirou e a sessão foi reiniciada. O build removeu o controle temporário da fixture iniciada antes da compilação; reiniciei a fixture após o build e refiz login com sucesso. Erros de preparação não foram apresentados como falhas da aplicação corrigida. A consulta HTTP local precisou de permissão ampliada pelas restrições do sandbox, sem rejeição automática. Não houve acesso a conta, banco ou modelo reais. Logs tiveram somente espaços finais/linhas vazias excedentes normalizados. Nenhum arquivo de ambiente foi editado.

![Configurações simplificadas no tema escuro](<C:/Users/Fellipe/Documents/Projeto Integrador/EchoMind-main/docs/specs/design-system/ajustes/evidencias-configuracoes-simplificadas/config-escuro-1440.png>)

## Autorização posterior de commit — 13/10/2026

Após a apresentação da alteração e verificações, o usuário solicitou “faça commite dessa alteração”. Autorizado somente o commit local do ajuste, testes, documentação e evidências. Mensagem: `refactor(settings): remove seletores de personalidade e voz`; identificação no histórico Git. Sem push. O registro de verificações descreve o estado anterior ao commit; nenhum aceite final ou dispensa de pendências anteriores foi inferido.
