import { MobilePortal } from "../../agente-publico/components/mobile-portal";

type PublicPortalPageProps = {
  params: Promise<{ slug: string }>;
};

export default async function PublicPortalPage({ params }: PublicPortalPageProps) {
  const { slug } = await params;
  return <MobilePortal publicSlug={slug} />;
}
