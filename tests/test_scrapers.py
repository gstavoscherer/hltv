"""Tests for scraper logic with mocked Selenium."""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from src.scrapers.players import parse_stat_value
from src.scrapers.events import _parse_placement_number, _extract_team_id_from_href


class TestParseStatValue:
    def test_integer_string(self):
        assert parse_stat_value("1234") == 1234.0

    def test_float_string(self):
        assert parse_stat_value("1.28") == 1.28

    def test_with_commas(self):
        assert parse_stat_value("12,345") == 12345.0

    def test_percentage(self):
        assert parse_stat_value("65.3%") == 65.3

    def test_with_whitespace(self):
        assert parse_stat_value("  1.05  ") == 1.05

    def test_none_input(self):
        assert parse_stat_value(None) is None

    def test_empty_string(self):
        assert parse_stat_value("") is None

    def test_no_numbers(self):
        assert parse_stat_value("abc") is None

    def test_mixed_text_and_number(self):
        assert parse_stat_value("Rating: 1.15") == 1.15


class TestCreateDriver:
    @patch('src.scrapers.selenium_helpers.uc.Chrome')
    @patch('src.scrapers.selenium_helpers._resolve_chrome_binary', return_value=None)
    @patch('src.scrapers.selenium_helpers.acquire_slot')
    def test_create_driver_headless(self, mock_acquire, mock_binary, mock_chrome):
        from src.scrapers.selenium_helpers import create_driver

        mock_driver = MagicMock()
        mock_chrome.return_value = mock_driver

        driver = create_driver(headless=True)

        mock_acquire.assert_called_once()
        mock_chrome.assert_called_once()

        # headless is passed to uc.Chrome() constructor, not as option
        assert mock_chrome.call_args[1]['headless'] is True

    @patch('src.scrapers.selenium_helpers.uc.Chrome')
    @patch('src.scrapers.selenium_helpers._resolve_chrome_binary', return_value=None)
    @patch('src.scrapers.selenium_helpers.acquire_slot')
    def test_create_driver_not_headless(self, mock_acquire, mock_binary, mock_chrome):
        from src.scrapers.selenium_helpers import create_driver

        mock_driver = MagicMock()
        mock_chrome.return_value = mock_driver

        driver = create_driver(headless=False)

        assert mock_chrome.call_args[1]['headless'] is False

    @patch('src.scrapers.selenium_helpers.uc.Chrome')
    @patch('src.scrapers.selenium_helpers._resolve_chrome_binary', return_value=None)
    @patch('src.scrapers.selenium_helpers.acquire_slot')
    def test_no_single_process_flag(self, mock_acquire, mock_binary, mock_chrome):
        from src.scrapers.selenium_helpers import create_driver

        mock_driver = MagicMock()
        mock_chrome.return_value = mock_driver

        driver = create_driver(headless=True)

        options = mock_chrome.call_args[1]['options']
        args = options.arguments
        assert '--single-process' not in args

    @patch('src.scrapers.selenium_helpers.uc.Chrome')
    @patch('src.scrapers.selenium_helpers._resolve_chrome_binary', return_value=None)
    @patch('src.scrapers.selenium_helpers.acquire_slot')
    def test_no_hardcoded_debug_port(self, mock_acquire, mock_binary, mock_chrome):
        from src.scrapers.selenium_helpers import create_driver

        mock_driver = MagicMock()
        mock_chrome.return_value = mock_driver

        driver = create_driver(headless=True)

        options = mock_chrome.call_args[1]['options']
        args = options.arguments
        assert not any('remote-debugging-port' in arg for arg in args)

    @patch('src.scrapers.selenium_helpers.uc.Chrome')
    @patch('src.scrapers.selenium_helpers._resolve_chrome_binary', return_value=None)
    @patch('src.scrapers.selenium_helpers.acquire_slot')
    def test_vps_options_present(self, mock_acquire, mock_binary, mock_chrome):
        from src.scrapers.selenium_helpers import create_driver

        mock_driver = MagicMock()
        mock_chrome.return_value = mock_driver

        driver = create_driver(headless=True)

        options = mock_chrome.call_args[1]['options']
        args = options.arguments
        # undetected-chromedriver handles anti-detection internally
        # verify VPS-essential options are present
        assert '--no-sandbox' in args
        assert '--disable-dev-shm-usage' in args

    @patch('src.scrapers.selenium_helpers.uc.Chrome', side_effect=Exception("Chrome not found"))
    @patch('src.scrapers.selenium_helpers._resolve_chrome_binary', return_value=None)
    @patch('src.scrapers.selenium_helpers.acquire_slot')
    @patch('src.scrapers.selenium_helpers.release_slot')
    @patch('src.scrapers.selenium_helpers.time.sleep')
    def test_create_driver_retries_and_releases_slot_on_failure(
        self, mock_sleep, mock_release, mock_acquire, mock_binary, mock_chrome
    ):
        from src.scrapers.selenium_helpers import create_driver

        with pytest.raises(Exception, match="Chrome not found"):
            create_driver(headless=True)

        assert mock_chrome.call_count == 3
        mock_release.assert_called_once()


