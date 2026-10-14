# Preparação do EchoMind para publicação na AWS

Branch de trabalho: `codex/deploy-config`. A preparação será feita em etapas;
cada etapa precisa de evidência de validação antes de ser marcada como concluída.
Esta primeira etapa prepara o backend localmente. Ainda não publica a aplicação.

## Arquitetura definida

- Frontend Next.js na Vercel, usando a configuração já documentada no README.
- Backend FastAPI em um container Linux `amd64` em uma EC2 na região `us-east-1`.
- PostgreSQL, pgvector e autenticação continuam no Supabase.
- Geração das respostas continua na Groq; embeddings E5 rodam na CPU da EC2.
- Uma instância e um worker. O limitador em memória bloqueia configurações com
  mais workers ou réplicas; escalar exige primeiro um store compartilhado.
- `t3.small` com 2 GiB permanece como candidata para o MVP de baixo tráfego;
  o tamanho definitivo depende da medição no container com o modelo real e da
  margem para o sistema operacional e o proxy. A medição local anterior não
  equivale a um teste em Linux limitado a 2 GiB. Não é necessário usar GPU.
- A disponibilidade e a validade dos créditos da conta precisam ser verificadas
  antes de provisionar. Esta configuração não promete hospedagem gratuita permanente.

## Checklist de execução

- [x] **1. Análise e empacotamento do backend:** Dockerfile, contexto sem segredos,
  dependências fixadas para Python 3.12/Linux, usuário sem privilégios, um worker,
  teste de construção, inicialização, `/health` e encerramento controlado.
- [ ] **2. Inicialização automática:** Compose para a EC2, reinício após falha/reboot,
  volume do cache de modelos, rotação de logs, limites de recursos e tempo de parada.
  O Docker precisa estar habilitado no boot. Um healthcheck isolado não reinicia
  automaticamente um processo travado.
- [ ] **3. Persistência e segurança dos uploads durante atualizações:** definir e
  implementar a retenção dos originais, recuperação de processamento interrompido,
  drenagem antes de trocar versões e teste de recriação do container sem perda.
  Definir backup e recuperação; volume local não substitui backup.
- [ ] **4. Configuração de produção e segredos:** exemplo sem valores reais,
  validação de variáveis obrigatórias, armazenamento fora do Git e da imagem,
  entrega ao processo em tempo de execução e permissões mínimas. Se houver uso do
  Secrets Manager pelo agente, usar `asm-exec` e referências dinâmicas.
- [ ] **5. HTTPS e acesso público:** definir domínio da API, proxy e certificados
  com renovação, portas públicas 80/443, API acessível somente pelo proxy, CORS exato,
  streaming e limite de upload. Configurar confiança no IP do proxy para preservar
  o IP do cliente no rate limiting sem aceitar cabeçalhos falsificados.
- [ ] **6. Infraestrutura AWS:** revisar créditos e custos, identidade dedicada,
  EC2 por infraestrutura como código, acesso administrativo via Systems Manager,
  EBS criptografado e persistente, regras de rede, backup e orçamento/alertas.
- [ ] **7. Banco e frontend:** conferir migrations com backup e acesso PostgreSQL,
  aplicar migrations como operação explícita, ajustar URL HTTPS da API na Vercel e
  URLs de autenticação no Supabase. Reindexação de embeddings continua manual.
- [ ] **8. Publicação por GitHub Actions:** testes antes de publicar, autenticação
  temporária OIDC, imagem identificada pelo commit, atualizações serializadas,
  drenagem de tarefas, verificação após deploy e recuperação da versão anterior.
  O fluxo atual em `.github/workflows/ci.yml` apenas testa e constrói o frontend.
- [ ] **9. Validação em produção:** login, recuperação de senha, chat, upload e
  consulta de documentos, memória/CPU/disco com embeddings reais, revisão de
  vulnerabilidades das dependências, logs e recuperação após reinício.

## O que a análise encontrou

| Área | Situação atual | Consequência para o deploy |
| --- | --- | --- |
| Runtime | FastAPI/Uvicorn e Python 3.12; frontend Next.js com Node 22 | Empacotar apenas o backend para EC2; manter o frontend separado |
| Dependências | Há versões fixas e intervalos em `requirements.txt` | Usar um lock específico de produção para evitar resolução diferente a cada build |
| Inicialização | A API pede Alembic antes de iniciar e aquece o RAG com timeout | Não aplicar migrations nem reindexar automaticamente ao reiniciar |
| Verificação | `/health` retorna que a API está viva | Não comprova banco, login, LLM ou disponibilidade do modelo |
| Uploads | Os bytes originais são passados em memória para `BackgroundTasks` | Encerrar o processo pode interromper um upload já aceito; um volume sozinho não resolve |
| Documentos processados | Metadados, texto, chunks e vetores ficam no PostgreSQL/Supabase | Recriar a API preserva o conteúdo já persistido; é necessário planejar backup do banco |
| Arquivos originais | Não há gravação durável dos PDFs/TXTs/DOCXs recebidos | A retenção e a retomada precisam ser tratadas na etapa 3 |
| Modelos | O código aceita `HF_HOME` para o cache do FastEmbed | Montar um volume nesse caminho para evitar novo download a cada atualização |
| Rate limiting | O código exige uma instância e um worker e usa o IP da conexão | Manter um worker e configurar corretamente o proxy HTTPS |
| Segredos | O backend usa `DATABASE_URL`, `SUPABASE_SECRET_KEY` e `GROQ_API_KEY` | Injetar em runtime; nunca copiar `.env` para o build ou usar chaves privadas no frontend |

