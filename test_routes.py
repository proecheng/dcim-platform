"""
Test API route registration
"""
import sys
sys.path.insert(0, r'D:\mytest1\backend')

try:
    print("Importing regulation module...")
    from app.api.v1 import regulation
    print(f"[OK] Regulation module imported")
    print(f"  Router: {regulation.router}")
    print(f"  Routes count: {len(regulation.router.routes)}")

    print("\nImporting api_router...")
    from app.api.v1 import api_router
    print(f"[OK] API Router imported")
    print(f"  Total routes: {len(api_router.routes)}")

    print("\nChecking regulation routes...")
    regulation_routes = [r for r in api_router.routes if hasattr(r, 'path') and 'regulation' in r.path.lower()]
    print(f"  Found {len(regulation_routes)} regulation routes:")
    for route in regulation_routes:
        print(f"    - {route.path} [{','.join(route.methods)}]")

    if len(regulation_routes) == 0:
        print("\n[ERROR] Regulation routes not registered!")
    else:
        print("\n[OK] Regulation routes registered correctly")

except Exception as e:
    print(f"\n[ERROR] Import failed: {e}")
    import traceback
    traceback.print_exc()
