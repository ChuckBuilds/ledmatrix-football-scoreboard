# Dynamic Cycle Duration

## Overview

The football scoreboard plugin supports both **dynamic cycle duration** (automatic calculation based on game count) and **fixed mode durations** (explicit time limits per mode). This provides flexibility to control display timing at different levels.

## Duration Types

### 1. Per-Game Duration
Controls how long each individual game displays **within a mode**.

**Configuration Keys:**
- `live_game_duration`: Seconds per live game (default: 30s)
- `recent_game_duration`: Seconds per recent game (default: 15s)  
- `upcoming_game_duration`: Seconds per upcoming game (default: 15s)

**Example:** With `recent_game_duration: 15`, each recent game shows for 15 seconds before moving to the next.

### 2. Per-Mode Duration (NEW)
Controls the **total time** a mode displays before rotating, regardless of game count.

**Configuration Keys:**
- `recent_mode_duration`: Total seconds for Recent mode (default: null = dynamic)
- `upcoming_mode_duration`: Total seconds for Upcoming mode (default: null = dynamic)
- `live_mode_duration`: Total seconds for Live mode (default: null = dynamic)

**Example:** With `recent_mode_duration: 60` and `recent_game_duration: 15`, Recent mode shows 4 games (60s ÷ 15s = 4) before rotating.

### 3. Dynamic Calculation (Fallback)
When per-mode duration is **not set**, the plugin calculates duration dynamically.

**Formula:**
```
total_duration = number_of_games × per_game_duration
```

## How Mode-Level Duration Works

### Basic Example

```json
{
  "recent_mode_duration": 60,
  "recent_game_duration": 15
}
```

**Behavior:**
```
Recent Mode (60s total, 10 games available):
  ├─ Game 1 (0-15s) ✓
  ├─ Game 2 (15-30s) ✓
  ├─ Game 3 (30-45s) ✓
  ├─ Game 4 (45-60s) ✓
  └─ Time expires (60s) → Rotate to Upcoming Mode
     Games 5-10 NOT shown yet (progress preserved)
```

### Resume Functionality (NEW)

When a mode times out before showing all games, it **resumes from where it left off** on the next cycle:

```
Cycle 1: Recent Mode (60s, 10 games available)
  ├─ Game 1 (0-15s) ✓
  ├─ Game 2 (15-30s) ✓
  ├─ Game 3 (30-45s) ✓
  ├─ Game 4 (45-60s) ✓
  └─ Time expires (60s) → Rotate to Upcoming Mode
     Progress: [game_1, game_2, game_3, game_4] preserved

Cycle 2: Upcoming Mode (60s)
  └─ ... (shows upcoming games)

Cycle 3: Recent Mode resumes
  ├─ Game 5 (0-15s) ✓ (continues from game 4, not restarting)
  ├─ Game 6 (15-30s) ✓
  ├─ Game 7 (30-45s) ✓
  ├─ Game 8 (45-60s) ✓
  └─ Time expires (60s) → Rotate to Upcoming Mode
     Progress: [game_1, game_2, game_3, game_4, game_5, game_6, game_7, game_8] preserved

Cycle 4: Recent Mode resumes again
  ├─ Game 9 (0-15s) ✓
  ├─ Game 10 (15-30s) ✓
  └─ All games shown → Full cycle complete → Reset progress for next cycle
```

**Key Points:**
- Progress tracking persists across mode rotations
- Only resets when full cycle completes (all games shown)
- No repetition of already-shown games when mode cycles back
- Mode start time resets when mode changes or full cycle completes

## Configuration

### Global Configuration
Set the default per-game duration for all modes:

```json
{
  "game_display_duration": 15
}
```

### Per-Mode Duration Configuration (NEW)
Set explicit time limits for each mode:

```json
{
  "recent_mode_duration": 60,
  "upcoming_mode_duration": 60,
  "live_mode_duration": 90
}
```

**Behavior:**
- Recent mode: Shows games for 60 seconds total, then rotates
- Upcoming mode: Shows games for 60 seconds total, then rotates
- Live mode: Shows games for 90 seconds total, then rotates
- Games not shown due to time limits will resume on next cycle

### Per-League Configuration
Override durations for specific leagues:

```json
{
  "nfl": {
    "enabled": true,
    "live_game_duration": 20,
    "recent_game_duration": 15,
    "upcoming_game_duration": 10
  },
  "ncaa_fb": {
    "enabled": true,
    "live_game_duration": 25,
    "recent_game_duration": 15,
    "upcoming_game_duration": 12
  }
}
```

### Per-League Mode Duration Overrides (NEW)
Override mode-level durations per league:

```json
{
  "nfl": {
    "enabled": true,
    "mode_durations": {
      "recent_mode_duration": 45,
      "upcoming_mode_duration": 30,
      "live_mode_duration": 60
    }
  },
  "ncaa_fb": {
    "enabled": true,
    "mode_durations": {
      "recent_mode_duration": 60,
      "upcoming_mode_duration": 45
    }
  }
}
```

**Multi-League Behavior:**
- If multiple leagues have different mode durations, the system uses the **maximum**
- Example: NFL=45s, NCAA FB=60s → uses 60s (ensures both leagues get their time)

### Configuration Hierarchy

**For Per-Game Duration:**
1. **Most Specific**: `config.nfl.live_game_duration`
2. **Fallback**: `config.game_display_duration`

**For Per-Mode Duration (NEW):**
1. **Most Specific**: `config.nfl.mode_durations.recent_mode_duration` (per-league override)
2. **Top-Level**: `config.recent_mode_duration`
3. **Fallback**: Dynamic calculation (games × per_game_duration)

## Integration with Dynamic Duration Caps (NEW)

If you have dynamic duration caps configured:

```json
{
  "nfl": {
    "dynamic_duration": {
      "enabled": true,
      "max_duration_seconds": 120
    }
  }
}
```

**Integration Logic:**
- If both mode duration and dynamic cap are set: uses **minimum**
- Example: `recent_mode_duration: 180`, `max_duration_seconds: 120` → uses 120s
- Ensures dynamic caps are always respected

## Mode-Specific Durations

Each mode type can have its own duration:

| Mode Type | Configuration Key | Use Case |
|-----------|------------------|----------|
| **Live** | `live_game_duration` | Games currently in progress |
| **Recent** | `recent_game_duration` | Recently completed games |
| **Upcoming** | `upcoming_game_duration` | Future scheduled games |

## Integration with Display Controller

The plugin provides a `get_cycle_duration(display_mode)` method that the display controller can call to get the expected duration:

```python
# Display controller calls this
duration = plugin.get_cycle_duration("football_recent")
# Returns: 30.0 (for 2 games @ 15s each)
```

## Benefits

1. **Automatic Scaling**: Duration adjusts based on available games (dynamic mode)
2. **Predictable Rotation**: Fixed mode durations ensure consistent timing (mode duration)
3. **Resume Functionality**: Games continue from where they left off (no repetition)
4. **Consistent Display Time**: Each game gets equal viewing time
5. **Flexible Configuration**: Set different durations per league and mode
6. **Prevents Premature Cycling**: Mode stays active until time expires or all games shown
7. **Dynamic Integration**: Mode durations work seamlessly with dynamic caps

## Example Scenarios

### Scenario 1: Fixed Mode Duration with Truncation
- **Configuration**: `recent_mode_duration: 60`, `recent_game_duration: 15`
- **Games Available**: 10 recent games
- **Behavior**: Shows 4 games (60s ÷ 15s), then rotates. Resumes with game 5 next cycle.
- **Total Duration**: 60 seconds

### Scenario 2: Dynamic Calculation (No Mode Duration Set)
- **Configuration**: TB and DAL as favorites, 15s per game, no mode duration
- **Games Available**: 2 games (TB, DAL)
- **Behavior**: Shows both games (2 × 15s)
- **Total Duration**: 30 seconds (dynamic)

### Scenario 3: Mode Duration with Dynamic Cap
- **Configuration**: `recent_mode_duration: 180`, `max_duration_seconds: 120`, 15s per game
- **Games Available**: 10 games
- **Behavior**: Cap applies → 120s total (shows 8 games)
- **Total Duration**: 120 seconds (min of 180 and 120)

### Scenario 4: Multi-League with Resume
- **Configuration**: NFL @ 15s/game, NCAA FB @ 15s/game, `recent_mode_duration: 60`
- **Games**: 20 NFL + 30 NCAA FB = 50 total recent games
- **Cycle 1**: Shows NFL games 1-4 (60s) → rotates
- **Cycle 2**: Resumes NFL at game 5-8 → continues until all NFL shown
- **Cycle 3**: Shows NCAA FB games 1-4 → continues across cycles
- **Total Cycles**: ~13 cycles to show all 50 games (4 per 60s cycle)

### Scenario 5: Single Favorite Team
- **Configuration**: TB as favorite, 15s per game
- **Games Available**: 1 TB game in recent
- **Total Duration**: 1 × 15s = **15 seconds** (dynamic)

### Scenario 6: Full League
- **Configuration**: Show all NFL games, 10s per game, no mode duration
- **Games Available**: 16 games this week
- **Total Duration**: 16 × 10s = **160 seconds (2.67 minutes)** (dynamic)

