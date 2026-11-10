import { expect, test } from "@playwright/test";

test("o chat público mostra o erro e responde na nova tentativa", async ({ page }, testInfo) => {
  await page.goto("/p/ds04-fixture");
  const question = page.getByRole("textbox", { name: "Digite sua pergunta" });
  const send = page.getByRole("button", { name: "Enviar pergunta" });
  const errorMessage = page.getByText("Não foi possível obter uma resposta agora. Tente novamente em instantes.");

  await expect(question).toBeEnabled();
  await question.fill("falha de teste");
  await send.click();
  await expect(errorMessage).toBeVisible();
  await expect(page.getByText("detalhe interno da fixture")).toHaveCount(0);
  await errorMessage.scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath("falha-tratada.png") });

  await question.fill("Como acessar a biblioteca?");
  await send.click();
  const answer = page.getByText("Resposta local preservada após a navegação e a troca de largura.");
  await expect(answer).toBeVisible({ timeout: 15_000 });
  await expect(question).toBeEnabled();
  await expect(errorMessage).toHaveCount(0);
  await answer.scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath("resposta-concluida.png") });
});
