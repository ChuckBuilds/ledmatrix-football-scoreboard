# Football Scoreboard Plugin - Standalone Implementation

## Overview

This plugin has been completely rewritten to be **100% self-contained** with **NO dependencies** on LEDMatrix base classes. All football functionality is embedded directly within the plugin.

## Major Changes from v1.x

### ✅ What Changed

1. **No Base Class Dependencies**
   - ❌ No longer uses `Football` base class
   - ❌ No longer uses `FootballLive`, `SportsRecent`, `SportsUpcoming`
   - ❌ No longer uses `SportsCore`
   - ✅ All functionality embedded in plugin

2. **Flattened Configuration**
   - ❌ No nested objects (was: `nfl.enabled`)
   - ✅ Flat structure (now: `nfl_enabled`)
   - ✅ All keys at root level with prefixes
   - ✅ Works with JSON Schema validation

3. **Self-Contained ESPN API Integration**
   - ✅ Built-in HTTP session with retry logic
   - ✅ Embedded API endpoint management
   - ✅ Direct ESPN API calls
   - ✅ Custom caching logic

4. **Embedded Rendering**
   - ✅ Complete scorebug rendering
   - ✅ Logo loading and caching
   - ✅ Font management
   - ✅ All display modes (live, recent, upcoming)

### 🔧 What Stayed the Same

- ✅ ESPN API endpoints (same URLs)
- ✅ Display modes (same 9 modes)
- ✅ Game data structure
- ✅ Visual appearance and layout
- ✅ Feature parity (all features preserved)

## Architecture

### v1.x (Old - Base Class Dependent)

```
Football (base class from LEDMatrix)
├── BaseNFLManager
│   ├── NFLLiveManager (+ FootballLive mixin)
│   ├── NFLRecentManager (+ SportsRecent mixin)
│   └── NFLUpcomingManager (+ SportsUpcoming mixin)
└── BaseNCAAFBManager
    ├── NCAAFBLiveManager (+ FootballLive mixin)
    ├── NCAAFBRecentManager (+ SportsRecent mixin)
    └── NCAAFBUpcomingManager (+ SportsUpcoming mixin)

FootballScoreboardPlugin (wrapper)
└── Creates and manages base class instances
```

**Dependencies**: Football, FootballLive, SportsCore, SportsRecent, SportsUpcoming, ESPNDataSource

### v2.0 (New - Standalone)

```
BasePlugin (only dependency - plugin system interface)
└── FootballScoreboardPlugin
    ├── ESPN API Integration (embedded)
    ├── Game Data Extraction (embedded)
    ├── Logo Management (embedded)
    ├── Caching Logic (embedded)
    ├── Display Rendering (embedded)
    │   ├── Live Games
    │   ├── Recent Games
    │   └── Upcoming Games
    ├── NFL State Management
    └── NCAA FB State Management
```

**Dependencies**: None (only BasePlugin for plugin system)

## Configuration Structure

### v1.x (Nested)

```json
{
  "enabled": true,
  "nfl": {
    "enabled": true,
    "favorite_teams": ["TB", "DAL"],
    "display_modes": {
      "live": true,
      "recent": true,
      "upcoming": true
    }
  }
}
```

### v2.0 (Flattened)

```json
{
  "enabled": true,
  "nfl_enabled": true,
  "nfl_favorite_teams": ["TB", "DAL"],
  "nfl_display_modes_live": true,
  "nfl_display_modes_recent": true,
  "nfl_display_modes_upcoming": true
}
```

## File Structure

```
ledmatrix-football-scoreboard/
├── manager.py                      # Complete standalone implementation (1000+ lines)
├── manifest.json                   # Plugin metadata (no base class deps)
├── config_schema.json              # Flattened JSON schema
├── requirements.txt                # Python dependencies only
├── README.md                       # User documentation
├── STANDALONE_IMPLEMENTATION.md    # This file
├── PLUGIN_IMPLEMENTATION.md        # Technical details (legacy)
└── LICENSE                         # License file
```

## Implementation Details

### Key Components in manager.py

1. **Configuration Parser** (`_parse_config`)
   - Converts flat config to internal structured format
   - Maps `nfl_enabled` → `config['nfl']['enabled']`
   - Handles all 40+ configuration options

2. **ESPN API Client**
   - `_fetch_espn_data()` - Generic ESPN API calls
   - `_fetch_season_data()` - Full season schedule
   - `_fetch_todays_games()` - Today's games only
   - Built-in retry logic (5 attempts, backoff)

3. **Game Data Extraction** (`_extract_game_details`)
   - Parses ESPN API response
   - Extracts football-specific details:
     - Down & distance
     - Possession
     - Timeouts
     - Red zone status
     - Quarter/period
   - Handles all game states (live, recent, upcoming)

4. **State Management**
   - `nfl_state` - NFL games and indices
   - `ncaa_fb_state` - NCAA games and indices
   - Independent state for each league
   - Game rotation tracking

5. **Update Logic**
   - `_update_nfl()` - Update NFL data
   - `_update_ncaa_fb()` - Update NCAA data
   - `_update_live_games()` - Live game refresh
   - `_update_recent_games()` - Recent game filtering
   - `_update_upcoming_games()` - Upcoming game filtering
   - Smart caching (24h season, 30s live)

