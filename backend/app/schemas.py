from typing import Optional, Dict, List
from pydantic import BaseModel, ConfigDict, Field


class WarehouseBase(BaseModel):
    id: str
    label: str
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class WarehouseCreate(WarehouseBase):
    pass


class WarehouseOut(WarehouseBase):
    model_config = ConfigDict(from_attributes=True)


class TransportControlTeamBase(BaseModel):
    name: str
    warehouse_id: Optional[str] = None
    description: Optional[str] = None


class TransportControlTeamCreate(TransportControlTeamBase):
    pass


class TransportControlTeamOut(TransportControlTeamBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class CustomerTypeBase(BaseModel):
    name: str


class CustomerTypeCreate(CustomerTypeBase):
    pass


class CustomerTypeOut(CustomerTypeBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class MissionAllocationPolicyBase(BaseModel):
    customer_type_id: int
    target_pct: float = Field(gt=0, le=1)  # 0-1


class MissionAllocationPolicyCreate(MissionAllocationPolicyBase):
    pass


class MissionAllocationPolicyOut(MissionAllocationPolicyBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class CustomerBase(BaseModel):
    id: str
    label: str
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    priority_rank: int = Field(ge=1)
    included: bool = True
    customer_type_id: Optional[int] = None


class CustomerCreate(CustomerBase):
    pass


class CustomerOut(CustomerBase):
    model_config = ConfigDict(from_attributes=True)


class PackageTypeBase(BaseModel):
    id: str
    name: str
    weight: float = Field(gt=0)
    volume: float = Field(gt=0)


class PackageTypeCreate(PackageTypeBase):
    pass


class PackageTypeOut(PackageTypeBase):
    model_config = ConfigDict(from_attributes=True)


class MethodSpecBase(BaseModel):
    method: str
    speed_mph: float = Field(gt=0)
    weight_cap: float = Field(gt=0)
    vol_cap: float = Field(gt=0)
    range_mi: float = Field(gt=0)


class MethodSpecCreate(MethodSpecBase):
    pass


class MethodSpecOut(MethodSpecBase):
    model_config = ConfigDict(from_attributes=True)


class AssetRestrictionBase(BaseModel):
    asset_id: str
    package_type_id: str


class AssetRestrictionCreate(AssetRestrictionBase):
    pass


class AssetRestrictionOut(AssetRestrictionBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class AssetBase(BaseModel):
    id: str
    home_warehouse_id: str
    method: str
    vehicle_type: str = "Unspecified"
    available: bool = True
    team_id: Optional[int] = None


class AssetCreate(AssetBase):
    pass


class AssetOut(AssetBase):
    model_config = ConfigDict(from_attributes=True)


class RefuelerBase(BaseModel):
    id: str
    home_warehouse_id: str
    vehicle_type: str = "Unspecified"
    available: bool = True
    team_id: Optional[int] = None
    extension_mi: float = Field(ge=0)
    self_range_mi: float = Field(ge=0)


class RefuelerCreate(RefuelerBase):
    pass


class RefuelerOut(RefuelerBase):
    model_config = ConfigDict(from_attributes=True)


class WarehouseInventoryBase(BaseModel):
    warehouse_id: str
    package_type_id: str
    qty: int = Field(ge=0)


class WarehouseInventoryCreate(WarehouseInventoryBase):
    pass


class WarehouseInventoryOut(WarehouseInventoryBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class CustomerBundleItemBase(BaseModel):
    customer_id: str
    package_type_id: str
    qty_needed: int = Field(ge=1)


class CustomerBundleItemCreate(CustomerBundleItemBase):
    pass


class CustomerBundleItemOut(CustomerBundleItemBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class SettingsBase(BaseModel):
    cycle_hours: float = Field(gt=0)
    handling_time_hours: float = Field(ge=0)
    refuel_overhead_hours: float = Field(ge=0)
    default_daily_cap: int = Field(ge=1)


class SettingsOut(SettingsBase):
    model_config = ConfigDict(from_attributes=True)


class PlannedMissionBase(BaseModel):
    customer_id: str
    asset_id: Optional[str] = None
    refueler_id: Optional[str] = None
    package_type_id: Optional[str] = None
    source_warehouse_id: Optional[str] = None


class PlannedMissionCreate(PlannedMissionBase):
    pass


class PlannedMissionOut(PlannedMissionBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class QuotaInput(BaseModel):
    customer_type_id: int
    target_pct: float = Field(gt=0, le=1)  # fraction 0-1 of the day's missions


class SolveRequest(BaseModel):
    daily_cap: int = Field(ge=1)
    # per-type mission share floors set on the generate page;
    # None means fall back to the stored Mission Allocation Policies
    quotas: Optional[List[QuotaInput]] = None
