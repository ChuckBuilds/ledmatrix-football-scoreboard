-----------------------------------------------------------------------------------
### Connect with ChuckBuilds

- Show support on Youtube: https://www.youtube.com/@ChuckBuilds
- Stay in touch on Instagram: https://www.instagram.com/ChuckBuilds/
- Want to chat or need support? Reach out on the ChuckBuilds Discord: https://discord.com/invite/uW36dVAtcT
- Feeling Generous? Support the project:
  - Github Sponsorship: https://github.com/sponsors/ChuckBuilds
  - Buy Me a Coffee: https://buymeacoffee.com/chuckbuilds
  - Ko-fi: https://ko-fi.com/chuckbuilds/ 

-----------------------------------------------------------------------------------

# Football Scoreboard Plugin

A production-ready plugin for LEDMatrix that displays live, recent, and upcoming football games across NFL and NCAA Football leagues. This plugin reuses the proven, battle-tested code from the main LEDMatrix project for maximum reliability and feature completeness.

## 🏈 Features

Upcoming Game (NCAA FB):

<img width="768" height="192" alt="led_matrix_1764889978847" src="https://github.com/user-attachments/assets/3561386b-1327-415d-92bc-f17f7e446984" />

Recent Game (NCAA FB):

<img width="768" height="192" alt="led_matrix_1764889931266" src="https://github.com/user-attachments/assets/a5361ddf-5472-4724-9665-1783db4eb3d1" />



### Core Functionality
- **Multiple League Support**: NFL and NCAA Football with independent configuration
- **Live Game Tracking**: Real-time scores, quarters, time remaining, down & distance
- **Recent Games**: Recently completed games with final scores and records
- **Upcoming Games**: Scheduled games with start times and odds
- **Dynamic Team Resolution**: Support for `AP_TOP_25`, `AP_TOP_10`, `AP_TOP_5` automatic team selection
- **Production-Ready**: Real ESPN API integration with caching and error handling

### Professional Display
- **Team Logos**: Professional team logos with automatic download fallback
- **Scorebug Layout**: Broadcast-quality scoreboard display
- **Football-Specific Details**: Down & distance, possession indicators, timeout tracking
- **Color-Coded States**: Live (green), final (gray), upcoming (yellow), redzone (red)
- **Odds Integration**: Real-time betting odds display with spread and over/under
- **Rankings Display**: AP Top 25 rankings for NCAA Football teams

### Advanced Features
- **Background Data Service**: Non-blocking API calls with intelligent caching
- **Smart Filtering**: Show favorite teams only or all games
- **Mode Cycling**: Automatic rotation between live, recent, and upcoming games
- **Error Recovery**: Graceful handling of API failures and missing data
- **Memory Optimized**: Efficient resource usage for Raspberry Pi deployment

## 🎯 Dynamic Team Resolution

The plugin supports automatic team selection using dynamic patterns:

- **`AP_TOP_25`**: Automatically includes all 25 AP Top 25 ranked teams
- **`AP_TOP_10`**: Automatically includes top 10 ranked teams  
- **`AP_TOP_5`**: Automatically includes top 5 ranked teams

These patterns update automatically as rankings change throughout the season. You can mix them with specific teams:

```json
"favorite_teams": ["AP_TOP_25", "UGA", "ALA"]
```

This will show games for all AP Top 25 teams plus Georgia and Alabama (duplicates are automatically removed).

## 📺 Display Modes

The plugin supports three display modes that cycle automatically:

1. **Live Games**: Currently active games with real-time updates
2. **Recent Games**: Recently completed games with final scores
3. **Upcoming Games**: Scheduled games with start times and odds

## 🔄 Rotation Order Configuration

The plugin supports configurable rotation order, allowing you to specify the exact sequence of league/mode combinations. This gives you precise control over how games are displayed.

### Combined vs Granular Modes

**Combined Modes** (default, backward compatible):
- `football_recent`: Shows all recent games from all enabled leagues (NFL → NCAA FB)
- `football_upcoming`: Shows all upcoming games from all enabled leagues
- `football_live`: Shows all live games from all enabled leagues

**Granular Modes** (for precise control):
- `nfl_recent`, `nfl_upcoming`, `nfl_live`: NFL-specific modes
- `ncaa_fb_recent`, `ncaa_fb_upcoming`, `ncaa_fb_live`: NCAA FB-specific modes

### Configuration

Add a `rotation_order` array to your config to specify the rotation sequence:

```json
{
  "rotation_order": [
    "nfl_recent",
    "nfl_upcoming",
    "ncaa_fb_recent",
    "ncaa_fb_upcoming"
  ]
}
```

### Rotation Patterns

**League-First Pattern** (all NFL modes, then all NCAA FB modes):
```json
{
  "rotation_order": [
    "nfl_recent",
    "nfl_upcoming",
    "nfl_live",
    "ncaa_fb_recent",
    "ncaa_fb_upcoming",
    "ncaa_fb_live"
  ]
}
```

