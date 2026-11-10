"""Persistência do mapa geográfico com isolamento de tenant e campus."""

from __future__ import annotations

from hashlib import sha256
from urllib.parse import quote

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import (
    Campus,
    CampusBuilding,
    CampusLandmark,
    CampusPlacePhoto,
    CampusPathEdge,
    CampusPathNode,
    CampusSpace,
    utc_now,
)


class GeoNotFoundError(LookupError):
    pass


class GeoConflictError(ValueError):
    pass


class GeoValidationError(ValueError):
    pass


def _save(db: Session, row):
    try:
        db.add(row)
        db.commit()
        db.refresh(row)
    except IntegrityError as exc:
        db.rollback()
        raise GeoConflictError("Nome ou conexão já cadastrado.") from exc
    return row


def _delete_commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise GeoConflictError("O item possui vínculos e não pode ser excluído.") from exc


def _get_campus(db: Session, tenant_id: str, campus_id: str) -> Campus:
    campus = db.query(Campus).filter(
        Campus.id == campus_id,
        Campus.tenant_id == tenant_id,
    ).first()
    if campus is None:
        raise GeoNotFoundError("Campus não encontrado.")
    return campus


def _get_child(db: Session, model, tenant_id: str, campus_id: str, item_id: str):
    _get_campus(db, tenant_id, campus_id)
    item = db.query(model).filter(
        model.id == item_id,
        model.tenant_id == tenant_id,
        model.campus_id == campus_id,
    ).first()
    if item is None:
        raise GeoNotFoundError("Item não encontrado neste campus.")
    return item


def _name_taken(db: Session, model, tenant_id: str, name: str, *, campus_id: str | None = None,
                building_id: str | None = None, exclude_id: str | None = None) -> bool:
    query = db.query(model.id).filter(
        model.tenant_id == tenant_id,
        func.lower(model.name) == name.casefold(),
    )
    if campus_id is not None:
        query = query.filter(model.campus_id == campus_id)
    if building_id is not None:
        query = query.filter(model.building_id == building_id)
    if exclude_id is not None:
        query = query.filter(model.id != exclude_id)
    return query.first() is not None


def _check_name(db: Session, model, tenant_id: str, name: str, *, campus_id: str | None = None,
                building_id: str | None = None, exclude_id: str | None = None) -> None:
    if _name_taken(db, model, tenant_id, name, campus_id=campus_id,
                   building_id=building_id, exclude_id=exclude_id):
        raise GeoConflictError("Já existe um item com esse nome neste local.")


def _required_update(changes: dict, *fields: str) -> None:
    for field in fields:
        if field in changes and changes[field] is None:
            raise GeoValidationError(f"{field} não pode ser nulo.")


def _apply(row, changes: dict) -> None:
    for key, value in changes.items():
        setattr(row, key, value)
    row.updated_at = utc_now()


def list_campuses(db: Session, tenant_id: str) -> list[Campus]:
    return db.query(Campus).filter(Campus.tenant_id == tenant_id).order_by(Campus.name, Campus.id).all()


def create_campus(db: Session, tenant_id: str, data: dict) -> Campus:
    _check_name(db, Campus, tenant_id, data["name"])
    return _save(db, Campus(tenant_id=tenant_id, **data))


def update_campus(db: Session, tenant_id: str, campus_id: str, changes: dict) -> Campus:
    campus = _get_campus(db, tenant_id, campus_id)
    _required_update(changes, "name", "center_lat", "center_lng", "zoom", "active")
    if "name" in changes:
        _check_name(db, Campus, tenant_id, changes["name"], exclude_id=campus_id)
    _apply(campus, changes)
    return _save(db, campus)


def delete_campus(db: Session, tenant_id: str, campus_id: str) -> None:
    campus = _get_campus(db, tenant_id, campus_id)
    scope = {"tenant_id": tenant_id, "campus_id": campus_id}
    for model in (CampusPathEdge, CampusSpace, CampusBuilding, CampusLandmark, CampusPathNode):
        db.query(model).filter_by(**scope).delete(synchronize_session=False)
    db.delete(campus)
    _delete_commit(db)


