# Football Scoreboard Plugin - Standalone

A **completely self-contained** football scoreboard plugin for LEDMatrix that displays live, recent, and upcoming football games across NFL and NCAA Football. This plugin has **NO dependencies** on LEDMatrix base classes - all functionality is embedded within the plugin itself.

## Key Features

### 🏈 Full Football Experience
- **NFL & NCAA Football Support**: Track games from both professional and college football
- **Live Game Tracking**: Real-time scores, quarters, clock, down & distance
- **Recent Games**: Show completed games with final scores
- **Upcoming Games**: Display scheduled games with dates and times
- **Favorite Team Priority**: Filter and prioritize games by your favorite teams

### ⚡ Standalone Architecture  
- **No Base Class Dependencies**: All functionality self-contained
- **No External Dependencies**: Only requires standard LEDMatrix plugin system
- **Easy Installation**: Drop-in plugin with no additional setup
- **Portable**: Can be moved between LEDMatrix installations easily

### 🎮 Advanced Features
- **Football-Specific Display**:
  - Down & distance with red zone indicator
  - Possession indicator (football icon)
  - Timeout tracking (visual bars)
  - Team logos with automatic loading
  - Quarter/period display with overtime support
  
- **Smart Data Management**:
  - Automatic API caching (24-hour season cache)
  - Intelligent update intervals (30s live, 60s schedule)
  - Background data fetching
  - Logo caching in memory

- **Test Mode**: Built-in test games for development and demonstration

## Display Modes

The plugin supports **nine display modes**:

### Generic Modes
- `football_live` - Live games from any enabled league
- `football_recent` - Recent games from any enabled league  
- `football_upcoming` - Upcoming games from any enabled league

### League-Specific Modes
- `nfl_live`, `nfl_recent`, `nfl_upcoming` - NFL-only displays
- `ncaa_fb_live`, `ncaa_fb_recent`, `ncaa_fb_upcoming` - NCAA Football-only displays

## Configuration

### ⚠️ Important: Flattened Configuration Structure

This plugin uses a **completely flat configuration structure** with NO nested objects. All configuration keys are at the root level with prefixes to indicate their category.

### Configuration Format

```json
{
  "enabled": true,
  "display_duration": 15,
  "show_records": false,
  "show_ranking": false,
  
  "nfl_enabled": true,
  "nfl_favorite_teams": ["TB", "DAL", "GB"],
  "nfl_display_modes_live": true,
  "nfl_display_modes_recent": true,
  "nfl_display_modes_upcoming": true,
  "nfl_recent_games_to_show": 5,
  "nfl_upcoming_games_to_show": 10,
  "nfl_show_favorite_teams_only": true,
  "nfl_show_all_live": false,
  "nfl_show_odds": true,
  "nfl_test_mode": false,
  "nfl_update_interval_seconds": 60,
  "nfl_live_update_interval": 30,
  "nfl_live_game_duration": 30,
  "nfl_logo_dir": "assets/sports/nfl_logos",
  
  "ncaa_fb_enabled": true,
  "ncaa_fb_favorite_teams": ["UGA", "AUB", "BAMA"],
  "ncaa_fb_display_modes_live": true,
  "ncaa_fb_display_modes_recent": true,
  "ncaa_fb_display_modes_upcoming": true,
  "ncaa_fb_recent_games_to_show": 5,
  "ncaa_fb_upcoming_games_to_show": 10,
  "ncaa_fb_show_favorite_teams_only": true,
  "ncaa_fb_show_all_live": false,
  "ncaa_fb_show_odds": true,
  "ncaa_fb_test_mode": false,
  "ncaa_fb_update_interval_seconds": 60,
  "ncaa_fb_live_update_interval": 30,
  "ncaa_fb_live_game_duration": 30,
  "ncaa_fb_logo_dir": "assets/sports/ncaa_logos"
}
```

### Configuration Reference

#### Global Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | boolean | `true` | Enable/disable entire plugin |
| `display_duration` | number | `15` | Seconds to display each game (5-60) |
| `show_records` | boolean | `false` | Display team win-loss records |
| `show_ranking` | boolean | `false` | Display AP/CFP rankings (NCAA) |