**Mode-First Pattern** (all Recent, then all Upcoming, then all Live):
```json
{
  "rotation_order": [
    "nfl_recent",
    "ncaa_fb_recent",
    "nfl_upcoming",
    "ncaa_fb_upcoming",
    "nfl_live",
    "ncaa_fb_live"
  ]
}
```

**Custom Pattern** (your preferred sequence):
```json
{
  "rotation_order": [
    "nfl_recent",
    "nfl_upcoming",
    "ncaa_fb_recent",
    "ncaa_fb_upcoming"
  ]
}
```

### How It Works

1. **When `rotation_order` is configured**: The plugin uses granular rotation internally
   - Display controller still calls combined modes (`football_recent`, `football_upcoming`, `football_live`)
   - Plugin internally rotates through granular modes based on `rotation_order`
   - Each granular mode can have its own duration

2. **When `rotation_order` is not configured**: Uses default sequential block behavior
   - Shows all NFL games, then all NCAA FB games
   - Maintains backward compatibility with existing configs

3. **Mode Durations**: Each granular mode respects its own mode duration settings
   - `nfl_recent` uses `nfl.mode_durations.recent_mode_duration` or top-level `recent_mode_duration`
   - `ncaa_fb_upcoming` uses `ncaa_fb.mode_durations.upcoming_mode_duration` or top-level `upcoming_mode_duration`

4. **Resume Functionality**: When a mode cycles back, it continues from where it left off
   - Progress is preserved across rotation cycles
   - No repetition of already-shown games

### Example Flow

**Config:**
```json
{
  "rotation_order": [
    "nfl_recent",
    "nfl_upcoming",
    "ncaa_fb_recent",
    "ncaa_fb_upcoming"
  ],
  "recent_mode_duration": 60,
  "upcoming_mode_duration": 60
}
```

**Display Controller calls `football_recent`:**
1. Plugin checks `rotation_order` and finds `["nfl_recent", "ncaa_fb_recent"]` (filtered for recent mode)
2. Shows `nfl_recent` for 60 seconds
3. Advances to `ncaa_fb_recent` for 60 seconds
4. Wraps around to `nfl_recent` again

**Display Controller calls `football_upcoming`:**
1. Plugin checks `rotation_order` and finds `["nfl_upcoming", "ncaa_fb_upcoming"]`
2. Shows `nfl_upcoming` for 60 seconds
3. Advances to `ncaa_fb_upcoming` for 60 seconds
4. Wraps around to `nfl_upcoming` again

### Backward Compatibility

- If `rotation_order` is not configured, the plugin uses default sequential block behavior
- Existing configs continue to work without changes
- Combined modes (`football_recent`, etc.) can still be used in `rotation_order` for mixed patterns

## ⏱️ Duration Configuration

The plugin offers flexible duration control at multiple levels to fine-tune your display experience:

### Per-Game Duration

Controls how long each individual game displays before rotating to the next game **within the same mode**.

**Configuration:**
- `live_game_duration`: Seconds per live game (default: 30s)
- `recent_game_duration`: Seconds per recent game (default: 15s)
- `upcoming_game_duration`: Seconds per upcoming game (default: 15s)

**Example:** With `recent_game_duration: 15`, each recent game shows for 15 seconds before moving to the next.

### Per-Mode Duration

Controls the **total time** a mode displays before rotating to the next mode, regardless of how many games are available.

**Configuration:**
- `recent_mode_duration`: Total seconds for Recent mode (default: dynamic)
- `upcoming_mode_duration`: Total seconds for Upcoming mode (default: dynamic)
- `live_mode_duration`: Total seconds for Live mode (default: dynamic)

**Example:** With `recent_mode_duration: 60` and `recent_game_duration: 15`, Recent mode shows 4 games (60s ÷ 15s = 4) before rotating to Upcoming mode.

### How They Work Together

**Per-game duration** + **Per-mode duration**:
```
Recent Mode (60s total):
  ├─ Game 1: 15s
  ├─ Game 2: 15s
  ├─ Game 3: 15s
  └─ Game 4: 15s
  → Rotate to Upcoming Mode

Upcoming Mode (60s total):
  ├─ Game 1: 15s
  └─ ... (continues)
```

### Resume Functionality

When a mode times out before showing all games, it **resumes from where it left off** on the next cycle:

```
Cycle 1: Recent Mode (60s, 10 games available)
  ├─ Game 1-4 shown ✓
  └─ Time expires → Rotate

Cycle 2: Recent Mode resumes
  ├─ Game 5-8 shown ✓ (continues from Game 4, no repetition)
  └─ Time expires → Rotate

Cycle 3: Recent Mode resumes
  ├─ Game 9-10 shown ✓
  └─ All games shown → Full cycle complete → Reset progress
```

### Dynamic Duration (Fallback)

If per-mode durations are **not** configured, the plugin uses **dynamic calculation**:
- **Formula**: `total_duration = number_of_games × per_game_duration`
- **Example**: 24 games @ 15s each = 360 seconds for the mode

