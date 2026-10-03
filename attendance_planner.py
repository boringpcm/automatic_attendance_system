#!/usr/bin/env python3
"""
Amity University Chhattisgarh - Automatic Attendance Calculator & Strategy Planner
AY 2026-27 Odd Semester

Features:
- Dynamically maps timetable from Amizone portal (https://s.amizone.net/TimeTable) on every run.
- Treats the mapped weekly timetable as PRIMARY for all forward projections to the last instructional day.
- Auto-discovers and dynamically registers any new or old subjects (e.g. SEBEH40501 - IPC).
- Automatically patches current live/cached attendance numbers into the timetable projection model.
- Takes into account all Chhattisgarh state holidays, university holidays, and in-lieu working Saturdays.
- Actionable mathematical recommendations: safe misses, recovery classes needed, and critical alerts.
- Offline cache support with timetable_cache.json and attendance_cache.json.
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

# Scraper module
from amizone_fetcher import (
    clear_saved_data,
    fetch_amizone_data,
    load_cached_attendance,
    load_cached_timetable,
    save_cached_timetable,
)

BASE_DIR = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# SEMESTER SETTINGS
# ---------------------------------------------------------------------------

SEMESTER_START = date(2026, 7, 20)
LAST_INSTRUCTIONAL_DAY = date(2026, 12, 2)
TARGET = 0.75  # 75.0% university minimum threshold


# ---------------------------------------------------------------------------
# HOLIDAYS / WORKING SATURDAYS
# ---------------------------------------------------------------------------

HOLIDAYS = {
    date(2026, 8, 12),   # Hareli
    date(2026, 8, 15),   # Independence Day
    date(2026, 8, 26),   # Id-e-Milad
    date(2026, 8, 28),   # Raksha Bandhan additional holiday
    date(2026, 9, 4),    # Janmashtmi additional holiday
    date(2026, 9, 14),   # Ganesh Chaturthi
    date(2026, 10, 2),   # Gandhi Jayanti
    date(2026, 10, 19),  # Durga Puja (Maha Ashtami/Navami)
    date(2026, 10, 20),  # Dussehra
    date(2026, 11, 8),   # Diwali
    date(2026, 11, 9),   # Govardhan Puja
    date(2026, 11, 24),  # Guru Nanak Jayanti
    date(2026, 12, 18),  # Guru Ghasidas Jayanti (after instruction period)
    date(2026, 12, 25),  # Christmas (after instruction period)
}

IN_LIEU_SATURDAYS = {
    date(2026, 8, 22),
    date(2026, 9, 26),
    date(2026, 11, 28),
    date(2026, 12, 5),
    date(2026, 12, 12),
}


# ---------------------------------------------------------------------------
# DYNAMIC SUBJECT REGISTRY & AUTO-DISCOVERY
# ---------------------------------------------------------------------------

class SubjectRegistry:
    """
    Dynamic subject catalog and auto-discovery engine.
    Ensures no subject is ever dropped or missed, even if new subjects are added.
    """

    def __init__(self):
        self._code_to_meta: dict[str, tuple[str, str]] = {}   # CODE -> (SHORT, FULL_NAME)
        self._short_to_code: dict[str, str] = {}              # SHORT -> CODE
        self._short_to_name: dict[str, str] = {}              # SHORT -> FULL_NAME

        # Standard master catalog (seeded with official codes and titles)
        default_catalog = [
            ("CSE4502", "ML", "Introduction to Machine Learning"),
            ("CSE4501", "SPCD", "System Programming and Compiler Design"),
            ("CSE4503", "CC", "Cloud Computing"),
            ("CSE4504", "CS", "Cyber Security"),
            ("IOT4501", "IOT", "Introduction to IoT and Embedded System"),
            ("AECSS40501", "EWPE", "Effective Writing and Professional Ethics"),
            ("CRC2501", "ENT", "Entrepreneurship"),
            ("ALAN40501", "FRENCH", "French Advance Grammer and Comprehension"),
            ("CSE4505", "CC-LAB", "Cloud Computing Lab"),
            ("CSE4506", "CS-LAB", "Cyber Security Lab"),
            ("IOT4502", "IOT-LAB", "Introduction to IoT and Embedded System Lab"),
            ("SEBEH40501", "IPC", "Interpersonal Communication"),
        ]

        for code, short, name in default_catalog:
            self.register(code, short, name)

    def register(self, code: str, short: str, name: str) -> None:
        c = code.strip().upper()
        s = short.strip().upper()
        n = name.strip()
        self._code_to_meta[c] = (s, n)
        self._short_to_code[s] = c
        self._short_to_name[s] = n

    def get_or_register(self, code: str, name: str = "") -> tuple[str, str]:
        c = code.strip().upper()
        n = name.strip()

        if c in self._code_to_meta:
            s, existing_name = self._code_to_meta[c]
            if n and not existing_name:
                self.register(c, s, n)
            return s, existing_name or n or c

        # Match known keywords if name is provided
        if n:
            upper_name = n.upper()
            keyword_mappings = [
                ("MACHINE LEARNING", "ML"),
                ("COMPILER DESIGN", "SPCD"),
                ("SYSTEM PROGRAMMING", "SPCD"),
                ("CLOUD COMPUTING LAB", "CC-LAB"),
                ("CLOUD COMPUTING", "CC"),
                ("CYBER SECURITY LAB", "CS-LAB"),
                ("CYBER SECURITY", "CS"),
                ("EMBEDDED SYSTEM LAB", "IOT-LAB"),
                ("IOT LAB", "IOT-LAB"),
                ("EMBEDDED SYSTEM", "IOT"),
                ("IOT", "IOT"),
                ("EFFECTIVE WRITING", "EWPE"),
                ("PROFESSIONAL ETHICS", "EWPE"),
                ("ENTREPRENEURSHIP", "ENT"),
                ("FRENCH", "FRENCH"),
                ("INTERPERSONAL COMMUNICATION", "IPC"),
            ]
            for kw, default_short in keyword_mappings:
                if kw in upper_name:
                    self.register(c, default_short, n)
                    return default_short, n

        # Dynamically auto-generate a new short code
        s = self._generate_short_code(c, n)
        self.register(c, s, n or c)
        print(f"  [Auto-Discovered Subject] Registered '{c}' -> '{s}' ({n or c})")
        return s, n or c

    def _generate_short_code(self, code: str, name: str) -> str:
        if name:
            words = [w for w in name.upper().split() if w not in ("AND", "OF", "TO", "THE", "IN")]
            is_lab = any("LAB" in w for w in words)
            clean_words = [w for w in words if "LAB" not in w]
            if clean_words:
                acronym = "".join(w[0] for w in clean_words)
                cand = f"{acronym}-LAB" if is_lab else acronym
                if cand not in self._short_to_code:
                    return cand

        # Fallback to course code
        return code

    def get_full_name(self, short: str) -> str:
        s = short.strip().upper()
        return self._short_to_name.get(s, s)

    def get_code(self, short: str) -> str:
        s = short.strip().upper()
        return self._short_to_code.get(s, s)

    def all_subjects(self) -> list[tuple[str, str, str]]:
        """Returns sorted list of (code, short, full_name)."""
        res = []
        for s, n in self._short_to_name.items():
            c = self._short_to_code.get(s, "")
            res.append((c, s, n))
        return sorted(res, key=lambda x: x[1])


# ---------------------------------------------------------------------------
# PRIMARY TIMETABLE STRUCTURE
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ClassSlot:
    code: str
    subject: str
    short: str
    start: str
    end: str
    faculty: str = ""
    room: str = ""


# Default fallback weekly schedule (incorporates confirmed Amizone timetable slots)
DEFAULT_TIMETABLE_CONFIG: dict[int, list[dict]] = {
    0: [  # Monday
        {"code": "CSE4502", "start": "09:10", "end": "10:09", "faculty": "Dr. Goldi Soni", "room": "TF-LT-4"},
        {"code": "CSE4501", "start": "10:10", "end": "11:09", "faculty": "Dr. Kranti Kumar Dewangan", "room": "TF-LT-4"},
        {"code": "CSE4503", "start": "11:10", "end": "12:09", "faculty": "Dr. Vinay Kumar Singh", "room": "TF-LT-4"},
        {"code": "CSE4504", "start": "12:10", "end": "13:10", "faculty": "Dr. Omprakash Dewangan", "room": "TF-LT-5"},
    ],
    1: [  # Tuesday
        {"code": "CSE4504", "start": "09:10", "end": "10:09", "faculty": "", "room": ""},
        {"code": "CSE4501", "start": "10:10", "end": "11:09", "faculty": "", "room": ""},
        {"code": "CSE4502", "start": "11:10", "end": "12:09", "faculty": "", "room": ""},
        {"code": "IOT4501", "start": "12:10", "end": "13:13", "faculty": "", "room": ""},
        {"code": "CSE4505", "start": "13:50", "end": "14:49", "faculty": "", "room": ""},
        {"code": "CSE4505", "start": "14:50", "end": "15:49", "faculty": "", "room": ""},
    ],
    2: [  # Wednesday
        {"code": "IOT4501", "start": "09:10", "end": "10:09", "faculty": "", "room": ""},
        {"code": "CSE4504", "start": "10:10", "end": "11:09", "faculty": "", "room": ""},
        {"code": "CSE4503", "start": "11:10", "end": "12:09", "faculty": "", "room": ""},
        {"code": "SEBEH40501", "start": "12:10", "end": "13:10", "faculty": "", "room": ""},
        {"code": "CSE4502", "start": "13:50", "end": "14:49", "faculty": "", "room": ""},
        {"code": "AECSS40501", "start": "14:50", "end": "15:49", "faculty": "", "room": ""},
    ],
    3: [  # Thursday
        {"code": "CRC2501", "start": "09:10", "end": "10:09", "faculty": "", "room": ""},
        {"code": "CSE4506", "start": "11:10", "end": "12:09", "faculty": "", "room": ""},
        {"code": "CSE4506", "start": "12:10", "end": "13:13", "faculty": "", "room": ""},
        {"code": "CSE4501", "start": "13:50", "end": "14:49", "faculty": "", "room": ""},
        {"code": "AECSS40501", "start": "14:50", "end": "15:49", "faculty": "", "room": ""},
        {"code": "ALAN40501", "start": "15:50", "end": "16:50", "faculty": "", "room": ""},
    ],
    4: [  # Friday
        {"code": "IOT4501", "start": "10:10", "end": "11:09", "faculty": "", "room": ""},
        {"code": "CSE4503", "start": "11:10", "end": "12:09", "faculty": "", "room": ""},
        {"code": "IOT4502", "start": "13:50", "end": "14:49", "faculty": "", "room": ""},
        {"code": "IOT4502", "start": "14:50", "end": "15:49", "faculty": "", "room": ""},
    ],
    5: [],  # Saturday (empty unless special class; in-lieu Saturdays use Friday schedule)
    6: [],  # Sunday
}


def load_primary_timetable(registry: SubjectRegistry) -> dict[int, list[ClassSlot]]:
    """
    Load the mapped timetable as the PRIMARY source of schedule truth.
    Pulls from timetable_cache.json if present; otherwise defaults and persists.
    """
    cached = load_cached_timetable()
    raw_days: dict[int, list[dict]] = {}

    if cached and "days" in cached:
        for k, slots in cached["days"].items():
            raw_days[int(k)] = slots
    else:
        raw_days = DEFAULT_TIMETABLE_CONFIG
        save_cached_timetable(raw_days, username="DefaultConfig")

    timetable: dict[int, list[ClassSlot]] = {i: [] for i in range(7)}

    for day_idx, raw_slots in raw_days.items():
        slot_list = []
        for s in raw_slots:
            code = s.get("code", "").strip().upper()
            short, full_name = registry.get_or_register(code, s.get("name", ""))
            slot = ClassSlot(
                code=code,
                subject=full_name,
                short=short,
                start=s.get("start", "00:00"),
                end=s.get("end", "00:00"),
                faculty=s.get("faculty", ""),
                room=s.get("room", ""),
            )
            slot_list.append(slot)
        timetable[day_idx] = sorted(slot_list, key=lambda x: x.start)

    return timetable


def print_timetable_summary(timetable: dict[int, list[ClassSlot]]) -> None:
    """Print an executive overview of the mapped primary timetable."""
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    print("=" * 95)
    print("                    PRIMARY MAPPED TIMETABLE (ODD SEMESTER)")
    print("=" * 95)
    total_slots = 0
    for i in range(5):
        slots = timetable.get(i, [])
        total_slots += len(slots)
        if slots:
            slots_str = ", ".join(f"{s.start}-{s.end} {s.short}" for s in slots)
            print(f"  • {day_names[i]:<10}: {len(slots)} class(es) | {slots_str}")
        else:
            print(f"  • {day_names[i]:<10}: Free / No classes")

    saturdays_str = ", ".join(d.strftime("%d %b") for d in sorted(IN_LIEU_SATURDAYS) if d <= LAST_INSTRUCTIONAL_DAY)
    print(f"  • In-Lieu Working Saturdays (Follows Friday Schedule): {saturdays_str}")
    print(f"  • Weekly Standard Load: {total_slots} teaching periods scheduled")
    print("=" * 95 + "\n")


# ---------------------------------------------------------------------------
# CALENDAR & INSTRUCTION DAY LOGIC
# ---------------------------------------------------------------------------

def is_instruction_day(day: date) -> bool:
    """Return True if teaching is scheduled on this calendar date."""
    if day < SEMESTER_START or day > LAST_INSTRUCTIONAL_DAY:
        return False

    if day.weekday() <= 4:
        return day not in HOLIDAYS

    if day.weekday() == 5:
        return day in IN_LIEU_SATURDAYS and day <= LAST_INSTRUCTIONAL_DAY

    return False


def dates_between(start: date, end: date) -> list[date]:
    """Return list of instruction dates within the range [start, end]."""
    current = start
    result = []
    while current <= end:
        if is_instruction_day(current):
            result.append(current)
        current += timedelta(days=1)
    return result


def slots_for_date(day: date, timetable: dict[int, list[ClassSlot]]) -> list[ClassSlot]:
    """Get the active class slots for a date (In-lieu Saturday uses Friday timetable)."""
    if not is_instruction_day(day):
        return []

    if day.weekday() == 5:
        return timetable.get(4, [])

    return timetable.get(day.weekday(), [])


def count_future_classes(
    short: str,
    start: date,
    timetable: dict[int, list[ClassSlot]],
    exclude_dates: set[date] | None = None,
) -> int:
    """Count future scheduled classes for a subject through the last instructional day."""
    count = 0
    excludes = exclude_dates or set()
    for day in dates_between(start, LAST_INSTRUCTIONAL_DAY):
        if day in excludes:
            continue
        for slot in slots_for_date(day, timetable):
            if slot.short == short:
                count += 1
    return count


# ---------------------------------------------------------------------------
# ATTENDANCE MATHEMATICS & METRICS
# ---------------------------------------------------------------------------

def format_pct(value: float) -> str:
    return f"{value:.1f}%"


def attendance_pct(attended: int, conducted: int) -> float:
    return (attended / conducted * 100) if conducted > 0 else 100.0


def recovery_classes_needed(conducted: int, attended: int) -> int:
    """Calculate minimum consecutive future classes that must be attended to reach 75%."""
    if conducted == 0 or (attended / conducted) >= TARGET:
        return 0
    return math.ceil((TARGET * conducted - attended) / (1 - TARGET))


# ---------------------------------------------------------------------------
# ATTENDANCE PARSING & INTEGRATION
# ---------------------------------------------------------------------------

def process_scraped_attendance(
    records: list[dict],
    registry: SubjectRegistry,
) -> dict[str, dict[str, int]]:
    """
    Parses scraped records and updates the SubjectRegistry dynamically.
    Returns: {short_code: {'attended': x, 'conducted': y, 'code': code, 'name': name}}
    """
    attendance: dict[str, dict[str, int]] = {}

    for r in records:
        code = r.get("code", "").strip().upper()
        name = r.get("name", "").strip()
        short, full_name = registry.get_or_register(code, name)

        count_str = r.get("count", "")
        att, cond = 0, 0
        if "/" in count_str:
            try:
                parts = count_str.split("/")
                att = int(parts[0].strip())
                cond = int(parts[1].strip())
            except ValueError:
                pass

        attendance[short] = {
            "attended": att,
            "conducted": cond,
            "code": code,
            "name": full_name,
        }

    return attendance


# ---------------------------------------------------------------------------
# STRATEGY REPORT BUILDER
# ---------------------------------------------------------------------------

def build_report(
    attendance: dict[str, dict[str, int]],
    as_of: date,
    timetable: dict[int, list[ClassSlot]],
    registry: SubjectRegistry,
) -> list[dict]:
    """
    Build comprehensive attendance report keeping mapped timetable as primary.
    """
    tomorrow = as_of + timedelta(days=1)
    rows = []

    for code, short, full_name in registry.all_subjects():
        att_data = attendance.get(short, {"attended": 0, "conducted": 0, "code": code, "name": full_name})
        attended = att_data["attended"]
        conducted = att_data["conducted"]

        current = attendance_pct(attended, conducted)
        future = count_future_classes(short, tomorrow, timetable)
        total_semester = conducted + future
        required = math.ceil(TARGET * total_semester)
        max_attended = attended + future
        max_pct = attendance_pct(max_attended, total_semester)

        recovery = recovery_classes_needed(conducted, attended)
        safe_misses = max(0, max_attended - required)

        if total_semester == 0:
            status = "SAFE"
            advice = "No classes scheduled or recorded for this subject."
        elif max_attended < required:
            status = "CRITICAL"
            shortage = required - max_attended
            advice = (
                f"Cannot reach 75% even with 100% future attendance. "
                f"Short by {shortage} class(es). Seek faculty/duty leave assistance."
            )
        elif current < 75.0:
            status = "RECOVERY"
            advice = f"Attend next {recovery} class(es) continuously to reach {format_pct(75.0)}."
        else:
            status = "SAFE"
            advice = f"You can miss up to {safe_misses} future class(es) and still finish at or above 75%."

        rows.append(
            {
                "code": code,
                "short": short,
                "name": full_name,
                "attended": attended,
                "conducted": conducted,
                "current": current,
                "future": future,
                "required": required,
                "total_semester": total_semester,
                "max_pct": max_pct,
                "recovery": recovery,
                "safe_misses": safe_misses,
                "status": status,
                "advice": advice,
            }
        )

    return rows


def print_report(rows: list[dict], as_of: date) -> None:
    print("\n" + "=" * 118)
    print("                      AMITY UNIVERSITY CHHATTISGARH - ATTENDANCE STRATEGY REPORT")
    print("=" * 118)
    print(f" As-Of Date        : {as_of.strftime('%A, %d %B %Y')}")
    print(f" Instruction Period: {SEMESTER_START.strftime('%d %b %Y')} to {LAST_INSTRUCTIONAL_DAY.strftime('%d %b %Y')}")
    print(f" University Target : {format_pct(TARGET * 100)}")
    print("=" * 118)

    header = (
        f"{'Code':<9} {'Current %':>10} {'Attended':>10} {'Conducted':>10} "
        f"{'Future':>8} {'Max %':>9} {'Safe Miss':>11} {'Status':<12}"
    )
    print(header)
    print("-" * 118)

    rank = {"CRITICAL": 0, "RECOVERY": 1, "SAFE": 2}
    ordered = sorted(rows, key=lambda r: (rank[r["status"]], r["current"]))

    for row in ordered:
        if row["status"] == "CRITICAL":
            tag_str = "[!] CRITICAL"
        elif row["status"] == "RECOVERY":
            tag_str = "[*] RECOVERY"
        else:
            tag_str = "[+] SAFE"

        print(
            f"{row['short']:<9} "
            f"{format_pct(row['current']):>10} "
            f"{row['attended']:>10} "
            f"{row['conducted']:>10} "
            f"{row['future']:>8} "
            f"{format_pct(row['max_pct']):>9} "
            f"{row['safe_misses']:>11} "
            f"{tag_str:<12}"
        )

    print("-" * 118)
    print("STRATEGY & ADVICE BREAKDOWN")
    for row in ordered:
        tag_marker = "(!)" if row["status"] != "SAFE" else "(✓)"
        print(f"\n{tag_marker} {row['short']} — {row['name']} ({row['code']})")
        print(f"    Status: {row['status']} | Current: {format_pct(row['current'])} ({row['attended']}/{row['conducted']})")
        print(f"    Action: {row['advice']}")
        print(
            f"    Target Requirement: At least {row['required']} attended "
            f"classes out of {row['total_semester']} total semester classes."
        )

    print("=" * 118 + "\n")


def print_dangerous_subjects(rows: list[dict]) -> None:
    dangerous = [r for r in rows if r["status"] in ("CRITICAL", "RECOVERY")]

    print("\n" + "=" * 90)
    print("                        DANGEROUS SUBJECTS (BELOW 75%)")
    print("=" * 90)

    if not dangerous:
        print("  ✓ Excellent! No subject is currently below 75%. All courses are SAFE.")
        print("=" * 90)
        return

    for row in dangerous:
        tag = "[!] CRITICAL" if row["status"] == "CRITICAL" else "[*] RECOVERY"
        print(f"\n{tag} {row['short']:<8} ({row['name']})")
        print(f"    Current Attendance : {format_pct(row['current'])} ({row['attended']}/{row['conducted']})")
        print(f"    Maximum Possible   : {format_pct(row['max_pct'])} with {row['future']} future classes remaining")
        print(f"    Immediate Action   : {row['advice']}")

    print("=" * 90)


# ---------------------------------------------------------------------------
# DATE & SKIP PROJECTIONS
# ---------------------------------------------------------------------------

def parse_date_input(text: str) -> date:
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            pass
    raise ValueError("Please use DD-MM-YYYY, DD/MM/YYYY, or YYYY-MM-DD.")


def project_to_date(
    attendance: dict[str, dict[str, int]],
    as_of: date,
    target_date: date,
    timetable: dict[int, list[ClassSlot]],
    registry: SubjectRegistry,
    skipped_dates: set[date] | None = None,
) -> list[dict]:
    skipped_dates = skipped_dates or set()

    if target_date < as_of:
        raise ValueError("Projection date must be on or after the as-of date.")

    rows = []
    for code, short, full_name in registry.all_subjects():
        att_data = attendance.get(short, {"attended": 0, "conducted": 0})
        attended = att_data["attended"]
        conducted = att_data["conducted"]

        additional_classes = 0
        additional_attended = 0

        next_day = as_of + timedelta(days=1)
        if target_date >= next_day:
            for day in dates_between(next_day, target_date):
                classes = len([s for s in slots_for_date(day, timetable) if s.short == short])
                additional_classes += classes
                if day not in skipped_dates:
                    additional_attended += classes

        final_conducted = conducted + additional_classes
        final_attended = attended + additional_attended

        rows.append(
            {
                "short": short,
                "name": full_name,
                "attended": final_attended,
                "conducted": final_conducted,
                "pct": attendance_pct(final_attended, final_conducted),
                "added": additional_classes,
                "missed": additional_classes - additional_attended,
            }
        )

    return rows


def print_date_projection(
    attendance: dict[str, dict[str, int]],
    as_of: date,
    target_date: date,
    timetable: dict[int, list[ClassSlot]],
    registry: SubjectRegistry,
) -> None:
    if target_date > LAST_INSTRUCTIONAL_DAY:
        print(
            f"\nNote: {target_date.strftime('%d %b %Y')} is beyond the "
            f"last instructional day ({LAST_INSTRUCTIONAL_DAY.strftime('%d %b %Y')})."
        )

    rows = project_to_date(attendance, as_of, target_date, timetable, registry)

    print("\n" + "=" * 80)
    print(
        f"PROJECTED ATTENDANCE ON {target_date.strftime('%d %b %Y')}\n"
        "(Assuming 100% attendance from tomorrow until target date)"
    )
    print("=" * 80)
    for row in rows:
        status = "[+] SAFE" if row["pct"] >= 75.0 else "[-] BELOW 75%"
        print(
            f"{row['short']:<9} {format_pct(row['pct']):>7} "
            f"({row['attended']:>2}/{row['conducted']:>2})  |  {status}"
        )
    print("=" * 80)


def ask_date_list(as_of: date, timetable: dict[int, list[ClassSlot]]) -> set[date]:
    print(
        "\nEnter dates you plan to miss, one by one (e.g., 10-10-2026).\n"
        "Press ENTER on an empty line when finished."
    )
    result = set()
    while True:
        raw = input("Date to miss: ").strip()
        if not raw:
            break
        try:
            day = parse_date_input(raw)
            if day <= as_of:
                print("  Date must be in the future (after as-of date).")
                continue
            if day > LAST_INSTRUCTIONAL_DAY:
                print("  Date is after the last instructional day.")
                continue

            slots = slots_for_date(day, timetable)
            if not slots:
                print(f"  No classes scheduled on {day.strftime('%A, %d %b %Y')} (Holiday/Weekend).")
                continue

            result.add(day)
            print(f"  Added {day.strftime('%A, %d %b %Y')} — {len(slots)} classes will be skipped.")
        except ValueError as exc:
            print(f"  Invalid date: {exc}")

    return result


def print_skip_projection(
    attendance: dict[str, dict[str, int]],
    as_of: date,
    skipped_dates: set[date],
    timetable: dict[int, list[ClassSlot]],
    registry: SubjectRegistry,
) -> None:
    rows = project_to_date(
        attendance, as_of, LAST_INSTRUCTIONAL_DAY, timetable, registry, skipped_dates=skipped_dates
    )

    print("\n" + "=" * 85)
    print("                  WHAT-IF SCENARIO: FINAL SEMESTER OUTCOME")
    print(f"Missing {len(skipped_dates)} date(s) and attending all other remaining classes:")
    print("=" * 85)

    for row in rows:
        status = "[+] SAFE" if row["pct"] >= 75.0 else "[!] BELOW 75%"
        print(
            f"{row['short']:<9} {format_pct(row['pct']):>7} "
            f"({row['attended']:>2}/{row['conducted']:>2}) "
            f"| Missed: {row['missed']:>2} classes | {status}"
        )
    print("=" * 85)


def print_next_seven_days(as_of: date, timetable: dict[int, list[ClassSlot]]) -> None:
    start = as_of + timedelta(days=1)
    end = start + timedelta(days=6)

    print("\n" + "=" * 85)
    print(f"TIMETABLE SCHEDULE FOR NEXT 7 DAYS: {start.strftime('%d %b %Y')} to {end.strftime('%d %b %Y')}")
    print("=" * 85)

    current = start
    found = False
    while current <= end:
        slots = slots_for_date(current, timetable)
        if slots:
            found = True
            is_lieu = " (In-Lieu Saturday)" if current.weekday() == 5 else ""
            print(f"\n{current.strftime('%A, %d %b %Y')}{is_lieu}:")
            for slot in slots:
                fac = f" ({slot.faculty})" if slot.faculty else ""
                rm = f" [{slot.room}]" if slot.room else ""
                print(f"  • {slot.start} - {slot.end} : {slot.short:<8} {slot.subject}{fac}{rm}")
        current += timedelta(days=1)

    if not found:
        print("  No classes scheduled in the next 7 days.")
    print("=" * 85)


def print_full_weekly_timetable(timetable: dict[int, list[ClassSlot]]) -> None:
    """Print complete day-by-day weekly timetable breakdown."""
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    print("\n" + "=" * 90)
    print("                   COMPLETE WEEKLY TIMETABLE SCHEDULE")
    print("=" * 90)
    for day_idx in range(7):
        slots = timetable.get(day_idx, [])
        print(f"\n[{day_names[day_idx].upper()}] ({len(slots)} classes scheduled)")
        if not slots:
            print("  (No regular classes scheduled)")
            continue
        for s in slots:
            fac = f" | Faculty: {s.faculty}" if s.faculty else ""
            rm = f" | Room: {s.room}" if s.room else ""
            print(f"  • {s.start} - {s.end} : {s.short:<8} ({s.code}) - {s.subject}{fac}{rm}")
    print("\n" + "=" * 90)


# ---------------------------------------------------------------------------
# MANUAL EDIT & OVERRIDE
# ---------------------------------------------------------------------------

def manual_override_attendance(
    attendance: dict[str, dict[str, int]],
    registry: SubjectRegistry,
) -> dict[str, dict[str, int]]:
    print("\n" + "=" * 65)
    print("MANUAL ATTENDANCE OVERRIDE")
    print("Format: attended/conducted  (e.g., 18/22)")
    print("Press Enter without changes to keep existing values.")
    print("=" * 65)

    for _, short, name in registry.all_subjects():
        current = attendance.get(short, {"attended": 0, "conducted": 0})
        att = current["attended"]
        cond = current["conducted"]
        pct_str = format_pct(attendance_pct(att, cond))

        raw = input(f"  {short:<9} ({pct_str}, current: {att}/{cond}): ").strip()
        if not raw:
            continue

        if "/" in raw:
            try:
                parts = raw.split("/")
                a = int(parts[0].strip())
                c = int(parts[1].strip())
                if a <= c and c >= 0:
                    attendance[short] = {"attended": a, "conducted": c, "code": registry.get_code(short), "name": name}
                    print(f"    ✓ Updated {short} to {a}/{c}")
                else:
                    print(f"    Invalid ratio: {raw} (attended cannot exceed conducted)")
            except ValueError:
                print(f"    Invalid format: {raw}. Expected: attended/conducted")

    return attendance


# ---------------------------------------------------------------------------
# MAIN APPLICATION LOOP
# ---------------------------------------------------------------------------

def print_menu() -> None:
    print("\n-------------------------------------------------------")
    print("MAIN MENU")
    print("-------------------------------------------------------")
    print("1. Show Full Attendance Strategy Report")
    print("2. Show Dangerous Subjects (Below 75%)")
    print("3. Project Attendance on a Future Date")
    print("4. What-If: Miss Selected Dates")
    print("5. Show Next 7 Days Timetable")
    print("6. Show Complete Weekly Timetable Breakdown")
    print("7. Refresh Live Attendance & Timetable from Amizone")
    print("8. Manually Edit / Override Subject Attendance")
    print("9. View Subject Registry & Raw Amizone Records")
    print("C. Clear Stored Credentials & Caches")
    print("0. Exit")
    print("-------------------------------------------------------")


def main() -> None:
    as_of = date.today()
    registry = SubjectRegistry()

    print("\n" + "=" * 80)
    print("           AMITY UNIVERSITY CHHATTISGARH (ODD SEMESTER)")
    print("             AUTOMATIC ATTENDANCE STRATEGY SYSTEM")
    print("=" * 80)
    print(f"System Date: {as_of.strftime('%A, %d %B %Y')}")
    print(f"Target     : {format_pct(TARGET * 100)}")
    print(f"Semester   : {SEMESTER_START.strftime('%d %b %Y')} → {LAST_INSTRUCTIONAL_DAY.strftime('%d %b %Y')}\n")

    # Step 1: Map primary timetable
    timetable = load_primary_timetable(registry)
    print_timetable_summary(timetable)

    # Step 2: Check for cached attendance / prompt
    cached_att = load_cached_attendance()
    example_file = BASE_DIR / "attendance_cache.example.json"
    raw_records: list[dict] = []

    if cached_att and "records" in cached_att:
        date_str = cached_att.get("date_str", "earlier")
        print(f"Found local cached attendance from {date_str}.")
        choice = input("Press [Enter] to fetch fresh live data from Amizone, or type 'c' to use cache: ").strip().lower()
        if choice in ("c", "cache"):
            raw_records = cached_att["records"]
            print(f"  ✓ Loaded {len(raw_records)} subjects from local cache.")
    elif example_file.exists():
        choice = input("Press [Enter] to fetch fresh live data from Amizone, or type 'd' for demo data: ").strip().lower()
        if choice in ("d", "demo", "example"):
            try:
                with open(example_file, "r", encoding="utf-8") as f:
                    demo_data = json.load(f)
                    raw_records = demo_data.get("records", [])
                    print(f"  ✓ Loaded {len(raw_records)} subjects from demo dataset.")
            except Exception:
                pass

    if not raw_records:
        try:
            raw_records, live_tt = fetch_amizone_data()
            if any(len(slots) > 0 for slots in live_tt.values()):
                timetable = load_primary_timetable(registry)
        except Exception as exc:
            print(f"\n[Notice] Could not fetch live data: {exc}")
            if cached_att and "records" in cached_att:
                print("Falling back to cached attendance...")
                raw_records = cached_att["records"]
            elif example_file.exists():
                print("Falling back to demo attendance data...")
                try:
                    with open(example_file, "r", encoding="utf-8") as f:
                        demo_data = json.load(f)
                        raw_records = demo_data.get("records", [])
                except Exception:
                    raw_records = []
            else:
                raw_records = []

    # Step 3: Patch attendance
    attendance = process_scraped_attendance(raw_records, registry)

    # Step 4: Display main report immediately
    rows = build_report(attendance, as_of, timetable, registry)
    print_report(rows, as_of)

    # Step 5: Interactive menu
    while True:
        print_menu()
        choice = input("Choose an option: ").strip().lower()

        if choice == "1":
            rows = build_report(attendance, as_of, timetable, registry)
            print_report(rows, as_of)

        elif choice == "2":
            rows = build_report(attendance, as_of, timetable, registry)
            print_dangerous_subjects(rows)

        elif choice == "3":
            raw = input("\nEnter projection target date (DD-MM-YYYY): ").strip()
            try:
                target_date = parse_date_input(raw)
                print_date_projection(attendance, as_of, target_date, timetable, registry)
            except ValueError as exc:
                print(f"Invalid date: {exc}")

        elif choice == "4":
            skipped = ask_date_list(as_of, timetable)
            if skipped:
                print_skip_projection(attendance, as_of, skipped, timetable, registry)
            else:
                print("No dates selected.")

        elif choice == "5":
            print_next_seven_days(as_of, timetable)

        elif choice == "6":
            print_full_weekly_timetable(timetable)

        elif choice == "7":
            print("\nRefreshing live attendance and timetable from Amizone...")
            try:
                raw_records, live_tt = fetch_amizone_data(force_relogin=True)
                attendance = process_scraped_attendance(raw_records, registry)
                timetable = load_primary_timetable(registry)
                rows = build_report(attendance, as_of, timetable, registry)
                print_report(rows, as_of)
            except Exception as e:
                print(f"Refresh failed: {e}")

        elif choice == "8":
            attendance = manual_override_attendance(attendance, registry)
            rows = build_report(attendance, as_of, timetable, registry)
            print_report(rows, as_of)

        elif choice == "9":
            print("\n" + "=" * 70)
            print("SUBJECT REGISTRY & RAW AMIZONE ATTENDANCE")
            print("=" * 70)
            for r in raw_records:
                c = r.get("code", "")
                s, n = registry.get_or_register(c, r.get("name", ""))
                cnt = r.get("count", "")
                pct = r.get("percent", "")
                print(f"{c:<12} | {s:<8} | {cnt:<8} ({pct}%) | {n}")
            print("=" * 70)

        elif choice in ("c", "clear"):
            clear_saved_data()

        elif choice in ("0", "exit", "q", "quit"):
            print("\nThank you for using Amity Attendance Planner. Have a great day!")
            break

        else:
            print("Please enter a valid menu option.")


if __name__ == "__main__":
    main()
