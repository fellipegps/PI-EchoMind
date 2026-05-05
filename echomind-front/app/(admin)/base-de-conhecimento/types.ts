// Tipos locais do módulo base-de-conhecimento
// Faq e CompanyEvent são importados de @/lib/api

export interface EventFormState {
  title: string;
  event_date: Date | undefined;
  event_type: string;
  description: string;
}
