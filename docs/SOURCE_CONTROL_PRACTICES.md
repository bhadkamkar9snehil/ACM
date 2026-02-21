"""
ACM Source Control and Release Management Practices

This document defines professional source control practices for ACM, including branching strategy,
commit conventions, release management, and version management for all future development.

Last Updated: 2025-12-04
Version: v9.0.0
"""

# ============================================================================
# 1. BRANCHING STRATEGY (Git Flow Variant)
# ============================================================================

BRANCHING_STRATEGY = """
ACM uses a modified Git Flow branching model:

PRODUCTION BRANCHES:
  main
    - Always production-ready code
    - Tagged with semantic version (v9.0.0, v9.0.1, etc.)
    - Protected: requires PR review + passing tests before merge
    - Merges only from release branches or hotfix branches
    - Never force-push; always preserve history

FEATURE/DEVELOPMENT BRANCHES:
  feature/<feature-name>
    - New features, enhancements, non-urgent improvements
    - Branched from: main
    - Example: feature/detector-label-consistency, feature/sql-optimization
    - Merge back to: main via PR with --no-ff
    - Lifecycle: Delete after merge

  fix/<bug-name>
    - Bug fixes, critical patches, operational fixes
    - Branched from: main
    - Example: fix/pca-metrics-calculation, fix/run-completion-tracking
    - Merge back to: main via PR with --no-ff
    - Lifecycle: Delete after merge

  refactor/<component>
    - Code refactoring, cleanup, architectural improvements
    - Branched from: main
    - Example: refactor/output-manager, refactor/detector-heads
    - Merge back to: main via PR with --no-ff
    - Lifecycle: Delete after merge

  docs/<topic>
    - Documentation updates, guides, handbooks
    - Branched from: main
    - Example: docs/release-notes, docs/operator-guide
    - Merge back to: main directly (no PR required for minor updates)
    - Lifecycle: Delete after merge

  experimental/<experiment-id>
    - Exploratory work, prototypes, research branches
    - Branched from: main or feature branches
    - Example: experimental/new-detector-approach
    - Merge: Only if experiment successful; otherwise delete
    - Lifecycle: Delete when experiment concluded

NAMING CONVENTIONS:
  ✓ lowercase with hyphens: feature/detector-labels, fix/run-completion
  ✗ CamelCase: feature/DetectorLabels (avoid)
  ✗ underscores: feature/detector_labels (avoid)
  ✗ vague names: feature/update, fix/bug (avoid)

BRANCH PROTECTION RULES FOR MAIN:
  - Require PR review from 1+ maintainer
  - Require all tests to pass
  - Require CI/CD pipeline success (when available)
  - Require branch to be up to date with main
  - Dismiss stale PR approvals when new commits pushed
  - Allow force pushes: only for maintainers, only in rare cases
"""

# ============================================================================
# 2. COMMIT MESSAGE CONVENTIONS
# ============================================================================

