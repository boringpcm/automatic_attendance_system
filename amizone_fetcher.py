#!/usr/bin/env python3
"""
Amizone Attendance & Timetable Scraper Module
Connects to Amizone (https://s.amizone.net/) to fetch attendance and weekly timetable.

Supports:
1. Fast CDP connection if Chrome is already running with remote debugging (port 9222).
2. Automated Selenium browser login with anti-detection and Cloudflare Turnstile handling.
3. Interactive user login assistance in browser if desired.
4. Local credential storage (optional, stored locally in .credentials.json).
5. Offline caching for both attendance (attendance_cache.json) and timetable (timetable_cache.json).
"""

from __future__ import annotations

import getpass
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

# Selenium imports
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

try:
    import websocket
except ImportError:
    websocket = None

BASE_DIR = Path(__file__).resolve().parent
CACHE_FILE = BASE_DIR / "attendance_cache.json"
TIMETABLE_CACHE_FILE = BASE_DIR / "timetable_cache.json"
CREDS_FILE = BASE_DIR / ".credentials.json"
AMIZONE_HOME = "https://s.amizone.net/Home"
AMIZONE_LOGIN = "https://s.amizone.net/"
AMIZONE_TIMETABLE = "https://s.amizone.net/TimeTable"

ATTENDANCE_EXTRACTION_JS = """
(() => {
    const items = document.querySelectorAll('#tasks li, ul.item-list li');
    if (!items || items.length === 0) return [];
    return Array.from(items).map(li => {
        const codeEl = li.querySelector('.sub-code');
        const countEl = li.querySelector('.class-count');
        const percentEl = li.querySelector('.percent');
        const lblEl = li.querySelector('.lbl');
        let name = '';
        if (lblEl) {
            const clone = lblEl.cloneNode(true);
            const sc = clone.querySelector('.sub-code');
            if (sc) sc.remove();
            name = clone.innerText.trim();
        }
        let code = codeEl ? codeEl.innerText.replace(/[\\[\\]]/g, '').trim() : '';
        return {
            code: code,
            name: name,
            count: countEl ? countEl.innerText.trim() : '',
            percent: percentEl ? percentEl.innerText.trim() : ''
        };
    }).filter(x => x.code && x.count);
})()
"""

TIMETABLE_CARDS_JS = """
(() => {
    const timeRegex = /(\\d{1,2}:\\d{2})\\s*(?:to|-)\\s*(\\d{1,2}:\\d{2})/i;
    const codeRegex = /\\b([A-Z]{3,8}\\d{3,8})\\b/;

    const elements = Array.from(document.querySelectorAll('div, td, [class*="card"], [class*="schedule"], [class*="slot"], [class*="item"]'))
        .filter(el => {
            if (el.offsetParent === null && el.offsetWidth === 0 && el.offsetHeight === 0) return false;
            const txt = el.innerText || '';
            return timeRegex.test(txt) && codeRegex.test(txt);
        });

    const leafCards = elements.filter(c => !elements.some(other => other !== c && c.contains(other)));
    const results = [];
    const seen = new Set();

    for (const c of leafCards) {
        const txt = c.innerText.trim();
        const tm = txt.match(timeRegex);
        const cm = txt.match(codeRegex);
        if (!tm || !cm) continue;

        const start = tm[1];
        const end = tm[2];
        const code = cm[1];
        const key = `${start}-${end}-${code}`;
        if (seen.has(key)) continue;
        seen.add(key);

        const lines = txt.split('\\n').map(s => s.trim()).filter(Boolean);
        let faculty = '';
        let room = '';
        for (const line of lines) {
            if (line.includes('[') && line.includes(']')) {
                faculty = line;
            } else if (/LT-\\d|LAB|ROOM|TF-|FF-|GF-|CR-\\d/i.test(line)) {
                room = line;
            }
        }

        results.push({
            start: start,
            end: end,
            code: code,
            faculty: faculty,
            room: room
        });
    }

    results.sort((a, b) => a.start.localeCompare(b.start));
    return results;
})()
"""


# ---------------------------------------------------------------------------
# CACHE & CREDENTIAL HELPERS
# ---------------------------------------------------------------------------

