.pragma library

function localPaths(urls) {
    if (!urls || urls.length < 1 || urls.length > 256)
        throw new Error("Select between 1 and 256 local files.");
    const paths = [];
    for (const value of urls) {
        const url = value.toString();
        // Remote authorities, query/fragment suffixes and malformed escapes
        // must never silently become different local filenames.
        if (!url.startsWith("file:///") || /[?#]/.test(url))
            throw new Error("Choose files from a local folder.");
        let path;
        try { path = decodeURIComponent(url.substring(7)); }
        catch (_) { throw new Error("A selected file URL is invalid. Choose it again."); }
        if (!path.startsWith("/") || path.includes("\0"))
            throw new Error("Choose files from a local folder.");
        if (!paths.includes(path)) paths.push(path);
    }
    return paths;
}

function summary(paths, sizeLabel) {
    if (!paths.length) return "No files selected";
    const name = paths.length === 1 ? paths[0].substring(paths[0].lastIndexOf("/") + 1) : paths.length + " files selected";
    return name + (sizeLabel ? " · " + sizeLabel : "");
}
