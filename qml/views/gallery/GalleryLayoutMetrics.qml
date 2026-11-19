import QtQuick

Item {
    id: metrics
    required property var view
    visible: false

    readonly property bool compact: metrics.view.width < 1000          // status bar wording
    readonly property bool veryCompact: metrics.view.width < 700        // status bar disk label
    readonly property bool showTypeColumn: metrics.view.width >= 760    // list view ITEMS / TYPE column
    readonly property real _fitSlack: 16

    FontMetrics { id: fmButton; font.family: "Segoe UI, sans-serif"; font.pixelSize: 10; font.weight: 600 }
    FontMetrics { id: fmDriveName; font.family: "Segoe UI, sans-serif"; font.pixelSize: 10; font.weight: 700 }
    FontMetrics { id: fmDriveSpace; font.family: "Segoe UI, monospace"; font.pixelSize: 9 }
    FontMetrics { id: fmPill; font.pixelSize: 11; font.weight: 600 }
    FontMetrics { id: fmSort; font.family: "Segoe UI, sans-serif"; font.pixelSize: 11; font.weight: 600 }
    FontMetrics { id: fmSelCount; font.family: "Segoe UI, sans-serif"; font.pixelSize: 11; font.weight: 700 }

    // Row 1: drives + action buttons. Button labels win over drive free-space labels.
    readonly property real _row1Avail: metrics.view.width - 20 - 8
    readonly property real _drivesCompactW: {
        var w = 0
        var ds = metrics.view.drives || []
        for (var i = 0; i < ds.length; i++) w += fmDriveName.advanceWidth("💽 " + (ds[i].name || "")) + 16 + 6
        return w
    }
    readonly property real _drivesLabelsW: {
        var w = 0
        var ds = metrics.view.drives || []
        for (var i = 0; i < ds.length; i++) {
            if (ds[i].space_label) w += fmDriveSpace.advanceWidth(ds[i].space_label) + 5
        }
        return w
    }
    readonly property real _actionsIconOnlyW: 216 - 31 + 2 * 11 + 31   // icon-only buttons + view toggle + view options, plus the two group dividers
        + fmButton.advanceWidth("Blurred") + 40 + 11                   // the always-labelled Privacy button and its divider
    readonly property real _actionsLabelsW: {
        var labels = ["New folder", metrics.view.tr("gallery_btn_open_system", "Open in Explorer"), "Batch Rename", "Clean & Organize"]
        var w = 0
        for (var i = 0; i < labels.length; i++) w += fmButton.advanceWidth(labels[i]) + 4
        return w
    }
    readonly property bool showActionLabels: _drivesCompactW + _actionsIconOnlyW + _actionsLabelsW + _fitSlack <= _row1Avail
    readonly property bool showDriveLabels: showActionLabels
        && _drivesCompactW + _drivesLabelsW + _actionsIconOnlyW + _actionsLabelsW + _fitSlack <= _row1Avail

    // Row 3: category pills + sort + search
    readonly property real _row3Avail: metrics.view.width - 20 - 16
    function _pillsWidth(full) {
        var allCount = metrics.view.recursiveActive ? metrics.view.searchResults.length : metrics.view.rawItems.length
        var texts = full
            ? ["All (" + allCount + ")", "📁 Folders (" + metrics.view.folderCount + ")", "🖼️ Images (" + metrics.view.imageCount + ")",
               "🎬 Videos (" + metrics.view.videoCount + ")", "📦 Archives (" + metrics.view.archiveCount + ")", "🎵 Audio (" + metrics.view.audioCount + ")"]
            : ["All (" + allCount + ")", "📁 " + metrics.view.folderCount, "🖼️ " + metrics.view.imageCount,
               "🎬 " + metrics.view.videoCount, "📦 " + metrics.view.archiveCount, "🎵 " + metrics.view.audioCount]
        var w = 0
        for (var i = 0; i < texts.length; i++) w += fmPill.advanceWidth(texts[i]) + 14 + 6
        return w
    }
    readonly property real _pillsFullW: _pillsWidth(true)
    readonly property real _pillsCompactW: _pillsWidth(false)
    readonly property real _sortFullW: fmSort.advanceWidth(metrics.view.sortLabel(metrics.view.sortKey) + "  ▲") + 16 + 18
    readonly property real _sortArrowW: 48
    readonly property bool showZoomSlider: metrics.view.viewMode === "grid" && _pillsCompactW + _sortArrowW + 120 + 112 + _fitSlack <= _row3Avail
    readonly property real _zoomW: (showZoomSlider ? 112 : 0) + 34 + 34   // + group-by-post and character buttons
    readonly property bool showPillLabels: _pillsFullW + _zoomW + _sortFullW + 150 + _fitSlack <= _row3Avail
    readonly property bool showSortLabel: _pillsCompactW + _zoomW + _sortFullW + 120 + _fitSlack <= _row3Avail
    readonly property int searchBoxWidth: {
        var pills = (showPillLabels ? _pillsFullW : _pillsCompactW) + _zoomW
        var sort = showSortLabel ? _sortFullW : _sortArrowW
        if (pills + sort + 200 + _fitSlack <= _row3Avail) return 200
        if (pills + sort + 150 + _fitSlack <= _row3Avail) return 150
        return 120
    }

    // Selection bar: chip labels, then the word "selected", then the size
    readonly property real _selBarAvail: metrics.view.width - 20 - 16
    readonly property bool selectionHasArchive: metrics.view.selectionCount > 0 && metrics.view.archivesIn(metrics.view.selectedItems()).length > 0
    // Bar buttons, left to right: organize | archive | More, Delete
    readonly property var _selChipLabels: {
        var labels = ["Move to…"]
        if (metrics.view.archiver) {
            labels.push("Copy to…")
            if (metrics.view.selectionHasArchive) labels.push("Extract")
            labels.push("Compress")
        }
        return labels.concat(["More", "Delete"])
    }
    readonly property real _selDividersW: (metrics.view.archiver ? 2 : 1) * 13
    readonly property real _selChipsFullW: {
        var w = 0
        for (var i = 0; i < _selChipLabels.length; i++) w += 14 + 4 + fmButton.advanceWidth(_selChipLabels[i]) + 14 + 6
        return w + _selDividersW
    }
    readonly property real _selChipsIconW: _selChipLabels.length * (26 + 6) + _selDividersW
    readonly property real _selCountFullW: fmSelCount.advanceWidth("☑ " + metrics.view.selectionCount + " selected") + 6
    readonly property real _selLinksW: fmButton.advanceWidth("Select all") + fmButton.advanceWidth("Clear") + 44
    readonly property real _selSizeW: 80
    // Collapse order when space runs out: labels -> size -> Select all/Clear links -> the word "selected"
    readonly property bool showChipLabels: _selCountFullW + _selLinksW + _selChipsFullW + _fitSlack <= _selBarAvail
    readonly property real _selChipsW: showChipLabels ? _selChipsFullW : _selChipsIconW
    readonly property bool showSelLinks: _selChipsW + _selCountFullW + _selLinksW + _fitSlack <= _selBarAvail
    readonly property bool showSelectedWord: _selChipsW + _selCountFullW + (showSelLinks ? _selLinksW : 0) + _fitSlack <= _selBarAvail
    readonly property bool showSelSize: showSelectedWord
        && _selChipsW + _selCountFullW + (showSelLinks ? _selLinksW : 0) + _selSizeW + _fitSlack <= _selBarAvail
}