class TestResolveBinary:
    @patch.dict('os.environ', {'CHROME_BINARY': '/usr/bin/test-chrome'})
    @patch('os.path.exists', return_value=True)
    def test_env_var_override(self, mock_exists):
        from src.scrapers.selenium_helpers import _resolve_chrome_binary
        result = _resolve_chrome_binary()
        assert result == '/usr/bin/test-chrome'

    @patch.dict('os.environ', {}, clear=True)
    @patch('os.path.exists', return_value=False)
    @patch('shutil.which', return_value=None)
    def test_returns_none_when_no_chrome(self, mock_which, mock_exists):
        from src.scrapers.selenium_helpers import _resolve_chrome_binary
        # Remove CHROME_BINARY if set
        import os
        os.environ.pop('CHROME_BINARY', None)
        result = _resolve_chrome_binary()
        assert result is None


class TestScrapeTeam:
    @patch('src.scrapers.teams.time.sleep')
    @patch('src.scrapers.teams.WebDriverWait')
    @patch('src.scrapers.teams.create_driver')
    def test_scrape_team_returns_team_data(self, mock_create_driver, mock_wait_cls, mock_sleep):
        from src.scrapers.teams import scrape_team

        mock_driver = MagicMock()
        mock_create_driver.return_value = mock_driver

        # Mock WebDriverWait().until() to just return
        mock_wait_cls.return_value.until.return_value = True

        # Mock team name
        name_mock = MagicMock()
        name_mock.text = "Natus Vincere"

        # Mock country
        country_mock = MagicMock()
        country_mock.get_attribute.return_value = "Ukraine"
        country_mock.text = "Ukraine"

        # Mock rank
        rank_mock = MagicMock()
        rank_mock.text = "#1"

        # Mock player links
        player_mock = MagicMock()
        player_mock.get_attribute.return_value = "https://www.hltv.org/player/7998/s1mple"
        player_mock.text = "s1mple"

        def find_element_side_effect(by, value):
            if value == "profile-team-name":
                return name_mock
            elif value == ".team-country":
                return country_mock
            elif value == ".profile-team-stat .right":
                return rank_mock
            raise Exception("Not found")

        def find_elements_side_effect(by, value):
            if value == ".bodyshot-team a":
                return [player_mock]
            return []

        mock_driver.find_element.side_effect = find_element_side_effect
        mock_driver.find_elements.side_effect = find_elements_side_effect

        result = scrape_team(100, headless=True)

        assert result is not None
        assert result['team']['name'] == "Natus Vincere"
        assert result['team']['id'] == 100
        assert len(result['roster']) == 1
        assert result['roster'][0]['nickname'] == "s1mple"

    @patch('src.scrapers.teams.time.sleep')
    @patch('src.scrapers.teams.WebDriverWait')
    def test_scrape_team_with_external_driver(self, mock_wait_cls, mock_sleep):
        from src.scrapers.teams import scrape_team

        mock_driver = MagicMock()
        mock_wait_cls.return_value.until.return_value = True

        name_mock = MagicMock()
        name_mock.text = "FaZe Clan"
        mock_driver.find_element.return_value = name_mock
        mock_driver.find_elements.return_value = []

        result = scrape_team(100, headless=True, driver=mock_driver)

        assert result is not None
        # External driver should NOT be quit
        mock_driver.quit.assert_not_called()


