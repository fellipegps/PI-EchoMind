import Link from "next/link";
import { PROJECT_PRIVACY_EMAIL, PROJECT_PRIVACY_MAILTO } from "@/lib/privacy-contact";

export default function PrivacyPage() {
  return (
    <main className="mx-auto max-w-3xl space-y-6 px-6 py-10 text-foreground">
      <h1 className="text-3xl font-semibold">Privacidade no EchoMind</h1>
      <p className="text-sm text-muted-foreground">Atualizado em 10 de novembro de 2026.</p>
      <p>O EchoMind oferece atendimento com inteligência artificial a partir das informações da instituição identificada no portal. Use o chat para dúvidas gerais; não envie documentos pessoais, CPF, senhas, dados de saúde ou informações de terceiros.</p>
      <section className="space-y-2" aria-labelledby="responsibilities-title">
        <h2 id="responsibilities-title" className="text-xl font-semibold">Responsabilidades no atendimento</h2>
        <p>A instituição que define a finalidade e as condições de uso dos dados responde por essas decisões e pelo atendimento aos direitos dos visitantes. A equipe do EchoMind pode prestar a operação técnica conforme as instruções acordadas com a instituição. Os papéis e responsabilidades dependem do funcionamento de cada contratação.</p>
      </section>
      <section className="space-y-2">
        <h2 className="text-xl font-semibold">Quais dados são usados</h2>
        <p>As perguntas e respostas são armazenadas para acompanhar o atendimento. Quando o bot não consegue responder, você pode escolher encaminhar a pergunta para análise da equipe. Ela só entra na fila de perguntas não respondidas após essa confirmação, sujeita à triagem administrativa. Escolher “Agora não” não elimina a conversa do histórico, que segue o prazo informado pela instituição. O envio não garante uma resposta posterior. O chat não exige uma conta de visitante.</p>
        <p>No chat público, um filtro substitui padrões comuns de CPF, CNPJ numérico, e-mail e telefone com DDD por [DADO] antes de consultar a base, enviar à IA e gravar a pergunta. O filtro não reconhece todos os dados pessoais; nomes, senhas e informações de saúde podem passar. A mensagem original chega à API para essa filtragem e continua visível no seu navegador durante a conversa.</p>
        <p>Contas administrativas usam e-mail, senha e, quando informados, nome e instituição. A autenticação é realizada pelo Supabase Auth. O navegador mantém dados de sessão para o login e a preferência de tema.</p>
      </section>
      <section className="space-y-2">
        <h2 className="text-xl font-semibold">IA e serviços externos</h2>
        <p>Para gerar respostas, a pergunta e trechos relevantes da base institucional podem ser enviados à Groq. O Supabase armazena dados da aplicação e autentica administradores. A hospedagem e esses fornecedores podem tratar dados fora do Brasil, conforme a contratação da instituição.</p>
        <p>O mapa é um guia visual dos blocos, espaços internos e pontos de referência publicados pela instituição. As fichas apresentam descrições e fotos e podem ser abertas pelo mapa ou por QR Code. Os mapas de fundo e as imagens externas podem revelar seu endereço IP aos respectivos provedores.</p>
        <p>As respostas são geradas por IA, podem conter erros e devem ser confirmadas com a instituição quando necessário.</p>
      </section>
      <section className="space-y-2">
        <h2 className="text-xl font-semibold">Retenção e seus direitos</h2>
        <p>A instituição deve informar a finalidade, a base legal e os prazos de retenção aplicáveis ao seu atendimento. A eliminação do histórico depende da execução da rotina de descarte; cópias de segurança e dados dos fornecedores têm seus próprios ciclos de exclusão.</p>
        <p>Você pode solicitar confirmação do tratamento, acesso, correção e, quando aplicável, eliminação dos dados e revogação do consentimento. Procure os canais oficiais da instituição exibidos no portal e solicite o contato do responsável por privacidade. Informe apenas o necessário para localizar o atendimento, como data aproximada e assunto; não envie senhas.</p>
      </section>
      <section className="space-y-2" id="contato-equipe" aria-labelledby="project-contact-title">
        <h2 id="project-contact-title" className="text-xl font-semibold">Contato da equipe Horizon Code</h2>
        <p>Para pedidos sobre seus dados no projeto, escreva para <a className="underline underline-offset-4" href={PROJECT_PRIVACY_MAILTO}>{PROJECT_PRIVACY_EMAIL}</a>. O link abre seu aplicativo de e-mail; o site não envia o pedido automaticamente.</p>
        <p>Este é o contato da equipe do projeto, separado do responsável por cada atendimento institucional. Para pedidos sobre uma conversa, use o canal da instituição informado no aviso do respectivo portal. Se precisar de ajuda para localizar esse canal, informe apenas a instituição, o pedido, a data aproximada e o assunto; não envie senhas ou documentos pessoais por iniciativa própria.</p>
      </section>
      <p className="text-sm text-muted-foreground">Este aviso descreve o funcionamento do produto. A identificação do controlador, seu canal de privacidade e as condições específicas de tratamento devem ser divulgados pela instituição responsável antes do uso com dados pessoais.</p>
      <Link href="/login" className="inline-block underline underline-offset-4">Acessar conta administrativa</Link>
    </main>
  );
}
