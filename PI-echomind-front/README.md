~Tecnologias e Versões
Para garantir que o projeto rode sem problemas, recomendo o uso das seguintes versões:

-Node.js: v20.x (LTS) ou superior
-pnpm: v10.x
-Next.js: v15.x (App Router)

~Instalação e Configuração
1. Pré-requisitos (pnpm)
Caso ainda não tenha o pnpm instalado, utilize um dos comandos abaixo:

Via PowerShell (Windows):
Invoke-WebRequest https://get.pnpm.io/install.ps1 -UseBasicParsing | Invoke-Expression

Via npm (Se já tiver o Node instalado):
npm install -g pnpm@latest-10

2. Clone o repositório

3. Instale as dependências
pnpm install

4. Como rodar o projeto
Desenvolvimento
Para rodar o servidor local com hot-reload:
pnpm dev
O projeto estará disponível em http://localhost:3000. 
