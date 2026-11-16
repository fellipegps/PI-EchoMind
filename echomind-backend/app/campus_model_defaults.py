"""Prepara o cadastro editável para o acervo de Anápolis já distribuído no portal."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .campus_map_repository import GeoConflictError, GeoNotFoundError
from .database import Campus, CampusBuilding, CampusSpace

CATALOG = json.loads(Path(__file__).with_name("anapolis_catalog.json").read_text(encoding="utf-8"))
ALIASES = {
    "biblioteca": {"bloco b1", "biblioteca central"},
    "bloco-g": {"bloco g"},
    "ginasio": {"ginasio"},
}


def _normalize(name: str) -> str:
    text = unicodedata.normalize("NFD", name.casefold())
    return " ".join("".join(char for char in text if not unicodedata.combining(char)).split())


def prepare_anapolis(db: Session, tenant_id: str, campus_id: str, slug: str, company_name: str) -> None:
    campus = db.query(Campus).filter_by(tenant_id=tenant_id, id=campus_id, active=True).with_for_update().one_or_none()
    if campus is None:
        raise GeoNotFoundError("Campus não encontrado.")
    if campus.model_defaults_applied:
        return
    if campus.model_key is None:
        institution = re.match(r"^unievangelica(?:-|$)", slug, re.I) or re.search(r"\bunievangelica\b", _normalize(company_name))
        near_anapolis = abs(campus.center_lat + 16.294) < .01 and abs(campus.center_lng + 48.944) < .01
        if not institution or not near_anapolis:
            return
    elif campus.model_key != "anapolis":
        return

    buildings = db.query(CampusBuilding).filter_by(tenant_id=tenant_id, campus_id=campus_id).all()
    by_destination = {building.model_destination_id: building for building in buildings}
    by_name = {_normalize(building.name): building for building in buildings}
    space_names = {(building_id, _normalize(name)) for building_id, name in
                   db.query(CampusSpace.building_id, CampusSpace.name).filter_by(tenant_id=tenant_id, campus_id=campus_id)}

    try:
        for preset in CATALOG:
            key, name = preset["id"], preset["name"]
            building = by_destination.get(key)
            if building is None:
                building = by_name.get(_normalize(name))
                if building is None:
                    aliases = ALIASES.get(key, set())
                    matches = [row for alias, row in by_name.items() if alias in aliases and not row.model_destination_id]
                    if len(matches) == 1:
                        building = matches[0]
                if building is None:
                    lng, lat = preset["coordinates"]
                    building = CampusBuilding(tenant_id=tenant_id, campus_id=campus_id, name=name,
                                              category="bloco", entrance_lat=lat, entrance_lng=lng)
                    db.add(building)
                elif building.model_destination_id:
                    continue
                building.model_destination_id = key
                db.flush()

            for laboratory in preset.get("laboratories", []):
                name, *parts = laboratory.split(" · ")
                if (building.id, _normalize(name)) in space_names or (building.id, _normalize(laboratory)) in space_names:
                    continue
                floor = next((part for part in parts if part.startswith("Piso ")), None)
                description = " · ".join(part for part in parts if part != floor) or None
                db.add(CampusSpace(tenant_id=tenant_id, campus_id=campus_id, building_id=building.id,
                                   name=name, kind="laboratório", floor=floor, description=description))
        campus.model_defaults_applied = True
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise GeoConflictError("Não foi possível preparar os blocos. Atualize os dados do campus e tente novamente.") from exc
