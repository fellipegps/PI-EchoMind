"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import {
  Bot,
  Building2,
  CalendarDays,
  ChevronRight,
  Loader2,
  MapPin,
  Navigation,
  Search,
  Send,
  Sparkles,
} from "lucide-react";

import { publicPortalApi, streamPublicChat } from "@/lib/api";
import type { PublicCampusLocation, PublicEvent, PublicFaq } from "@/lib/api";

import styles from "./public-portal.module.css";

type TabId = "chat" | "eventos" | "locais";

type ChatMessage = {
  id: number;
  role: "assistant" | "user";
  content: string;
};

const NAV_ITEMS = [
  { id: "chat", label: "Chat", icon: Bot },
  { id: "eventos", label: "Eventos", icon: CalendarDays },
  { id: "locais", label: "Locais", icon: MapPin },
] as const;

const INITIAL_MESSAGE: ChatMessage = {
  id: 1,
  role: "assistant",
  content: "Olá! Sou o assistente acadêmico. Como posso ajudar você hoje?",
};

function eventDateParts(eventDate: string) {
  const [year, month, day] = eventDate.split("-").map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  return {
    day,
    year,
    month: new Intl.DateTimeFormat("pt-BR", {
      month: "long",
      timeZone: "UTC",
    }).format(date).replace(".", ""),
  };
}

function capitalize(value: string) {
  return value.charAt(0).toLocaleUpperCase("pt-BR") + value.slice(1);
}

function formatEventPeriod(startDate: string, endDate: string) {
  const start = eventDateParts(startDate);
  const end = eventDateParts(endDate);
  const startMonth = capitalize(start.month);
  const endMonth = capitalize(end.month);
  if (startDate === endDate) return `${start.day} de ${startMonth} de ${start.year}`;
  if (start.month === end.month && start.year === end.year) {
    return `${start.day} a ${end.day} de ${startMonth} de ${start.year}`;
  }
  if (start.year === end.year) {
    return `${start.day} de ${startMonth} a ${end.day} de ${endMonth} de ${start.year}`;
  }
  return `${start.day} de ${startMonth} de ${start.year} a ${end.day} de ${endMonth} de ${end.year}`;
}

function safeEventUrl(value: string | null, protocols: string[]) {
  if (!value || /\s|[\u0000-\u001f\u007f]/.test(value)) return null;
  try {
    const url = new URL(value);
    return protocols.includes(url.protocol) && url.hostname && !url.username && !url.password
      ? value
      : null;
  } catch {
    return null;
  }
}

function EventCard({ event }: { event: PublicEvent }) {
  const [imageFailed, setImageFailed] = useState(false);
  const period = formatEventPeriod(event.event_date, event.event_end_date);
  const imageUrl = safeEventUrl(event.image_url, ["https:"]);
  const linkUrl = safeEventUrl(event.link_url, ["http:", "https:"]);

  return (
    <article className={styles.eventCard}>
      {imageUrl && !imageFailed && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          className={styles.eventCover}
          src={imageUrl}
          loading="lazy"
          referrerPolicy="no-referrer"
          alt={event.title}
          onError={() => setImageFailed(true)}
        />
      )}
      <div className={styles.eventBody}>
        <div className={styles.eventBodyContent}>
          <h3>{event.title}</h3>
          <p className={styles.eventInfo}><strong>Data:</strong> {period}</p>
          <p className={styles.eventInfo}><strong>Curso:</strong> {event.course}</p>
          <p className={styles.eventInfo}><strong>Local:</strong> {event.location}</p>
          {event.description && <p className={styles.eventDescription}>{event.description}</p>}
          {linkUrl && (
            <a className={styles.eventLink} href={linkUrl} target="_blank" rel="noopener noreferrer">
              {linkUrl}
            </a>
          )}
        </div>
      </div>
    </article>
  );
}

function schematicDistanceInMeters(
  from: PublicCampusLocation,
  to: PublicCampusLocation
) {
  return Math.max(25, Math.round(Math.hypot(to.x - from.x, to.y - from.y) * 12));
}

type PublicPortalProps = {
  publicSlug?: string;
};

