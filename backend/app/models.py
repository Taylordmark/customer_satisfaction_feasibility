"""
SQLAlchemy models. Every entity here is fully CRUD-editable through the API —
there is no hardcoded dataset baked into the app logic. seed.py populates an
initial example dataset once, on first boot, if the database is empty.
"""

from sqlalchemy import Column, String, Float, Integer, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from .database import Base


class Warehouse(Base):
    """A resource node: holds package inventory and is the home base for
    transport assets and refuelers stationed there."""
    __tablename__ = "warehouses"
    id = Column(String, primary_key=True)          # e.g. "W1"
    label = Column(String, nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)

    assets = relationship("Asset", back_populates="home_warehouse", cascade="all, delete-orphan")
    refuelers = relationship("Refueler", back_populates="home_warehouse", cascade="all, delete-orphan")
    inventory = relationship("WarehouseInventory", back_populates="warehouse", cascade="all, delete-orphan")
    teams = relationship("TransportControlTeam", back_populates="warehouse")


class TransportControlTeam(Base):
    """The organization that owns and can task a set of transport assets."""
    __tablename__ = "transport_control_teams"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    warehouse_id = Column(String, ForeignKey("warehouses.id"), nullable=True)  # where they're stationed
    description = Column(String, nullable=True)

    warehouse = relationship("Warehouse", back_populates="teams")
    assets = relationship("Asset", back_populates="team")
    refuelers = relationship("Refueler", back_populates="team")


class CustomerType(Base):
    """A category of customer (storefront, warehouse, FOB, ...) used for
    mission-allocation quotas — e.g. 'at least 40% of missions to Storefront'."""
    __tablename__ = "customer_types"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False, unique=True)

    customers = relationship("Customer", back_populates="customer_type")
    policy = relationship("MissionAllocationPolicy", back_populates="customer_type",
                           uselist=False, cascade="all, delete-orphan")


class MissionAllocationPolicy(Base):
    """Minimum share of scheduled missions (deliveries) that must go to
    customers of a given type, as a fraction 0-1."""
    __tablename__ = "mission_allocation_policies"
    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_type_id = Column(Integer, ForeignKey("customer_types.id"), nullable=False, unique=True)
    target_pct = Column(Float, nullable=False)  # 0.40 == 40%

    customer_type = relationship("CustomerType", back_populates="policy")


class Customer(Base):
    __tablename__ = "customers"
    id = Column(String, primary_key=True)           # e.g. "C1"
    label = Column(String, nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    priority_rank = Column(Integer, nullable=False, default=1)  # 1 = highest priority
    included = Column(Boolean, nullable=False, default=True)    # in today's plan?
    customer_type_id = Column(Integer, ForeignKey("customer_types.id"), nullable=True)

    bundle_items = relationship("CustomerBundleItem", back_populates="customer", cascade="all, delete-orphan")
    customer_type = relationship("CustomerType", back_populates="customers")


class PackageType(Base):
    __tablename__ = "package_types"
    id = Column(String, primary_key=True)            # e.g. "K1"
    name = Column(String, nullable=False)
    weight = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)


class MethodSpec(Base):
    """Default capabilities for a transport method (Air / Ground / Sea / ...)."""
    __tablename__ = "method_specs"
    method = Column(String, primary_key=True)
    speed_mph = Column(Float, nullable=False)
    weight_cap = Column(Float, nullable=False)
    vol_cap = Column(Float, nullable=False)
    range_mi = Column(Float, nullable=False)

    assets = relationship("Asset", back_populates="method_spec")


class Asset(Base):
    __tablename__ = "assets"
    id = Column(String, primary_key=True)             # e.g. "Air-1"
    home_warehouse_id = Column(String, ForeignKey("warehouses.id"), nullable=False)
    method = Column(String, ForeignKey("method_specs.method"), nullable=False)
    vehicle_type = Column(String, nullable=False, default="Unspecified")  # model name, e.g. "Albatross HL"
    available = Column(Boolean, nullable=False, default=True)  # in service today?
    team_id = Column(Integer, ForeignKey("transport_control_teams.id"), nullable=True)

    home_warehouse = relationship("Warehouse", back_populates="assets")
    method_spec = relationship("MethodSpec", back_populates="assets")
    team = relationship("TransportControlTeam", back_populates="assets")
    restrictions = relationship("AssetRestriction", back_populates="asset", cascade="all, delete-orphan")


