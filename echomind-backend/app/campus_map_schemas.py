"""Contratos do mapa geográfico de instituições e seus caminhos."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class GeoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("name", "category", "kind", check_fields=False)
    @classmethod
    def normalize_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if len(value) < 2:
            raise ValueError("O campo deve ter pelo menos 2 caracteres.")
        return value

    @field_validator("description", "floor", "label", check_fields=False)
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class CampusCreate(GeoInput):
    name: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    center_lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    center_lng: float = Field(ge=-180, le=180, allow_inf_nan=False)
    zoom: int = Field(default=17, ge=1, le=22)
    active: bool = True


class CampusUpdate(GeoInput):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    center_lat: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    center_lng: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    zoom: int | None = Field(default=None, ge=1, le=22)
    active: bool | None = None


class CampusResponse(BaseModel):
    id: str
    name: str
    description: str | None
    center_lat: float
    center_lng: float
    zoom: int
    active: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class BuildingCreate(GeoInput):
    name: str = Field(min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    category: str = Field(default="predio", min_length=2, max_length=100)
    entrance_lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    entrance_lng: float = Field(ge=-180, le=180, allow_inf_nan=False)
    entrance_node_id: str | None = Field(default=None, min_length=1)
    active: bool = True


class BuildingUpdate(GeoInput):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    category: str | None = Field(default=None, min_length=2, max_length=100)
    entrance_lat: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    entrance_lng: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    entrance_node_id: str | None = Field(default=None, min_length=1)
    active: bool | None = None


class BuildingResponse(BaseModel):
    id: str
    campus_id: str
    name: str
    description: str | None
    category: str
    entrance_lat: float
    entrance_lng: float
    entrance_node_id: str | None
    active: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class SpaceCreate(GeoInput):
    building_id: str = Field(min_length=1)
    name: str = Field(min_length=2, max_length=200)
    kind: str = Field(default="outro", min_length=2, max_length=100)
    floor: str | None = Field(default=None, max_length=50)
    description: str | None = Field(default=None, max_length=2000)
    active: bool = True


class SpaceUpdate(GeoInput):
    building_id: str | None = Field(default=None, min_length=1)
    name: str | None = Field(default=None, min_length=2, max_length=200)
    kind: str | None = Field(default=None, min_length=2, max_length=100)
    floor: str | None = Field(default=None, max_length=50)
    description: str | None = Field(default=None, max_length=2000)
    active: bool | None = None


class SpaceResponse(BaseModel):
    id: str
    campus_id: str
    building_id: str
    name: str
    kind: str
    floor: str | None
    description: str | None
    active: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PathNodeCreate(GeoInput):
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lng: float = Field(ge=-180, le=180, allow_inf_nan=False)
    label: str | None = Field(default=None, max_length=200)


class PathNodeUpdate(GeoInput):
    lat: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    lng: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    label: str | None = Field(default=None, max_length=200)


class PathNodeResponse(BaseModel):
    id: str
    campus_id: str
    lat: float
    lng: float
    label: str | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PathEdgeCreate(GeoInput):
    from_node_id: str = Field(min_length=1)
    to_node_id: str = Field(min_length=1)
    distance_m: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    accessible: bool = True
    active: bool = True

    @model_validator(mode="after")
    def distinct_nodes(self):
        if self.from_node_id == self.to_node_id:
            raise ValueError("Um trecho deve conectar dois nós diferentes.")
        return self


class PathEdgeUpdate(GeoInput):
    from_node_id: str | None = Field(default=None, min_length=1)
    to_node_id: str | None = Field(default=None, min_length=1)
    distance_m: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    accessible: bool | None = None
    active: bool | None = None


class PathEdgeResponse(BaseModel):
    id: str
    campus_id: str
    from_node_id: str
    to_node_id: str
    distance_m: float | None
    accessible: bool
    active: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PublicGeoCampusResponse(BaseModel):
    campuses: list[CampusResponse]
    buildings: list[BuildingResponse]
    spaces: list[SpaceResponse]
    nodes: list[PathNodeResponse]
    edges: list[PathEdgeResponse]
