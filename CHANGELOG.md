# CHANGELOG.md — Release & Modification History

All notable changes to the **Fisch Macro** project are documented in this file.

---

## [1.0.0] — 2026-11-11 (Production Modular Release)

### Added
- **Architectural Layering:**
  - Created `core/` package: Decoupled lifecycle management (`MacroEngine`, `StateManager`, `EventBus`, `CancellationToken`, `InputManager`).
  - Created `automation/` package: Isolated fishing workflow operations (`CastOperation`, `BiteWaitOperation`, `ReelOperation`, `EquipRodOperation`, `FishingWorkflow`, `ReelController`, `SigmaDeltaModulator`).
  - Created `vision/` package: Multi-tier screen capture (`MssScreenGrabber`, `PilScreenGrabber`, `MockScreenGrabber`, `ScreenGrabber`), pure computer vision analysis (`color_mask`, `runs_of`, `choose`, `analyze`, `measure`, `centers`), and predictive EMA tracking (`Track`).
  - Created `data/` package: Strongly typed dataclasses (`User`, `Session`, `LoginLog`), transactional context-managed database pool (`DatabaseManager`), repository pattern (`UserRepository`, `SessionRepository`, `LogRepository`), and atomic config persistence (`ConfigManager`).
  - Created `gui/` package: Modular Tkinter presentation layer (`ApiClient`, `Tip`, `DateField`, `LoginWindow`, `AccountDialog`, `MacroDashboard`).
- **Testing & Continuous Integration:**
  - Full automated Pytest suite (53 tests) covering all 5 subsystems with 100% pass rate.
  - Performance profiling suite (`tests/test_performance.py`): Vision throughput benchmark (> 1,200 FPS), control loop latency (< 2 µs), database indexed query latency (< 0.2 ms), and memory stability stress test (< 0.15 MB delta).
  - Cross-module end-to-end integration test suite (`tests/test_integration.py` - 7 tests).
  - Standalone service compatibility test suite (`test_service.py` - 10/10 PASS).
  - GitHub Actions CI pipeline (`.github/workflows/ci.yml`) testing across Ubuntu (with Xvfb), Windows, and macOS on Python 3.10, 3.11, and 3.12.
- **Documentation:**
  - Comprehensive documentation suite: `PROJECT_AUDIT.md`, `ARCHITECTURE.md`, `TEAM_ROLES.md`, `BRANCH_STRATEGY.md`, `ROADMAP.md`, `FEATURES.md`, `UI_SPEC.md`, `TEST_REPORT.md`, `USER_GUIDE.md`, `HANDOFF.md`, and `PHASE-LOG.md`.

### Changed
- **`fisch_macro.py` Refactoring:**
  - Reduced monolithic file from 1,751 lines down to a clean 375-line façade.
  - Rewired `Bot` class to delegate execution loop to `automation.FishingWorkflow`, `core.MacroEngine`, and `core.EventBus`.
  - Added dependency injection support for `grabber` and `input_mgr`, unlocking headless automated testing.
  - Preserved 100% backward compatibility for all external callers, launchers, and batch scripts.
- **`service.py` Persistence Layer:**
  - Replaced inline raw SQL queries with strongly typed repository calls via `data/`.
  - Preserved all API route contracts, status codes, and error responses.
- **`vision.capture.MssScreenGrabber`:**
  - Upgraded to modern `mss.MSS()` API, eliminating deprecation warnings.
- **Windows Platform Safety:**
  - Encapsulated Win32 `SendInput` and `timeBeginPeriod` calls behind platform guards with `MockInputDriver` fallbacks for non-Windows dev environments.

### Fixed
- Fixed unshielded Win32 `ctypes.windll` import crashes on macOS and Linux.
- Fixed potential duplicate callback argument error in `ui_kit.GSlider`.
- Fixed potential database lockups during concurrent sheet sync operations via thread-safe transactional context managers.
- Fixed non-deterministic config writes by implementing atomic tempfile and fsync writes with `.corrupted` backup recovery.
