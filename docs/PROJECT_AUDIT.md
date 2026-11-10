# PROJECT_AUDIT.md — Phase 0 Repository Audit Report

**Project:** Fisch Macro  
**Repository:** `https://github.com/69030304-bot/fisch_macro.git`  
**Audit Date:** 2026-11-11  
**Audit Author:** Member 69030450 (นายกิตติศักดิ์ พัฒนนิติศักดิ์ — QA / Docs)  
**Branch:** `task/69030450-phase0-audit`  
**Status:** COMPLETED  

---

## 1. Executive Summary

This audit establishes the baseline architectural state, code inventory, functional coverage, dependency matrix, test results, and operational risks of the **Fisch Macro** project prior to Phase 1 architecture refactoring.

The repository represents a functional prototype combining:
1. A **FastAPI + SQLite** backend providing user authentication, role-based access control (Admin/User), rate-limiting, session management, and Google Sheet integration via Google Apps Script.
2. A **Python + Tkinter + Pillow** desktop macro application (`fisch_macro.py`) delivering automated fishing capabilities for the game Fisch (casting, bite detection / shake minigame, horizontal bar reel tracking with PD control, failsafe emergency stops, and calibration).
3. A custom modern widget system (`ui_kit.py`) implementing themes (`MAIN` navy/cyan and `LOGIN` indigo/peach), anti-aliased rounded cards, gradient buttons, toggles, sliders, and custom inputs.
4. An administrative SQLite inspection utility (`view_database.py`) with raw SQL console.

**Key Finding:** While existing features operate successfully, the application core suffers from monolithic architectural coupling in `fisch_macro.py` (1,931 lines), platform-bound Windows Win32 API calls (`ctypes.windll`) executed unconditionally at module import time, and an absence of automated regression tests for automation, vision, and UI subsystems.

---

## 2. Codebase Inventory

| File | Size (Bytes) | Lines | Primary Responsibility | Primary Owner |
|---|---|---|---|---|
| `fisch_macro.py` | 89,436 | 1,931 | Monolithic client: GUI, Bot state machine, Vision detection, Win32 SendInput, HTTP API client | 69030304 / 69030208 |
| `ui_kit.py` | 34,644 | 816 | Custom Canvas/Pillow UI widgets (buttons, cards, toggles, sliders, tabs, combos) | 69030377 / 69030208 |
| `main.py` | 5,842 | 168 | FastAPI REST API server (11 endpoints) | 69030343 |
| `service.py` | 16,597 | 317 | Core business logic, validation, rate limiting, hashing, sheet export data | 69030343 |
| `database.py` | 3,926 | 67 | SQLite database schema (`users`, `sessions`, `login_logs`) and connection context | 69030343 |
| `security.py` | 2,543 | 55 | PBKDF2-HMAC-SHA256 password hashing, token generation, constant-time verification | 69030343 |
| `sheets.py` | 4,702 | 100 | Background worker thread with debounced (2.0s) push to Google Apps Script webhook | 69030343 |
| `view_database.py` | 15,756 | 326 | Tkinter SQLite database viewer and SQL query console | 69030208 / 69030343 |
| `test_service.py` | 5,365 | 110 | Automated test suite for backend `service.py` and `database.py` (10 test cases) | 69030450 |
| `google_apps_script.js` | 2,432 | 49 | Google Apps Script Web App webhook code for Google Sheets sync | 69030343 |
| `settings.py` | 831 | 20 | Settings loader for Google Sheet webhook URL and secret | 69030343 |
| `settings.example.json` | 69 | 4 | Template configuration for Google Sheet integration | 69030343 |
| `settings.json` | 52 | 4 | Local configuration for Google Sheet integration | 69030343 |
| `requirements.txt` | 49 | 7 | Python package dependencies (`fastapi`, `uvicorn`, `requests`, `pillow`, `numpy`, `pynput`, `mss`) | All Members |
| `setup.bat` | 3,008 | 86 | Windows one-click environment installer & virtual environment setup script | 69030450 |
| `start_app.bat` | 501 | 12 | Launcher for client application (`fisch_macro.py`) | 69030450 |
| `start_backend.bat` | 533 | 12 | Launcher for backend server (`main.py`) | 69030450 |
| `view_database.bat` | 518 | 12 | Launcher for database viewer tool (`view_database.py`) | 69030450 |
| `AGENT.md` | 26,897 | 1,193 | Project master instructions, architectural blueprint, team specifications | Coordinator / Lead |
| `README.md` | 26,149 | 222 | Project documentation and educational guide (in Thai) | 69030450 |
| `วิธีใช้.txt` | 1,043 | 12 | Quick start guide for end users (in Thai) | 69030450 |

