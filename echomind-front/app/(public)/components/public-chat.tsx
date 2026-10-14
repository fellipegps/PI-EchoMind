import type { ComponentProps, FormEvent, RefObject } from "react";
import { ChevronRight, Loader2, Send, Sparkles } from "lucide-react";
import Markdown from "react-markdown";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { PublicEvent, PublicFaq } from "@/lib/api";
import { EventSummary } from "./public-events";

export type ChatMessage = { id: number; role: "assistant" | "user"; content: string };

const markdownComponents = {
  pre: ({ children }: ComponentProps<"pre">) => (
    <pre role="region" aria-label="Código da resposta" tabIndex={0}
      className="outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card">
      {children}
    </pre>
  ),
};

function FaqSuggestions({ faqs, disabled, onQuestion, auxiliary = false }: {
  faqs: PublicFaq[];
  disabled: boolean;
  onQuestion: (question: string) => void;
  auxiliary?: boolean;
}) {
  return (
    <div className="space-y-3" aria-label="Perguntas frequentes">
      <h3 className="text-sm leading-5 font-semibold">Perguntas frequentes</h3>
      <div className="flex flex-col gap-2">
        {faqs.map((faq) => (
          <Button key={faq.id} type="button" variant="outline" disabled={disabled}
            aria-label={auxiliary ? `Perguntar: ${faq.question}` : undefined}
            onClick={() => onQuestion(faq.question)}
            className="h-auto min-h-11 w-full justify-between gap-3 whitespace-normal px-3 py-3 text-left [overflow-wrap:anywhere]">
            <span className="min-w-0">{faq.question}</span><ChevronRight aria-hidden="true" className="size-4" />
          </Button>
        ))}
      </div>
    </div>
  );
}

