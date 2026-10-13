package core

import "context"

// baseCtx is the process-wide context, cancelled when the process receives an
// interrupt/terminate signal. RunCmdSimple uses it so that child processes are
// killed on Ctrl+C without threading a context through every caller.
var baseCtx context.Context = context.Background()

// SetBaseContext installs the process-wide context (called from main with a
// signal-aware context).
func SetBaseContext(ctx context.Context) {
	if ctx != nil {
		baseCtx = ctx
	}
}

// BaseContext returns the process-wide context.
func BaseContext() context.Context {
	return baseCtx
}
