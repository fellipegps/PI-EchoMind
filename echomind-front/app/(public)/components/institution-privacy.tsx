"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { publicPortalApi, type PublicInstitution } from "@/lib/api";

export function InstitutionPrivacy({ publicSlug }: { publicSlug: string }) {
  const [institution, setInstitution] = useState<PublicInstitution | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true;
    publicPortalApi.getInstitution(publicSlug).then(value => { if (active) setInstitution(value); })
      .catch(() => { if (active) setFailed(true); });
    return () => { active = false; };
  }, [publicSlug]);
  return (
    <main className="mx-auto max-w-3xl space-y-6 px-6 py-10 text-foreground">
      <h1 className="text-3xl font-semibold">Privacidade no atendimento</h1>
      {!institution ? <p role={failed ? "alert" : "status"}>{failed ? "Não foi possível carregar as informações da instituição. Tente novamente mais tarde." : "Carregando informações de privacidade…"}</p> : <>
        <p className="text-lg">{institution.company_name}</p>
        {!institution.privacy_ready ? <p role="status" className="rounded-lg border p-4">As informações de privacidade ainda estão incompletas. O chat está indisponível até a instituição concluir o cadastro.</p> : null}
        <section className="space-y-2"><h2 className="text-xl font-semibold">Responsável e contato</h2>
          <p>Controlador: {institution.privacy_controller || "ainda não informado pela instituição"}.</p>
          {institution.privacy_email ? <p>Para solicitar acesso, correção ou eliminação quando cabível, escreva para{" "}
            <a className="underline underline-offset-4" href={`mailto:${encodeURIComponent(institution.privacy_email)}?subject=${encodeURIComponent("Pedido de privacidade — EchoMind")}`}>{institution.privacy_email}</a>.
          </p> : <p>O canal de privacidade da instituição ainda não foi cadastrado. Solicite esse contato pelos canais oficiais da instituição.</p>}
          <p>Informe a instituição, o direito que deseja exercer e uma referência mínima do atendimento, como data aproximada e assunto. Não envie senhas ou documentos pessoais por iniciativa própria. A instituição poderá verificar sua identidade de forma proporcional ao pedido.</p>
          <p>Você também pode pedir confirmação do tratamento e informações sobre compartilhamento, anonimização ou bloqueio de dados desnecessários ou tratados irregularmente, além de portabilidade, oposição e revogação de consentimento quando cabíveis. O atendimento é gratuito, observadas as condições legais. Consulte os <a className="underline underline-offset-4" href="https://www.gov.br/anpd/pt-br/assuntos/titular-de-dados-1/direito-dos-titulares" target="_blank" rel="noopener noreferrer">direitos explicados pela ANPD</a>.</p>
        </section>
        <section className="space-y-2"><h2 className="text-xl font-semibold">Finalidade e base legal do chat</h2>
          <p className="whitespace-pre-wrap">{institution.privacy_purpose || "Finalidade ainda não informada."}</p>
          <p className="whitespace-pre-wrap">Base legal informada pela instituição: {institution.privacy_legal_basis || "ainda não definida"}.</p>
        </section>
        <section className="space-y-2"><h2 className="text-xl font-semibold">Dados e fornecedores</h2>
          <p>O chat não exige uma conta de visitante. Perguntas, respostas, avaliações quando utilizadas e datas são armazenadas para o atendimento. Quando o bot não consegue responder, a pergunta só é encaminhada à fila de não respondidas após sua confirmação e passa pela triagem administrativa. Escolher “Agora não” não exclui a conversa do histórico. Encaminhar a pergunta não garante uma resposta posterior.</p>
          <p>Antes de consultar a base, enviar à IA ou gravar a pergunta, o chat público substitui padrões comuns de CPF, CNPJ numérico, e-mail e telefone com DDD por [DADO]. Esse filtro não reconhece todos os dados pessoais. A mensagem original chega à API para filtragem e permanece visível no seu navegador durante a conversa.</p>
          <p>A pergunta e trechos relevantes da base podem ser enviados à Groq para gerar respostas. O Supabase armazena dados e autentica administradores. Fornecedores e hospedagem podem tratar dados fora do Brasil, conforme a contratação. Consulte o responsável sobre operadores, países e condições aplicáveis.</p>
          <p>Não envie CPF, senhas, dados de saúde ou informações de terceiros. As respostas da IA podem conter erros; confirme informações importantes com a instituição.</p>
        </section>
        <section className="space-y-2"><h2 className="text-xl font-semibold">Retenção</h2>
          {institution.chat_retention_days ? <p>Prazo adotado para o histórico: {institution.chat_retention_days} dias. {institution.chat_retention_enabled ? "A limpeza automática roda a cada hora enquanto a API está ativa; registros podem permanecer até a próxima execução após o prazo." : "A limpeza automática está desativada; solicite esclarecimentos à instituição."}</p> : <p>O prazo do histórico ainda não foi definido.</p>}
          <p>A limpeza abrange conversas e a fila de perguntas não respondidas. Documentos, FAQs publicadas, contas, cópias de segurança e dados dos fornecedores seguem procedimentos próprios, que a instituição deve informar. As exceções legais de conservação são avaliadas no atendimento ao pedido.</p>
        </section>
        <section className="space-y-2"><h2 className="text-xl font-semibold">Mapas e armazenamento no navegador</h2>
          <p>A localização é opcional, depende de sua ação e da permissão do navegador e é usada para trajetos no dispositivo; as coordenadas não são enviadas à API EchoMind. Tiles de mapas e imagens são carregados de terceiros, que recebem seu IP e podem inferir a área visualizada.</p>
          <p>O navegador guarda a preferência de tema e, para administradores, dados necessários à sessão de login. Não há conta de visitante para conversar.</p>
        </section>
        <p className="text-sm text-muted-foreground">Para esclarecer as condições de tratamento dos seus dados, entre em contato com a instituição pelo canal informado acima.</p>
      </>}
      <Link className="inline-block underline underline-offset-4" href={`/p/${encodeURIComponent(publicSlug)}`}>Voltar ao portal da instituição</Link>
      <p className="text-sm text-muted-foreground"><Link className="underline underline-offset-4" href="/privacidade#contato-equipe">Contato da equipe técnica Horizon Code</Link>. Esse é o contato do projeto; o canal da instituição, quando cadastrado, aparece acima.</p>
    </main>
  );
}
