# Deploy e operação do EchoMind

Antes de publicar com dados pessoais, concluir a
checklist de LGPD e segurança interna, incluindo retenção,
fornecedores e resposta a incidentes. A limpeza automática do chat é ativada
explicitamente por instituição no painel; a primeira execução ocorre uma hora
após a inicialização. Não há exclusão habilitada por padrão nem no ato do deploy.
Cada instituição preenche sua própria política e contato no painel. Não há
perfil/e-mail/prazo automático por nome; UniEVANGÉLICA e 30 dias são dados do
primeiro cadastro usado nos testes. O contato da equipe do projeto permanece
separado do contato institucional. Confirmar controlador, operação e instruções
antes de liberar o uso real, conforme a checklist.
Registrar essas decisões na cópia privada do
modelo de ficha por instituição interna, fora do
Git e do site. O modelo é mantido com a documentação interna.

FastAPI `0.133.1` e Starlette `1.3.1` foram validados localmente com o lock da
imagem, sem alterar Pydantic, modelo ou schema. Sem Bearer token, rotas protegidas
retornam `401` com `WWW-Authenticate: Bearer`; outra instituição continua `403`.
O frontend já trata `401`. O chat escuta a desconexão durante a espera de tokens;
manter o ensaio de cancelamento do HTTPS ao atualizar o framework novamente.
Resultados e limites na avaliação do backend interna.

Esta etapa exige aplicar as migrations **0024, 0025 e 0026 antes de publicar a nova API** pelo
procedimento de banco existente; não há migração automática. A `0024` adiciona os
campos de privacidade, sem remover registros. A `0025` revoga os privilégios de
`PUBLIC`, `anon` e `authenticated` nas tabelas do aplicativo e os defaults de
novas tabelas do executor no schema público. Não altera Supabase Auth, Storage,
funções de extensões ou a conexão do backend. Usar o mesmo papel de banco do
backend no procedimento existente; outros criadores exigem revisão dos defaults.
A `0026` adiciona hash e recibo de encaminhamento às interações, sem apagar
histórico. Publicar a nova API antes do frontend: versões antigas da API ainda
encaminham automaticamente. Com a API nova, clientes públicos antigos em texto
continuam funcionando, mas não alimentam a fila nem exibem a confirmação.
Validar com pergunta sintética: **Agora não** mantém a fila intacta; **Enviar
pergunta** encaminha uma vez, inclusive após duplo clique ou tentativa repetida.
Respostas conhecidas e falhas técnicas não devem oferecer encaminhamento.
O downgrade de `0026` invalida confirmações pendentes e remove os recibos, sem
excluir histórico ou perguntas já encaminhadas; preferir manter os campos em rollback.
O preflight bloqueia permissões diretas de clientes, inclusive após restauração
de backups sem ACLs. Cadastros existentes ficam com o
chat público bloqueado até preencherem controlador, contato, finalidade, base
legal, prazo e ativarem a limpeza em **Configurações → Privacidade e retenção**.
Mapas e eventos continuam acessíveis. Se houver revisões anteriores pendentes,
revisar os riscos próprios delas; `0023` é destrutiva para o recurso descontinuado.
Conferir aviso em `/p/{slug}/privacidade`, chat sintético e eventos
`privacy.retention` após a liberação. A checklist interna
detalha ativação, descarte, direitos e reversão. A imagem inclui o comando
`python scripts/purge_chat_data.py` para prévia e manutenção, sem dados reais
nos argumentos além da identificação institucional necessária.

Para atender um pedido sobre interações específicas, a imagem também inclui
`python scripts/manage_chat_data.py`: recebe seleção privada de IDs e instituição,
mostra contagem por padrão, exporta para arquivo privado com `--export-to` ou
exclui a seleção conferida com `--apply`. A ferramenta não identifica titulares,
não encerra contas e não exclui documentos/FAQs/dados de provedores. Seguir o
procedimento de direitos na checklist. Nunca registrar texto de conversa em
argumentos ou logs; exportações/seleções devem permanecer fora do Git. No
container, usar destino temporário gravável e transferir o arquivo por canal
privado antes de remover as cópias temporárias.