def list_buildings(db: Session, tenant_id: str, campus_id: str) -> list[CampusBuilding]:
    _get_campus(db, tenant_id, campus_id)
    return db.query(CampusBuilding).filter_by(tenant_id=tenant_id, campus_id=campus_id).order_by(
        CampusBuilding.name, CampusBuilding.id,
    ).all()


def create_building(db: Session, tenant_id: str, campus_id: str, data: dict) -> CampusBuilding:
    _get_campus(db, tenant_id, campus_id)
    _check_name(db, CampusBuilding, tenant_id, data["name"], campus_id=campus_id)
    return _save(db, CampusBuilding(tenant_id=tenant_id, campus_id=campus_id, **data))


def update_building(db: Session, tenant_id: str, campus_id: str, building_id: str,
                    changes: dict) -> CampusBuilding:
    building = _get_child(db, CampusBuilding, tenant_id, campus_id, building_id)
    _required_update(changes, "name", "category", "entrance_lat", "entrance_lng", "active")
    if "name" in changes:
        _check_name(db, CampusBuilding, tenant_id, changes["name"], campus_id=campus_id,
                    exclude_id=building_id)
    _apply(building, changes)
    return _save(db, building)


def delete_building(db: Session, tenant_id: str, campus_id: str, building_id: str) -> None:
    building = _get_child(db, CampusBuilding, tenant_id, campus_id, building_id)
    db.query(CampusSpace).filter_by(
        tenant_id=tenant_id, campus_id=campus_id, building_id=building_id,
    ).delete(synchronize_session=False)
    db.delete(building)
    _delete_commit(db)


def list_spaces(db: Session, tenant_id: str, campus_id: str) -> list[CampusSpace]:
    _get_campus(db, tenant_id, campus_id)
    return db.query(CampusSpace).filter_by(tenant_id=tenant_id, campus_id=campus_id).order_by(
        CampusSpace.name, CampusSpace.id,
    ).all()


def create_space(db: Session, tenant_id: str, campus_id: str, data: dict) -> CampusSpace:
    _get_child(db, CampusBuilding, tenant_id, campus_id, data["building_id"])
    _check_name(db, CampusSpace, tenant_id, data["name"], campus_id=campus_id,
                building_id=data["building_id"])
    return _save(db, CampusSpace(tenant_id=tenant_id, campus_id=campus_id, **data))


def update_space(db: Session, tenant_id: str, campus_id: str, space_id: str,
                 changes: dict) -> CampusSpace:
    space = _get_child(db, CampusSpace, tenant_id, campus_id, space_id)
    _required_update(changes, "building_id", "name", "kind", "active")
    building_id = changes.get("building_id", space.building_id)
    if "building_id" in changes:
        _get_child(db, CampusBuilding, tenant_id, campus_id, building_id)
    if "name" in changes or "building_id" in changes:
        _check_name(db, CampusSpace, tenant_id, changes.get("name", space.name),
                    campus_id=campus_id, building_id=building_id, exclude_id=space_id)
    _apply(space, changes)
    return _save(db, space)


def delete_space(db: Session, tenant_id: str, campus_id: str, space_id: str) -> None:
    space = _get_child(db, CampusSpace, tenant_id, campus_id, space_id)
    db.delete(space)
    _delete_commit(db)


def list_landmarks(db: Session, tenant_id: str, campus_id: str) -> list[CampusLandmark]:
    _get_campus(db, tenant_id, campus_id)
    return db.query(CampusLandmark).filter_by(tenant_id=tenant_id, campus_id=campus_id).order_by(
        CampusLandmark.name, CampusLandmark.id,
    ).all()