#### NFL Settings (prefix: `nfl_`)

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `nfl_enabled` | boolean | `true` | Enable NFL games |
| `nfl_favorite_teams` | array | `[]` | Favorite NFL teams (e.g., ["TB", "DAL"]) |
| `nfl_display_modes_live` | boolean | `true` | Show live NFL games |
| `nfl_display_modes_recent` | boolean | `true` | Show recent NFL games |
| `nfl_display_modes_upcoming` | boolean | `true` | Show upcoming NFL games |
| `nfl_recent_games_to_show` | integer | `5` | Max recent games (1-20) |
| `nfl_upcoming_games_to_show` | integer | `10` | Max upcoming games (1-20) |
| `nfl_show_favorite_teams_only` | boolean | `true` | Filter to favorites only |
| `nfl_show_all_live` | boolean | `false` | Show all live games |
| `nfl_show_odds` | boolean | `true` | Display betting odds |
| `nfl_test_mode` | boolean | `false` | Enable test mode |
| `nfl_update_interval_seconds` | integer | `60` | Data refresh interval (30-86400) |
| `nfl_live_update_interval` | integer | `30` | Live game refresh (10-300) |
| `nfl_live_game_duration` | number | `30` | Seconds per live game (10-120) |
| `nfl_logo_dir` | string | `"assets/sports/nfl_logos"` | Logo directory path |

#### NCAA Football Settings (prefix: `ncaa_fb_`)

All NCAA settings follow the same pattern as NFL with the `ncaa_fb_` prefix:
- `ncaa_fb_enabled`
- `ncaa_fb_favorite_teams`
- `ncaa_fb_display_modes_live`
- `ncaa_fb_display_modes_recent`
- `ncaa_fb_display_modes_upcoming`
- ... (same structure as NFL)

Default logo directory: `"assets/sports/ncaa_logos"`

## Team Abbreviations

### NFL Teams (32 teams)

**AFC East**: BUF, MIA, NE, NYJ  
**AFC North**: BAL, CIN, CLE, PIT  
**AFC South**: HOU, IND, JAX, TEN  
**AFC West**: DEN, KC, LV, LAC  

**NFC East**: DAL, NYG, PHI, WAS  
**NFC North**: CHI, DET, GB, MIN  
**NFC South**: ATL, CAR, NO, TB  
**NFC West**: ARI, LAR, SF, SEA  

### NCAA Football Teams (Popular)

**SEC**: UGA, AUB, BAMA, LSU, FLA, TENN, MSST, OLE, ARK, SCAR, MIZ, TAMU, UK, VAN  
**ACC**: CLEM, FSU, MIAMI, UNC, NCST, UVA, VT, GT, DUKE, WAKE, BC, LOU, PITT, SYR  
**Big Ten**: OSU, MICH, PSU, MSU, WIS, IOWA, MINN, ILL, NW, PUR, IND, NEB, MD, RUT  
**Big 12**: OU, TEX, OKST, TCU, BAY, TTU, WVU, ISU, KU, KSU  
**Pac-12**: USC, UCLA, ORE, WASH, STAN, CAL, UTAH, COLO, ASU, ARIZ, WSU, ORST  

*Note: Abbreviations may vary. Check ESPN's API for current abbreviations.*

## Data Source

Game data is fetched from ESPN's public API endpoints:
- **NFL**: `https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard`
- **NCAA Football**: `https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard`

