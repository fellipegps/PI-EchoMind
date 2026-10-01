import { PublicPortal } from "../../components/public-portal";

type PublicPortalPageProps = {
  params: Promise<{ slug: string }>;
};

export default async function PublicPortalPage({ params }: PublicPortalPageProps) {
  const { slug } = await params;
  return <PublicPortal publicSlug={slug} />;
}
