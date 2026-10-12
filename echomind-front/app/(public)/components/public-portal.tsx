"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import {
  Sparkles,
} from "lucide-react";

import { publicPortalApi, streamPublicChat } from "@/lib/api";
import type { PublicCampusLocation, PublicEvent, PublicFaq } from "@/lib/api";

import { PublicCampusNavigator } from "./public-campus-navigator";
import { PortalSectionHeading, PortalShell, type PortalTabId as TabId } from "./public-portal-shell";
import styles from "./public-portal.module.css";

import { ChatAuxiliary, PublicChat, type ChatMessage } from "./public-chat";
import { PublicEvents } from "./public-events";
import { Button } from "@/components/ui/button";
import { PublicSchematicMap } from "./public-schematic-map";
import { mapControlFocus } from "./public-map-controls";

const INITIAL_MESSAGE: ChatMessage = {
  id: 1,
  role: "assistant",
  content: "Olá! Sou o assistente acadêmico. Como posso ajudar você hoje?",
};

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
  const [geoAvailable, setGeoAvailable] = useState(false);
  const [showLegacyMap, setShowLegacyMap] = useState(false);
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
    if (!question || sending || portalLoading) return;
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
    <div>
      <PortalShell activeTab={activeTab} onTabChange={setActiveTab} companyName={companyName}
        auxiliary={<ChatAuxiliary faqs={faqs} events={events} eventsLoading={eventsLoading} eventsError={eventsError}
          disabled={sending || portalLoading || Boolean(portalError)} onQuestion={(question) => void sendQuestion(question)}
          onEvents={() => setActiveTab("eventos")} />}>
          {activeTab === "chat" && (
            <section className={styles.panel} aria-labelledby="chat-title">
              <PortalSectionHeading id="chat-title" eyebrow="Atendimento digital" title="Como podemos ajudar?" icon={<Sparkles className="size-5" />} />

              <PublicChat messages={messages} scrollRef={chatScroll} input={input} onInput={setInput}
                onSubmit={submitChat} onQuestion={(question) => void sendQuestion(question)} faqs={faqs}
                sending={sending} waitingForFirstToken={waitingForFirstToken}
                blocked={sending || portalLoading || Boolean(portalError)} portalLoading={portalLoading}
                portalError={portalError} chatError={chatError} />
            </section>
          )}

          {activeTab === "eventos" && (
            <section className={styles.panel} aria-labelledby="events-title">
              <PortalSectionHeading id="events-title" eyebrow="Agenda" title="Próximos eventos" description="Atividades para aprender, conectar e participar." />
              <PublicEvents events={events} loading={eventsLoading} error={eventsError} />
            </section>
          )}

          {activeTab === "locais" && (
            <section className={styles.panel} aria-labelledby="places-title">
              <PortalSectionHeading id="places-title" eyebrow="Encontre seu caminho" title="Locais do campus" description="Pesquise os espaços cadastrados pela instituição." />

              <div className="space-y-6">
                <PublicCampusNavigator publicSlug={normalizedSlug} onAvailabilityChange={setGeoAvailable} />
                {geoAvailable && <Button variant="outline" type="button" className={mapControlFocus}
                  onClick={() => setShowLegacyMap((visible) => !visible)} aria-expanded={showLegacyMap}>
                  {showLegacyMap ? "Ocultar mapa esquemático" : "Ver mapa esquemático"}
                </Button>}
                {(!geoAvailable || showLegacyMap) && <PublicSchematicMap
                  locations={locations} filteredLocations={filteredLocations} loading={locationsLoading} error={locationsError}
                  search={locationSearch} onSearch={setLocationSearch} originId={originId}
                  onOrigin={(value) => { setOriginId(value); setRoute(null); }} destinationId={destinationId}
                  onDestination={selectDestination} originLocation={originLocation} destinationLocation={destinationLocation}
                  route={route} status={locationStatus} onTrace={traceRoute} />}
              </div>
            </section>
          )}
      </PortalShell>
    </div>
  );
}
