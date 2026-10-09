import QtQuick
import QtTest
import "../components/State.js" as State

TestCase {
    name: "AirDropState"
    function test_unknown_never_off() {
        compare(State.state(null, "", false), "UNKNOWN");
        compare(State.state({ok: false}, "", false), "UNKNOWN");
        compare(State.state({ok: true, status: {receiving: false, visible: null}}, "", false), "UNKNOWN");
        compare(State.state({ok: false, code: "missing"}, "", false), "UNAVAILABLE");
    }
    function test_states() {
        compare(State.state({ok: true, status: {receiving: false, visible: false}}, "", false), "OFF");
        compare(State.state({ok: true, status: {receiving: true, visible: true}}, "", false), "RECEIVING");
        compare(State.state({ok: true, status: {receiving: true, visible: false}}, "", false), "ERROR");
        compare(State.state({ok: true, status: {receiving: false, visible: false, receiver_state: "failed"}}, "", false), "ERROR");
        compare(State.state({ok: true, external_send: true}, "", false), "SENDING");
        compare(State.state({ok: true, busy: true, job: {action: "send"}}, "", false), "SENDING");
        compare(State.state(null, "on", false), "STARTING");
        compare(State.state(null, "off", false), "STOPPING");
        compare(State.state(null, "prepare-send", false), "PREPARING");
        compare(State.state({ok: true, busy: true, job: {action: "prepare-send"}}, "", false), "PREPARING");
        compare(State.state({ok: true, busy: true, job: {action: "cleanup-send"}}, "", false), "CLEANING");
        compare(State.state({ok: true, busy: true, session: {phase: "cleaning"}, job: {action: "prepare-send", state: "complete"}}, "", false), "CLEANING");
    }
    function test_stale_not_off() {
        compare(State.state({ok: true, status: {receiving: false, visible: false}}, "", true), "UNKNOWN");
    }
    function test_backend_countdown() {
        compare(State.remaining({receiving: true, mode: "timed", remaining: 480}, 1000, 2000), "8m remaining");
        compare(State.remaining({receiving: true, mode: "timed", remaining: 1}, 1000, 3000), "Checking window expiry");
        compare(State.remaining({receiving: true, mode: "once"}, 0, 100), "Until one transfer arrives");
        compare(State.remaining({receiving: false}, 0, 100), "");
    }
}
