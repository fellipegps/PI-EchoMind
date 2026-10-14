import { EventsManager } from "./events-manager";
import { PageContainer } from "@/components/page-container";
import { PageHeader } from "@/components/page-header";

export default function EventsPage() {
  return (
    <PageContainer variant="standard">
      <PageHeader title="Eventos" description="Cadastre os eventos exibidos no portal público da instituição." eyebrow="Portal institucional" />
      <EventsManager />
    </PageContainer>
  );
}