COMMIT_CONVENTIONS = """
ACM uses conventional commits format for clear, searchable history:

FORMAT:
  <type>(<scope>): <subject>
  
  <body>
  
  <footer>

TYPES (required):
  feat:      New feature, detector, or capability (minor version bump)
  fix:       Bug fix or issue resolution (patch version bump)
  refactor:  Code restructuring without behavior change (patch version bump)
  perf:      Performance optimization (patch version bump)
  test:      Test additions, fixes, coverage improvements
  docs:      Documentation updates (README, guides, comments)
  chore:     Build, dependencies, tooling (not user-facing)
  ci:        CI/CD pipeline changes
  revert:    Revert a previous commit

SCOPE (optional but recommended):
  Indicates which component/module is affected:
    output-manager, detector-labels, database, sql-integration, feature-engineering,
    fusion, episodes, regimes, drift, forecasting, rul-engine, versioning, etc.

SUBJECT (required):
  - Imperative mood: "add" not "added" or "adds"
  - Lowercase first letter
  - No period at the end
  - Max 50 characters (headline style)
  - Specific and descriptive

BODY (optional but recommended for non-trivial commits):
  - Wrap at 72 characters
  - Explain WHAT changed and WHY, not HOW
  - Reference related issues/PRs: "Fixes #123", "Related to #456"
  - Use bullet points for multiple changes
  - Separate from subject with blank line

FOOTER (optional):
  - Reference issue tracker: "Closes #123"
  - Breaking changes: "BREAKING CHANGE: description"
  - Co-authors: "Co-authored-by: Name <email@example.com>"

EXAMPLES:

  GOOD:
    feat(detector-labels): standardize detector label format across outputs
    
    - Implement get_detector_label() utility for consistent formatting
    - Update extract_dominant_sensor() to preserve full labels
    - Apply changes to ACM_EpisodeDiagnostics table
    - Update Grafana dashboards to use standardized labels
    - Add validation tests for label consistency
    
    Fixes #CRIT-04
    Tested against: 26 production runs

  GOOD:
    fix(run-completion): ensure all runs have CompletedAt timestamp
    
    Mark 4 incomplete runs with NOOP status and zero duration.
    Fixes timestamp ordering issues in dashboards.
    
    Closes #DATA-12

  GOOD:
    refactor(output-manager): extract culprit processing to separate function
    
    No behavior change. Improves maintainability and testability.
    Preparation for enhanced culprit formatting in v9.1.

  BAD:
    Update stuff
    (too vague, no type, no scope)

  BAD:
    feat: Add new feature
    (no scope, not specific)

  BAD:
    FEAT(OutputManager): STANDARDIZE DETECTOR LABEL FORMAT ACROSS OUTPUTS
    (uppercase, too long, unclear)
"""

# ============================================================================
# 3. VERSION MANAGEMENT (Semantic Versioning)
# ============================================================================

VERSION_MANAGEMENT = """
ACM uses Semantic Versioning (MAJOR.MINOR.PATCH):

FORMAT: MAJOR.MINOR.PATCH[-PRERELEASE][+BUILD]
  Example: 9.0.0, 9.1.0, 9.0.1, 9.1.0-rc1, 9.0.0-beta.1

MAJOR VERSION (X._._ → X+1.0.0):
  - Breaking changes in API, database schema, or functionality
  - Backward incompatibility with previous version
  - Example: v8→v9 (detector label format change, database cleanup)
  - Happens: Rarely, planned in advance

MINOR VERSION (_.X._ → _.X+1.0):
  - New features or enhancements (backward compatible)
  - New detectors, algorithms, or capabilities added
  - Configuration enhancements
  - Performance improvements
  - Example: v9.0→v9.1 (new detector, enhanced forecasting)
  - Happens: 2-4 times per development cycle

PATCH VERSION (_._.X → _._.X+1):
  - Bug fixes and patches (backward compatible)
  - Minor improvements and refinements
  - Documentation updates
  - Performance tweaks
  - Example: v9.0.0→v9.0.1 (fix edge case in calibration)
  - Happens: As needed for hotfixes

PRE-RELEASE VERSIONS:
  Format: X.Y.Z-<identifier>
  Examples: 9.0.0-rc1 (release candidate), 9.0.0-beta.1, 9.0.0-alpha
  Usage: Testing phases before stable release
  Lifecycle: Delete after release; don't accumulate old pre-releases

VERSION FILE LOCATION:
  utils/version.py (single source of truth)
    __version__ = "9.0.0"
    __version_date__ = "2025-12-04"
    VERSION_MAJOR, VERSION_MINOR, VERSION_PATCH (parsed from above)

INCREMENTING VERSION:
  1. Update utils/version.py with new version number and date
  2. Update RELEASE_NOTES in utils/version.py
  3. Commit: "chore(version): bump to v9.1.0"
  4. Tag: git tag -a v9.1.0 -m "Version 9.1.0 - <short description>"
  5. Push: git push origin main v9.1.0

VERSION CHECK IN CODE:
  from utils.version import get_version_string, is_compatible
  
  # Log version at startup
  logger.info(f"Starting ACM {get_version_string()}")
  
  # Check compatibility
  if not is_compatible("9.0.0"):
      raise RuntimeError("Incompatible ACM version")

VERSION COMPATIBILITY:
  - Same MAJOR version: fully compatible
  - Different MAJOR version: incompatible, migration required
  - MINOR version: newer is always compatible with older
  - PATCH version: bug fixes, always upgrade available
"""

