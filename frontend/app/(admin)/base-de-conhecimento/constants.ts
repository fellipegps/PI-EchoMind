import { Faq, CompanyEvent } from "./types";

export const MOCK_FAQS: Faq[] = [
  { id: "1", question: "Como resetar minha senha?", answer: "Vá em configurações e clique em 'esqueci senha'.", show_on_totem: true, created_at: new Date().toISOString() },
  { id: "2", question: "Qual o horário de suporte?", answer: "Atendimento de segunda a sexta, das 09h às 18h.", show_on_totem: true, created_at: new Date().toISOString() },
];

export const MOCK_EVENTS: CompanyEvent[] = [
  { id: "1", title: "Confraternização de Ano Novo", event_date: "2024-12-31", event_type: "evento_social", description: "Festa no escritório principal com toda a equipe.", created_at: new Date().toISOString() },
];

export const EVENT_TYPES = [
  { value: "palestra", label: "Palestra" },
  { value: "feriado", label: "Feriado" },
  { value: "promocao", label: "Promoção" },
  { value: "workshop", label: "Workshop" },
  { value: "reuniao", label: "Reunião" },
  { value: "evento_social", label: "Evento Social" },
  { value: "outro", label: "Outro" },
];