# Football Scoreboard Plugin

A production-ready plugin for LEDMatrix that displays live, recent, and upcoming football games across NFL and NCAA Football leagues. This plugin reuses the proven, battle-tested code from the main LEDMatrix project for maximum reliability and feature completeness.

## 🏈 Features

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

## ⚙️ Configuration

### Global Settings

```json
{
  "enabled": true,
  "display_duration": 30,
  "game_display_duration": 15,
  "show_records": false,
  "show_ranking": false,
  "show_odds": true,
  "timezone": "UTC"
}
```

### NFL Configuration

```json
{
  "nfl": {
    "enabled": true,
    "favorite_teams": ["TB", "DAL", "GB"],
    "display_modes": {
      "show_live": true,
      "show_recent": true,
      "show_upcoming": true
    },
    "game_limits": {
      "recent_games_to_show": 5,
      "upcoming_games_to_show": 2
    },
    "display_options": {
      "show_records": true,
      "show_ranking": false,
      "show_odds": true
    },
    "filtering": {
      "show_favorite_teams_only": true,
      "show_all_live": false
    },
    "live_update_interval": 30,
    "live_game_duration": 20
  }
}
```

### NCAA Football Configuration

```json
{
  "ncaa_fb": {
    "enabled": true,
    "favorite_teams": ["AP_TOP_25", "UGA", "ALA"],
    "display_modes": {
      "show_live": true,
      "show_recent": true,
      "show_upcoming": true
    },
    "game_limits": {
      "recent_games_to_show": 3,
      "upcoming_games_to_show": 2
    },
    "display_options": {
      "show_records": false,
      "show_ranking": true,
      "show_odds": true
    },
    "filtering": {
      "show_favorite_teams_only": true,
      "show_all_live": false
    },
    "live_update_interval": 30,
    "live_game_duration": 20
  }
}
```

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

### Manual Installation
1. Download the latest release from GitHub
2. Extract to your `ledmatrix-plugins/plugins/` folder
3. Ensure the plugin is enabled in your LEDMatrix configuration
4. Configure your favorite teams and display preferences
5. Restart LEDMatrix to load the new plugin

## 🐛 Troubleshooting

### Common Issues
- **No games showing**: Check if leagues are enabled and favorite teams are configured
- **Missing team logos**: Logos are automatically downloaded from ESPN API
- **Slow updates**: Adjust the `live_update_interval` in league configuration
- **API errors**: Check your internet connection and ESPN API availability
- **Dynamic teams not working**: Ensure you're using exact patterns like `AP_TOP_25`

### Debug Mode
Enable debug logging to troubleshoot issues:
```json
{
  "logging": {
    "level": "DEBUG"
  }
}
```

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