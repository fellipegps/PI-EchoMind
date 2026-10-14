import { notFound } from "next/navigation";
import { CampusVerification } from "@/test/fixtures/campus-verification";
export const metadata = { title: "EchoMind · Simulação DS-14", robots: { index: false, follow: false } };
export default function CampusVerificationPage() {
  if (process.env.NODE_ENV !== "development" || process.env.NEXT_PUBLIC_API_URL !== "http://127.0.0.1:4181") notFound();
  return <CampusVerification />;
}
