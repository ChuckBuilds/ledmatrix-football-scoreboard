# Season and Team Data Handling Comparison

## Overview
Comparison of how the plugin handles season and team data versus the old `ncaa_fb_manager.py`.

---

## Season Data Fetching

### Old NCAA FB Manager

**Strategy**: Full season fetch with partial fallback
```python
def _fetch_ncaa_fb_api_data(self, use_cache: bool = True) -> Optional[Dict]:
    # Season: Aug 1 to Feb 1 (end date is Feb, not Mar)
    datestring = f"{season_year}0801-{season_year+1}0201"
    cache_key = f"ncaafb_schedule_{season_year}"
    
    # 1. Check cache first
    cached_data = self.cache_manager.get(cache_key)
    
    # 2. Start background fetch for full season
    self.background_service.submit_fetch_request(...)
    
    # 3. Return partial data immediately (while full fetch runs in background)
    partial_data = self._get_weeks_data()  # Last 2 weeks + next 1 week
    return partial_data
```

**Date Range**: 
- **Full season**: `Aug 1 - Feb 1` (6 months)
- **Partial fallback**: `-2 weeks to +1 week` (3 weeks)

### New Plugin

**Strategy**: Full season fetch with multiple fallbacks
```python
def fetch_ncaa_fb_data(self, use_cache: bool = True) -> Optional[Dict]:
    # Season: Aug 1 to Mar 1 (end date is Mar, not Feb)
    datestring = f"{season_year}0801-{season_year+1}0301"
    cache_key = f"ncaa_fb_schedule_{season_year}"
    
    # 1. Check cache first
    cached_data = self.cache_manager.get(cache_key)
    
    # 2. Start background fetch
    self._start_background_fetch(...)
    
    # 3. Try full season fetch first
    full_season_data = self._fetch_full_season_games(...)
    if full_season_data:
        return full_season_data
    
    # 4. Fallback to today's games
    return self._fetch_todays_games("ncaa_fb")
```

**Date Range**:
- **Full season**: `Aug 1 - Mar 1` (7 months)
- **Fallback**: Today's games only

### Key Differences

| Aspect | Old Manager | New Plugin |
|--------|-------------|------------|
| **End date** | Feb 1 | Mar 1 |
| **Season length** | 6 months | 7 months |
| **Partial fallback** | -2 weeks to +1 week | Today only |
| **Immediate data** | Get partial while full loads | Try full, fallback to today |
| **Multi-API calls** | Single call for full season | Separate calls |

---

## Team Data Extraction

### Old Manager (`sports.py`)

**Extracts from `competitors` array**:
```python
def _extract_game_details_common(self, game_event: Dict):
    competition = game_event["competitions"][0]
    competitors = competition["competitors"]
    
    home_team = next((c for c in competitors if c.get("homeAway") == "home"), None)
    away_team = next((c for c in competitors if c.get("homeAway") == "away"), None)
    
    # Extract team info
    home_abbr = home_team["team"]["abbreviation"]
    away_abbr = away_team["team"]["abbreviation"]
    home_id = home_team["id"]
    away_id = away_team["id"]
    home_score = home_team.get("score", "0")
    away_score = away_team.get("score", "0")
    
    # Extract team records (Win-Loss-Tie)
    home_record = home_team.get('records', [{}])[0].get('summary', '') if home_team.get('records') else ''
    away_record = away_team.get('records', [{}])[0].get('summary', '') if away_team.get('records') else ''
    
    # Clean up "0-0" records
    if home_record in {"0-0", "0-0-0"}:
        home_record = ''
    if away_record in {"0-0", "0-0-0"}:
        away_record = ''
    
    # Logo paths with normalization
    home_logo_path = self.logo_dir / Path(f"{LogoDownloader.normalize_abbreviation(home_abbr)}.png")
    away_logo_path = self.logo_dir / Path(f"{LogoDownloader.normalize_abbreviation(away_abbr)}.png")
    home_logo_url = home_team["team"].get("logo")
    away_logo_url = away_team["team"].get("logo")
```

**Team Fields Extracted**:
- ✅ Abbreviation
- ✅ ID
- ✅ Score
- ✅ **Record (Win-Loss-Tie)** ← Missing in plugin!
- ✅ Logo path (normalized)
- ✅ Logo URL

### New Plugin (`data_fetcher.py`)

