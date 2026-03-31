# Events Scraper Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 6 issues in the events scraper: reuse driver across event functions, extract end_date, improve prize_pool targeting, fix location filter, fix event_type classification, and add delays between sequential event requests.

**Architecture:** All event functions (`get_event_details`, `get_event_teams`, `get_event_results`) gain an optional `driver=` parameter following the same owns_driver pattern already used in `teams.py` and `players.py`. `sync_all.py` creates one driver for all 3 calls per event. Date parsing, prize targeting, and location filtering are improved in `events.py` helper functions.

**Tech Stack:** Python 3.10, Selenium, SQLAlchemy, pytest

---

### Task 1: Add `driver=None` parameter to event functions

**Files:**
- Modify: `src/scrapers/events.py` (functions at lines 107, 202, 329)
- Test: `tests/test_scrapers.py`

**Step 1: Write failing tests for driver reuse**

Add to `tests/test_scrapers.py`:

```python
class TestEventDriverReuse:
    """Event functions should accept an external driver and not quit it."""

    @patch('src.scrapers.events.time.sleep')
    @patch('src.scrapers.events.WebDriverWait')
    def test_get_event_details_external_driver(self, mock_wait_cls, mock_sleep):
        from src.scrapers.events import get_event_details

        mock_driver = MagicMock()
        mock_wait_cls.return_value.until.return_value = True
        mock_driver.find_elements.return_value = []

        result = get_event_details(8504, driver=mock_driver)

        mock_driver.quit.assert_not_called()

    @patch('src.scrapers.events.time.sleep')
    @patch('src.scrapers.events.WebDriverWait')
    def test_get_event_teams_external_driver(self, mock_wait_cls, mock_sleep):
        from src.scrapers.events import get_event_teams

        mock_driver = MagicMock()
        mock_wait_cls.return_value.until.return_value = True
        mock_driver.find_elements.return_value = []

        result = get_event_teams(8504, driver=mock_driver)

        mock_driver.quit.assert_not_called()

    @patch('src.scrapers.events.time.sleep')
    @patch('src.scrapers.events.WebDriverWait')
    def test_get_event_results_external_driver(self, mock_wait_cls, mock_sleep):
        from src.scrapers.events import get_event_results

        mock_driver = MagicMock()
        mock_wait_cls.return_value.until.return_value = True
        mock_driver.find_elements.return_value = []

        result = get_event_results(8504, driver=mock_driver)

        mock_driver.quit.assert_not_called()
```

**Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_scrapers.py::TestEventDriverReuse -v`
Expected: FAIL — `get_event_details()` does not accept `driver` kwarg

**Step 3: Implement driver reuse in all 3 functions**

In `src/scrapers/events.py`, apply the owns_driver pattern to each internal function:

For `_get_event_details_selenium`:
```python
def _get_event_details_selenium(event_id, headless=True, driver=None):
    owns_driver = driver is None
    if owns_driver:
        driver = create_driver(headless=headless)
    details = {}

    try:
        # ... existing body unchanged ...
        return details
    except Exception as e:
        logger.error("Erro ao buscar detalhes do evento %d: %s", event_id, e)
        traceback.print_exc()
        return {}
    finally:
        if owns_driver:
            driver.quit()
```

Same pattern for `_get_event_teams_selenium` and `_get_event_results_selenium`.

Update public wrappers:
```python
def get_event_details(event_id, headless=True, driver=None):
    return _get_event_details_selenium(event_id, headless=headless, driver=driver)

def get_event_teams(event_id, headless=True, driver=None):
    return _get_event_teams_selenium(event_id, headless=headless, driver=driver)

def get_event_results(event_id, headless=True, driver=None):
    return _get_event_results_selenium(event_id, headless=headless, driver=driver)
```

**Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_scrapers.py -v`
Expected: All tests PASS (54 existing + 3 new = 57)

**Step 5: Commit**

