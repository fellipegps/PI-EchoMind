export interface Faq {
  id: string;
  question: string;
  answer: string;
  category: string;
  show_on_totem: boolean; // campo local — ainda não existe no backend
  created_at: string;
}

export interface CompanyEvent {
  id: string;
  title: string;
  event_date: string; // "yyyy-MM-dd"
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
