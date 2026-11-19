.pragma library

var IMAGE_EXTS = [
    ".jpg", ".jpeg", ".jpe", ".jfif", ".pjpeg", ".pjp", ".png", ".apng", ".gif", ".webp",
    ".avif", ".heic", ".heif", ".jxl", ".bmp", ".dib", ".svg", ".svgz", ".ico", ".cur",
    ".tif", ".tiff", ".tga", ".psd", ".jp2", ".j2k", ".dds", ".qoi", ".pcx", ".ppm",
    ".pgm", ".pbm", ".xbm", ".xpm", ".icns", ".wbmp"
]

var VIDEO_EXTS = [
    ".mp4", ".m4v", ".mkv", ".webm", ".mov", ".avi", ".flv", ".f4v", ".wmv", ".asf",
    ".mpg", ".mpeg", ".m2v", ".ts", ".mts", ".m2ts", ".3gp", ".3g2", ".ogv", ".vob", ".divx"
]

var AUDIO_EXTS = [
    ".mp3", ".flac", ".wav", ".ogg", ".oga", ".m4a", ".aac", ".opus", ".wma",
    ".aiff", ".aif", ".alac", ".mka"
]

var ARCHIVE_EXTS = [
    ".7z", ".zip", ".zipx", ".rar", ".tar", ".gz", ".tgz", ".bz2", ".tbz2", ".tbz",
    ".xz", ".txz", ".zst", ".tzst", ".cab", ".lzma", ".iso"
]

var CATEGORY_ARCHIVE_EXTS = [
    ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".zst", ".tgz", ".cab", ".iso"
]

function formatBytes(bytes) {
    if (!bytes || bytes <= 0) return "0 B"
    var k = 1024
    var sizes = ["B", "KB", "MB", "GB", "TB"]
    var i = Math.floor(Math.log(bytes) / Math.log(k))
    if (i < 0) i = 0
    if (i >= sizes.length) i = sizes.length - 1
    return (bytes / Math.pow(k, i)).toFixed(i === 0 ? 0 : 1) + " " + sizes[i]
}

function formatDate(ts) {
    if (!ts || ts <= 0) return ""
    var d = new Date(ts * 1000)
    var yr = d.getFullYear()
    var mo = ("0" + (d.getMonth() + 1)).slice(-2)
    var da = ("0" + d.getDate()).slice(-2)
    var hr = ("0" + d.getHours()).slice(-2)
    var mn = ("0" + d.getMinutes()).slice(-2)
    return yr + "-" + mo + "-" + da + "  " + hr + ":" + mn
}

function getCategory(ext) {
    if (!ext) return "other"
    ext = ext.toLowerCase()
    if (IMAGE_EXTS.indexOf(ext) >= 0) return "image"
    if (VIDEO_EXTS.indexOf(ext) >= 0) return "video"
    if (CATEGORY_ARCHIVE_EXTS.indexOf(ext) >= 0) return "archive"
    if (AUDIO_EXTS.indexOf(ext) >= 0) return "audio"
    return "other"
}

function getItemIcon(item) {
    if (item.is_group) return "🗂"
    if (item.is_dir) return "📁"
    var cat = getCategory(item.ext)
    if (cat === "image") return "🖼️"
    if (cat === "video") return "🎬"
    if (cat === "archive") return "📦"
    if (cat === "audio") return "🎵"
    return "📄"
}

function getItemColor(item) {
    if (item.is_dir) return "#38BDF8"
    var cat = getCategory(item.ext)
    if (cat === "image") return "#EC4899"
    if (cat === "video") return "#8B5CF6"
    if (cat === "archive") return "#F59E0B"
    if (cat === "audio") return "#10B981"
    return "#94A3B8"
}

function formatFolderSize(item) {
    if (!item) return ""
    if (item.is_group) return formatBytes(item.size)
    if (!item.is_dir) return formatBytes(item.size)
    if (item.size >= 0) return formatBytes(item.size)
    if (item.child_count >= 0) return item.child_count + (item.child_count === 1 ? " item" : " items")
    return "Calculating…"
}

