"""
Run this directly: python debug_api.py
Tests both CDN and stats.nba.com endpoints for a historical game.
"""
import requests

GAME_ID = "0042400407"

CDN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}

STATS_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "x-nba-stats-origin": "stats",
    "x-nba-stats-token": "true",
    "Host": "stats.nba.com",
    "Connection": "keep-alive",
}

print("=" * 60)
print(f"Testing game ID: {GAME_ID}")
print("=" * 60)

# Test 1: CDN endpoint
print("\n[1] CDN live endpoint...")
cdn_url = f"https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_{GAME_ID}.json"
try:
    r = requests.get(cdn_url, headers=CDN_HEADERS, timeout=10)
    print(f"    Status: {r.status_code}")
    if r.status_code == 200:
        actions = r.json().get("game", {}).get("actions", [])
        print(f"    Actions: {len(actions)}")
    else:
        print(f"    Response: {r.text[:200]}")
except Exception as e:
    print(f"    ERROR: {e}")

# Test 2: stats.nba.com playbyplayv3
print("\n[2] stats.nba.com playbyplayv3...")
stats_url = f"https://stats.nba.com/stats/playbyplayv3?GameID={GAME_ID}&StartPeriod=0&EndPeriod=14"
try:
    r = requests.get(stats_url, headers=STATS_HEADERS, timeout=15)
    print(f"    Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        # Try both response shapes
        actions = data.get("game", {}).get("actions", [])
        if actions:
            print(f"    Actions (game.actions): {len(actions)}")
        else:
            result_sets = data.get("resultSets", [])
            if result_sets:
                rows = result_sets[0].get("rowSet", [])
                print(f"    Actions (resultSets): {len(rows)}")
            else:
                print(f"    Keys in response: {list(data.keys())}")
                print(f"    Raw (first 300): {str(data)[:300]}")
    else:
        print(f"    Response: {r.text[:200]}")
except Exception as e:
    print(f"    ERROR: {e}")

# Test 3: stats.nba.com playbyplayv2 (older endpoint, more reliable)
print("\n[3] stats.nba.com playbyplayv2...")
v2_url = f"https://stats.nba.com/stats/playbyplayv2?GameID={GAME_ID}&StartPeriod=0&EndPeriod=14&RangeType=0&StartRange=0&EndRange=55800"
try:
    r = requests.get(v2_url, headers=STATS_HEADERS, timeout=15)
    print(f"    Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        result_sets = data.get("resultSets", [])
        if result_sets:
            rows = result_sets[0].get("rowSet", [])
            print(f"    Actions (resultSets): {len(rows)}")
            if rows:
                print(f"    First row keys: {result_sets[0].get('headers', [])[:8]}")
        else:
            print(f"    Keys: {list(data.keys())}")
    else:
        print(f"    Response: {r.text[:200]}")
except Exception as e:
    print(f"    ERROR: {e}")

print("\n" + "=" * 60)