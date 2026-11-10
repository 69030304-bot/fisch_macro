# AGENT.md
# Fisch Macro — Master Development Instructions

**Project:** Fisch Macro  
**Repository:** https://github.com/69030304-bot/fisch_macro.git  
**Platform:** Windows  
**Development Strategy:** Preserve & Refactor  
**Feature Scope:** Full Automation  
**UI Direction:** Modern Desktop Application  
**Autonomy:** High  
**Testing:** Full  
**Git Workflow:** Team-Based Branching, Pull Requests, and CI

---

# 1. PROJECT MISSION

You are an autonomous software development agent responsible for developing, maintaining, testing, and improving Fisch Macro.

The objective is to evolve the existing Fisch Macro application into a modern, reliable, modular, and maintainable Windows desktop automation application.

The project must preserve existing working functionality while improving its architecture, performance, reliability, usability, and maintainability.

## Core Requirements

- Windows-only desktop application.
- Full Fisch automation functionality.
- Modern and polished GUI.
- Maintainable and modular architecture.
- Reliable automation engine.
- Efficient CPU and memory usage.
- Comprehensive error handling.
- Full automated and manual testing.
- Clear documentation for future developers.
- Collaborative Git workflow for five team members.

## Development Strategy: Preserve & Refactor

This is NOT a complete rewrite project.

You MUST:

1. Inspect the existing codebase before changing anything.
2. Preserve existing working functionality.
3. Understand existing algorithms before refactoring.
4. Reuse suitable existing modules and dependencies.
5. Refactor incrementally.
6. Replace components only when technically justified.
7. Maintain compatibility with existing user configurations.
8. Add regression tests for important existing behavior.

Never rewrite the entire application simply because a different implementation appears cleaner.

---

# 2. INITIAL REPOSITORY SETUP

Before implementation, clone the repository.

```bash
git clone https://github.com/69030304-bot/fisch_macro.git
cd fisch_macro
```

Then:

1. Read this AGENT.md completely.
2. Inspect repository structure.
3. Inspect README and existing documentation.
4. Inspect source code and configuration files.
5. Identify programming language and frameworks.
6. Identify the current application entry point.
7. Identify existing dependencies and build tools.
8. Inspect Git branches and working-tree status.
9. Identify existing tests.
10. Run the existing application and tests where possible.

Do not assume that the project uses Python, PySide6, PyQt, Tkinter, SQLite, or any other framework until verified from the repository.

If cloning fails:

- Investigate repository access and authentication.
- Verify the repository URL.
- Do not silently substitute another repository.
- Report the exact blocker.

Do not begin major implementation until the initial audit is complete.

---

# 3. TEAM MEMBERS AND RESPONSIBILITIES

The project consists of five designated team members.

Every agent must understand the ownership structure before modifying code.

## 3.1 Member 69030450 — QA and Documentation

**Name:** นายกิตติศักดิ์ พัฒนนิติศักดิ์

**Role:** Quality Assurance / Testing / Documentation

Responsibilities:

- Test application functionality.
- Perform unit testing.
- Perform integration testing.
- Perform regression testing.
- Identify and document bugs.
- Verify bug fixes.
- Prepare technical documentation.
- Prepare user manuals.
- Prepare project presentation materials.
- Maintain testing reports.
- Verify release readiness.

Primary branch:

`team/69030450-qa-docs`

## 3.2 Member 69030377 — UX/UI Design

**Name:** นางสาวพิชชาภา ภูววิไลเมธา

**Role:** UX/UI Designer

Responsibilities:

- Design application user experience.
- Design modern application interfaces.
- Define design systems.
- Define colors, typography, spacing, and components.
- Design navigation and user flows.
- Prepare UI specifications.
- Review visual consistency.
- Coordinate with GUI implementation.

Primary branch:

`team/69030377-ux-ui`

## 3.3 Member 69030343 — Backend and Database

**Name:** นายธีระนิตย์ บุญทวี

**Role:** Backend / Database Developer

Responsibilities:

- Design database architecture.
- Manage database schemas.
- Design data models.
- Develop backend services.
- Implement data access layers.
- Implement data validation.
- Manage data persistence.
- Integrate database functionality.
- Maintain database reliability.

Primary branch:

`team/69030343-backend-db`

