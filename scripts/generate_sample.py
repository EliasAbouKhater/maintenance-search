#!/usr/bin/env python3
"""
Generate a synthetic maintenance-log CSV to data/sample.csv (TSV, UTF-8).

Hybrid pipeline:
  - ~3000 templated rows generated locally (fast, deterministic, seed-controlled)
  - ~2000 rows produced via the DeepSeek chat API (natural technician-style narrative)

Usage:
  DEEPSEEK_API_KEY=sk-... python scripts/generate_sample.py \\
      [--seed 42] [--templated 3000] [--llm 2000] [--skip-llm] [--out data/sample.csv]
"""

import argparse
import csv
import json
import math
import os
import random
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests

# ── Value pools ──────────────────────────────────────────────────────────────

CASINO_NAMES = [
    "Casino Alpha", "Casino Beta", "Casino Gamma", "Casino Delta",
    "Casino Epsilon", "Casino Zeta", "Venue Eta", "Venue Theta",
    "Venue Iota", "Venue Kappa", "Regional Office A", "Regional Office B",
]

DEPARTMENTS = ["Gaming Floor", "IT", "HVAC", "Electrical", "General", "Slots", "Tables", ""]
DEPT_WEIGHTS = [70, 5, 1, 2, 12, 1, 1, 8]

SUB_DEPT_MAP = {
    "Gaming Floor": ["Card Shuffler", "Slot Machines", "Table Games", "Roulette", "Jackpot System"],
    "IT":           ["Network Infrastructure", "Surveillance", "IT Systems", "Servers/Computers", "AV/Power"],
}

MAINTENANCE_TYPES = ["Corrective", "Preventive", "Installation/Upgrade", "Maintenance", "Problem Solving"]
STATUSES = ["OK", "Working", "Escalated", "Awaiting parts - Working", "In Progress", "Completed"]
TECHNICIAN_HANDLES = ["Alex", "Jordan", "Taylor", "Casey", "Morgan", "Riley", "Quinn", "Avery"]

# ── Equipment generators ─────────────────────────────────────────────────────

def _slot(): return f"Slot #{random.randint(1, 500)}"
def _camera(): return f"Camera CT{random.randint(1, 50)}"
def _table(): return f"Table #{random.randint(1, 200)}"
def _roulette(): return f"Roulette {random.randint(1, 20)}"
def _shuffler(): return f"Shuffler #{random.randint(1, 100)}"
def _generic(name, hi=100): return f"{name} {random.randint(1, hi)}"

# ── Templates ────────────────────────────────────────────────────────────────
# (problem, solution, equipment_fn) per department.

