from .. import models, schemas
from .crud_factory import make_crud_router

warehouses_router = make_crud_router(
    prefix="/api/warehouses", tag="warehouses", model=models.Warehouse,
    create_schema=schemas.WarehouseCreate, out_schema=schemas.WarehouseOut, id_type=str,
)

teams_router = make_crud_router(
    prefix="/api/teams", tag="teams", model=models.TransportControlTeam,
    create_schema=schemas.TransportControlTeamCreate, out_schema=schemas.TransportControlTeamOut, id_type=int,
)

customer_types_router = make_crud_router(
    prefix="/api/customer-types", tag="customer-types", model=models.CustomerType,
    create_schema=schemas.CustomerTypeCreate, out_schema=schemas.CustomerTypeOut, id_type=int,
)

allocation_policies_router = make_crud_router(
    prefix="/api/allocation-policies", tag="allocation-policies", model=models.MissionAllocationPolicy,
    create_schema=schemas.MissionAllocationPolicyCreate, out_schema=schemas.MissionAllocationPolicyOut, id_type=int,
)

customers_router = make_crud_router(
    prefix="/api/customers", tag="customers", model=models.Customer,
    create_schema=schemas.CustomerCreate, out_schema=schemas.CustomerOut, id_type=str,
)

package_types_router = make_crud_router(
    prefix="/api/package-types", tag="package-types", model=models.PackageType,
    create_schema=schemas.PackageTypeCreate, out_schema=schemas.PackageTypeOut, id_type=str,
)

method_specs_router = make_crud_router(
    prefix="/api/method-specs", tag="method-specs", model=models.MethodSpec,
    create_schema=schemas.MethodSpecCreate, out_schema=schemas.MethodSpecOut, id_type=str,
)

method_restrictions_router = make_crud_router(
    prefix="/api/method-restrictions", tag="method-restrictions", model=models.MethodRestriction,
    create_schema=schemas.MethodRestrictionCreate, out_schema=schemas.MethodRestrictionOut, id_type=int,
)

assets_router = make_crud_router(
    prefix="/api/assets", tag="assets", model=models.Asset,
    create_schema=schemas.AssetCreate, out_schema=schemas.AssetOut, id_type=str,
)

refuelers_router = make_crud_router(
    prefix="/api/refuelers", tag="refuelers", model=models.Refueler,
    create_schema=schemas.RefuelerCreate, out_schema=schemas.RefuelerOut, id_type=str,
)

warehouse_inventory_router = make_crud_router(
    prefix="/api/warehouse-inventory", tag="warehouse-inventory", model=models.WarehouseInventory,
    create_schema=schemas.WarehouseInventoryCreate, out_schema=schemas.WarehouseInventoryOut, id_type=int,
)

customer_bundle_items_router = make_crud_router(
    prefix="/api/customer-bundle-items", tag="customer-bundle-items", model=models.CustomerBundleItem,
    create_schema=schemas.CustomerBundleItemCreate, out_schema=schemas.CustomerBundleItemOut, id_type=int,
)

all_crud_routers = [
    warehouses_router, teams_router, customer_types_router, allocation_policies_router,
    customers_router, package_types_router, method_specs_router, method_restrictions_router,
    assets_router, refuelers_router, warehouse_inventory_router, customer_bundle_items_router,
]