```bash
git add src/scrapers/events.py tests/test_scrapers.py
git commit -m "feat: add driver reuse to event scraper functions"
```

---

### Task 2: Use shared driver in sync_all.py

**Files:**
- Modify: `sync_all.py:26-62` (the 3 sequential calls in `sync_full_event`)

**Step 1: Write failing test**

Add to `tests/test_scrapers.py`:

```python
class TestSyncFullEventDriverReuse:
    """sync_full_event should create one driver for all 3 event calls."""

    @patch('sync_all.DriverPool')
    @patch('sync_all.get_event_results')
    @patch('sync_all.get_event_teams')
    @patch('sync_all.get_event_details')
    @patch('sync_all.create_driver')
    @patch('sync_all.session_scope')
    def test_shares_driver_across_event_calls(
        self, mock_session, mock_create_driver, mock_details, mock_teams,
        mock_results, mock_pool
    ):
        from sync_all import sync_full_event

        mock_driver = MagicMock()
        mock_create_driver.return_value = mock_driver
        mock_details.return_value = {'location': 'Test'}
        mock_teams.return_value = []
        mock_results.return_value = []

        # Mock session context manager
        mock_sess = MagicMock()
        mock_session.return_value.__enter__ = MagicMock(return_value=mock_sess)
        mock_session.return_value.__exit__ = MagicMock(return_value=False)
        mock_sess.query.return_value.filter_by.return_value.first.return_value = MagicMock()

        sync_full_event(8504)

        # All 3 calls should receive the shared driver
        mock_details.assert_called_once()
        assert mock_details.call_args[1].get('driver') == mock_driver
        mock_teams.assert_called_once()
        assert mock_teams.call_args[1].get('driver') == mock_driver

        # Driver should be quit once at the end
        mock_driver.quit.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_scrapers.py::TestSyncFullEventDriverReuse -v`
Expected: FAIL

**Step 3: Modify sync_full_event to create and share one driver**

In `sync_all.py`, add `create_driver` import and wrap the 3 calls:

```python
from src.scrapers.selenium_helpers import DriverPool, create_driver

def sync_full_event(event_id, headless=True, team_workers=3, player_workers=3):
    # ... print header ...

    # Create a shared driver for event-level scraping (details, teams, results)
    event_driver = create_driver(headless=headless)
    try:
        # 0. Buscar detalhes do evento
        print("Etapa 0/4: Buscando detalhes do evento...")
        event_details = get_event_details(event_id, headless=headless, driver=event_driver)
        random_delay(2.0, 4.0)

        # ... save details (unchanged) ...

        # 1. Buscar times do evento
        print("Etapa 1/4: Buscando times do evento...")
        team_ids = get_event_teams(event_id, headless=headless, driver=event_driver)
        random_delay(2.0, 4.0)

        # 2. Buscar placements e prizes
        print("Etapa 2/4: Buscando placements e prizes...")
        results = get_event_results(event_id, headless=headless, driver=event_driver)
    finally:
        event_driver.quit()

    # ... rest unchanged (team_ids check, team/player scraping) ...
```

**Step 4: Run tests**

Run: `python3 -m pytest tests/test_scrapers.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add sync_all.py tests/test_scrapers.py
git commit -m "perf: share single driver across event detail/teams/results calls"
```

---

### Task 3: Extract end_date from event page

**Files:**
- Modify: `src/scrapers/events.py` (both `_scrape_events_selenium` and `_get_event_details_selenium`)
- Test: `tests/test_scrapers.py`

**Step 1: Write failing tests for date parsing helper**

```python
class TestParseDateRange:
    def test_standard_range(self):
        from src.scrapers.events import _parse_date_range
        start, end = _parse_date_range(1709251200000, 1709683200000)
        assert start.year == 2024
        assert end > start

    def test_single_date(self):
        from src.scrapers.events import _parse_date_range
        start, end = _parse_date_range(1709251200000, None)
        assert start is not None
        assert end is None
```

**Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_scrapers.py::TestParseDateRange -v`

**Step 3: Implement end_date extraction**

In `_scrape_events_selenium`, extract both `data-unix` spans from each event element:

```python
# Replace the single date extraction (lines 52-60) with:
start_date = None
end_date = None
try:
    date_elems = event_elem.find_elements(By.CSS_SELECTOR, "span[data-unix]")
    if len(date_elems) >= 1:
        start_unix = int(date_elems[0].get_attribute("data-unix"))
        start_date = datetime.fromtimestamp(start_unix / 1000).date()
    if len(date_elems) >= 2:
        end_unix = int(date_elems[1].get_attribute("data-unix"))
        end_date = datetime.fromtimestamp(end_unix / 1000).date()
except Exception:
    pass
```

Add `_parse_date_range` helper:

```python
def _parse_date_range(start_unix_ms, end_unix_ms):
    """Convert unix timestamps (ms) to date objects."""
    start = datetime.fromtimestamp(start_unix_ms / 1000).date() if start_unix_ms else None
    end = datetime.fromtimestamp(end_unix_ms / 1000).date() if end_unix_ms else None
    return start, end
```

In `_get_event_details_selenium`, also extract dates from the event detail page:

```python
# After location extraction, add date extraction:
try:
    date_elems = driver.find_elements(By.CSS_SELECTOR, ".eventdate span[data-unix]")
    if len(date_elems) >= 2:
        start_unix = int(date_elems[0].get_attribute("data-unix"))
        end_unix = int(date_elems[1].get_attribute("data-unix"))
        details['start_date'] = datetime.fromtimestamp(start_unix / 1000).date()
        details['end_date'] = datetime.fromtimestamp(end_unix / 1000).date()
except Exception:
    pass
```

**Step 4: Run tests**

Run: `python3 -m pytest tests/test_scrapers.py -v`

**Step 5: Commit**

```bash
git add src/scrapers/events.py tests/test_scrapers.py
git commit -m "feat: extract end_date from event pages"
```

---

### Task 4: Improve prize_pool extraction targeting

**Files:**
- Modify: `src/scrapers/events.py:147-170`
- Test: `tests/test_scrapers.py`

**Step 1: Write test**

```python
class TestPrizeParsing:
    def test_parse_prize_value(self):
        from src.scrapers.events import _parse_prize_value
        assert _parse_prize_value("$250,000") == "$250,000"

    def test_parse_prize_value_none(self):
        from src.scrapers.events import _parse_prize_value
        assert _parse_prize_value("") is None

    def test_parse_prize_value_no_dollar(self):
        from src.scrapers.events import _parse_prize_value
        assert _parse_prize_value("no prize here") is None
```

**Step 2: Run to verify fail**

**Step 3: Implement improved prize extraction**

Add helper:
```python
def _parse_prize_value(text):
    """Extract prize value like '$250,000' from text."""
    if not text:
        return None
    match = re.search(r'\$[\d,]+', text)
    return match.group(0) if match else None
```

In `_get_event_details_selenium`, try specific containers first:

```python
# Replace prize extraction block with:
try:
    prize = None
    # Strategy 1: Look in known prize pool containers
    for selector in [".prizepool", ".prize-pool", ".eventMeta"]:
        try:
            container = driver.find_element(By.CSS_SELECTOR, selector)
            prize = _parse_prize_value(container.text)
            if prize:
                break
        except Exception:
            continue

    # Strategy 2: Look for elements with "Prize Pool" label nearby
    if not prize:
        try:
            labels = driver.find_elements(By.XPATH, "//*[contains(text(), 'Prize')]")
            for label in labels:
                parent = label.find_element(By.XPATH, "..")
                prize = _parse_prize_value(parent.text)
                if prize:
                    break
        except Exception:
            pass

    # Strategy 3: Fallback — largest $ value on page (current behavior)
    if not prize:
        prize_elems = driver.find_elements(By.XPATH, "//*[contains(text(), '$')]")
        max_prize = None
        max_amount = 0
        for elem in prize_elems:
            text = elem.text.strip()
            match = re.search(r'\$([0-9,]+)', text)
            if match:
                amount_str = match.group(1).replace(',', '')
                try:
                    amount = int(amount_str)
                    if amount > max_amount:
                        max_amount = amount
                        max_prize = match.group(0)
                except ValueError:
                    pass
        prize = max_prize

    if prize:
        details['prize_pool'] = prize