TEMPLATES = {
    "Gaming Floor": [
        ("card reader not working on {equip}",       "replaced card reader",                        _slot),
        ("bill acceptor jammed",                     "cleared jam and cleaned rollers",             _slot),
        ("machine won't boot after power outage",    "performed RAM clear and reboot",              _slot),
        ("display screen flickering",                "replaced display cable",                      _slot),
        ("touch screen unresponsive",                "recalibrated touch sensor",                   _slot),
        ("printer not dispensing tickets",           "replaced paper roll and cleaned path",        _slot),
        ("coin hopper empty",                        "refilled coin hopper",                        _slot),
        ("machine emitting loud noise",              "lubricated reel motors",                      _slot),
        ("door sensor fault",                        "adjusted door alignment and reset sensor",    _slot),
        ("invalid validator error",                  "replaced validator module",                   _slot),
        ("roulette wheel not spinning evenly",       "rebalanced wheel and greased bearing",        _roulette),
        ("card shuffler jamming",                    "cleaned shuffler rollers and deck",           _shuffler),
        ("table felt torn",                          "replaced felt on table",                      _table),
        ("chip counter miscalibrated",               "recalibrated chip counter",                   _table),
        ("dealer button stuck",                      "freed button mechanism",                      _table),
        ("jackpot display not updating",             "reset link controller",                       lambda: _generic("Jackpot Display")),
        ("progressive link error",                   "re-synced progressive controller",            lambda: _generic("Progressive Controller")),
        ("card shuffler noisy",                      "lubricated gears",                            _shuffler),
        ("shuffler not detecting deck",              "cleaned optical sensor",                      _shuffler),
        ("roulette ball detector error",             "cleaned ball track sensors",                  _roulette),
        ("slot machine tilting",                     "checked leveling feet and reseated",          _slot),
        ("slot ticket reader offline",               "power cycled and reconnected network",        _slot),
        ("money wheel motor failure",                "replaced motor brushes",                      lambda: _generic("Money Wheel")),
    ],
    "IT": [
        ("network switch down on floor",             "replaced faulty switch",                      lambda: f"Switch {random.randint(1,50)}"),
        ("surveillance camera offline",              "reconnected BNC and power",                   _camera),
        ("server not responding",                    "rebooted server and verified RAID",           lambda: f"Server {random.randint(1,20)}"),
        ("WiFi AP no connectivity",                  "replaced AP and re-provisioned",              lambda: f"AP-{random.randint(100,199)}"),
        ("POS terminal frozen",                      "hard restart and database check",             lambda: f"POS-{random.randint(1,100)}"),
        ("ethernet cable damage",                    "re-terminated cable",                         lambda: f"Patch Panel Port {random.randint(1,48)}"),
        ("UPS battery low",                          "replaced UPS battery pack",                   lambda: f"UPS {random.randint(1,10)}"),
        ("data projector lamp failure",              "replaced lamp module",                        lambda: f"Projector {random.randint(1,5)}"),
        ("audio system buzzing",                     "ground lifted and cables shielded",           lambda: f"Audio Rack {random.randint(1,3)}"),
        ("surveillance DVR storage full",            "expanded storage array",                      lambda: f"DVR {random.randint(1,8)}"),
        ("firewall rule misconfiguration",           "updated access control policies",             lambda: "Firewall"),
        ("phone lines static",                       "traced and replaced patch cord",              lambda: f"Phone Port {random.randint(1,200)}"),
        ("biometric reader offline",                 "restarted controller service",                lambda: f"Biometric Reader {random.randint(1,20)}"),
        ("ID card printer jam",                      "cleared paper path",                          lambda: "ID Card Printer"),
        ("digital signage player crashed",           "re-imaged player",                            lambda: f"Signage Player {random.randint(1,15)}"),
    ],
    "General": [
        ("ceiling tile water stain",                 "identified roof leak and replaced tile",      lambda: "Ceiling Lobby"),
        ("door closer broken",                       "replaced door closer",                        lambda: f"{random.choice(['Main Entrance', 'Restroom', 'Office'])} Door"),
        ("vending machine not cooling",              "recharged refrigerant",                       lambda: f"Vending Machine {random.randint(1,20)}"),
        ("carpet loose in hallway",                  "re-stretched and tacked carpet",              lambda: "Hallway A3"),
        ("broken chair in lounge",                   "replaced chair",                              lambda: "Lounge Area"),
        ("fire extinguisher missing",                "replaced extinguisher and mounted",           lambda: f"Extinguisher Point {random.randint(1,50)}"),
        ("restroom faucet leaking",                  "replaced cartridge",                          lambda: f"Restroom {random.choice(['Men','Women'])} Faucet"),
        ("HVAC vent no airflow",                     "cleaned duct and replaced filter",            lambda: "Meeting Room 2"),
        ("emergency exit sign off",                  "replaced battery pack",                       lambda: f"Exit Sign {random.randint(1,30)}"),
        ("office chair armrest broken",              "replaced armrest",                            lambda: "Office Chair"),
        ("paper shredder jam",                       "cleared jam and oiled blades",                lambda: "Office Shredder"),
        ("coffee machine error",                     "descaled and reset",                          lambda: "Break Room Coffee Machine"),
        ("elevator certificate expired",             "coordinated inspection",                      lambda: "Elevator #2"),
        ("parking gate arm stuck",                   "replaced spring",                             lambda: "Parking Gate #1"),
        ("loading dock door seal torn",              "replaced rubber seal",                        lambda: "Loading Dock Door"),
    ],
    "HVAC": [
        ("AC unit not cooling",                      "replaced compressor capacitor",               lambda: "AC Unit 4"),
        ("chiller pump noisy",                       "replaced bearings",                           lambda: "Chiller #2"),
        ("thermostat unresponsive",                  "replaced thermostat",                         lambda: "Thermostat Floor 3"),
        ("air handler belt squealing",               "replaced belt",                               lambda: "AHU-5"),
        ("duct temperature sensor fault",            "replaced sensor",                             lambda: "Supply Duct 3A"),
    ],
    "Electrical": [
        ("circuit breaker tripping",                 "replaced breaker",                            lambda: f"Panel L{random.randint(1,10)} Breaker {random.randint(1,30)}"),
        ("light flickering",                         "tightened connections and replaced ballast",  lambda: "Ceiling Light Fixture"),
        ("outlet no power",                          "replaced outlet and reset GFCI",              lambda: f"Outlet #{random.randint(1,100)}"),
        ("emergency generator fail to start",        "replaced battery and tested",                 lambda: "Backup Generator"),
        ("signage lighting transformer hum",         "replaced transformer",                        lambda: "Signage Transformer #2"),
    ],
    "Slots": [
        ("payline display misaligned",               "replaced display module",                     _slot),
        ("hopper payout incorrect",                  "recalibrated hopper",                         _slot),
        ("game theme missing graphics",              "reloaded game firmware",                      _slot),
        ("progressive meter link down",              "reconnected RS485 cable",                     _slot),
    ],
    "Tables": [
        ("felt worn at player 3",                    "re-felted table",                             _table),
        ("dealer shoe broken",                       "replaced shoe",                               _table),
        ("chip tray lock broken",                    "replaced lock",                               _table),
        ("table light dim",                          "replaced bulb",                               _table),
    ],
    "": [
        ("general maintenance request",              "completed as requested",                      lambda: "Various"),
    ],
}