Em produção, manter tracing/debug do LangChain/LangSmith desativado. A API
recusa flags que ativem esses recursos, pois podem registrar prompts e respostas
inteiros em um serviço adicional. Não adicionar chaves/flags de tracing ao
ambiente sem revisão de privacidade. A reversão da migration `0025` preserva
as restrições de acesso; não restaura permissões amplas automaticamente.

Estrutura: a raiz contém este guia, `.env.example` e os dois arquivos Compose.
`aws/` define a infraestrutura; `pipeline/` publica e recupera versões;
`proxy/` configura HTTPS; `operations/` reúne manutenção, backup e medições;
`tests/` contém validações e testes auxiliares, com dados sintéticos em `tests/fixtures/`.

## Arquitetura e infraestrutura

- Frontend: Next.js na Vercel, projeto com raiz `echomind-front`, Node 22 e pnpm do `package.json`.
- API: FastAPI e Caddy/HTTPS em uma EC2 `t3.small`, Linux amd64, região `us-east-1`.
- Um worker e uma instância: embeddings E5 na CPU, respostas pela Groq; banco, vetores e Auth no Supabase.
- API: https://echomind-api.duckdns.org. Frontend: https://echomind-front.vercel.app.
- Dados persistentes em EBS criptografado. Docker/containerd em `/srv/echomind`; configuração privada em `/etc/echomind`.

Os templates em `aws` são a fonte da infraestrutura: `stack.yaml` define EC2,
rede, disco, snapshots, auditoria e alertas; `access.yaml` define o operador;
`provisioning.yaml` separa permissões administrativas das da aplicação;
`pipeline.yaml` define OIDC, ECR, S3 e o comando SSM de publicação. Os templates
`restore-access.yaml` e `restore-drill.yaml` permitem o ensaio isolado de recuperação.
Não excluir recursos ativos para limpar arquivos do repositório. Senha e MFA do
operador são configurados pelo responsável; a aplicação não recebe escrita IAM.

## Publicação automática

1. Envie sua branch e abra um PR para `main`.
2. Aguarde os testes de backend, frontend, migrations e segurança/recuperação do deploy.
3. Integre o PR. O CI de **push da main** aprovado aciona `.github/workflows/deploy-aws.yml`.
4. Acompanhe os jobs `publish` e `deploy` no GitHub Actions.

O workflow usa OIDC com credenciais temporárias, imagens imutáveis por commit e
bundle verificado por SHA-256. Na EC2, drena escritas, faz backup dos originais,
atualiza os containers, verifica banco e HTTPS e libera escritas. Falhas tentam
recuperar a versão anterior. Deploys são serializados; a API pode ficar brevemente
indisponível. Migrations e reindexação **não** são automáticas.

Para a transição revisada `0023 → 0026`, o rollout confere as heads das imagens
sem rede/segredos. Se precisar recuperar o runtime `0023`, valida o banco com
o checker da imagem `0026` aprovada por digest e mantém a verificação HTTPS do
runtime recuperado. Isso também vale para recuperação de `pending.json`.
Outros pares de revisões são recusados antes de manutenção; não restaurar
grants amplos nem desfazer as migrações de segurança para contornar a checagem.

`main` exige PR e os quatro testes, aplica a regra a administradores e bloqueia
force push/exclusão, sem exigir outro revisor. Os ambientes `aws-build` e
`aws-production` devem permitir apenas `main`, sem tags. As trust policies usam
audience `sts.amazonaws.com` e o subject exato de cada ambiente do repositório.

Variáveis públicas do repositório, preenchidas com outputs reais da AWS:

| Variável | Origem |
| --- | --- |
| `AWS_DEPLOY_ENABLED` | `true` ativa o fluxo automático; `false` impede novos acionamentos automáticos |
| `AWS_ACCOUNT_ID` | Conta de destino |
| `AWS_BUILD_ROLE_ARN` / `AWS_DEPLOY_ROLE_ARN` | Outputs `BuildRoleArn` / `DeployRoleArn` |
| `AWS_BACKEND_REPOSITORY` / `AWS_PROXY_REPOSITORY` | Outputs `BackendRepositoryUri` / `ProxyRepositoryUri` |
| `AWS_RELEASE_BUCKET` / `AWS_DEPLOY_DOCUMENT` | Outputs `ReleaseBucketName` / `DeployDocumentName` |
| `AWS_INSTANCE_ID` | Instância do stack da aplicação |

