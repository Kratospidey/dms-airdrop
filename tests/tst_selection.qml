import QtQuick
import QtTest
import "../picker/FileSelection.js" as Selection
TestCase {
    name: "FileSelection"
    function test_urls() {
        compare(Selection.localPaths(["file:///tmp/a%20b%23c%3F.txt", "file:///tmp/%E6%97%A5.txt"]), ["/tmp/a b#c?.txt", "/tmp/日.txt"]);
        compare(Selection.localPaths(["file:///tmp/a", "file:///tmp/a"]), ["/tmp/a"]);
    }
    function test_invalid_data() {
        for (const values of [[], ["https://example.com/a"], ["file://remote/a"], ["file:///a?x"], ["file:///a%00"], ["file:///a%zz"]]) {
            let rejected = false;
            try { Selection.localPaths(values); } catch (_) { rejected = true; }
            verify(rejected, "Invalid URL accepted: " + values);
        }
    }
    function test_summary() {
        compare(Selection.summary(["/private/photo 日.jpg"], "1.0 KiB"), "photo 日.jpg · 1.0 KiB");
        compare(Selection.summary(["/a", "/b"], "20 B"), "2 files selected · 20 B");
    }
}
