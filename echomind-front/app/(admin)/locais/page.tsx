import { CampusLocationsManager } from "./campus-locations-manager";
import { PageContainer } from "@/components/page-container";
import { PageHeader } from "@/components/page-header";

export default function CampusLocationsPage() {
  return (
    <PageContainer variant="standard">
      <PageHeader title="Locais do Campus" description="Cadastre os pontos que serão exibidos no mapa público da instituição." eyebrow="Mapa institucional" />
      <CampusLocationsManager />
    </PageContainer>
  );
}