**Extracts from `competitors` array**:
```python
def _extract_game_details(self, event: Dict, league_key: str, league_config: Dict):
    competitors = competition.get("competitors", [])
    
    # Home and away teams
    for competitor in competitors:
        if competitor.get("homeAway") == "home":
            home_competitor = competitor
        elif competitor.get("homeAway") == "away":
            away_competitor = competitor
    
    # Extract team info
    home_team = home_competitor.get("team", {})
    away_team = away_competitor.get("team", {})
    
    home_abbr = home_team.get("abbreviation", "HOME")
    away_abbr = away_team.get("abbreviation", "AWAY")
    home_id = home_team.get("id", "")
    away_id = away_team.get("id", "")
    home_score = home_competitor.get("score", "0")
    away_score = away_competitor.get("score", "0")
    
    # Logo URLs
    home_logo_url = home_team.get("logo")
    away_logo_url = away_team.get("logo")
    
    # Logo paths with normalization
    home_logo_path = Path(logo_dir) / f"{LogoDownloader.normalize_abbreviation(home_abbr)}.png"
    away_logo_path = Path(logo_dir) / f"{LogoDownloader.normalize_abbreviation(away_abbr)}.png"
```

**Team Fields Extracted**:
- ✅ Abbreviation
- ✅ ID
- ✅ Score
- ❌ **Record (Win-Loss-Tie)** ← MISSING!
- ✅ Logo path (normalized)
- ✅ Logo URL

---

## Critical Missing Feature: Team Records

### Impact

**Old Manager**: Shows team win-loss records when `show_records` config is enabled
```python
# In _draw_scorebug_layout()
if self.show_records:
    away_text = game.get('away_record', '')  # e.g., "8-2"
    home_text = game.get('home_record', '')  # e.g., "7-3"
```

**New Plugin**: Cannot show records because they're not extracted!
```python
# In scoreboard_renderer.py
elif hasattr(self, 'show_records') and self.show_records:
    away_text = game.get('away_record', '')  # Always '' because not in game data!
    home_text = game.get('home_record', '')  # Always '' because not in game data!
```

### Why This Matters

- **Display**: Records won't show even if `show_records: true` in config
- **Rankings**: Won't affect rankings display (separate feature)
- **User Experience**: Missing information that old managers provided

---

## Season Date Range Differences

### Why Different End Dates?

**Old Manager**: `Aug 1 - Feb 1`
- Covers regular season through bowl season
- Shorter cache window

**New Plugin**: `Aug 1 - Mar 1`
- Includes conference championship games
- One extra month of data

### Impact

- **More games**: Plugin will fetch more games than old manager
- **Larger cache**: Takes more memory/storage
- **Potentially slower**: More data to process

---

## Fallback Strategy Differences

### Old Manager

```
Cache Hit? 
├─ Yes → Return cached data
└─ No → Start background fetch + return _get_weeks_data()
                └─ Returns: Last 2 weeks + Next 1 week
```

**Advantages**:
- ✅ Immediate partial data available
- ✅ Smooth transition to full data
- ✅ Fewer API calls

### New Plugin

```
Cache Hit?
├─ Yes → Return cached data
└─ No → Start background fetch + try full season fetch
                ├─ Success → Return full season
                └─ Fail → Return today's games only
```

**Advantages**:
- ✅ Faster full season fetch (when API cooperates)
- ✅ More complete data when available

**Disadvantages**:
- ❌ No partial data fallback
- ❌ Could show empty if fetch fails
- ❌ Today's games might not be enough

---

## Recommendations

### 1. Add Team Records Extraction

```python
# In data_fetcher.py _extract_game_details()
# Extract team records
home_record = home_competitor.get('records', [{}])[0].get('summary', '') if home_competitor.get('records') else ''
away_record = away_competitor.get('records', [{}])[0].get('summary', '') if away_competitor.get('records') else ''

# Clean up "0-0" records
if home_record in {"0-0", "0-0-0"}:
    home_record = ''
if away_record in {"0-0", "0-0-0"}:
    away_record = ''

# Add to game dict
game = {
    # ... existing fields ...
    "home_record": home_record,
    "away_record": away_record,
}
```

### 2. Add Partial Data Fallback

```python
# In data_fetcher.py fetch_ncaa_fb_data()
# Add fallback similar to old manager
if not full_season_data:
    # Try partial data (-2 weeks to +1 week)
    partial_data = self._fetch_partial_games("ncaa_fb")
    if partial_data:
        return partial_data
    
    # Last resort: today's games
    return self._fetch_todays_games("ncaa_fb")
```

### 3. Standardize Season End Date

Decide which is correct:
- **Feb 1**: Aligns with bowl season end
- **Mar 1**: Includes conference championships

Recommendation: Use **Feb 1** to match old managers and reduce data volume.

---

## Summary

| Feature | Old Manager | New Plugin | Status |
|---------|-------------|------------|--------|
| Season data fetch | ✅ | ✅ | ✅ Same |
| Team records | ✅ | ❌ | ❌ Missing |
| Logo paths | ✅ | ✅ | ✅ Same |
| Logo URLs | ✅ | ✅ | ✅ Same |
| Season end date | Feb 1 | Mar 1 | ⚠️ Different |
| Partial fallback | ✅ | ❌ | ❌ Missing |
| Background fetch | ✅ | ✅ | ✅ Same |
| Cache key | ✅ | ✅ | ✅ Same |

**Priority Fix**: Add team records extraction for parity with old managers.

