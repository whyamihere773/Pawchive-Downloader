import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

Item {
    id: galleryDialogs
    required property var view
    anchors.fill: parent
    z: 9000

    property alias deleteConfirm: deleteConfirm
    property alias renameDialog: renameDialog
    property alias renameField: renameField

    Item {
        id: deleteConfirm
        property bool isOpen: false
        property var items: []
        anchors.fill: parent
        z: 9000
        // Fades in / out; no input while closing
        opacity: isOpen ? 1 : 0
        visible: opacity > 0.005
        enabled: isOpen
        Behavior on opacity { NumberAnimation { duration: 170; easing.type: Easing.OutCubic } }

        function show(list) {
            items = list
            isOpen = true
            deleteKeys.forceActiveFocus()
        }
        function close() {
            isOpen = false
            items = []
        }
        function confirm() {
            if (!galleryDialogs.view.bridge || !items.length) { close(); return }
            var paths = galleryDialogs.view._pathsOf(items)
            var res = galleryDialogs.view.bridge.deleteItems(paths)
            close()
            if (res.failed > 0) {
                galleryDialogs.view.showToast("Moved " + res.deleted + " to the Recycle Bin, " + res.failed + " failed: " + (res.errors.length ? res.errors[0] : ""), true)
            } else {
                galleryDialogs.view.showToast("Moved " + res.deleted + (res.deleted === 1 ? " item" : " items") + " to the Recycle Bin", false)
            }
            galleryDialogs.view.refreshPreservingScroll()
        }

        Item {
            id: deleteKeys
            focus: deleteConfirm.isOpen
            Keys.onEscapePressed: deleteConfirm.close()
            Keys.onReturnPressed: deleteConfirm.confirm()
            Keys.onEnterPressed: deleteConfirm.confirm()
        }

        Rectangle {
            anchors.fill: parent
            color: "#060910"
            opacity: 0.85
            MouseArea { anchors.fill: parent; hoverEnabled: true; onClicked: deleteConfirm.close() }
        }

        Rectangle {
            // Heavy panel: settles in on a soft spring
            scale: deleteConfirm.isOpen ? 1.0 : 0.9
            Behavior on scale { SpringAnimation { spring: 3.4; damping: 0.36; mass: 1.6; epsilon: 0.0008 } }
            anchors.centerIn: parent
            width: Math.min(440, parent.width - 40)
            height: delCol.implicitHeight + 32
            radius: 10
            color: "#121725"
            border.color: "#EF4444"
            border.width: 1
            MouseArea { anchors.fill: parent; hoverEnabled: true }

            ColumnLayout {
                id: delCol
                anchors.fill: parent
                anchors.margins: 16
                spacing: 10

                Text {
                    text: "🗑️  Move " + deleteConfirm.items.length + (deleteConfirm.items.length === 1 ? " item" : " items") + " to the Recycle Bin?"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 14
                    font.weight: 700
                    color: "#F8FAFC"
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                }
                Text {
                    Layout.fillWidth: true
                    text: {
                        var list = deleteConfirm.items
                        var names = []
                        for (var i = 0; i < Math.min(5, list.length); i++) names.push((list[i].is_dir ? "📁 " : "• ") + list[i].name)
                        if (list.length > 5) names.push("…and " + (list.length - 5) + " more")
                        return names.join("\n")
                    }
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#CBD5E1"
                    elide: Text.ElideMiddle
                }
                Text {
                    Layout.fillWidth: true
                    readonly property real sz: galleryDialogs.view.totalSize(deleteConfirm.items)
                    text: (sz > 0 ? (galleryDialogs.view.formatBytes(sz) + " • ") : "") + "You can restore these from the Recycle Bin. Folders are moved with everything inside them."
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    color: "#94A3B8"
                    wrapMode: Text.WordWrap
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Item { Layout.fillWidth: true }
                    GalleryActionChip {
                        label: "Cancel"
                        implicitHeight: 28
                        onTriggered: deleteConfirm.close()
                    }
                    GalleryActionChip {
                        icon: "🗑️"; label: "Move to Recycle Bin"; danger: true
                        implicitHeight: 28
                        onTriggered: deleteConfirm.confirm()
                    }
                }
            }
        }
    }

    // ── Rename dialog ───────────────────────────────────────────────────────
    Item {
        id: renameDialog
        property bool isOpen: false
        property var target: null
        property string errorText: ""
        property bool creating: false   // true = "New folder" mode
        anchors.fill: parent
        z: 9000
        opacity: isOpen ? 1 : 0
        visible: opacity > 0.005
        enabled: isOpen
        Behavior on opacity { NumberAnimation { duration: 170; easing.type: Easing.OutCubic } }

        function showCreate() {
            creating = true
            target = null
            errorText = ""
            renameField.text = "New folder"
            isOpen = true
            renameField.forceActiveFocus()
            renameField.selectAll()
        }
        function show(item) {
            creating = false
            target = item
            errorText = ""
            renameField.text = item.name
            isOpen = true
            renameField.forceActiveFocus()
            // Select the name without its extension, like Explorer
            var dot = item.is_dir ? -1 : item.name.lastIndexOf(".")
            renameField.select(0, dot > 0 ? dot : item.name.length)
        }
        function close() {
            isOpen = false
            target = null
        }
        function confirm() {
            if (creating) {
                var res0 = galleryDialogs.view.tools.createFolder(galleryDialogs.view.currentPath, renameField.text.trim())
                if (!res0.success) {
                    errorText = res0.error
                    return
                }
                close()
                galleryDialogs.view.showToast("Created folder " + renameField.text.trim(), false, true)
                galleryDialogs.view.pendingRevealPath = res0.path
                galleryDialogs.view.refreshPreservingScroll()
                return
            }
            if (!galleryDialogs.view.bridge || !target) { close(); return }
            var newName = renameField.text.trim()
            if (newName === target.name) { close(); return }
            var res = galleryDialogs.view.tools ? galleryDialogs.view.tools.renameItem(target.path, newName) : galleryDialogs.view.bridge.renameItem(target.path, newName)
            if (!res.success) {
                errorText = res.error
                return
            }
            close()
            galleryDialogs.view.showToast("Renamed to " + newName, false, true)
            galleryDialogs.view.refreshPreservingScroll()
        }

        Rectangle {
            anchors.fill: parent
            color: "#060910"
            opacity: 0.85
            MouseArea { anchors.fill: parent; hoverEnabled: true; onClicked: renameDialog.close() }
        }

        Rectangle {
            // Heavy panel: settles in on a soft spring
            scale: renameDialog.isOpen ? 1.0 : 0.9
            Behavior on scale { SpringAnimation { spring: 3.4; damping: 0.36; mass: 1.6; epsilon: 0.0008 } }
            anchors.centerIn: parent
            width: Math.min(460, parent.width - 40)
            height: renCol.implicitHeight + 32
            radius: 10
            color: "#121725"
            border.color: "#38BDF8"
            border.width: 1
            MouseArea { anchors.fill: parent; hoverEnabled: true }

            ColumnLayout {
                id: renCol
                anchors.fill: parent
                anchors.margins: 16
                spacing: 10

                Text {
                    text: renameDialog.creating ? "📁  New folder" : ("✏️  Rename " + (renameDialog.target && renameDialog.target.is_dir ? "folder" : "file"))
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 14
                    font.weight: 700
                    color: "#F8FAFC"
                }

                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 32
                    radius: 6
                    color: renameField.activeFocus ? "#0B0D12" : "#0D1018"
                    border.color: renameDialog.errorText ? "#EF4444" : (renameField.activeFocus ? "#38BDF8" : (renameBoxMouse.containsMouse ? "#475569" : "#252D3E"))
                    border.width: renameField.activeFocus ? 1.5 : 1

                    TextBarContextArea {
                        id: renameBoxMouse
                        target: renameField
                        focusOnLeftClick: true
                    }

                    TextInput {
                        id: renameField
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        verticalAlignment: TextInput.AlignVCenter
                        color: "#F8FAFC"
                        selectionColor: "#0284C7"
                        selectedTextColor: "#FFFFFF"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        selectByMouse: true
                        clip: true
                        TextBarContextArea {}
                        onTextChanged: renameDialog.errorText = ""
                        Keys.onReturnPressed: renameDialog.confirm()
                        Keys.onEnterPressed: renameDialog.confirm()
                        Keys.onEscapePressed: renameDialog.close()
                    }
                }

                Text {
                    visible: renameDialog.errorText.length > 0
                    Layout.fillWidth: true
                    text: "⚠ " + renameDialog.errorText
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 10
                    color: "#F87171"
                    wrapMode: Text.WordWrap
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Item { Layout.fillWidth: true }
                    GalleryActionChip {
                        label: "Cancel"
                        implicitHeight: 28
                        onTriggered: renameDialog.close()
                    }
                    GalleryActionChip {
                        icon: "✔"; label: renameDialog.creating ? "Create" : "Rename"
                        implicitHeight: 28
                        onTriggered: renameDialog.confirm()
                    }
                }
            }
        }
    }
}
