# Deploy e operação do EchoMind

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