function formatFolderSubtitle(item) {
    if (!item) return ""
    if (!item.is_dir) return formatDate(item.mtime)
    if (item.file_count >= 0) {
        var txt = item.file_count + (item.file_count === 1 ? " file" : " files")
        if (item.folder_count > 0) {
            txt += " • " + item.folder_count + (item.folder_count === 1 ? " dir" : " dirs")
        }
        if (item.size >= 0) {
            txt += " • " + formatBytes(item.size)
        }
        return txt
    }
    if (item.child_count >= 0) {
        return item.child_count + (item.child_count === 1 ? " item" : " items") + " • Calculating size…"
    }
    return "Folder • Calculating size…"
}

function withFolderStats(item, st, pv) {
    var out = {}
    for (var k in item) out[k] = item[k]
    if (st) {
        out.size = st.size
        out.file_count = st.file_count
        out.folder_count = st.folder_count
    }
    if (pv !== undefined) {
        out.previews = pv
    }
    return out
}

function samePlace(a, b) {
    var na = (a || "").replace(/[\\\/]+$/, "").toLowerCase()
    var nb = (b || "").replace(/[\\\/]+$/, "").toLowerCase()
    return na === nb
}

function markKey(path, isWindows) {
    var p = path || ""
    return isWindows ? p.toLowerCase() : p
}

function starText(n) {
    var t = ""
    for (var i = 0; i < 5; i++) t += i < n ? "★" : "☆"
    return t
}

function characterCounts(sortedItems, charTags) {
    var counts = {}, display = {}
    var list = sortedItems || []
    for (var i = 0; i < list.length; i++) {
        var tags = charTags[list[i].path]
        if (!tags || list[i].is_dir) continue
        for (var j = 0; j < tags.length; j++) {
            var k = tags[j].toLowerCase()
            counts[k] = (counts[k] || 0) + 1
            if (!display[k]) display[k] = tags[j]
        }
    }
    var out = []
    for (var key in counts) out.push({ name: display[key], count: counts[key] })
    out.sort(function(a, b) { return b.count - a.count || a.name.localeCompare(b.name) })
    if (out.length > 500) out = out.slice(0, 500)
    return out
}

function hasCharacter(charTags, item, name) {
    var tags = charTags[item.path]
    if (!tags) return false
    var n = name.toLowerCase()
    for (var i = 0; i < tags.length; i++) if (tags[i].toLowerCase() === n) return true
    return false
}

function computeCounts(items) {
    var fc = 0, ic = 0, vc = 0, ac = 0, auc = 0, oc = 0
    var totalFilesSize = 0
    for (var i = 0; i < items.length; i++) {
        var it = items[i]
        if (it.is_dir) {
            fc++
        } else {
            if (it.size > 0) totalFilesSize += it.size
            var cat = getCategory(it.ext)
            if (cat === "image") ic++
            else if (cat === "video") vc++
            else if (cat === "archive") ac++
            else if (cat === "audio") auc++
            else oc++
        }
    }
    return {
        folderCount: fc,
        fileCount: Math.max(0, items.length - fc),
        currentFolderFilesSize: totalFilesSize,
        imageCount: ic,
        videoCount: vc,
        archiveCount: ac,
        audioCount: auc,
        otherCount: oc
    }
}

function naturalKey(name) {
    return (name || "").toLowerCase().match(/\d+|\D+/g) || []
}

function isDigitChunk(s) {
    var c = s.charCodeAt(0)
    return c >= 48 && c <= 57
}

function compareNatural(ka, kb) {
    var n = Math.min(ka.length, kb.length)
    for (var i = 0; i < n; i++) {
        var a = ka[i], b = kb[i]
        if (a === b) continue
        if (isDigitChunk(a) && isDigitChunk(b)) {
            var d = parseFloat(a) - parseFloat(b)
            if (d !== 0) return d < 0 ? -1 : 1
            if (a.length !== b.length) return a.length - b.length
            continue
        }
        return a < b ? -1 : 1
    }
    return ka.length - kb.length
}

