"""Publica os dados de um campus a partir de um manifesto da equipe EchoMind."""

import argparse
import json
from pathlib import Path

from pydantic import Field
from sqlalchemy.orm import Session

from app import campus_map_repository as geo
from app.campus_map_schemas import BuildingCreate, CampusCreate, GeoInput
from app.campus_photo import MAX_PHOTO_BYTES, normalize_photo
from app.database import Config, engine

ASSETS = Path(__file__).resolve().parents[2] / "echomind-front" / "public" / "campus-guide"


class PhotoFile(GeoInput):
    file: Path
    caption: str | None = Field(default=None, max_length=300)


class ModelBuilding(BuildingCreate):
    id: str | None = None
    photos: list[PhotoFile] = Field(default_factory=list)
    replace_photos: bool = False


class CampusManifest(CampusCreate):
    buildings: list[ModelBuilding] = Field(default_factory=list)


def check_assets(model_key: str, assets: Path) -> dict[str, dict]:
    root = assets if model_key == "anapolis" else assets / model_key
    data = json.loads((root / "destinations.json").read_text(encoding="utf-8"))
    buildings = json.loads((root / "buildings.geojson").read_text(encoding="utf-8"))
    context = json.loads((root / "context.geojson").read_text(encoding="utf-8"))
    if buildings["type"] != "FeatureCollection" or context["type"] != "FeatureCollection":
        raise ValueError("Use FeatureCollection nos arquivos GeoJSON.")
    destinations = {item["id"]: item for item in data["destinations"]}
    features = [feature for feature in buildings["features"] if feature["properties"]["kind"] == "destination"]
    if (not destinations or destinations.keys() != {feature["id"] for feature in features}
            or len(destinations) != len(data["destinations"]) or len(destinations) != len(features)):
        raise ValueError("Cada destino da maquete deve corresponder a um contorno único em buildings.geojson.")
    return destinations


def include_model_buildings(manifest: CampusManifest, destinations: dict[str, dict]) -> None:
    configured = {building.model_destination_id for building in manifest.buildings}
    for identifier, destination in destinations.items():
        if identifier in configured:
            continue
        entry = destination["entry"].get("coordinates")
        lng, lat = entry or destination["labelCoordinates"]
        manifest.buildings.append(ModelBuilding(
            name=destination["name"], category="bloco", model_destination_id=identifier,
            entrance_lat=lat, entrance_lng=lng, description=destination["entry"].get("description"),
        ))


def publish_campus(db: Session, slug: str, manifest: CampusManifest, photo_root: Path, campus_id: str | None) -> str:
    config = db.query(Config).filter_by(public_slug=slug).with_for_update().one_or_none()
    if config is None:
        raise ValueError("Portal não encontrado. Confira o slug da instituição.")
    tenant = config.tenant_id
    campus_data = manifest.model_dump(exclude={"buildings"})
    if campus_id is None:
        campus_id = next(
            (row.id for row in geo.list_campuses(db, tenant) if row.name.casefold() == manifest.name.casefold()),
            None,
        )
    campus = (geo.update_campus(db, tenant, campus_id, campus_data) if campus_id
              else geo.create_campus(db, tenant, campus_data))

    existing = geo.list_buildings(db, tenant, campus.id)
    by_destination = {row.model_destination_id: row.id for row in existing if row.model_destination_id}
    by_name = {row.name.casefold(): row.id for row in existing}
    for block in manifest.buildings:
        data = block.model_dump(exclude={"id", "photos", "replace_photos"})
        block_id = block.id or by_destination.get(block.model_destination_id) or by_name.get(block.name.casefold())
        row = (geo.update_building(db, tenant, campus.id, block_id, data) if block_id
               else geo.create_building(db, tenant, campus.id, data))
        uploaded = set()
        for photo in block.photos:
            with (photo_root / photo.file).open("rb") as source:
                original = source.read(MAX_PHOTO_BYTES + 1)
            saved, _ = geo.add_photo(db, tenant, campus.id, "building", row.id, normalize_photo(original), photo.caption)
            uploaded.add(saved.id)
        if block.replace_photos:
            for photo in geo.place_data(db, row, "building")["photos"]:
                if photo["id"] not in uploaded:
                    geo.delete_photo(db, tenant, campus.id, "building", row.id, photo["id"])
    return campus.id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slug", required=True, help="Slug do portal existente.")
    parser.add_argument("--campus-id", help="ID do campus existente, necessário para renomeá-lo.")
    parser.add_argument("--assets", type=Path, default=ASSETS, help="Pasta public/campus-guide do frontend.")
    parser.add_argument("--include-model-buildings", action="store_true", help="Importa os destinos da maquete no manifesto.")
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()

    try:
        manifest = CampusManifest.model_validate_json(args.manifest.read_bytes())
        links = [block.model_destination_id for block in manifest.buildings if block.model_destination_id]
        if manifest.model_key:
            destinations = check_assets(manifest.model_key, args.assets)
            if not set(links).issubset(destinations) or len(links) != len(set(links)):
                raise ValueError("Os vínculos de blocos devem apontar para destinos distintos da maquete.")
            if args.include_model_buildings:
                include_model_buildings(manifest, destinations)
        elif links or args.include_model_buildings:
            raise ValueError("Informe model_key para vincular blocos à maquete.")
        # As operações existentes usam commit; a transação externa torna o manifesto atômico.
        with engine.begin() as connection, Session(bind=connection, join_transaction_mode="rollback_only") as db:
            campus_id = publish_campus(db, args.slug, manifest, args.manifest.parent, args.campus_id)
    except (OSError, TypeError, ValueError, LookupError) as exc:
        parser.exit(1, f"Falha ao publicar o campus: {exc}\n")

    print(f"Campus publicado. ID: {campus_id}")


if __name__ == "__main__":
    main()