## Etapa 1: empacotamento

Arquivos:

- `echomind-backend/Dockerfile`: base oficial Python 3.12/Bookworm fixada por digest,
  dependências com hashes, execução com UID/GID 10001 e um worker Uvicorn.
- `echomind-backend/.dockerignore`: permite apenas os arquivos explicitamente
  necessários; exclui configuração local, credenciais, testes e caches.
- `echomind-backend/requirements-deploy.lock`: dependências diretas e transitivas
  resolvidas para Python 3.12 em Linux `amd64`. Não substitui o arquivo usado no
  desenvolvimento Windows/Python 3.13 ou superior.

A imagem não contém banco de dados, frontend, segredos ou modelos baixados.
O caminho do cache é `/var/cache/echomind/models`. O volume será configurado na
etapa 2. A etapa 1 não garante retenção dos arquivos originais ou recuperação de
uploads interrompidos.

### Construir a imagem

Na raiz do repositório, com Docker em modo de containers Linux:

```sh
docker build --platform linux/amd64 --tag echomind-backend:local ./echomind-backend
```

O build não precisa de credenciais AWS, Supabase ou Groq. Não use o `.env` como
argumento de build. A base fixada por digest e o lock precisam ser atualizados
deliberadamente para incorporar correções de dependências.

### Verificar inicialização sem acessar serviços reais

Este teste usa apenas valores fictícios e desativa o aquecimento do RAG. O banco
aponta para uma porta local indisponível dentro do container. Não valida chat,
autenticação, migrations, ingestão ou download do E5.

```sh
docker run --detach --name echomind-backend-smoke --publish 127.0.0.1:18000:8000 --cpus 2 --memory 2g --env DATABASE_URL=postgresql://smoke:smoke@127.0.0.1:1/smoke --env SUPABASE_URL=http://127.0.0.1:54321 --env SUPABASE_SECRET_KEY=smoke-placeholder --env GROQ_API_KEY=smoke-placeholder --env RAG_WARMUP_ENABLED=false echomind-backend:local
```

Após a inicialização, abra `http://127.0.0.1:18000/health`. A resposta esperada é
`{"status":"ok","service":"EchoMind API"}`. O container deve executar com o
usuário `10001:10001` e sem processos de desenvolvimento ou recarga automática.

```sh
docker inspect --format '{{.Config.User}}' echomind-backend-smoke
docker stop --timeout 310 echomind-backend-smoke
docker inspect --format '{{.State.ExitCode}}' echomind-backend-smoke
docker rm echomind-backend-smoke
```

O código de saída esperado é `0`. A API permite até 300 segundos para concluir
requisições no encerramento; o orquestrador deve esperar mais que isso. Esse
timeout não garante concluir uploads longos; a etapa 3 precisa impedir que uma
atualização mate processamento ainda em curso.

### Atualizar o lock

Com `uv` disponível, execute na raiz do repositório e depois repita o build e os
testes. Use um interpretador Python 3.12; no Windows ele está atualmente em
`echomind-backend/.venv/Scripts/python.exe`.

```sh
uv pip compile echomind-backend/requirements.txt --python-version 3.12 --python-platform x86_64-unknown-linux-gnu --generate-hashes --no-annotate --no-header --no-emit-index-url --output-file echomind-backend/requirements-deploy.lock
```

## Evidência de validação

Etapa 1 concluída em 2026-10-14, com Docker Desktop executando containers Linux.

| Verificação | Resultado |
| --- | --- |
| Build `linux/amd64` | Sucesso; imagem local `echomind-backend:deploy-step1` |
| Instalação com hashes e somente wheels | Sucesso para as 105 dependências fixadas |
| `pip check` no build | Nenhuma dependência incompatível |
| Inicialização com dois CPUs e limite de 2 GiB | Sucesso com aquecimento do RAG desativado e configurações fictícias |
| GET `/health` pela porta publicada em localhost | HTTP 200 e resposta esperada |
| Healthcheck do Docker | `healthy` |
| Usuário do processo | UID/GID `10001:10001` |
| Configuração local na imagem | Nenhum `.env`, diretório `.aws`, virtualenv ou cache Python encontrado em `/app` |
| Cache de modelos | Caminho configurado gravável pelo usuário sem privilégios |
| Migrations disponíveis na imagem | `alembic heads` retorna `0023 (head)` sem conectar ao banco |
| Testes rápidos com as dependências da imagem | 514 passaram; 8 avisos de transação SQLAlchemy nas fixtures SQLite |
| Encerramento via SIGTERM | Código de saída 0; sem encerramento por falta de memória |
| Limpeza | Containers descartáveis removidos; imagem local preservada |

Os testes foram montados somente para leitura em um container descartável,
com datasets sintéticos e fixtures SQLite/mocks. Pytest e seus auxiliares foram
instalados apenas em `/tmp` desse container, preservando a imagem de produção;
`packaging` permaneceu na versão 24.2 do lock. O `.env.example` público foi
montado apenas para os testes de consistência da documentação. Nenhum `.env`
real foi lido ou enviado ao Docker.

Esses resultados não validam consumo de memória com E5 carregado, banco remoto,
autenticação real, Groq, HTTPS ou persistência após interrupção. Nenhum recurso
AWS foi criado ou alterado. A próxima etapa é a **2: inicialização automática**.

## Referências

- [FastAPI em containers](https://fastapi.tiangolo.com/deployment/docker/)
- [Boas práticas de build do Docker](https://docs.docker.com/build/building/best-practices/)
- [Contexto de build e `.dockerignore`](https://docs.docker.com/build/concepts/context/)
