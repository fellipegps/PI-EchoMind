import { notFound } from "next/navigation";
import { anapolisDestinations } from "../../../../../components/campus-guide/places";
import { PublicCampusDestination } from "../../../../../components/public-campus-destination";

export default async function CampusDestinationPage({ params }: {
  params: Promise<{ slug: string; id: string }>;
}) {
  const { slug, id } = await params;
  const destination = anapolisDestinations.find((item) => item.id === id);
  if (!destination) notFound();
  return <PublicCampusDestination publicSlug={slug} destination={destination} />;
}
