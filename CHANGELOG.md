# Changelog

## [1.3.0] - 2025-10-20

### Fixed
- **CRITICAL: Recent Games Not Showing**: Added date range parameters to ESPN API calls
  - Now fetches last 21 days + next 14 days of games (matching old implementation)
  - Previously only fetched "today's" games, missing Saturday's UGA game
  - `recent_games_to_show` means "N games per favorite team", not "N days ago"
  
### Changed
- ESPN API now called with `?dates=YYYYMMDD-YYYYMMDD` parameter
- Matches old base class behavior (21-day lookback for recent games)

### Technical Details
- Old implementation: fetched 21 days of data, then filtered to N most recent games per team
- New implementation: same 21-day fetch, proper filtering by favorite teams
- This fixes UGA's Saturday game not appearing in recent games

## [1.2.2] - 2025-10-20

### Added
- **Deep Game Structure Logging**: Added comprehensive logging to show exact game dict structure when checking favorites
  - Shows all keys in game dict
  - Shows all keys in home_team and away_team dicts
  - Shows actual abbreviation values being compared
  - Shows favorites list and membership check results
  - Limited to first 3 checks to avoid log spam

### Purpose
- Compare with old base class implementation to identify structural differences
- Diagnose why UGA and TB aren't matching when they worked in old managers

## [1.2.1] - 2025-10-20

### Added
- **Enhanced Team Abbreviation Logging**: Added detailed debug logging to show exact team abbreviations returned by ESPN API
  - Shows original and uppercase versions of team abbreviations
  - Shows explicit membership checks against favorites list
  - Helps diagnose why specific teams aren't matching (e.g., if ESPN uses "GEOR" instead of "UGA")

### Changed
- Set logger to INFO level by default to reduce DEBUG noise

## [1.2.0] - 2025-10-20

### Fixed
- **CRITICAL: Favorite Teams Array Handling**: Added robust normalization for favorite_teams configuration
  - Handles both array and comma-separated string formats from web UI
  - Normalizes all team abbreviations to UPPERCASE for consistent matching
  - Case-insensitive team matching (TB, tb, Tb all work)
- **Configuration Validation**: Enhanced config loading with detailed logging
  - Logs RAW config values with types to diagnose web UI saving issues
  - Logs normalized values to show what plugin is actually using
  - Shows enabled/disabled status for each league

### Technical Details
- Added `normalize_favorite_teams()` helper function
- Updated `_is_favorite_game()` to use uppercase comparison
- This ensures UGA, TB, and all favorite teams work regardless of how web UI saves them

## [1.1.9] - 2025-10-20

### Added
- **Startup Configuration Logging**: Added INFO-level logging on startup to show:
  - Which leagues are enabled (NFL, NCAA FB)
  - How many favorite teams are configured for each league
  - Actual favorite team lists (e.g., `['TB']`, `['UGA']`)
- **Troubleshooting**: Immediately visible in logs to diagnose configuration issues

## [1.1.8] - 2025-10-20

### Added
- **Enhanced Debug Logging**: Added detailed filtering logs to diagnose game visibility issues
  - Shows total games available before filtering
  - Logs first 3 games being evaluated with their favorite status
  - Shows favorite teams list and filtering settings for each game
  - Displays final filtered count
- **Troubleshooting**: Helps identify why UGA or other favorite teams aren't showing

## [1.1.7] - 2025-10-20

### Fixed
- **CRITICAL: Favorite Team Filtering**: Added missing favorite team filter logic matching original managers
  - Now properly checks `show_favorite_teams_only` setting
  - Respects `show_all_live` for showing all live games regardless of favorites
  - Filters live, recent, and upcoming games based on favorite teams
- **Timeout Display**: Timeouts now only display for live games (not FINAL or UPCOMING)
- **Debug Logging**: Added detailed game breakdown logging (NFL vs NCAA FB, Live vs Recent vs Upcoming)
  - Helps diagnose why games aren't appearing

