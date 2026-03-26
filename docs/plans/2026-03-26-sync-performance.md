# Sync Performance Optimization Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce sync time from ~10min to ~3-4min (first run) and near-instant for re-syncs by skipping known players, enabling parallel workers, and reducing idle delays.

**Architecture:** Three independent optimizations applied to `sync_all.py` and `src/scrapers/players.py`: (A) skip players with existing stats via DB check + `--force` flag override, (B) bump default worker count to 2 with configurable pool size, (C) tighten `random_delay` and remove redundant sleeps. Each is independently valuable and testable.

**Tech Stack:** Python 3.10, SQLAlchemy, Selenium, pytest

---

### Task 1: Skip players that already have stats

**Files:**
- Modify: `sync_all.py:169-171` (player ID filtering)
- Test: `tests/test_scrapers.py`

**Step 1: Write failing test**

Add to `tests/test_scrapers.py`:

```python
class TestSkipExistingPlayers:
    """sync_full_event should skip players that already have stats."""

    @patch('sync_all.DriverPool')
    @patch('sync_all.get_event_results')
    @patch('sync_all.get_event_teams')
    @patch('sync_all.get_event_details')
    @patch('sync_all.create_driver')
    @patch('sync_all.session_scope')
    def test_skips_players_with_rating(
        self, mock_session, mock_create_driver, mock_details, mock_teams,
        mock_results, mock_pool
    ):
        from sync_all import sync_full_event

        mock_driver = MagicMock()
        mock_create_driver.return_value = mock_driver
        mock_details.return_value = {'location': 'Test'}
        mock_teams.return_value = [100]
        mock_results.return_value = []

        # Mock session context manager
        mock_sess = MagicMock()
        mock_session.return_value.__enter__ = MagicMock(return_value=mock_sess)
        mock_session.return_value.__exit__ = MagicMock(return_value=False)

        # Mock event exists
        mock_event = MagicMock()
        mock_sess.query.return_value.filter_by.return_value.first.return_value = mock_event

        # Mock DriverPool context manager for team scraping
        mock_pool_instance = MagicMock()
        mock_pool.return_value.__enter__ = MagicMock(return_value=mock_pool_instance)
        mock_pool.return_value.__exit__ = MagicMock(return_value=False)

        # Player 7998 already has rating - should be skipped
        mock_player = MagicMock()
        mock_player.rating_2_0 = 1.15

        # We need to track which query paths return what
        # This is complex to mock — test the filtering function directly instead
        from sync_all import _filter_players_needing_stats

        # Simulated: player 7998 has stats, player 8000 does not
        assert _filter_players_needing_stats is not None
```

Actually, the test is cleaner as a unit test on the filtering logic. Revised:

```python
class TestFilterPlayersNeedingStats:
    """Filter out players that already have complete stats."""

    def test_filters_players_with_rating(self):
        from sync_all import _filter_players_needing_stats
        from unittest.mock import MagicMock

        mock_session = MagicMock()

        # Player 1 has rating, Player 2 does not
        player_with_stats = MagicMock()
        player_with_stats.id = 1
        player_with_stats.rating_2_0 = 1.15

        player_without_stats = MagicMock()
        player_without_stats.id = 2
        player_without_stats.rating_2_0 = None

        mock_session.query.return_value.filter.return_value.all.return_value = [
            player_without_stats
        ]

        result = _filter_players_needing_stats(mock_session, [1, 2])
        assert result == [2]

    def test_force_returns_all(self):
        from sync_all import _filter_players_needing_stats
        from unittest.mock import MagicMock

        mock_session = MagicMock()
        result = _filter_players_needing_stats(mock_session, [1, 2], force=True)
        assert result == [1, 2]
```

**Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_scrapers.py::TestFilterPlayersNeedingStats -v`
Expected: FAIL — `_filter_players_needing_stats` not found

**Step 3: Implement filtering function and integrate**

In `sync_all.py`, add the filter function after imports:

```python
def _filter_players_needing_stats(session, player_ids, force=False):
    """Return player IDs that don't have stats yet. With force=True, return all."""
    if force or not player_ids:
        return player_ids
    players_without_stats = session.query(Player).filter(
        Player.id.in_(player_ids),
        Player.rating_2_0.is_(None)
    ).all()
    return [p.id for p in players_without_stats]
```

In `sync_full_event`, update the player filtering block (around line 169):

```python
    # 4. Sincronizar stats de todos os jogadores
    unique_player_ids = list(set(all_player_ids))

    # Filter out players that already have stats
    with session_scope() as session:
        needed_ids = _filter_players_needing_stats(session, unique_player_ids, force=force_players)
    skipped = len(unique_player_ids) - len(needed_ids)
    if skipped:
        print(f"  Pulando {skipped} jogadores que ja tem stats")
    print(f"\nEtapa 4/4: Sincronizando stats de {len(needed_ids)} jogadores...")
```

Replace `unique_player_ids` with `needed_ids` in the DriverPool/executor block below.

Add `force_players=False` parameter to `sync_full_event` signature.

Add `--force-players` CLI flag in `main()`:

```python
parser.add_argument('--force-players', action='store_true',
                    help='Re-scrape players even if they already have stats')
