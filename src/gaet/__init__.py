"""gaet — PostgreSQL Backup & Sync CLI (v3 package layout)."""

from .core import BACKUP_DIR, CRON_LOG, DEF_AUTO_INTERVAL, DEF_DASHBOARD_HOST, DEF_DASHBOARD_PORT, DEF_LOCAL_DB, DEF_LOCAL_HOST, DEF_LOCAL_PASS, DEF_LOCAL_PORT, DEF_LOCAL_USER, DEF_PG_TIMEOUT, DEF_REMOTE_SSLMODE, DEF_RETENTION_DAYS, DEF_SERVICE_PREFIX, ENV_FILE, EXIT_CLOUD_DOWN, EXIT_CONFIG, EXIT_LOCAL_DOWN, EXIT_LOCKED, EXIT_TOOLS, GAET_DIR, GITHUB_API, GITHUB_RAW, HOME, IS_LINUX, IS_MACOS, IS_WINDOWS, LOCK_PATH, LOG_FILE, NAME, PLAIN, QUIET, SYSTEM, Spinner, VERSION, _FORCE_COLOR, _NO_COLOR, _SUGGEST_NAMES, _TABLE_NAME_RE, _USE_COLOR, _build_env_content, _ensure_git_workspace, _find_socket_paths, _gh_download, _raw_download, _is_socket_host, _local_config_lines, _lock_is_stale, _print_summary, _save_init_config, _socket_port, _validate_table_name, _write_env_file, _write_lock_pid, acquire_lock, box_section, box_title, cleanup_pg_env, cronlog, die, discover_tables, draw_colored_table, draw_table, echo, emit_help_json, find_pg_tools, get_env_int, get_env_str, get_local_db, get_tables, is_plain, load_env, log, mask_url_password, parse_remote_url, pg_env, print_push_summary, print_sync_summary, release_lock, run_cmd, safe_getpass, safe_input, set_output_modes, status_arrow, status_fail, status_info, status_ok, status_warn, suggest_command
from .detect import detect_local_pg
from .export import _build_export_parser, cmd_export
from .init import PRESETS, _build_init_parser, _local_db_menu, _manual_db_input, _url_input, cmd_init
from .config import _build_get_parser, _build_set_parser, cmd_get, cmd_set
from .status import _build_check_parser, _build_completion_parser, _build_diff_parser, _build_doctor_parser, _build_status_parser, check_local_db, check_tools, cmd_check, cmd_check_inner, cmd_completion, cmd_diff, cmd_doctor, cmd_status, get_status_inline
from .backup import _build_fetch_parser, _build_push_parser, _reset_target_objects, cmd_fetch, cmd_push, cmd_push_cron
from .scheduler import _build_stop_parser, _svc_is_running, _svc_start, _svc_status, _svc_stop, cmd_auto_on, cmd_stop_auto
from .log import _build_log_parser, cmd_log
from .serve import _build_serve_parser, cmd_serve
from .update import _build_install_parser, _build_uninstall_parser, _build_update_parser, _update_download, cmd_install, cmd_uninstall, cmd_update
from .cli import main