def load_cached_attendance() -> dict[str, Any] | None:
    """Load cached attendance data if available."""
    if not CACHE_FILE.exists():
        return None
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_cached_attendance(data: list[dict], username: str = "") -> None:
    """Save attendance data to local cache with timestamp."""
    payload = {
        "timestamp": datetime.now().isoformat(),
        "date_str": datetime.now().strftime("%d %b %Y, %I:%M %p"),
        "username": username,
        "records": data,
    }
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except Exception as exc:
        print(f"[Warning] Failed to save attendance cache: {exc}")


def load_cached_timetable() -> dict[str, Any] | None:
    """Load cached timetable data if available."""
    if not TIMETABLE_CACHE_FILE.exists():
        return None
    try:
        with open(TIMETABLE_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_cached_timetable(timetable_data: dict, username: str = "") -> None:
    """Save timetable data to local cache with timestamp."""
    formatted_days = {str(k): v for k, v in timetable_data.items()}
    payload = {
        "timestamp": datetime.now().isoformat(),
        "date_str": datetime.now().strftime("%d %b %Y, %I:%M %p"),
        "username": username,
        "days": formatted_days,
    }
    try:
        with open(TIMETABLE_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except Exception as exc:
        print(f"[Warning] Failed to save timetable cache: {exc}")


def load_saved_credentials() -> tuple[str, str] | None:
    """Load saved credentials from .credentials.json."""
    if not CREDS_FILE.exists():
        return None
    try:
        with open(CREDS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            u = data.get("username", "").strip()
            p = data.get("password", "").strip()
            if u and p:
                return u, p
    except Exception:
        pass
    return None


def save_credentials(username: str, password: str) -> None:
    """Save credentials to local file."""
    try:
        with open(CREDS_FILE, "w", encoding="utf-8") as f:
            json.dump({"username": username, "password": password}, f, indent=2)
        print("  [Saved] Credentials saved locally for future automatic runs.")
    except Exception as exc:
        print(f"[Warning] Failed to save credentials: {exc}")


def clear_saved_data() -> None:
    """Delete saved credentials, attendance cache, and timetable cache."""
    cleared = []
    if CREDS_FILE.exists():
        CREDS_FILE.unlink()
        cleared.append("saved credentials")
    if CACHE_FILE.exists():
        CACHE_FILE.unlink()
        cleared.append("attendance cache")
    if TIMETABLE_CACHE_FILE.exists():
        TIMETABLE_CACHE_FILE.unlink()
        cleared.append("timetable cache")
    if cleared:
        print(f"Cleared: {', '.join(cleared)}.")
    else:
        print("No stored credentials or cache found.")


# ---------------------------------------------------------------------------
# CDP / FAST SCRAPE & NATIVE CHROME RUNNER
# ---------------------------------------------------------------------------

def find_chrome_executable() -> str | None:
    """Locate the native Google Chrome executable on the host system."""
    candidates = [
        # macOS
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        # Linux
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        # Windows
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for c in candidates:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


class CDPClient:
    """Lightweight CDP WebSocket client for tab inspection & extraction."""
    def __init__(self, ws_conn):
        self.ws = ws_conn
        self.msg_id = 1

    def call(self, method: str, params: dict | None = None) -> dict:
        req_data = {"id": self.msg_id, "method": method, "params": params or {}}
        self.msg_id += 1
        self.ws.send(json.dumps(req_data))
        while True:
            r = json.loads(self.ws.recv())
            if r.get("id") == req_data["id"]:
                return r


def try_cdp_scrape(port: int = 9222) -> tuple[list[dict], dict[int, list[dict]]] | None:
    """
    Attempt to scrape directly via Chrome Remote Debugging port if Chrome is already open.
    Requires no chromedriver and works instantaneously.
    """
    if not websocket:
        return None

    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/json")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            tabs = json.loads(resp.read().decode())

        target = None
        for t in tabs:
            if t.get("type") != "page":
                continue
            url = t.get("url", "")
            if "s.amizone.net/Home" in url or "s.amizone.net/home" in url:
                target = t
                break
            elif "s.amizone.net" in url and not target:
                target = t

        if not target or "webSocketDebuggerUrl" not in target:
            return None

        ws_url = target["webSocketDebuggerUrl"]
        ws = websocket.create_connection(ws_url, timeout=3.0)
        cdp = CDPClient(ws)

        # Check if URL is Home
        eval_url = cdp.call("Runtime.evaluate", {"expression": "window.location.href"})
        curr_url = eval_url.get("result", {}).get("result", {}).get("value", "")

        if "s.amizone.net" not in curr_url:
            ws.close()
            return None

        # Execute attendance extraction script
        res = cdp.call(
            "Runtime.evaluate",
            {"expression": ATTENDANCE_EXTRACTION_JS, "returnByValue": True},
        )
        val = res.get("result", {}).get("result", {}).get("value")
        records = val if (isinstance(val, list) and len(val) > 0) else []

        ws.close()

        if records:
            cached_tt = load_cached_timetable()
            tt_data = {int(k): v for k, v in cached_tt["days"].items()} if cached_tt and "days" in cached_tt else {}
            return records, tt_data
    except Exception:
        pass
    return None


def fetch_via_native_chrome(timeout_seconds: int = 240) -> tuple[list[dict], dict[int, list[dict]]] | None:
    """
    Launch native Google Chrome directly with remote debugging port enabled.
    This guarantees 100% genuine browser TLS and DOM environment with NO chromedriver,
    ensuring Cloudflare Turnstile passes seamlessly without bot detection.
    """
    chrome_exe = find_chrome_executable()
    if not chrome_exe or not websocket:
        return None

    port = 9222
    profile_dir = Path.home() / ".amizone_chrome_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    # 1. Check if Chrome with port 9222 is already open
    is_running = False
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1.0):
            is_running = True
    except Exception:
        pass

    proc = None
    if not is_running:
        cmd = [
            chrome_exe,
            f"--remote-debugging-port={port}",
            "--remote-allow-origins=*",
            f"--user-data-dir={profile_dir}",
            AMIZONE_LOGIN,
        ]
        print("\n[1/3] Launching native Google Chrome (Cloudflare-safe mode)...")
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2.0)

    print("\n" + "=" * 70)
    print("👉 NATIVE GOOGLE CHROME LAUNCHED (CLOUDFLARE SAFE)")
    print("A genuine Chrome window has opened on your screen.")
    print("Please log into Amizone and click the Cloudflare verification.")
    print("Because this is your genuine Chrome browser (no automation driver),")
    print("Cloudflare Turnstile will verify successfully without failing!")
    print(f"(Waiting up to {timeout_seconds} seconds for login...)")
    print("=" * 70 + "\n")

    # 2. Wait for login by polling tabs
    start_time = time.time()
    logged_in_tab = None

    while time.time() - start_time < timeout_seconds:
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{port}/json")
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                tabs = json.loads(resp.read().decode())

            for t in tabs:
                if t.get("type") != "page":
                    continue
                url = t.get("url", "").lower()
                if "s.amizone.net/home" in url:
                    logged_in_tab = t
                    break
            if logged_in_tab:
                break
        except Exception:
            pass
        time.sleep(1.0)

    if not logged_in_tab:
        if proc:
            try:
                proc.terminate()
            except Exception:
                pass
        raise TimeoutError("Timed out waiting for Amizone login in Chrome.")

    print("  ✓ Login detected! Extracting attendance and timetable via CDP...")
    time.sleep(1.5)

    try:
        ws_url = logged_in_tab["webSocketDebuggerUrl"]
        ws = websocket.create_connection(ws_url, timeout=5.0)
        cdp = CDPClient(ws)

        # Detect user name
        user_res = cdp.call("Runtime.evaluate", {
            "expression": "(() => { const el = document.querySelector('span.user-info, .user-name'); return el ? el.innerText.trim() : ''; })()",
            "returnByValue": True
        })
        detected_user = user_res.get("result", {}).get("result", {}).get("value") or "LiveStudent"
        detected_user = detected_user.replace("\n", " ")

        # Extract attendance
        att_res = cdp.call("Runtime.evaluate", {
            "expression": ATTENDANCE_EXTRACTION_JS,
            "returnByValue": True
        })
        records = att_res.get("result", {}).get("result", {}).get("value")
        if not records or not isinstance(records, list) or len(records) == 0:
            ws.close()
            raise RuntimeError("Connected to dashboard, but could not find attendance cards in DOM.")

        # Save attendance cache
        save_cached_attendance(records, username=detected_user)
        print(f"  ✓ Successfully scraped {len(records)} attendance subjects!")

        # Extract timetable
        timetable = {i: [] for i in range(7)}
        try:
            print("  [Timetable] Navigating to Weekly Timetable...")
            cdp.call("Page.navigate", {"url": AMIZONE_TIMETABLE})
            time.sleep(2.5)

            day_indices = {
                "monday": 0, "tuesday": 1, "wednesday": 2,
                "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6
            }
            for day_name, day_idx in day_indices.items():
                click_js = f"""
                (() => {{
                    const els = Array.from(document.querySelectorAll('a, li, button, span'));
                    const target = els.find(el => el.innerText.trim().toLowerCase().includes('{day_name}') && el.innerText.trim().length <= 25);
                    if (target) {{ target.click(); return true; }}
                    return false;
                }})()
                """
                cdp.call("Runtime.evaluate", {"expression": click_js})
                time.sleep(0.4)
                cards_res = cdp.call("Runtime.evaluate", {"expression": TIMETABLE_CARDS_JS, "returnByValue": True})
                cards = cards_res.get("result", {}).get("result", {}).get("value")
                if isinstance(cards, list) and len(cards) > 0:
                    timetable[day_idx] = cards

            total_slots = sum(len(v) for v in timetable.values())
            if total_slots > 0:
                save_cached_timetable(timetable, username=detected_user)
                print(f"  ✓ Successfully mapped {total_slots} timetable slots from Amizone!")
            else:
                cached_tt = load_cached_timetable()
                if cached_tt and "days" in cached_tt:
                    timetable = {int(k): v for k, v in cached_tt["days"].items()}
        except Exception as exc:
            print(f"  [Notice] Timetable extraction: {exc}; using cached/default timetable.")
            cached_tt = load_cached_timetable()
            if cached_tt and "days" in cached_tt:
                timetable = {int(k): v for k, v in cached_tt["days"].items()}

        ws.close()
        if proc:
            try:
                proc.terminate()
            except Exception:
                pass

        return records, timetable

    except Exception as exc:
        if proc:
            try:
                proc.terminate()
            except Exception:
                pass
        raise exc


# ---------------------------------------------------------------------------
# SELENIUM SCRAPER
# ---------------------------------------------------------------------------

def scrape_timetable_from_driver(driver: webdriver.Chrome) -> dict[int, list[dict]]:
    """
    Navigate through day tabs on https://s.amizone.net/TimeTable and extract all slots.
    """
    day_indices = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }
    timetable: dict[int, list[dict]] = {i: [] for i in range(7)}

    try:
        print("  [Timetable] Navigating to Weekly Schedule (https://s.amizone.net/TimeTable)...")
        driver.get(AMIZONE_TIMETABLE)
        time.sleep(2)

        for day_name, day_idx in day_indices.items():
            try:
                # Find day tab / button
                xpath_selectors = [
                    f"//*[self::a or self::li or self::button or self::span][contains(translate(normalize-space(text()), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{day_name}')]",
                ]
                for xp in xpath_selectors:
                    elements = driver.find_elements(By.XPATH, xp)
                    for el in elements:
                        txt = el.text.strip().lower()
                        if day_name in txt and len(txt) <= 25:
                            try:
                                driver.execute_script("arguments[0].click();", el)
                                time.sleep(0.4)
                                break
                            except Exception:
                                pass

                # Extract slot cards currently visible
                cards = driver.execute_script(TIMETABLE_CARDS_JS)
                if cards:
                    timetable[day_idx] = cards
            except Exception as exc:
                print(f"    [Warning] Could not extract {day_name.title()} timetable: {exc}")

        total_slots = sum(len(v) for v in timetable.values())
        if total_slots > 0:
            print(f"  ✓ Successfully mapped {total_slots} weekly timetable slots from Amizone!")
        else:
            print("  [Notice] Live timetable page returned 0 slots; maintaining active cached timetable.")

    except Exception as exc:
        print(f"  [Warning] Timetable extraction encountered an error: {exc}")

    return timetable


def fetch_via_selenium(
    username: str = "",
    password: str = "",
    headless: bool = False,
    manual_login: bool = False,
    timeout_seconds: int = 180,
) -> tuple[list[dict], dict[int, list[dict]]]:
    """
    Launch Chrome via Selenium, authenticate (or assist with manual browser login),
    scrape attendance from /Home, then scrape timetable from /TimeTable.
    """
    options = Options()
    if headless:
        options.add_argument("--headless=new")

    # Anti-bot, persistent profile, and clean session options
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--remote-allow-origins=*")
    options.add_argument("--window-size=1366,868")

    profile_dir = Path.home() / ".amizone_chrome_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    options.add_argument(f"--user-data-dir={profile_dir}")

    print("\n[1/3] Launching Chrome browser...")
    driver = None
    try:
        driver = webdriver.Chrome(options=options)
        try:
            driver.execute_cdp_cmd(
                "Page.addScriptToEvaluateOnNewDocument",
                {
                    "source": """
                        Object.defineProperty(navigator, 'webdriver', {
                            get: () => undefined
                        });
                    """
                }
            )
        except Exception:
            pass
    except Exception as exc:
        raise RuntimeError(
            f"Failed to start Chrome WebDriver: {exc}\n"
            "Please ensure Google Chrome is installed on this computer."
        )

    try:
        print("[2/3] Opening Amizone portal (https://s.amizone.net/)...")
        driver.get(AMIZONE_LOGIN)
        time.sleep(2)

        # Check if already authenticated
        if "s.amizone.net/Home" in driver.current_url.lower():
            print("  ✓ Already authenticated.")
        else:
            if manual_login or not (username and password):
                print("\n" + "=" * 65)
                print("👉 MANUAL AMIZONE LOGIN MODE")
                print("A Google Chrome window has opened on your screen.")
                print("Please log in to Amizone in that browser window.")
                print("The system is waiting and will automatically capture your")
                print("live attendance as soon as your dashboard loads.")
                print(f"(Waiting up to {timeout_seconds} seconds...)")
                print("=" * 65 + "\n")
            else:
                print(f"[3/3] Authenticating as '{username}'...")
                wait = WebDriverWait(driver, 15)

                try:
                    # Locate input fields
                    user_input = wait.until(
                        EC.presence_of_element_located((By.NAME, "_UserName"))
                    )
                    pass_input = driver.find_element(By.NAME, "_Password")

                    # Fill username and password
                    user_input.clear()
                    user_input.send_keys(username)
                    pass_input.clear()
                    pass_input.send_keys(password)

                    # Trigger user activity simulation
                    driver.execute_script(
                        """
                        window.userActive = true;
                        const event = new MouseEvent('mousemove', { bubbles: true, cancelable: true });
                        document.dispatchEvent(event);
                        """
                    )

                    # Click login button
                    try:
                        login_btn = driver.find_element(By.CSS_SELECTOR, "button.login100-form-btn")
                        login_btn.click()
                    except Exception:
                        driver.execute_script("document.getElementById('loginform').submit();")
                except Exception as e:
                    print(f"  [Notice] Auto-fill failed ({e}); please fill credentials directly in Chrome.")

                print("  Waiting for Amizone dashboard to load...")
                print("  (If Cloudflare verification appears on screen, please complete it if prompted)")

            # Wait for redirect to /Home or tasks element
            start_wait = time.time()
            logged_in = False

            while time.time() - start_wait < timeout_seconds:
                try:
                    if len(driver.window_handles) == 0:
                        raise RuntimeError("Chrome browser window was closed before login completed.")
                except Exception as e:
                    if "closed" in str(e).lower() or "no such window" in str(e).lower():
                        raise RuntimeError("Chrome browser window was closed before login completed.")

                try:
                    curr_url = driver.current_url.lower()
                    if "/home" in curr_url or driver.find_elements(By.CSS_SELECTOR, "#tasks li, ul.item-list li"):
                        logged_in = True
                        break

                    body_text = driver.find_element(By.TAG_NAME, "body").text
                    if "Invalid User Name or Password" in body_text:
                        print("  [Alert] 'Invalid User Name or Password' on screen. Please correct it in Chrome.")
                except Exception:
                    pass

                time.sleep(1)

            if not logged_in:
                raise TimeoutError(
                    "Timed out waiting for Amizone dashboard. "
                    "Please check your internet connection or login credentials."
                )

        # Detect logged-in username if not provided
        if not username:
            try:
                user_el = driver.find_elements(By.CSS_SELECTOR, "span.user-info, .user-name")
                if user_el and user_el[0].text.strip():
                    username = user_el[0].text.strip().replace("\n", " ")
            except Exception:
                pass
            if not username:
                username = "LiveStudent"

        # Step 1: Attendance Extraction from /Home
        print("  ✓ Dashboard loaded. Extracting attendance details...")
        wait_home = WebDriverWait(driver, 15)
        wait_home.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#tasks li, ul.item-list li")))
        time.sleep(1.5)

        records = driver.execute_script(ATTENDANCE_EXTRACTION_JS)

        if not records or len(records) == 0:
            raise RuntimeError("Dashboard opened, but no attendance records were found in '#tasks'.")

        # Step 2: Timetable Extraction from /TimeTable
        timetable = scrape_timetable_from_driver(driver)

        # Save caches
        save_cached_attendance(records, username=username)
        if any(len(slots) > 0 for slots in timetable.values()):
            save_cached_timetable(timetable, username=username)

        return records, timetable

    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# MAIN FETCHER INTERFACES
# ---------------------------------------------------------------------------

def fetch_amizone_data(
    force_relogin: bool = False,
    manual_login: bool = False,
) -> tuple[list[dict], dict[int, list[dict]]]:
    """
    Main entry point to fetch live attendance records AND timetable from Amizone.
    Supports CDP, automatic Selenium login, or manual in-browser login.
    """
    if manual_login:
        native_res = fetch_via_native_chrome()
        if native_res:
            return native_res
        return fetch_via_selenium(headless=False, manual_login=True)

    # 1. Try fast CDP first
    if not force_relogin:
        print("Checking for existing active Amizone browser session...")
        cdp_res = try_cdp_scrape()
        if cdp_res:
            records, tt = cdp_res
            print(f"  ✓ Connected to active Chrome session! Scraped {len(records)} subjects instantly.")
            save_cached_attendance(records, username="ActiveSession")
            return records, tt

    # 2. Get credentials
    username, password = "", ""
    saved_creds = load_saved_credentials() if not force_relogin else None

    if saved_creds:
        u, p = saved_creds
        print(f"Using saved credentials for user '{u}'.")
        username, password = u, p
    else:
        print("\n" + "=" * 55)
        print("AMIZONE LOGIN SELECTION")
        print("=" * 55)
        print("How would you like to log in?")
        print("  [1] Manual login in Chrome (Recommended - Chrome opens, you log in)")
        print("  [2] Automatic login (Enter Enrollment No. & Password here)")
        method = input("Choose [1/2] (Default: 1): ").strip()

        if method == "2":
            username = input("Amizone User Name (Enrollment No.): ").strip()
            while not username:
                username = input("User Name cannot be empty: ").strip()

            password = getpass.getpass("Amizone Password: ").strip()
            while not password:
                password = getpass.getpass("Password cannot be empty: ").strip()

            remember = input("Save credentials locally for automatic login next time? [Y/n]: ").strip().lower()
            if remember in ("", "y", "yes"):
                save_credentials(username, password)
        else:
            native_res = fetch_via_native_chrome()
            if native_res:
                return native_res
            return fetch_via_selenium(headless=False, manual_login=True)

    # 3. Launch Selenium
    try:
        records, timetable = fetch_via_selenium(username=username, password=password, headless=False)
        print(f"  ✓ Successfully updated attendance ({len(records)} subjects) and weekly timetable!")
        return records, timetable
    except Exception as exc:
        print(f"\n[Error] Unable to fetch live data from Amizone: {exc}")

        # Check if cache is available
        cached_att = load_cached_attendance()
        cached_tt = load_cached_timetable()
        if cached_att and "records" in cached_att:
            date_str = cached_att.get("date_str", "earlier")
            print(f"\nCached attendance from {date_str} is available.")
            choice = input("Use cached attendance and timetable? [Y/n]: ").strip().lower()
            if choice in ("", "y", "yes"):
                tt_data = {int(k): v for k, v in cached_tt["days"].items()} if cached_tt and "days" in cached_tt else {}
                return cached_att["records"], tt_data

        raise exc


def fetch_amizone_attendance(force_relogin: bool = False) -> list[dict]:
    """Backward-compatible helper returning attendance records list."""
    records, _ = fetch_amizone_data(force_relogin=force_relogin)
    return records


def fetch_amizone_timetable(force_relogin: bool = False) -> dict[int, list[dict]]:
    """Helper returning timetable dictionary."""
    _, timetable = fetch_amizone_data(force_relogin=force_relogin)
    return timetable


if __name__ == "__main__":
    print("Testing Unified Amizone Scraper...")
    try:
        rec, tt = fetch_amizone_data()
        print(f"Records: {len(rec)}, Timetable days: {len(tt)}")
    except Exception as e:
        print(f"Failed: {e}")
