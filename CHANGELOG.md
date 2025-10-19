# Changelog

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