except Exception as e:
    logger.warning("Nao foi possivel extrair prize_pool: %s", e)
```

**Step 4: Run tests**

Run: `python3 -m pytest tests/test_scrapers.py -v`

**Step 5: Commit**

```bash
git add src/scrapers/events.py tests/test_scrapers.py
git commit -m "fix: improve prize_pool extraction with targeted selectors"
```

---

### Task 5: Fix location filter and event_type classification

**Files:**
- Modify: `src/scrapers/events.py` (lines 64-73)
- Test: `tests/test_scrapers.py`

**Step 1: Write tests**

```python
class TestLocationFilter:
    def test_is_likely_location(self):
        from src.scrapers.events import _is_likely_location
        assert _is_likely_location("Budapest, Hungary") is True
        assert _is_likely_location("Mayfair, London") is True
        assert _is_likely_location("Mar 10 - 15") is False
        assert _is_likely_location("Jan 2026") is False
        assert _is_likely_location("") is False
```

**Step 2: Run to verify fail**

**Step 3: Implement improved location filter**

Replace the month-name filter with a smarter heuristic:

```python
def _is_likely_location(text):
    """Check if text looks like a location rather than a date string."""
    if not text or len(text) < 3:
        return False
    # Date strings typically match patterns like "Mar 10 - 15" or "Jan 2026"
    date_pattern = re.match(
        r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d',
        text
    )
    if date_pattern:
        return False
    # Location strings typically contain a comma (City, Country)
    if ',' in text:
        return True
    return False
```

Use this in both `_scrape_events_selenium` and `_get_event_details_selenium` instead of the inline month check.

For `event_type` — leave as-is for now since there's no reliable CSS indicator for LAN/Online on the event list page. The detail page could be checked later but would require an extra request per event. Note this as a known limitation.

**Step 4: Run tests**

Run: `python3 -m pytest tests/test_scrapers.py -v`

**Step 5: Commit**

```bash
git add src/scrapers/events.py tests/test_scrapers.py
git commit -m "fix: improve location detection to handle 'May' edge case"
```

---

### Task 6: Update sync_all.py end_date handling and add import

**Files:**
- Modify: `sync_all.py`

**Step 1: Add random_delay import and update event details saving**

In `sync_all.py`, the event details dict may now contain `start_date` and `end_date`. Update the save block:

```python
from src.scrapers.selenium_helpers import DriverPool, create_driver, random_delay

# In sync_full_event, update the details save block:
with session_scope() as session:
    event = session.query(Event).filter_by(id=event_id).first()
    if event and event_details:
        if 'location' in event_details:
            event.location = event_details['location']
        if 'prize_pool' in event_details:
            event.prize_pool = event_details['prize_pool']
        if 'start_date' in event_details:
            event.start_date = event_details['start_date']
        if 'end_date' in event_details:
            event.end_date = event_details['end_date']
```

**Step 2: Run full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: All PASS

**Step 3: Commit**

```bash
git add sync_all.py
git commit -m "feat: save start_date/end_date from event details, add delays between requests"
```

---

### Task 7: Final verification

**Step 1: Run full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: All PASS (54 existing + new tests)

**Step 2: Verify no regressions in imports**

Run: `python3 -c "from src.scrapers.events import scrape_events, get_event_details, get_event_teams, get_event_results; print('OK')"`

**Step 3: Final commit if any remaining changes**

```bash
git status
```
