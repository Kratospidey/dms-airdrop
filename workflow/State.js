.pragma library

function state(snapshot, pending, stale) {
    if (pending)
        return pending === "on" ? "STARTING" : pending === "off" ? "STOPPING" : pending === "send" ? "SENDING" : pending === "prepare-send" ? "PREPARING" : pending === "cleanup-send" ? "CLEANING" : "CHECKING";
    if (!snapshot || !snapshot.ok || stale)
        return snapshot && snapshot.code === "missing" ? "UNAVAILABLE" : "UNKNOWN";
    const job = snapshot.job || {};
    if (snapshot.busy) {
        if (snapshot.session && snapshot.session.phase === "cleaning") return "CLEANING";
        if (job.action === "send") return "SENDING";
        if (job.action === "on") return "STARTING";
        if (job.action === "off") return "STOPPING";
        if (job.action === "prepare-send") return "PREPARING";
        if (job.action === "cleanup-send") return "CLEANING";
        return "CHECKING";
    }
    if (snapshot.external_send)
        return "SENDING";
    const s = snapshot.status;
    if (!s || typeof s.receiving !== "boolean" || typeof s.visible !== "boolean")
        return "UNKNOWN";
    if (s.receiver_state === "failed")
        return "ERROR";
    if (s.receiving && s.visible)
        return "RECEIVING";
    if (!s.receiving && !s.visible)
        return "OFF";
    return "ERROR";
}

function label(value) {
    return {OFF: "Off", STARTING: "Starting", STOPPING: "Stopping", SENDING: "Sending",
        RECEIVING: "Discoverable", UNKNOWN: "Checking AirDrop status", UNAVAILABLE: "Backend unavailable",
        PREPARING: "Looking for nearby devices…", CLEANING: "Finishing sending session…",
        CHECKING: "Working", ERROR: "AirDrop needs attention"}[value] || "Checking AirDrop status";
}

function remaining(status, sampledAt, now) {
    if (!status || !status.receiving) return "";
    if (status.mode === "once") return "Until one transfer arrives";
    if (status.mode === "forever") return "Until turned off";
    if (typeof status.remaining !== "number") return "Checking remaining time";
    const left = Math.max(0, status.remaining - Math.floor((now - sampledAt) / 1000));
    return left > 0 ? Math.ceil(left / 60) + "m remaining" : "Checking window expiry";
}