class AssetRestriction(Base):
    """A package type this specific vehicle is NOT able to carry. Carrying
    ability is per-asset, not per method — two ships can differ."""
    __tablename__ = "asset_restrictions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    asset_id = Column(String, ForeignKey("assets.id"), nullable=False)
    package_type_id = Column(String, ForeignKey("package_types.id"), nullable=False)
    __table_args__ = (UniqueConstraint("asset_id", "package_type_id", name="uq_asset_package"),)

    asset = relationship("Asset", back_populates="restrictions")
    package_type = relationship("PackageType")


class Refueler(Base):
    __tablename__ = "refuelers"
    id = Column(String, primary_key=True)              # e.g. "Tanker-1"
    home_warehouse_id = Column(String, ForeignKey("warehouses.id"), nullable=False)
    vehicle_type = Column(String, nullable=False, default="Unspecified")  # model name, e.g. "Pelican KR"
    available = Column(Boolean, nullable=False, default=True)  # in service today?
    team_id = Column(Integer, ForeignKey("transport_control_teams.id"), nullable=True)
    extension_mi = Column(Float, nullable=False)
    self_range_mi = Column(Float, nullable=False)

    home_warehouse = relationship("Warehouse", back_populates="refuelers")
    team = relationship("TransportControlTeam", back_populates="refuelers")


class WarehouseInventory(Base):
    __tablename__ = "warehouse_inventory"
    id = Column(Integer, primary_key=True, autoincrement=True)
    warehouse_id = Column(String, ForeignKey("warehouses.id"), nullable=False)
    package_type_id = Column(String, ForeignKey("package_types.id"), nullable=False)
    qty = Column(Integer, nullable=False, default=0)
    __table_args__ = (UniqueConstraint("warehouse_id", "package_type_id", name="uq_warehouse_package"),)

    warehouse = relationship("Warehouse", back_populates="inventory")
    package_type = relationship("PackageType")


class CustomerBundleItem(Base):
    """Package options for a customer — fully delivering any one option's
    quantity satisfies them (lines are alternatives, not a checklist)."""
    __tablename__ = "customer_bundle_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    package_type_id = Column(String, ForeignKey("package_types.id"), nullable=False)
    qty_needed = Column(Integer, nullable=False)
    __table_args__ = (UniqueConstraint("customer_id", "package_type_id", name="uq_customer_package"),)

    customer = relationship("Customer", back_populates="bundle_items")
    package_type = relationship("PackageType")


class PlannedMission(Base):
    """A human-pinned mission for today's plan, at any level of detail:
    just a customer ("must be satisfied today"), through a specific asset,
    refueler, bundle option, or source warehouse. Whatever is specified
    becomes a hard constraint on the solve; whatever is left null stays the
    optimizer's choice. Conflicting pins make the run refuse and explain
    rather than being silently dropped."""
    __tablename__ = "planned_missions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=False)
    asset_id = Column(String, ForeignKey("assets.id"), nullable=True)
    refueler_id = Column(String, ForeignKey("refuelers.id"), nullable=True)
    package_type_id = Column(String, ForeignKey("package_types.id"), nullable=True)
    source_warehouse_id = Column(String, ForeignKey("warehouses.id"), nullable=True)

    customer = relationship("Customer")
    asset = relationship("Asset")
    refueler = relationship("Refueler")
    package_type = relationship("PackageType")
    source_warehouse = relationship("Warehouse")


class Settings(Base):
    """Single-row table of cycle-wide constants."""
    __tablename__ = "settings"
    id = Column(Integer, primary_key=True, default=1)
    cycle_hours = Column(Float, nullable=False, default=24)
    handling_time_hours = Column(Float, nullable=False, default=2)
    refuel_overhead_hours = Column(Float, nullable=False, default=3)
    default_daily_cap = Column(Integer, nullable=False, default=10)
