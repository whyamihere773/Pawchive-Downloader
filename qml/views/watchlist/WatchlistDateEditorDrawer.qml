import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

// ── Inline Date Editor Drawer (Enforces / Converts to YYYY-MM-DD for Pawchive & Kemono)
Item {
    id: dateEditorContainer
    required property var card
    required property var view

    function focusEditor(initialText) {
        dateInput.text = initialText
        dateInput.forceActiveFocus()
    }
    width: parent.width
    height: dateEditorContainer.card.isEditingDate ? dateEditorBg.implicitHeight : 0
    clip: true
    visible: height > 0.5
    opacity: dateEditorContainer.card.isEditingDate ? 1.0 : 0.0

    Behavior on height {
        SpringAnimation {
            spring: 3.2
            damping: 0.35
            mass: 1.0
            epsilon: 0.5
        }
    }
    Behavior on opacity {
        NumberAnimation { duration: 180; easing.type: Easing.OutCubic }
    }

    Rectangle {
        id: dateEditorBg
        width: parent.width
        implicitHeight: dateEditorCol.implicitHeight + 16
        radius: 8
        color: "#080E1B"
        border.color: "#0284C7"
        border.width: 1.2
        y: dateEditorContainer.card.isEditingDate ? 0 : -6
        transformOrigin: Item.Top
        Behavior on y {
            SpringAnimation { spring: 3.5; damping: 0.35; mass: 1.0; epsilon: 0.5 }
        }

        ColumnLayout {
            id: dateEditorCol
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 10
            spacing: 8

            readonly property string validationResult: {
                if (!dateEditorContainer.card.isEditingDate) return ""
                var t = (dateInput.text || "").trim()
                if (!t) return "EMPTY"
                return (dateEditorContainer.view.bridge && typeof dateEditorContainer.view.bridge.normalizeWatchlistDate === "function")
                    ? dateEditorContainer.view.bridge.normalizeWatchlistDate(t)
                    : t
            }
            readonly property bool isDateValid: validationResult !== "INVALID"

            // Header & quick shortcut chips
            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Text {
                    text: "📅 " + dateEditorContainer.view.tr("watchlist_edit_cutoff_title", "Set Last Downloaded Cutoff Date:")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: Font.Bold
                    color: "#BAE6FD"
                }

                Item { Layout.fillWidth: true }

                // Today quick chip
                Rectangle {
                    height: 20
                    implicitWidth: todayText.implicitWidth + 12
                    radius: 4
                    color: todayMouse.containsMouse ? "#1E293B" : "#0F172A"
                    border.color: "#334155"
                    border.width: 1

                    Text {
                        id: todayText
                        anchors.centerIn: parent
                        text: "Today"
                        font.pixelSize: 10
                        font.weight: 600
                        color: "#94A3B8"
                    }
                    MouseArea {
                        id: todayMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            dateInput.text = Qt.formatDate(new Date(), "yyyy-MM-dd")
                        }
                    }
                }

                // Reset to Never quick chip
                Rectangle {
                    height: 20
                    implicitWidth: clearDateText.implicitWidth + 12
                    radius: 4
                    color: clearDateMouse.containsMouse ? "#2A1215" : "#190B0E"
                    border.color: "#7F1D1D"
                    border.width: 1

                    Text {
                        id: clearDateText
                        anchors.centerIn: parent
                        text: "Reset (Never)"
                        font.pixelSize: 10
                        font.weight: 600
                        color: "#FCA5A5"
                    }
                    MouseArea {
                        id: clearDateMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: "Clear cutoff date so all artist posts are eligible as updates"
                        onClicked: {
                            dateInput.text = ""
                        }
                    }
                }
            }

            // Input row & Save / Cancel buttons
            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Rectangle {
                    Layout.fillWidth: true
                    height: 32
                    radius: 5
                    color: dateInput.activeFocus ? "#0B0D12" : "#050811"
                    border.color: dateInput.activeFocus ? "#38BDF8" : (dateEditorCol.isDateValid ? (dateBoxMouse.containsMouse ? "#475569" : "#1E293B") : "#EF4444")
                    border.width: dateInput.activeFocus ? 1.5 : 1

                    TextBarContextArea {
                        id: dateBoxMouse
                        target: dateInput
                        focusOnLeftClick: true
                    }

                    TextInput {
                        id: dateInput
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        verticalAlignment: TextInput.AlignVCenter
                        font.family: "Consolas, Segoe UI, monospace"
                        font.pixelSize: 12
                        color: "#F1F5F9"
                        selectionColor: "#0284C7"
                        selectedTextColor: "#FFFFFF"
                        clip: true
                        text: dateEditorContainer.card.artistLastPostDate || ""
                        selectByMouse: true
                        TextBarContextArea {}

                        Text {
                            text: "YYYY-MM-DD (e.g. 2024-05-18, 18/05/2024, Aug 19 2024)"
                            font: parent.font
                            color: "#475569"
                            visible: !dateInput.text && !dateInput.activeFocus
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            elide: Text.ElideRight
                        }

                        Keys.onReturnPressed: saveDateBtn.doSave()
                        Keys.onEnterPressed: saveDateBtn.doSave()
                        Keys.onEscapePressed: dateEditorContainer.card.isEditingDate = false
                    }
                }

                // Save button
                Rectangle {
                    id: saveDateBtn
                    height: 32
                    implicitWidth: saveDateText.implicitWidth + 20
                    radius: 5
                    opacity: dateEditorCol.isDateValid ? 1.0 : 0.4
                    color: saveDateMouse.containsMouse ? "#0C382E" : "#07241C"
                    border.color: "#10B981"
                    border.width: 1

                    function doSave() {
                        if (!dateEditorCol.isDateValid) return
                        if (dateEditorContainer.view.bridge) {
                            var res = dateEditorContainer.view.bridge.setWatchlistLastDownloadDate(dateEditorContainer.card.artistUserId, dateEditorContainer.card.artistService, dateInput.text)
                            dateEditorContainer.card.isEditingDate = false
                            dateEditorContainer.card.viewRoot.showToast("✅ Saved cutoff date: " + (res || "Never"))
                        }
                    }

                    Text {
                        id: saveDateText
                        anchors.centerIn: parent
                        text: "✓ Save"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: Font.Bold
                        color: "#6EE7B7"
                    }

                    MouseArea {
                        id: saveDateMouse
                        anchors.fill: parent
                        hoverEnabled: dateEditorCol.isDateValid
                        cursorShape: dateEditorCol.isDateValid ? Qt.PointingHandCursor : Qt.ArrowCursor
                        onClicked: saveDateBtn.doSave()
                    }
                }

                // Cancel button
                Rectangle {
                    height: 32
                    implicitWidth: cancelDateText.implicitWidth + 18
                    radius: 5
                    color: cancelDateMouse.containsMouse ? "#1E2536" : "#131826"
                    border.color: "#2E3A52"
                    border.width: 1

                    Text {
                        id: cancelDateText
                        anchors.centerIn: parent
                        text: "✕ Cancel"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: 600
                        color: "#94A3B8"
                    }

                    MouseArea {
                        id: cancelDateMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: dateEditorContainer.card.isEditingDate = false
                    }
                }
            }

            // Live conversion guidance
            Text {
                text: {
                    if (!dateEditorContainer.card.isEditingDate) return ""
                    if (dateEditorCol.validationResult === "INVALID") {
                        return "⚠️ Unrecognized date. Please use YYYY-MM-DD or DD/MM/YYYY, Month DD YYYY"
                    }
                    if (dateEditorCol.validationResult === "EMPTY" || !dateInput.text.trim()) {
                        return "ℹ️ Will reset cutoff to 'Never' (checks will consider all posts as new)"
                    }
                    return "✓ Converted to: " + dateEditorCol.validationResult + " (enforced Pawchive & Kemono format)"
                }
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 10
                font.weight: 500
                color: !dateEditorCol.isDateValid ? "#F87171" : (dateInput.text.trim() ? "#34D399" : "#64748B")
                Layout.fillWidth: true
            }
        }
    }
}