function sortItems(list, key, ascending, ratingOfFn) {
    var dir = ascending ? 1 : -1
    var decorated = new Array(list.length)
    for (var i = 0; i < list.length; i++) {
        decorated[i] = { it: list[i], nk: naturalKey(list[i].name), i: i }
    }
    decorated.sort(function(a, b) {
        if (a.it.is_dir !== b.it.is_dir) return a.it.is_dir ? -1 : 1
        var c = 0
        if (key === "date") c = (a.it.mtime || 0) - (b.it.mtime || 0)
        else if (key === "rating") c = ratingOfFn(a.it) - ratingOfFn(b.it)
        else if (key === "size") c = (a.it.size || 0) - (b.it.size || 0)
        else if (key === "type") {
            var ea = a.it.ext || "", eb = b.it.ext || ""
            c = ea < eb ? -1 : (ea > eb ? 1 : 0)
        }
        if (c === 0) c = compareNatural(a.nk, b.nk)
        if (c === 0) c = a.i - b.i
        return c * dir
    })
    var out = new Array(decorated.length)
    for (var j = 0; j < decorated.length; j++) out[j] = decorated[j].it
    return out
}

function sortLabel(key) {
    if (key === "date") return "Date modified"
    if (key === "size") return "Size"
    if (key === "type") return "Type"
    if (key === "rating") return "Rating"
    return "Name"
}

function postKey(item) {
    if (!item || item.is_dir || item.is_group) return ""
    var m = /^(\d{5,})_/.exec(item.name || "")
    return m ? m[1] : ""
}

function postTitleFromName(name) {
    var t = (name || "").replace(/^\d{5,}_/, "")
    var dot = t.lastIndexOf(".")
    if (dot > 0) t = t.substring(0, dot)
    t = t.replace(/_[0-9a-f]{4,8}(_\d+)?$/i, "").replace(/ \(\d+\)$/, "")
    t = t.replace(/_ /g, ": ").replace(/_/g, " ").replace(/\s+/g, " ").trim()
    return t || "Untitled post"
}

function stackTitle(members) {
    for (var i = 0; i < members.length; i++) {
        if (!/^\d{5,}_embed_\d+_/i.test(members[i].name)) return postTitleFromName(members[i].name)
    }
    return postTitleFromName(members[0].name)
}

function groupByPost(list) {
    var groups = {}
    var order = []
    for (var i = 0; i < list.length; i++) {
        var it = list[i]
        var key = postKey(it)
        if (!key) { order.push(it); continue }
        if (!groups[key]) {
            groups[key] = { key: key, members: [] }
            order.push(groups[key])
        }
        groups[key].members.push(it)
    }
    var out = []
    for (var j = 0; j < order.length; j++) {
        var g = order[j]
        if (!g.members) { out.push(g); continue }
        if (g.members.length === 1) { out.push(g.members[0]); continue }
        var size = 0, mtime = 0, cover = null
        for (var k = 0; k < g.members.length; k++) {
            var m = g.members[k]
            if (m.size > 0) size += m.size
            if (m.mtime > mtime) mtime = m.mtime
            var cat = getCategory(m.ext)
            if (!cover && (cat === "image" || cat === "video")) cover = m
        }
        out.push({
            is_group: true, is_dir: false, group_key: g.key,
            name: stackTitle(g.members),
            path: "post:" + g.key, ext: "", size: size, mtime: mtime,
            members: g.members, cover: cover || g.members[0],
            file_count: g.members.length, folder_count: 0, child_count: g.members.length,
            rel_dir: g.members[0].rel_dir || ""
        })
    }
    return out
}

function displayDir(d) {
    if (!d) return ""
    var parts = d.split(/[\\/]+/).filter(function(x) { return x.length > 0 })
    var absolute = d.indexOf(":") === 1 || d.indexOf("\\\\") === 0 || d.charAt(0) === "/"
    return (absolute && parts.length > 2) ? ("…\\" + parts.slice(-2).join("\\")) : d
}

function thumbUrl(item) {
    if (typeof item === "string") {
        return "image://thumb/" + encodeURIComponent(item)
    }
    return "image://thumb/" + encodeURIComponent(item.path) + "?m=" + Math.round(item.mtime || 0)
}

function folderName(p) {
    var t = (p || "").replace(/[\\\/]+$/, "")
    return t.substring(Math.max(t.lastIndexOf("\\"), t.lastIndexOf("/")) + 1) || t
}

function isSpacer(it) {
    return !!it && (!!it.is_header || !!it.is_filler)
}

