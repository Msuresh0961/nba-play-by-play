from datetime import date, timedelta
from nba_api.stats.endpoints import scoreboardv3

target_date = date.today() + timedelta(days=1)

print("Checking date:", target_date.isoformat())

board = scoreboardv3.ScoreboardV3(
    game_date=target_date.isoformat(),
    league_id="00"
)

print("\nAvailable attributes:")
print([name for name in dir(board) if not name.startswith("_")])

print("\nGame header dataframe:")
df = board.game_header.get_data_frame()
print(df)

print("\nColumns:")
print(list(df.columns))

print("\nFirst row:")
if not df.empty:
    print(df.iloc[0].to_dict())
else:
    print("No rows returned")