import { notFound } from "next/navigation";
import { MapVerification } from "@/test/fixtures/map-verification";
export const metadata = { title: "EchoMind · Simulação DS-06", robots: { index: false, follow: false } };
export default function MapVerificationPage() {
  if (process.env.NODE_ENV !== "development" || process.env.NEXT_PUBLIC_API_URL !== "http://127.0.0.1:4109") notFound();
  return <MapVerification />;
}
