# Odds Display Documentation

## Current Status: ✅ IMPLEMENTED

The plugin now properly **fetches and displays odds** using `BaseOddsManager` when `show_odds` is enabled in the configuration.

---

## How Old Managers Handle Odds

### Old Manager (`SportsCore` in `sports.py`)

**1. Import and Initialize**:
```python
from src.odds_manager import OddsManager

class SportsCore(ABC):
    def __init__(self, ...):
        self.odds_manager = OddsManager(
            self.cache_manager, self.config_manager)
        self.show_odds: bool = self.mode_config.get("show_odds", False)
```

**2. Fetch Odds During Update**:
```python
def update(self):
    # ... process games ...
    for event in events:
        game = self._extract_game_details(event)
        if game and game['is_upcoming']:
            if self.show_odds:
                self._fetch_odds(game)  # ← Fetch odds here

def _fetch_odds(self, game: Dict) -> None:
    """Fetch odds for a specific game using the new architecture."""
    if not self.show_odds:
        return
    
    # Determine update interval based on game state
    is_live = game.get('is_live', False)
    update_interval = self.mode_config.get("live_odds_update_interval", 60) if is_live \
        else self.mode_config.get("odds_update_interval", 3600)
    
    # Fetch odds using OddsManager
    odds_data = self.odds_manager.get_odds(
        sport=self.sport,
        league=self.league,
        event_id=game['id'],
        update_interval_seconds=update_interval
    )
    
    if odds_data:
        game['odds'] = odds_data  # ← Attach to game dict
```

**3. Display Odds During Render**:
```python
def _draw_scorebug_layout(self, game: Dict, force_clear: bool = False):
    # ... draw game elements ...
    
    # Draw odds if available
    if 'odds' in game and game['odds']:
        self._draw_dynamic_odds(draw_overlay, game['odds'], 
                               self.display_width, self.display_height)

def _draw_dynamic_odds(self, draw: ImageDraw.Draw, odds: Dict[str, Any], 
                      width: int, height: int) -> None:
    """Draw odds with dynamic positioning - only show negative spread."""
    home_team_odds = odds.get('home_team_odds', {})
    away_team_odds = odds.get('away_team_odds', {})
    home_spread = home_team_odds.get('spread_odds')
    away_spread = away_team_odds.get('spread_odds')
    
    # Determine which team is favored (has negative spread)
    home_favored = home_spread is not None and home_spread < 0
    away_favored = away_spread is not None and away_spread < 0
    
    # Only show the negative spread (favored team)
    if home_favored:
        favored_spread = home_spread
        favored_side = 'home'
    elif away_favored:
        favored_spread = away_spread
        favored_side = 'away'
    
    # Show spread on appropriate side
    if favored_spread is not None:
        spread_text = str(favored_spread)
        spread_x = width - spread_width if favored_side == 'home' else 0
        spread_y = 0
        self._draw_text_with_outline(draw, spread_text, (spread_x, spread_y), 
                                    font, fill=(0, 255, 0))
    
    # Show over/under on opposite side
    over_under = odds.get('over_under')
    if over_under is not None:
        ou_text = f"O/U: {over_under}"
        ou_x = 0 if favored_side == 'home' else width - ou_width
        ou_y = 0
        self._draw_text_with_outline(draw, ou_text, (ou_x, ou_y), 
                                    font, fill=(0, 255, 0))
```

---

## Plugin Implementation

### Current Plugin (`manager.py`)

**Has Config**:
```python
self.show_odds = config.get("show_odds", False)
```

**Implemented**:
- ✅ BaseOddsManager import
- ✅ Odds fetching logic via `_fetch_odds()`
- ✅ Odds drawing code via `_draw_dynamic_odds()`
- ✅ Odds data attached to game dictionaries

---

## What Was Added

### 1. Added BaseOddsManager to Plugin

```python
# In manager.py __init__()
try:
    from src.base_odds_manager import BaseOddsManager
except ImportError:
    BaseOddsManager = None

class FootballScoreboardPlugin(BasePlugin if BasePlugin else object):
    def __init__(self, ...):
        # ... existing code ...
        
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

### 2. Fetch Odds During Update

```python
# In manager.py update()
def update(self) -> None:
    # ... existing game fetching ...
    
    # Fetch odds for games if enabled
    if self.show_odds and self.odds_manager:
        for game in all_games:
            self._fetch_odds(game)

