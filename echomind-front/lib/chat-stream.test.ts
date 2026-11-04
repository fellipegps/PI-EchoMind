import { expect, it, vi } from "vitest";
import { readChatStream } from "./chat-stream";

const token = "a".repeat(43);
const event = (name: string, data: unknown) => `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`;
const text = event("token", { text: "Não há informação.\n" }) + event("token", { text: "Olá!" }) + event("done", { unanswered_token: token });

function response(chunks: Uint8Array[], structured = true) {
  return new Response(new ReadableStream({
    start(controller) { for (const chunk of chunks) controller.enqueue(chunk); controller.close(); },
  }), { headers: { "Content-Type": structured ? "text/event-stream; charset=utf-8" : "text/plain" } });
}

it("recompõe frames e UTF-8 em qualquer fronteira entre pacotes", async () => {
  const bytes = new TextEncoder().encode(text);
  for (let split = 1; split < bytes.length; split++) {
    const parts: string[] = [];
    expect(await readChatStream(response([bytes.slice(0, split), bytes.slice(split)]), part => parts.push(part), true)).toEqual({ unanswered_token: token });
    expect(parts.join("")).toBe("Não há informação.\nOlá!");
  }
});

it.each([
  event("token", { text: "Parcial" }),
  event("token", { text: "Parcial" }) + event("error", { message: "Falha" }),
  event("token", { text: "Parcial" }) + event("done", { unanswered_token: "inválido" }),
  event("done", { unanswered_token: token }),
  event("token", { text: "Parcial" }) + event("done", { unanswered_token: token }).trim(),
  text + event("token", { text: "Depois do fim" }),
  "event: token\ndata: not-json\n\n",
])("não aceita conclusão incompleta ou inválida: %s", async stream => {
  await expect(readChatStream(response([new TextEncoder().encode(stream)]), vi.fn(), true)).rejects.toThrow();
});

it("falha se a conexão cair mesmo após receber uma resposta parcial", async () => {
  let read = 0;
  const res = new Response(new ReadableStream({
    pull(controller) {
      if (!read++) controller.enqueue(new TextEncoder().encode(event("token", { text: "Parcial" })));
      else controller.error(new Error("Desconectado"));
    },
  }), { headers: { "Content-Type": "text/event-stream" } });
  await expect(readChatStream(res, vi.fn(), true)).rejects.toThrow();
});

it("mantém compatibilidade com API de texto e recusa resposta vazia", async () => {
  const onToken = vi.fn();
  expect(await readChatStream(response([new TextEncoder().encode("Resposta pública")], false), onToken, true)).toEqual({});
  expect(onToken).toHaveBeenCalledWith("Resposta pública");
  await expect(readChatStream(response([], false), vi.fn(), true)).rejects.toThrow();
});
