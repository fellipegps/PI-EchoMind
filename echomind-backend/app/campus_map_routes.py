"""API administrativa e pública para mapas geográficos de campus."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from . import crud
from .auth import CurrentUser, get_current_user
from .campus_map_repository import GeoConflictError, GeoNotFoundError, GeoValidationError
from . import campus_map_repository as geo
from .campus_map_schemas import (
    BuildingCreate, BuildingResponse, BuildingUpdate,
    CampusCreate, CampusResponse, CampusUpdate,
    LandmarkCreate, LandmarkResponse, LandmarkUpdate,
    PlacePhotoResponse, PlaceType, PublicGeoCampusResponse, PublicPlaceResponse,
    SpaceCreate, SpaceResponse, SpaceUpdate,
)
from .database import get_db
from .campus_photo import InvalidPhoto, MAX_PHOTO_BYTES, normalize_photo
from .document_upload import DocumentUploadRoute


router_campuses = APIRouter(prefix="/campuses", tags=["Mapa geográfico"], route_class=DocumentUploadRoute)
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
    return geo.places_data(db, _call(geo.list_buildings, db, tenant_id, campus_id), "building")


@router_campuses.post("/{campus_id}/buildings", response_model=BuildingResponse, status_code=201)
def create_building(campus_id: str, payload: BuildingCreate, db: Session = Depends(get_db),
                    tenant_id: str = Depends(_tenant_id)):
    return geo.place_data(db, _call(geo.create_building, db, tenant_id, campus_id, payload.model_dump()), "building")


@router_campuses.get("/{campus_id}/buildings/{building_id}", response_model=BuildingResponse)
def get_building(campus_id: str, building_id: str, db: Session = Depends(get_db),
                 tenant_id: str = Depends(_tenant_id)):
    return geo.place_data(db, _call(geo.get_place, db, tenant_id, campus_id, "building", building_id), "building")


@router_campuses.put("/{campus_id}/buildings/{building_id}", response_model=BuildingResponse)
def update_building(campus_id: str, building_id: str, payload: BuildingUpdate,
                    db: Session = Depends(get_db), tenant_id: str = Depends(_tenant_id)):
    return geo.place_data(db, _call(geo.update_building, db, tenant_id, campus_id, building_id,
                 payload.model_dump(exclude_unset=True)), "building")


@router_campuses.delete("/{campus_id}/buildings/{building_id}", status_code=204)
def delete_building(campus_id: str, building_id: str, db: Session = Depends(get_db),
                    tenant_id: str = Depends(_tenant_id)):
    _call(geo.delete_building, db, tenant_id, campus_id, building_id)


@router_campuses.get("/{campus_id}/spaces", response_model=list[SpaceResponse])
def list_spaces(campus_id: str, db: Session = Depends(get_db),
                tenant_id: str = Depends(_tenant_id)):
    return geo.places_data(db, _call(geo.list_spaces, db, tenant_id, campus_id), "space")


@router_campuses.post("/{campus_id}/spaces", response_model=SpaceResponse, status_code=201)
def create_space(campus_id: str, payload: SpaceCreate, db: Session = Depends(get_db),
                 tenant_id: str = Depends(_tenant_id)):
    return geo.place_data(db, _call(geo.create_space, db, tenant_id, campus_id, payload.model_dump()), "space")


@router_campuses.get("/{campus_id}/spaces/{space_id}", response_model=SpaceResponse)
def get_space(campus_id: str, space_id: str, db: Session = Depends(get_db),
              tenant_id: str = Depends(_tenant_id)):
    return geo.place_data(db, _call(geo.get_place, db, tenant_id, campus_id, "space", space_id), "space")


@router_campuses.put("/{campus_id}/spaces/{space_id}", response_model=SpaceResponse)
def update_space(campus_id: str, space_id: str, payload: SpaceUpdate,
                 db: Session = Depends(get_db), tenant_id: str = Depends(_tenant_id)):
    return geo.place_data(db, _call(geo.update_space, db, tenant_id, campus_id, space_id,
                 payload.model_dump(exclude_unset=True)), "space")


@router_campuses.delete("/{campus_id}/spaces/{space_id}", status_code=204)
def delete_space(campus_id: str, space_id: str, db: Session = Depends(get_db),
                 tenant_id: str = Depends(_tenant_id)):
    _call(geo.delete_space, db, tenant_id, campus_id, space_id)


@router_campuses.get("/{campus_id}/landmarks", response_model=list[LandmarkResponse])
def list_landmarks(campus_id: str, db: Session = Depends(get_db),
                   tenant_id: str = Depends(_tenant_id)):
    rows = _call(geo.list_landmarks, db, tenant_id, campus_id)
    return geo.places_data(db, rows, "landmark")


@router_campuses.post("/{campus_id}/landmarks", response_model=LandmarkResponse, status_code=201)
def create_landmark(campus_id: str, payload: LandmarkCreate, db: Session = Depends(get_db),
                    tenant_id: str = Depends(_tenant_id)):
    row = _call(geo.create_landmark, db, tenant_id, campus_id, payload.model_dump())
    return geo.place_data(db, row, "landmark")


@router_campuses.get("/{campus_id}/landmarks/{landmark_id}", response_model=LandmarkResponse)
def get_landmark(campus_id: str, landmark_id: str, db: Session = Depends(get_db),
                 tenant_id: str = Depends(_tenant_id)):
    row = _call(geo.get_place, db, tenant_id, campus_id, "landmark", landmark_id)
    return geo.place_data(db, row, "landmark")


@router_campuses.put("/{campus_id}/landmarks/{landmark_id}", response_model=LandmarkResponse)
def update_landmark(campus_id: str, landmark_id: str, payload: LandmarkUpdate,
                    db: Session = Depends(get_db), tenant_id: str = Depends(_tenant_id)):
    row = _call(geo.update_landmark, db, tenant_id, campus_id, landmark_id,
                payload.model_dump(exclude_unset=True))
    return geo.place_data(db, row, "landmark")


@router_campuses.delete("/{campus_id}/landmarks/{landmark_id}", status_code=204)
def delete_landmark(campus_id: str, landmark_id: str, db: Session = Depends(get_db),
                    tenant_id: str = Depends(_tenant_id)):
    _call(geo.delete_landmark, db, tenant_id, campus_id, landmark_id)


@router_campuses.post(
    "/{campus_id}/places/{place_type}/{place_id}/photos",
    response_model=PlacePhotoResponse, status_code=201,
)
def upload_photo(campus_id: str, place_type: PlaceType, place_id: str,
                 file: UploadFile = File(), caption: str | None = Form(default=None, max_length=300),
                 db: Session = Depends(get_db), tenant_id: str = Depends(_tenant_id)):
    _call(geo.get_place, db, tenant_id, campus_id, place_type, place_id)
    content = file.file.read(MAX_PHOTO_BYTES + 1)
    if len(content) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail="A foto deve ter até 5 MiB.")
    try:
        content = normalize_photo(content)
    except InvalidPhoto as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    photo, row = _call(geo.add_photo, db, tenant_id, campus_id, place_type, place_id,
                       content, caption.strip() or None if caption else None)
    return geo.photo_data(photo, row, place_type)


def _image_response(photo):
    return Response(
        content=photo.content, media_type=photo.mime_type,
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                 "Content-Disposition": 'inline; filename="campus-photo.jpg"'},
    )


@router_campuses.get("/{campus_id}/places/{place_type}/{place_id}/photos/{photo_id}")
def get_photo(campus_id: str, place_type: PlaceType, place_id: str, photo_id: str,
              db: Session = Depends(get_db), tenant_id: str = Depends(_tenant_id)):
    row = _call(geo.get_place, db, tenant_id, campus_id, place_type, place_id)
    return _image_response(_call(geo.get_photo, db, row, place_type, photo_id))


@router_campuses.delete("/{campus_id}/places/{place_type}/{place_id}/photos/{photo_id}", status_code=204)
def delete_photo(campus_id: str, place_type: PlaceType, place_id: str, photo_id: str,
                 db: Session = Depends(get_db), tenant_id: str = Depends(_tenant_id)):
    _call(geo.delete_photo, db, tenant_id, campus_id, place_type, place_id, photo_id)


def _public_config(db: Session, public_slug: str):
    config = crud.get_config_by_public_slug(db, public_slug)
    if config is None:
        raise HTTPException(status_code=404, detail="Instituição não encontrada.")
    return config


@router_public_geo.get("/{public_slug}/geo-campus", response_model=PublicGeoCampusResponse)
def get_public_geo_campus(public_slug: str, db: Session = Depends(get_db)):
    config = _public_config(db, public_slug)
    return geo.public_map(db, config.tenant_id, public_slug)


@router_public_geo.get("/{public_slug}/places/{place_type}/{public_code}", response_model=PublicPlaceResponse)
def get_public_place(public_slug: str, place_type: PlaceType, public_code: str,
                     db: Session = Depends(get_db)):
    config = _public_config(db, public_slug)
    row, campus, building = _call(geo.public_place, db, config.tenant_id, place_type, public_code)
    return {
        "type": place_type, "campus": campus,
        "place": geo.place_data(db, row, place_type, public_slug),
        "building": geo.place_data(db, building, "building", public_slug) if building else None,
    }


@router_public_geo.get("/{public_slug}/places/{place_type}/{public_code}/photos/{photo_id}")
def get_public_photo(public_slug: str, place_type: PlaceType, public_code: str,
                     photo_id: str, db: Session = Depends(get_db)):
    config = _public_config(db, public_slug)
    row, _campus, _building = _call(geo.public_place, db, config.tenant_id, place_type, public_code)
    return _image_response(_call(geo.get_photo, db, row, place_type, photo_id))
