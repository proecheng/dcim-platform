#!/usr/bin/env python
"""Test VPP System - Initialize data and test endpoints"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def init_data():
    """Initialize VPP test data"""
    print("=" * 50)
    print("Initializing VPP Test Data")
    print("=" * 50)

    from app.core.database import async_session
    from app.db.init_vpp_data import init_vpp_test_data

    async with async_session() as db:
        await init_vpp_test_data(db)

    print("\n[OK] VPP test data initialized successfully!")

async def verify_data():
    """Verify VPP data was created"""
    print("\n" + "=" * 50)
    print("Verifying VPP Data")
    print("=" * 50)

    from app.core.database import async_session
    from sqlalchemy import select, func
    from app.models.vpp_data import (
        ElectricityBill, LoadCurve, ElectricityPrice,
        AdjustableLoad, VPPConfig
    )

    async with async_session() as db:
        # Count records in each table
        bills = await db.execute(select(func.count(ElectricityBill.id)))
        curves = await db.execute(select(func.count(LoadCurve.id)))
        prices = await db.execute(select(func.count(ElectricityPrice.id)))
        loads = await db.execute(select(func.count(AdjustableLoad.id)))
        configs = await db.execute(select(func.count(VPPConfig.id)))

        print(f"  electricity_bills: {bills.scalar()} records")
        print(f"  load_curves: {curves.scalar()} records")
        print(f"  electricity_prices: {prices.scalar()} records")
        print(f"  adjustable_loads: {loads.scalar()} records")
        print(f"  vpp_configs: {configs.scalar()} records")

    print("\n[OK] VPP data verification complete!")

async def test_calculator():
    """Test VPP Calculator"""
    print("\n" + "=" * 50)
    print("Testing VPP Calculator")
    print("=" * 50)

    from app.core.database import async_session
    from app.services.vpp_calculator import VPPCalculator
    from datetime import date

    async with async_session() as db:
        calculator = VPPCalculator(db)

        # Test average price
        print("\nA1. Testing calc_average_price('2025-01')...")
        result = await calculator.calc_average_price("2025-01")
        print(f"    Value: {result.get('value')} {result.get('unit')}")
        print(f"    Formula: {result.get('formula')}")

        # Test load metrics
        print("\nB. Testing calc_load_metrics(2025-10-01 to 2025-10-30)...")
        result = await calculator.calc_load_metrics(
            date(2025, 10, 1),
            date(2025, 10, 30)
        )
        if 'P_max' in result:
            print(f"    P_max: {result['P_max'].get('value')} {result['P_max'].get('unit')}")
            print(f"    P_avg: {result['P_avg'].get('value')} {result['P_avg'].get('unit')}")
            print(f"    Load rate: {result['load_rate'].get('value')}")
        else:
            print(f"    Error: {result.get('error')}")

        # Test transfer potential
        print("\nD. Testing calc_transfer_potential()...")
        result = await calculator.calc_transfer_potential()
        print(f"    Transferable load: {result['transferable_load'].get('value')} {result['transferable_load'].get('unit')}")
        print(f"    Annual benefit: {result['annual_transfer_benefit'].get('value')} {result['annual_transfer_benefit'].get('unit')}")

        # Test VPP revenue
        print("\nF. Testing calc_vpp_revenue(5290)...")
        result = await calculator.calc_vpp_revenue(5290)
        print(f"    Total VPP revenue: {result['total_vpp_revenue'].get('value')} {result['total_vpp_revenue'].get('unit')}")

    print("\n[OK] VPP Calculator tests complete!")

async def main():
    try:
        await init_data()
        await verify_data()
        await test_calculator()
        print("\n" + "=" * 50)
        print("ALL TESTS PASSED!")
        print("=" * 50)
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