This member is the primary owner of database schema changes.

## 3.4 Member 69030304 — Python Application and Automation

**Name:** นายชยภัทร พุทธศรีเมือง

**Role:** Python Application / Automation Developer

Responsibilities:

- Develop the Python application.
- Maintain application architecture.
- Develop the Macro Engine.
- Develop automatic fishing functionality.
- Implement fishing workflows.
- Implement automation scheduling.
- Integrate Vision and Input systems.
- Manage application lifecycle.
- Improve automation performance and reliability.

Primary branch:

`team/69030304-python-automation`

This member is the primary owner of the Python application and automation core.

## 3.5 Member 69030208 — GUI and Database Integration

**Name:** นายฤทธิพร วงค์ป้อม

**Role:** GUI Developer / Database Integration

Responsibilities:

- Implement application GUI.
- Improve visual appearance.
- Develop reusable UI components.
- Integrate GUI with backend services.
- Implement database integration in the application.
- Improve interface usability.
- Perform GUI testing.
- Coordinate with UX/UI and Backend developers.

Primary branch:

`team/69030208-gui-db`

---

# 4. TEAM OWNERSHIP AND COLLABORATION

Subsystem ownership must be clearly defined.

| Subsystem | Primary Owner | Collaborator |
|---|---|---|
| UX/UI Design | 69030377 | 69030208 |
| GUI Implementation | 69030208 | 69030377 |
| Database Schema | 69030343 | 69030208 |
| Backend / Data Access | 69030343 | 69030304 |
| Python Application | 69030304 | 69030450 |
| Macro Engine | 69030304 | 69030450 |
| Fishing Automation | 69030304 | 69030450 |
| QA / Regression | 69030450 | All Members |
| Documentation | 69030450 | All Members |

## Ownership Rules

1. Every subsystem must have a primary owner.
2. Other members may contribute with coordination.
3. Never overwrite another member's implementation.
4. Never modify another subsystem's public interface without coordination.
5. Document interface changes.
6. Keep communication between modules explicit.
7. Review shared files before modifying them.

### Database Collaboration

- Member 69030343 owns database schema changes.
- Member 69030208 implements GUI-side database integration.
- GUI developers must follow approved data contracts.
- Coordinate before modifying shared database models or schemas.

### UI Collaboration

- Member 69030377 owns UX/UI specifications.
- Member 69030208 owns GUI implementation.
- UI implementation should follow the agreed design system.
- Design changes must be documented.

### Automation Collaboration

- Member 69030304 owns the automation core.
- Other members may contribute tests, documentation, and supporting functionality.
- Automation logic must not be tightly coupled to GUI implementation.

---

# 5. GIT BRANCH STRATEGY

Never work directly on `main`.

The repository must use the following branch structure:

## Main Branches

### main

Purpose:

- Stable production version.
- Release-ready code.
- Verified application versions.

Rules:

- No direct development.
- No direct commits from team members.
- No merging without explicit project maintainer approval.

### develop

Purpose:

- Shared integration branch.
- Collect completed team contributions.
- Run integration testing.
- Verify cross-module compatibility.

Rules:

- Changes must arrive through Pull Requests.
- CI must be checked before integration.
- Conflicts must be reviewed.
- Do not merge untested work.

## Team Branches

```text
team/69030450-qa-docs
team/69030377-ux-ui
team/69030343-backend-db
team/69030304-python-automation
team/69030208-gui-db
```

Each member is responsible for their designated branch.

## Task Branches

For independent tasks, create additional task branches.

Examples:

```text
feature/69030304-macro-engine
feature/69030304-fishing-workflow
feature/69030377-dashboard-design
feature/69030208-gui-components
feature/69030343-database-schema
fix/69030450-regression-tests
refactor/69030304-core-architecture
docs/69030450-user-manual
```

Task branches should be created from the relevant member branch or agreed integration base.

After implementation:

1. Test the changes.
2. Commit changes.
3. Push the task branch.
4. Open a Pull Request into the relevant member branch.
5. Review and integrate.
6. Open a Pull Request from the member branch into `develop` when the work is ready.

Avoid unnecessary branch proliferation.

---

# 6. GIT OPERATING RULES

Before starting work:

```bash
git status
git branch --show-current
git fetch origin
```

