// Package remote implements `gaet remote` command.
package remote

import (
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"time"

	"github.com/ghanirahmans/gaet/pkg/core"
)

// RunRemote implements `gaet remote [action] [url]`.
func RunRemote(action, urlArg string, jsonOut bool) error {
	if jsonOut {
		core.Quiet = true
		core.Plain = true
	}

	env, err := core.LoadEnv(core.EnvFile())
	if err != nil {
		return err
	}

	switch strings.ToLower(action) {
	case "set-url":
		if urlArg == "" {
			return core.Die("Usage: gaet remote set-url <postgresql://user:pass@host:port/db>", core.ExitUsage)
		}
		if _, err := core.ParseRemoteURL(urlArg); err != nil {
			return core.Die("Invalid remote URL format. Expected: postgresql://user:pass@host:port/dbname", core.ExitConfig)
		}
		if err := core.SetEnvKey(core.EnvFile(), "GAET_REMOTE_URL", urlArg); err != nil {
			return err
		}
		core.WriteJSONLog(core.LogEntry{
			Level:    "INFO",
			Category: "REMOTE",
			Action:   "REMOTE_SET",
			Status:   "SUCCESS",
			Message:  "GAET_REMOTE_URL updated successfully",
		})
		core.StatusOK("GAET_REMOTE_URL updated successfully")
		return nil

	case "remove", "unset", "rm":
		if err := core.SetEnvKey(core.EnvFile(), "GAET_REMOTE_URL", ""); err != nil {
			return err
		}
		core.WriteJSONLog(core.LogEntry{
			Level:    "INFO",
			Category: "REMOTE",
			Action:   "REMOTE_REMOVE",
			Status:   "SUCCESS",
			Message:  "GAET_REMOTE_URL removed from .env",
		})
		core.StatusOK("GAET_REMOTE_URL removed from .env")
		return nil

	default: // "show"
		remoteURL := core.GetEnvStr(env, "GAET_REMOTE_URL", "")
		if remoteURL == "" {
			remoteURL = core.GetEnvStr(env, "GAET_SUPABASE_URL", "")
		}
		parsed, parseErr := core.ParseRemoteURL(remoteURL)

		if jsonOut {
			result := map[string]any{"command": "remote", "configured": parseErr == nil, "remote": nil}
			if parseErr == nil {
				result["remote"] = map[string]any{
					"host": parsed.Host, "port": parsed.Port,
					"user": parsed.User, "db": parsed.DB,
				}
			}
			enc := json.NewEncoder(os.Stdout)
			enc.SetIndent("", "  ")
			return enc.Encode(result)
		}

		core.BoxTitle("gaet remote")
		if parseErr != nil {
			core.StatusWarn("No Remote Cloud DB configured yet.")
			core.Echo(fmt.Sprintf("  Usage: %sgaet remote set-url postgresql://user:pass@host:port/db%s",
				core.ColorCyan, core.ColorReset))
			return nil
		}

		maskedURL := core.MaskURLPassword(remoteURL)
		core.BoxSection("Remote Configuration")
		core.StatusArrow(fmt.Sprintf("Host:     %s", parsed.Host))
		core.StatusArrow(fmt.Sprintf("Port:     %s", parsed.Port))
		core.StatusArrow(fmt.Sprintf("User:     %s", parsed.User))
		core.StatusArrow(fmt.Sprintf("Database: %s", parsed.DB))
		core.StatusArrow(fmt.Sprintf("URL:      %s", maskedURL))

		fmt.Println()
		core.Echo(fmt.Sprintf("  %s[INFO]%s  Testing remote cloud connection...",
			core.ColorBCyan, core.ColorReset))
		tools := core.FindPGTools(env)
		if tools.Psql != "" {
			ssl := core.GetEnvStr(env, "GAET_REMOTE_SSLMODE", core.DefRemoteSSLMode)
			envCloud := core.PGEnv(parsed.User, parsed.Password, ssl)
			out, _, rc := core.RunCmdSimple(tools.Psql,
				[]string{"-w", "-h", parsed.Host, "-p", parsed.Port,
					"-U", parsed.User, "-d", parsed.DB, "-tAc", "SELECT 1;"},
				envCloud, 5*time.Second)
			if rc == 0 && strings.TrimSpace(out) == "1" {
				core.StatusOK("Cloud connection OK")
			} else {
				core.StatusFail("Cannot connect to cloud database")
				core.StatusWarn("Check GAET_REMOTE_URL and cloud database status")
			}
		} else {
			core.StatusWarn("psql not found — connection test skipped")
		}
		fmt.Println()
		return nil
	}
}