```

Pass it through: `sync_full_event(..., force_players=args.force_players)`

**Step 4: Run tests**

Run: `python3 -m pytest tests/test_scrapers.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add sync_all.py tests/test_scrapers.py
git commit -m "perf: skip players that already have stats, add --force-players flag"
```

---

### Task 2: Reduce delays between player requests

**Files:**
- Modify: `src/scrapers/players.py:170` (random_delay in scrape loop)
- Test: manual timing comparison

**Step 1: Write test for reduced delay**

```python
class TestPlayerDelayConfig:
    """Player scraper should use configurable delays."""

    @patch('src.scrapers.players.time.sleep')
    @patch('src.scrapers.players.WebDriverWait')
    @patch('src.scrapers.players.create_driver')
    def test_default_delay_is_short(self, mock_create_driver, mock_wait_cls, mock_sleep):
        from src.scrapers.players import scrape_player
        import src.scrapers.players as players_mod

        mock_driver = MagicMock()
        mock_create_driver.return_value = mock_driver
        mock_wait_cls.return_value.until.return_value = True
        type(mock_driver).title = PropertyMock(return_value="Test 'nick' Player - HLTV")
        mock_driver.find_elements.return_value = []
        mock_driver.find_element.side_effect = Exception("Not found")

        with patch.object(players_mod, 'random_delay') as mock_delay:
            scrape_player(9999, headless=True)
            # Should be called with shorter delays
            mock_delay.assert_called_once_with(0.5, 1.5)
```

**Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_scrapers.py::TestPlayerDelayConfig -v`
Expected: FAIL — delay is (1.0, 2.0)

**Step 3: Reduce delays**

In `src/scrapers/players.py`, line 170:
```python
# Change from:
random_delay(1.0, 2.0)
# To:
random_delay(0.5, 1.5)
```

In `src/scrapers/players.py`, line 237 (`scrape_players` function):
```python
# Change from:
time.sleep(3)
# To:
time.sleep(1)
```

**Step 4: Run tests**

Run: `python3 -m pytest tests/test_scrapers.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/scrapers/players.py tests/test_scrapers.py
git commit -m "perf: reduce inter-request delays for player scraping"
```

---

### Task 3: Enable multiple Chrome workers

**Files:**
- Modify: `sync_all.py` (default worker count + pool size logic)
- Modify: `src/scrapers/selenium_helpers.py:20` (default concurrency)
- Test: `tests/test_scrapers.py`

**Step 1: Write test**

```python
class TestWorkerConfig:
    """Default workers should be 2 for player scraping."""

    def test_default_workers_env(self):
        import os
        # When HLTV_WORKERS is not set, default should be 2
        os.environ.pop('HLTV_WORKERS', None)
        # Re-import to pick up new default
        import importlib
        import sync_all
        importlib.reload(sync_all)
        assert sync_all._DEFAULT_WORKERS == 2
```

**Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_scrapers.py::TestWorkerConfig -v`
Expected: FAIL — default is 1

**Step 3: Implement**

In `sync_all.py`, change the default:
```python
# Change from:
_DEFAULT_WORKERS = int(os.getenv("HLTV_WORKERS", "1"))
# To:
_DEFAULT_WORKERS = int(os.getenv("HLTV_WORKERS", "2"))
```

In `src/scrapers/selenium_helpers.py`, bump semaphore default:
```python
# Change from:
_MAX = int(os.getenv("SELENIUM_MAX_CONCURRENCY", "1"))
# To:
_MAX = int(os.getenv("SELENIUM_MAX_CONCURRENCY", "2"))
```

**Step 4: Run tests**

Run: `python3 -m pytest tests/ -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add sync_all.py src/scrapers/selenium_helpers.py tests/test_scrapers.py
git commit -m "perf: default to 2 workers for parallel player/team scraping"
```

---

### Task 4: Live test with 2 workers

**Step 1: Run sync with 2 workers on event 8504 with --force-players**

```bash
PYTHONUNBUFFERED=1 xvfb-run --auto-servernum --server-args="-screen 0 1920x1080x24" \
    python3 sync_all.py --event 8504 --show --workers 2 --force-players
```

Watch for:
- Chrome crashes / `RemoteDisconnected` errors
- Cloudflare blocks
- Completion time vs previous ~10min

**Step 2: If 2 workers fails, fallback to 1**

If Chrome instability: revert default back to 1 in both files, keep the code supporting multiple workers for future use.

**Step 3: Report timing results**

Compare before/after timing.

---

### Task 5: Final verification

**Step 1: Run full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: All PASS

**Step 2: Test re-sync (skip path)**

```bash
PYTHONUNBUFFERED=1 xvfb-run --auto-servernum --server-args="-screen 0 1920x1080x24" \
    python3 sync_all.py --event 8504 --show
```

Expected: Should skip all 79 players and finish in ~2min (just event details + teams + results).

**Step 3: Commit any remaining changes**

```bash
git status
```