This ensures all games are shown but may result in very long mode durations if you have many games.

### Per-League Overrides

You can set different durations per league using the `mode_durations` section:

```json
{
  "nfl": {
    "mode_durations": {
      "recent_mode_duration": 45,
      "upcoming_mode_duration": 30
    }
  },
  "ncaa_fb": {
    "mode_durations": {
      "recent_mode_duration": 60
    }
  }
}
```

When multiple leagues are enabled with different durations, the system uses the **maximum** to ensure all leagues get their time.

### Integration with Dynamic Duration Caps

If you have dynamic duration caps configured (e.g., `max_duration_seconds: 120`), the system uses the **minimum** of:
- Per-mode duration (e.g., 180s)
- Dynamic duration cap (e.g., 120s)
- **Result**: 120s (ensures cap is respected)

## 🎨 Visual Features

### Professional Scorebug Display
- **Team Logos**: High-quality team logos positioned on left and right sides
- **Scores**: Centered score display with outlined text for visibility
- **Game Status**: Quarter/time display at top center
- **Down & Distance**: Live game situation information (NFL only)
- **Possession Indicator**: Visual indicators for ball possession
- **Odds Display**: Spread and over/under betting lines
- **Rankings**: AP Top 25 rankings for NCAA Football

### Color Coding
- **Live Games**: Green text for active status
- **Redzone**: Red highlighting when teams are in scoring position
- **Final Games**: Gray text for completed games
- **Upcoming Games**: Yellow text for scheduled games
- **Odds**: Green text for betting information

## 🏷️ Team Abbreviations

### NFL Teams
Common abbreviations: TB, DAL, GB, KC, BUF, SF, PHI, NE, MIA, NYJ, LAC, DEN, LV, CIN, BAL, CLE, PIT, IND, HOU, TEN, JAX, ARI, LAR, SEA, WAS, NYG, MIN, DET, CHI, ATL, CAR, NO

### NCAA Football Teams
Common abbreviations: UGA (Georgia), AUB (Auburn), BAMA (Alabama), CLEM (Clemson), OSU (Ohio State), MICH (Michigan), FSU (Florida State), LSU (LSU), OU (Oklahoma), TEX (Texas), ORE (Oregon), MISS (Mississippi), GT (Georgia Tech), VAN (Vanderbilt), BYU (BYU)

## 🔧 Technical Details

### Architecture
This plugin reuses the proven code from the main LEDMatrix project:
- **SportsCore**: Base class for all sports functionality
- **Football**: Football-specific game detail extraction
- **NFL Managers**: Live, Recent, and Upcoming managers for NFL
- **NCAA FB Managers**: Live, Recent, and Upcoming managers for NCAA Football
- **BaseOddsManager**: Production-ready odds fetching from ESPN API
- **DynamicTeamResolver**: Automatic team resolution for rankings

### Data Sources
- **ESPN API**: Primary data source for games, scores, and rankings
- **Real-time Updates**: Live game data updates every 30 seconds
- **Intelligent Caching**: 1-hour cache for rankings, 30-minute cache for odds
- **Error Recovery**: Graceful handling of API failures

### Performance
- **Background Processing**: Non-blocking data fetching
- **Memory Optimized**: Efficient resource usage for Raspberry Pi
- **Smart Caching**: Reduces API calls while maintaining data freshness
- **Configurable Intervals**: Adjustable update frequencies per league

## 📦 Installation

### From Plugin Store (Recommended)
1. Open LEDMatrix web interface
2. Navigate to Plugin Store
3. Search for "Football Scoreboard"
4. Click Install
5. Configure your favorite teams and preferences


## 🐛 Troubleshooting

### Common Issues
- **No games showing**: Check if leagues are enabled and favorite teams are configured
- **Missing team logos**: Logos are automatically downloaded from ESPN API
- **Slow updates**: Adjust the `live_update_interval` in league configuration
- **API errors**: Check your internet connection and ESPN API availability
- **Dynamic teams not working**: Ensure you're using exact patterns like `AP_TOP_25`


## 📊 Version History

### v2.0.5 (Current)
- ✅ Production-ready with real ESPN API integration
- ✅ Dynamic team resolution (AP_TOP_25, AP_TOP_10, AP_TOP_5)
- ✅ Real-time odds display with spread and over/under
- ✅ Nested configuration structure for better organization
- ✅ Full compatibility with LEDMatrix web UI
- ✅ Comprehensive error handling and caching
- ✅ Memory-optimized for Raspberry Pi deployment

### Previous Versions
- v2.0.4: Initial refactoring to reuse LEDMatrix core code
- v1.x: Original modular implementation

## 🤝 Contributing

This plugin is built on the proven LEDMatrix core codebase. For issues or feature requests, please use the GitHub issue tracker.

## 📄 License

This plugin follows the same license as the main LEDMatrix project.