function dateBucket(ts) {
    if (!ts || ts <= 0) return { key: "unknown", label: "Unknown date" }
    var now = new Date()
    var today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime() / 1000
    if (ts >= today) return { key: "today", label: "Today" }
    if (ts >= today - 86400) return { key: "yesterday", label: "Yesterday" }
    var weekStart = today - ((now.getDay() + 6) % 7) * 86400
    if (ts >= weekStart) return { key: "week", label: "Earlier this week" }
    var monthStart = new Date(now.getFullYear(), now.getMonth(), 1).getTime() / 1000
    if (ts >= monthStart) return { key: "month", label: "Earlier this month" }
    var d = new Date(ts * 1000)
    if (now.getFullYear() - d.getFullYear() <= 1)
        return { key: "m" + d.getFullYear() + "-" + d.getMonth(), label: Qt.formatDate(d, "MMMM yyyy") }
    return { key: "y" + d.getFullYear(), label: "" + d.getFullYear() }
}

function groupByDate(list, sortKey, sortAscending, isGrid, cols) {
    var folders = [], sections = {}, order = []
    for (var i = 0; i < list.length; i++) {
        var it = list[i]
        if (it.is_dir) { folders.push(it); continue }
        var b = dateBucket(it.mtime)
        if (!sections[b.key]) { sections[b.key] = { label: b.label, items: [], newest: 0 }; order.push(b.key) }
        sections[b.key].items.push(it)
        sections[b.key].newest = Math.max(sections[b.key].newest, it.mtime || 0)
    }
    var oldestFirst = sortKey === "date" && sortAscending
    order.sort(function(a, b) { var d = sections[b].newest - sections[a].newest; return oldestFirst ? -d : d })
    var out = []
    function addSection(key, label, icon, items) {
        if (!items.length) return
        var paths = []
        for (var k = 0; k < items.length; k++) paths.push(items[k].path)
        out.push({ is_header: true, path: "::section:" + key, name: label, icon: icon, count: items.length,
                   sectionPaths: paths, ext: "", is_dir: false, size: 0, mtime: 0 })
        for (var m = 0; m < items.length; m++) out.push(items[m])
        if (isGrid) {
            var pad = (cols - ((items.length + 1) % cols)) % cols
            for (var f = 0; f < pad; f++) out.push({ is_filler: true, path: "::filler:" + key + ":" + f, name: "", ext: "", is_dir: false, size: 0, mtime: 0 })
        }
    }
    addSection("folders", "Folders", "📁", folders)
    for (var o = 0; o < order.length; o++) addSection(order[o], sections[order[o]].label, "📅", sections[order[o]].items)
    return out
}

function totalSize(items) {
    var s = 0
    for (var i = 0; i < items.length; i++) {
        if (items[i].size > 0) s += items[i].size
    }
    return s
}

function isMedia(item) {
    if (!item || item.is_dir) return false
    var cat = getCategory(item.ext)
    return cat === "image" || cat === "video" || cat === "audio"
}

function pathsOf(items) {
    var out = []
    for (var i = 0; i < items.length; i++) out.push(items[i].path)
    return out
}

