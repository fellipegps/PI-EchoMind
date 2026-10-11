import { notFound } from "next/navigation";
import { DesignSystemSample } from "./sample";

export const metadata = { title: "EchoMind · Revisão DS-01", robots: { index: false, follow: false } };

export default function DesignSystemReviewPage() {
  if (process.env.NODE_ENV !== "development") notFound();
  return <DesignSystemSample />;
}
