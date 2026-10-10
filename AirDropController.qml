import QtQuick
import Quickshell
import Quickshell.Io
import qs.Services
import "components"
import "picker"
import "workflow"
import "workflow/State.js" as State
import "picker/FileSelection.js" as Selection

Item {
    id: root
    property string pluginId: "dmsAirDrop"
    property var pluginService: null
    property int preferenceRevision: 0
    property var snapshot: ({ok: false})
    property var backend: snapshot.status || ({})
    property var job: snapshot.job || ({})
    property var peers: []
    property var selectedFiles: []
    property string selectedPeer: ""
    property string error: ""
    property string peerMessage: ""
    property var diagnostics: null
    property string pending: ""
    property string pendingId: ""
    property double pendingSince: 0
    property double sampledAt: 0
    property double peersAt: 0
    property double now: Date.now()
    property var visiblePopouts: []
    property bool openingRefresh: false
    property bool lastKnownActive: false
    property bool lastKnownBusy: false
    readonly property bool popoutVisible: visiblePopouts.length > 0
    readonly property int openInterval: Math.max(10, Math.min(60, Number(pref("openInterval", 15)) || 15)) * 1000
    // Receiving/owned discovery is availability, not a running operation.
    // Backend locks (including cleanup) and queued UI work need fast checks;
    // session phase alone can outlive a worker and must not pin that rate.
    readonly property bool fastPolling: busy || lastKnownBusy || prepareRequested || cleanupRequested
    readonly property bool receivingSession: active || lastKnownActive || temporarySession
    readonly property int pollInterval: fastPolling ? 3000 : receivingSession ? (popoutVisible ? 3000 : 30000) : popoutVisible ? openInterval : 300000
    readonly property int freshnessLimit: Math.max(30000, pollInterval + 15000)
    readonly property bool clockNeeded: active || busy || temporarySession || selectedFiles.length > 0 || (popoutVisible && peersAt > 0 && now - peersAt < 15000)
    readonly property bool clockRunning: clockTimer.running
    readonly property bool checking: statusCommand.busy
    property int generation: 0
    property int statusGeneration: 0
    property int peerGeneration: 0
    property bool autoDiscover: false
    property bool prepareRequested: false
    property bool cleanupRequested: false
    property string cleanupToken: ""
    property bool basicPicker: false
    property string pickerComponentUrl: "workflow/KdePickerSession.qml"
    readonly property var sendSession: snapshot.session || ({})
    readonly property bool temporarySession: sendSession.owned === true
    readonly property string sessionMessage: active ? sendSession.message || "" : ""
    property string notifiedId: ""
    property string dismissedId: ""
    property bool hadStatus: false
    property bool hadSnapshot: false
    property bool wasReceiving: false
    property double lastNames: 0
    readonly property var picker: filePicker.session
    readonly property string pickerState: filePicker.state
    readonly property bool pickerActive: filePicker.active
    readonly property bool selecting: selectionCommand.busy
    readonly property bool canPickFiles: !busy && !selecting
    property var pendingFiles: []
    property int selectionRevision: 0
    property int validationRevision: 0
    property string selectionSize: ""
    readonly property string selectionSummary: Selection.summary(selectedFiles, selectionSize)
    property string helper: decodeURIComponent(Qt.resolvedUrl("scripts/backend.py").toString().substring(7))
    readonly property bool stale: openingRefresh || sampledAt === 0 || now - sampledAt >= freshnessLimit
    readonly property string state: State.state(snapshot, pending, stale)
    readonly property string statusLabel: State.label(state)
    readonly property string timeLabel: stale ? "" : State.remaining(backend, sampledAt, now)
    readonly property bool busy: pending !== "" || submitCommand.busy || snapshot.busy === true || snapshot.external_send === true
    readonly property bool canAct: !busy && !stale && snapshot.ok === true
    readonly property bool active: backend.receiving === true || backend.visible === true
    readonly property bool canSend: canAct && !pickerActive && !selecting && backend.receiving === true && backend.visible === true && selectedFiles.length > 0 && selectedPeer !== "" && now - peersAt < 15000 && backend.mode !== "once" && (backend.mode === "forever" || (typeof backend.remaining === "number" && backend.remaining - (now - sampledAt) / 1000 >= 120))
    readonly property bool scanning: peersCommand.busy || (snapshot.busy && job.action === "names")
    readonly property string tooltip: "AirDrop — " + (state === "RECEIVING" ? "Receiving, " + timeLabel : statusLabel)
    readonly property bool showResult: !!job.id && job.id !== dismissedId && (job.state === "failed" || job.state === "interrupted")

    function pref(key, fallback) {
        const revision = preferenceRevision;
        return pluginService ? pluginService.loadPluginData(pluginId, key, fallback) : fallback;
    }
    function args(command) { return ["python3", helper, command]; }
    function syncClock() {
        now = Date.now();
        if (peersAt && now - peersAt >= 15000) selectedPeer = "";
    }
    function setPopoutVisible(owner, opened) {
        const others = visiblePopouts.filter(item => item && item !== owner);
        visiblePopouts = opened ? others.concat([owner]) : others;
    }
    onPopoutVisibleChanged: {
        syncClock();
        if (popoutVisible) {
            openingRefresh = true;
            refresh();
        }
    }
    onClockNeededChanged: { if (clockNeeded) syncClock(); }
    function armFreshness() {
        freshnessDeadline.stop();
        if (sampledAt === 0 || openingRefresh) return;
        const remaining = sampledAt + freshnessLimit - Date.now();
        if (remaining <= 0) { syncClock(); return; }
        freshnessDeadline.interval = remaining;
        freshnessDeadline.start();
    }
    onSampledAtChanged: armFreshness()
    onFreshnessLimitChanged: armFreshness()
    onOpeningRefreshChanged: armFreshness()
    function refresh() {
        syncClock();
        if (statusCommand.busy) return;
        statusGeneration = generation;
        statusCommand.start(args("status"));
    }
    function act(action, values) {
        syncClock();
        if (!canAct) { if (stale) refresh(); return; }
        error = "";
        pending = action;
        pendingId = "";
        pendingSince = Date.now();
        generation++;
        const data = Object.assign({action: action}, values || {});
        submitCommand.start(args("submit").concat([JSON.stringify(data)]));
    }
    function receive(duration) { cleanupRequested = false; act("on", {duration: duration || pref("duration", "10m")}); }
    function stop() { clearSelection(false); act("off"); }
    // The same guarded controller actions are available for optional keybindings.
    // Merely inspecting status never opens a receiving window.
    IpcHandler {
        target: "dmsAirDrop"
        function status(): string {
            return JSON.stringify({state: root.state, label: root.statusLabel,
                remaining: root.timeLabel, busy: root.busy, canAct: root.canAct,
                pickerState: root.pickerState, selectedCount: root.selectedFiles.length,
                session: root.sendSession,
                backend: root.backend, job: root.job,
                error: root.error || root.snapshot.error || ""});
        }
        function receive(duration: string): string {
            if (!/^(once|([1-9]|[1-5][0-9]|60)m)$/.test(duration))
                return "ERROR: choose once or 1m–60m";
            if (!root.canAct) return "ERROR: AirDrop is busy or status is unavailable";
            root.receive(duration);
            return "REQUESTED: receive " + duration;
        }
        function stop(): string {
            if (!root.canAct) return "ERROR: AirDrop is busy or status is unavailable";
            root.stop();
            return "REQUESTED: stop";
        }
        function refresh(): string {
            root.refresh();
            return "REQUESTED: status refresh";
        }
        function chooseFiles(): string {
            if (!root.canPickFiles) return "ERROR: Wait for the current operation before choosing files";
            root.pickFiles();
            return "REQUESTED: file picker";
        }
        function cancelPicker(): string {
            root.cancelPicker();
            return "CANCELLED: file picker";
        }
    }
    function discover() {
        if (!canAct || backend.visible !== true || peersCommand.busy) return;
        peerGeneration = generation;
        peerMessage = "";
        peersCommand.start(args("peers"));
    }
    function resolveNames() {
        if (Date.now() - lastNames < 30000 || scanning) return;
        lastNames = Date.now();
        act("names");
    }
    function pickFiles() {
        if (!canPickFiles) { error = "Wait for the current operation before changing files."; return; }
        error = "";
        if (filePicker.sessionComponent.status === Component.Error) console.warn("AirDrop picker:", filePicker.sessionComponent.errorString());
        filePicker.open();
    }
    function useBasicPicker() { basicPicker = true; pickFiles(); }
    function cancelPicker() { filePicker.cancel(); }
    function startDiscovery() {
        if (!selectedFiles.length) return;
        prepareRequested = true;
        syncClock();
        if (stale) refresh();
        continueWorkflow();
    }
    function continueWorkflow() {
        if (!canAct) return;
        if (cleanupRequested) {
            const token = cleanupToken || sendSession.token;
            cleanupRequested = false;
            cleanupToken = "";
            if (token && temporarySession) act("cleanup-send", {token: token});
            return;
        }
        if (prepareRequested && selectedFiles.length) {
            prepareRequested = false;
            autoDiscover = true;
            act("prepare-send");
        }
    }
    FilePicker {
        id: filePicker
        // DMS only cache-busts its entrypoint on plugin reload. Give each
        // controller's short-lived picker windows a fresh component too.
        sessionComponent: Qt.createComponent(Qt.resolvedUrl(root.basicPicker ? "picker/FilePickerSession.qml" : root.pickerComponentUrl).toString() + "?v=" + Date.now())
        onFailed: message => root.error = message
        onSelected: paths => {
            if (root.busy) { root.error = "AirDrop became busy. Choose files again when the operation finishes."; return; }
            root.validationRevision = ++root.selectionRevision;
            root.pendingFiles = paths;
            selectionCommand.start(root.args("inspect-files").concat([JSON.stringify(paths)]));
        }
    }
    Command {
        id: selectionCommand
        onCompleted: result => {
            const paths = root.pendingFiles;
            root.pendingFiles = [];
            if (root.validationRevision !== root.selectionRevision) return;
            if (!result.ok) { root.error = result.error; return; }
            root.selectedFiles = paths;
            root.selectionSize = result.size_label;
            root.selectedPeer = "";
            root.error = "";
            selectionExpiry.restart();
            root.startDiscovery();
            ToastService.showInfo("Choose an AirDrop destination", "Open AirDrop to select a nearby device.");
        }
    }
    function clearSelection(cleanup = true) {
        const needsCleanup = temporarySession || pending === "prepare-send" || autoDiscover;
        selectionRevision++;
        selectedFiles = [];
        selectionSize = "";
        selectedPeer = "";
        selectionExpiry.stop();
        prepareRequested = false;
        autoDiscover = false;
        if (cleanup && needsCleanup) {
            cleanupRequested = true;
            cleanupToken = sendSession.token || "";
            Qt.callLater(continueWorkflow);
        }
    }
    function send() {
        if (!canSend) return;
        const files = selectedFiles.slice();
        act("send", {files: files, peer: selectedPeer});
        clearSelection(false);
    }
    function openDownloads() {
        if (typeof backend.dir === "string" && backend.dir.startsWith("/"))
            Qt.openUrlExternally("file://" + backend.dir.split("/").map(encodeURIComponent).join("/"));
    }
    function diagnose() {
        if (!diagnosticCommand.busy) diagnosticCommand.start(args("diagnostics"));
    }
    function publish() {
        if (pluginService) {
            pluginService.setGlobalVar(pluginId, "controller", root);
        }
    }
    Component.onCompleted: { publish(); refresh(); }
    onPluginServiceChanged: publish()
    Component.onDestruction: {
        if (pluginService && pluginService.getGlobalVar(pluginId, "controller", null) === root)
            pluginService.setGlobalVar(pluginId, "controller", null);
        for (const category of successCategories) ToastService.dismissCategory(category);
        // No off, cancel, or restart here: Omdrop owns receiving and a finite
        // transient service owns an already-requested operation.
    }
    Connections {
        target: root.pluginService
        function onPluginDataChanged(id) {
            if (id === root.pluginId) root.preferenceRevision++;
        }
    }
    Timer {
        objectName: "statusPoll"
        interval: root.pollInterval
        running: true
        repeat: true
        onTriggered: root.refresh()
    }
    Timer {
        id: clockTimer
        interval: 1000
        running: root.clockNeeded
        repeat: true
        onTriggered: {
            root.syncClock();
        }
    }
    // One deadline wakeup invalidates a sample if reconciliation stalls.
    // Static idle UI needs neither a ticking clock nor another polling loop.
    Timer {
        id: freshnessDeadline
        objectName: "freshnessDeadline"
        onTriggered: { root.syncClock(); root.armFreshness(); }
    }
    Timer {
        interval: 5000
        running: root.selectedFiles.length > 0 && root.active
        repeat: true
        onTriggered: root.discover()
    }
    Timer { id: selectionExpiry; objectName: "selectionExpiry"; interval: 300000; onTriggered: { root.error = "File selection expired. Choose files again when you are ready."; root.clearSelection(); } }

    // Scope the native toast timer to our own category. Other notifications,
    // warnings and errors retain DMS's normal timing and queue behavior.
    property var successCategories: []
    function showSuccess(id) {
        const category = "dms-airdrop-sent-" + id;
        successCategories = successCategories.filter(c => c === ToastService.currentCategory || ToastService.toastQueue.some(t => t.category === c)).concat([category]);
        ToastService.showInfo("✓ Sent successfully", "", "", category);
        toastSetup.restart();
    }
    Connections {
        target: ToastService
        function onCurrentCategoryChanged() { toastSetup.restart(); }
        function onToastVisibleChanged() { toastSetup.restart(); }
    }
    Timer {
        id: toastSetup
        interval: 1
        onTriggered: {
            if (ToastService.toastVisible && root.successCategories.indexOf(ToastService.currentCategory) >= 0) {
                ToastService.stopTimer();
                successLifetime.category = ToastService.currentCategory;
                successLifetime.restart();
            } else successLifetime.stop();
        }
    }
    Timer {
        id: successLifetime
        property string category: ""
        interval: 3500
        onTriggered: ToastService.dismissCategory(category)
    }

    Command {
        id: statusCommand
        onCompleted: result => {
            if (root.statusGeneration !== root.generation) { Qt.callLater(root.refresh); return; }
            const initialSnapshot = !root.hadSnapshot;
            root.hadSnapshot = true;
            root.syncClock();
            root.snapshot = result;
            root.openingRefresh = false;
            if (result.ok || (typeof result.busy === "boolean" && typeof result.external_send === "boolean"))
                root.lastKnownBusy = result.busy === true || result.external_send === true;
            if (initialSnapshot && result.session?.owned && result.session.phase === "discovering" && !result.busy) {
                root.cleanupRequested = true;
                root.cleanupToken = result.session.token;
            }
            if (result.ok) {
                root.lastKnownActive = result.status.receiving || result.status.visible;
                // Keep the sample and interpolated countdown on one timestamp.
                root.sampledAt = root.now;
                const receiving = result.status.receiving;
                if (root.hadStatus && root.wasReceiving && !receiving && !root.pending && result.status.mode === "off" && root.pref("notifyExpiry", false))
                    ToastService.showInfo("AirDrop window closed");
                root.wasReceiving = receiving;
                root.hadStatus = true;
                if (!result.status.visible && root.selectedFiles.length && !root.prepareRequested && !root.pending && result.session?.phase === "expired") {
                    root.error = "The temporary discovery session ended. Choose files again to retry.";
                    root.clearSelection(false);
                }
            }
            const job = result.job || {};
            if (root.pendingId && job.id === root.pendingId) {
                root.pending = "";
                root.pendingId = "";
            } else if (root.pending && !submitCommand.busy && Date.now() - root.pendingSince > 15000) {
                root.pending = "";
                root.pendingId = "";
                root.error = "The operation could not be confirmed. Check status before trying again.";
            }
            if (job.id && job.state !== "running" && job.id !== root.notifiedId) {
                root.notifiedId = job.id;
                // Reconcile an existing result silently after reload. A job
                // observed running still notifies when it later completes.
                // Successful jobs never become persistent result cards.
                if (!initialSnapshot && Date.now() / 1000 - job.updated < 12 && root.pref("notifyResults", true)) {
                    if (job.state === "complete" && job.action === "send") root.showSuccess(job.id);
                    else if (job.state === "failed") ToastService.showError("AirDrop", job.message);
                }
                if (job.action === "names" && job.state === "complete") {
                    root.peers = job.peers || [];
                    root.peersAt = job.updated * 1000;
                }
            }
            if (root.autoDiscover && !root.busy) {
                root.autoDiscover = false;
                if (job.state === "complete" && result.ok && result.status.visible && root.selectedFiles.length) Qt.callLater(root.discover);
            }
            if (result.ok && !result.status.visible) {
                root.peers = [];
                root.selectedPeer = "";
            }
            Qt.callLater(root.continueWorkflow);
        }
    }
    Command {
        id: submitCommand
        onCompleted: result => {
            if (result.ok) root.pendingId = result.id;
            else {
                root.error = result.error;
                root.pending = "";
                root.autoDiscover = false;
            }
            Qt.callLater(root.refresh);
        }
    }
    Command {
        id: peersCommand
        onCompleted: result => {
            if (root.peerGeneration !== root.generation) return;
            root.peers = result.ok ? result.peers : [];
            root.peersAt = result.ok ? Date.now() : 0;
            root.peerMessage = result.ok ? (result.peers.length ? "" : "No Apple devices found. Enable AirDrop on your iPhone and try again.") : result.error;
            if (!root.peers.some(p => p.mac === root.selectedPeer)) root.selectedPeer = "";
        }
    }
    Command {
        id: diagnosticCommand
        onCompleted: result => root.diagnostics = result
    }
}
