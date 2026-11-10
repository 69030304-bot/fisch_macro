# FEATURES.md — Feature Inventory & Tracking Matrix

**Project:** Fisch Macro  
**Audit Reference:** Phase 0 Baseline  
**Status Legend:**  
- `Working`: Verified functional and stable.  
- `Partially Working`: Operates but has identified limitations or lack of platform decoupling.  
- `Broken`: Fails or throws unhandled errors.  
- `Missing`: Planned in roadmap but not yet implemented.  
- `Needs Verification`: Implemented but requires live game/Windows environment verification.  

---

## 1. Authentication & Member Management

| Feature | Subsystem | Status | Owner | Notes |
|---|---|---|---|---|
| User Registration | Backend / DB | **Working** | 69030343 | Validated; first user is admin; subsequent are regular users. |
| User Login | Backend / DB | **Working** | 69030343 | PBKDF2 hash verification; issues 12-hour bearer token. |
| Login Rate Limiting | Backend / Security | **Working** | 69030343 | 5 failed attempts -> 60s lockout. |
| Self Password Reset | Backend / DB | **Working** | 69030343 | Verified with nickname + birthday; 5 failures -> 300s lock. |
| Self Change Password | Backend / DB | **Working** | 69030343 | Invalidates all other active sessions; verifies old password. |
| Session Expiration & Cleanup | Backend / DB | **Working** | 69030343 | Expired tokens automatically cleaned up during login. |
| Client Heartbeat | Client / Network | **Working** | 69030208 | Background thread polls `/me` every 60s; kicks on 401/403. |
| Admin User List | Backend / GUI | **Working** | 69030343 / 69030208 | Admin table in `AccountDialog` with live status. |
| Admin Toggle Active | Backend / GUI | **Working** | 69030343 / 69030208 | Admins can suspend/unsuspend accounts. |
| Admin Password Reset | Backend / GUI | **Working** | 69030343 / 69030208 | Generates 8-character random password if blank. |
| Admin Delete User | Backend / DB | **Working** | 69030343 / 69030208 | Cascade deletes sessions via SQLite FK. |
| Google Sheet Live Sync | Backend / Cloud | **Working** | 69030343 | Debounced (2.0s); excludes sensitive hashes/tokens; graceful thread shutdown. |
| Admin Manual Sheet Sync | Backend / GUI | **Working** | 69030343 / 69030208 | One-click button in account dialog to trigger immediate sync. |

---

## 2. Persistence & Data Layer (Phase 5)

| Feature | Subsystem | Status | Owner | Notes |
|---|---|---|---|---|
| Strongly Typed Models | Data / Models | **Working** | 69030343 | `User`, `Session`, `LoginLog` dataclasses in `data.models` with `from_row()` and serialization. |
| Database Manager & Pool | Data / Database | **Working** | 69030343 | `DatabaseManager`: Context-managed transactions, dynamic path resolution, `PRAGMA foreign_keys = ON`. |
| User Repository | Data / DAL | **Working** | 69030343 | `UserRepository`: Decoupled CRUD, case-insensitive username lookups, failed count and lockout handling. |
| Session Repository | Data / DAL | **Working** | 69030343 | `SessionRepository`: Token hash queries, join with user, expired session cleanup, multi-session management. |
| Audit Log Repository | Data / DAL | **Working** | 69030343 | `LogRepository`: IP and timestamp audit tracking for security operations. |
| Safe Schema Migrations | Data / Database | **Working** | 69030343 | `MigrationManager` tracking migrations in `_schema_migrations` table idempotently. |
| Atomic Config Manager | Data / Config | **Working** | 69030343 | `ConfigManager`: Atomic tempfile + fsync write, fallback defaults, automatic `.corrupted` backup recovery. |

---

## 3. Desktop GUI & User Experience