6. **Display Rendering**
   - `_render_game()` - Main render dispatcher
   - `_render_live_game()` - Live game scorebug
   - `_render_recent_game()` - Recent game scorebug
   - `_render_upcoming_game()` - Upcoming game scorebug
   - `_render_timeouts()` - Timeout indicators
   - `_draw_text_outline()` - Text with outline

7. **Logo Management**
   - `_load_logo()` - Load and cache logos
   - `_normalize_abbr()` - Handle special cases
   - In-memory caching
   - Automatic sizing

8. **Test Mode**
   - `_init_nfl_test_game()` - NFL test data
   - `_init_ncaa_fb_test_game()` - NCAA test data
   - Simulated live games

## Benefits of Standalone Design

### For Users
✅ Easier installation (no base class requirements)  
✅ Portable between installations  
✅ No conflicts with core updates  
✅ Clear configuration structure  
✅ Self-documenting (all code in one file)  

### For Developers
✅ No inheritance complexity  
✅ All code visible in one place  
✅ Easy to debug  
✅ Easy to modify  
✅ No breaking changes from core  
✅ Can fork and customize easily  

### For Maintainers
✅ Independent versioning  
✅ No core synchronization needed  
✅ Can update without core changes  
✅ Clear dependency management  
✅ Easier testing  

## Migration Guide

### For Users Upgrading from v1.x

**Step 1**: Backup old configuration

**Step 2**: Convert nested config to flattened:
```python
# Old (v1.x):
"nfl": {"enabled": true, "favorite_teams": ["TB"]}

# New (v2.0):
"nfl_enabled": true
"nfl_favorite_teams": ["TB"]
```

**Step 3**: Remove base class references (none needed)

**Step 4**: Install v2.0 plugin

**Step 5**: Verify functionality with test mode

### Configuration Conversion Table

| v1.x (Nested) | v2.0 (Flattened) |
|---------------|------------------|
| `nfl.enabled` | `nfl_enabled` |
| `nfl.favorite_teams` | `nfl_favorite_teams` |
| `nfl.display_modes.live` | `nfl_display_modes_live` |
| `nfl.recent_games_to_show` | `nfl_recent_games_to_show` |
| `ncaa_fb.enabled` | `ncaa_fb_enabled` |
| `ncaa_fb.favorite_teams` | `ncaa_fb_favorite_teams` |

## Performance

### Memory Usage
- **v1.x**: Multiple manager instances + base class overhead
- **v2.0**: Single plugin instance, lighter footprint

### Speed
- **v1.x**: Base class abstraction layers
- **v2.0**: Direct API calls, faster

### Caching
- **v1.x**: Shared cache through base classes
- **v2.0**: Dedicated cache per plugin, more efficient

## Testing

### Test Mode Usage

```json
{
  "enabled": true,
  "nfl_enabled": true,
  "nfl_test_mode": true,
  "ncaa_fb_enabled": true,
  "ncaa_fb_test_mode": true
}
```

Test mode provides:
- Simulated live game (TB vs DAL for NFL, UGA vs AUB for NCAA)
- All display features functional
- No API calls required
- Instant verification

### Verify Installation

1. Enable test mode
2. Set display mode to `nfl_live` or `ncaa_fb_live`
3. Verify scorebug displays correctly
4. Check logs for initialization messages

## Troubleshooting

### Common Issues

**Issue**: No games displaying  
**Solution**: Check flattened config keys (use underscores)

**Issue**: Import errors  
**Solution**: Ensure BasePlugin available (only dependency)

**Issue**: API errors  
**Solution**: Check ESPN API availability, verify internet

**Issue**: Missing logos  
**Solution**: Verify logo directory paths in config

### Debug Mode

Enable detailed logging:
```python
import logging
logging.getLogger('FootballScoreboardPlugin').setLevel(logging.DEBUG)
```

## Future Enhancements

Possible additions that maintain standalone nature:

1. ✅ Additional sports leagues (XFL, USFL, CFL)
2. ✅ Custom display layouts (user templates)
3. ✅ Advanced statistics display
4. ✅ Play-by-play scrolling text
5. ✅ Team-specific color schemes
6. ✅ Multiple game split-screen
7. ✅ Playoff bracket displays
8. ✅ Historical game archives

All can be added to the plugin without external dependencies.

## API Reference

### ESPN API Endpoints

**NFL**:
```
URL: https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard
Season: ?dates=20240801-20250301&limit=1000
Today: ?dates=20241017&limit=1000
```

**NCAA Football**:
```
URL: https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard
Season: ?dates=20240801-20250201&limit=1000
Today: ?dates=20241017&limit=1000
```

### Response Format

ESPN returns:
```json
{
  "events": [
    {
      "id": "game_id",
      "date": "2024-10-17T20:00Z",
      "competitions": [{
        "competitors": [
          {"homeAway": "home", "team": {...}, "score": "21"},
          {"homeAway": "away", "team": {...}, "score": "17"}
        ],
        "status": {...},
        "situation": {...}
      }]
    }
  ]
}
```

## Support & Contribution

- **Issues**: Report on GitHub
- **Documentation**: See README.md
- **Source**: Single file (manager.py)
- **License**: Same as LEDMatrix

## Conclusion

The v2.0 standalone implementation provides:
- ✅ Complete feature parity with v1.x
- ✅ No external dependencies (except BasePlugin)
- ✅ Flattened, easy-to-use configuration
- ✅ All functionality in one file
- ✅ Better performance
- ✅ Easier maintenance

This is a complete, production-ready, standalone football scoreboard plugin.

