import { CampusLocationsManager } from "./campus-locations-manager";

export default function CampusLocationsPage() {
  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 p-6">
      <div>
        <p className="text-sm font-medium text-primary">Mapa institucional</p>
        <h1 className="text-3xl font-bold tracking-tight">Locais do Campus</h1>
        <p className="mt-2 text-muted-foreground">
          Cadastre os pontos que serão exibidos no mapa público da instituição.
        </p>
      </div>
      <CampusLocationsManager />
    </div>
  );
}