# ============================================================================
# 4. RELEASE MANAGEMENT
# ============================================================================

RELEASE_MANAGEMENT = """
Professional release management process for ACM:

RELEASE CYCLE:
  1. Feature Development (2-4 weeks)
     - Work on feature/*, fix/*, refactor/* branches
     - Regular PRs to main
     - All tests passing
     - Code reviews complete

  2. Release Branch Creation
     - When ready for release: git checkout -b release/v9.1.0
     - Update version in utils/version.py
     - Update CHANGELOG.md (if exists)
     - Final testing and bugfixes only on release branch
     - Commit: "chore(release): prepare v9.1.0"

  3. Release Tagging
     - Tag release: git tag -a v9.1.0 -m "Release v9.1.0 - <notes>"
     - Push tag: git push origin v9.1.0
     - Tag message includes comprehensive release notes (see example below)

  4. Merge to Main
     - Merge release branch to main: git merge --no-ff release/v9.1.0
     - Commit message: "Merge release v9.1.0"
     - Push: git push origin main

  5. Archive Release Branch
     - Delete local: git branch -d release/v9.1.0
     - Delete remote: git push origin --delete release/v9.1.0

HOTFIX PROCESS (for production issues):
  1. Branch from main: git checkout -b hotfix/v9.0.1
  2. Fix issue and test thoroughly
  3. Update version to v9.0.1
  4. Commit: "fix(hotfix): description" + "chore(version): bump to v9.0.1"
  5. Tag: git tag -a v9.0.1 -m "Hotfix v9.0.1 - critical fix for X"
  6. Merge to main: git merge --no-ff hotfix/v9.0.1
  7. Push: git push origin main v9.0.1
  8. Delete hotfix branch

GIT TAG STRUCTURE:
  Annotated Tags (recommended):
    git tag -a v9.0.0 -m "Release v9.0.0 - description"
    Contains: tagger, date, message (stored in Git database)

  Never use lightweight tags for releases:
    git tag v9.0.0  # Avoid this for releases
    Insufficient metadata and history

TAG MESSAGE FORMAT:
  v9.0.0 - Production Release

  HIGHLIGHTS:
    - Detector label standardization (CRIT-04)
    - Database cleanup (85→79 tables)
    - Equipment name standardization
    - Comprehensive testing suite (30+ tests)

  BREAKING CHANGES:
    None - fully backward compatible

  TESTING:
    All 30+ Python tests passing ✓
    All 8 SQL validation checks passing ✓

  DEPLOYMENT:
    Production-ready. Deploy to environment.

  ISSUES FIXED:
    - Fixes CRIT-04: Detector label inconsistency
    - Fixes DATA-12: Run completion tracking
    - Fixes SCHEMA-08: Backup table cleanup

  NEXT VERSION:
    v9.0.1: Scheduled for hotfixes if needed
    v9.1.0: Next feature release (planned)

DEPLOYMENT FROM TAG:
  # Always deploy from specific tag, never from branch
  git checkout v9.0.0
  # ... deploy to production environment
  # ... validate deployment
  # ... return to main
  git checkout main

VERSIONING IN OUTPUTS:
  All major outputs should include version:
    - SQL run logs: ACM_Runs.ACMVersion
    - Output CSV headers: # Generated by ACM v9.0.0
    - Log files: [ACM v9.0.0] Starting run...
    - Grafana dashboards: Footer showing ACM version
    - API responses: "version": "9.0.0"
"""