---

## 3. Existing Architecture vs. Target Architecture

### 3.1 Actual Current Architecture

Currently, the application is split into two physical processes:

```
[ Backend Process (FastAPI) ]
  main.py (HTTP Routes)
    │
    ▼
  service.py (Business Logic / Auth / Rate Limit)
    │
    ├──▶ security.py (PBKDF2-HMAC-SHA256, Tokens)
    ├──▶ database.py (SQLite: app.db)
    └──▶ sheets.py (Debounced Thread) ──▶ Google Apps Script ──▶ Google Sheet

[ Desktop App Process (Tkinter) ]
  fisch_macro.py (Monolithic Script)
    ├── UI Layer (LoginWindow, App, AccountDialog, Calibration Overlay)
    │     └── ui_kit.py (Canvas-rendered rounded widgets)
    ├── Client Network Layer (ApiClient calling FastAPI)
    ├── Automation Engine (Bot Thread: cast, wait, reel, rest)
    ├── Vision Layer (Grabber with mss/ImageGrab, analyze, measure, runs_of)
    ├── Control Layer (Track EMA velocity, PD controller, sigma-delta pulsing)
    ├── Input Layer (ctypes.windll.user32.SendInput, scan codes)
    └── Hotkey Layer (pynput.keyboard.GlobalHotKeys for F6, F7, F8)
```

### 3.2 Target Modular Architecture (AGENT.md Blueprint)

```
Fisch Macro
│
├── Presentation Layer (ui/): Dashboard, Controls, Settings, Profiles, Logs, Theme System
├── Application Layer (app/): Application Controller, Workflow Manager, Hotkey Manager, Lifecycle
├── Core Layer (core/): Macro Engine, State Manager, Event Bus, Error Handler
├── Automation Layer (automation/): Fishing Workflow, Casting, Bite Detection, Reeling, Scheduler
├── Vision Layer (vision/): Screen Capture, Image Detection, Color Analysis, Recognition
├── Input Layer (input/): Mouse Controller, Keyboard Controller, Input Manager, Failsafe
├── Data Layer (data/): Database, Repository, Models, Configuration Persistence
└── Monitoring Layer (monitoring/): Logger, Diagnostics, Telemetry, Performance Monitor
```

---

## 4. Current Features Audit

