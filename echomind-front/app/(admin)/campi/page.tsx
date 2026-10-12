import { GeoCampusManager } from "./geo-campus-manager";
import { PageContainer } from "@/components/page-container";
import { PageHeader } from "@/components/page-header";

export default function CampusesPage() {
  return (
    <PageContainer variant="wide">
      <PageHeader title="Mapa dos campi" description="Marque as entradas dos prédios e conecte os caminhos que podem ser percorridos. Os estudantes poderão consultar os espaços e seguir uma rota a partir da posição atual." eyebrow="Navegação institucional" />
      <GeoCampusManager />
    </PageContainer>
  );
}
