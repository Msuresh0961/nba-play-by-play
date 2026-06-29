"""
Run: python debug_nba_api.py
Tests nba_api package endpoints for historical play-by-play.
"""

GAME_ID = "0042400407"

print("=" * 60)
print(f"Testing nba_api package for game: {GAME_ID}")
print("=" * 60)

# Test 1: nba_api playbyplayv2
print("\n[1] nba_api PlayByPlayV2...")
try:
    from nba_api.stats.endpoints import playbyplayv2
    pbp = playbyplayv2.PlayByPlayV2(game_id=GAME_ID, timeout=30)
    df = pbp.get_data_frames()[0]
    print(f"    Rows: {len(df)}")
    if len(df) > 0:
        print(f"    Columns: {list(df.columns[:8])}")
        print(f"    First play: {df.iloc[0].to_dict()}")
except Exception as e:
    print(f"    ERROR: {e}")

# Test 2: nba_api playbyplayv3
print("\n[2] nba_api PlayByPlayV3...")
try:
    from nba_api.stats.endpoints import playbyplayv3
    pbp = playbyplayv3.PlayByPlayV3(game_id=GAME_ID, timeout=30)
    df = pbp.get_data_frames()[0]
    print(f"    Rows: {len(df)}")
    if len(df) > 0:
        print(f"    Columns: {list(df.columns[:8])}")
except Exception as e:
    print(f"    ERROR: {e}")

print("\n" + "=" * 60)