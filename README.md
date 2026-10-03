# 🎓 Amity University Chhattisgarh - Automatic Attendance Planner

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey.svg)]()

An intelligent, automated attendance calculator and semester strategy planner tailored for **Amity University Chhattisgarh** students (AY 2026-27 Odd Semester).

Instead of manually checking Amizone and typing numbers for every subject, this system **automatically fetches your live attendance and weekly timetable directly from the Amizone portal (`https://s.amizone.net/`)**, maps them to your instructional schedule, and generates an actionable attendance strategy.

---

## 🚀 Quick Start

### On macOS / Linux
Open Terminal and run:
```bash
cd automatic_attendance_system
./run.sh
```

### On Windows
Double-click `run.bat` or open Command Prompt / PowerShell:
```cmd
cd automatic_attendance_system
run.bat
```

> **Note:** The launcher script automatically verifies Python 3, builds an isolated virtual environment (`./venv`), installs dependencies from `requirements.txt`, and launches the planner.

---

## ⚡ Key Features

1. **Dynamic Timetable Mapping as Primary Source of Truth**:
   - Maps your complete weekly schedule from `https://s.amizone.net/TimeTable`.
   - Projects classes through the last instructional day (**02 December 2026**).
   - Accurately accounts for official Chhattisgarh university holidays (Hareli, Dussehra, Diwali, etc.) and declared **in-lieu working Saturdays** (using Friday's schedule).

2. **Automatic Subject & Code Mapping with Auto-Discovery**:
   - Automatically correlates Amizone course codes with subject titles and readable short codes:

   | Amizone Course Code | Subject Name | Planner Code |
   | :--- | :--- | :--- |
   | `CSE4502` | Introduction to Machine Learning | `ML` |
   | `CSE4501` | System Programming and Compiler Design | `SPCD` |
   | `CSE4503` | Cloud Computing | `CC` |
   | `CSE4504` | Cyber Security | `CS` |
   | `IOT4501` | Introduction to IoT and Embedded System | `IOT` |
   | `AECSS40501` | Effective Writing and Professional Ethics | `EWPE` |
   | `CRC2501` | Entrepreneurship | `ENT` |
   | `ALAN40501` | French Advance Grammar and Comprehension | `FRENCH` |
   | `CSE4505` | Cloud Computing Lab | `CC-LAB` |
   | `CSE4506` | Cyber Security Lab | `CS-LAB` |
   | `IOT4502` | Introduction to IoT and Embedded System Lab | `IOT-LAB` |
   | `SEBEH40501` | Interpersonal Communication | `IPC` |

   - **Auto-Discovery**: If any new course or elective is added to your Amizone dashboard, the system auto-registers it dynamically without requiring manual code modifications.

3. **Flexible Authentication & Scraping Options**:
   - **Active Chrome Session (CDP)**: If Chrome is launched with remote debugging enabled (`--remote-debugging-port=9222`), extraction takes **< 1 second** without prompting.
   - **Interactive Browser (Selenium)**: Opens Chrome on your screen so you can log in, solve Cloudflare Turnstile if prompted, and let the scraper extract your data.
   - **Local Caching**: Saves scraped data locally to `attendance_cache.json` and `timetable_cache.json` for offline usage.
   - **Sample / Demo Mode**: If no local cache exists, you can press `d` to test the planner immediately with sample demo data.

---

## 📊 Strategy Report Explained

When the system runs, it displays a detailed report:

```text
======================================================================================================================
                      AMITY UNIVERSITY CHHATTISGARH - ATTENDANCE STRATEGY REPORT
======================================================================================================================
 As-Of Date        : Saturday, 03 October 2026
 Instruction Period: 20 Jul 2026 to 02 Dec 2026
 University Target : 75.0%
======================================================================================================================
Code       Current %   Attended  Conducted   Future     Max %   Safe Miss Status      
----------------------------------------------------------------------------------------------------------------------
ML             44.8%         13         29       23     69.2%           0 [!] CRITICAL
IPC             0.0%          0          2        9     81.8%           0 [*] RECOVERY
CC             53.6%         15         28       25     75.5%           0 [*] RECOVERY
SPCD           56.7%         17         30       22     75.0%           0 [*] RECOVERY
CS             58.1%         18         31       23     75.9%           0 [*] RECOVERY
IOT            69.0%         20         29       25     83.3%           4 [*] RECOVERY
CS-LAB         72.7%         16         22       16     84.2%           3 [*] RECOVERY
ENT            75.0%          6          8        8     87.5%           2 [+] SAFE    
IOT-LAB        75.0%         12         16       18     88.2%           4 [+] SAFE    
CC-LAB         78.3%         18         23       14     86.5%           4 [+] SAFE    
EWPE           88.9%         16         18       17     94.3%           6 [+] SAFE    
FRENCH        100.0%         11         11        8    100.0%           4 [+] SAFE    
======================================================================================================================
```

### Metrics:
- **Current %**: Your real percentage on Amizone right now.
- **Future**: Total scheduled classes remaining between tomorrow and December 2 based on your primary timetable.
- **Max %**: The absolute highest percentage you can achieve if you attend **100% of all future classes**.
- **Safe Miss**: How many future classes you can miss while keeping your final percentage $\ge 75\%$.
- **Status**:
  - `[+] SAFE`: You are currently above 75% and have safe misses remaining.
  - `[*] RECOVERY`: You are below 75%, but can still recover by attending the indicated number of consecutive classes.
  - `[!] CRITICAL`: Even with 100% attendance until the end of semester, it is impossible to reach 75%.

---

## 🛠️ Interactive Menu Options

1. **Show Full Attendance Strategy Report**: Complete analysis and detailed advice for each subject.
2. **Show Dangerous Subjects (Below 75%)**: Quick filter isolating courses requiring urgent recovery.
3. **Project Attendance on a Future Date**: Calculates what your attendance percentage will be on any target date.
4. **What-If: Miss Selected Dates**: Select planned leave dates and simulate the final semester impact.
5. **Show Next 7 Days Timetable**: Schedule of classes for the upcoming 7 days.
6. **Show Complete Weekly Timetable Breakdown**: Full day-by-day weekly timetable breakdown with class hours and rooms.
7. **Refresh Live Attendance & Timetable from Amizone**: Re-fetches the latest updates from the portal.
8. **Manually Edit / Override Subject Attendance**: Adjust any count manually if Amizone has a temporary discrepancy.
9. **View Subject Registry & Raw Amizone Records**: Inspect all registered subjects and raw API records.
C. **Clear Stored Credentials & Caches**: Resets stored logins or cached files.

---

## 🔒 Security & Privacy

- **No Credentials in Repository**: Your credentials (`.credentials.json`), attendance cache (`attendance_cache.json`), and timetable cache (`timetable_cache.json`) are stored strictly on your local machine and are ignored by `.gitignore`.
- **Open Source Transparency**: All scraping and calculation logic is inspectable in [`amizone_fetcher.py`](amizone_fetcher.py) and [`attendance_planner.py`](attendance_planner.py). No third-party servers or telemetry are used.

---

## 📁 Repository Structure

```
automatic_attendance_system/
├── attendance_planner.py          # Main application & calculation engine
├── amizone_fetcher.py             # Amizone portal scraper & session manager
├── attendance_cache.example.json  # Example attendance cache template
├── timetable_cache.example.json   # Example timetable cache template
├── requirements.txt               # Python package dependencies
├── run.sh                         # macOS / Linux 1-click launcher
├── run.bat                        # Windows 1-click launcher
├── .gitignore                     # Git exclusion rules
├── LICENSE                        # MIT License
└── README.md                      # Documentation
```

---

## 📄 License

Distributed under the [MIT License](LICENSE).