Never discard uncommitted changes belonging to another task.

Before changing branches, inspect the working tree.

If there are uncommitted changes:

- Determine their ownership.
- Preserve them.
- Commit or safely stash only when appropriate.
- Never overwrite another member's work.

## Commit Standards

Use clear and meaningful commit messages.

Examples:

```text
docs: add project architecture documentation
feat: implement fishing workflow
feat: add macro engine state management
fix: release input on emergency stop
refactor: separate automation from UI
test: add fishing workflow regression tests
ui: improve dashboard layout
```

Commit only logically related changes.

Review the complete diff before committing:

```bash
git diff
git diff --staged
```

## Remote Git Permissions

Agents may:

- Clone the repository.
- Fetch remote changes.
- Create local branches.
- Commit local changes.
- Push to authorized team/task branches.
- Open Pull Requests targeting `develop`.
- Review Pull Requests.
- Check CI results.

Agents MUST NOT perform these actions without explicit user approval:

- Merge into `main`.
- Push directly to `main`.
- Delete protected branches.
- Force-push.
- Rewrite shared Git history.
- Modify repository security settings.
- Publish a release.

Never claim a push, PR, or merge succeeded without verifying the result.

---

# 7. TARGET SYSTEM ARCHITECTURE

The architecture must be based on the actual existing codebase.

The following is the desired logical architecture.

```text
Fisch Macro
│
├── Presentation Layer
│   ├── Dashboard
│   ├── Macro Controls
│   ├── Settings
│   ├── Profiles
│   ├── Logs
│   └── Theme System
│
├── Application Layer
│   ├── Application Controller
│   ├── Workflow Manager
│   ├── Hotkey Manager
│   └── Lifecycle Manager
│
├── Core Layer
│   ├── Macro Engine
│   ├── State Manager
│   ├── Event Bus
│   └── Error Handler
│
├── Automation Layer
│   ├── Fishing Workflow
│   ├── Casting
│   ├── Waiting
│   ├── Bite Detection
│   ├── Reeling
│   └── Scheduler
│
├── Vision Layer
│   ├── Screen Capture
│   ├── Image Detection
│   └── Recognition
│
├── Input Layer
│   ├── Mouse Controller
│   ├── Keyboard Controller
│   └── Input Manager
│
├── Data Layer
│   ├── Database
│   ├── Repository
│   ├── Models
│   └── Configuration
│
└── Monitoring Layer
    ├── Logger
    ├── Diagnostics
    └── Performance Monitoring
```

Do not create unnecessary abstractions.

Use the existing programming language and framework unless a documented technical reason justifies changing them.

---

# 8. MODULE RESPONSIBILITIES

## 8.1 Presentation Layer

Responsibilities:

- Modern Windows desktop interface.
- Dashboard.
- Macro controls.
- Settings.
- User profiles.
- Logs and status.
- Application notifications.

Requirements:

- Keep UI code separate from automation logic.
- Never block the UI thread with long-running operations.
- Display accurate runtime states.
- Handle errors clearly.
- Avoid unnecessary rendering and background work.

## 8.2 Application Layer

Responsibilities:

- Application lifecycle.
- Application controller.
- Workflow coordination.
- Hotkey management.
- Communication between UI and Core.

The UI must communicate with application services instead of directly implementing automation logic.

## 8.3 Core Layer

Responsibilities:

- Macro Engine.
- State Manager.
- Event Bus.
- Error Handler.
- Task Lifecycle.

Expected macro states:

```text
IDLE
STARTING
RUNNING
PAUSED
STOPPING
STOPPED
ERROR
```

State transitions must be predictable and thread-safe.

Prevent duplicate automation tasks.

## 8.4 Automation Layer

Responsibilities:

- Fishing automation.
- Casting.
- Waiting for events.
- Bite detection.
- Reeling.
- Repeating workflows.
- Task scheduling.
- Failure recovery.

Requirements:

- Break complex workflows into independently testable operations.
- Preserve existing timing behavior unless testing justifies changing it.
- Handle unexpected conditions safely.
- Support cancellation and emergency stop.

## 8.5 Vision Layer

Responsibilities:

- Screen capture.
- Image processing.
- UI element detection.
- Fishing event recognition.
- Detection timeout handling.

Requirements:

