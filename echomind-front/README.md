# Frontend do EchoMind

Interface em Next.js para o portal público e o painel administrativo. Para usar os dois fluxos localmente, mantenha a [API do EchoMind](../echomind-backend/README.md) rodando em outro terminal.

## 1. Instalar as dependências

Use Node.js 22, a versão da CI, e Corepack. A versão do pnpm está fixada no [package.json](package.json). Se você já usa pnpm, execute os mesmos comandos com a versão indicada no arquivo.

No Arch Linux, as ferramentas estão disponíveis nos pacotes `nodejs` e `corepack`.

A partir da raiz do repositório:

```bash
cd echomind-front
corepack pnpm install --frozen-lockfile
```

Execute os comandos seguintes dentro de `echomind-front`.

## 2. Configurar o ambiente

Se ainda não houver um `.env.local`, copie o [.env.local.example](.env.local.example).

```powershell
# Windows PowerShell
Copy-Item .env.local.example .env.local
```

```bash
# Linux e macOS
cp .env.local.example .env.local
```

| Variável | Valor para desenvolvimento |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` ou a origem da API em execução |
| `NEXT_PUBLIC_SUPABASE_URL` | URL do mesmo projeto Supabase usado pelo backend |
| `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | Chave pública `sb_publishable_...` desse projeto |

Consulte [onde encontrar a URL e a chave no Supabase](https://supabase.com/docs/guides/getting-started/api-keys). Mantenha as credenciais do banco, a chave secreta do Supabase e a chave da Groq no backend. Reinicie o frontend após alterar o `.env.local`.

Para testar recuperação de senha em um projeto Supabase de desenvolvimento, adicione `http://localhost:3000/redefinir-senha` às **Redirect URLs** em **Authentication → URL Configuration**. Use a origem pela qual você abre o frontend.

### Mapas

As variáveis `NEXT_PUBLIC_MAP_TILE_URL` e `NEXT_PUBLIC_MAP_TILE_ATTRIBUTION` permitem configurar os tiles do mapa base, que usa OpenStreetMap por padrão. Para habilitar as fotos aéreas na maquete da UniEVANGÉLICA e no cadastro administrativo, preencha `NEXT_PUBLIC_MAP_SATELLITE_TILE_URL` com uma URL XYZ de tiles de 256 px e `NEXT_PUBLIC_MAP_SATELLITE_TILE_ATTRIBUTION` com os créditos do provedor. Sem essas duas variáveis, a vista **Satélite** da maquete mostra os contornos do campus.

## 3. Iniciar o frontend

```bash
corepack pnpm dev
```

- [Login administrativo](http://localhost:3000/login) e [cadastro](http://localhost:3000/registrar-conta).
- **Portal público** em `/p/{slug}`. Copie o link da sua instituição no painel em **Configurações**. Na aba **Locais**, os marcadores e o diretório abrem as fichas dos destinos.
- Para voltar a rodar o frontend depois, execute `corepack pnpm dev` na mesma pasta. Encerre com `Ctrl+C`.

## Verificações

```bash
corepack pnpm lint
corepack pnpm typecheck
corepack pnpm test:run
```

Use `corepack pnpm test` para acompanhar alterações ou `corepack pnpm test:coverage` para gerar a cobertura. Os testes de navegador usam uma API simulada e precisam das portas 3019 e 4105 livres.

```bash
corepack pnpm exec playwright install chromium --only-shell
corepack pnpm test:e2e
```

## Build e publicação

Execute `corepack pnpm build` com as variáveis públicas de produção. O build exige a URL HTTPS do Supabase e a chave pública. Quando preenchida, `NEXT_PUBLIC_API_URL` deve ser a origem HTTPS da API, sem barra final. Defina `ECHOMIND_REQUIRE_API_URL=true` para exigir a URL da API no build.

Na Vercel, a raiz do projeto é `echomind-front`, o preset é **Next.js** e a produção acompanha a branch `main`. Alterações em `NEXT_PUBLIC_*` exigem um novo build. Veja [deploy, autenticação e CORS em produção](../deploy/README.md#frontend-e-autenticacao).

[Voltar à visão geral do EchoMind](../README.md)
