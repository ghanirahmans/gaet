# CLI Consistency Baseline Reference
## What `gaet get` and `gaet set` Do Right

This document defines the **golden standard** that all other commands should follow.

---

## cmd_get Pattern (Reference Implementation)

**Location**: `gaet.py:1921-1975`

```python
def cmd_get(args: argparse.Namespace) -> None:
    """Get environment variables from .env file."""
    # ✓ Clear docstring explaining what it does
    
    env = load_env()
    
    if not env:
        status_warn("No .env file found or file is empty")
        # ✓ Early return with clear error message
        return
    
    box_title(f"{NAME} get")
    # ✓ Title box at START of actual output section
    
    # Determine which keys to show
    if hasattr(args, 'keys') and args.keys:
        keys_to_show = args.keys
    else:
        keys_to_show = sorted(env.keys())
    
    # Display variables
    found_count = 0
    not_found = []
    
    for key in keys_to_show:
        if key in env:
            value = env[key]
            # ✓ Masks sensitive values
            display_value = value
            if key.lower().endswith("password") or key.lower().endswith("url"):
                if len(value) > 20:
                    display_value = value[:10] + "***" + value[-5:]
                else:
                    display_value = "***"
            status_ok(f"{C}{key}{NC}  =  {display_value}")
            # ✓ Uses status_ok() for each successful item
            found_count += 1
        else:
            not_found.append(key)
    
    # Report not found keys
    if not_found:
        for key in not_found:
            status_warn(f"{key} not found")
            # ✓ Uses status_warn() for warnings, not failures
    
    echo()
    # ✓ Spacing before summary
    
    if hasattr(args, 'keys') and args.keys:
        # User requested specific keys
        if found_count > 0:
            status_info(f"Showing {found_count} of {len(keys_to_show)} requested variables")
    else:
        # Show all
        status_info(f"Total {found_count} variables configured")
    # ✓ Context-aware summary using status_info()
    
    echo()
    # ✓ Final spacing for clean exit
```

### Key Characteristics:
1. ✓ **Clear Purpose**: Docstring explains what command does
2. ✓ **Title Box**: `box_title()` marks main output section
3. ✓ **Consistent Status Functions**: 
   - `status_ok()` for successes
   - `status_warn()` for warnings (not errors)
   - `status_info()` for summaries
4. ✓ **Logical Flow**: 
   - Setup → Validate → Process → Report → Summary
5. ✓ **Good Error Handling**: 
   - Early return if preconditions fail
   - Clear messages about what went wrong
6. ✓ **Proper Spacing**: 
   - `echo()` calls separate logical sections
   - No trailing output - ends cleanly
7. ✓ **Summary at End**: 
   - Context-aware message
   - Total counts or matching criteria

---

## cmd_set Pattern (Reference Implementation)

**Location**: `gaet.py:1978-2052`

```python
def cmd_set(args: argparse.Namespace) -> None:
    """Set environment variables in .env file."""
    # ✓ Clear docstring with usage examples
    
    if not args.variables:
        die("Usage: gaet set KEY=value [KEY2=value2] ...")
    # ✓ Fails fast if parameters missing
    
    # Ensure .env directory exists
    GAET_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load existing env
    env = load_env()
    
    # Parse and update variables
    updates = {}
    for var in args.variables:
        if "=" not in var:
            die(f"Invalid format: {var}. Use KEY=value")
            # ✓ Clear validation error message
        key, value = var.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            die("Key cannot be empty")
            # ✓ Specific error for specific problem
        updates[key] = value
        env[key] = value
    
    # Save back to .env file (complex logic omitted for brevity)
    # ... [file handling] ...
    
    # Display result
    box_title(f"{NAME} set")
    # ✓ Title box at output section start
    
    for key, value in updates.items():
        # Mask sensitive values in display
        display_value = value
        if key.lower().endswith("password") or key.lower().endswith("url"):
            if len(value) > 20:
                display_value = value[:10] + "***" + value[-5:]
            else:
                display_value = "***"
        status_ok(f"{C}{key}{NC}  =  {display_value}")
        # ✓ Uses status_ok() for each set item
    
    echo()
    # ✓ Spacing before summary
    
    status_info(f"Config saved: {ENV_FILE}")
    # ✓ Clear action completed message
    
    echo()
    # ✓ Final spacing
```

### Key Characteristics:
1. ✓ **Validation First**: Check parameters before processing
2. ✓ **Specific Errors**: Each validation has dedicated error message
3. ✓ **Title Box**: Marks actual output section
4. ✓ **Immediate Feedback**: Each item shows `status_ok()`
5. ✓ **Summary Line**: Final message confirms action
6. ✓ **Proper Spacing**: Clear visual separation

---