def _random_date() -> str:
    start = datetime(2020, 1, 1)
    end   = datetime(2025, 12, 31)
    delta = (end - start).days
    return (start + timedelta(days=random.randint(0, delta))).strftime("%Y-%m-%d")


def _random_notes() -> str:
    if random.random() >= 0.2:
        return ""
    tech = random.choice(TECHNICIAN_HANDLES)
    manpower = random.randint(1, 3)
    return f"Manpower: {manpower} | Performed By: {tech}"


def generate_templated_row() -> dict:
    dept = random.choices(DEPARTMENTS, weights=DEPT_WEIGHTS, k=1)[0]
    sub_dept = random.choice(SUB_DEPT_MAP.get(dept, [""]))
    templates_pool = TEMPLATES.get(dept) or TEMPLATES["General"]
    problem_tmpl, solution_tmpl, equip_fn = random.choice(templates_pool)

    equipment = equip_fn() if callable(equip_fn) else equip_fn
    problem  = problem_tmpl.format(equip=equipment)  if "{equip}" in problem_tmpl  else f"{problem_tmpl} on {equipment}"
    solution = solution_tmpl.format(equip=equipment) if "{equip}" in solution_tmpl else solution_tmpl

    return {
        "Report Date":              _random_date(),
        "Casino Name":              random.choice(CASINO_NAMES),
        "Department":               dept,
        "Sub-Department":           sub_dept,
        "Maintenance Type":         random.choice(MAINTENANCE_TYPES),
        "Equipment / Location":     equipment,
        "Problem Description":      problem,
        "Action Taken / Solution":  solution,
        "Status":                   random.choice(STATUSES),
        "Notes":                    _random_notes(),
    }


# ── DeepSeek batch generator ─────────────────────────────────────────────────

DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"

_LLM_PROMPT_TEMPLATE = """Generate exactly {n} realistic synthetic maintenance-log entries for a fictional casino operations dataset.

Output ONLY a valid JSON array of {n} objects. Each object MUST have these fields:
- department: one of "Gaming Floor", "IT", "HVAC", "Electrical", "General", "Slots", "Tables", or ""
- sub_department: appropriate for the department (Gaming Floor → Card Shuffler|Slot Machines|Table Games|Roulette|Jackpot System, IT → Network Infrastructure|Surveillance|IT Systems|Servers/Computers|AV/Power, others → "")
- equipment: a fictional equipment identifier like "Slot #345", "Camera CT12", "AC Unit 5", "Server 3". Do NOT use real brand names.
- problem: terse technician-style problem description, 10-40 words
- solution: what was done to resolve it, 5-30 words
- status: usually "OK" or "Working", occasionally "Escalated" or "Awaiting parts - Working"

Vary vocabulary. Use realistic paraphrases a field technician would write. Never mention real people, real companies, real cities, or proprietary systems. Output ONLY the JSON array — no prose, no markdown fences."""