class TestParsePlacement:
    def test_first_place(self):
        assert _parse_placement_number("1st") == 1

    def test_second_place(self):
        assert _parse_placement_number("2nd") == 2

    def test_third_place(self):
        assert _parse_placement_number("3rd") == 3

    def test_range_placement(self):
        assert _parse_placement_number("3-4th") == 3

    def test_wide_range(self):
        assert _parse_placement_number("5-8th") == 5

    def test_none_input(self):
        assert _parse_placement_number(None) is None

    def test_empty_string(self):
        assert _parse_placement_number("") is None

    def test_text_with_placement(self):
        assert _parse_placement_number("Team NAVI\n1st\n$500,000") == 1


class TestExtractTeamId:
    def test_valid_url(self):
        assert _extract_team_id_from_href("https://www.hltv.org/team/4608/natus-vincere") == 4608

    def test_none_url(self):
        assert _extract_team_id_from_href(None) is None

    def test_no_team_url(self):
        assert _extract_team_id_from_href("https://www.hltv.org/player/7998/s1mple") is None

    def test_invalid_id(self):
        assert _extract_team_id_from_href("https://www.hltv.org/team/abc/name") is None


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


class TestScrapePlayerRetry:
    @patch('src.scrapers.players.time.sleep')
    @patch('src.scrapers.players.create_driver')
    def test_retries_on_timeout(self, mock_create_driver, mock_sleep):
        from src.scrapers.players import scrape_player
        from selenium.common.exceptions import TimeoutException

        mock_driver = MagicMock()
        mock_create_driver.return_value = mock_driver

        # Make WebDriverWait raise TimeoutException every time
        mock_wait = MagicMock()
        mock_wait.until.side_effect = TimeoutException("timeout")

        with patch('src.scrapers.players.wait_for_cloudflare', return_value=True):
            with patch('src.scrapers.players.WebDriverWait', return_value=mock_wait):
                result = scrape_player(9999, headless=True, max_retries=2)

        assert result is None
        # Driver is created once and reused for retries, quit once at the end
        assert mock_create_driver.call_count == 1
        mock_driver.quit.assert_called()


class TestScrapePlayer:
    @patch('src.scrapers.players.time.sleep')
    @patch('src.scrapers.players.WebDriverWait')
    @patch('src.scrapers.players.create_driver')
    def test_scrape_player_returns_player_data(self, mock_create_driver, mock_wait_cls, mock_sleep):
        from src.scrapers.players import scrape_player

        mock_driver = MagicMock()
        mock_create_driver.return_value = mock_driver

        # Mock WebDriverWait().until() to just return
        mock_wait_cls.return_value.until.return_value = True

        # Mock title
        type(mock_driver).title = PropertyMock(return_value="Oleksandr 's1mple' Kostyliev - HLTV")

        # Mock stats rows
        row_mock = MagicMock()
        span1 = MagicMock()
        span1.text = "Total kills"
        span2 = MagicMock()
        span2.text = "35,647"
        row_mock.find_elements.return_value = [span1, span2]

        mock_driver.find_elements.return_value = [row_mock]

        # Mock find_element to raise for optional elements
        mock_driver.find_element.side_effect = Exception("Not found")

        result = scrape_player(7998, headless=True)

        assert result is not None
        assert result['id'] == 7998
        assert result['nickname'] == 's1mple'
        assert result['total_kills'] == 35647