Desativar a variável não cancela um comando SSM já iniciado. Uma execução manual
de `Deploy AWS` apenas publica artefatos da revisão atual da main com CI de push
aprovado; não implanta. A primeira ativação e o rollback real foram verificados
em 2026-10-20 no [PR #31](https://github.com/fellipegps/PI-EchoMind/pull/31) e na
[execução automática](https://github.com/fellipegps/PI-EchoMind/actions/runs/39436978677).

## Configuração privada

`deploy/.env.example` e `deploy/proxy/.env.example` contêm somente exemplos.
Na EC2, `/etc/echomind/backend.env` contém a configuração privada; `deploy.env`
contém domínio, contato ACME, rede e limites públicos. Arquivos devem pertencer
a root, modo `600`, fora do checkout/imagem. `operations/configure_runtime.py` valida a
configuração e pode instalá-la no host; não imprime os valores. Em uma máquina
nova é necessário instalar essa configuração privadamente antes de publicar.

Não colocar valores reais em Git, GitHub Variables, logs, argumentos SSM ou
relatórios. Não imprimir `docker inspect` completo. Mantenha um worker,
`BACKEND_ENV_FILE=/etc/echomind/backend.env`, portas 80/443, CORS com origem exata
e o DuckDNS apontando para o IP público da máquina. Caddy renova o certificado;
os volumes `proxy_data` e `proxy_config` preservam seu estado.

## Frontend e autenticacao

Na Vercel, produção acompanha `main`. Configure `NEXT_PUBLIC_API_URL` com a URL
HTTPS da API sem barra final, `NEXT_PUBLIC_SUPABASE_URL`, a chave pública em
`NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` e `ECHOMIND_REQUIRE_API_URL=true`.
Esses valores entram no build; nunca exponha `DATABASE_URL`, `GROQ_API_KEY` ou
`SUPABASE_SECRET_KEY` no frontend. Alterações exigem novo build.

No Supabase Auth, Site URL deve ser a origem do frontend e Redirect URLs deve
permitir `/redefinir-senha`; mantenha os retornos locais usados no desenvolvimento.
No backend, `ALLOWED_ORIGINS` deve incluir a origem exata do frontend.
Banco e frontend não são publicados atomicamente com a API. Mudanças de schema
exigem backup, ensaio de restauração e migrations explícitas e compatíveis.
O envio de e-mails para público geral depende da configuração de SMTP do projeto.

## Verificação e diagnóstico

Na raiz do repositório, para verificar HTTPS, redirecionamento, CORS e acesso anônimo:

```sh
python deploy/operations/verify_public.py --domain echomind-api.duckdns.org --origin https://echomind-front.vercel.app
```

Na EC2, `operations/check_application_host.py` verifica containers, limites e
contadores sem exportar ambientes/logs brutos. `operations/check_document_originals.py`
deve ser executado **dentro do backend**, com seu usuário e configuração existentes;
confere hashes/tamanhos e emite contagens. Esses scripts não são incluídos na imagem:
transfira o código público revisado e use uma entrada privada para a execução.
`operations/observe_capacity.py` observa o host; `operations/measure_resources.py` e
`operations/measure_public_chat.py` geram cargas sintéticas e não devem ser disparados em produção
sem janela e escopo definidos. `/health` sozinho não comprova chat ou embeddings.

## Backup e recuperação

Os volumes `echomind_documents` e `echomind_model_cache` sobrevivem à recriação
dos containers. Originais ficam no volume de documentos; registros, trechos e
vetores ficam no Supabase. Não executar `compose down --volumes` ou prune como limpeza.

Cada deploy salva originais/marcadores no prefixo privado `backups/` do S3. Isso
não inclui banco, credenciais, certificados ou cache. DLM cria snapshots diários
do EBS de dados e retém sete. `operations/backup_production_database.py` permite backup do
schema público e ensaio local de restauração, com projeto esperado explícito;
os arquivos privados ficam ignorados em `.database-backups`. Não equivale a um
backup completo de Supabase Auth ou a recuperação coordenada de todos os serviços.

Conferência somente em leitura de **02/11/2026**: política DLM ativa com sete
snapshots concluídos e criptografados; MFA da conta principal e do operador AWS
confirmados. Bucket do pipeline com bloqueio público e criptografia, mas sem
objetos correntes em `backups/` na consulta. Esses metadados não comprovam
restauração nem backup recente do banco. Supabase permanece no plano Free;
o procedimento de backup do schema público e restore local foi executado em
02/11: revisão `0023`, contagens de 19 tabelas e RLS conferidas, sem alterar
produção. Não inclui ACLs/Auth/Storage/originais; reaplicar grants e exclusões
antes de reabrir uma restauração. Falta definir frequência, prazo e cópia externa
restrita, sem pressupor backup gerenciado disponível ou
contratar upgrade. Custos, limites e pendências estão na
conferência operacional interna.

`/srv/echomind/current.json` registra o release saudável; `previous.json`, o
anterior; `pending.json`, uma operação interrompida. Preserve esses arquivos,
os diretórios e imagens referenciados. Confira o comando SSM antes de repetir um
deploy: timeout do runner não prova que o host parou. Não apague `pending.json`
para desbloquear a publicação.

Para reconciliar uma operação interrompida com anterior registrado, um operador
deve usar o `rollout.py` revisado com `--recover-previous`, como root via SSM,
com `RELEASE_BUCKET`, `BACKEND_REPOSITORY` e `PROXY_REPOSITORY` dos outputs reais.
O comando verifica, drena, recupera e retoma antes de remover o marcador.
Uma primeira implantação sem anterior exige diagnóstico; não há rollback inventado.
O suporte ao antigo baseline `manual-adoption` permanece para recuperar a versão
anterior à adoção do pipeline. Rollback não desfaz migrations nem restaura documentos.

Para ensaiar EBS: selecione snapshot concluído, criptografado e do disco correto;
confira IDs dos discos ativos, instância, AZ e slot livre. O administrador revisa
`SourceSnapshotId` em `restore-access.yaml`; o operador usa a role fixa de
provisionamento para criar somente o stack temporário de `restore-drill.yaml`.
Após confirmar a cópia pela API, use `operations/inspect_restored_volume.py`
com `--volume-id`, `--root-volume-id`, `--data-volume-id`, `--archive` e
`--archive-sha256`. Ele identifica o VolumeId pelo serial e monta somente a cópia
em leitura, sem replay do journal. Não formatar nem identificar a cópia pelo UUID.
Confira desmontagem antes de excluir somente o stack/cópia temporários; preserve
snapshot e discos ativos. O ensaio já realizado comprovou leitura dos originais,
não recuperação completa do serviço/banco nem um tempo de recuperação garantido.

`operations/rehearse_document_backup.py --sha256 HASH` recebe arquivo privado por
stdin dentro do backend e restaura em diretório temporário, sem substituir dados
ativos. `operations/restore_document_original.py` repara um original ausente,
valida por padrão e exige `--apply` para instalar; a entrada deve chegar por canal
privado autenticado, nunca em comandos/logs públicos. Essas operações não reindexam.

## Testes locais e armazenamento

```sh
docker build --tag echomind-infra-validation:local --file deploy/aws/validation.Dockerfile deploy/aws
python deploy/pipeline/validate.py
python deploy/tests/validate_runtime.py --image IMAGEM_BACKEND_LOCAL
python deploy/pipeline/smoke_release.py --image IMAGEM_BACKEND_LOCAL
python -m unittest discover -s deploy/tests -p "test_*.py"
```

Os testes usam dados sintéticos; a validação offline não chama a AWS. Execute os
testes de recuperação em Linux (container ou ambiente equivalente à EC2): eles
verificam permissões e comportamento do sistema de arquivos desse ambiente.
`tests/validate_https.py` com `tests/fixtures/https_app.py` testa o proxy com CA local;
`tests/validate_database_release.py` ensaia migrations/backup em PostgreSQL descartável.
O teste de restauração de arquivo requer as dependências do backend. A revisão
de um template precede qualquer aplicação real; recursos não mudam ao editar o guia.

S3 expira bundles após 90 dias, backups correntes após sete e versões não correntes
após mais sete. Imagens sem tag expiram após sete dias; imagens com tag e releases
locais requerem limpeza revisada, preservando ativo, anterior e operações pendentes.
O armazenamento cresce com novas versões. ECR/S3, transferências e a EC2/EBS podem
consumir créditos ou gerar cobrança. Consulte preços/créditos atuais; a pequena
carga controlada já medida não comprova capacidade sustentada, uploads máximos
ou funcionamento com créditos de CPU esgotados.