def create_landmark(db: Session, tenant_id: str, campus_id: str, data: dict) -> CampusLandmark:
    _get_campus(db, tenant_id, campus_id)
    _check_name(db, CampusLandmark, tenant_id, data["name"], campus_id=campus_id)
    return _save(db, CampusLandmark(tenant_id=tenant_id, campus_id=campus_id, **data))


def update_landmark(db: Session, tenant_id: str, campus_id: str, landmark_id: str,
                    changes: dict) -> CampusLandmark:
    row = _get_child(db, CampusLandmark, tenant_id, campus_id, landmark_id)
    _required_update(changes, "name", "lat", "lng", "active")
    if "name" in changes:
        _check_name(db, CampusLandmark, tenant_id, changes["name"], campus_id=campus_id,
                    exclude_id=landmark_id)
    _apply(row, changes)
    return _save(db, row)


def delete_landmark(db: Session, tenant_id: str, campus_id: str, landmark_id: str) -> None:
    row = _get_child(db, CampusLandmark, tenant_id, campus_id, landmark_id)
    db.delete(row)
    _delete_commit(db)


PLACE_MODELS = {"building": CampusBuilding, "space": CampusSpace, "landmark": CampusLandmark}


def get_place(db: Session, tenant_id: str, campus_id: str, place_type: str, place_id: str):
    return _get_child(db, PLACE_MODELS[place_type], tenant_id, campus_id, place_id)


def _photo_query(db: Session, row, place_type: str):
    return db.query(CampusPlacePhoto).filter(
        CampusPlacePhoto.tenant_id == row.tenant_id,
        CampusPlacePhoto.campus_id == row.campus_id,
        getattr(CampusPlacePhoto, f"{place_type}_id") == row.id,
    )


def photo_data(photo: CampusPlacePhoto, row, place_type: str, public_slug: str | None = None) -> dict:
    if public_slug is not None:
        base = f"/public/{quote(public_slug, safe='')}/places/{place_type}/{row.public_code}"
    else:
        base = f"/campuses/{row.campus_id}/places/{place_type}/{row.id}"
    return {
        "id": photo.id, "caption": photo.caption, "sort_order": photo.sort_order,
        "url": f"{base}/photos/{photo.id}",
    }


def places_data(db: Session, rows: list, place_type: str,
                public_slug: str | None = None) -> list[dict]:
    if not rows:
        return []
    field = getattr(CampusPlacePhoto, f"{place_type}_id")
    photos = db.query(CampusPlacePhoto).filter(
        CampusPlacePhoto.tenant_id == rows[0].tenant_id,
        field.in_([row.id for row in rows]),
    ).order_by(CampusPlacePhoto.sort_order, CampusPlacePhoto.created_at, CampusPlacePhoto.id).all()
    by_place = {row.id: [] for row in rows}
    row_lookup = {row.id: row for row in rows}
    for photo in photos:
        place_id = getattr(photo, f"{place_type}_id")
        by_place[place_id].append(photo_data(photo, row_lookup[place_id], place_type, public_slug))
    result = []
    for row in rows:
        values = {column.name: getattr(row, column.name)
                  for column in row.__table__.columns if column.name != "tenant_id"}
        values["photos"] = by_place[row.id]
        result.append(values)
    return result


def place_data(db: Session, row, place_type: str, public_slug: str | None = None) -> dict:
    return places_data(db, [row], place_type, public_slug)[0]