export function PublicChat({ messages, scrollRef, input, onInput, onSubmit, onQuestion, faqs,
  sending, waitingForFirstToken, blocked, portalLoading, portalError, chatError }: {
  messages: ChatMessage[];
  scrollRef: RefObject<HTMLDivElement | null>;
  input: string;
  onInput: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onQuestion: (question: string) => void;
  faqs: PublicFaq[];
  sending: boolean;
  waitingForFirstToken: boolean;
  blocked: boolean;
  portalLoading: boolean;
  portalError: string;
  chatError: string;
}) {
  return (
    <div className="min-w-0 rounded-xl border border-border bg-card text-card-foreground shadow-sm">
      {portalLoading ? <p className="m-4 rounded-lg border border-border bg-muted p-4 text-sm text-muted-foreground" role="status">Carregando portal da instituição...</p> : null}
      {portalError ? <p className="m-4 rounded-lg border border-destructive bg-card p-4 text-sm text-destructive [overflow-wrap:anywhere]" role="alert">{portalError}</p> : null}

      <div ref={scrollRef} role="log" aria-label="Conversa com o assistente" aria-live="polite" aria-relevant="additions text" aria-atomic="false"
        tabIndex={0} className="flex max-h-[min(640px,65dvh)] min-h-64 min-w-0 flex-col gap-6 overflow-y-auto overscroll-y-contain rounded-t-xl p-4 outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background sm:p-6">
        {messages.map((message) => (
          <article key={message.id} aria-label={message.role === "assistant" ? "Resposta do assistente" : "Sua pergunta"}
            className={message.role === "user" ? "flex min-w-0 justify-end" : "flex min-w-0 items-start gap-3"}>
            {message.role === "assistant" ? <span aria-hidden="true" className="flex size-8 shrink-0 items-center justify-center rounded-full bg-accent text-primary"><Sparkles className="size-4" /></span> : null}
            <div className={message.role === "user"
              ? "min-w-0 max-w-[85%] space-y-1 rounded-xl bg-primary p-4 text-primary-foreground [overflow-wrap:anywhere]"
              : "min-w-0 max-w-full space-y-1 rounded-xl border border-border bg-card p-4 [overflow-wrap:anywhere]"}>
              <p className="text-xs leading-4 font-medium">{message.role === "assistant" ? "EchoMind" : "Você"}</p>
              {message.role === "assistant" ? (
                <div className="space-y-3 text-base leading-6 [&_p]:whitespace-pre-wrap [&_ul]:list-disc [&_ul]:pl-6 [&_ol]:list-decimal [&_ol]:pl-6 [&_li+li]:mt-1 [&_a]:text-primary [&_a]:underline [&_a]:underline-offset-4 [&_a]:outline-none [&_a:focus-visible]:ring-2 [&_a:focus-visible]:ring-ring [&_a:focus-visible]:ring-offset-2 [&_a:focus-visible]:ring-offset-card [&_pre]:max-w-full [&_pre]:overflow-x-auto [&_pre]:rounded-sm [&_pre]:bg-muted [&_pre]:p-3 [&_pre]:text-sm [&_code]:font-mono [&_code]:text-sm [&_blockquote]:border-l-2 [&_blockquote]:border-border [&_blockquote]:pl-3 [&_blockquote]:text-muted-foreground">
                  <Markdown components={markdownComponents} skipHtml allowedElements={["p", "strong", "em", "a", "br", "ul", "ol", "li", "code", "pre", "blockquote"]} unwrapDisallowed>{message.content}</Markdown>
                </div>
              ) : <p className="whitespace-pre-wrap text-base leading-6">{message.content}</p>}
            </div>
          </article>
        ))}
        {sending && waitingForFirstToken ? <p role="status" className="flex items-center gap-2 text-sm leading-5 text-muted-foreground"><span className="animate-spin motion-reduce:animate-none"><Loader2 aria-hidden="true" className="size-4" /></span>Buscando a melhor resposta...</p> : null}
      </div>

      {faqs.length > 0 ? <div className="border-t border-border p-4 sm:p-6 xl:hidden"><FaqSuggestions faqs={faqs} disabled={blocked} onQuestion={onQuestion} /></div> : null}
      {chatError ? <p role="alert" className="mx-4 my-4 rounded-lg border border-destructive bg-card p-4 text-sm leading-5 text-destructive [overflow-wrap:anywhere]">{chatError}</p> : null}
      <form onSubmit={onSubmit} aria-busy={sending} className="flex min-w-0 items-center gap-3 border-t border-border p-4 sm:p-6">
        <label className="sr-only" htmlFor="portal-question">Digite sua pergunta</label>
        <Input id="portal-question" value={input} onChange={(event) => onInput(event.target.value)} placeholder="Digite sua dúvida..." disabled={blocked} autoComplete="off" className="md:text-base md:leading-6" />
        <Button type="submit" size="icon" aria-label="Enviar pergunta" disabled={blocked || !input.trim()}>
          {sending ? <span className="animate-spin motion-reduce:animate-none"><Loader2 aria-hidden="true" className="size-5" /></span> : <Send aria-hidden="true" className="size-5" />}
        </Button>
      </form>
    </div>
  );
}

export function ChatAuxiliary({ faqs, events, eventsLoading, eventsError, disabled, onQuestion, onEvents }: {
  faqs: PublicFaq[];
  events: PublicEvent[];
  eventsLoading: boolean;
  eventsError: string;
  disabled: boolean;
  onQuestion: (question: string) => void;
  onEvents: () => void;
}) {
  return (
    <div className="space-y-6 text-foreground">
      {faqs.length > 0 ? <div className="rounded-xl border border-border bg-card p-4"><FaqSuggestions faqs={faqs} disabled={disabled} onQuestion={onQuestion} auxiliary /></div> : null}
      <section aria-labelledby="chat-events-title" className="space-y-4 rounded-xl border border-border bg-card p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 id="chat-events-title" className="text-sm leading-5 font-semibold">Agenda da instituição</h3>
          <Button type="button" variant="link" onClick={onEvents} className="px-0">Ver eventos</Button>
        </div>
        {eventsLoading ? <p role="status" className="text-sm text-muted-foreground">Carregando eventos...</p>
          : eventsError ? <p role="alert" className="text-sm text-destructive">{eventsError}</p>
          : events.length === 0 ? <p className="text-sm text-muted-foreground">Nenhum evento programado no momento.</p>
          : <ul className="space-y-4">{events.map((event) => <EventSummary event={event} key={event.id} />)}</ul>}
      </section>
    </div>
  );
}
