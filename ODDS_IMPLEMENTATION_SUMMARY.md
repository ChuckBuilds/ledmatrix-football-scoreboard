# Odds Implementation Summary

## Overview
Successfully implemented betting odds functionality in the football scoreboard plugin using `BaseOddsManager` from the LEDMatrix core.

---

## Changes Made

### 1. Manager (`manager.py`)

**Added Imports**:
```python
from src.base_odds_manager import BaseOddsManager
```

**Initialized Odds Manager**:
```python
# Initialize odds manager if enabled
self.odds_manager = None
if self.show_odds and BaseOddsManager:
    try:
        config_manager = getattr(cache_manager, 'config_manager', None)
        self.odds_manager = BaseOddsManager(cache_manager, config_manager)
        self.logger.info("Odds manager initialized")
    except Exception as e:
        self.logger.warning("Could not initialize odds manager: %s", e)
```

**Fetch Odds During Update**:
```python
# In update() method
if self.show_odds and self.odds_manager:
    self._fetch_odds_for_games(all_games)
```

**Added Methods**:
- `_fetch_odds_for_games()` - Iterates through games and fetches odds
- `_fetch_odds()` - Fetches odds for individual game using BaseOddsManager

### 2. Renderer (`scoreboard_renderer.py`)

**Added Odds Drawing Call**:
```python
# In _draw_scorebug_layout()
# Draw odds if available (matches old managers)
if 'odds' in game and game['odds']:
    self._draw_dynamic_odds(draw_overlay, game['odds'], 
                           self.display_width, self.display_height)
```

**Added Method**:
- `_draw_dynamic_odds()` - Draws spread and over/under with dynamic positioning

---

## How It Works

### 1. Initialization
- Plugin checks if `show_odds` config is enabled
- If enabled, initializes `BaseOddsManager` with cache_manager and config_manager
- Logs success or warning if initialization fails

### 2. Data Fetching
- During `update()`, iterates through all games
- For each game, calls `_fetch_odds()` which:
  - Determines sport and league for the game
  - Sets update interval (60s for live, 3600s for upcoming)
  - Calls `BaseOddsManager.get_odds()` with event ID
  - Attaches odds data to game dictionary

### 3. Display
- During `_draw_scorebug_layout()`, checks if game has odds data
- If present, calls `_draw_dynamic_odds()` which:
  - Extracts spread and over/under from odds data
  - Determines which team is favored (negative spread)
  - Shows spread on favored team's side (green text)
  - Shows over/under on opposite side or center (green text)

---

## Configuration

Enable odds in plugin config:
```json
{
  "show_odds": true,
  "nfl": {
    "display_modes": {
      "show_live": true,
      "show_recent": true,
      "show_upcoming": true
    }
  }
}
```

---

## Differences from Old Managers

| Aspect | Old Manager | Plugin |
|--------|-------------|--------|
| **Odds Manager** | `OddsManager` | `BaseOddsManager` |
| **Import Path** | `src.odds_manager` | `src.base_odds_manager` |
| **Initialization** | In SportsCore | In Plugin init |
| **Fetching** | `_fetch_odds()` in SportsCore | `_fetch_odds()` in Plugin |
| **Drawing** | `_draw_dynamic_odds()` in SportsCore | `_draw_dynamic_odds()` in Renderer |

---

## Testing

To test odds functionality:

1. **Enable in config**:
   ```json
   "show_odds": true
   ```

2. **Check logs**:
   - Should see "Odds manager initialized"
   - Should see "Attached odds to game <ID>" for games with odds

3. **Visual verification**:
   - Spread displayed in green on top corners
   - Over/under displayed in green
   - Positioning based on favored team

---

## Benefits

1. **Uses BaseOddsManager**: More modern, configurable odds system
2. **Proper Integration**: Follows plugin architecture patterns
3. **Matches Old Behavior**: Same visual appearance and logic
4. **Error Handling**: Gracefully handles missing odds or API failures
5. **Conditional**: Only runs when `show_odds` is enabled

---

## Future Enhancements

Potential improvements:
- Per-league odds config (NFL vs NCAA FB)
- Custom odds display colors
- Money line display option
- Odds update interval configuration