export function PublicPortal({ publicSlug = "" }: PublicPortalProps) {
  const [activeTab, setActiveTab] = useState<TabId>("chat");
  const normalizedSlug = publicSlug.trim();
  const [companyName, setCompanyName] = useState("Portal Acadêmico");
  const [faqs, setFaqs] = useState<PublicFaq[]>([]);
  const [events, setEvents] = useState<PublicEvent[]>([]);
  const [eventsLoading, setEventsLoading] = useState(Boolean(normalizedSlug));
  const [eventsError, setEventsError] = useState("");
  const [locations, setLocations] = useState<PublicCampusLocation[]>([]);
  const [locationsLoading, setLocationsLoading] = useState(Boolean(normalizedSlug));
  const [locationsError, setLocationsError] = useState("");
  const [portalLoading, setPortalLoading] = useState(Boolean(normalizedSlug));
  const [portalError, setPortalError] = useState(
    normalizedSlug ? "" : "Link inválido. Solicite à instituição o endereço correto do portal."
  );
  const [messages, setMessages] = useState<ChatMessage[]>([INITIAL_MESSAGE]);
  const [input, setInput] = useState("");
  const [chatError, setChatError] = useState("");
  const [sending, setSending] = useState(false);
  const [waitingForFirstToken, setWaitingForFirstToken] = useState(false);
  const [locationSearch, setLocationSearch] = useState("");
  const [originId, setOriginId] = useState("");
  const [destinationId, setDestinationId] = useState("");
  const [locationStatus, setLocationStatus] = useState("");
  const [route, setRoute] = useState<{
    originName: string;
    destination: PublicCampusLocation;
    distance: number;
    minutes: number;
  } | null>(null);
  const nextMessageId = useRef(2);
  const firstToken = useRef(true);
  const chatScroll = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!normalizedSlug) return;
    publicPortalApi
      .listFaqs(normalizedSlug)
      .then((items) => setFaqs(items.slice(0, 4)))
      .catch(() => setFaqs([]));
    publicPortalApi
      .listEvents(normalizedSlug)
      .then(setEvents)
      .catch(() => {
        setEvents([]);
        setEventsError("Não foi possível carregar os eventos agora.");
      })
      .finally(() => setEventsLoading(false));
    publicPortalApi
      .listLocations(normalizedSlug)
      .then(setLocations)
      .catch(() => {
        setLocations([]);
        setLocationsError("Não foi possível carregar os locais agora.");
      })
      .finally(() => setLocationsLoading(false));
    publicPortalApi
      .getInstitution(normalizedSlug)
      .then((institution) => {
        setCompanyName(institution.company_name || "Portal Acadêmico");
      })
      .catch(() => {
        setCompanyName("Portal Acadêmico");
        setPortalError("Instituição não encontrada. Verifique o endereço e tente novamente.");
      })
      .finally(() => setPortalLoading(false));
  }, [normalizedSlug]);

  useEffect(() => {
    if (chatScroll.current) {
      chatScroll.current.scrollTop = chatScroll.current.scrollHeight;
    }
  }, [messages, sending]);

  const appendMessage = (role: ChatMessage["role"], content: string) => {
    const id = nextMessageId.current++;
    setMessages((current) => [...current, { id, role, content }]);
  };

  const sendQuestion = async (suggestedQuestion?: string) => {
    const question = (suggestedQuestion ?? input).trim();
    if (!question || sending) return;
    if (!normalizedSlug || portalError) {
      setChatError("Link inválido. Solicite à instituição o endereço correto do portal.");
      return;
    }

    setInput("");
    setChatError("");
    setSending(true);
    setWaitingForFirstToken(true);
    firstToken.current = true;
    appendMessage("user", question);

    await streamPublicChat(
      question,
      normalizedSlug,
      (token) => {
        if (!token) return;
        if (firstToken.current) {
          firstToken.current = false;
          setWaitingForFirstToken(false);
          appendMessage("assistant", token);
          return;
        }
        setMessages((current) => {
          const updated = [...current];
          const last = updated.at(-1);
          if (last?.role === "assistant") {
            updated[updated.length - 1] = { ...last, content: last.content + token };
          }
          return updated;
        });
      },
      () => {
        setSending(false);
        setWaitingForFirstToken(false);
      },
      () => {
        setSending(false);
        setWaitingForFirstToken(false);
        setChatError("Não foi possível obter uma resposta agora. Tente novamente em instantes.");
      }
    );
  };

  const submitChat = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void sendQuestion();
  };

  const filteredLocations = locations.filter((location) => {
    const normalizedSearch = locationSearch.trim().toLocaleLowerCase("pt-BR");
    return (
      !normalizedSearch ||
      `${location.name} ${location.category} ${location.building ?? ""} ${location.floor ?? ""} ${location.description ?? ""}`
        .toLocaleLowerCase("pt-BR")
        .includes(normalizedSearch)
    );
  });

  const selectDestination = (location: PublicCampusLocation) => {
    setDestinationId(location.id);
    setRoute(null);
    setLocationStatus(`${location.name} selecionado como destino.`);
  };

  const traceRoute = () => {
    const destination = locations.find((location) => location.id === destinationId);
    const storedOrigin = locations.find((location) => location.id === originId);
    const originName = storedOrigin?.name;

    if (!destination || !storedOrigin || !originName) {
      setLocationStatus("Selecione a origem e o destino para calcular o trajeto.");
      return;
    }
    const distance = schematicDistanceInMeters(storedOrigin, destination);
    setRoute({
      originName,
      destination,
      distance,
      minutes: Math.max(1, Math.ceil(distance / 75)),
    });
    setLocationStatus("Trajeto aproximado calculado.");
  };

  const originLocation = locations.find((location) => location.id === originId);
  const destinationLocation = locations.find(
    (location) => location.id === destinationId
  );

  return (
    <div className={styles.portalRoot}>
      <aside className={styles.navigation} aria-label="Navegação principal">
        <div className={styles.brand}>
          <span className={styles.brandMark}>EM</span>
          <span>EchoMind</span>
        </div>
        <nav className={styles.navItems}>
          {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
            <button
              className={`${styles.navButton} ${activeTab === id ? styles.navButtonActive : ""}`}
              type="button"
              key={id}
              onClick={() => setActiveTab(id)}
              aria-current={activeTab === id ? "page" : undefined}
            >
              <Icon aria-hidden="true" />
              <span>{label}</span>
            </button>
          ))}
        </nav>
      </aside>

      <div className={styles.mainWrapper}>
        <header className={styles.header}>
          <div>
            <span className={styles.headerEyebrow}>Portal do estudante</span>
            <h1>{companyName}</h1>
          </div>
          <span className={styles.statusPill}>
            <span aria-hidden="true" /> Assistente online
          </span>
        </header>

        <main className={styles.content}>
          {activeTab === "chat" && (
            <section className={styles.panel} role="tabpanel" aria-labelledby="chat-title">
              <div className={styles.sectionHeading}>
                <span className={styles.sectionIcon}><Sparkles aria-hidden="true" /></span>
                <div>
                  <p>Atendimento digital</p>
                  <h2 id="chat-title">Como podemos ajudar?</h2>
                </div>
              </div>

              {portalLoading && (
                <div className={styles.alert} role="status">
                  Carregando portal da instituição...
                </div>
              )}

              {portalError && (
                <div className={styles.alert} role="alert">
                  {portalError}
                </div>
              )}

              <div className={styles.chatCard}>
                <div className={styles.messages} ref={chatScroll} aria-live="polite">
                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className={`${styles.messageRow} ${
                        message.role === "user" ? styles.messageRowUser : ""
                      }`}
                    >
                      {message.role === "assistant" && (
                        <span className={styles.avatar}><Bot aria-hidden="true" /></span>
                      )}
                      <p className={`${styles.message} ${
                        message.role === "user" ? styles.userMessage : styles.assistantMessage
                      }`}>
                        {message.content}
                      </p>
                    </div>
                  ))}
                  {sending && waitingForFirstToken && (
                    <div className={styles.typing} role="status">
                      <Loader2 aria-hidden="true" /> Buscando a melhor resposta...
                    </div>
                  )}
                </div>

                {faqs.length > 0 && (
                  <div className={styles.suggestions} aria-label="Perguntas frequentes">
                    {faqs.map((faq) => (
                      <button
                        type="button"
                        key={faq.id}
                        onClick={() => void sendQuestion(faq.question)}
                        disabled={sending}
                      >
                        {faq.question}<ChevronRight aria-hidden="true" />
                      </button>
                    ))}
                  </div>
                )}

                {chatError && <p className={styles.chatError} role="alert">{chatError}</p>}
                <form className={styles.chatForm} onSubmit={submitChat}>
                  <label className={styles.srOnly} htmlFor="portal-question">Digite sua pergunta</label>
                  <input
                    id="portal-question"
                    value={input}
                    onChange={(event) => setInput(event.target.value)}
                    placeholder="Digite sua dúvida..."
                    disabled={sending || portalLoading || Boolean(portalError)}
                    autoComplete="off"
                  />
                  <button
                    type="submit"
                    aria-label="Enviar pergunta"
                    disabled={
                      sending ||
                      portalLoading ||
                      Boolean(portalError) ||
                      !input.trim()
                    }
                  >
                    {sending ? <Loader2 className={styles.spin} aria-hidden="true" /> : <Send aria-hidden="true" />}
                  </button>
                </form>
              </div>
            </section>
          )}

          {activeTab === "eventos" && (
            <section className={styles.panel} role="tabpanel" aria-labelledby="events-title">
              <div className={styles.pageIntro}>
                <p>Agenda</p>
                <h2 id="events-title">Próximos eventos</h2>
                <span>Atividades para aprender, conectar e participar.</span>
              </div>
              {eventsLoading && (
                <div className={styles.alert} role="status">Carregando eventos...</div>
              )}
              {eventsError && (
                <div className={styles.alert} role="alert">{eventsError}</div>
              )}
              {!eventsLoading && !eventsError && events.length === 0 && (
                <p className={styles.emptyState}>Nenhum evento programado no momento.</p>
              )}
              <div className={styles.eventList}>
                {events.map((event) => <EventCard event={event} key={event.id} />)}
              </div>
            </section>
          )}

          {activeTab === "locais" && (
            <section className={styles.panel} role="tabpanel" aria-labelledby="places-title">
              <div className={styles.pageIntro}>
                <p>Encontre seu caminho</p>
                <h2 id="places-title">Locais do campus</h2>
                <span>Pesquise os espaços cadastrados pela instituição.</span>
              </div>

              {locationsLoading && (
                <div className={styles.alert} role="status">Carregando locais...</div>
              )}
              {locationsError && (
                <div className={styles.alert} role="alert">{locationsError}</div>
              )}
              {!locationsLoading && !locationsError && locations.length === 0 && (
                <p className={styles.emptyState}>Nenhum local disponível no momento.</p>
              )}

              <div className={styles.locationToolbar}>
                <label className={styles.searchField}>
                  <Search aria-hidden="true" />
                  <span className={styles.srOnly}>Buscar local</span>
                  <input
                    value={locationSearch}
                    onChange={(event) => setLocationSearch(event.target.value)}
                    placeholder="Buscar bloco ou laboratório..."
                  />
                </label>
                <label>
                  <span className={styles.srOnly}>Ponto de origem</span>
                  <select
                    aria-label="Ponto de origem"
                    value={originId}
                    onChange={(event) => {
                      setOriginId(event.target.value);
                      setRoute(null);
                    }}
                  >
                    <option value="">Selecione a origem</option>
                    {locations.map((location) => (
                      <option key={location.id} value={location.id}>{location.name}</option>
                    ))}
                  </select>
                </label>
              </div>

              <div className={styles.campusMap} aria-label="Mapa esquemático do campus">
                <span className={styles.mapLabel}><Building2 aria-hidden="true" />Campus</span>
                <span className={styles.mapPathOne} aria-hidden="true" />
                <span className={styles.mapPathTwo} aria-hidden="true" />
                {originLocation && destinationLocation && route && (
                  <svg className={styles.routeLine} aria-hidden="true">
                    <line
                      x1={`${originLocation.x}%`}
                      y1={`${originLocation.y}%`}
                      x2={`${destinationLocation.x}%`}
                      y2={`${destinationLocation.y}%`}
                    />
                  </svg>
                )}
                {filteredLocations.map((location) => (
                  <button
                    type="button"
                    key={location.id}
                    className={`${styles.mapMarker} ${
                      destinationId === location.id ? styles.mapMarkerActive : ""
                    }`}
                    style={{ left: `${location.x}%`, top: `${location.y}%` }}
                    onClick={() => selectDestination(location)}
                    aria-label={`Selecionar ${location.name} como destino`}
                  >
                    <MapPin aria-hidden="true" /><span>{location.name}</span>
                  </button>
                ))}
              </div>

              <div className={styles.routeControls}>
                <p aria-live="polite">{locationStatus || "Toque em um marcador para escolher o destino."}</p>
                <button type="button" onClick={traceRoute} disabled={!originId || !destinationId}>
                  <Navigation aria-hidden="true" /> Traçar rota
                </button>
              </div>

              {route && (
                <div className={styles.routeSummary} role="status">
                  <Navigation aria-hidden="true" />
                  <div>
                    <strong>{route.originName} → {route.destination.name}</strong>
                    <span>Aproximadamente {route.distance} m · {route.minutes} min a pé</span>
                    <small>Estimativa temporária baseada no mapa esquemático.</small>
                  </div>
                </div>
              )}

              <div className={styles.locationList}>
                {filteredLocations.map((location) => (
                  <button type="button" key={location.id} onClick={() => selectDestination(location)}>
                    <span className={styles.locationPin}><MapPin aria-hidden="true" /></span>
                    <span>
                      <strong>{location.name}</strong>
                      <small>
                        {[location.category, location.building, location.floor]
                          .filter(Boolean)
                          .join(" · ")}
                      </small>
                    </span>
                    <ChevronRight aria-hidden="true" />
                  </button>
                ))}
                {filteredLocations.length === 0 && (
                  <p className={styles.emptyState}>Nenhum local encontrado para essa busca.</p>
                )}
              </div>
            </section>
          )}
        </main>
      </div>
    </div>
  );
}