### Technical Details
- Filtering logic now matches `SportsLive.update()` from base classes (line 1229)
- Timeout indicators only drawn when `status.state == 'in'` (live games only)
- Enhanced logging shows per-league and per-state game counts

## [1.1.6] - 2025-10-20

### Fixed
- **Live Priority System**: Implemented `has_live_content()` method to properly integrate with display controller
- **Display Logic**: Plugin now only shows "football_live" mode when there are actual live games
- **No More "No Live Games"**: Plugin won't be called when there are no live games to display
- **Mode Filtering**: Added `get_live_modes()` to only show live mode during live priority takeover

## [1.1.5] - 2025-10-20

### Fixed
- **Logo Sizing**: Fixed logo size to match original managers - now uses `display_width/height * 1.5`
- **Visual Parity**: Logos now display at the correct size matching NFL/NCAA FB managers exactly
- **Before**: Logos were too small (20x20 max)
- **After**: Logos properly scaled to display dimensions (96x96 for 64x64 matrix)

## [1.1.4] - 2025-10-20

### Changed
- **Reduced Log Noise**: Throttled repetitive DEBUG logs to only appear every 5 minutes
- **Smarter Logging**: "Updated football data" now only logs when game count changes or every 5 minutes
- **Cleaner Logs**: Removed "Logo not found" debug messages, fail silently and use text fallback
- **Performance**: Less log I/O improves overall system performance

## [1.1.3] - 2025-10-20

### Fixed
- **Logo Loading Case Sensitivity**: Fixed logo loading to try uppercase, lowercase, and original case variations
- **Missing Logos**: Now correctly finds logo files regardless of case (DET.png vs det.png)
- **Logo Fallback**: Improved logo search to match original managers' behavior

## [1.1.2] - 2025-10-19

### Fixed
- **Logo Loading**: Fixed team logo loading by using absolute paths to LEDMatrix assets directory
- **Path Resolution**: Added logic to find LEDMatrix project root and resolve logo paths correctly
- **Debug Logging**: Added better debug logging for logo loading failures
- **Cross-Platform**: Improved path handling for different operating systems

## [1.1.1] - 2025-10-19

### Fixed
- **Upcoming Game Display**: Fixed upcoming games to use proper layout matching original NCAA FB manager
- **Layout Separation**: Added separate `_draw_upcoming_layout()` method for upcoming games vs live/recent games
- **Date/Time Parsing**: Proper parsing and display of game date and time for upcoming games
- **Odds Display**: Added `_draw_dynamic_odds()` method for proper odds display on upcoming games
- **Visual Parity**: Upcoming games now show "Next Game", date, time, team logos, and rankings exactly like original managers

## [1.1.0] - 2025-10-19

### Changed
- **MAJOR VISUAL UPDATE**: Complete rewrite of rendering to match original NFL/NCAA FB managers exactly
  - Added proper font loading with PressStart2P and 4x6 fonts
  - Use `textlength()` for accurate text measurement instead of approximations
  - Updated `_draw_text_with_outline()` to accept font parameter (matching base class API)
  
### Added
- Team records display (e.g., "8-1", "10-0")
- Team rankings display for NCAA (e.g., "#1", "#5")
- Halftime detection and display
- Proper possession indicator mapping (home/away based on team IDs)
- Records/rankings positioning in bottom corners above timeouts

### Fixed
- Possession indicator now correctly identifies home vs away team
- Timeout defaults to 3 if not specified (matching football rules)
- All text rendering now uses proper fonts for consistent appearance
- Text positioning uses accurate measurements instead of character-count approximations

### Technical Details
- Fonts loaded: PressStart2P (8px, 10px), 4x6 (6px)
- Rankings cache infrastructure added (for NCAA rankings)
- Visual layout now pixel-perfect match to original managers
- Halftime status extracted from ESPN API

## [1.0.10] - 2025-10-19