| Feature | Subsystem | Status | Owner | Notes |
|---|---|---|---|---|
| Authentication UI | Presentation | **Working** | 69030377 / 69030208 | Theme `LOGIN` (indigo/peach), tabs for Sign In, Register, Forgot. |
| Main Dashboard Window | Presentation | **Working** | 69030377 / 69030208 | Header, live stats (fish count, runtime, cycles), status chip. |
| Custom Rounded Widgets | Presentation | **Working** | 69030377 / 69030208 | `ui_kit.py`: Canvas-drawn anti-aliased cards, buttons, tabs. |
| Live Camera Preview | Presentation / Vision | **Working** | 69030208 | Displays captured minigame slice with color mask overlays. |
| Calibration Tool | Presentation / Vision | **Working** | 69030208 | Fullscreen overlay, loupe zoom, color picker, region bounding box. |
| Settings Tab | Presentation | **Working** | 69030208 | Sliders and text fields for timing, PID constants, and tolerances. |
| Log Viewer Tab | Presentation | **Working** | 69030208 | Thread-safe queue log display with color tags. |
| Database Viewer GUI | Admin Tools | **Working** | 69030208 / 69030343 | `view_database.py` standalone tool with raw SQL console. |

---

## 4. Automation Core & Fishing Workflow

| Feature | Subsystem | Status | Owner | Notes |
|---|---|---|---|---|
| Rod Equipping | Automation | **Working** | 69030304 | `EquipRodOperation`: Taps rod hotbar slot (1-9) once at startup. |
| Casting Action | Automation / Input | **Working** | 69030304 | `CastOperation`: Holds left mouse button for configurable `cast_hold` duration. |
| Bite Detection / Shake | Automation / Vision | **Working** | 69030304 | `BiteWaitOperation`: Repeatedly taps `Enter` and toggles `\` navigation. |
| Horizontal Reel Tracking | Vision / Automation | **Working** | 69030304 | `ReelOperation`: Vectorized color masking and clustering with `ReelController`. |
| Predictive Position Estimator | Core / Automation | **Working** | 69030304 | `Track` class uses exponential moving average (EMA) velocity. |
| PD Controller & Sigma-Delta | Automation / Core | **Working** | 69030304 | `ReelController` & `SigmaDeltaModulator` modularized with comprehensive unit tests. |
| Telemetry Trace Recording | Monitoring | **Working** | 69030304 | Logs timestamped tracking data to `fisch_trace.csv`. |
| Global Hotkeys | Input / Core | **Working** | 69030304 | `pynput` listener for F6 (start/stop), F7 (abort), F8 (snapshot). |
| Emergency Stop Failsafe | Input / Safety | **Working** | 69030304 | Cursor at (0, 0) aborts macro loop immediately. |
| Platform Independence | Core / Input | **Working** | 69030304 / 69030450 | `core.input` abstracts Win32 SendInput and provides MockInputDriver for cross-platform execution & tests. |

---

## 5. Testing & Infrastructure

| Feature | Subsystem | Status | Owner | Notes |
|---|---|---|---|---|
| Backend Automated Tests | QA / Backend | **Working** | 69030450 | `test_service.py` and `tests/test_service_compat.py` pass 10/10 test cases. |
| Database Unit Tests | QA / Backend | **Working** | 69030450 / 69030343 | `tests/test_database.py`: 8 tests validating transactions, cascades, repositories, migrations, and atomic config. |
| Automated Vision Tests | QA / Vision | **Working** | 69030450 | `tests/test_vision_math.py` unit tests for `color_mask`, `runs_of`, `choose`, `Track`, and `centers`. |
| Automated Control Tests | QA / Core | **Working** | 69030450 | `tests/test_core.py` tests for `Track` EMA, `InputManager`, and failsafe triggers. |
| Automated Macro Engine Tests | QA / Core | **Working** | 69030450 | `tests/test_core.py` tests for `StateManager`, `EventBus`, `CancellationToken`, and `MacroEngine`. |
| Automated Automation Tests | QA / Automation | **Working** | 69030450 | `tests/test_automation.py` tests for `ReelController`, `SigmaDeltaModulator`, and operations. |
| CI Pipeline Configuration | QA / DevOps | **Missing** | 69030450 | GitHub Actions workflow to run automated tests on pull requests. |
