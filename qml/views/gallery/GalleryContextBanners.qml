import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

ColumnLayout {
    id: contextBanners
    required property var view
    Layout.fillWidth: true
    Layout.fillHeight: false
    visible: privacyBanner.shown || privacyBanner.reveal > 0.01
          || openPostBanner.shown || openPostBanner.reveal > 0.01
          || charFilterBanner.shown || charFilterBanner.reveal > 0.01
          || virtualBucketBanner.shown || virtualBucketBanner.reveal > 0.01
          || selectionActionBanner.shown || selectionActionBanner.reveal > 0.01
    spacing: 8

    Rectangle {
        id: privacyBanner
        Layout.fillWidth: true
        readonly property bool shown: contextBanners.view.privacyBlur
        property real reveal: shown ? 1 : 0
        Behavior on reveal { SpringAnimation { spring: 4.2; damping: 0.34; mass: 1.0; epsilon: 0.001 } }
        implicitHeight: 30
        Layout.preferredHeight: 30 * Math.max(0, reveal)
        visible: reveal > 0.01
        opacity: Math.max(0, Math.min(1, reveal))
        clip: true
        radius: 6
        color: "#2A2210"
        border.color: "#F59E0B"
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 10
            anchors.rightMargin: 6
            spacing: 8
            Text { text: "🙈"; font.pixelSize: 13 }
            Text {
                Layout.fillWidth: true
                text: "Privacy blur is on: thumbnails and previews are hidden."
                elide: Text.ElideRight
                font.family: "Segoe UI, sans-serif"; font.pixelSize: 11; font.weight: 600; color: "#FDE68A"
            }
            GalleryActionChip {
                icon: "👁"; label: "Show them"
                tip: "Turn the privacy blur off (Ctrl+H)"
                onTriggered: contextBanners.view.togglePrivacy()
            }
        }
    }

    // 4a. OPEN POST BAR (while looking inside a grouped post)
    Rectangle {
        id: openPostBanner
        Layout.fillWidth: true
        readonly property bool shown: contextBanners.view.openGroupKey.length > 0
        property real reveal: shown ? 1 : 0
        Behavior on reveal { SpringAnimation { spring: 4.2; damping: 0.34; mass: 1.0; epsilon: 0.001 } }
        implicitHeight: 30
        Layout.preferredHeight: 30 * Math.max(0, reveal)
        visible: reveal > 0.01
        opacity: Math.max(0, Math.min(1, reveal))
        clip: true
        radius: 6
        color: "#1A1430"
        border.color: "#A78BFA"
        border.width: 1
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 6
            anchors.rightMargin: 10
            spacing: 8
            GalleryActionChip {
                icon: "◂"; label: "All posts"
                tip: "Back to all posts (Backspace)"
                onTriggered: contextBanners.view.closeGroup()
            }
            Text {
                Layout.fillWidth: true
                text: "🗂 " + contextBanners.view.openGroupTitle + "  •  " + contextBanners.view.filteredItems.length + " files  •  post " + contextBanners.view.openGroupKey
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                font.weight: 600
                color: "#DDD6FE"
                elide: Text.ElideRight
            }
        }
    }

    // 4a2. CHARACTER FILTER BAR
    Rectangle {
        id: charFilterBanner
        Layout.fillWidth: true
        readonly property bool shown: contextBanners.view.characterFilter.length > 0
        property real reveal: shown ? 1 : 0
        Behavior on reveal { SpringAnimation { spring: 4.2; damping: 0.34; mass: 1.0; epsilon: 0.001 } }
        implicitHeight: 30
        Layout.preferredHeight: 30 * Math.max(0, reveal)
        visible: reveal > 0.01
        opacity: Math.max(0, Math.min(1, reveal))
        clip: true
        radius: 6
        color: "#0F2A22"
        border.color: "#34D399"
        border.width: 1
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 6
            spacing: 8
            Text {
                Layout.fillWidth: true
                text: "👤 " + contextBanners.view.characterFilter + "  •  " + contextBanners.view.shownItemCount + (contextBanners.view.shownItemCount === 1 ? " file" : " files")
                      + (contextBanners.view.tagging ? ("  •  still scanning names (" + contextBanners.view.taggingCurrent + "/" + contextBanners.view.taggingTotal + ")…") : "")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                font.weight: 600
                color: "#A7F3D0"
                elide: Text.ElideRight
            }
            GalleryActionChip {
                visible: contextBanners.view.tagging
                icon: "⏹"; label: "Stop scan"
                tip: "Stop scanning and free AI model from VRAM"
                onTriggered: contextBanners.view.cancelTagging()
            }
            GalleryActionChip {
                icon: "✕"; label: "Clear filter"
                tip: "Show every file again"
                onTriggered: contextBanners.view.setCharacterFilter("")
            }
        }
    }

    // 4a3. VIRTUAL SORT BUCKET FILTER BAR (while previewing a virtual sort bucket in Gallery)
    Rectangle {
        id: virtualBucketBanner
        Layout.fillWidth: true
        readonly property bool shown: contextBanners.view.virtualBucketName.length > 0
        property real reveal: shown ? 1 : 0
        Behavior on reveal { SpringAnimation { spring: 4.2; damping: 0.34; mass: 1.0; epsilon: 0.001 } }
        implicitHeight: 30
        Layout.preferredHeight: 30 * Math.max(0, reveal)
        visible: reveal > 0.01
        opacity: Math.max(0, Math.min(1, reveal))
        clip: true
        radius: 6
        color: "#1E1B4B"
        border.color: "#818CF8"
        border.width: 1
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 6
            spacing: 8
            Text {
                Layout.fillWidth: true
                text: "✨ Virtual Sort Bucket: " + contextBanners.view.virtualBucketName + "  •  " + contextBanners.view.shownItemCount + (contextBanners.view.shownItemCount === 1 ? " file" : " files") + " (preview only — no disk changes)"
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                font.weight: 600
                color: "#C7D2FE"
                elide: Text.ElideRight
            }
            GalleryActionChip {
                icon: "✨"; label: "Reopen Sorter"
                tip: "Reopen the Visual Sorter sandbox"
                onTriggered: contextBanners.view.openVisualSorter()
            }
            GalleryActionChip {
                icon: "✕"; label: "Clear virtual filter"
                tip: "Show every file in the folder again"
                onTriggered: contextBanners.view.setVirtualBucketFilter("", [])
            }
        }
    }

    // 4b. SELECTION ACTION BAR (visible while items are selected)
    // Left: what's selected + selection links. Right, grouped: organize | archive | More, Delete.
    Rectangle {
        id: selectionActionBanner
        Layout.fillWidth: true
        readonly property bool shown: contextBanners.view.selectionCount > 0
        property real reveal: shown ? 1 : 0
        Behavior on reveal { SpringAnimation { spring: 4.2; damping: 0.34; mass: 1.0; epsilon: 0.001 } }
        implicitHeight: 34
        Layout.preferredHeight: 34 * Math.max(0, reveal)
        visible: reveal > 0.01
        opacity: Math.max(0, Math.min(1, reveal))
        clip: true
        radius: 6
        color: "#112033"
        border.color: "#38BDF8"
        border.width: 1

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 6
            spacing: 6

            Text {
                text: "☑ " + contextBanners.view.selectionCount + (contextBanners.view.showSelectedWord ? " selected" : "")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                font.weight: 700
                color: "#38BDF8"
            }
            Text {
                readonly property real selSize: contextBanners.view.selectionCount > 0 ? contextBanners.view.totalSize(contextBanners.view.selectedItems()) : 0
                visible: selSize > 0 && contextBanners.view.showSelSize
                text: "·  " + contextBanners.view.formatBytes(selSize)
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 10
                color: "#94A3B8"
            }

            // Selection links sit with the count they change
            Row {
                visible: contextBanners.view.showSelLinks
                spacing: 12
                Layout.leftMargin: 8
                GallerySelLink { label: "Select all"; tip: "Select every item shown (Ctrl+A)"; onTriggered: contextBanners.view.selectAll() }
                GallerySelLink { label: "Clear"; tip: "Clear the selection (Esc)"; onTriggered: contextBanners.view.clearSelection() }
            }

            Item { Layout.fillWidth: true }

            // Organize
            GalleryActionChip {
                compact: !contextBanners.view.showChipLabels
                icon: "→"; label: "Move to…"
                tip: "Move the selected items into another folder. Existing files are never overwritten."
                onTriggered: contextBanners.view.moveItemsToFolder(contextBanners.view.selectedItems())
            }
            GalleryActionChip {
                compact: !contextBanners.view.showChipLabels
                visible: !!contextBanners.view.archiver
                icon: "⧉"; label: "Copy to…"
                tip: "Copy the selected items into another folder. Existing files are never overwritten."
                onTriggered: contextBanners.view.copyItemsToFolder(contextBanners.view.selectedItems())
            }

            GalleryBarDivider { visible: !!contextBanners.view.archiver }

            // Archive
            GalleryActionChip {
                compact: !contextBanners.view.showChipLabels
                visible: !!contextBanners.view.archiver && contextBanners.view.selectionHasArchive
                icon: "⊟"; label: "Extract"
                tip: "Extract the selected archives (ZIP, 7Z, RAR, TAR…), each into its own folder"
                onTriggered: contextBanners.view.extractItems(contextBanners.view.selectedItems(), false)
            }
            GalleryActionChip {
                compact: !contextBanners.view.showChipLabels
                visible: !!contextBanners.view.archiver
                icon: "⊞"; label: "Compress"
                tip: "Pack the selected files and folders into a ZIP or 7Z archive, or one archive per item"
                onTriggered: contextBanners.view.compressItems(contextBanners.view.selectedItems())
            }

            GalleryBarDivider {}

            // Everything else, then the one destructive action on its own
            GalleryActionChip {
                id: moreChip
                compact: !contextBanners.view.showChipLabels
                icon: "⋯"; label: "More"
                tip: "Open, show in Explorer, copy path, rename…"
                onTriggered: contextBanners.view.openMoreMenu(moreChip)
            }
            GalleryActionChip {
                compact: !contextBanners.view.showChipLabels
                icon: "🗑"; label: "Delete"; danger: true
                tip: "Move the selected items to the Recycle Bin (Delete key). You can restore them from there."
                onTriggered: contextBanners.view.deleteItems(contextBanners.view.selectedItems())
            }
        }
    }
}