def _fetch_odds(self, game: Dict) -> None:
    """Fetch odds for a specific game."""
    try:
        if not self.show_odds or not self.odds_manager:
            return
        
        # Determine league for odds lookup
        league = game.get("league", "nfl")
        if league == "nfl":
            sport = "football"
            league_for_odds = "nfl"
        elif league == "ncaa_fb":
            sport = "football"
            league_for_odds = "college-football"
        else:
            return
        
        # Determine update interval based on game state
        is_live = game.get('is_live', False)
        update_interval = 60 if is_live else 3600
        
        # Fetch odds using OddsManager
        odds_data = self.odds_manager.get_odds(
            sport=sport,
            league=league_for_odds,
            event_id=game['id'],
            update_interval_seconds=update_interval
        )
        
        if odds_data:
            game['odds'] = odds_data
            self.logger.debug(f"Attached odds to game {game['id']}")
            
    except Exception as e:
        self.logger.error(f"Error fetching odds for game {game.get('id', 'N/A')}: {e}")
```

### 3. Added Odds Drawing to Renderer

```python
# In scoreboard_renderer.py
class ScoreboardRenderer:
    def _draw_scorebug_layout(self, game: Dict, force_clear: bool = False):
        # ... existing drawing code ...
        
        # Draw odds if available
        if 'odds' in game and game['odds']:
            self._draw_dynamic_odds(draw_overlay, game['odds'], 
                                   self.display_width, self.display_height)
    
    def _draw_dynamic_odds(self, draw: ImageDraw.Draw, odds: Dict[str, Any], 
                          width: int, height: int) -> None:
        """Draw odds with dynamic positioning."""
        # Copy from sports.py _draw_dynamic_odds method
        home_team_odds = odds.get('home_team_odds', {})
        away_team_odds = odds.get('away_team_odds', {})
        home_spread = home_team_odds.get('spread_odds')
        away_spread = away_team_odds.get('spread_odds')
        
        # Get top-level spread as fallback
        top_level_spread = odds.get('spread')
        
        # Use top-level spread if individual spreads missing
        if top_level_spread is not None:
            if home_spread is None or home_spread == 0.0:
                home_spread = top_level_spread
            if away_spread is None:
                away_spread = -top_level_spread
        
        # Determine which team is favored
        home_favored = home_spread is not None and home_spread < 0
        away_favored = away_spread is not None and away_spread < 0
        
        # Only show the negative spread
        favored_spread = None
        favored_side = None
        
        if home_favored:
            favored_spread = home_spread
            favored_side = 'home'
        elif away_favored:
            favored_spread = away_spread
            favored_side = 'away'
        
        # Show spread on appropriate side
        if favored_spread is not None:
            spread_text = str(favored_spread)
            font = self.fonts['detail']
            
            if favored_side == 'home':
                spread_width = draw.textlength(spread_text, font=font)
                spread_x = width - spread_width
                spread_y = 0
                self._draw_text_with_outline(draw, spread_text, (spread_x, spread_y), 
                                            font, fill=(0, 255, 0))
            else:
                spread_x = 0
                spread_y = 0
                self._draw_text_with_outline(draw, spread_text, (spread_x, spread_y), 
                                            font, fill=(0, 255, 0))
        
        # Show over/under on opposite side
        over_under = odds.get('over_under')
        if over_under is not None:
            ou_text = f"O/U: {over_under}"
            font = self.fonts['detail']
            ou_width = draw.textlength(ou_text, font=font)
            
            if favored_side == 'home':
                ou_x = 0
                ou_y = 0
            elif favored_side == 'away':
                ou_x = width - ou_width
                ou_y = 0
            else:
                ou_x = (width - ou_width) // 2
                ou_y = 0
            
            self._draw_text_with_outline(draw, ou_text, (ou_x, ou_y), 
                                        font, fill=(0, 255, 0))
```

---

## Configuration

### Old Manager Config
```json
{
  "nfl_scoreboard": {
    "show_odds": true,
    "odds_update_interval": 3600,
    "live_odds_update_interval": 60
  }
}
```

### Plugin Config (Currently Non-Functional)
```json
{
  "show_odds": true,
  "nfl": {
    "display_modes": {
      "show_odds": true
    }
  }
}
```

---

## Summary

| Feature | Old Manager | Plugin | Status |
|---------|-------------|--------|--------|
| **Config option** | ✅ | ✅ | ✅ Same |
| **OddsManager import** | ✅ OddsManager | ✅ BaseOddsManager | ✅ Implemented |
| **Odds fetching** | ✅ | ✅ | ✅ Implemented |
| **Odds drawing** | ✅ | ✅ | ✅ Implemented |
| **Works** | ✅ | ✅ | ✅ Functional |

**Current State**: The plugin **now properly fetches and displays odds** when `show_odds: true` is set in configuration.

**Implementation**: Added BaseOddsManager integration, odds fetching via `_fetch_odds()`, and odds drawing via `_draw_dynamic_odds()` method in the renderer.