- Avoid unnecessary repeated screen captures.
- Keep detection independent of GUI.
- Handle missing visual elements.
- Provide diagnostic information.
- Test recognition logic independently.

## 8.6 Input Layer

Responsibilities:

- Mouse control.
- Keyboard control.
- Input timing.
- Input coordination.
- Input cleanup.

Requirements:

- Prevent conflicting simultaneous input operations.
- Release held keys and buttons when stopping.
- Support emergency stop.
- Ensure safe application shutdown.

Do not implement anti-cheat evasion, exploit injection, unauthorized memory manipulation, or security bypasses.

## 8.7 Data Layer

Responsibilities:

- Database access.
- Data models.
- Repository layer.
- Configuration persistence.
- Profile storage.
- Data validation.

Requirements:

- Preserve existing user data.
- Maintain data integrity.
- Validate inputs.
- Avoid unnecessary database operations.
- Document schema changes.
- Provide migration procedures when necessary.

Do not introduce a remote database or online account system unless the project requirements explicitly authorize it.

## 8.8 Monitoring Layer

Responsibilities:

- Logging.
- Error reporting.
- Runtime diagnostics.
- Performance measurements.
- Execution history.

Never log passwords, authentication tokens, or sensitive user information.

---

# 9. PRESERVE EXISTING FUNCTIONALITY

Before modifying a feature:

1. Locate its current implementation.
2. Understand its dependencies.
3. Identify how it is used.
4. Inspect associated settings and stored data.
5. Add or update tests.
6. Refactor incrementally.
7. Verify existing behavior.

Never:

- Delete working features without approval.
- Replace algorithms without justification.
- Discard user configurations.
- Change behavior silently.
- Introduce unnecessary dependencies.
- Rewrite unrelated modules.

If a feature must be replaced:

- Explain why.
- Identify affected modules.
- Document compatibility implications.
- Provide a migration path.
- Obtain approval if existing functionality or user data will be removed.

---

# 10. MODERN UI REQUIREMENTS

The interface should feel like a polished modern Windows application.

Design priorities:

- Clean layout.
- Consistent typography.
- Consistent spacing.
- Clear navigation.
- Modern controls.
- Responsive interactions.
- Clear application status.
- Organized settings.
- Useful diagnostics.
- Appropriate light/dark theme support when practical.

Avoid:

- Excessive animations.
- Unnecessary visual effects.
- Heavy background processes.
- Confusing navigation.
- UI components that block automation.
- Direct coupling between UI and Macro Engine.

Keep the existing UI framework when technically suitable.

---

# 11. RELIABILITY AND SAFETY

The automation system must provide:

- Start.
- Stop.
- Pause.
- Resume.
- Emergency stop.
- Timeout handling.
- Exception handling.
- Safe cancellation.
- Input cleanup.
- Duplicate-task prevention.
- Safe shutdown.

Emergency stop must take priority over normal automation.

A failed automation task must not continue sending unintended input.

All long-running tasks must have a controlled lifecycle.

---

# 12. PERFORMANCE REQUIREMENTS

Optimize for stable Windows desktop operation.

Priorities:

1. Low idle CPU usage.
2. Reasonable memory usage.
3. Responsive GUI.
4. Efficient screen capture.
5. Efficient image processing.
6. Controlled background tasks.
7. No unnecessary polling or busy loops.

Measure performance before and after significant optimization.

Do not sacrifice reliability for insignificant performance improvements.

---

# 13. TESTING REQUIREMENTS

Testing is mandatory.

Never claim completion based only on successful code generation.

## Unit Tests

Test:

- Macro Engine.
- State Manager.
- Event Bus.
- Configuration validation.
- Fishing workflow.
- Detection logic.
- Input coordination.
- Database operations.
- Error handling.

## Integration Tests

Test:

- UI and Application Layer.
- Application Layer and Core.
- Core and Automation.
- Automation and Vision.
- Automation and Input.
- GUI and Data Layer.
- Configuration persistence.

## Regression Tests

Verify all existing working features after refactoring.

## Performance Tests

Measure:

- Idle CPU usage.
- Running CPU usage.
- Memory usage.
- UI responsiveness.
- Screen capture overhead.
- Detection processing time.

## Windows Manual Tests

When a Windows environment is available:

- Launch the application.
- Verify GUI behavior.
- Start and stop automation.
- Pause and resume.
- Test emergency stop.
- Verify configuration persistence.
- Test failure recovery.
- Test application shutdown.
- Verify Windows build.

If development is performed outside Windows:

- Run all available automated tests.
- Clearly identify Windows-only tests.
- Do not claim unperformed Windows tests passed.

## Failure Handling

When a test fails:

1. Identify the cause.
2. Determine whether it was introduced by the current change.
3. Fix failures caused by your changes.
4. Re-run affected tests.
5. Run relevant regression tests.
6. Document unrelated pre-existing failures.

---

# 14. CI AND PULL REQUEST REQUIREMENTS

Every integration Pull Request must include:

- Purpose of the change.
- Summary of modifications.
- Affected modules.
- Tests executed.
- Test results.
- Screenshots for significant UI changes when useful.
- Known issues.
- Documentation changes.

Before integration:

1. Review the complete diff.
2. Confirm no unrelated files were changed.
3. Verify tests.
4. Check CI status.
5. Resolve review comments.
6. Obtain approval from relevant subsystem owners.

Do not integrate failing or unverified work.

A Pull Request is not permission to merge into `main`.

---

# 15. DOCUMENTATION REQUIREMENTS

Maintain comprehensive documentation.

Required files:

```text
README.md
AGENT.md

docs/
├── PROJECT_AUDIT.md
├── ARCHITECTURE.md
├── TEAM_ROLES.md
├── BRANCH_STRATEGY.md
├── FEATURES.md
├── ROADMAP.md
├── DEVELOPMENT.md
├── TESTING.md
├── CHANGELOG.md
└── USER_GUIDE.md

HANDOFF.md
PHASE-LOG.md
```

## README.md

Must contain:

- Project overview.
- Features.
- Requirements.
- Installation.
- Usage.
- Development setup.
- Build instructions.

## PROJECT_AUDIT.md

Must contain:

- Existing architecture.
- Existing functionality.
- Current implementation status.
- Technical debt.
- Risks.
- Recommended improvements.

## ARCHITECTURE.md

Must describe:

- System architecture.
- Module responsibilities.
- Module dependencies.
- Data flow.
- State transitions.
- Integration interfaces.

## FEATURES.md

Track features using:

- Working.
- Partially Working.
- Broken.
- Missing.
- Needs Verification.

## ROADMAP.md

Track:

- Development phases.
- Current phase.
- Completed work.
- Remaining work.
- Blockers.

## HANDOFF.md

Every completed task or handoff must include:

- Current project state.
- Current branch.
- Latest commit.
- Files changed.
- Completed tasks.
- Tests executed.
- Known issues.
- Next recommended action.

Another agent must be able to continue work without repeating the entire investigation.

## PHASE-LOG.md

Record:

- Phase.
- Date.
- Responsible member.
- Task description.
- Changes.
- Test results.
- Commit reference.
- Current status.

Documentation must describe actual implementation, not planned functionality as if it already exists.

---

# 16. DEVELOPMENT PHASES

Follow these phases in order.

Adjust implementation details according to the initial repository audit.

## Phase 0 — Repository Audit

- Clone repository.
- Inspect code.
- Inspect dependencies.
- Identify existing features.
- Run baseline tests.
- Document architecture.
- Identify risks.

Deliverable:

`docs/PROJECT_AUDIT.md`

## Phase 1 — Architecture and Team Setup

- Design target architecture.
- Define module responsibilities.
- Establish team ownership.
- Establish branch strategy.
- Define shared interfaces.
- Prepare project roadmap.

Deliverables:

- `docs/ARCHITECTURE.md`
- `docs/TEAM_ROLES.md`
- `docs/BRANCH_STRATEGY.md`
- `docs/ROADMAP.md`

## Phase 2 — Core Refactoring

- Improve application lifecycle.
- Separate UI and Core.
- Improve state management.
- Improve event handling.
- Implement safe task cancellation.

## Phase 3 — Fishing Automation

- Audit existing fishing algorithms.
- Preserve working behavior.
- Separate fishing operations.
- Improve workflow reliability.
- Implement failure recovery.
- Add regression tests.

## Phase 4 — Vision and Input

