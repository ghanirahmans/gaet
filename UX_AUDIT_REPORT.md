# CLI UX Consistency Audit Report
## gaet v1.0.0

**Baseline Pattern** (`gaet get` & `gaet set`):
- Clear title box: `box_title(f"{NAME} get")`
- Consistent output formatting: `status_ok()`, `status_warn()`, `status_info()`
- Summary at end with `echo()` spacing
- Good error handling with `die()`
- Logical flow and helpful guidance

---

## ISSUES FOUND

### 1. **CRITICAL: cmd_check — Missing Box Title**
**File**: `gaet.py:1213-1218`
- ✗ Has `box_title()` inside `cmd_check_inner()` (line 1217) but not at top level
- ✗ Creates redundant title rendering if function is called multiple times
- **Impact**: Confusing when `cmd_check` calls `cmd_check_inner()` - title appears at wrong level
- **Fix**: Move title to `cmd_check()` function wrapper level

### 2. **CRITICAL: cmd_status — Incomplete Output Summary**
**File**: `gaet.py:1221-1413`
- ✗ Missing `box_title()` wrapper at start of output section
- ✗ No closing summary line (compare with `print_push_summary()`)
- ✗ Inconsistent spacing: Some `box_section()` calls without final spacing
- ✗ Output ends abruptly after auto-backup status (line 1413)
- **Impact**: User can't tell when command completes
- **Fix**: Add final `echo()` and summary message

### 3. **CRITICAL: cmd_push — Inconsistent Dry-Run Output**
**File**: `gaet.py:1553-1658`
- ✗ Dry-run has `status_arrow()` but actual push doesn't use consistent status formatting
- ✗ No final summary for dry-run (compare with actual run: `print_push_summary()`)
- ✗ Mixing emoji placement: `  {C}📦{NC}` vs `  {C}☁️{NC}` (inconsistent spacing)
- **Impact**: Dry-run looks unfinished
- **Fix**: Unify status indicators and add closing summary

### 4. **CRITICAL: cmd_fetch — Missing Final Summary Box**
**File**: `gaet.py:1661-1763`
- ✗ Lacks closing `box_section()` or summary like `print_push_summary()`
- ✗ Output ends with individual echo (line 1760) instead of clean summary
- ✗ No retention cleanup confirmation (unlike `cmd_push`)
- **Impact**: Command feels incomplete, user doesn't see full status
- **Fix**: Add proper closing with `print_sync_summary()` or custom summary

### 5. **MAJOR: cmd_init — Language Mixing & Unclear Help**
**File**: `gaet.py:845-1047`
- ✗ Mixing Indonesian and English throughout (e.g., "tidak ditemukan" vs "OK")
- ✗ No docstring with usage examples (only: "Interactive setup wizard")
- ✗ Error message language inconsistent: Line 859 uses Indonesian `tidak dikenal`
- ✗ Emoji usage inconsistent: `💾` vs `📋` with varying emoji-to-text spacing
- ✗ No clear "what happens next" guidance at end
- **Impact**: Confusing UX, hard to follow for non-Indonesian speakers
- **Fix**: Standardize language (English preferred for CLI), add clear guidance

