import { EventsManager } from "./events-manager";

export default function EventsPage() {
  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 p-6">
      <div>
        <p className="text-sm font-medium text-primary">Portal institucional</p>
        <h1 className="text-3xl font-bold tracking-tight">Eventos</h1>
        <p className="mt-2 text-muted-foreground">
          Cadastre os eventos exibidos no portal público da instituição.
        </p>
      </div>
      <EventsManager />
    </div>
  );
}
