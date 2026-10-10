# 🎓 Amity University Chhattisgarh - Automatic Attendance Planner

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey.svg)]()

An intelligent, automated attendance calculator and semester strategy planner tailored for **Amity University Chhattisgarh** students (AY 2026-27 Odd Semester).

Instead of manually checking Amizone and typing numbers for every subject, this system **automatically fetches your live attendance and weekly timetable directly from the Amizone portal (`https://s.amizone.net/`)**, maps them to your instructional schedule, and generates an actionable attendance strategy.

---

## 🚀 Quick Start & New Device Setup

### 📋 Prerequisites on New Device
Before running on a new computer, ensure you have:
1. **Python 3.8+** installed ([Download from python.org](https://www.python.org/downloads/)).
   > ⚠️ **Windows Users:** During Python installation, ensure you check the box **"Add python.exe to PATH"**.
2. **Google Chrome** installed ([Download Chrome](https://www.google.com/chrome/)).
3. **Git** installed ([Download Git](https://git-scm.com/)) or download this repo as a ZIP file.

---

### 📥 1. Clone or Download the Project
Open Terminal (macOS/Linux) or Command Prompt / PowerShell (Windows):
```bash
git clone https://github.com/boringpcm/automatic_attendance_system.git
cd automatic_attendance_system
```

---

### ⚡ 2. One-Click Launch

#### On macOS / Linux
```bash
# Make launcher executable (first time only):
chmod +x run.sh

# Recommended: Open native Chrome for Cloudflare-safe manual login:
./run.sh --manual

# Or launch standard interactive menu:
./run.sh
```

#### On Windows
Double-click `run.bat` in File Explorer, or open Command Prompt / PowerShell:
```cmd
# Recommended: Open native Chrome for Cloudflare-safe manual login:
run.bat --manual

# Or launch standard interactive menu:
run.bat
```

> **Automatic Environment Setup**: The launcher script (`run.sh` / `run.bat`) automatically creates an isolated virtual environment (`./venv`), installs dependencies from `requirements.txt`, and launches the program. You do not need to install packages globally.

---

### 🔑 3. First-Time Login Walkthrough
1. Running with `--manual` opens your genuine **Google Chrome** browser directly to `https://s.amizone.net/`.
2. Type your **Enrollment No.** and **Password**, and click the Cloudflare Turnstile verification checkbox.
   > **Note:** The scraper connects to your native Chrome process via Chrome DevTools Protocol (CDP), meaning no automated chromedriver is detected by Cloudflare. Turnstile will verify smoothly.
3. As soon as your Amizone dashboard loads, the system automatically extracts your live attendance and weekly schedule, saves them locally to `attendance_cache.json` and `timetable_cache.json`, and prints your full strategy report.
4. **Subsequent Runs**: After the first run, you can run `./run.sh` (or `run.bat`) offline and press `c` to load cached data instantly without needing to log in again. Use menu option `7` or `--manual` whenever you want to refresh with fresh live data.

---

### 🛠️ Alternative: Manual Setup (Without Launcher Scripts)
If you prefer setting up Python manually without `run.sh` / `run.bat`:
```bash
# 1. Create virtual environment
python3 -m venv venv

# 2. Activate virtual environment
# On macOS / Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Launch attendance planner
python attendance_planner.py --manual
```

#### Supported CLI Flags:
- `--manual` / `-m`: Launches native Google Chrome for manual login (Cloudflare-safe).
- `--live` / `-l`: Prompts for live data fetch options.
- `--demo` / `-d`: Uses sample demo data for quick testing without Amizone login.
- `--once`: Generates the strategy report and exits immediately without staying in the interactive menu loop.

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
==========================================================================================================================
                      AMITY UNIVERSITY CHHATTISGARH - ATTENDANCE STRATEGY REPORT
==========================================================================================================================
 As-Of Date        : Saturday, 10 October 2026
 Instruction Period: 20 Jul 2026 to 02 Dec 2026
 University Target : 75.0%
==========================================================================================================================
Code       Current %   Attended  Conducted   Future     Max %   Safe Miss       Addl Req Status        
--------------------------------------------------------------------------------------------------------------------------
IPC             0.0%          0          4        8     66.7%           0     +1 (4 ext) [!] CRITICAL  
CS-LAB         16.7%          4         24       14     47.4%           0   +11 (42 ext) [!] CRITICAL  
CS             29.4%         10         34       20     55.6%           0   +11 (42 ext) [!] CRITICAL  
SPCD           31.2%         10         32       19     56.9%           0   +10 (37 ext) [!] CRITICAL  
ML             40.6%         13         32       20     63.5%           0    +6 (24 ext) [!] CRITICAL  
CC-LAB         44.0%         11         25       12     62.2%           0    +5 (19 ext) [!] CRITICAL  
CC             51.6%         16         31       22     71.7%           0     +2 (7 ext) [!] CRITICAL  
ANN            71.9%         23         32        0     71.9%           0     +1 (4 ext) [!] CRITICAL  
ENT            63.6%          7         11        7     77.8%           0          5 rec [*] RECOVERY  
EWPE           70.0%         14         20       15     82.9%           2          4 rec [*] RECOVERY  
ANN-LAB        75.0%         12         16        0     75.0%           0              0 [+] SAFE      
FRENCH        100.0%         12         12        7    100.0%           4              0 [+] SAFE      
IOT           100.0%          0          0       22    100.0%           5              0 [+] SAFE      
IOT-LAB       100.0%          0          0       16    100.0%           4              0 [+] SAFE      
==========================================================================================================================
```

### Metrics:
- **Current %**: Your real percentage on Amizone right now.
- **Future**: Total scheduled classes remaining between tomorrow and December 2 based on your primary timetable.
- **Max %**: The absolute highest percentage you can achieve if you attend **100% of all future classes**.
- **Safe Miss**: How many future classes you can miss while keeping your final percentage $\ge 75\%$.
- **Addl Req (Additional Classes Required)**:
  - For **CRITICAL** subjects: Shows classes short beyond standard timetable, formatted as `+X (Y ext)`, where `+X` is the duty/medical leave credits needed, and `Y ext` is the number of extra remedial classes faculty must conduct (and you attend) to reach $\ge 75\%$.
  - For **RECOVERY** subjects: Shows `N rec`, the number of consecutive scheduled classes you must attend to cross the 75% threshold.
  - For **SAFE** subjects: Shows `0`.
- **Status**:
  - `[+] SAFE`: You are currently above 75% and have safe misses remaining.
  - `[*] RECOVERY`: You are below 75%, but can still recover by attending the indicated number of consecutive classes.
  - `[!] CRITICAL`: Even with 100% attendance until the end of semester, it is impossible to reach 75% without institutional duty leave or extra classes.

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