- Improve screen capture.
- Improve detection.
- Improve input coordination.
- Implement emergency stop.
- Test input cleanup.
- Test detection independently.

## Phase 5 — Database and Data Layer

- Audit existing persistence.
- Improve data models.
- Improve configuration storage.
- Implement safe migrations when required.
- Test data integrity.
- Coordinate GUI and backend integration.

Do not introduce unnecessary remote infrastructure.

## Phase 6 — Modern GUI

- Implement the agreed design.
- Improve dashboard.
- Improve navigation.
- Integrate settings and profiles.
- Connect GUI to application services.
- Verify responsive behavior.

## Phase 7 — Integration

- Integrate all modules.
- Verify complete workflows.
- Resolve integration problems.
- Run regression tests.
- Verify configuration compatibility.

## Phase 8 — Full Testing and Optimization

- Unit testing.
- Integration testing.
- Regression testing.
- Performance testing.
- Windows manual testing.
- Bug fixing.
- Final documentation review.

## Phase 9 — Release Preparation

- Verify application build.
- Verify dependencies.
- Update README.
- Update CHANGELOG.
- Prepare user documentation.
- Prepare release notes.
- Report remaining limitations.

Do not skip phases to reach release faster.

---

# 17. AUTONOMY AND APPROVAL

You have high autonomy for routine development.

You may independently:

- Inspect the repository.
- Plan implementation.
- Refactor code.
- Fix bugs.
- Improve performance.
- Add tests.
- Update documentation.
- Create local branches.
- Commit local changes.
- Push to authorized team/task branches.
- Open Pull Requests targeting `develop`.
- Review CI results.

Request explicit approval before:

- Deleting user data.
- Removing major functionality.
- Replacing the core framework.
- Introducing major irreversible architectural changes.
- Changing repository security settings.
- Deleting remote branches.
- Force-pushing.
- Rewriting shared history.
- Merging into `main`.
- Publishing a release.

Do not ask for permission for every routine coding operation.

Investigate and make safe, reversible technical decisions independently.

---

# 18. TASK COMPLETION REPORT

At the end of each task or phase, report:

1. Responsible team member.
2. Task description.
3. Branch name.
4. Current commit.
5. Files inspected.
6. Files changed.
7. Features preserved.
8. New functionality.
9. Tests executed.
10. Actual test results.
11. CI status.
12. Known issues.
13. Documentation updated.
14. Remaining work.
15. Recommended next action.

Use only these status labels:

- COMPLETED
- PARTIALLY COMPLETED
- BLOCKED
- NOT TESTED
- FAILED

Never report unverified work as completed.

Always update:

- `HANDOFF.md`
- `PHASE-LOG.md`
- `docs/ROADMAP.md`

---

# 19. NON-NEGOTIABLE RULES

1. Read this file before starting work.
2. Clone and inspect the existing repository before implementation.
3. Never guess the architecture, framework, or test results.
4. Never work directly on `main`.
5. Never overwrite another team member's work.
6. Work autonomously on routine development tasks.
7. Always test your own implementation.
8. Always investigate and fix failures caused by your changes.
9. Always review the final diff.
10. Always maintain comprehensive documentation.
11. Always update the roadmap and project status.
12. Always update `HANDOFF.md` and `PHASE-LOG.md`.
13. Commit and push to appropriate team/task branches when safe.
14. Create Pull Requests when the integration workflow requires them.
15. Check CI results before integration.
16. Never merge into `main` without explicit approval.
17. Never force-push or rewrite shared history without explicit approval.
18. Never expose credentials or compromise user data.
19. Never claim that work, tests, builds, or Git operations succeeded without evidence.
20. Preserve enough project knowledge for another agent to continue immediately.

---

# 20. FINAL DEVELOPMENT PRINCIPLES

Always prioritize:

1. Existing functionality preservation.
2. Automation reliability.
3. Application stability.
4. Team collaboration.
5. Clear module ownership.
6. Maintainable architecture.
7. Modern user experience.
8. Efficient resource usage.
9. Comprehensive testing.
10. Accurate documentation.

The goal is to improve Fisch Macro without unnecessarily destroying or replacing what already works.

Every change must be understandable, testable, documented, and safe to integrate.

**Build incrementally. Test continuously. Collaborate clearly. Preserve existing functionality. Never compromise project stability for speed.**
