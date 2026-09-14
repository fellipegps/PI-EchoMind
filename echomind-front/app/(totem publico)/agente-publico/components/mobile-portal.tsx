"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import {
  Bot,
  Building2,
  CalendarDays,
  ChevronRight,
  Clock3,
  Loader2,
  LocateFixed,
  MapPin,
  Megaphone,
  Navigation,
  Search,
  Send,
  Sparkles,
} from "lucide-react";

import { configApi, faqApi, streamChat } from "@/lib/api";
import type { Faq } from "@/lib/api";

import styles from "./mobile-portal.module.css";

type TabId = "chat" | "avisos" | "eventos" | "locais";
type Coordinates = readonly [number, number];

type ChatMessage = {
  id: number;
  role: "assistant" | "user";
  content: string;
};

type CampusLocation = {
  id: string;
  name: string;
  type: string;
  details: string;
  coordinates: Coordinates;
  position: { x: number; y: number };
};

const NAV_ITEMS = [
  { id: "chat", label: "Chat", icon: Bot },
  { id: "avisos", label: "Avisos", icon: Megaphone },
  { id: "eventos", label: "Eventos", icon: CalendarDays },
  { id: "locais", label: "Locais", icon: MapPin },
] as const;

const ANNOUNCEMENTS = [
  {
    id: "rematricula",
    category: "Acadêmico",
    title: "Prazo para rematrícula",
    date: "Publicado em 10 de julho",
    description:
      "O período de rematrícula para o próximo semestre estará aberto até 30 de julho.",
  },
  {
    id: "biblioteca",
    category: "Atendimento",
    title: "Horário ampliado da biblioteca",
    date: "Publicado em 8 de julho",
    description:
      "A Biblioteca Central funciona de segunda a sexta, das 7h30 às 22h.",
  },
];

const EVENTS = [
  {
    id: "semana-tecnologia",
    day: "15",
    month: "AGO",
    title: "Semana da Tecnologia",
    period: "15 a 19 de agosto",
    place: "Auditório do Bloco F",
    description: "Palestras, oficinas e encontros com profissionais de tecnologia.",
  },
  {
    id: "boas-vindas",
    day: "22",
    month: "AGO",
    title: "Encontro de boas-vindas",
    period: "22 de agosto, às 18h30",
    place: "Praça central",
    description: "Integração para estudantes, professores e comunidade acadêmica.",
  },
];

const CAMPUS_LOCATIONS: CampusLocation[] = [
  {
    id: "portaria-principal",
    name: "Portaria Principal",
    type: "Acesso",
    details: "Entrada principal de estudantes e visitantes.",
    coordinates: [-16.2945, -48.9452],
    position: { x: 18, y: 74 },
  },
  {
    id: "bloco-f",
    name: "Bloco F",
    type: "Computação e Engenharias",
    details: "Laboratórios de redes e desenvolvimento de software.",
    coordinates: [-16.2932, -48.9438],
    position: { x: 70, y: 30 },
  },
  {
    id: "bloco-a",
    name: "Bloco A",
    type: "Atendimento",
    details: "Secretaria Geral, Financeiro e Atendimento ao Aluno.",
    coordinates: [-16.2941, -48.9441],
    position: { x: 54, y: 70 },
  },
  {
    id: "biblioteca",
    name: "Biblioteca Central",
    type: "Estudo",
    details: "Acervo, salas de estudo individual e em grupo.",
    coordinates: [-16.2938, -48.9445],
    position: { x: 38, y: 42 },
  },
  {
    id: "bloco-b",
    name: "Bloco B",
    type: "Saúde e Odontologia",
    details: "Clínicas de Odontologia e laboratórios de Anatomia.",
    coordinates: [-16.2929, -48.9448],
    position: { x: 28, y: 18 },
  },
];

const INITIAL_MESSAGE: ChatMessage = {
  id: 1,
  role: "assistant",
  content: "Olá! Sou o assistente acadêmico. Como posso ajudar você hoje?",
};

function tenantFromUrl() {
  if (typeof window === "undefined") return "";
  return new URLSearchParams(window.location.search).get("tenant")?.trim() ?? "";
}

