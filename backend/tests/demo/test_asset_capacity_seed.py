"""Demo asset/capacity seed tests."""

from sqlalchemy import func, select

from app.demo import seeds as _unused  # noqa: F401
from app.demo.seeds import asset_capacity_seed
from app.models.asset import Asset, Cabinet
from app.models.capacity import CoolingCapacity, PowerCapacity, SpaceCapacity, WeightCapacity
from app.models.cooling import CoolingUnit
from app.models.device import Device
from app.models.energy import PowerDevice, Transformer
from app.models.spatial import Floor, Room, Site


class _SessionCtx:
    def __init__(self, session):
        self.session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


async def test_seed_asset_capacity_derives_assets_and_capacities(async_db, monkeypatch):
    monkeypatch.setattr(asset_capacity_seed, "async_session", _SessionCtx(async_db))

    site = Site(site_code="SZ-DC-01", site_name="深圳算力中心", is_demo=True)
    async_db.add(site)
    await async_db.flush()

    floor = Floor(site_id=site.id, floor_code="F2", floor_name="二层", sort_order=2, is_demo=True)
    async_db.add(floor)
    await async_db.flush()

    room = Room(
        floor_id=floor.id,
        room_code="F2-A1",
        room_name="A1机房",
        area_sqm=500.0,
        grid_cols=20,
        grid_rows=20,
        is_demo=True,
    )
    async_db.add(room)

    transformer = Transformer(
        transformer_code="TR-DEMO-01",
        transformer_name="Demo变压器",
        rated_capacity=1000.0,
        is_enabled=True,
        is_demo=True,
    )
    async_db.add(transformer)

    cooling_device = Device(
        device_code="AC-A01",
        device_name="A区精密空调",
        device_type="AC",
        area_code="A1",
        is_enabled=True,
        is_demo=True,
    )
    async_db.add(cooling_device)
    await async_db.flush()

    async_db.add(
        CoolingUnit(
            device_id=cooling_device.id,
            unit_type="indoor",
            cooling_capacity_kw=70.0,
            is_demo=True,
        )
    )

    async_db.add_all(
        [
            PowerDevice(
                device_code="SRV-DEMO-01",
                device_name="Demo服务器",
                device_type="IT",
                rated_power=20.0,
                area_code="A1",
                is_enabled=True,
                is_demo=True,
            ),
            PowerDevice(
                device_code="PDU-F2-01",
                device_name="F2列头柜",
                device_type="PDU",
                rated_power=22.0,
                area_code="F2",
                is_enabled=True,
                is_demo=True,
            ),
        ]
    )
    await async_db.commit()

    result = await asset_capacity_seed.seed_asset_capacity()

    assert result["layouts"] == 1
    assert result["cabinets_created"] == 10
    assert result["assets_created"] == 2
    assert result["capacities_created"] == {"space": 1, "power": 1, "cooling": 1, "weight": 1}

    assert await async_db.scalar(select(func.count(Cabinet.id))) == 10
    assert await async_db.scalar(select(func.count(Asset.id))) == 2
    assert await async_db.scalar(select(func.count(SpaceCapacity.id))) == 1
    assert await async_db.scalar(select(func.count(PowerCapacity.id))) == 1
    assert await async_db.scalar(select(func.count(CoolingCapacity.id))) == 1
    assert await async_db.scalar(select(func.count(WeightCapacity.id))) == 1
    space = (await async_db.execute(select(SpaceCapacity))).scalar_one()
    weight = (await async_db.execute(select(WeightCapacity))).scalar_one()
    assert space.used_u_positions == 4
    assert space.used_cabinets == 2
    assert weight.used_weight_kg == 72.0

    second = await asset_capacity_seed.seed_asset_capacity()

    assert second["cabinets_created"] == 0
    assert second["assets_created"] == 0
    assert second["capacities_created"] == {"space": 0, "power": 0, "cooling": 0, "weight": 0}
    assert await async_db.scalar(select(func.count(Cabinet.id))) == 10
    assert await async_db.scalar(select(func.count(Asset.id))) == 2
