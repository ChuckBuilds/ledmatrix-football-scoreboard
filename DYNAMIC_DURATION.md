# Dynamic Cycle Duration

## Overview

The football scoreboard plugin now supports **dynamic cycle duration** that automatically calculates the total display time based on the number of games available.

## How It Works

### Formula
```
total_duration = number_of_games × per_game_duration
```

### Examples

**NFL Recent with 2 games @ 15s each:**
- Game 1 (TB): 15 seconds
- Game 2 (DAL): 15 seconds  
- **Total: 30 seconds** before switching to next mode

**NFL Recent with 5 games @ 15s each:**
- 5 games × 15s = **75 seconds total**

**NCAA FB Upcoming with 3 games @ 20s each:**
- 3 games × 20s = **60 seconds total**

## Configuration

### Global Configuration
Set the default per-game duration for all modes:

```json
{
  "game_display_duration": 15
}
```

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

### Configuration Hierarchy

1. **Most Specific**: `config.nfl.live_game_duration`
2. **Fallback**: `config.game_display_duration`

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

1. **Automatic Scaling**: Duration adjusts based on available games
2. **Consistent Display Time**: Each game gets equal viewing time
3. **Flexible Configuration**: Set different durations per league and mode
4. **Prevents Premature Cycling**: Mode stays active until all games have been shown

## Example Scenarios

### Scenario 1: Single Favorite Team
- **Configuration**: TB as favorite, 15s per game
- **Games Available**: 1 TB game in recent
- **Total Duration**: 1 × 15s = **15 seconds**

### Scenario 2: Multiple Favorite Teams
- **Configuration**: TB and DAL as favorites, 15s per game
- **Games Available**: 2 games (TB, DAL)
- **Total Duration**: 2 × 15s = **30 seconds**

### Scenario 3: Full League
- **Configuration**: Show all NFL games, 10s per game  
- **Games Available**: 16 games this week
- **Total Duration**: 16 × 10s = **160 seconds (2.67 minutes)**

### Scenario 4: Mixed Leagues
- **Configuration**: NFL @ 15s/game, NCAA FB @ 12s/game
- **Mode**: `football_recent`
- **Games**: 2 NFL + 3 NCAA FB = 5 total
- **Total Duration**: (2 × 15s) + (3 × 12s) = **66 seconds**

## Technical Details

### Method Signature
```python
def get_cycle_duration(self, display_mode: str = None) -> Optional[float]:
    """
    Calculate the expected cycle duration for a display mode.
    
    Args:
        display_mode: The mode name (e.g., 'football_live', 'football_recent')
    
    Returns:
        Total duration in seconds, or None if no games available
    """
```

### Return Values
- **Positive Number**: Total calculated duration in seconds
- **None**: No games available for this mode (controller should skip)

### Game Filtering
The calculation automatically filters out:
- **Live mode**: Games marked as final
- **Live mode**: Games that appear to be over (stuck clock, final period)
- **All modes**: Games not matching favorite team filters (if configured)

## Logging

When enabled, the plugin logs cycle duration calculations:

```
INFO - get_cycle_duration: nfl recent has 2 games, per_game_duration=15s
INFO - get_cycle_duration: football_recent = 2 games × 15s = 30s
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

The display controller's dynamic duration system will automatically use `get_cycle_duration()` to calculate the proper duration.