# ============================================================================
# 5. PULL REQUEST PROCESS
# ============================================================================

PR_PROCESS = """
Standard PR process for all non-trivial changes:

PR CREATION:
  1. Ensure branch is up to date: git pull origin main
  2. Push branch: git push origin feature/detector-labels
  3. Create PR on GitHub:
     - Title: Use conventional commit format (feat/fix/refactor)
     - Description: Explain what, why, and how
     - Link related issues: "Fixes #123"
     - Select reviewers (at least 1)
     - Assign to yourself

PR DESCRIPTION TEMPLATE:
  ## Description
  Brief summary of what this PR does.

  ## Related Issues
  Fixes #ISSUE_NUMBER
  Related to #ISSUE_NUMBER

  ## Changes
  - Change 1
  - Change 2
  - Change 3

  ## Testing
  - How was this tested?
  - Edge cases considered?
  - Test results: all passing

  ## Screenshots (if applicable)
  Before/after or dashboard changes

  ## Checklist
  - [ ] Code follows style guidelines
  - [ ] Tests added/updated
  - [ ] Documentation updated
  - [ ] All tests passing
  - [ ] No breaking changes (or documented)

PR REVIEW REQUIREMENTS:
  ✓ At least 1 approval from maintainer
  ✓ All tests passing (CI/CD green)
  ✓ Branch up to date with main
  ✓ No conflicts
  ✓ Code review complete

MERGE TO MAIN:
  git checkout main
  git pull origin main
  git merge --no-ff feature/detector-labels
  git commit -m "Merge: Detector label standardization"
  git push origin main

  (OR use GitHub UI: "Merge pull request" with --no-ff)

POST-MERGE CLEANUP:
  git branch -d feature/detector-labels
  git push origin --delete feature/detector-labels
"""

# ============================================================================
# 6. TESTING & VALIDATION BEFORE MERGE
# ============================================================================

TESTING_CHECKLIST = """
Required testing before merging any PR to main:

UNIT TESTS:
  [ ] All existing tests pass: pytest tests/ -v
  [ ] New tests added for features: pytest tests/test_*.py -v
  [ ] Coverage not decreased: pytest tests/ --cov=core
  [ ] No test warnings or deprecations

SQL VALIDATION:
  [ ] Schema consistency: python scripts/sql/export_schema_doc.py
  [ ] Data integrity: sqlcmd -E -d ACM -i scripts/sql/validate_p0_fixes.sql
  [ ] Stored procedures: Test SP modifications manually
  [ ] Database performance: Monitor query times

CODE QUALITY:
  [ ] No lint errors: ruff check core/ utils/
  [ ] Type checking: mypy core/ utils/ (if applicable)
  [ ] No hardcoded credentials: grep -r "password" scripts/
  [ ] Comments and docstrings: All public functions documented

INTEGRATION TESTS:
  [ ] File mode still works: python -m core.acm --equip TEST_EQUIP
  [ ] SQL mode works: python scripts/sql_batch_runner.py --equip GAS_TURBINE --tick-minutes 1440
  [ ] Output files generated correctly
  [ ] Database entries created properly

PERFORMANCE:
  [ ] No new N+1 queries
  [ ] Response times acceptable
  [ ] Memory usage within bounds
  [ ] No data loading timeouts

BACKWARD COMPATIBILITY:
  [ ] Existing data still loads
  [ ] Old configurations still work
  [ ] No breaking API changes
  [ ] Database migrations tested (if applicable)

DOCUMENTATION:
  [ ] README updated if needed
  [ ] Inline code comments added
  [ ] Docstrings complete
  [ ] CHANGELOG.md updated
"""

