import { InstitutionPrivacy } from "../../../components/institution-privacy";

export default async function InstitutionPrivacyPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return <InstitutionPrivacy publicSlug={slug} />;
}