def call_deepseek_batch(batch_size: int, api_key: str) -> list[dict]:
    """One call to DeepSeek → list of dicts. Returns [] on unrecoverable failure."""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "You are a synthetic data generator. Output only valid JSON."},
            {"role": "user",   "content": _LLM_PROMPT_TEMPLATE.format(n=batch_size)},
        ],
        "temperature": 0.9,
        "max_tokens": 4096,
    }

    for attempt in range(5):
        try:
            resp = requests.post(DEEPSEEK_URL, headers=headers, json=payload, timeout=90)
        except requests.exceptions.RequestException:
            time.sleep(2 ** attempt)
            continue

        if resp.status_code == 429:
            wait = float(resp.headers.get("Retry-After") or (2 ** attempt))
            time.sleep(wait)
            continue
        if resp.status_code != 200:
            time.sleep(2 ** attempt)
            continue

        try:
            content = resp.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, json.JSONDecodeError):
            time.sleep(2 ** attempt)
            continue

        # Strip common LLM wrappings (```json ... ```)
        content = content.strip()
        if content.startswith("```"):
            content = content.split("```", 2)[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip("`").strip()

        try:
            records = json.loads(content)
        except json.JSONDecodeError:
            time.sleep(2 ** attempt)
            continue

        if not isinstance(records, list):
            continue

        required = {"department", "sub_department", "equipment", "problem", "solution", "status"}
        out = []
        for entry in records:
            if isinstance(entry, dict) and required.issubset(entry.keys()):
                out.append({k: str(entry[k]) for k in required})
        return out

    return []


def convert_llm_row_to_full(entry: dict) -> dict:
    """Wrap an LLM-generated entry into a full 10-column row."""
    return {
        "Report Date":              _random_date(),
        "Casino Name":              random.choice(CASINO_NAMES),
        "Department":               entry["department"],
        "Sub-Department":           entry["sub_department"],
        "Maintenance Type":         random.choice(MAINTENANCE_TYPES),
        "Equipment / Location":     entry["equipment"],
        "Problem Description":      entry["problem"],
        "Action Taken / Solution":  entry["solution"],
        "Status":                   entry["status"],
        "Notes":                    _random_notes(),
    }


# ── Main ─────────────────────────────────────────────────────────────────────

FIELDS = [
    "Report Date", "Casino Name", "Department", "Sub-Department",
    "Maintenance Type", "Equipment / Location", "Problem Description",
    "Action Taken / Solution", "Status", "Notes",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed",      type=int, default=42)
    ap.add_argument("--templated", type=int, default=3000)
    ap.add_argument("--llm",       type=int, default=2000)
    ap.add_argument("--skip-llm",  action="store_true")
    ap.add_argument("--out",       type=Path, default=Path("data/sample.csv"))
    ap.add_argument("--batch",     type=int, default=20, help="Rows per LLM call")
    args = ap.parse_args()

    random.seed(args.seed)
    rows: list[dict] = []

    # ── Templated ─────────────────────────────────────────────────────────────
    print(f"[1/2] Generating {args.templated} templated rows…", flush=True)
    t0 = time.time()
    for _ in range(args.templated):
        rows.append(generate_templated_row())
    n_templated = len(rows)
    print(f"      done in {time.time() - t0:.1f}s ({n_templated / max(0.001, time.time() - t0):.0f} rows/s)")

    # ── LLM ──────────────────────────────────────────────────────────────────
    n_llm = 0
    if not args.skip_llm and args.llm > 0:
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            print("ERROR: DEEPSEEK_API_KEY not set. Use --skip-llm to run without LLM rows.", file=sys.stderr)
            return 1

        n_batches = math.ceil(args.llm / args.batch)
        print(f"[2/2] Generating ~{args.llm} LLM rows via DeepSeek ({n_batches} batches × {args.batch})…", flush=True)
        t0 = time.time()
        for i in range(n_batches):
            batch = call_deepseek_batch(args.batch, api_key)
            if not batch:
                print(f"      batch {i+1}/{n_batches}: empty (skipped)", flush=True)
                continue
            for entry in batch:
                rows.append(convert_llm_row_to_full(entry))
                n_llm += 1
            if (i + 1) % 5 == 0 or i == n_batches - 1:
                elapsed = time.time() - t0
                rate = n_llm / max(0.001, elapsed)
                print(f"      batch {i+1}/{n_batches}: total {n_llm} LLM rows ({rate:.1f} rows/s)", flush=True)
            if n_llm >= args.llm:
                break
        print(f"      LLM phase done in {time.time() - t0:.1f}s, {n_llm} rows accepted")
    else:
        print("[2/2] Skipping LLM phase")

    # ── Shuffle + write ──────────────────────────────────────────────────────
    random.shuffle(rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nWrote {len(rows)} rows ({n_templated} templated + {n_llm} LLM) to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