### 6. **MAJOR: cmd_push_cron — No Output Formatting**
**File**: `gaet.py:1766-1817`
- ✗ No `box_title()` - cron job intentionally has no terminal output
- ✗ Only uses `cronlog()` which writes to file only, not console
- ✗ No way to preview what cron will do (no dry-run equivalent)
- ✗ Missing step-by-step progress indicators (compare with `cmd_push`)
- **Impact**: User can't see what cron does, only logs after-the-fact
- **Limitation**: By design (cron shouldn't print to terminal), but document it

### 7. **MAJOR: cmd_auto_on — Incomplete Error Handling**
**File**: `gaet.py:1820-1846`
- ✗ Validates interval but doesn't check if config exists first
- ✗ `status_info()` on line 1835 used for informational step start (OK)
- ✗ Line 1841 uses `echo()` directly instead of `status_ok()`
- ✗ Fallback on line 1846: `echo()` + `status_fail()` is inconsistent
- **Impact**: Mixed status indicators confuse output flow
- **Fix**: Standardize to use `status_ok()` and `status_fail()` consistently

### 8. **MAJOR: cmd_stop_auto — No Closing Summary**
**File**: `gaet.py:1849-1885`
- ✗ Multiple `status_ok()` calls without grouping summary
- ✗ No final `echo()` spacing for clean exit
- ✗ Doesn't confirm what was actually stopped
- **Impact**: User doesn't see clear summary of actions taken
- **Fix**: Add closing summary like `cmd_uninstall`

### 9. **MAJOR: cmd_log — Missing Box Title & Summary**
**File**: `gaet.py:1888-1918`
- ✗ Has `box_title()` (line 1911) ✓ but positioned after metadata echo
- ✓ Uses echo with `{D}│{NC}` for table-like formatting (good)
- ✗ No closing summary or "end of log" indicator
- **Impact**: Unclear when log ends
- **Fix**: Add final status summary

### 10. **MAJOR: cmd_install — Minimal Output & No Help**
**File**: `gaet.py:2055-2073`
- ✗ Delegates to external `scripts.installer` module
- ✗ Docstring only: "Jalankan installer universal" (Indonesian + vague)
- ✗ No error message if import fails (line 2060: generic error message)
- ✗ No summary output after installation
- ✗ Calls `sys.exit()` directly instead of returning
- **Impact**: Can't follow installation progress from main CLI
- **Fix**: Add wrapper output and better error messaging

### 11. **MAJOR: cmd_uninstall — Inconsistent Icon Usage**
**File**: `gaet.py:2076-2226`
- ✓ Generally good structure with sections (lines 2091-2214)
- ✗ Mixes `{G}✓{NC}` and `{G}{ICON_OK}{NC}` (inconsistent)
- ✗ Step indicators use `{C}▸{NC}` (uncommon in other commands)
- ✗ Error messages use `{Y}⚠` instead of `status_warn()`
- ✗ Final summary (lines 2215-2226) uses direct `echo()` instead of `status_info()`
- **Impact**: Visual inconsistency with baseline commands
- **Fix**: Use standard status functions throughout

### 12. **MAJOR: cmd_update — Mixed Output Patterns**
**File**: `gaet.py:2306-2447`
- ✗ Uses `status_info()`, `status_ok()`, `status_warn()` correctly ✓
- ✗ Line 2333: Emoji+Path uses different format: `{C}📁{NC}`
- ✗ Section markers inconsistent: `box_section()` sometimes has no preceding status
- ✗ Line 2346-2348: Shows raw commands in `{D}..{NC}` instead of suggested format
- ✗ Line 2443: Tries to extract version but doesn't verify output format
- ✗ No final summary box showing what changed
- **Impact**: Output feels scattered, not cohesive
- **Fix**: Unify formatting and add final summary

### 13. **MAJOR: cmd_serve — No Confirmation Message**
**File**: `gaet.py:2450-2517`
- ✗ Line 2487-2496: Automatic build without clear user confirmation
- ✗ Line 2508: Uses direct `echo()` + custom formatting instead of structured output
- ✓ Does show URL (line 2509) ✓
- ✗ Line 2517: Failure uses `status_fail()` but success uses `echo()` with `{G}`
- **Impact**: Inconsistent success/failure messaging
- **Fix**: Standardize to `status_ok()` / `status_fail()`

---

## SUMMARY TABLE

| Command | Issue Category | Severity | Status Functions | Box Title | Summary | Error Handling |
|---------|---|---|---|---|---|---|
| `cmd_init` | Language mix, unclear help | MAJOR | ✓ | ✓ | ✓ | ✗ Inconsistent |
| `cmd_check` | Redundant title | CRITICAL | ✓ | ⚠ (wrong level) | ✗ | ✓ |
| `cmd_status` | No closing summary | CRITICAL | ✓ | ✗ | ✗ | ✓ |
| `cmd_push` | Inconsistent dry-run | CRITICAL | ✗ (dry-run) | ✓ | ✓ | ✓ |
| `cmd_fetch` | Missing summary | CRITICAL | ✓ | ✓ | ✗ | ✓ |
| `cmd_push_cron` | Design limitation | MAJOR | N/A | N/A | N/A | ✓ (cronlog) |
| `cmd_auto_on` | Mixed indicators | MAJOR | ⚠ (inconsistent) | ✓ | ✓ | ✗ |
| `cmd_stop_auto` | No summary | MAJOR | ✓ | ✗ | ✗ | ✓ |
| `cmd_log` | No closing indicator | MAJOR | ✓ | ✓ | ✗ | ✓ |
| `cmd_install` | Minimal output | MAJOR | ✗ | ✓ | ✗ | ✗ |
| `cmd_uninstall` | Icon mixing | MAJOR | ⚠ (mixed) | ✓ | ⚠ (direct echo) | ⚠ (mixed) |
| `cmd_update` | Scattered output | MAJOR | ✓ | ✓ | ✗ | ✓ |
| `cmd_serve` | Inconsistent success/fail | MAJOR | ⚠ (mixed) | ✓ | ✗ | ✓ |

---

## RECOMMENDED IMPROVEMENTS

### 🔴 PRIORITY 1: QUICK WINS (Easy, High Impact)

#### 1.1 Fix cmd_status - Add Final Summary (5 min)
**File**: `gaet.py:1413`
```python
# After line 1413, before function ends:
echo()
echo(f"  {D}To view details:{NC}")
echo(f"    {D}gaet status --json{NC}  (machine-readable)")
echo()
```
**Impact**: Clear command completion

#### 1.2 Fix cmd_log - Add End Indicator (2 min)
**File**: `gaet.py:1918`
```python
# After line 1918, add:
echo()
status_info(f"Showing {min(lines, total_filtered)}/{total_filtered} filtered lines")
echo()
```
**Impact**: Clear log ending

#### 1.3 Fix cmd_stop_auto - Add Closing Echo (1 min)
**File**: `gaet.py:1885`
```python
# After line 1885, add:
echo()
```
**Impact**: Proper spacing for clean exit

#### 1.4 Fix cmd_serve - Standardize Success Message (2 min)
**File**: `gaet.py:2508-2509`
```python
# Replace lines 2508-2509:
# OLD:
# echo(f"\n  {G}{ICON_OK}{NC}  {B}Dashboard is running!{NC}")
# echo(f"  {D}{ICON_ARROW}{NC}  http://localhost:{port}")
# NEW:
status_ok(f"Dashboard is running!")
status_info(f"Access at: http://localhost:{port}")
```
**Impact**: Consistent with baseline

#### 1.5 Fix cmd_uninstall - Use status_fail for errors (3 min)
**File**: `gaet.py:2102, 2111, 2115, etc.`
Replace `status_warn()` for actual failures with `status_fail()` for clarity.

---

### 🟡 PRIORITY 2: MEDIUM EFFORT, HIGH IMPACT

#### 2.1 Standardize cmd_auto_on Status Indicators (5 min)
**File**: `gaet.py:1841, 1846`
```python
# Line 1841 - Change echo to status_ok:
status_ok(f"Auto-backup aktif setiap {interval} jam!")

# Line 1846 - Be consistent:
status_warn(f"Di sistem ini, aktifkan auto-backup secara manual.")
```

#### 2.2 Fix cmd_check - Remove Redundant Title (5 min)
**File**: `gaet.py:1213-1218` and `cmd_check_inner()`
- Remove `box_title()` from inside `cmd_check_inner()` 
- Keep only at `cmd_check()` level
- This prevents double-title when called from other places

#### 2.3 Standardize cmd_push Dry-Run (10 min)
**File**: `gaet.py:1564-1575`
```python
# After status lines, add matching summary:
echo()
status_info("Dry-run: No changes will be made")
echo()
```
**Match with cmd_fetch dry-run format.**

#### 2.4 Add Closing Summary to cmd_fetch (5 min)
**File**: `gaet.py:1760`
```python
# After line 1760, add:
echo()
status_info("Next: gaet push  (to sync back)")
echo()
```

#### 2.5 Fix cmd_update Version Check (5 min)
**File**: `gaet.py:2443-2444`
```python
# Replace unreliable version extraction:
try:
    out, _, rc = run_cmd([sys.executable, str(dst), "--version"], timeout=5)
    if rc == 0 and out.strip():
        status_ok(f"Version: {out.strip()}")
    else:
        status_ok("Update complete")
except:
    status_ok("Update complete")
```

---

### 🟠 PRIORITY 3: STRUCTURAL IMPROVEMENTS

#### 3.1 Consolidate Status Output Functions (15 min)
**Create helper in gaet.py**:
```python
def print_command_summary(title: str, details: List[Tuple[str, str]]) -> None:
    """Print consistent command summary."""
    echo()
    box_section("Summary")
    for label, value in details:
        status_arrow(f"{label}: {value}")
    echo()
```

**Use in**: `cmd_status()`, `cmd_fetch()`, `cmd_push()`

#### 3.2 Create Unified Error Handler (10 min)
**Current**: Mix of `die()`, `status_fail()`, direct exceptions
**Proposed**:
```python
def cmd_error(message: str, details: Optional[str] = None) -> None:
    """Consistent error output."""
    echo()
    status_fail(message)
    if details:
        echo(f"  {D}{details}{NC}")
    echo()
    sys.exit(1)
```

#### 3.3 Standardize Emoji Placement (10 min)
**Current inconsistency**:
- `{C}📦{NC}  text` 
- `{C}☁️{NC}   text` (extra space)
- `  {C}💾{NC}  text` (leading space)

**Proposal**: Use `status_arrow()` for all progress steps:
```python
status_arrow(f"Dumping database...")  # Handles spacing
```

#### 3.4 Standardize Docstrings for All Commands (15 min)
**Pattern**:
```python
def cmd_xxx(args: argparse.Namespace) -> None:
    """Short description.
    
    Usage:
      gaet xxx [options]
    
    Outputs: [what will be shown]
    
    Exit codes:
      0 = success
      1 = error
    """
```

---

## EDGE CASES NOT HANDLED

### 1. **cmd_status with invalid psql**
- Line 1225: Assumes `tools["psql"]` exists but doesn't validate
- **Fix**: Add `if tools.get("psql")` check

### 2. **cmd_push with connection timeout**
- No timeout handling for cloud restore (line 1635)
- **Fix**: Add retry logic or clearer timeout message

### 3. **cmd_fetch without cloud database**
- Line 1688: Validates `parsed` but early-returns without summary
- **Fix**: Add summary even for failures

### 4. **cmd_log with empty log file**
- Line 1893-1895: Handles gracefully ✓ but no happy-path message
- **Fix**: Show "no backups yet" instead of silent return

### 5. **cmd_update without .git directory**
- Line 2327-2331: Falls back to download gracefully ✓
- **Issue**: Doesn't show which method is used clearly
- **Fix**: Better messaging at line 2329

### 6. **cmd_serve with Node.js missing**
- Line 2496: Dies with direct message instead of status function
- **Fix**: Use `die()` consistently or `status_fail()`

### 7. **cmd_auto_on with existing cron**
- Line 1840: `scheduler_enable()` may fail silently
- **Fix**: Add clearer error message on line 1846

### 8. **cmd_init with partial database input**
- Lines 895-976: Complex branching but could fail on network
- **Fix**: Add timeout handling for test connection (line 981)

### 9. **cmd_uninstall with permission denied**
- Lines 2127, 2142, 2153: Catches exceptions generically
- **Fix**: More specific error messages (e.g., permission denied vs. not found)

### 10. **cmd_check_inner called multiple times**
- Doesn't track state - prints progress each time
- **Fix**: Cache results if called multiple times in session

---

## MAJOR REFACTORS NEEDED

### Refactor 1: Unify Progress Indicators (2-3 hours)
**Current state**: Mix of `status_arrow()`, `status_info()`, direct `echo()`
**Target state**: 
- `status_info()` = Starting step
- `status_ok()` = Step completed successfully
- `status_warn()` = Step completed with warnings  
- `status_arrow()` = Metadata/detail lines
- `echo()` = Spacing only (no direct content)

**Files affected**: All cmd_* functions

### Refactor 2: Standardize Help Text (1-2 hours)
**Current**: Mix of Indonesian/English, vague docstrings
**Target**: 
- All docstrings in English
- Include "Usage:" section
- Include "Options:" section  
- Standardized "See also:" section

**Files affected**: All cmd_* function docstrings

### Refactor 3: Create Consistent Summary Pattern (1 hour)
**Current**: Some commands use custom summary, some use `print_push_summary()`
**Target**: Use unified `print_summary()` function

```python
def print_summary(
    title: str,
    items: Dict[str, str],
    next_steps: Optional[List[str]] = None
) -> None:
    """Print consistent command summary."""
```

### Refactor 4: Centralize Config Validation (1-2 hours)
**Current**: Each command validates independently
**Target**: Single `validate_config()` that checks:
- Config exists
- Local DB reachable
- Remote DB reachable (if needed)
- Tools available

### Refactor 5: Add Output Levels (1-2 hours)
**Current**: No way to suppress output (for scripting)
**Target**: Add `--quiet` flag to all commands
```python
if not args.quiet:
    status_ok("Step complete")
```

---

## QUICK REFERENCE: FIX CHECKLIST

- [ ] **cmd_status** - Add closing summary (5 min)
- [ ] **cmd_log** - Add end indicator (2 min)
- [ ] **cmd_stop_auto** - Add closing echo (1 min)
- [ ] **cmd_serve** - Standardize success message (2 min)
- [ ] **cmd_uninstall** - Replace status_warn with status_fail for errors (3 min)
- [ ] **cmd_auto_on** - Standardize status indicators (5 min)
- [ ] **cmd_check** - Remove redundant title (5 min)
- [ ] **cmd_push** - Fix dry-run summary (10 min)
- [ ] **cmd_fetch** - Add closing summary (5 min)
- [ ] **cmd_update** - Fix version check (5 min)
- [ ] **All commands** - Standardize docstrings (15 min)
- [ ] **All commands** - Standardize emoji placement (10 min)
- [ ] **cmd_init** - Language consistency review (20 min)

**Total Quick Wins**: ~90 minutes for all critical + priority 1 fixes

---

## TESTING RECOMMENDATIONS

1. **Test each command with `--help` flag** - Verify docstrings are clear
2. **Run each command in sequence** - Verify output consistency  
3. **Run with `--quiet` flag** - Verify behavior (once implemented)
4. **Check output in non-TTY** - Verify `NC` handling
5. **Test error paths** - Missing config, permission denied, timeouts

---

## CONSISTENCY SCORE

| Category | Score | Notes |
|----------|-------|-------|
| Status Functions | 70% | Some commands skip `status_*()` |
| Box Structure | 85% | Most have box_title/section |
| Emoji Usage | 60% | Inconsistent spacing & mixing |
| Docstrings | 50% | Mix of languages, vague |
| Error Handling | 75% | Generally OK, some inconsistent |
| Final Summary | 40% | Many commands missing closing |
| **Overall** | **63%** | Room for improvement |

---

Generated: 2024-12-21
Next Step: Implement Priority 1 fixes for quick consistency wins
