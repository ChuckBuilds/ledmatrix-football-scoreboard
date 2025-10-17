# Football Scoreboard Plugin - Implementation Summary

## Overview

This plugin has been completely rewritten to match the exact functionality of the core LEDMatrix NFL and NCAA FB managers. It provides full feature parity with the built-in managers while operating as a standalone plugin.

## Architecture

### Manager Class Hierarchy

The plugin implements the same class structure as the core managers:

```
BasePlugin (from plugin system)
└── FootballScoreboardPlugin
    ├── Creates and manages manager instances
    └── Delegates to appropriate managers

Football (base class)
├── BaseNFLManager
│   ├── NFLLiveManager (+ FootballLive)
│   ├── NFLRecentManager (+ SportsRecent)
│   └── NFLUpcomingManager (+ SportsUpcoming)
│
└── BaseNCAAFBManager
    ├── NCAAFBLiveManager (+ FootballLive)
    ├── NCAAFBRecentManager (+ SportsRecent)
    └── NCAAFBUpcomingManager (+ SportsUpcoming)
```

### Key Components

1. **Base Managers** (`BaseNFLManager`, `BaseNCAAFBManager`)
   - Handle league-specific API endpoints
   - Manage background data fetching
   - Configure display modes and settings
   - Implement season data caching

2. **Live Managers** (`NFLLiveManager`, `NCAAFBLiveManager`)
   - Fetch and display live games
   - Update every 30 seconds (configurable)
   - Show real-time scores, quarters, time
   - Display down/distance, possession, timeouts
   - Support test mode for development

3. **Recent Managers** (`NFLRecentManager`, `NCAAFBRecentManager`)
   - Display recently completed games (last 21 days)
   - Show final scores and game outcomes
   - Rotate through multiple games
   - Filter by favorite teams

4. **Upcoming Managers** (`NFLUpcomingManager`, `NCAAFBUpcomingManager`)
   - Display scheduled games
   - Show game date and time
   - Filter and prioritize by favorite teams
   - Limit to configurable number of games

5. **Plugin Wrapper** (`FootballScoreboardPlugin`)
   - Extends `BasePlugin` for plugin system integration
   - Creates manager instances based on configuration
   - Routes update() and display() calls to appropriate managers
   - Aggregates info for web UI

## Feature Parity with Core Managers

### ✅ Complete Feature Match

- **ESPN API Integration**: Same endpoints and data structures
- **Background Data Fetching**: Non-blocking API calls with threading
- **Logo Loading**: Automatic download and caching of team logos
- **Scorebug Rendering**: Identical display layouts and positioning
- **Down & Distance**: Full play-by-play information display
- **Possession Indicator**: Football icon showing which team has the ball
- **Timeout Tracking**: Visual bars showing remaining timeouts
- **Red Zone Detection**: Special highlighting in red zone situations
- **Scoring Events**: Touchdown, field goal, and PAT notifications
- **Team Records**: Display win-loss records when enabled
- **Team Rankings**: Display AP/CFP rankings (NCAA) when enabled
- **Odds Integration**: Show betting lines and over/under
- **Favorite Team Filtering**: Prioritize and filter by favorites
- **Test Mode**: Built-in test games for development
- **Season Caching**: Cache entire season data for efficiency
- **Today's Games**: Fast fetch for live game updates
- **Game Switching**: Automatic rotation through multiple games

## Configuration Structure

### Hierarchical Configuration

The plugin uses a two-level configuration structure:

```
Global Settings
├── enabled (bool)
├── display_duration (number)
├── show_records (bool)
└── show_ranking (bool)

League Settings (nfl, ncaa_fb)
├── enabled (bool)
├── favorite_teams (array)
├── display_modes
│   ├── live (bool)
│   ├── recent (bool)
│   └── upcoming (bool)
├── recent_games_to_show (number)
├── upcoming_games_to_show (number)
├── show_favorite_teams_only (bool)
├── show_all_live (bool)
├── show_odds (bool)
├── test_mode (bool)
├── update_interval_seconds (number)
├── live_update_interval (number)
├── live_game_duration (number)
├── logo_dir (string)
└── background_service
    ├── enabled (bool)
    ├── request_timeout (number)
    ├── max_retries (number)
    └── priority (number)
```

### Configuration Mapping

The plugin translates its configuration to the format expected by the base classes:

```python
# Plugin receives:
config = {
  "nfl": {
    "enabled": true,
    "favorite_teams": ["TB", "DAL"],
    "display_modes": {"live": true, "recent": true, "upcoming": true},
    ...
  }
}

# Transforms to manager format:
nfl_manager_config = {
  "nfl_scoreboard": {
    "enabled": true,
    "display_modes": {
      "nfl_live": true,
      "nfl_recent": true,
      "nfl_upcoming": true
    },
    "favorite_teams": ["TB", "DAL"],
    ...
  }
}
```

## Display Modes

### Nine Supported Modes

1. **Generic Modes** (use first available league)
   - `football_live`
   - `football_recent`
   - `football_upcoming`

2. **NFL-Specific Modes**
   - `nfl_live`
   - `nfl_recent`
   - `nfl_upcoming`

3. **NCAA FB-Specific Modes**
   - `ncaa_fb_live`
   - `ncaa_fb_recent`
   - `ncaa_fb_upcoming`

### Display Mode Routing

```python
display_mode = "football_live"
# Plugin finds first available live manager:
# 1. Check for nfl_live manager
# 2. Check for ncaa_fb_live manager
# 3. Use first found

display_mode = "nfl_live"
# Plugin uses specific NFL live manager
```

## API Endpoints

### NFL
- Base URL: `https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard`
- Season Data: `?dates=20240801-20250301&limit=1000`
- Today's Games: `?dates=20241017&limit=1000`

### NCAA Football
- Base URL: `https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard`
- Season Data: `?dates=20240801-20250201&limit=1000`
- Today's Games: `?dates=20241017&limit=1000`

## Data Flow

### Initialization
1. Plugin initialized by LEDMatrix plugin system
2. Plugin reads configuration
3. Creates manager instances for enabled leagues/modes
4. Managers initialize base classes (Football, FootballLive, etc.)
5. Managers configure background service
6. Managers load fonts and assets

### Update Cycle
1. LEDMatrix calls `plugin.update()`
2. Plugin calls `manager.update()` for each manager
3. Manager checks if update needed (based on interval)
4. Manager fetches data:
   - Live: Today's games only
   - Recent/Upcoming: Full season cache
5. Manager processes games:
   - Extract game details
   - Filter by favorites (if enabled)
   - Fetch odds (if enabled)
   - Fetch rankings (if enabled)
6. Manager updates internal game list

### Display Cycle
1. LEDMatrix calls `plugin.display(display_mode)`
2. Plugin routes to appropriate manager
3. Manager checks for games to display
4. Manager handles game rotation (if multiple games)
5. Manager calls `_draw_scorebug_layout(game)`
6. Manager renders to display_manager
7. Manager calls `display_manager.update_display()`

## Background Service

### Asynchronous Data Fetching

The plugin uses the LEDMatrix background service for non-blocking API calls:

```python
request_id = background_service.submit_fetch_request(
    sport="nfl",
    year=2024,
    url=ESPN_NFL_SCOREBOARD_URL,
    cache_key="nfl_schedule_2024",
    params={"dates": "20240801-20250301", "limit": 1000},
    headers=headers,
    timeout=30,
    max_retries=3,
    priority=2,
    callback=fetch_callback
)
```

### Benefits
- Non-blocking: Display continues while data fetches
- Retries: Automatic retry on failure
- Priority: Configurable priority for resource management
- Callbacks: Notification when fetch completes

## Caching Strategy

### Multi-Level Caching

1. **Season Cache** (24 hours)
   - Cache key: `nfl_schedule_2024` or `ncaafb_schedule_2024`
   - Contains all games for entire season
   - Used by Recent and Upcoming managers
   - Refreshed daily or on cache miss

2. **Today's Games** (5 minutes)
   - Cache key: `nfl_todays_games_20241017`
   - Contains only today's games
   - Used by Live managers
   - Refreshed every 30 seconds during live games

3. **Logo Cache** (in-memory)
   - Cache key: team abbreviation
   - Contains PIL Image objects
   - Persists for session lifetime
   - Automatic download on cache miss

4. **Rankings Cache** (1 hour)
   - Cache key: per-manager instance
   - Contains team rankings dictionary
   - Refreshed hourly
   - Used for display if enabled

## Testing

### Test Mode

Enable test mode for development without live data:

```json
{
  "nfl": {
    "test_mode": true
  }
}
```

Test mode provides:
- Simulated live game with test teams
- Clock countdown simulation
- Down & distance changes
- Possession changes
- All display features functional

## Performance Optimizations

### Memory Efficient
- Single background worker thread
- Cached season data shared across managers
- Logo caching prevents repeated downloads
- Smart update intervals prevent excessive API calls

### Network Efficient
- Background fetching doesn't block display
- Automatic retry with backoff
- Season caching reduces API calls
- Only fetch today's games for live updates

### Display Efficient
- Pre-rendered logos
- Font caching
- Efficient PIL image operations
- Smart redraw only when needed

## Error Handling

### Graceful Degradation

1. **API Failures**
   - Use cached data if available
   - Log warning, continue with old data
   - Retry with exponential backoff

2. **Missing Logos**
   - Attempt automatic download
   - Create placeholder if download fails
   - Display error message on screen

3. **Invalid Configuration**
   - Log error with details
   - Skip invalid settings
   - Continue with defaults

4. **Network Timeouts**
   - Respect timeout settings
   - Use retry mechanism
   - Fall back to cached data

## Compatibility

### LEDMatrix Version
- Minimum: 2.0.0
- Tested: 2.0.0+
- Requires: Plugin system support

### Python Version
- Minimum: 3.8
- Recommended: 3.9+

### Dependencies
- `requests>=2.31.0`
- `Pillow>=10.0.0`
- `pytz>=2023.3`

### Base Classes
- `src.base_classes.football.Football`
- `src.base_classes.football.FootballLive`
- `src.base_classes.sports.SportsRecent`
- `src.base_classes.sports.SportsUpcoming`

## Files

### Core Files
- `manager.py` - Main plugin implementation (650+ lines)
- `manifest.json` - Plugin metadata and display modes
- `config_schema.json` - JSON Schema for configuration validation
- `requirements.txt` - Python dependencies

### Documentation
- `README.md` - User-facing documentation
- `PLUGIN_IMPLEMENTATION.md` - This file (technical details)
- `example_config.json` - Example configuration with all options

## Comparison with Core Managers

### Identical Functionality

| Feature | Core Managers | Plugin | Notes |
|---------|--------------|--------|-------|
| ESPN API | ✅ | ✅ | Same endpoints |
| Background Fetch | ✅ | ✅ | Same service |
| Live Games | ✅ | ✅ | Identical display |
| Recent Games | ✅ | ✅ | Identical display |
| Upcoming Games | ✅ | ✅ | Identical display |
| Down/Distance | ✅ | ✅ | Full play info |
| Possession | ✅ | ✅ | Football icon |
| Timeouts | ✅ | ✅ | Visual bars |
| Red Zone | ✅ | ✅ | Color highlight |
| Scoring Events | ✅ | ✅ | TD/FG/PAT |
| Records | ✅ | ✅ | Win-loss |
| Rankings | ✅ | ✅ | AP/CFP (NCAA) |
| Odds | ✅ | ✅ | Spread/O-U |
| Logo Caching | ✅ | ✅ | Auto-download |
| Test Mode | ✅ | ✅ | Simulated games |

### Key Differences

| Aspect | Core Managers | Plugin |
|--------|--------------|--------|
| Installation | Built-in | User-installable |
| Configuration | Global config | Plugin config |
| Updates | LEDMatrix updates | Plugin updates |
| Activation | Always available | Must be installed |
| Customization | Core code changes | Plugin modifications |

## Future Enhancements

### Potential Additions
1. ✅ Custom display layouts (user-configurable positions)
2. ✅ Additional sports leagues (XFL, CFL, etc.)
3. ✅ Enhanced statistics display
4. ✅ Play-by-play text scrolling
5. ✅ Game highlights/summaries
6. ✅ Team-specific color schemes
7. ✅ Multiple game comparison view
8. ✅ Playoff bracket display

### Backward Compatibility
All future enhancements will maintain backward compatibility with existing configurations.

## Conclusion

This plugin provides complete feature parity with the core LEDMatrix NFL and NCAA FB managers while offering the flexibility of a standalone, user-installable plugin. Users can expect identical functionality and display quality to the built-in managers.

The modular architecture makes it easy to add new leagues or customize behavior without modifying core LEDMatrix code.

