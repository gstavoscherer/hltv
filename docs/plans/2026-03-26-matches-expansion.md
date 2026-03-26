# Matches Expansion Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add matches, per-map stats, and veto data to the HLTV scraper — the core data layer for predictive analytics and fantasy game.

**Architecture:** 4 new SQLAlchemy models (Match, MatchMap, MatchPlayerStats, MatchVeto), a new `matches.py` scraper with 3 functions (event matches list, match detail, map stats), and a new Etapa 5 in `sync_all.py` that chains them together using the shared driver pattern.

**Tech Stack:** Python 3.10, SQLAlchemy, Selenium, pytest

---

### Task 1: Add Match and MatchMap models

**Files:**
- Modify: `src/database/models.py`
- Test: `tests/test_models.py`

**Step 1: Write failing tests**

Add to `tests/test_models.py`:

```python
from src.database.models import Match, MatchMap


class TestMatchModel:
    def test_create_match(self, db_session):
        event = Event(id=1, name="Test Event")
        team1 = Team(id=1, name="Team A")
        team2 = Team(id=2, name="Team B")
        db_session.add_all([event, team1, team2])
        db_session.commit()

        match = Match(
            id=100, event_id=1, team1_id=1, team2_id=2,
            score1=2, score2=1, best_of=3, winner_id=1,
            date=date(2026, 2, 20)
        )
        db_session.add(match)
        db_session.commit()

        result = db_session.query(Match).filter_by(id=100).first()
        assert result is not None
        assert result.score1 == 2
        assert result.best_of == 3
        assert result.winner_id == 1

    def test_match_unique(self, db_session):
        event = Event(id=1, name="Test Event")
        team1 = Team(id=1, name="Team A")
        team2 = Team(id=2, name="Team B")
        db_session.add_all([event, team1, team2])
        db_session.commit()

        m1 = Match(id=100, event_id=1, team1_id=1, team2_id=2, best_of=3)
        db_session.add(m1)
        db_session.commit()

        m2 = Match(id=100, event_id=1, team1_id=1, team2_id=2, best_of=3)
        db_session.add(m2)
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestMatchMapModel:
    def test_create_match_map(self, db_session):
        event = Event(id=1, name="Test Event")
        team1 = Team(id=1, name="Team A")
        team2 = Team(id=2, name="Team B")
        db_session.add_all([event, team1, team2])
        db_session.commit()

        match = Match(id=100, event_id=1, team1_id=1, team2_id=2, best_of=3)
        db_session.add(match)
        db_session.commit()

        mm = MatchMap(
            id=5000, match_id=100, map_name="Mirage", map_number=1,
            team1_score=16, team2_score=9,
            team1_ct_score=10, team1_t_score=6,
            team2_ct_score=5, team2_t_score=4,
            picked_by=1, winner_id=1
        )
        db_session.add(mm)
        db_session.commit()

        result = db_session.query(MatchMap).filter_by(id=5000).first()
        assert result.map_name == "Mirage"
        assert result.team1_score == 16
        assert result.picked_by == 1
```

**Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_models.py::TestMatchModel tests/test_models.py::TestMatchMapModel -v`
Expected: FAIL — `Match` not found

**Step 3: Implement models**

Add to `src/database/models.py` after the `Player` class:

```python
class Match(Base):
    __tablename__ = 'matches'

    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey('events.id'), nullable=False)
    team1_id = Column(Integer, ForeignKey('teams.id'), nullable=False)
    team2_id = Column(Integer, ForeignKey('teams.id'), nullable=False)

    score1 = Column(Integer)
    score2 = Column(Integer)
    best_of = Column(Integer)
    date = Column(Date)
    winner_id = Column(Integer, ForeignKey('teams.id'), nullable=True)
    stars = Column(Integer)

    created_at = Column(DateTime, server_default=func.now())

    event = relationship("Event")
    team1 = relationship("Team", foreign_keys=[team1_id])
    team2 = relationship("Team", foreign_keys=[team2_id])
    winner = relationship("Team", foreign_keys=[winner_id])
    maps = relationship("MatchMap", back_populates="match", cascade="all, delete-orphan")
    vetos = relationship("MatchVeto", back_populates="match", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Match(id={self.id}, {self.team1_id} vs {self.team2_id})>"


class MatchMap(Base):
    __tablename__ = 'match_maps'

    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey('matches.id'), nullable=False)
    map_name = Column(String(50), nullable=False)
    map_number = Column(Integer, nullable=False)

    team1_score = Column(Integer)
    team2_score = Column(Integer)
    team1_ct_score = Column(Integer)
    team1_t_score = Column(Integer)
    team2_ct_score = Column(Integer)
    team2_t_score = Column(Integer)

    picked_by = Column(Integer, ForeignKey('teams.id'), nullable=True)
    winner_id = Column(Integer, ForeignKey('teams.id'), nullable=True)

    created_at = Column(DateTime, server_default=func.now())

    match = relationship("Match", back_populates="maps")
    picker = relationship("Team", foreign_keys=[picked_by])
    winner = relationship("Team", foreign_keys=[winner_id])
    player_stats = relationship("MatchPlayerStats", back_populates="match_map", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<MatchMap(id={self.id}, map={self.map_name})>"
```

**Step 4: Run tests**

Run: `python3 -m pytest tests/test_models.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/database/models.py tests/test_models.py
git commit -m "feat: add Match and MatchMap models"
```

---

### Task 2: Add MatchPlayerStats and MatchVeto models

**Files:**
- Modify: `src/database/models.py`
- Test: `tests/test_models.py`

**Step 1: Write failing tests**

```python
from src.database.models import MatchPlayerStats, MatchVeto


class TestMatchPlayerStatsModel:
    def test_create_match_player_stats(self, db_session):
        event = Event(id=1, name="Test Event")
        team1 = Team(id=1, name="Team A")
        team2 = Team(id=2, name="Team B")
        player = Player(id=10, nickname="s1mple")
        db_session.add_all([event, team1, team2, player])
        db_session.commit()

        match = Match(id=100, event_id=1, team1_id=1, team2_id=2, best_of=3)
        db_session.add(match)
        db_session.commit()

        mm = MatchMap(id=5000, match_id=100, map_name="Mirage", map_number=1)
        db_session.add(mm)
        db_session.commit()

        stats = MatchPlayerStats(
            map_id=5000, player_id=10, team_id=1,
            kills=25, deaths=15, assists=4, headshots=12,
            flash_assists=2, adr=85.3, kast=72.5, rating=1.35,
            opening_kills=3, opening_deaths=1, multi_kill_rounds=4,
            clutches_won=1
        )
        db_session.add(stats)
        db_session.commit()

        result = db_session.query(MatchPlayerStats).first()
        assert result.kills == 25
        assert result.rating == 1.35
        assert result.adr == 85.3

    def test_unique_player_per_map(self, db_session):
        event = Event(id=1, name="Test Event")
        team1 = Team(id=1, name="Team A")
        team2 = Team(id=2, name="Team B")
        player = Player(id=10, nickname="s1mple")
        db_session.add_all([event, team1, team2, player])
        db_session.commit()

        match = Match(id=100, event_id=1, team1_id=1, team2_id=2, best_of=3)
        mm = MatchMap(id=5000, match_id=100, map_name="Mirage", map_number=1)
        db_session.add_all([match, mm])
        db_session.commit()

        s1 = MatchPlayerStats(map_id=5000, player_id=10, team_id=1, kills=20)
        db_session.add(s1)
        db_session.commit()

        s2 = MatchPlayerStats(map_id=5000, player_id=10, team_id=1, kills=25)
        db_session.add(s2)
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestMatchVetoModel:
    def test_create_veto(self, db_session):
        event = Event(id=1, name="Test Event")
        team1 = Team(id=1, name="Team A")
        team2 = Team(id=2, name="Team B")
        db_session.add_all([event, team1, team2])
        db_session.commit()

        match = Match(id=100, event_id=1, team1_id=1, team2_id=2, best_of=3)
        db_session.add(match)
        db_session.commit()

        veto = MatchVeto(
            match_id=100, veto_number=1, team_id=1,
            action="removed", map_name="Ancient"
        )
        db_session.add(veto)
        db_session.commit()

        result = db_session.query(MatchVeto).first()
        assert result.action == "removed"
        assert result.map_name == "Ancient"
```

**Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_models.py::TestMatchPlayerStatsModel tests/test_models.py::TestMatchVetoModel -v`

**Step 3: Implement models**

Add to `src/database/models.py`:

```python
class MatchPlayerStats(Base):
    __tablename__ = 'match_player_stats'

    id = Column(Integer, primary_key=True, autoincrement=True)
    map_id = Column(Integer, ForeignKey('match_maps.id'), nullable=False)
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False)
    team_id = Column(Integer, ForeignKey('teams.id'), nullable=False)

    kills = Column(Integer)
    deaths = Column(Integer)
    assists = Column(Integer)
    headshots = Column(Integer)
    flash_assists = Column(Integer)
    adr = Column(Float)
    kast = Column(Float)
    rating = Column(Float)
    opening_kills = Column(Integer)
    opening_deaths = Column(Integer)
    multi_kill_rounds = Column(Integer)
    clutches_won = Column(Integer)

    created_at = Column(DateTime, server_default=func.now())

    match_map = relationship("MatchMap", back_populates="player_stats")
    player = relationship("Player")
    team = relationship("Team")

    __table_args__ = (
        UniqueConstraint('map_id', 'player_id', name='uq_map_player_stats'),
    )

    def __repr__(self):
        return f"<MatchPlayerStats(map_id={self.map_id}, player_id={self.player_id})>"


class MatchVeto(Base):
    __tablename__ = 'match_vetos'

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_id = Column(Integer, ForeignKey('matches.id'), nullable=False)
    veto_number = Column(Integer, nullable=False)
    team_id = Column(Integer, ForeignKey('teams.id'), nullable=True)
    action = Column(String(20), nullable=False)
    map_name = Column(String(50), nullable=False)

    created_at = Column(DateTime, server_default=func.now())

    match = relationship("Match", back_populates="vetos")
    team = relationship("Team")

    __table_args__ = (
        UniqueConstraint('match_id', 'veto_number', name='uq_match_veto_number'),
    )

    def __repr__(self):
        return f"<MatchVeto(match_id={self.match_id}, #{self.veto_number} {self.action} {self.map_name})>"
```

**Step 4: Run tests**

Run: `python3 -m pytest tests/test_models.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/database/models.py tests/test_models.py
git commit -m "feat: add MatchPlayerStats and MatchVeto models"
```

---

### Task 3: Create matches scraper — scrape_event_matches

**Files:**
- Create: `src/scrapers/matches.py`
- Test: `tests/test_scrapers.py`

**Step 1: Write failing tests**

```python
class TestScrapeEventMatches:
    def test_parse_match_result(self):
        from src.scrapers.matches import _parse_match_id_from_url
        assert _parse_match_id_from_url("/matches/2389987/team-a-vs-team-b-event") == 2389987

    def test_parse_match_id_none(self):
        from src.scrapers.matches import _parse_match_id_from_url
        assert _parse_match_id_from_url(None) is None

    def test_parse_best_of(self):
        from src.scrapers.matches import _parse_best_of
        assert _parse_best_of("bo3") == 3
        assert _parse_best_of("bo1") == 1
        assert _parse_best_of("bo5") == 5
        assert _parse_best_of("") is None
```

**Step 2: Run to verify fail**

Run: `python3 -m pytest tests/test_scrapers.py::TestScrapeEventMatches -v`

**Step 3: Implement**

Create `src/scrapers/matches.py`:

```python
"""Match scraper for HLTV."""

import logging
import re
import time
import traceback

from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from .selenium_helpers import create_driver, wait_for_cloudflare, random_delay
from .events import _extract_team_id_from_href

logger = logging.getLogger(__name__)


def _parse_match_id_from_url(url):
    """Extract match ID from HLTV match URL like /matches/2389987/slug."""
    if not url:
        return None
    match = re.search(r'/matches/(\d+)/', url)
    return int(match.group(1)) if match else None


def _parse_best_of(text):
    """Parse best-of from text like 'bo3', 'bo1', 'bo5'."""
    if not text:
        return None
    m = re.search(r'bo(\d)', text.lower())
    return int(m.group(1)) if m else None


def scrape_event_matches(event_id, headless=True, driver=None):
    """Scrape all match results for an event from /results?event={id}."""
    owns_driver = driver is None
    if owns_driver:
        driver = create_driver(headless=headless)

    matches = []
    try:
        url = f"https://www.hltv.org/results?event={event_id}"
        print(f"Buscando matches do evento {event_id}...")
        driver.get(url)
        wait_for_cloudflare(driver)
        random_delay(2.0, 4.0)

        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        result_elements = driver.find_elements(By.CSS_SELECTOR, ".result-con")
        print(f"  Encontrados {len(result_elements)} matches")

        for elem in result_elements:
            try:
                link = elem.find_element(By.CSS_SELECTOR, "a")
                href = link.get_attribute("href")
                match_id = _parse_match_id_from_url(href)
                if not match_id:
                    continue

                # Teams
                team_elems = elem.find_elements(By.CSS_SELECTOR, ".team")
                team1_name = team_elems[0].text.strip() if len(team_elems) > 0 else None
                team2_name = team_elems[1].text.strip() if len(team_elems) > 1 else None

                # Team IDs from lineup links or team links
                team1_id = None
                team2_id = None
                team_links = elem.find_elements(By.CSS_SELECTOR, "a[href*='/team/']")
                if len(team_links) >= 2:
                    team1_id = _extract_team_id_from_href(team_links[0].get_attribute("href"))
                    team2_id = _extract_team_id_from_href(team_links[1].get_attribute("href"))

                # Scores
                score1 = None
                score2 = None
                try:
                    score_won = elem.find_element(By.CSS_SELECTOR, ".score-won")
                    score_lost = elem.find_element(By.CSS_SELECTOR, ".score-lost")
                    # Determine which team won by checking parent position
                    score_elems = elem.find_elements(By.CSS_SELECTOR, ".result-score span")
                    if len(score_elems) >= 2:
                        score1 = int(score_elems[0].text.strip())
                        score2 = int(score_elems[1].text.strip())
                except Exception:
                    pass

                # Best of
                best_of = None
                try:
                    map_text = elem.find_element(By.CSS_SELECTOR, ".map-text")
                    best_of = _parse_best_of(map_text.text.strip())
                except Exception:
                    pass

                # Date from parent container
                match_date = None
                try:
                    unix = elem.get_attribute("data-zonedgrouping-entry-unix")
                    if unix:
                        match_date = datetime.fromtimestamp(int(unix) / 1000).date()
                except Exception:
                    pass

                # Stars
                stars = 0
                try:
                    star_elems = elem.find_elements(By.CSS_SELECTOR, "i.fa-star")
                    stars = len(star_elems)
                except Exception:
                    pass

                # Winner
                winner_id = None
                if score1 is not None and score2 is not None:
                    if score1 > score2:
                        winner_id = team1_id
                    elif score2 > score1:
                        winner_id = team2_id

                matches.append({
                    'id': match_id,
                    'event_id': event_id,
                    'team1_id': team1_id,
                    'team2_id': team2_id,
                    'team1_name': team1_name,
                    'team2_name': team2_name,
                    'score1': score1,
                    'score2': score2,
                    'best_of': best_of,
                    'date': match_date,
                    'winner_id': winner_id,
                    'stars': stars,
                })
            except Exception as e:
                logger.warning("Erro ao processar match: %s", e)
                continue

        print(f"  {len(matches)} matches coletados")
        return matches

    except Exception as e:
        logger.error("Erro ao buscar matches do evento %d: %s", event_id, e)
        traceback.print_exc()
        return []
    finally:
        if owns_driver:
            driver.quit()
```

**Step 4: Run tests**

Run: `python3 -m pytest tests/test_scrapers.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add src/scrapers/matches.py tests/test_scrapers.py
git commit -m "feat: add scrape_event_matches for match result listing"
```

---

### Task 4: Add scrape_match_detail (maps, vetos, half scores)

**Files:**
- Modify: `src/scrapers/matches.py`
- Test: `tests/test_scrapers.py`

**Step 1: Write failing tests**

```python
class TestParseVeto:
    def test_parse_veto_line(self):
        from src.scrapers.matches import _parse_veto_line
        result = _parse_veto_line("1. Vitality removed Ancient")
        assert result['veto_number'] == 1
        assert result['team_name'] == "Vitality"
        assert result['action'] == "removed"
        assert result['map_name'] == "Ancient"

    def test_parse_veto_picked(self):
        from src.scrapers.matches import _parse_veto_line
        result = _parse_veto_line("3. Vitality picked Overpass")
        assert result['action'] == "picked"
        assert result['map_name'] == "Overpass"

    def test_parse_veto_leftover(self):
        from src.scrapers.matches import _parse_veto_line
        result = _parse_veto_line("7. Anubis was left over")
        assert result['action'] == "left over"
        assert result['map_name'] == "Anubis"
        assert result['team_name'] is None

    def test_parse_veto_invalid(self):
        from src.scrapers.matches import _parse_veto_line
        result = _parse_veto_line("Best of 3 (LAN)")
        assert result is None


class TestParseHalfScores:
    def test_parse_half_scores(self):
        from src.scrapers.matches import _parse_half_scores
        ct, t = _parse_half_scores("(10:5; 6:4)")
        assert ct == 10
        assert t == 6

    def test_parse_half_scores_empty(self):
        from src.scrapers.matches import _parse_half_scores
        ct, t = _parse_half_scores("")
        assert ct is None
        assert t is None
```

**Step 2: Run to verify fail**

**Step 3: Implement**

Add to `src/scrapers/matches.py`:

```python
def _parse_veto_line(line):
    """Parse a veto line like '1. Vitality removed Ancient'."""
    # Left over pattern: "7. Anubis was left over"
    leftover = re.match(r'(\d+)\.\s+(\w+)\s+was\s+left\s+over', line.strip())
    if leftover:
        return {
            'veto_number': int(leftover.group(1)),
            'team_name': None,
            'action': 'left over',
            'map_name': leftover.group(2),
        }

    # Standard pattern: "1. TeamName removed/picked MapName"
    standard = re.match(r'(\d+)\.\s+(.+?)\s+(removed|picked)\s+(\w+)', line.strip())
    if standard:
        return {
            'veto_number': int(standard.group(1)),
            'team_name': standard.group(2),
            'action': standard.group(3),
            'map_name': standard.group(4),
        }

    return None


def _parse_half_scores(text):
    """Parse half scores from text like '(10:5; 6:4)'. Returns (ct_score, t_score)."""
    if not text:
        return None, None
    m = re.search(r'\((\d+):(\d+);\s*(\d+):(\d+)\)', text)
    if m:
        return int(m.group(1)), int(m.group(3))
    return None, None


def scrape_match_detail(match_id, headless=True, driver=None):
    """Scrape match detail page for maps, scores, and vetos."""
    owns_driver = driver is None
    if owns_driver:
        driver = create_driver(headless=headless)

    try:
        url = f"https://www.hltv.org/matches/{match_id}/placeholder"
        driver.get(url)
        wait_for_cloudflare(driver)
        random_delay(0.5, 1.5)

        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        result = {'match_id': match_id, 'maps': [], 'vetos': []}

        # Team IDs
        team_links = driver.find_elements(By.CSS_SELECTOR, ".team1-gradient a[href*='/team/'], .team2-gradient a[href*='/team/']")
        team_ids = []
        for tl in team_links:
            tid = _extract_team_id_from_href(tl.get_attribute("href"))
            if tid and tid not in team_ids:
                team_ids.append(tid)
        result['team1_id'] = team_ids[0] if len(team_ids) > 0 else None
        result['team2_id'] = team_ids[1] if len(team_ids) > 1 else None

        # Parse vetos
        try:
            veto_boxes = driver.find_elements(By.CSS_SELECTOR, ".veto-box .padding")
            for box in veto_boxes:
                lines = box.text.strip().split('\n')
                for line in lines:
                    parsed = _parse_veto_line(line)
                    if parsed:
                        result['vetos'].append(parsed)
        except Exception:
            pass

        # Parse maps
        map_holders = driver.find_elements(By.CSS_SELECTOR, ".mapholder")
        for idx, mh in enumerate(map_holders, 1):
            try:
                map_data = {'map_number': idx}

                # Map name
                try:
                    name_elem = mh.find_element(By.CSS_SELECTOR, ".mapname")
                    map_data['map_name'] = name_elem.text.strip()
                except Exception:
                    continue

                # Scores
                score_elems = mh.find_elements(By.CSS_SELECTOR, ".results-team-score")
                if len(score_elems) >= 2:
                    s1 = score_elems[0].text.strip()
                    s2 = score_elems[1].text.strip()
                    if s1 != '-' and s2 != '-':
                        map_data['team1_score'] = int(s1)
                        map_data['team2_score'] = int(s2)
                    else:
                        continue  # Unplayed map

                # Half scores
                half_elems = mh.find_elements(By.CSS_SELECTOR, ".results-center-half-score")
                if len(half_elems) >= 2:
                    ct1, t1 = _parse_half_scores(half_elems[0].text.strip())
                    ct2, t2 = _parse_half_scores(half_elems[1].text.strip())
                    map_data['team1_ct_score'] = ct1
                    map_data['team1_t_score'] = t1
                    map_data['team2_ct_score'] = ct2
                    map_data['team2_t_score'] = t2

                # Pick indicator
                try:
                    pick_left = mh.find_elements(By.CSS_SELECTOR, ".results-left.pick")
                    pick_right = mh.find_elements(By.CSS_SELECTOR, ".results-right.pick")
                    if pick_left:
                        map_data['picked_by'] = result.get('team1_id')
                    elif pick_right:
                        map_data['picked_by'] = result.get('team2_id')
                except Exception:
                    pass

                # Winner
                if 'team1_score' in map_data and 'team2_score' in map_data:
                    if map_data['team1_score'] > map_data['team2_score']:
                        map_data['winner_id'] = result.get('team1_id')
                    else:
                        map_data['winner_id'] = result.get('team2_id')

                # Map stats URL (mapstatsid)
                try:
                    stats_link = mh.find_element(By.CSS_SELECTOR, "a[href*='mapstatsid']")
                    href = stats_link.get_attribute("href")
                    stats_match = re.search(r'mapstatsid/(\d+)/', href)
                    if stats_match:
                        map_data['mapstats_id'] = int(stats_match.group(1))
                except Exception:
                    pass

                result['maps'].append(map_data)
            except Exception as e:
                logger.warning("Erro ao processar mapa %d: %s", idx, e)

        print(f"  Match {match_id}: {len(result['maps'])} mapas, {len(result['vetos'])} vetos")
        return result

    except Exception as e:
        logger.error("Erro ao buscar detalhes do match %d: %s", match_id, e)
        traceback.print_exc()
        return None
    finally:
        if owns_driver:
            driver.quit()
```

**Step 4: Run tests**

Run: `python3 -m pytest tests/test_scrapers.py -v`

**Step 5: Commit**

```bash
git add src/scrapers/matches.py tests/test_scrapers.py
git commit -m "feat: add scrape_match_detail for maps, vetos, half scores"
```

---

### Task 5: Add scrape_map_stats (per-player per-map stats)

**Files:**
- Modify: `src/scrapers/matches.py`
- Test: `tests/test_scrapers.py`

**Step 1: Write failing tests**

```python
class TestParseMapPlayerStats:
    def test_parse_kills_hs(self):
        from src.scrapers.matches import _parse_kills_hs
        kills, hs = _parse_kills_hs("25(12)")
        assert kills == 25
        assert hs == 12

    def test_parse_kills_hs_no_parens(self):
        from src.scrapers.matches import _parse_kills_hs
        kills, hs = _parse_kills_hs("17")
        assert kills == 17
        assert hs == 0

    def test_parse_assists_flash(self):
        from src.scrapers.matches import _parse_kills_hs
        assists, flash = _parse_kills_hs("9(3)")
        assert assists == 9
        assert flash == 3

    def test_parse_opening_kd(self):
        from src.scrapers.matches import _parse_opening_kd
        ok, od = _parse_opening_kd("5:2")
        assert ok == 5
        assert od == 2
```

**Step 2: Run to verify fail**

**Step 3: Implement**

Add to `src/scrapers/matches.py`:

```python
def _parse_kills_hs(text):
    """Parse 'N(M)' format used for kills(hs), assists(flash), deaths(traded)."""
    if not text:
        return 0, 0
    m = re.match(r'(\d+)\((\d+)\)', text.strip())
    if m:
        return int(m.group(1)), int(m.group(2))
    m2 = re.match(r'(\d+)', text.strip())
    if m2:
        return int(m2.group(1)), 0
    return 0, 0


def _parse_opening_kd(text):
    """Parse 'K:D' format for opening kills/deaths."""
    if not text:
        return 0, 0
    m = re.match(r'(\d+):(\d+)', text.strip())
    if m:
        return int(m.group(1)), int(m.group(2))
    return 0, 0


def scrape_map_stats(mapstats_id, headless=True, driver=None):
    """Scrape per-player stats for a specific map from /stats/matches/mapstatsid/{id}/."""
    owns_driver = driver is None
    if owns_driver:
        driver = create_driver(headless=headless)

    try:
        url = f"https://www.hltv.org/stats/matches/mapstatsid/{mapstats_id}/placeholder"
        driver.get(url)
        wait_for_cloudflare(driver)
        random_delay(0.5, 1.5)

        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".stats-table")))

        all_stats = []

        # Two visible stats tables (one per team)
        tables = driver.find_elements(By.CSS_SELECTOR, "table.stats-table.totalstats")
        if not tables:
            tables = driver.find_elements(By.CSS_SELECTOR, ".stats-table")

        for table in tables:
            # Skip hidden/eco-adjusted tables
            try:
                parent = table.find_element(By.XPATH, "..")
                if 'hidden' in (parent.get_attribute("class") or ""):
                    continue
            except Exception:
                pass

            rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
            for row in rows:
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) < 9:
                        continue

                    # Player ID from link
                    player_id = None
                    team_id = None
                    try:
                        player_link = row.find_element(By.CSS_SELECTOR, "a[href*='/player/']")
                        href = player_link.get_attribute("href")
                        pid_match = re.search(r'/player/(\d+)/', href)
                        if pid_match:
                            player_id = int(pid_match.group(1))
                    except Exception:
                        continue

                    if not player_id:
                        continue

                    # Try to get team ID from team link in the table header
                    try:
                        team_link = table.find_element(By.CSS_SELECTOR, "th a[href*='/team/']")
                        team_href = team_link.get_attribute("href")
                        tid_match = re.search(r'/team/(\d+)/', team_href)
                        if tid_match:
                            team_id = int(tid_match.group(1))
                    except Exception:
                        pass

                    stat = {'player_id': player_id, 'team_id': team_id, 'map_id': mapstats_id}

                    # Parse cells by class or position
                    # Order: player | opkd | mks | kast | 1vsx | k(hs) | a(f) | d(t) | adr | swing | rating
                    for cell in cells:
                        cls = cell.get_attribute("class") or ""
                        text = cell.text.strip()

                        if 'st-opkd' in cls:
                            stat['opening_kills'], stat['opening_deaths'] = _parse_opening_kd(text)
                        elif 'st-mks' in cls:
                            stat['multi_kill_rounds'] = int(text) if text.isdigit() else 0
                        elif 'st-kast' in cls:
                            stat['kast'] = float(text.replace('%', '')) if text else None
                        elif 'st-clutches' in cls:
                            stat['clutches_won'] = int(text) if text.isdigit() else 0
                        elif 'st-kills' in cls:
                            stat['kills'], stat['headshots'] = _parse_kills_hs(text)
                        elif 'st-assists' in cls:
                            stat['assists'], stat['flash_assists'] = _parse_kills_hs(text)
                        elif 'st-deaths' in cls:
                            stat['deaths'], _ = _parse_kills_hs(text)
                        elif 'st-adr' in cls:
                            try:
                                stat['adr'] = float(text) if text else None
                            except ValueError:
                                pass
                        elif 'st-rating' in cls:
                            try:
                                stat['rating'] = float(text) if text else None
                            except ValueError:
                                pass

                    all_stats.append(stat)
                except Exception as e:
                    logger.warning("Erro ao processar player stat row: %s", e)

        print(f"    Map {mapstats_id}: {len(all_stats)} player stats")
        return all_stats

    except Exception as e:
        logger.error("Erro ao buscar map stats %d: %s", mapstats_id, e)
        traceback.print_exc()
        return []
    finally:
        if owns_driver:
            driver.quit()
```

**Step 4: Run tests**

Run: `python3 -m pytest tests/test_scrapers.py -v`

**Step 5: Commit**

```bash
git add src/scrapers/matches.py tests/test_scrapers.py
git commit -m "feat: add scrape_map_stats for per-player per-map statistics"
```

---

### Task 6: Integrate into sync_all.py

**Files:**
- Modify: `sync_all.py`

**Step 1: Add imports and Etapa 5**

Add imports at top of `sync_all.py`:

```python
from src.scrapers.matches import scrape_event_matches, scrape_match_detail, scrape_map_stats
from src.database.models import Match, MatchMap, MatchPlayerStats, MatchVeto
```

Add after Etapa 4 (player stats save), before the final success print:

```python
    # 5. Sincronizar matches, mapas e stats por mapa
    print(f"\nEtapa 5/5: Sincronizando matches do evento...")

    # 5a. Get match list from results page
    event_driver = create_driver(headless=headless)
    try:
        match_list = scrape_event_matches(event_id, headless=headless, driver=event_driver)
    finally:
        event_driver.quit()

    if not match_list:
        print("  Nenhum match encontrado")
        print(f"\n{'='*70}")
        print(f"EVENTO {event_id} SINCRONIZADO COM SUCESSO!")
        print(f"{'='*70}\n")
        return

    # Filter out matches already in DB
    with session_scope() as session:
        existing_match_ids = {m.id for m in session.query(Match.id).filter(
            Match.event_id == event_id
        ).all()}
    new_matches = [m for m in match_list if m['id'] not in existing_match_ids]
    if len(match_list) - len(new_matches) > 0:
        print(f"  Pulando {len(match_list) - len(new_matches)} matches ja no banco")
    print(f"  {len(new_matches)} matches novos para processar")

    if not new_matches:
        print(f"\n{'='*70}")
        print(f"EVENTO {event_id} SINCRONIZADO COM SUCESSO!")
        print(f"{'='*70}\n")
        return

    # 5b. Save basic match data
    with session_scope() as session:
        for m in new_matches:
            match = Match(
                id=m['id'], event_id=event_id,
                team1_id=m.get('team1_id'), team2_id=m.get('team2_id'),
                score1=m.get('score1'), score2=m.get('score2'),
                best_of=m.get('best_of'), date=m.get('date'),
                winner_id=m.get('winner_id'), stars=m.get('stars'),
            )
            session.merge(match)

    # 5c. Scrape each match detail + map stats
    match_driver = create_driver(headless=headless)
    try:
        for idx, m in enumerate(new_matches, 1):
            mid = m['id']
            print(f"  [{idx}/{len(new_matches)}] Match {mid}...")

            detail = scrape_match_detail(mid, headless=headless, driver=match_driver)
            if not detail:
                continue
            random_delay(0.5, 1.5)

            # Save vetos
            with session_scope() as session:
                for v in detail.get('vetos', []):
                    # Resolve team_id from team_name
                    veto_team_id = None
                    if v.get('team_name'):
                        team = session.query(Team).filter(
                            Team.name.ilike(f"%{v['team_name']}%")
                        ).first()
                        if team:
                            veto_team_id = team.id

                    existing = session.query(MatchVeto).filter_by(
                        match_id=mid, veto_number=v['veto_number']
                    ).first()
                    if not existing:
                        session.add(MatchVeto(
                            match_id=mid,
                            veto_number=v['veto_number'],
                            team_id=veto_team_id,
                            action=v['action'],
                            map_name=v['map_name'],
                        ))

            # Save maps and scrape map stats
            for map_data in detail.get('maps', []):
                mapstats_id = map_data.get('mapstats_id')
                if not mapstats_id:
                    continue

                with session_scope() as session:
                    existing_map = session.query(MatchMap).filter_by(id=mapstats_id).first()
                    if not existing_map:
                        mm = MatchMap(
                            id=mapstats_id,
                            match_id=mid,
                            map_name=map_data.get('map_name', 'Unknown'),
                            map_number=map_data.get('map_number', 0),
                            team1_score=map_data.get('team1_score'),
                            team2_score=map_data.get('team2_score'),
                            team1_ct_score=map_data.get('team1_ct_score'),
                            team1_t_score=map_data.get('team1_t_score'),
                            team2_ct_score=map_data.get('team2_ct_score'),
                            team2_t_score=map_data.get('team2_t_score'),
                            picked_by=map_data.get('picked_by'),
                            winner_id=map_data.get('winner_id'),
                        )
                        session.add(mm)
                    else:
                        continue  # Already have this map's data

                # Scrape map player stats
                random_delay(0.5, 1.5)
                player_stats = scrape_map_stats(mapstats_id, headless=headless, driver=match_driver)

                if player_stats:
                    with session_scope() as session:
                        for ps in player_stats:
                            existing = session.query(MatchPlayerStats).filter_by(
                                map_id=mapstats_id, player_id=ps['player_id']
                            ).first()
                            if not existing:
                                session.add(MatchPlayerStats(
                                    map_id=mapstats_id,
                                    player_id=ps['player_id'],
                                    team_id=ps.get('team_id'),
                                    kills=ps.get('kills'),
                                    deaths=ps.get('deaths'),
                                    assists=ps.get('assists'),
                                    headshots=ps.get('headshots'),
                                    flash_assists=ps.get('flash_assists'),
                                    adr=ps.get('adr'),
                                    kast=ps.get('kast'),
                                    rating=ps.get('rating'),
                                    opening_kills=ps.get('opening_kills'),
                                    opening_deaths=ps.get('opening_deaths'),
                                    multi_kill_rounds=ps.get('multi_kill_rounds'),
                                    clutches_won=ps.get('clutches_won'),
                                ))
    finally:
        match_driver.quit()
```

Also update all print references from "Etapa N/4" to "Etapa N/5" throughout `sync_full_event`.

**Step 2: Run full test suite**

Run: `python3 -m pytest tests/ -v`

**Step 3: Commit**

```bash
git add sync_all.py
git commit -m "feat: integrate match/map/stats scraping into sync_all (Etapa 5)"
```

---

### Task 7: Live test and final verification

**Step 1: Initialize new tables**

```bash
python3 -c "from src.database import init_db; init_db(); print('OK')"
```

**Step 2: Run sync on a small event (or re-sync existing)**

```bash
PYTHONUNBUFFERED=1 xvfb-run --auto-servernum --server-args="-screen 0 1920x1080x24" \
    python3 sync_all.py --event 8047 --show
```

Expected: Etapas 0-4 skip quickly (data exists), Etapa 5 scrapes matches.

**Step 3: Verify data in DB**

```python
from src.database import session_scope
from src.database.models import Match, MatchMap, MatchPlayerStats, MatchVeto

with session_scope() as s:
    matches = s.query(Match).filter_by(event_id=8047).count()
    maps = s.query(MatchMap).count()
    stats = s.query(MatchPlayerStats).count()
    vetos = s.query(MatchVeto).count()
    print(f"Matches: {matches}, Maps: {maps}, PlayerStats: {stats}, Vetos: {vetos}")
```

**Step 4: Run full test suite**

Run: `python3 -m pytest tests/ -v`

**Step 5: Commit any remaining changes**
