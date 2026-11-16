import { GeoCampusManager } from "./geo-campus-manager";
import { PageContainer } from "@/components/page-container";
import { PageHeader } from "@/components/page-header";

export default function CampusesPage() {
  return (
    <PageContainer variant="wide">
      <PageHeader title="Mapa dos campi" description="Gerencie as fichas dos blocos, os locais internos e os pontos de referência da maquete e do mapa de satélite." eyebrow="Guia visual institucional" />
      <GeoCampusManager />
    </PageContainer>
  );
}
