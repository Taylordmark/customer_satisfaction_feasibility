from typing import Optional, Dict
from pydantic import BaseModel, ConfigDict


class WarehouseBase(BaseModel):
    id: str
    label: str
    lat: float
    lon: float


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
    target_pct: float  # 0-1


class MissionAllocationPolicyCreate(MissionAllocationPolicyBase):
    pass


class MissionAllocationPolicyOut(MissionAllocationPolicyBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class CustomerBase(BaseModel):
    id: str
    label: str
    lat: float
    lon: float
    w: float
    h: float
    customer_type_id: Optional[int] = None


class CustomerCreate(CustomerBase):
    pass


class CustomerOut(CustomerBase):
    score: float
    model_config = ConfigDict(from_attributes=True)


class PackageTypeBase(BaseModel):
    id: str
    name: str
    weight: float
    volume: float


class PackageTypeCreate(PackageTypeBase):
    pass


class PackageTypeOut(PackageTypeBase):
    model_config = ConfigDict(from_attributes=True)


class MethodSpecBase(BaseModel):
    method: str
    speed_mph: float
    weight_cap: float
    vol_cap: float
    range_mi: float


class MethodSpecCreate(MethodSpecBase):
    pass


class MethodSpecOut(MethodSpecBase):
    model_config = ConfigDict(from_attributes=True)


class MethodRestrictionBase(BaseModel):
    method: str
    package_type_id: str


class MethodRestrictionCreate(MethodRestrictionBase):
    pass


class MethodRestrictionOut(MethodRestrictionBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class AssetBase(BaseModel):
    id: str
    home_warehouse_id: str
    method: str
    team_id: Optional[int] = None


class AssetCreate(AssetBase):
    pass


class AssetOut(AssetBase):
    model_config = ConfigDict(from_attributes=True)


class RefuelerBase(BaseModel):
    id: str
    home_warehouse_id: str
    team_id: Optional[int] = None
    extension_mi: float
    self_range_mi: float


class RefuelerCreate(RefuelerBase):
    pass


class RefuelerOut(RefuelerBase):
    model_config = ConfigDict(from_attributes=True)


class WarehouseInventoryBase(BaseModel):
    warehouse_id: str
    package_type_id: str
    qty: int


class WarehouseInventoryCreate(WarehouseInventoryBase):
    pass


class WarehouseInventoryOut(WarehouseInventoryBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class CustomerBundleItemBase(BaseModel):
    customer_id: str
    package_type_id: str
    qty_needed: int


class CustomerBundleItemCreate(CustomerBundleItemBase):
    pass


class CustomerBundleItemOut(CustomerBundleItemBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class SettingsBase(BaseModel):
    cycle_hours: float
    handling_time_hours: float
    refuel_overhead_hours: float
    default_daily_cap: int


class SettingsOut(SettingsBase):
    model_config = ConfigDict(from_attributes=True)


class SolveRequest(BaseModel):
    daily_cap: int