### Scenario 7: Mixed Leagues with Per-League Overrides
- **Configuration**: 
  - NFL: `mode_durations.recent_mode_duration: 45`
  - NCAA FB: `mode_durations.recent_mode_duration: 60`
- **Behavior**: Uses 60s (maximum) to ensure both leagues get their time
- **Total Duration**: 60 seconds

## Technical Details

### Method Signature
```python
def get_cycle_duration(self, display_mode: str = None) -> Optional[float]:
    """
    Calculate the expected cycle duration for a display mode.
    
    Priority order:
    1. Mode-level duration (if configured)
    2. Dynamic calculation (if no mode-level duration)
    3. Dynamic duration cap applies to both if enabled
    
    Args:
        display_mode: The mode name (e.g., 'football_live', 'football_recent')
    
    Returns:
        Total duration in seconds, or None if no games available
    """
```

### Return Values
- **Positive Number**: Total calculated duration in seconds
- **None**: No games available for this mode (controller should skip)

### Duration Resolution Logic

**For Mode-Level Duration:**
1. Check per-league overrides: `config.nfl.mode_durations.recent_mode_duration`
2. If multiple leagues, use maximum: `max(nfl_duration, ncaa_fb_duration)`
3. Check top-level: `config.recent_mode_duration`
4. If both mode duration and dynamic cap exist: `min(mode_duration, dynamic_cap)`
5. If neither, use dynamic calculation

**For Dynamic Calculation:**
1. Count games from all enabled leagues
2. Get per-game duration for each league
3. Calculate: `total_games × per_game_duration`
4. Apply dynamic duration cap if enabled

### Progress Tracking

The plugin uses `_dynamic_manager_progress` to track which games have been shown:

```python
# Format: {manager_key: {game_id_1, game_id_2, ...}}
_dynamic_manager_progress: Dict[str, Set[str]] = {}
```

**Behavior:**
- Game IDs are added when a game completes its full display duration
- Progress persists across mode rotations (for resume functionality)
- Progress resets when full cycle completes (all games shown)

### Mode Start Time Tracking (NEW)

The plugin tracks when each mode started displaying:

```python
# Format: {display_mode: start_time}
_mode_start_time: Dict[str, float] = {}
```

**Behavior:**
- Set when mode first displays
- Used to check if mode duration has expired
- Reset when mode changes or full cycle completes
- Not cleared on time expiry (preserves for resume)

### Game Filtering
The calculation automatically filters out:
- **Live mode**: Games marked as final
- **Live mode**: Games that appear to be over (stuck clock, final period)
- **All modes**: Games not matching favorite team filters (if configured)

## Logging

When enabled, the plugin logs cycle duration calculations:

```
INFO - get_cycle_duration: using mode-level duration for football_recent = 60s
INFO - get_cycle_duration: nfl recent has 2 games, per_game_duration=15s
INFO - get_cycle_duration: football_recent = 2 games × 15s = 30s
INFO - Mode duration expired for football_recent: 60.2s >= 60s. Rotating to next mode (progress preserved for resume).
```

## Migration from Fixed Duration

### Before (Fixed Duration)
```json
{
  "display_duration": 30  // Always 30s regardless of games
}
```

### After (Dynamic Duration)  
```json
{
  "game_display_duration": 15  // 15s per game, scales automatically
}
```

### After (Fixed Mode Duration - NEW)
```json
{
  "recent_mode_duration": 60,      // 60s total for Recent mode
  "upcoming_mode_duration": 60,    // 60s total for Upcoming mode
  "live_mode_duration": 90,        // 90s total for Live mode
  "game_display_duration": 15      // 15s per game within each mode
}
```

**Benefits of Mode Duration:**
- Predictable rotation timing
- Resume functionality (no repetition)
- Works with dynamic caps
- Scales to large game counts

The display controller's dynamic duration system will automatically use `get_cycle_duration()` to calculate the proper duration.

## Troubleshooting

### Mode Not Rotating
- **Symptom**: Stuck on one mode for very long time
- **Cause**: Too many games with dynamic calculation (no mode duration set)
- **Solution**: Set `recent_mode_duration`, `upcoming_mode_duration`, `live_mode_duration`

### Games Repeating
- **Symptom**: Same games show every cycle
- **Cause**: Progress tracking not working
- **Solution**: Check logs for "progress preserved" messages, ensure dynamic duration is enabled

### Mode Duration Not Working
- **Symptom**: Mode doesn't rotate after configured time
- **Cause**: Dynamic cap may be overriding
- **Solution**: Check if `max_duration_seconds` is set lower than mode duration

### Games Skipped
- **Symptom**: Not all games are shown
- **Cause**: Mode duration too short for game count
- **Solution**: Increase mode duration or decrease per-game duration