def add_photo(db: Session, tenant_id: str, campus_id: str, place_type: str, place_id: str,
              content: bytes, caption: str | None) -> tuple[CampusPlacePhoto, object]:
    model = PLACE_MODELS[place_type]
    # The parent lock serializes uploads and deletion of the same place in PostgreSQL.
    row = db.query(model).filter_by(
        tenant_id=tenant_id, campus_id=campus_id, id=place_id,
    ).with_for_update().first()
    if row is None:
        raise GeoNotFoundError("Local não encontrado neste campus.")
    digest = sha256(content).hexdigest()
    existing = _photo_query(db, row, place_type).filter(CampusPlacePhoto.sha256 == digest).first()
    if existing is not None:
        return existing, row
    last_order = _photo_query(db, row, place_type).with_entities(
        func.max(CampusPlacePhoto.sort_order),
    ).scalar()
    photo = CampusPlacePhoto(
        tenant_id=tenant_id, campus_id=campus_id, **{f"{place_type}_id": place_id},
        caption=caption, sort_order=(last_order + 1 if last_order is not None else 0),
        mime_type="image/jpeg", sha256=digest, size_bytes=len(content), content=content,
    )
    try:
        db.add(photo)
        db.commit()
        db.refresh(photo)
    except IntegrityError:
        db.rollback()
        # A retry of an upload returns the same photo rather than adding a duplicate.
        existing = _photo_query(db, row, place_type).filter(CampusPlacePhoto.sha256 == digest).first()
        if existing is None:
            raise GeoConflictError("O local foi alterado. Atualize a página e tente novamente.") from None
        return existing, row
    return photo, row


def get_photo(db: Session, row, place_type: str, photo_id: str) -> CampusPlacePhoto:
    photo = _photo_query(db, row, place_type).filter(CampusPlacePhoto.id == photo_id).first()
    if photo is None:
        raise GeoNotFoundError("Foto não encontrada neste local.")
    return photo


def delete_photo(db: Session, tenant_id: str, campus_id: str, place_type: str,
                 place_id: str, photo_id: str) -> None:
    row = get_place(db, tenant_id, campus_id, place_type, place_id)
    photo = get_photo(db, row, place_type, photo_id)
    db.delete(photo)
    _delete_commit(db)


def public_place(db: Session, tenant_id: str, place_type: str, public_code: str):
    model = PLACE_MODELS[place_type]
    row = db.query(model).filter_by(
        tenant_id=tenant_id, public_code=public_code, active=True,
    ).first()
    if row is None:
        raise GeoNotFoundError("Local não encontrado.")
    campus = db.query(Campus).filter_by(
        id=row.campus_id, tenant_id=tenant_id, active=True,
    ).first()
    building = None
    if place_type == "space":
        building = db.query(CampusBuilding).filter_by(
            id=row.building_id, tenant_id=tenant_id, campus_id=row.campus_id, active=True,
        ).first()
        if building is None:
            raise GeoNotFoundError("Local não encontrado.")
    if campus is None:
        raise GeoNotFoundError("Local não encontrado.")
    return row, campus, building


def public_map(db: Session, tenant_id: str, public_slug: str) -> dict:
    campuses = db.query(Campus).filter_by(tenant_id=tenant_id, active=True).order_by(
        Campus.name, Campus.id,
    ).all()
    campus_ids = [campus.id for campus in campuses]
    buildings = db.query(CampusBuilding).filter(
        CampusBuilding.tenant_id == tenant_id,
        CampusBuilding.campus_id.in_(campus_ids), CampusBuilding.active.is_(True),
    ).order_by(CampusBuilding.name, CampusBuilding.id).all()
    spaces = db.query(CampusSpace).filter(
        CampusSpace.tenant_id == tenant_id, CampusSpace.campus_id.in_(campus_ids),
        CampusSpace.building_id.in_([building.id for building in buildings]),
        CampusSpace.active.is_(True),
    ).order_by(CampusSpace.name, CampusSpace.id).all()
    landmarks = db.query(CampusLandmark).filter(
        CampusLandmark.tenant_id == tenant_id, CampusLandmark.campus_id.in_(campus_ids),
        CampusLandmark.active.is_(True),
    ).order_by(CampusLandmark.name, CampusLandmark.id).all()
    return {
        "campuses": campuses,
        "buildings": places_data(db, buildings, "building", public_slug),
        "spaces": places_data(db, spaces, "space", public_slug),
        "landmarks": places_data(db, landmarks, "landmark", public_slug),
    }