function distanceInMeters(from: Coordinates, to: Coordinates) {
  const toRadians = (value: number) => (value * Math.PI) / 180;
  const earthRadius = 6_371_000;
  const latitudeDelta = toRadians(to[0] - from[0]);
  const longitudeDelta = toRadians(to[1] - from[1]);
  const fromLatitude = toRadians(from[0]);
  const toLatitude = toRadians(to[0]);
  const haversine =
    Math.sin(latitudeDelta / 2) ** 2 +
    Math.cos(fromLatitude) *
      Math.cos(toLatitude) *
      Math.sin(longitudeDelta / 2) ** 2;
  return earthRadius * 2 * Math.atan2(Math.sqrt(haversine), Math.sqrt(1 - haversine));
}

export function MobilePortal() {
  const [activeTab, setActiveTab] = useState<TabId>("chat");
  const [tenantId] = useState(tenantFromUrl);
  const [companyName, setCompanyName] = useState("Portal Acadêmico");
  const [faqs, setFaqs] = useState<Faq[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([INITIAL_MESSAGE]);
  const [input, setInput] = useState("");
  const [chatError, setChatError] = useState("");
  const [sending, setSending] = useState(false);
  const [waitingForFirstToken, setWaitingForFirstToken] = useState(false);
  const [locationSearch, setLocationSearch] = useState("");
  const [originId, setOriginId] = useState("");
  const [destinationId, setDestinationId] = useState("");
  const [gpsCoordinates, setGpsCoordinates] = useState<Coordinates | null>(null);
  const [locationStatus, setLocationStatus] = useState("");
  const [route, setRoute] = useState<{
    originName: string;
    destination: CampusLocation;
    distance: number;
    minutes: number;
  } | null>(null);
  const nextMessageId = useRef(2);
  const firstToken = useRef(true);
  const chatScroll = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!tenantId) return;
    faqApi
      .listTotem(tenantId)
      .then((items) => setFaqs(items.slice(0, 4)))
      .catch(() => setFaqs([]));
    configApi
      .getPublic(tenantId)
      .then((config) => setCompanyName(config.company_name || "Portal Acadêmico"))
      .catch(() => setCompanyName("Portal Acadêmico"));
  }, [tenantId]);

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
    if (!tenantId) {
      setChatError("Link inválido. Solicite à instituição o endereço correto do portal.");
      return;
    }

    setInput("");
    setChatError("");
    setSending(true);
    setWaitingForFirstToken(true);
    firstToken.current = true;
    appendMessage("user", question);

    await streamChat(
      question,
      tenantId,
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

  const filteredLocations = CAMPUS_LOCATIONS.filter((location) => {
    const normalizedSearch = locationSearch.trim().toLocaleLowerCase("pt-BR");
    return (
      !normalizedSearch ||
      `${location.name} ${location.type} ${location.details}`
        .toLocaleLowerCase("pt-BR")
        .includes(normalizedSearch)
    );
  });

  const selectDestination = (location: CampusLocation) => {
    setDestinationId(location.id);
    setRoute(null);
    setLocationStatus(`${location.name} selecionado como destino.`);
  };

  const useCurrentLocation = () => {
    if (!navigator.geolocation) {
      setLocationStatus("Geolocalização não disponível neste navegador.");
      return;
    }
    setLocationStatus("Obtendo sua localização...");
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        setGpsCoordinates([coords.latitude, coords.longitude]);
        setOriginId("gps");
        setRoute(null);
        setLocationStatus("Localização atual definida como origem.");
      },
      () => setLocationStatus("Não foi possível acessar o GPS. Verifique a permissão do navegador."),
      { enableHighAccuracy: true, timeout: 10_000 }
    );
  };

  const traceRoute = () => {
    const destination = CAMPUS_LOCATIONS.find((location) => location.id === destinationId);
    const storedOrigin = CAMPUS_LOCATIONS.find((location) => location.id === originId);
    const originCoordinates = originId === "gps" ? gpsCoordinates : storedOrigin?.coordinates;
    const originName = originId === "gps" ? "Sua localização" : storedOrigin?.name;

    if (!destination || !originCoordinates || !originName) {
      setLocationStatus("Selecione a origem e o destino para calcular o trajeto.");
      return;
    }
    const distance = Math.max(25, Math.round(distanceInMeters(originCoordinates, destination.coordinates) * 1.2));
    setRoute({
      originName,
      destination,
      distance,
      minutes: Math.max(1, Math.ceil(distance / 75)),
    });
    setLocationStatus("Trajeto aproximado calculado.");
  };

  const originLocation = CAMPUS_LOCATIONS.find((location) => location.id === originId);
  const destinationLocation = CAMPUS_LOCATIONS.find(
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

              {!tenantId && (
                <div className={styles.alert} role="alert">
                  Link inválido. Solicite à instituição o endereço correto do portal.
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
                    disabled={sending || !tenantId}
                    autoComplete="off"
                  />
                  <button
                    type="submit"
                    aria-label="Enviar pergunta"
                    disabled={sending || !input.trim() || !tenantId}
                  >
                    {sending ? <Loader2 className={styles.spin} aria-hidden="true" /> : <Send aria-hidden="true" />}
                  </button>
                </form>
              </div>
            </section>
          )}

          {activeTab === "avisos" && (
            <section className={styles.panel} role="tabpanel" aria-labelledby="notices-title">
              <div className={styles.pageIntro}>
                <p>Fique por dentro</p>
                <h2 id="notices-title">Avisos gerais</h2>
                <span>Informações importantes para sua rotina acadêmica.</span>
              </div>
              <div className={styles.cardGrid}>
                {ANNOUNCEMENTS.map((announcement) => (
                  <article className={styles.infoCard} key={announcement.id}>
                    <span className={styles.cardBadge}>{announcement.category}</span>
                    <h3>{announcement.title}</h3>
                    <p className={styles.meta}><Clock3 aria-hidden="true" />{announcement.date}</p>
                    <p>{announcement.description}</p>
                  </article>
                ))}
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
              <div className={styles.cardGrid}>
                {EVENTS.map((event) => (
                  <article className={styles.eventCard} key={event.id}>
                    <div className={styles.eventDate}><strong>{event.day}</strong><span>{event.month}</span></div>
                    <div>
                      <h3>{event.title}</h3>
                      <p className={styles.meta}><Clock3 aria-hidden="true" />{event.period}</p>
                      <p className={styles.meta}><MapPin aria-hidden="true" />{event.place}</p>
                      <p>{event.description}</p>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          )}

          {activeTab === "locais" && (
            <section className={styles.panel} role="tabpanel" aria-labelledby="places-title">
              <div className={styles.pageIntro}>
                <p>Encontre seu caminho</p>
                <h2 id="places-title">Locais do campus</h2>
                <span>Pesquise um bloco e obtenha uma estimativa de caminhada.</span>
              </div>

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
                    {CAMPUS_LOCATIONS.map((location) => (
                      <option key={location.id} value={location.id}>{location.name}</option>
                    ))}
                    {gpsCoordinates && <option value="gps">Minha localização</option>}
                  </select>
                </label>
                <button className={styles.gpsButton} type="button" onClick={useCurrentLocation}>
                  <LocateFixed aria-hidden="true" /> Usar GPS
                </button>
              </div>

              <div className={styles.campusMap} aria-label="Mapa esquemático do campus">
                <span className={styles.mapLabel}><Building2 aria-hidden="true" />Campus</span>
                <span className={styles.mapPathOne} aria-hidden="true" />
                <span className={styles.mapPathTwo} aria-hidden="true" />
                {originLocation && destinationLocation && route && (
                  <svg className={styles.routeLine} aria-hidden="true">
                    <line
                      x1={`${originLocation.position.x}%`}
                      y1={`${originLocation.position.y}%`}
                      x2={`${destinationLocation.position.x}%`}
                      y2={`${destinationLocation.position.y}%`}
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
                    style={{ left: `${location.position.x}%`, top: `${location.position.y}%` }}
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
                    <small>Estimativa em linha reta ajustada para caminhada dentro do campus.</small>
                  </div>
                </div>
              )}

              <div className={styles.locationList}>
                {filteredLocations.map((location) => (
                  <button type="button" key={location.id} onClick={() => selectDestination(location)}>
                    <span className={styles.locationPin}><MapPin aria-hidden="true" /></span>
                    <span><strong>{location.name}</strong><small>{location.type} · {location.details}</small></span>
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
