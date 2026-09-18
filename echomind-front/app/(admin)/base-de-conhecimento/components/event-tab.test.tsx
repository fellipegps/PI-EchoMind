import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const hookMocks = vi.hoisted(() => ({
  saveEvent: vi.fn(),
  deleteEvent: vi.fn(),
}));

vi.mock("../hooks/use-events", () => ({
  useEvents: () => ({
    events: [
      {
        id: "event-1",
        title: "Semana Acadêmica",
        event_date: "2099-08-15",
        event_type: "palestra",
        description: "Programação acadêmica.",
        location: "Auditório A",
        published: false,
        created_at: "2099-01-01T10:00:00Z",
      },
    ],
    loading: false,
    saving: false,
    saveEvent: hookMocks.saveEvent,
    deleteEvent: hookMocks.deleteEvent,
  }),
}));

import { EventTab } from "./event-tab";

describe("EventTab", () => {
  beforeEach(() => {
    hookMocks.saveEvent.mockReset();
    hookMocks.deleteEvent.mockReset();
    hookMocks.saveEvent.mockResolvedValue(true);
  });

  it("edita local e publicação antes de disponibilizar o evento no portal", async () => {
    const user = userEvent.setup();
    render(<EventTab />);

    expect(screen.getByText("Rascunho")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Editar Semana Acadêmica" }));

    const location = screen.getByLabelText("Local");
    await user.clear(location);
    await user.type(location, "Auditório Central");
    await user.click(screen.getByRole("switch", { name: "Publicar no portal" }));
    await user.click(screen.getByRole("button", { name: "Salvar" }));

    expect(hookMocks.saveEvent).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Semana Acadêmica",
        location: "Auditório Central",
        published: true,
      }),
      "event-1"
    );
  });
});