| Feature | Subsystem | Implementation File | Status | Notes |
|---|---|---|---|---|
| User Registration | Backend / DB | `service.py`, `main.py` | Working | First user becomes admin; subsequent become user; regex validation. |
| User Authentication | Backend / DB | `service.py`, `main.py` | Working | PBKDF2 hash verify; issue 12h session token; rate limited. |
| Rate Limiting & Lockout | Backend / Security | `service.py` | Working | 5 failed logins -> 60s lock; 5 failed resets -> 300s lock. |
| Self Password Reset | Backend / DB | `service.py` | Working | Verified via nickname + birthday (and optional username). |
| Change Password | Backend / DB | `service.py` | Working | Validates old password; invalidates all other active sessions. |
| Admin User Management | Backend / DB | `service.py`, `main.py` | Working | Toggle active status; reset user password; delete user (cascade). |
| Google Sheet Live Sync | Backend / Integration | `sheets.py`, `google_apps_script.js` | Working | 2-second debounce; excludes password hashes and tokens. |
| Database Viewer GUI | Admin Tools | `view_database.py` | Working | Visual treeviews for tables; SQL query execution box. |
| Modern GUI & Themes | Presentation | `ui_kit.py`, `fisch_macro.py` | Working | Two themes (`MAIN`, `LOGIN`); Pillow-rendered anti-aliased cards and buttons. |
| Client Heartbeat | Client / Network | `fisch_macro.py` | Working | Polling `/me` every 60s; automatic kick on 401/403 or 5 connection drops. |
| Global Hotkeys | Input / Core | `fisch_macro.py` | Working | F6 (Toggle start/stop), F7 (Emergency stop), F8 (Snapshot). |
| Emergency Failsafe | Input / Safety | `fisch_macro.py` | Working | Cursor at screen (0, 0) triggers immediate bot abort. |
| Screen Capture | Vision | `fisch_macro.py` | Working | Prefers `mss` (fast); falls back to `PIL.ImageGrab`. |
| Color Detection & Slicing | Vision | `fisch_macro.py` | Working | Slices horizontal region; tolerates RGB range with NumPy masks. |
| Horizontal Run-Length Clustering | Vision | `fisch_macro.py` | Working | `runs_of` groups contiguous matching pixel columns. |
| Reel Tracking & PID Control | Automation / Core | `fisch_macro.py` | Working | EMA tracking (`Track`), PD error correction, sigma-delta pulsed mouse clicks. |
| Calibration Overlay | Vision / GUI | `fisch_macro.py` | Working | Fullscreen overlay for region selection and color sampling with loupe. |
| Telemetry Trace Logging | Monitoring | `fisch_macro.py` | Working | Exports `fisch_trace.csv` for post-run telemetry analysis. |

---

## 5. Dependency Audit

### 5.1 Python Packages (`requirements.txt`)
- `fastapi` (0.162.4): Modern high-performance web framework for the backend authentication API.
- `uvicorn` (0.54.0): ASGI web server.
- `requests` (2.34.2): HTTP client used in `fisch_macro.py` (`ApiClient`) and `sheets.py` (webhook caller).
- `pillow` (13.0.0): Image manipulation, rendering UI cards/gradients, and screen capture fallback.
- `numpy` (2.5.4): Fast numerical matrix operations for color masking and UI gradient rendering.
- `pynput` (1.8.2): Global keyboard listeners for hotkeys (F6, F7, F8).
- `mss` (10.2.0): High-speed cross-platform screen capture library.

### 5.2 Operating System & Platform Dependencies
- **Windows APIs (via `ctypes`)**:
  - `user32.SendInput`: Hardware-level keyboard and mouse simulation.
  - `user32.GetCursorPos`: Reading mouse coordinates for failsafe detection.
  - `shcore.SetProcessDpiAwareness(2)`: DPI scaling coordination.
  - `winmm.timeBeginPeriod(1)` / `winmm.timeEndPeriod(1)`: Precision 1ms timer resolution.
  - `winsound.Beep`: Audio feedback when F8 snapshot is captured.

---

## 6. Baseline Test Results

### 6.1 Backend Automated Tests (`test_service.py`)
Executed on 2026-11-11 using Python 3.12.9 in isolated `.venv`:
```
เริ่มการทดสอบ...
[PASS] สมัครสมาชิกคนแรกเป็น admin
[PASS] ป้องกันชื่อผู้ใช้ซ้ำ
[PASS] สมัครสมาชิกคนที่สองเป็น user
[PASS] ปฏิเสธรหัสผ่านผิด
[PASS] ล็อกอินสำเร็จและได้ token
[PASS] ดึงข้อมูลผู้ใช้ปัจจุบัน (current_user) สำเร็จ
[PASS] export_users_rows ปลอดภัยและถูกต้อง
[PASS] ระงับบัญชีผู้ใช้สำเร็จ
[PASS] ปลดระงับสำเร็จ
[PASS] ลืมรหัสผ่านด้วย nickname + birthday สำเร็จ (ไม่ต้องใส่ username)
[PASS] ลืมรหัสผ่านด้วย username + nickname + birthday สำเร็จ

ผ่านทุกการทดสอบ! (10/10 PASS, 0 FAIL)
```

