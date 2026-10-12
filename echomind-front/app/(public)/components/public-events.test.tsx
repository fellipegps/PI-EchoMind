import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { PublicEvent } from "@/lib/api";
import { EventCard, EventSummary, PublicEvents } from "./public-events";

const event: PublicEvent = {
  id: "event-fixture", title: "Encontro de projetos", course: "Curso institucional",
  location: "Auditório", description: "Descrição completa recebida.", event_type: "evento_social",
  event_date: "2099-08-15", event_end_date: "2099-08-17",
  image_url: "https://example.com/capa.png", link_url: "https://example.com/evento",
};

describe("Eventos públicos", () => {
  it.each([
    ["2099-08-15", "2099-08-15", "15 de Agosto de 2099"],
    ["2099-08-15", "2099-08-17", "15 a 17 de Agosto de 2099"],
    ["2099-08-31", "2099-09-02", "31 de Agosto a 2 de Setembro de 2099"],
    ["2099-12-31", "2100-01-02", "31 de Dezembro de 2099 a 2 de Janeiro de 2100"],
  ])("preserva o período %s → %s na agenda e no resumo", (start, end, period) => {
    const item = { ...event, event_date: start, event_end_date: end };
    render(<><EventCard event={item} /><ul aria-label="Resumo"><EventSummary event={item} /></ul></>);
    const card = screen.getByRole("article", { name: event.title });
    expect(within(card).getByRole("heading", { level: 3 })).toHaveTextContent(event.title);
    expect(within(card).getByText(period)).toBeInTheDocument();
    expect(within(card).getByText(event.course)).toBeInTheDocument();
    expect(within(card).getByText(event.location)).toBeInTheDocument();
    expect(within(card).getByText(event.description!)).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: "Resumo" })).getByText(period)).toBeInTheDocument();
  });

  it.each([
    ["https://example.com/recurso", true, true],
    ["http://example.com/recurso", false, true],
    ["javascript:alert(1)", false, false],
    ["data:image/png;base64,AAAA", false, false],
    ["ftp://example.com/recurso", false, false],
    ["https://usuario:senha@example.com/recurso", false, false],
    ["https://example.com/com espaço", false, false],
    ["https://example.com/com\ncontrole", false, false],
    ["//example.com/recurso", false, false],
    ["endereço inválido", false, false],
  ])("mantém a regra de protocolo/validação para %s", (url, imageAllowed, linkAllowed) => {
    render(<EventCard event={{ ...event, image_url: url, link_url: url }} />);
    expect(Boolean(screen.queryByRole("img"))).toBe(imageAllowed);
    const link = screen.queryByRole("link");
    expect(Boolean(link)).toBe(linkAllowed);
    if (imageAllowed) {
      expect(screen.getByRole("img", { name: event.title })).toHaveAttribute("src", url);
      expect(screen.getByRole("img")).toHaveAttribute("referrerpolicy", "no-referrer");
    }
    if (linkAllowed) {
      expect(link).toHaveAttribute("href", url);
      expect(link).toHaveAccessibleName(url);
      expect(link).toHaveAttribute("target", "_blank");
      expect(link).toHaveAttribute("rel", "noopener noreferrer");
    }
  });

  it("retira uma capa quebrada sem perder os dados ou o link", () => {
    render(<EventCard event={event} />);
    fireEvent.error(screen.getByRole("img", { name: event.title }));
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: event.title })).toBeInTheDocument();
    expect(screen.getByText(event.course)).toBeInTheDocument();
    expect(screen.getByText(event.description!)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: event.link_url! })).toBeInTheDocument();
  });

  it("omite somente campos opcionais ausentes, sem substituir por conteúdo inventado", () => {
    render(<EventCard event={{ ...event, image_url: null, link_url: null, description: null }} />);
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.queryByText(event.description!)).not.toBeInTheDocument();
    expect(screen.getByText(event.course)).toBeInTheDocument();
    expect(screen.getByText(event.location)).toBeInTheDocument();
  });

  it("expõe carregamento compreensível e preserva a ordem dos dados recebidos", () => {
    const { rerender } = render(<PublicEvents events={[]} loading error="" />);
    expect(screen.getByRole("status")).toHaveTextContent("Carregando eventos...");
    expect(screen.queryByText("Nenhum evento programado no momento.")).not.toBeInTheDocument();
    rerender(<PublicEvents events={[{ ...event, id: "primeiro", title: "Z primeiro recebido" }, { ...event, id: "segundo", title: "A segundo recebido" }]} loading={false} error="" />);
    expect(screen.getAllByRole("heading", { level: 3 }).map((heading) => heading.textContent)).toEqual(["Z primeiro recebido", "A segundo recebido"]);
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });
});
