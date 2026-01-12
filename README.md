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
- **Granular Mode Control**: Enable/disable specific league/mode combinations independently
- **Dual Display Styles**: Switch mode (one game at a time) or scroll mode (all games scrolling)
- **High-FPS Scrolling**: Smooth 100+ FPS horizontal scrolling for scroll mode
- **Font Customization**: Customize fonts, sizes, and styles for all text elements
- **Layout Customization**: Adjust X/Y positioning offsets for all display elements
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

### Granular Mode Control

The plugin supports **granular display modes** that give you precise control over what's shown:

- **NFL Modes**: `nfl_live`, `nfl_recent`, `nfl_upcoming`
- **NCAA FB Modes**: `ncaa_fb_live`, `ncaa_fb_recent`, `ncaa_fb_upcoming`

Each league and game type can be independently enabled or disabled. This allows you to:
- Show only NFL live games
- Show only NCAA FB recent games
- Mix and match any combination of modes
- Control exactly which content appears on your display

### Display Style Options

The plugin supports two display styles for each game type:

1. **Switch Mode** (Default): Display one game at a time with timed transitions
   - Shows each game for a configurable duration
   - Smooth transitions between games
   - Best for focused viewing of individual games

2. **Scroll Mode**: High-FPS horizontal scrolling of all games
   - All games scroll horizontally in a continuous stream
   - League separator icons between different leagues
   - Dynamic duration based on total content width
   - Supports 100+ FPS smooth scrolling
   - Best for seeing all games at once

You can configure the display mode separately for live, recent, and upcoming games in each league.

## 🎨 Visual Features

### Professional Scorebug Display
- **Team Logos**: High-quality team logos positioned on left and right sides
- **Scores**: Centered score display with outlined text for visibility
- **Game Status**: Quarter/time display at top center
- **Date Display**: Recent games show date underneath score
- **Down & Distance**: Live game situation information (NFL only)
- **Possession Indicator**: Visual indicators for ball possession
- **Odds Display**: Spread and over/under betting lines
- **Rankings**: AP Top 25 rankings for NCAA Football
- **Customizable Layout**: Adjust positioning of all elements via X/Y offsets
- **Customizable Fonts**: Configure font family and size for each text element

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


## ⚙️ Configuration

### Display Mode Settings

Each league (NFL, NCAA FB) can be configured with:
- **Enable/Disable**: Turn entire leagues on or off
- **Mode Toggles**: Enable/disable live, recent, or upcoming games independently
- **Display Style**: Choose "switch" (one game at a time) or "scroll" (all games scrolling) for each game type
- **Scroll Settings**: Configure scroll speed, frame delay, gap between games, and league separators

### Customization Options

- **Font Customization**: Adjust font family and size for:
  - Score text
  - Period/time text
  - Team names
  - Status text
  - Detail text (down/distance, etc.)
  - Ranking text

- **Layout Customization**: Fine-tune positioning with X/Y offsets for:
  - Team logos (home/away)
  - Score display
  - Status/period text
  - Date and time
  - Down & distance
  - Timeouts
  - Possession indicator
  - Records/rankings
  - Betting odds

## 🐛 Troubleshooting

### Common Issues
- **No games showing**: Check if leagues are enabled and favorite teams are configured
- **Missing team logos**: Logos are automatically downloaded from ESPN API
- **Slow updates**: Adjust the `live_update_interval` in league configuration
- **API errors**: Check your internet connection and ESPN API availability
- **Dynamic teams not working**: Ensure you're using exact patterns like `AP_TOP_25`
- **Scroll mode not working**: Verify `scroll_display_mode` is set to "scroll" in config
- **Modes not appearing**: Check that specific modes (e.g., `nfl_live`) are enabled in display_modes settings


## 📊 Version History

### v2.0.7 (Current)
- ✅ **Granular Display Modes**: Independent control of NFL/NCAA FB live/recent/upcoming modes
- ✅ **Scroll Display Mode**: High-FPS horizontal scrolling of all games with league separators
- ✅ **Switch Display Mode**: One game at a time with timed transitions (default)
- ✅ **Font Customization**: Customize fonts and sizes for all text elements
- ✅ **Layout Customization**: Adjust X/Y positioning offsets for all display elements
- ✅ **Date Display**: Recent games show date underneath score
- ✅ Production-ready with real ESPN API integration
- ✅ Dynamic team resolution (AP_TOP_25, AP_TOP_10, AP_TOP_5)
- ✅ Real-time odds display with spread and over/under
- ✅ Nested configuration structure for better organization
- ✅ Full compatibility with LEDMatrix web UI
- ✅ Comprehensive error handling and caching
- ✅ Memory-optimized for Raspberry Pi deployment

### Previous Versions
- v2.0.6: Bug fixes and improvements
- v2.0.5: Production-ready release with ESPN API integration
- v2.0.4: Initial refactoring to reuse LEDMatrix core code
- v1.x: Original modular implementation

## 🤝 Contributing

This plugin is built on the proven LEDMatrix core codebase. For issues or feature requests, please use the GitHub issue tracker.

## 📄 License

This plugin follows the same license as the main LEDMatrix project.
