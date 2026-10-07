import { GeoCampusManager } from "./geo-campus-manager";

export default function CampusesPage() {
  return (
    <div className="mx-auto w-full max-w-7xl space-y-6 p-4 md:p-6">
      <header>
        <p className="text-sm font-medium text-primary">Navegação institucional</p>
        <h1 className="text-3xl font-bold tracking-tight">Mapa dos campi</h1>
        <p className="mt-2 max-w-3xl text-muted-foreground">
          Marque as entradas dos prédios e conecte os caminhos que podem ser percorridos. Os estudantes poderão consultar os espaços e seguir uma rota a partir da posição atual.
        </p>
      </header>
      <GeoCampusManager />
    </div>
  );
}
