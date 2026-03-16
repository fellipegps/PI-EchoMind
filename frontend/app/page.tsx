import { redirect } from "next/navigation";

export default function RootPage() {
  // Esta função interrompe a renderização desta página e manda o usuário instantaneamente para a rota /dashboard
  redirect("/dashboard");

  // O retorno null é apenas uma boa prática, pois o redirect acontece antes de chegar aqui.
  return null;
}