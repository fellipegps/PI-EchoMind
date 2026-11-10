import { PublicPortal } from "../../components/public-portal";

type PublicPortalPageProps = {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ tab?: string | string[] }>;
};

export default async function PublicPortalPage({ params, searchParams }: PublicPortalPageProps) {
  const [{ slug }, { tab }] = await Promise.all([params, searchParams]);
  return <PublicPortal publicSlug={slug} initialTab={tab === "locais" ? "locais" : "chat"} />;
}
