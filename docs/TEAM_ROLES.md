# TEAM_ROLES.md — Team Member Responsibilities and Ownership Mapping

**Project:** Fisch Macro  
**Academic / Team Structure:** 5 Designated Members  
**Framework:** Shared Responsibility with Strict Subsystem Ownership  

---

## 1. Team Roster and Designation

| Student ID | Full Name | Designated Role | Primary Branch | Key Deliverables |
|---|---|---|---|---|
| **69030450** | นายกิตติศักดิ์ พัฒนนิติศักดิ์ | Quality Assurance / Testing / Documentation | `team/69030450-qa-docs` | Automated test suites, regression testing, user manuals, project audit, architectural docs, presentation material |
| **69030377** | นางสาวพิชชาภา ภูววิไลเมธา | UX / UI Design | `team/69030377-ux-ui` | UI mockups, design systems (colors, typography, spacing), user journey, component specifications |
| **69030343** | นายธีระนิตย์ บุญทวี | Backend & Database Developer | `team/69030343-backend-db` | SQLite schemas, data models, REST endpoints (FastAPI), data validation, Google Sheets sync, security/hashing |
| **69030304** | นายชยภัทร พุทธศรีเมือง | Python Application & Automation Core | `team/69030304-python-automation` | Macro Engine, fishing workflow algorithms, vision capture & detection, PID control, SendInput, failsafe |
| **69030208** | นายฤทธิพร วงค์ป้อม | GUI Implementation & Database Integration | `team/69030208-gui-db` | Tkinter desktop UI, `ui_kit` components, client-side API integration, account dialog, DB viewer |

---

## 2. Detailed Member Responsibilities

### 2.1 Member 69030450 — Quality Assurance & Documentation
- **Name:** นายกิตติศักดิ์ พัฒนนิติศักดิ์
- **Primary Ownership:**
  - `test_service.py`, `tests/` directory, testing fixtures.
  - `docs/PROJECT_AUDIT.md`, `docs/ARCHITECTURE.md`, `docs/TEAM_ROLES.md`, `docs/BRANCH_STRATEGY.md`, `docs/ROADMAP.md`, `docs/FEATURES.md`, `docs/TESTING.md`, `docs/USER_GUIDE.md`.
  - `HANDOFF.md`, `PHASE-LOG.md`.
  - Windows verification logs and regression test sign-off.
- **Workflow:**
  - Authors unit and integration tests.
  - Validates bug fixes across branches.
  - Ensures full documentation coverage before phase sign-offs.

### 2.2 Member 69030377 — UX/UI Design
- **Name:** นางสาวพิชชาภา ภูววิไลเมธา
- **Primary Ownership:**
  - Design system specifications (color palettes, font hierarchy, component spacing).
  - Theme definitions (`MAIN` navy/cyan theme and `LOGIN` indigo/peach theme).
  - Navigation flow, interaction design, and visual polish guidelines.
- **Workflow:**
  - Produces visual specifications and collaborates directly with Member 69030208 on widget implementation.

### 2.3 Member 69030343 — Backend & Database Developer
- **Name:** นายธีระนิตย์ บุญทวี
- **Primary Ownership:**
  - `database.py`: SQLite schemas (`users`, `sessions`, `login_logs`), indexes, foreign keys, migrations.
  - `service.py`: Business logic, input validation, rate-limiting rules, token lifecycle.
  - `security.py`: Cryptographic primitives, PBKDF2 hashing, timing attack protection.
  - `main.py`: FastAPI server routes, request/response models, middleware, error handlers.
  - `sheets.py`: Google Sheets export and debounced synchronization.
  - `google_apps_script.js`: Google Apps Script receiver script.
- **Workflow:**
  - Primary gatekeeper for schema modifications and API contract updates.

### 2.4 Member 69030304 — Python Application & Automation Core
- **Name:** นายชยภัทร พุทธศรีเมือง
- **Primary Ownership:**
  - Application orchestration and macro lifecycle.
  - Automation engine and state machine (`IDLE`, `STARTING`, `RUNNING`, `PAUSED`, `STOPPING`, `ERROR`).
  - Fishing sequence logic: casting, bite detection / shake minigame, reeling loop.
  - Computer vision: screen capture (`mss`), color masking (NumPy), run-length clustering (`runs_of`), object tracking (`Track`).
  - Minigame control algorithms: PD error computation and sigma-delta mouse pulsing.
  - Win32 hardware simulation (`SendInput`, scan codes), failsafe watchdog, and input cleanup.
- **Workflow:**
  - Ensures the macro engine remains modular, performant, and decoupled from GUI frameworks.

### 2.5 Member 69030208 — GUI Implementation & Database Integration
- **Name:** นายฤทธิพร วงค์ป้อม
- **Primary Ownership:**
  - Desktop presentation layer (`fisch_macro.py` GUI components, `ui_kit.py`).
  - Implementation of custom widgets: `GButton`, `Card`, `StatCard`, `Chip`, `PillTabs`, `Toggle`, `GSlider`, `RoundEntry`, `RoundCombo`.
  - Client-side backend integration (`ApiClient`, asynchronous request dispatch with `run_bg`).
  - `view_database.py`: Administrative SQLite database visualizer and query console.
  - Dialog windows: `AccountDialog`, calibration overlay interface.
- **Workflow:**
  - Implements UI based on 69030377's designs and connects frontend to 69030343's backend API.

---

## 3. Subsystem Ownership Matrix

| Subsystem | Primary Owner | Collaborator | Reviewer / Sign-off |
|---|---|---|---|
| **UX/UI Design & System** | 69030377 | 69030208 | 69030450 |
| **GUI Implementation** | 69030208 | 69030377 | 69030450 |
| **Database Schema & Migrations** | 69030343 | 69030208 | 69030450 |
| **Backend API & Service Logic** | 69030343 | 69030304 | 69030450 |
| **Python Application Lifecycle** | 69030304 | 69030450 | 69030450 |
| **Macro Engine & State** | 69030304 | 69030450 | 69030450 |
| **Fishing Workflow & Controls** | 69030304 | 69030450 | 69030450 |
| **Vision & Screen Capture** | 69030304 | 69030450 | 69030450 |
| **Input & Failsafe System** | 69030304 | 69030450 | 69030450 |
| **QA / Automated Testing** | 69030450 | All Members | Coordinator |
| **Technical Documentation** | 69030450 | All Members | Coordinator |

---

## 4. Collaboration & Change Protocol

1. **Interface Stability**: No member may modify a shared interface (e.g. REST API contract, database schema, macro engine event signatures) without prior written alignment documented in `PHASE-LOG.md`.
2. **Non-Destructive Development**: Existing features, working algorithms, and user configuration compatibility must be preserved.
3. **Clean Code Isolation**: UI code must not contain automation logic, and automation code must not directly import UI classes.
4. **Testing Mandatory**: Every pull request into `develop` requires automated tests authored or verified by Member 69030450.
