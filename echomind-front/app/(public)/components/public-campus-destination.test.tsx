import { render, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import type { PublicGeoCampus } from "@/lib/geocampus-api";
import { anapolisDestinations } from "./campus-guide/places";
import { PublicCampusDestination } from "./public-campus-destination";

const destination = anapolisDestinations.find((item) => item.id === "bloco-a")!;
const map: PublicGeoCampus = { campuses: [], buildings: [], landmarks: [], spaces: [] };

const mocks = vi.hoisted(() => ({ getInstitution: vi.fn(), publicMap: vi.fn() }));
vi.mock("@/lib/api", () => ({ publicPortalApi: { getInstitution: mocks.getInstitution } }));
vi.mock("@/lib/geocampus-api", async (original) => ({
  ...await original<typeof import("@/lib/geocampus-api")>(),
  geoCampusApi: { publicMap: mocks.publicMap },
}));

beforeEach(() => {
  vi.clearAllMocks();
  mocks.publicMap.mockResolvedValue(map);
});

it("abre a ficha diretamente e mostra laboratórios e acesso sem cadastro no banco", async () => {
  mocks.getInstitution.mockResolvedValue({ company_name: "UniEVANGÉLICA" });

  render(<PublicCampusDestination publicSlug="unievangelica" destination={destination} />);

  expect(await screen.findByRole("heading", { name: "Bloco A" })).toBeInTheDocument();
  expect(screen.getByText(/Laboratório 12/)).toBeVisible();
  expect(screen.getByRole("heading", { name: "Referência de acesso" })).toBeVisible();
  expect(screen.getByRole("link", { name: /Voltar aos locais/ })).toHaveAttribute("href", "/p/unievangelica?tab=locais");
});

it("não disponibiliza a ficha da maquete em outro portal", async () => {
  mocks.getInstitution.mockResolvedValue({ company_name: "Instituição de teste" });

  render(<PublicCampusDestination publicSlug="outra" destination={destination} />);

  expect(await screen.findByRole("alert")).toHaveTextContent("indisponível neste portal");
  expect(screen.queryByRole("heading", { name: "Bloco A" })).not.toBeInTheDocument();
});
