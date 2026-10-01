import type { DateRange } from "react-day-picker";

export interface EventFormState {
  title: string;
  period: DateRange | undefined;
  event_type: string;
  course: string;
  description: string;
  location: string;
  image_url: string;
  link_url: string;
}