### Caching Strategy
- **Season Data**: Cached for 24 hours (full schedule)
- **Live Games**: Refreshed every 30 seconds (today's games only)
- **Logos**: Cached in memory for session lifetime

## Display Features

### Live Games
- Team logos (left: away, right: home)
- Real-time scores (centered)
- Quarter/period and clock (top)
- Down & distance with red zone indicator
- Possession indicator (football icon)
- Timeout bars (3 per team)
- Team records/rankings (if enabled)

### Recent Games
- Team logos (left: away, right: home)
- Final scores (centered)
- "Final" or "Final/OT" status (top)
- Team records/rankings (if enabled)

### Upcoming Games
- Team logos (left: away, right: home)
- "Next Game" label (top)
- Game date (centered)
- Game time (below date)
- Team records/rankings (if enabled)

## Dependencies

### Required
- **LEDMatrix**: Version 2.0.0+ with plugin system
- **Python**: 3.8+
- **Python Packages**: `requests`, `pytz`, `Pillow`

### NOT Required
- ❌ No LEDMatrix base classes
- ❌ No football base classes
- ❌ No sports base classes
- ✅ Completely self-contained!

## Installation

### Via Plugin Store (Recommended)
1. Open LEDMatrix web interface
2. Navigate to Plugin Store
3. Search for "Football Scoreboard"
4. Click Install
5. Configure your settings
6. Enable the plugin

### Manual Installation
1. Copy plugin directory to LEDMatrix plugins folder
2. Install dependencies: `pip install -r requirements.txt`
3. Configure plugin in web interface
4. Restart LEDMatrix

## Configuration Examples

### NFL Only (Simple)
```json
{
  "enabled": true,
  "nfl_enabled": true,
  "nfl_favorite_teams": ["TB", "KC", "BUF"],
  "ncaa_fb_enabled": false
}
```

### Both Leagues (Complete)
```json
{
  "enabled": true,
  "display_duration": 20,
  "show_records": true,
  "nfl_enabled": true,
  "nfl_favorite_teams": ["TB", "DAL"],
  "nfl_show_favorite_teams_only": true,
  "ncaa_fb_enabled": true,
  "ncaa_fb_favorite_teams": ["UGA", "BAMA"],
  "ncaa_fb_show_favorite_teams_only": true
}
```

### Test Mode (Development)
```json
{
  "enabled": true,
  "nfl_enabled": true,
  "nfl_test_mode": true,
  "ncaa_fb_enabled": true,
  "ncaa_fb_test_mode": true
}
```

## Architecture

### Self-Contained Design

This plugin includes all functionality inline:
- ✅ ESPN API integration
- ✅ Game data extraction and parsing
- ✅ Logo loading and caching
- ✅ Font management
- ✅ Scorebug rendering
- ✅ HTTP session with retry logic
- ✅ Data caching
- ✅ Test mode support

### No External Dependencies

The plugin only inherits from `BasePlugin` for plugin system integration. All football-specific functionality is implemented within the plugin itself.

```
BasePlugin (plugin system interface)
└── FootballScoreboardPlugin
    ├── _fetch_espn_data()
    ├── _extract_game_details()
    ├── _load_logo()
    ├── _render_game()
    └── ... (all functionality embedded)
```

## Troubleshooting

### No Games Showing
- Check that leagues are enabled (`nfl_enabled`, `ncaa_fb_enabled`)
- Verify favorite teams are configured correctly
- Check `show_favorite_teams_only` setting
- Review logs for API errors

### Missing Logos
- Ensure logo directories exist
- Check logo file naming (team abbreviation + .png)
- Verify file permissions

### API Errors
- Check internet connectivity
- Verify ESPN API availability
- Review `update_interval_seconds` settings

### Test Mode
Enable test mode to verify display functionality:
```json
{
  "nfl_test_mode": true,
  "ncaa_fb_test_mode": true
}
```

## Version History

### v2.0.0 (Current)
- Complete rewrite as standalone plugin
- No base class dependencies
- Flattened configuration structure
- Embedded all football functionality
- Self-contained ESPN API integration
- Improved caching and performance

### v1.x (Legacy)
- Depended on LEDMatrix base classes
- Nested configuration structure
- Required football and sports base classes

## Support

- **GitHub Issues**: [LEDMatrix Issues](https://github.com/ChuckBuilds/LEDMatrix/issues)
- **Documentation**: [LEDMatrix Wiki](https://github.com/ChuckBuilds/LEDMatrix/wiki)

## License

This plugin follows the same license as the main LEDMatrix project.
