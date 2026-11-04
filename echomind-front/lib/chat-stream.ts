export type PublicChatCompletion = { unanswered_token?: string | null };

/** Text remains compatible with older APIs; SSE adds a verified completion. */
export async function readChatStream(
  response: Response, onToken: (token: string) => void, events: boolean,
): Promise<PublicChatCompletion> {
  if (!response.body) throw new Error("Resposta vazia.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  const structured = events && response.headers.get("Content-Type")?.includes("text/event-stream");
  let buffer = "";
  let receivedAny = false;
  let completion: PublicChatCompletion | undefined;
  let ended = false;
  const emitText = (text: string) => {
    if (text) { receivedAny = true; onToken(text); }
  };
  const frame = (value: string) => {
    const lines = value.split("\n");
    const event = lines.find(line => line.startsWith("event: "))?.slice(7);
    const payload = lines.filter(line => line.startsWith("data: ")).map(line => line.slice(6)).join("\n");
    const data = JSON.parse(payload);
    if (completion) throw new Error("Resposta inválida.");
    if (event === "token" && typeof data.text === "string") emitText(data.text);
    else if (event === "done" && (data.unanswered_token === null || (typeof data.unanswered_token === "string" && /^[A-Za-z0-9_-]{43}$/.test(data.unanswered_token)))) {
      completion = { unanswered_token: data.unanswered_token };
    } else throw new Error("Não foi possível concluir a resposta.");
  };
  try {
    while (true) {
      const { done, value } = await reader.read();
      const text = decoder.decode(value, { stream: !done });
      if (structured) {
        buffer += text;
        let boundary: number;
        while ((boundary = buffer.indexOf("\n\n")) !== -1) {
          frame(buffer.slice(0, boundary));
          buffer = buffer.slice(boundary + 2);
        }
        if (buffer.length > 65536) throw new Error("Resposta inválida.");
      } else emitText(text);
      if (done) { ended = true; break; }
    }
    if (!receivedAny || (structured && (!completion || buffer.trim()))) throw new Error("Resposta incompleta.");
    return completion ?? {};
  } finally {
    if (!ended) await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
