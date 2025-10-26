# Football Plugin Fixes

## Summary

Fixed the football scoreboard plugin to work more like the old display managers by addressing critical differences in logo loading, game data structure, and game state detection.

## Changes Made

### 1. Logo Loading (`scoreboard_renderer.py`)

**Added:**
- Logo caching (`self._logo_cache = {}`) to improve performance
- Logo filename variation handling for cases like TA&M vs TAANDM
- `_load_logo_from_path()` method to load logos from game data paths
- Support for both hardcoded paths (fallback) and game data paths

**Before:**
```python
def _load_team_logo(self, team_abbr: str, logo_dir: str) -> Optional[Image.Image]:
    logo_path = Path(logo_dir) / f"{team_abbr}.png"
    if logo_path.exists():
        logo = Image.open(logo_path)
        # No caching, no variation handling
        return logo
    return None
```

**After:**
```python
def _load_team_logo(self, team_abbr: str, logo_dir: str) -> Optional[Image.Image]:
    # Check cache first
    if team_abbr in self._logo_cache:
        return self._logo_cache[team_abbr]
    
    # Try filename variations
    logo_path = Path(logo_dir) / f"{team_abbr}.png"
    if LogoDownloader:
        filename_variations = LogoDownloader.get_logo_filename_variations(team_abbr)
        for filename in filename_variations:
            test_path = Path(logo_dir) / filename
            if test_path.exists():
                actual_logo_path = test_path
                break
    
    # Load and cache logo
    logo = Image.open(actual_logo_path)
    self._logo_cache[team_abbr] = logo
    return logo
```

### 2. Logo Paths in Game Data (`data_fetcher.py`)

**Added:**
- Logo paths and URLs to game data dictionary
- Normalized team abbreviations using `LogoDownloader.normalize_abbreviation()`
- League-specific logo directory determination

**Added Fields:**
```python
game = {
    # ... existing fields ...
    "home_logo_path": home_logo_path,  # Path object
    "away_logo_path": away_logo_path,  # Path object
    "home_logo_url": home_logo_url,    # URL string
    "away_logo_url": away_logo_url,    # URL string
}
```

**Before:**
- No logo paths in game data
- Hardcoded absolute paths in renderer

**After:**
- Logo paths included in game data
- Uses `LogoDownloader.normalize_abbreviation()` for consistency
- Renderer uses paths from game data with fallback

### 3. Game State Detection (`data_fetcher.py`)

**Changed:**
- Uses `status_state` primarily instead of `type_code`
- Matches old managers' game state logic exactly

**Before:**
```python
is_live = type_code in ["STATUS_IN_PROGRESS", "STATUS_HALFTIME"]
is_final = type_code == "STATUS_FINAL"
is_upcoming = type_code in ["STATUS_SCHEDULED", "STATUS_PRE"]
```

**After:**
```python
is_live = status_state == "in"
is_final = status_state == "post"
is_upcoming = (status_state == "pre" or 
               type_code.lower() in ['scheduled', 'pre-game', 'status_scheduled'])
```

### 4. Period Text Formatting (`data_fetcher.py`)

**Changed:**
- Uses `game_time` variable for upcoming games (like old managers)
- Simplified logic to match old managers exactly

**Before:**
```python
elif status_state == "pre":
    try:
        game_time = game_date.strftime("%I:%M%p").lower()
        period_text = game_time
    except (ValueError, TypeError):
        period_text = "TBD"
```

**After:**
```python
# Format game_time variable separately
game_time = ""
if status_state == "pre":
    try:
        game_time = game_date.strftime("%I:%M%p").lower().lstrip('0')
    except (ValueError, TypeError):
        game_time = "TBD"

# Use in period_text
elif status_state == "pre":
    period_text = game_time
```

### 5. Renderer Logo Loading (`scoreboard_renderer.py`)

**Changed:**
- Uses logo paths from game data first
- Falls back to team abbreviation lookup if paths not available
- Uses relative paths instead of hardcoded absolute paths

**Before:**
```python
# Hardcoded absolute paths
if league == "nfl":
    logo_dir = "/home/chuck/Github/LEDMatrix/assets/sports/nfl_logos"
else:
    logo_dir = "/home/chuck/Github/LEDMatrix/assets/sports/ncaa_logos"

home_logo = self._load_team_logo(game.get("home_abbr", ""), logo_dir)
```

**After:**
```python
# Use paths from game data first
home_logo_path = game.get("home_logo_path")
away_logo_path = game.get("away_logo_path")

if home_logo_path and away_logo_path:
    home_logo = self._load_logo_from_path(home_logo_path, game.get("home_abbr", ""))
    away_logo = self._load_logo_from_path(away_logo_path, game.get("away_abbr", ""))
else:
    # Fallback to team abbreviation lookup
    logo_dir = "assets/sports/nfl_logos" if league == "nfl" else "assets/sports/ncaa_logos"
    home_logo = self._load_team_logo(game.get("home_abbr", ""), logo_dir)
```

## Benefits

1. **Performance**: Logo caching reduces file I/O operations
2. **Reliability**: Filename variation handling catches edge cases (TA&M vs TAANDM)
3. **Consistency**: Game state detection matches old managers exactly
4. **Flexibility**: Uses game data paths with fallback for backward compatibility
5. **Maintainability**: Matches old managers' patterns and logic

## Remaining Differences

These differences were NOT changed as they are architectural choices:

1. **Configuration Structure**: Plugin expects flattened config vs old managers' nested config
2. **Game Filtering**: Plugin filters in `display()` vs old managers filter in `update()`
3. **Attribute Access**: Plugin uses `hasattr()`/`getattr()` for safety
4. **Date Ranges**: Different fallback date ranges for data fetching (-7/+14 vs -2/+1 weeks)

## Testing Recommendations

1. Test logo loading with various team abbreviations (including TA&M, U&L, etc.)
2. Verify game state detection for live, final, and upcoming games
3. Check period text formatting for upcoming games
4. Test with both NFL and NCAA FB games
5. Verify logo caching improves performance over time