## Golden Rules Extracted

### Rule 1: Box Title First
```python
# GOOD ✓
def cmd_xxx(args):
    box_title(f"{NAME} xxx")
    # ... rest of implementation

# BAD ✗
def cmd_xxx(args):
    env = load_env()
    box_title(f"{NAME} xxx")  # Too late
```

### Rule 2: Status Functions in Order of Severity
```python
# In ascending severity:
status_arrow()   # ➜ Informational detail/metadata
status_info()    # ℹ  Informational step/summary
status_warn()    # ⚠  Warning - something unexpected but recoverable
status_fail()    # ✗ Error - command cannot proceed
die()            # ✗✗ Fatal - immediate exit

# NOT for output:
status_ok()      # ✓ Success - completes a step
echo()           # Spacing only
```

### Rule 3: Output Structure Template
```python
# STANDARD FLOW:

# 1. Validate preconditions
if not config:
    die("Config missing")

# 2. Start titled section
box_title(f"{NAME} command")

# 3. Process with status feedback
for item in items:
    status_ok(f"Processed: {item}")

# 4. Summary section
echo()  # Spacing
status_info(f"Total: {count} items")

# 5. Clean exit
echo()  # Final spacing
```

### Rule 4: Error Messages Are Specific
```python
# GOOD ✓
die(f"Database not found: {db_name}\n"
    f"  Available: {', '.join(available_dbs)}")

# BAD ✗
die("Error")

# BAD ✗
die("Database error")
```

### Rule 5: Sensitive Data Masking
```python
# GOOD ✓
if key.lower().endswith("password") or "url" in key.lower():
    if len(value) > 20:
        display_value = value[:10] + "***" + value[-5:]
    else:
        display_value = "***"

# BAD ✗
display_value = value  # Shows full password
```

### Rule 6: Early Returns for Edge Cases
```python
# GOOD ✓
env = load_env()
if not env:
    status_warn("No config found")
    return  # Don't crash, just exit gracefully

# BAD ✗
env = load_env()
# Assume env exists
status_ok(f"Found {len(env)} vars")  # Could crash
```

### Rule 7: Spacing for Visual Clarity
```python
# GOOD ✓
box_title("My Command")
status_ok("Step 1 complete")
status_ok("Step 2 complete")
echo()  # SPACING
status_info("Summary: 2 steps completed")
echo()  # Final spacing

# BAD ✗
box_title("My Command")
status_ok("Step 1 complete")
status_ok("Step 2 complete")
status_info("Summary: 2 steps completed")  # No spacing - cramped
```

### Rule 8: Consistent Icon/Emoji Usage
```python
# GOOD ✓ - Uses built-in constants
echo(f"  {G}{ICON_OK}{NC}  Success!")
echo(f"  {C}💾{NC}  Backup location: /path")
status_arrow(f"Details: {value}")

# BAD ✗ - Hardcoded/inconsistent
echo(f"  ✓ Success!")  # Not using COLOR
echo(f"  💾    Backup")  # Inconsistent spacing
```

---

## Status Function Recommendations

### status_ok()
**Use for**: Steps that completed successfully  
**Color**: Green  
**Icon**: ✓

```python
status_ok("Database connected successfully")
status_ok("Backup file saved")
status_ok("All checks passed")
```

### status_warn()
**Use for**: Warnings - unexpected but recoverable  
**Color**: Yellow  
**Icon**: ⚠

```python
status_warn("Database unreachable - continuing anyway")
status_warn("Config from last run - outdated")
status_warn("Auto-backup not enabled yet")
```

### status_fail()
**Use for**: Errors - command cannot continue  
**Color**: Red  
**Icon**: ✗

```python
status_fail("Database connection refused")
status_fail("Config file corrupted")
status_fail("Required tool not found: pg_dump")
```

### status_info()
**Use for**: Informational messages - progress or summaries  
**Color**: Cyan  
**Icon**: ℹ

```python
status_info("Starting backup...")
status_info("Total 5 tables synchronized")
status_info("Config saved successfully")
```

### status_arrow()
**Use for**: Detail lines - metadata, lists, parameters  
**Color**: Cyan  
**Icon**: →

```python
status_arrow(f"Source: {user}@{host}:{port}")
status_arrow(f"Backup size: 123.5 MB")
status_arrow(f"Retention: 7 days")
```

### echo()
**Use for**: Spacing only - never for content  
**Color**: None  
**Icon**: None

```python
echo()  # Add blank line for visual separation
```

---

## Common Output Patterns

### Pattern 1: Simple Listing
```python
box_title("Available Options")
for option in options:
    status_arrow(f"{option['name']:12} - {option['desc']}")
echo()
```

