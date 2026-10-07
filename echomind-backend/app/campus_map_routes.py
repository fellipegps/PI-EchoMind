"""API administrativa e pública para mapas geográficos de campus."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from . import crud
from .auth import CurrentUser, get_current_user
from .campus_map_repository import GeoConflictError, GeoNotFoundError, GeoValidationError
from . import campus_map_repository as geo
from .campus_map_schemas import (
    BuildingCreate, BuildingResponse, BuildingUpdate,
    CampusCreate, CampusResponse, CampusUpdate,
    PathEdgeCreate, PathEdgeResponse, PathEdgeUpdate,
    PathNodeCreate, PathNodeResponse, PathNodeUpdate,
    PublicGeoCampusResponse,
    SpaceCreate, SpaceResponse, SpaceUpdate,
)
from .database import get_db


router_campuses = APIRouter(prefix="/campuses", tags=["Mapa geográfico"])
router_public_geo = APIRouter(prefix="/public", tags=["Portal público"])


def _tenant_id(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> str:
    crud.ensure_tenant_onboarded(
        db,
        tenant_id=current_user.id,
        email=current_user.email,
        company_name=current_user.company_name,
        full_name=current_user.full_name,
    )
    return current_user.id


def _call(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except GeoNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except GeoConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except GeoValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router_campuses.get("", response_model=list[CampusResponse])
def list_campuses(db: Session = Depends(get_db), tenant_id: str = Depends(_tenant_id)):
    return geo.list_campuses(db, tenant_id)


@router_campuses.post("", response_model=CampusResponse, status_code=201)
def create_campus(payload: CampusCreate, db: Session = Depends(get_db),
                  tenant_id: str = Depends(_tenant_id)):
    return _call(geo.create_campus, db, tenant_id, payload.model_dump())


@router_campuses.get("/{campus_id}", response_model=CampusResponse)
def get_campus(campus_id: str, db: Session = Depends(get_db),
               tenant_id: str = Depends(_tenant_id)):
    return _call(geo._get_campus, db, tenant_id, campus_id)


@router_campuses.put("/{campus_id}", response_model=CampusResponse)
def update_campus(campus_id: str, payload: CampusUpdate, db: Session = Depends(get_db),
                  tenant_id: str = Depends(_tenant_id)):
    return _call(geo.update_campus, db, tenant_id, campus_id,
                 payload.model_dump(exclude_unset=True))


@router_campuses.delete("/{campus_id}", status_code=204)
def delete_campus(campus_id: str, db: Session = Depends(get_db),
                  tenant_id: str = Depends(_tenant_id)):
    _call(geo.delete_campus, db, tenant_id, campus_id)


@router_campuses.get("/{campus_id}/buildings", response_model=list[BuildingResponse])
def list_buildings(campus_id: str, db: Session = Depends(get_db),
                   tenant_id: str = Depends(_tenant_id)):
    return _call(geo.list_buildings, db, tenant_id, campus_id)


@router_campuses.post("/{campus_id}/buildings", response_model=BuildingResponse, status_code=201)
def create_building(campus_id: str, payload: BuildingCreate, db: Session = Depends(get_db),
                    tenant_id: str = Depends(_tenant_id)):
    return _call(geo.create_building, db, tenant_id, campus_id, payload.model_dump())


@router_campuses.get("/{campus_id}/buildings/{building_id}", response_model=BuildingResponse)
def get_building(campus_id: str, building_id: str, db: Session = Depends(get_db),
                 tenant_id: str = Depends(_tenant_id)):
    return _call(geo._get_child, db, geo.CampusBuilding, tenant_id, campus_id, building_id)


@router_campuses.put("/{campus_id}/buildings/{building_id}", response_model=BuildingResponse)
def update_building(campus_id: str, building_id: str, payload: BuildingUpdate,
                    db: Session = Depends(get_db), tenant_id: str = Depends(_tenant_id)):
    return _call(geo.update_building, db, tenant_id, campus_id, building_id,
                 payload.model_dump(exclude_unset=True))


@router_campuses.delete("/{campus_id}/buildings/{building_id}", status_code=204)
def delete_building(campus_id: str, building_id: str, db: Session = Depends(get_db),
                    tenant_id: str = Depends(_tenant_id)):
    _call(geo.delete_building, db, tenant_id, campus_id, building_id)


@router_campuses.get("/{campus_id}/spaces", response_model=list[SpaceResponse])
def list_spaces(campus_id: str, db: Session = Depends(get_db),
                tenant_id: str = Depends(_tenant_id)):
    return _call(geo.list_spaces, db, tenant_id, campus_id)


@router_campuses.post("/{campus_id}/spaces", response_model=SpaceResponse, status_code=201)
def create_space(campus_id: str, payload: SpaceCreate, db: Session = Depends(get_db),
                 tenant_id: str = Depends(_tenant_id)):
    return _call(geo.create_space, db, tenant_id, campus_id, payload.model_dump())


@router_campuses.get("/{campus_id}/spaces/{space_id}", response_model=SpaceResponse)
def get_space(campus_id: str, space_id: str, db: Session = Depends(get_db),
              tenant_id: str = Depends(_tenant_id)):
    return _call(geo._get_child, db, geo.CampusSpace, tenant_id, campus_id, space_id)


@router_campuses.put("/{campus_id}/spaces/{space_id}", response_model=SpaceResponse)
def update_space(campus_id: str, space_id: str, payload: SpaceUpdate,
                 db: Session = Depends(get_db), tenant_id: str = Depends(_tenant_id)):
    return _call(geo.update_space, db, tenant_id, campus_id, space_id,
                 payload.model_dump(exclude_unset=True))


@router_campuses.delete("/{campus_id}/spaces/{space_id}", status_code=204)
def delete_space(campus_id: str, space_id: str, db: Session = Depends(get_db),
                 tenant_id: str = Depends(_tenant_id)):
    _call(geo.delete_space, db, tenant_id, campus_id, space_id)


@router_campuses.get("/{campus_id}/path-nodes", response_model=list[PathNodeResponse])
def list_nodes(campus_id: str, db: Session = Depends(get_db),
               tenant_id: str = Depends(_tenant_id)):
    return _call(geo.list_nodes, db, tenant_id, campus_id)


@router_campuses.post("/{campus_id}/path-nodes", response_model=PathNodeResponse, status_code=201)
def create_node(campus_id: str, payload: PathNodeCreate, db: Session = Depends(get_db),
                tenant_id: str = Depends(_tenant_id)):
    return _call(geo.create_node, db, tenant_id, campus_id, payload.model_dump())


@router_campuses.get("/{campus_id}/path-nodes/{node_id}", response_model=PathNodeResponse)
def get_node(campus_id: str, node_id: str, db: Session = Depends(get_db),
             tenant_id: str = Depends(_tenant_id)):
    return _call(geo._get_child, db, geo.CampusPathNode, tenant_id, campus_id, node_id)


@router_campuses.put("/{campus_id}/path-nodes/{node_id}", response_model=PathNodeResponse)
def update_node(campus_id: str, node_id: str, payload: PathNodeUpdate,
                db: Session = Depends(get_db), tenant_id: str = Depends(_tenant_id)):
    return _call(geo.update_node, db, tenant_id, campus_id, node_id,
                 payload.model_dump(exclude_unset=True))


@router_campuses.delete("/{campus_id}/path-nodes/{node_id}", status_code=204)
def delete_node(campus_id: str, node_id: str, db: Session = Depends(get_db),
                tenant_id: str = Depends(_tenant_id)):
    _call(geo.delete_node, db, tenant_id, campus_id, node_id)


@router_campuses.get("/{campus_id}/path-edges", response_model=list[PathEdgeResponse])
def list_edges(campus_id: str, db: Session = Depends(get_db),
               tenant_id: str = Depends(_tenant_id)):
    return _call(geo.list_edges, db, tenant_id, campus_id)


@router_campuses.post("/{campus_id}/path-edges", response_model=PathEdgeResponse, status_code=201)
def create_edge(campus_id: str, payload: PathEdgeCreate, db: Session = Depends(get_db),
                tenant_id: str = Depends(_tenant_id)):
    return _call(geo.create_edge, db, tenant_id, campus_id, payload.model_dump())


@router_campuses.get("/{campus_id}/path-edges/{edge_id}", response_model=PathEdgeResponse)
def get_edge(campus_id: str, edge_id: str, db: Session = Depends(get_db),
             tenant_id: str = Depends(_tenant_id)):
    return _call(geo._get_child, db, geo.CampusPathEdge, tenant_id, campus_id, edge_id)


@router_campuses.put("/{campus_id}/path-edges/{edge_id}", response_model=PathEdgeResponse)
def update_edge(campus_id: str, edge_id: str, payload: PathEdgeUpdate,
                db: Session = Depends(get_db), tenant_id: str = Depends(_tenant_id)):
    return _call(geo.update_edge, db, tenant_id, campus_id, edge_id,
                 payload.model_dump(exclude_unset=True))


@router_campuses.delete("/{campus_id}/path-edges/{edge_id}", status_code=204)
def delete_edge(campus_id: str, edge_id: str, db: Session = Depends(get_db),
                tenant_id: str = Depends(_tenant_id)):
    _call(geo.delete_edge, db, tenant_id, campus_id, edge_id)


@router_public_geo.get("/{public_slug}/geo-campus", response_model=PublicGeoCampusResponse)
def get_public_geo_campus(public_slug: str, db: Session = Depends(get_db)):
    config = crud.get_config_by_public_slug(db, public_slug)
    if config is None:
        raise HTTPException(status_code=404, detail="Instituição não encontrada.")
    return geo.public_map(db, config.tenant_id)