### Fixed
- **CRITICAL**: Fixed type comparison error in cache validation
  - Added explicit type conversion for all numeric configuration values
  - Ensures `update_interval_seconds`, `recent_games_to_show`, `upcoming_games_to_show`, and `display_duration` are proper numbers
  - Fixes "'<' not supported between instances of 'float' and 'str'" error

## [1.0.9] - 2025-10-19

### Fixed
- **CRITICAL**: Fixed cache manager API compatibility
  - Removed invalid `ttl` parameter from `cache_manager.set()` call
  - Fixes "CacheManager.set() got an unexpected keyword argument 'ttl'" error
  - Plugin can now successfully cache game data

## [1.0.8] - 2025-10-19

### Fixed
- **CRITICAL**: Added missing `class_name` field to manifest
  - Plugin system now correctly identifies the Python class to load
  - Fixes "No class_name in manifest" error

## [1.0.7] - 2025-10-19

### Removed
- Removed redundant `enabled` field from config schema
  - Plugin enabled state is now managed solely by the plugin system
  - This eliminates confusion from having two "enabled" toggles in the UI
  - League-specific enabled fields (`nfl_enabled`, `ncaa_fb_enabled`) remain unchanged

### Fixed
- Configuration UI no longer shows duplicate enabled toggle

## [1.0.6] - 2025-10-19

### Changed
- **Per-League Configuration**: All display settings are now configurable separately for NFL and NCAA Football
  - Added `nfl_show_records`, `ncaa_fb_show_records` - Show team records per league
  - Added `nfl_show_ranking`, `ncaa_fb_show_ranking` - Show team rankings per league (NCAA defaults to true)
  - Added `nfl_show_odds`, `ncaa_fb_show_odds` - Show betting odds per league
  - Added `nfl_show_favorite_teams_only`, `ncaa_fb_show_favorite_teams_only` - Filter by favorites per league
  - Added `nfl_show_all_live`, `ncaa_fb_show_all_live` - Override favorites for live games per league
- Removed global settings in favor of per-league control

### Benefits
- Configure rankings to show for NCAA but not NFL (or vice versa)
- Different odds display preferences for professional vs college football
- Independent favorite team filtering for each league

## [1.0.5] - 2025-10-19

### Added
- `show_odds` - Toggle to show/hide betting odds for games
- `show_favorite_teams_only` - Control whether to show only favorite teams or all games
- `show_all_live` - Override favorites to show all live games

### Fixed
- Restored missing configuration options that were removed in 1.0.4

## [1.0.4] - 2025-10-19

### Changed
- **BREAKING CHANGE**: Flattened configuration structure to remove nested objects
  - Replaced `nfl.enabled` with `nfl_enabled`
  - Replaced `nfl.favorite_teams` with `nfl_favorite_teams`
  - Replaced `nfl.display_modes.live` with `nfl_show_live`
  - Replaced `nfl.display_modes.recent` with `nfl_show_recent`
  - Replaced `nfl.display_modes.upcoming` with `nfl_show_upcoming`
  - Replaced `nfl.recent_games_to_show` with `nfl_recent_games_to_show`
  - Replaced `nfl.upcoming_games_to_show` with `nfl_upcoming_games_to_show`
  - Same pattern applied for NCAA FB with `ncaa_fb_*` prefixes
  - Removed `background_service` nested configuration (handled internally)

### Fixed
- Configuration UI now properly displays all fields instead of empty text boxes
- Web interface can now render and save all configuration options

### Technical Details
- Plugin internally rebuilds nested structure from flattened config for backward compatibility
- All league-specific settings now use prefixed flat keys
- Logo directories are automatically determined from league configuration
- Update intervals are shared globally across all leagues

## [1.0.3] - 2025-10-19

### Initial Release
- Support for NFL and NCAA Football games
- Live, recent, and upcoming game modes
- Team logos and professional scorebug layout
- Down/distance and possession indicators
- Timeout tracking
- Scoring event detection