### 6.2 Unit and Regression Test Suite Evolution
- **Core Automation Suite (`tests/test_core.py`)**: 9 tests verifying StateManager, EventBus, CancellationToken, and MacroEngine lifecycle.
- **Vision Math Suite (`tests/test_vision_math.py`)**: 5 tests verifying `color_mask`, `runs_of`, `choose`, EMA `Track`, and `centers`.
- **Vision Suite (`tests/test_vision.py`)**: 5 tests verifying mock grabber, synthetic minigame detection, row stride, and track reset.
- **Automation Controller Suite (`tests/test_automation.py`)**: 8 tests verifying `ReelController`, `SigmaDeltaModulator`, and operations.
- **Database Persistence Suite (`tests/test_database.py`)**: 8 tests verifying SQLite foreign key cascades, transaction rollbacks, repositories, safe schema migrations, and atomic configuration recovery.
- **Service Compatibility Suite (`tests/test_service_compat.py`)**: 1 test running full 10-step service verification suite.
- **Overall Pytest Suite**: **36/36 PASS** (100% passing across all modules).

---

## 7. Identified Technical Debt & Risks

| Risk ID | Severity | Description | Impact | Mitigation Strategy |
|---|---|---|---|---|
| **R-01** | High | Monolithic `fisch_macro.py` (1,931 lines) mixing UI, network, input, vision, and bot state. | Difficult to maintain, test, or collaborate without merge conflicts. | Incrementally decouple into modular layers (`core/`, `automation/`, `vision/`, `input/`, `ui/`). |
| **R-02** | High | Unshielded `ctypes.windll` at global scope in `fisch_macro.py`. | Prevents running unit tests or CI on macOS/Linux. | Encapsulate Windows input behind an interface/adapter with platform guards or mock backends. |
| **R-03** | Medium | No unit tests for vision, control algorithms, or API client. | Regressions can occur undetected during refactoring. | Extract pure mathematical/vision functions (`color_mask`, `runs_of`, `Track`, PID) and write pytest suites. |
| **R-04** | Medium | Flat root repository structure vs. README folder structure. | Discrepancy between documentation and code; clutter in project root. | Plan staged relocation into clean subpackages without breaking existing `.bat` runners. |
| **R-05** | Low | Missing `.gitignore` in initial commit. | Risk of committing `.venv`, `app.db`, or user configs. | Created comprehensive `.gitignore`. |
| **R-06** | Low | Sensitive tokens/settings in plaintext `settings.json`. | Accidental leak if committed. | Ignored in `.gitignore`; keep `settings.example.json` tracked. |

---

## 8. Recommendations & Next Steps

1. **Establish Team Ownership & Branch Strategy (Phase 1)**: Formally assign subsystem ownership across the 5 members and verify Git branch isolation.
2. **Abstract Platform Dependencies**: Isolate `ctypes.windll` behind an `InputProvider` abstraction so automation logic and vision detection can be tested headlessly on any platform.
3. **Add Vision & Control Unit Tests**: Create unit tests for `runs_of`, `choose`, `analyze`, `Track`, and PID calculation with static fixture images.
4. **Decouple GUI from Macro Engine**: Introduce a clean `ApplicationController` and event bus/callback interface between Tkinter and the `Bot` thread.
5. **Preserve Compatibility**: Keep `setup.bat`, `start_app.bat`, and `start_backend.bat` working at every increment without breaking end-user workflows.