# ============================================================================
# 7. EXAMPLE WORKFLOWS
# ============================================================================

EXAMPLE_WORKFLOWS = """
COMMON WORKFLOWS:

1. START NEW FEATURE:
   git checkout main
   git pull origin main
   git checkout -b feature/new-detector-type
   # ... make changes, commit
   git commit -m "feat(detectors): add gradient boosting detector"
   git push origin feature/new-detector-type
   # Create PR on GitHub

2. FIX A BUG:
   git checkout main
   git pull origin main
   git checkout -b fix/calibration-edge-case
   # ... make changes, test
   git commit -m "fix(calibration): handle empty feature sets"
   git push origin fix/calibration-edge-case
   # Create PR, get review, merge

3. CREATE RELEASE:
   # Update version
   vi utils/version.py  # Change __version__ = "9.1.0"
   git add utils/version.py
   git commit -m "chore(version): bump to v9.1.0"
   # Tag release
   git tag -a v9.1.0 -m "Release v9.1.0 - new detectors and fixes"
   git push origin main v9.1.0
   # Deploy using tag
   git checkout v9.1.0
   # ... deploy to production

4. HOTFIX CRITICAL BUG:
   git checkout main
   git pull origin main
   git checkout -b hotfix/v9.0.1
   # ... fix issue
   git commit -m "fix(critical): fix detector crash on NaN"
   vi utils/version.py  # Change __version__ = "9.0.1"
   git commit -m "chore(version): bump to v9.0.1"
   git tag -a v9.0.1 -m "Hotfix v9.0.1 - critical crash fix"
   git push origin main v9.0.1
   # Deploy hotfix immediately
"""

# ============================================================================
# 8. TOOLS & HELPERS
# ============================================================================

RECOMMENDED_TOOLS = """
GIT CONFIGURATION:
  # Set up git user
  git config user.name "Your Name"
  git config user.email "your.email@company.com"

  # Configure signing (optional but recommended)
  git config commit.gpgsign false  # Or true if you use GPG keys

  # Useful aliases
  git config --global alias.co checkout
  git config --global alias.br branch
  git config --global alias.ci commit
  git config --global alias.st status
  git config --global alias.unstage 'reset HEAD --'
  git config --global alias.last 'log -1 HEAD'

USEFUL GIT COMMANDS:
  git log --oneline -10                    # View recent commits
  git log --graph --oneline --all           # Visualize branching
  git branch -vv                            # Show branch tracking
  git diff main feature/branch-name        # Compare branches
  git cherry-pick <commit-hash>            # Apply specific commit
  git rebase -i HEAD~3                     # Reorder last 3 commits
  git tag -l                               # List all tags
  git show v9.0.0                          # Show tag info

LINTING & TESTING:
  pytest tests/ -v                         # Run all tests
  pytest tests/test_specific.py -v         # Run specific test file
  pytest tests/ --cov=core                 # Coverage report
  ruff check core/                         # Lint code
  mypy core/                               # Type checking
"""

# ============================================================================
# SUMMARY
# ============================================================================

SUMMARY = """
ACM PROFESSIONAL DEVELOPMENT PRACTICES SUMMARY:

BRANCHING:
  feature/* → fix/* → refactor/* → docs/* → main (protected)

COMMITS:
  type(scope): subject + detailed body + footer

VERSIONING:
  utils/version.py → MAJOR.MINOR.PATCH

RELEASES:
  Branch → Update version → Tag → Merge → Deploy

TESTING:
  Unit + SQL + Integration + Performance + Compatibility

CODE REVIEW:
  PR → Review → Approve → Merge with --no-ff → Deploy

This ensures:
  ✓ Clear history and traceability
  ✓ Easy rollback and debugging
  ✓ Professional release management
  ✓ Quality gates and testing
  ✓ Semantic versioning across all systems
  ✓ Collaboration and knowledge sharing
"""
