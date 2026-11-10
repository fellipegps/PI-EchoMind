import { notFound } from "next/navigation";
import { PublicCampusPlace } from "../../../../../components/public-campus-place";

export default async function CampusPlacePage({ params }: {
  params: Promise<{ slug: string; type: string; code: string }>;
}) {
  const { slug, type, code } = await params;
  if (type !== "building" && type !== "space" && type !== "landmark") notFound();
  return <PublicCampusPlace publicSlug={slug} type={type} publicCode={code} />;
}
