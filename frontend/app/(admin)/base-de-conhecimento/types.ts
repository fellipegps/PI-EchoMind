export interface Faq {
  id: string;
  question: string;
  answer: string;
  show_on_totem: boolean;
  created_at: string;
}

export interface CompanyEvent {
  id: string;
  title: string;
  event_date: string;
  event_type: string;
  description: string | null;
  created_at: string;
}

export interface EventFormState {
  title: string;
  event_date: Date | undefined;
  event_type: string;
  description: string;
}