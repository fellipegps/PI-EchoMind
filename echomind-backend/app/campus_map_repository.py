"""Persistência do mapa geográfico com isolamento de tenant e campus."""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import (
    Campus,
    CampusBuilding,
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
    for model in (CampusPathEdge, CampusSpace, CampusBuilding, CampusPathNode):
        db.query(model).filter_by(**scope).delete(synchronize_session=False)
    db.delete(campus)
    _delete_commit(db)


def list_buildings(db: Session, tenant_id: str, campus_id: str) -> list[CampusBuilding]:
    _get_campus(db, tenant_id, campus_id)
    return db.query(CampusBuilding).filter_by(tenant_id=tenant_id, campus_id=campus_id).order_by(
        CampusBuilding.name, CampusBuilding.id,
    ).all()


def _check_node(db: Session, tenant_id: str, campus_id: str, node_id: str | None) -> None:
    if node_id is not None:
        _get_child(db, CampusPathNode, tenant_id, campus_id, node_id)


def create_building(db: Session, tenant_id: str, campus_id: str, data: dict) -> CampusBuilding:
    _get_campus(db, tenant_id, campus_id)
    _check_node(db, tenant_id, campus_id, data.get("entrance_node_id"))
    _check_name(db, CampusBuilding, tenant_id, data["name"], campus_id=campus_id)
    return _save(db, CampusBuilding(tenant_id=tenant_id, campus_id=campus_id, **data))


def update_building(db: Session, tenant_id: str, campus_id: str, building_id: str,
                    changes: dict) -> CampusBuilding:
    building = _get_child(db, CampusBuilding, tenant_id, campus_id, building_id)
    _required_update(changes, "name", "category", "entrance_lat", "entrance_lng", "active")
    if "entrance_node_id" in changes:
        _check_node(db, tenant_id, campus_id, changes["entrance_node_id"])
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


def list_nodes(db: Session, tenant_id: str, campus_id: str) -> list[CampusPathNode]:
    _get_campus(db, tenant_id, campus_id)
    return db.query(CampusPathNode).filter_by(tenant_id=tenant_id, campus_id=campus_id).order_by(
        CampusPathNode.created_at, CampusPathNode.id,
    ).all()


def create_node(db: Session, tenant_id: str, campus_id: str, data: dict) -> CampusPathNode:
    _get_campus(db, tenant_id, campus_id)
    return _save(db, CampusPathNode(tenant_id=tenant_id, campus_id=campus_id, **data))


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    d_lat = radians(lat2 - lat1)
    d_lng = radians(lng2 - lng1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lng / 2) ** 2
    return 2 * 6_371_000 * asin(min(1.0, sqrt(a)))


def _edge_distance(db: Session, tenant_id: str, campus_id: str,
                   from_node_id: str, to_node_id: str) -> float:
    start = _get_child(db, CampusPathNode, tenant_id, campus_id, from_node_id)
    end = _get_child(db, CampusPathNode, tenant_id, campus_id, to_node_id)
    return max(_haversine_m(start.lat, start.lng, end.lat, end.lng), 0.01)


def update_node(db: Session, tenant_id: str, campus_id: str, node_id: str,
                changes: dict) -> CampusPathNode:
    node = _get_child(db, CampusPathNode, tenant_id, campus_id, node_id)
    _required_update(changes, "lat", "lng")
    _apply(node, changes)
    if "lat" in changes or "lng" in changes:
        db.flush()
        edges = db.query(CampusPathEdge).filter(
            CampusPathEdge.tenant_id == tenant_id,
            CampusPathEdge.campus_id == campus_id,
            or_(CampusPathEdge.from_node_id == node_id, CampusPathEdge.to_node_id == node_id),
        ).all()
        for edge in edges:
            edge.distance_m = _edge_distance(db, tenant_id, campus_id,
                                             edge.from_node_id, edge.to_node_id)
            edge.updated_at = utc_now()
    return _save(db, node)


def delete_node(db: Session, tenant_id: str, campus_id: str, node_id: str) -> None:
    node = _get_child(db, CampusPathNode, tenant_id, campus_id, node_id)
    db.query(CampusBuilding).filter_by(
        tenant_id=tenant_id, campus_id=campus_id, entrance_node_id=node_id,
    ).update({
        CampusBuilding.entrance_node_id: None,
        CampusBuilding.updated_at: utc_now(),
    }, synchronize_session=False)
    db.query(CampusPathEdge).filter(
        CampusPathEdge.tenant_id == tenant_id,
        CampusPathEdge.campus_id == campus_id,
        or_(CampusPathEdge.from_node_id == node_id, CampusPathEdge.to_node_id == node_id),
    ).delete(synchronize_session=False)
    db.delete(node)
    _delete_commit(db)


def list_edges(db: Session, tenant_id: str, campus_id: str) -> list[CampusPathEdge]:
    _get_campus(db, tenant_id, campus_id)
    return db.query(CampusPathEdge).filter_by(tenant_id=tenant_id, campus_id=campus_id).order_by(
        CampusPathEdge.created_at, CampusPathEdge.id,
    ).all()


def _prepare_edge(db: Session, tenant_id: str, campus_id: str,
                  values: dict, *, existing: CampusPathEdge | None = None) -> dict:
    start_id = values.get("from_node_id", existing.from_node_id if existing else None)
    end_id = values.get("to_node_id", existing.to_node_id if existing else None)
    if start_id == end_id:
        raise GeoValidationError("Um trecho deve conectar dois nós diferentes.")
    first_id, second_id = sorted((start_id, end_id))
    _check_node(db, tenant_id, campus_id, first_id)
    _check_node(db, tenant_id, campus_id, second_id)
    duplicate = db.query(CampusPathEdge.id).filter(
        CampusPathEdge.tenant_id == tenant_id,
        CampusPathEdge.campus_id == campus_id,
        CampusPathEdge.from_node_id == first_id,
        CampusPathEdge.to_node_id == second_id,
    )
    if existing is not None:
        duplicate = duplicate.filter(CampusPathEdge.id != existing.id)
    if duplicate.first() is not None:
        raise GeoConflictError("Este trecho já foi cadastrado.")
    values["from_node_id"] = first_id
    values["to_node_id"] = second_id
    if existing is None or "from_node_id" in values or "to_node_id" in values or "distance_m" in values:
        if values.get("distance_m") is None:
            values["distance_m"] = _edge_distance(db, tenant_id, campus_id, first_id, second_id)
    return values


def create_edge(db: Session, tenant_id: str, campus_id: str, data: dict) -> CampusPathEdge:
    _get_campus(db, tenant_id, campus_id)
    data = _prepare_edge(db, tenant_id, campus_id, data)
    return _save(db, CampusPathEdge(tenant_id=tenant_id, campus_id=campus_id, **data))


def update_edge(db: Session, tenant_id: str, campus_id: str, edge_id: str,
                changes: dict) -> CampusPathEdge:
    edge = _get_child(db, CampusPathEdge, tenant_id, campus_id, edge_id)
    _required_update(changes, "from_node_id", "to_node_id", "accessible", "active")
    if "from_node_id" in changes or "to_node_id" in changes or "distance_m" in changes:
        changes = _prepare_edge(db, tenant_id, campus_id, changes, existing=edge)
    _apply(edge, changes)
    return _save(db, edge)


def delete_edge(db: Session, tenant_id: str, campus_id: str, edge_id: str) -> None:
    edge = _get_child(db, CampusPathEdge, tenant_id, campus_id, edge_id)
    db.delete(edge)
    _delete_commit(db)


def public_map(db: Session, tenant_id: str) -> dict:
    campuses = db.query(Campus).filter(Campus.tenant_id == tenant_id, Campus.active.is_(True)).order_by(
        Campus.name, Campus.id,
    ).all()
    campus_ids = [campus.id for campus in campuses]
    if not campus_ids:
        return {"campuses": [], "buildings": [], "spaces": [], "nodes": [], "edges": []}

    buildings = db.query(CampusBuilding).filter(
        CampusBuilding.tenant_id == tenant_id,
        CampusBuilding.campus_id.in_(campus_ids),
        CampusBuilding.active.is_(True),
    ).order_by(CampusBuilding.name, CampusBuilding.id).all()
    building_ids = [building.id for building in buildings]
    spaces = db.query(CampusSpace).filter(
        CampusSpace.tenant_id == tenant_id,
        CampusSpace.campus_id.in_(campus_ids),
        CampusSpace.building_id.in_(building_ids),
        CampusSpace.active.is_(True),
    ).order_by(CampusSpace.name, CampusSpace.id).all() if building_ids else []
    edges = db.query(CampusPathEdge).filter(
        CampusPathEdge.tenant_id == tenant_id,
        CampusPathEdge.campus_id.in_(campus_ids),
        CampusPathEdge.active.is_(True),
    ).all()
    node_ids = {
        node_id for edge in edges for node_id in (edge.from_node_id, edge.to_node_id)
    }
    node_ids.update(building.entrance_node_id for building in buildings if building.entrance_node_id)
    nodes = db.query(CampusPathNode).filter(
        CampusPathNode.tenant_id == tenant_id,
        CampusPathNode.campus_id.in_(campus_ids),
        CampusPathNode.id.in_(node_ids),
    ).all() if node_ids else []
    return {"campuses": campuses, "buildings": buildings, "spaces": spaces,
            "nodes": nodes, "edges": edges}
