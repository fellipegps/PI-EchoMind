import { GeoCampusManager } from "./geo-campus-manager";
import { PageContainer } from "@/components/page-container";
import { PageHeader } from "@/components/page-header";

export default function CampusesPage() {
  return (
    <PageContainer variant="wide">
      <PageHeader title="Mapa dos campi" description="Cadastre blocos, espaços internos e pontos de referência com fotos. Cada local tem uma ficha pública e um QR Code para imprimir e afixar no campus." eyebrow="Guia visual institucional" />
      <GeoCampusManager />
    </PageContainer>
  );
}
