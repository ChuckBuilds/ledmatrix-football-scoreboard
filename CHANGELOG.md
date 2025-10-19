# Changelog

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

