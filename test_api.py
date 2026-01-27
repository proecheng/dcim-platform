import requests
from datetime import datetime, timedelta

def test_apis():
    # Login
    resp = requests.post('http://localhost:8000/api/v1/auth/login', data={'username': 'admin', 'password': 'admin123'})
    if resp.status_code != 200:
        print(f'Login FAILED: {resp.text}')
        return

    token = resp.json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}
    print('=== Login OK ===\n')

    today = datetime.now().strftime('%Y-%m-%d')
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')

    tests = [
        ('Auth - Me', '/api/v1/auth/me'),
        ('Auth - Permissions', '/api/v1/auth/permissions'),
        ('Realtime - All', '/api/v1/realtime'),
        ('Realtime - Summary', '/api/v1/realtime/summary'),
        ('Realtime - Dashboard', '/api/v1/realtime/dashboard'),
        ('Points - List', '/api/v1/points?page=1&page_size=10'),
        ('Points - Types Summary', '/api/v1/points/types-summary'),
        ('Devices - List', '/api/v1/devices'),
        ('Devices - Tree', '/api/v1/devices/tree'),
        ('Devices - Status Summary', '/api/v1/devices/status-summary'),
        ('Alarms - List', '/api/v1/alarms'),
        ('Alarms - Active', '/api/v1/alarms/active'),
        ('Alarms - Count', '/api/v1/alarms/count'),
        ('Alarms - Statistics', '/api/v1/alarms/statistics'),
        ('History (point 1)', '/api/v1/history/1'),
        ('Thresholds - List', '/api/v1/thresholds'),
        ('Users - List', '/api/v1/users'),
        ('Logs - Operations', '/api/v1/logs/operations'),
        ('Logs - Systems', '/api/v1/logs/systems'),
        ('Logs - Communications', '/api/v1/logs/communications'),
        ('Logs - Statistics', '/api/v1/logs/statistics'),
        ('Configs - List', '/api/v1/configs'),
        ('Configs - Dictionaries', '/api/v1/configs/dictionaries'),
        ('Configs - License', '/api/v1/configs/license'),
        ('Statistics - Overview', '/api/v1/statistics/overview'),
        ('Statistics - Points', '/api/v1/statistics/points'),
        ('Statistics - Alarms', '/api/v1/statistics/alarms'),
        ('Energy - PUE', '/api/v1/energy/pue'),
        ('Energy - Devices', '/api/v1/energy/devices'),
        ('Energy - Realtime', '/api/v1/energy/realtime'),
        ('Energy - Daily Stats', f'/api/v1/energy/statistics/daily?start_date={week_ago}&end_date={today}'),
        ('Energy - Suggestions', '/api/v1/energy/suggestions'),
        ('Energy - Saving Potential', '/api/v1/energy/saving/potential'),
        ('Energy - Pricing', '/api/v1/energy/pricing'),
        ('Reports - Templates', '/api/v1/reports/templates'),
        ('Reports - Records', '/api/v1/reports/records'),
    ]

    ok_count = 0
    fail_count = 0

    for name, endpoint in tests:
        try:
            resp = requests.get(f'http://localhost:8000{endpoint}', headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                ok_count += 1
                if isinstance(data, list):
                    print(f'[OK] {name}: {len(data)} items')
                elif isinstance(data, dict):
                    if 'items' in data:
                        print(f'[OK] {name}: {len(data["items"])} items, total: {data.get("total", "N/A")}')
                    elif 'data' in data and isinstance(data['data'], list):
                        print(f'[OK] {name}: {len(data["data"])} items')
                    elif 'data' in data and isinstance(data['data'], dict):
                        print(f'[OK] {name}')
                    elif 'total_points' in data:
                        print(f'[OK] {name}: {data["total_points"]} points')
                    else:
                        print(f'[OK] {name}')
                else:
                    print(f'[OK] {name}')
            else:
                fail_count += 1
                print(f'[FAIL] {name}: {resp.status_code} - {resp.text[:80]}')
        except Exception as e:
            fail_count += 1
            print(f'[ERROR] {name}: {e}')

    print(f'\n=== Summary: {ok_count} OK, {fail_count} FAILED ===')

if __name__ == '__main__':
    test_apis()