### Pattern 2: Process with Progress
```python
box_title("Processing Items")
for i, item in enumerate(items, 1):
    status_info(f"[{i}/{len(items)}] {item}...")
    # ... do work ...
    status_ok(f"Completed")

echo()
status_info(f"Total: {len(items)} items processed")
echo()
```

### Pattern 3: Verification Steps
```python
box_title("Verification")
if condition1:
    status_ok("Check 1: Passed")
else:
    status_fail("Check 1: Failed")
    return

if condition2:
    status_ok("Check 2: Passed")
else:
    status_warn("Check 2: Warning")

echo()
status_info("Verification complete")
echo()
```

### Pattern 4: Data Display with Summary
```python
box_title("Data")

# Header
box_section("Details")

# Items
for key, value in data.items():
    display_value = mask_if_sensitive(key, value)
    status_ok(f"{C}{key}{NC}  =  {display_value}")

# Summary
echo()
status_info(f"Total: {len(data)} items")
echo()
```

### Pattern 5: Dry-Run Preview
```python
box_title("Command --dry-run")

box_section("Changes that would be made")
status_arrow(f"Would update: 10 records")
status_arrow(f"Would delete: 2 records")
status_arrow(f"Would create: 1 new table")

echo()
status_info("Dry-run: No changes were made")
status_info("To proceed: gaet command  (remove --dry-run)")
echo()
```

---

## Consistency Checklist for New Commands

Before finalizing a command, verify:

- [ ] Has clear docstring with usage examples
- [ ] Starts with `box_title()`
- [ ] Validates all preconditions early, exits with `die()` if needed
- [ ] Uses `status_ok()` for successful steps
- [ ] Uses `status_warn()` for recoverable issues
- [ ] Uses `status_fail()` or `die()` for fatal errors
- [ ] Uses `status_info()` for progress/summaries
- [ ] Uses `status_arrow()` for details/parameters
- [ ] Uses `echo()` for spacing only (never for content)
- [ ] Has closing summary section with `status_info()`
- [ ] Ends with `echo()` for clean exit
- [ ] No trailing output or incomplete sentences
- [ ] Masks sensitive data (passwords, URLs)
- [ ] All text is grammatically correct English
- [ ] Test both success and error paths

---

## Anti-Patterns to Avoid

### ✗ Anti-Pattern 1: Mixed Colors Without Structure
```python
# BAD
echo(f"  {G}✓{NC}  Success")
echo(f"  {Y}Item: value")
echo(f"  {R}Error occurred")
# User can't tell which is which

# GOOD
status_ok("Success")
status_arrow(f"Item: value")
status_fail("Error occurred")
```

### ✗ Anti-Pattern 2: No Spacing Between Sections
```python
# BAD
box_title("Command")
status_ok("Step 1")
status_ok("Step 2")
status_info("Summary")
# All crammed together

# GOOD
box_title("Command")
status_ok("Step 1")
status_ok("Step 2")
echo()
status_info("Summary")
echo()
```

### ✗ Anti-Pattern 3: Incomplete Summary
```python
# BAD
for item in items:
    status_ok(f"{item}")
# Command ends abruptly

# GOOD
for item in items:
    status_ok(f"{item}")
echo()
status_info(f"Total: {len(items)}")
echo()
```

### ✗ Anti-Pattern 4: No Error Checking
```python
# BAD
env = load_env()
remote_url = env["GAET_REMOTE_URL"]  # Crashes if missing

# GOOD
env = load_env()
remote_url = get_env_str(env, "GAET_REMOTE_URL") or ""
if not remote_url:
    die("GAET_REMOTE_URL not configured")
```

### ✗ Anti-Pattern 5: Showing Passwords
```python
# BAD
status_ok(f"Password: {password}")  # Security risk!

# GOOD
display_pass = "***" if len(password) > 0 else ""
status_ok(f"Password: {display_pass}")
```

### ✗ Anti-Pattern 6: Silent Failures
```python
# BAD
try:
    operation()
except:
    pass  # User doesn't know what failed

# GOOD
try:
    operation()
except Exception as e:
    status_warn(f"Operation failed: {e}")
    status_info("This may be recoverable - check logs")
```

---

## Summary

Every CLI command should aim to match the **consistency score** of `cmd_get` and `cmd_set`:

- **Status Functions**: 100% - All messages use appropriate status functions
- **Box Structure**: 100% - Clear title and sections
- **Error Handling**: 100% - Specific, helpful error messages
- **Spacing**: 100% - Clean visual separation
- **Clarity**: 100% - No ambiguity about success/failure
- **User Guidance**: 100% - Clear about what happened and what's next

**Target: All commands should score 95%+ consistency**

Current audit shows average of **63%** - room for improvement with quick wins and medium refactors.