function urlToPath(u, isWindows) {
    var s = u.toString()
    if (s.indexOf("file:///") === 0) s = s.substring(8)
    else if (s.indexOf("file://") === 0) s = "//" + s.substring(7)
    else return ""
    s = decodeURIComponent(s)
    if (isWindows) s = s.replace(/\//g, "\\")
    else if (s.charAt(0) !== "/") s = "/" + s
    return s
}

function isArchive(item) {
    if (!item || item.is_dir) return false
    var lower = (item.name || "").toLowerCase()
    if (lower.length > 4 && lower.substring(lower.length - 4) === ".001") return true
    return ARCHIVE_EXTS.indexOf((item.ext || "").toLowerCase()) >= 0
}

function archivesIn(items) {
    var out = []
    for (var i = 0; i < items.length; i++) if (isArchive(items[i])) out.push(items[i])
    return out
}

function parseQuery(text) {
    var words = [], exts = []
    var toks = (text || "").toLowerCase().split(/\s+/)
    for (var i = 0; i < toks.length; i++) {
        var t = toks[i]
        if (!t) continue
        if (t.indexOf("ext:") === 0) t = "." + t.substring(4).replace(/^\.+/, "")
        else if (t.indexOf("*.") === 0) t = t.substring(1)
        if (t.charAt(0) === "." && t.length > 1) exts.push(t)
        else words.push(t)
    }
    return { words: words, exts: exts }
}

function matchesQuery(item, pq) {
    if (!pq.words.length && !pq.exts.length) return true
    var lower = (item.name || "").toLowerCase()
    if (pq.exts.length) {
        if (item.is_dir) return false
        var ok = false
        for (var i = 0; i < pq.exts.length; i++) {
            var e = pq.exts[i]
            if (lower.length >= e.length && lower.substring(lower.length - e.length) === e) { ok = true; break }
        }
        if (!ok) return false
    }
    for (var j = 0; j < pq.words.length; j++) if (lower.indexOf(pq.words[j]) === -1) return false
    return true
}

function filterAndGroupItems(sortedItems, opts) {
    var list = sortedItems || []
    var cat = opts.activeCategory
    var pq = parseQuery(opts.searchFilter)
    var filtered = []
    for (var i = 0; i < list.length; i++) {
        var it = list[i]
        if (cat === "folders" && !it.is_dir) continue
        if (cat === "images" && (it.is_dir || getCategory(it.ext) !== "image")) continue
        if (cat === "videos" && (it.is_dir || getCategory(it.ext) !== "video")) continue
        if (cat === "archives" && (it.is_dir || getCategory(it.ext) !== "archive")) continue
        if (cat === "audio" && (it.is_dir || getCategory(it.ext) !== "audio")) continue

        if (opts.characterFilter && (it.is_dir || !hasCharacter(opts.charTags, it, opts.characterFilter))) continue

        if (opts.virtualBucketName.length > 0) {
            if (it.is_dir) continue
            var normItPath = String(it.path || "").replace(/\\/g, "/").toLowerCase()
            if (!opts.virtualBucketPaths[normItPath]) continue
        }

        if (!opts.recursive && !matchesQuery(it, pq)) continue

        filtered.push(it)
    }
    if (opts.openGroupKey) {
        var inside = []
        for (var g = 0; g < filtered.length; g++) if (postKey(filtered[g]) === opts.openGroupKey) inside.push(filtered[g])
        filtered = inside
    } else if (opts.groupByPost) {
        filtered = groupByPost(filtered)
    } else if (opts.groupByDate) {
        filtered = groupByDate(filtered, opts.sortKey, opts.sortAscending, opts.isGrid, opts.gridColumns)
    }
    var shown = 0
    for (var c = 0; c < filtered.length; c++) if (!isSpacer(filtered[c])) shown++
    return { filtered: filtered, shown: shown }
}

function scrollTo(view, anim, y) {
    var top = view.originY
    var bottom = view.originY + Math.max(0, view.contentHeight - view.height)
    var target = Math.max(top, Math.min(bottom, y))
    anim.stop()
    anim.from = view.contentY
    anim.to = target
    anim.start()
}

function wheelScroll(root, view, anim, event, rowH, rowsPerNotch) {
    var current = anim.running ? anim.to : view.contentY
    if (event.pixelDelta.y !== 0 && event.angleDelta.y % 120 !== 0) {
        view.contentY = Math.max(view.originY, Math.min(view.originY + Math.max(0, view.contentHeight - view.height), view.contentY - event.pixelDelta.y))
        return
    }
    var now = Date.now()
    root._wheelStreak = (now - root._lastWheelMs < 160) ? root._wheelStreak + 1 : 0
    root._lastWheelMs = now
    var totalRows = view.contentHeight / Math.max(1, rowH)
    var cap = Math.max(3, Math.min(40, totalRows / 25))
    var speed = Math.min(cap, Math.pow(1.25, root._wheelStreak))
    var notches = event.angleDelta.y / 120
    scrollTo(view, anim, current - notches * rowsPerNotch * rowH * speed)
}

function jumpToPrefix(root, view, list, prefix, start) {
    for (var n = 0; n < list.length; n++) {
        var i = ((start + n) % list.length + list.length) % list.length
        if (!isSpacer(list[i]) && (list[i].name || "").toLowerCase().indexOf(prefix) === 0) {
            view.currentIndex = i
            root.selectOnly(list[i].path, i)
            return true
        }
    }
    return false
}

function typeAhead(root, view, ch) {
    var list = root.filteredItems || []
    if (!list.length) return
    var c = ch.toLowerCase()
    var fresh = !root._typeAheadActive()
    var buf = fresh ? c : root._typeBuffer + c
    root._typeBuffer = buf
    root._typeLastMs = Date.now()

    var sameLetter = true
    for (var k = 0; k < buf.length; k++) if (buf.charAt(k) !== c) { sameLetter = false; break }
    var prefix = sameLetter ? c : buf
    var cur = view.currentIndex
    if (jumpToPrefix(root, view, list, prefix, (fresh || sameLetter) ? cur + 1 : Math.max(0, cur))) return
    if (prefix !== c) {
        root._typeBuffer = c
        jumpToPrefix(root, view, list, c, cur + 1)
    }
}

function followKeyboard(root, view, rangeFrom, focusOnly, fromIndex) {
    var list = root.filteredItems || []
    var i = view.currentIndex
    if (i >= 0 && i < list.length && list[i].is_filler) {
        var dir = (fromIndex !== undefined && fromIndex > i) ? -1 : 1
        var j = i
        while (j >= 0 && j < list.length && list[j].is_filler) j += dir
        if (j < 0 || j >= list.length) { j = i; while (j >= 0 && list[j].is_filler) j-- }
        if (j >= 0) view.currentIndex = j
        i = view.currentIndex
    }
    if (focusOnly || i < 0 || i >= list.length || isSpacer(list[i])) return
    if (rangeFrom >= 0) {
        root.selectRange(rangeFrom, i, false)
        root.selectionAnchor = rangeFrom
    } else {
        root.selectOnly(list[i].path, i)
    }
}

function handleBrowserKey(root, view, event, gridView, gridScrollAnim, listScrollAnim) {
    var list = root.filteredItems || []
    var isArrow = event.key === Qt.Key_Right || event.key === Qt.Key_Down || event.key === Qt.Key_Left || event.key === Qt.Key_Up
    var ctrl = (event.modifiers & Qt.ControlModifier) !== 0
    var shift = (event.modifiers & Qt.ShiftModifier) !== 0
    var alt = (event.modifiers & Qt.AltModifier) !== 0
    root.keyboardNav = true

    if (isArrow || event.key === Qt.Key_Home || event.key === Qt.Key_End) {
        root._typeBuffer = ""
        if (!list.length) { event.accepted = true; return }
        if (event.key === Qt.Key_Home || event.key === Qt.Key_End) {
            view.currentIndex = event.key === Qt.Key_Home ? 0 : list.length - 1
            event.accepted = true
        } else if (view.currentIndex < 0 || view.currentIndex >= list.length || root.selectionCount === 0) {
            if (view.currentIndex < 0 || view.currentIndex >= list.length) view.currentIndex = 0
            event.accepted = true
        }
        var from = root.selectionAnchor >= 0 ? root.selectionAnchor : view.currentIndex
        var before = view.currentIndex
        Qt.callLater(function() { followKeyboard(root, view, shift ? from : -1, ctrl, before) })
        return
    }

    var cur = view.currentIndex
    if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
        if (cur >= 0 && cur < list.length) root.openItem(list[cur])
        event.accepted = true
    } else if (event.key === Qt.Key_Space && !root._typeAheadActive()) {
        if (cur >= 0 && cur < list.length) {
            root.toggleSelection(list[cur].path)
            root.selectionAnchor = cur
        }
        event.accepted = true
    } else if (event.key === Qt.Key_Backspace) {
        if (root.openGroupKey) root.closeGroup()
        else root.navigateUp()
        event.accepted = true
    } else if (event.key === Qt.Key_PageDown || event.key === Qt.Key_PageUp) {
        var anim = view === gridView ? gridScrollAnim : listScrollAnim
        var dir = event.key === Qt.Key_PageDown ? 1 : -1
        scrollTo(view, anim, (anim.running ? anim.to : view.contentY) + dir * view.height * 0.9)
        event.accepted = true
    } else if (!ctrl && !alt && event.text.length === 1 && event.text.charCodeAt(0) >= 32 && event.text.charCodeAt(0) !== 127) {
        typeAhead(root, view, event.text)
        event.accepted = true
    }
}
