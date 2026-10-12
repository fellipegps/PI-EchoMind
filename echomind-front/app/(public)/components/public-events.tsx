import { useState } from "react";
import { CalendarDays, ExternalLink, GraduationCap, MapPin } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import type { PublicEvent } from "@/lib/api";

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

export function EventCard({ event }: { event: PublicEvent }) {
  const [imageFailed, setImageFailed] = useState(false);
  const period = formatEventPeriod(event.event_date, event.event_end_date);
  const imageUrl = safeEventUrl(event.image_url, ["https:"]);
  const linkUrl = safeEventUrl(event.link_url, ["http:", "https:"]);

  return (
    <article aria-label={event.title} className="min-w-0">
      <Card className="h-full min-w-0 gap-0 overflow-hidden border-border py-0">
        {imageUrl && !imageFailed ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={imageUrl} alt={event.title} loading="lazy" referrerPolicy="no-referrer"
            onError={() => setImageFailed(true)} className="aspect-video w-full object-cover" />
        ) : null}
        <CardContent className="flex min-w-0 flex-1 flex-col gap-4 p-4 [overflow-wrap:anywhere] sm:p-6">
          <h3 className="text-xl leading-7 font-semibold tracking-tight">{event.title}</h3>
          <dl className="space-y-3 text-sm leading-5">
            {[
              { label: "Data", value: period, icon: CalendarDays },
              { label: "Curso", value: event.course, icon: GraduationCap },
              { label: "Local", value: event.location, icon: MapPin },
            ].map(({ label, value, icon: Icon }) => (
              <div key={label} className="flex min-w-0 items-start gap-3">
                <Icon aria-hidden="true" className="mt-1 size-4 shrink-0 text-primary" />
                <div className="min-w-0 space-y-1">
                  <dt className="font-medium text-muted-foreground">{label}</dt>
                  <dd>{value}</dd>
                </div>
              </div>
            ))}
          </dl>
          {event.description ? <p className="whitespace-pre-wrap text-base leading-6">{event.description}</p> : null}
          {linkUrl ? (
            <a href={linkUrl} target="_blank" rel="noopener noreferrer"
              className="mt-auto scroll-mt-4 scroll-mb-[calc(96px+env(safe-area-inset-bottom))] lg:scroll-mb-4 flex min-h-11 min-w-0 items-center gap-2 rounded-sm py-2 text-sm leading-5 text-primary underline underline-offset-4 outline-none hover:text-primary-hover focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-card">
              <span className="min-w-0 flex-1">{linkUrl}</span><ExternalLink aria-hidden="true" className="size-4 shrink-0" />
            </a>
          ) : null}
        </CardContent>
      </Card>
    </article>
  );
}

export function EventSummary({ event }: { event: PublicEvent }) {
  return (
    <li className="flex min-w-0 items-start gap-3 border-t border-border pt-4">
      <CalendarDays aria-hidden="true" className="mt-1 size-5 shrink-0 text-primary" />
      <div className="min-w-0 space-y-1 [overflow-wrap:anywhere]">
        <p className="text-sm leading-5 font-medium">{event.title}</p>
        <p className="text-xs leading-4 text-muted-foreground">{formatEventPeriod(event.event_date, event.event_end_date)}</p>
        <p className="text-xs leading-4 text-muted-foreground">{event.location}</p>
      </div>
    </li>
  );
}

export function PublicEvents({ events, loading, error }: {
  events: PublicEvent[];
  loading: boolean;
  error: string;
}) {
  if (loading) return (
    <div role="status" className="space-y-4 text-foreground">
      <p className="text-sm leading-5 text-muted-foreground">Carregando eventos...</p>
      <Card aria-hidden="true" className="min-w-0 gap-4 border-border p-4 sm:p-6">
        <Skeleton className="h-40 w-full motion-reduce:animate-none" />
        <Skeleton className="h-6 w-3/4 motion-reduce:animate-none" />
        <Skeleton className="h-4 w-full motion-reduce:animate-none" />
      </Card>
    </div>
  );
  if (error) return <p role="alert" className="rounded-xl border border-destructive bg-card p-4 text-sm leading-5 text-destructive [overflow-wrap:anywhere]">{error}</p>;
  if (events.length === 0) return <Card className="items-center gap-3 border-border p-6 text-center">
    <CalendarDays aria-hidden="true" className="size-8 text-muted-foreground" />
    <p className="text-base leading-6 text-muted-foreground">Nenhum evento programado no momento.</p>
  </Card>;
  return <div className="grid min-w-0 gap-6 md:grid-cols-2 xl:grid-cols-3">{events.map((event) => <EventCard event={event} key={event.id} />)}</div>;
}
