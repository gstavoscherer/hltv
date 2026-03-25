#!/usr/bin/env python3
"""Batch scrape all players for event 8504, saving after each.

Uses DriverPool for fast scraping with driver reuse.
"""
import sys
import time

from src.scrapers.players import scrape_player
from src.scrapers.selenium_helpers import DriverPool
from src.database import session_scope
from src.database.models import Player, EventTeam, TeamPlayer

# Get all player IDs for event 8504
with session_scope() as s:
    event_teams = s.query(EventTeam).filter_by(event_id=8504).all()
    player_ids = []
    for et in event_teams:
        tps = s.query(TeamPlayer).filter_by(team_id=et.team_id, is_current=True).all()
        player_ids.extend([tp.player_id for tp in tps])
    player_ids = list(set(player_ids))

# Check which already have data
with session_scope() as s:
    need_scrape = []
    for pid in player_ids:
        p = s.query(Player).filter_by(id=pid).first()
        if p and p.rating_2_0 is None:
            need_scrape.append(pid)

print(f'Total: {len(player_ids)}, Need scrape: {len(need_scrape)}', flush=True)

if not need_scrape:
    print('Nothing to scrape, all players have data.', flush=True)
    sys.exit(0)

success = 0
fail = 0
failed_ids = []

with DriverPool(size=2, headless=False) as pool:
    for idx, pid in enumerate(need_scrape, 1):
        print(f'[{idx}/{len(need_scrape)}] Player {pid}...', end=' ', flush=True)
        driver = pool.checkout()
        try:
            data = scrape_player(pid, headless=False, driver=driver)
            if data:
                with session_scope() as s:
                    player = s.query(Player).filter_by(id=pid).first()
                    if player:
                        for k, v in data.items():
                            if hasattr(player, k):
                                setattr(player, k, v)
                print(f'OK {data.get("nickname","?")} rating={data.get("rating_2_0","N/A")}', flush=True)
                success += 1
            else:
                print('FAIL', flush=True)
                fail += 1
                failed_ids.append(pid)
        except Exception as e:
            print(f'ERR: {e}', flush=True)
            pool.mark_bad(driver)
            fail += 1
            failed_ids.append(pid)
        finally:
            pool.checkin(driver)
        time.sleep(1)

# Retry failed players with fresh drivers
if failed_ids:
    print(f'\nRetrying {len(failed_ids)} failed players...', flush=True)
    retry_success = 0
    with DriverPool(size=1, headless=False) as pool:
        for idx, pid in enumerate(failed_ids, 1):
            print(f'  [Retry {idx}/{len(failed_ids)}] Player {pid}...', end=' ', flush=True)
            driver = pool.checkout()
            try:
                data = scrape_player(pid, headless=False, max_retries=5, driver=driver)
                if data:
                    with session_scope() as s:
                        player = s.query(Player).filter_by(id=pid).first()
                        if player:
                            for k, v in data.items():
                                if hasattr(player, k):
                                    setattr(player, k, v)
                    print(f'OK {data.get("nickname","?")} rating={data.get("rating_2_0","N/A")}', flush=True)
                    retry_success += 1
                    fail -= 1
                else:
                    print('FAIL', flush=True)
            except Exception as e:
                print(f'ERR: {e}', flush=True)
                pool.mark_bad(driver)
            finally:
                pool.checkin(driver)
            time.sleep(2)
    print(f'Retry recovered: {retry_success}/{len(failed_ids)}', flush=True)

print(f'\nDONE: {success + (len(failed_ids) - fail)} ok, {fail} failed', flush=True)
