.pragma library
.import "../workflow/State.js" as Workflow

// Compatibility entrypoint for existing tests and consumers.
function state(snapshot, pending, stale) { return Workflow.state(snapshot, pending, stale); }
function label(value) { return Workflow.label(value); }
function remaining(status, sampledAt, now) { return Workflow.remaining(status, sampledAt, now); }
