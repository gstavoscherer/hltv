#!/usr/bin/env python3
"""Test script to verify fixes for KAST and event details."""

from src.scrapers.players import scrape_player
from src.scrapers.events import get_event_details

def test_player_kast():
    """Test player KAST extraction."""
    print("\n" + "="*70)
    print("Testing Player KAST and Rating extraction")
    print("="*70)

    # Test with s1mple (7998)
    player_id = 7998
    print(f"\nTesting with player ID: {player_id} (s1mple)")

    player_data = scrape_player(player_id, headless=True)

    if player_data:
        print("\n✅ Player data collected successfully!")
        print(f"\nKey stats:")
        print(f"  Nickname: {player_data.get('nickname', 'N/A')}")
        print(f"  Rating 2.0: {player_data.get('rating_2_0', 'N/A')}")
        print(f"  KAST: {player_data.get('kast', 'N/A')}%")
        print(f"  KPR: {player_data.get('kpr', 'N/A')}")
        print(f"  APR: {player_data.get('apr', 'N/A')}")
        print(f"  ADR: {player_data.get('adr', 'N/A')}")
        print(f"  Impact: {player_data.get('impact', 'N/A')}")

        # Check if KAST was extracted
        if player_data.get('kast'):
            print("\n✅ KAST extraction: SUCCESS")
        else:
            print("\n❌ KAST extraction: FAILED")

        # Check if Rating was extracted
        if player_data.get('rating_2_0'):
            print("✅ Rating extraction: SUCCESS")
        else:
            print("❌ Rating extraction: FAILED")

        return player_data.get('kast') is not None and player_data.get('rating_2_0') is not None
    else:
        print("\n❌ Failed to collect player data")
        return False

def test_event_details():
    """Test event details extraction."""
    print("\n" + "="*70)
    print("Testing Event Details (Location and Prize Pool)")
    print("="*70)

    # Test with PGL Major Copenhagen 2024 (7148)
    event_id = 7148
    print(f"\nTesting with event ID: {event_id} (PGL Major Copenhagen 2024)")

    event_details = get_event_details(event_id, headless=True)

    if event_details:
        print("\n✅ Event details collected successfully!")
        print(f"\nDetails:")
        print(f"  Location: {event_details.get('location', 'N/A')}")
        print(f"  Prize Pool: {event_details.get('prize_pool', 'N/A')}")

        # Check if location was extracted
        if event_details.get('location'):
            print("\n✅ Location extraction: SUCCESS")
        else:
            print("\n❌ Location extraction: FAILED")

        # Check if prize pool was extracted
        if event_details.get('prize_pool'):
            print("✅ Prize pool extraction: SUCCESS")
        else:
            print("❌ Prize pool extraction: FAILED")

        return event_details.get('location') is not None and event_details.get('prize_pool') is not None
    else:
        print("\n❌ Failed to collect event details")
        return False

if __name__ == '__main__':
    print("\n" + "="*70)
    print("HLTV Scraper Fixes - Test Suite")
    print("="*70)

    results = {}

    # Test player KAST
    results['player'] = test_player_kast()

    # Test event details
    results['event'] = test_event_details()

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"Player KAST/Rating: {'✅ PASS' if results['player'] else '❌ FAIL'}")
    print(f"Event Details: {'✅ PASS' if results['event'] else '❌ FAIL'}")

    if all(results.values()):
        print("\n🎉 All tests passed! Ready to run sync_all.py")
    else:
        print("\n⚠️  Some tests failed. Please review the output above.")
