import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// ── Smart Batch Renamer Modal ──────────────────────────────────────────────
// Rule-based bulk file renaming using metadata variables ({artist}, {post_id}, {title}, {date}).
Item {
    id: root

    property var bridge: null
    property bool isOpen: false
    property string folderPath: ""
    property var targetFiles: []

    signal renamed()

    // Form inputs
    property string renamePattern: "{name}.{ext}"
    property string findText: ""
    property string replaceText: ""
    property string prefixText: ""
    property string suffixText: ""
    property string caseMode: "keep"

    // Live preview plan
    property var previewPlan: []
    property int readyCount: 0
    property bool isExecuting: false

    anchors.fill: parent
    z: 9998
    visible: isOpen

    function open(currentFolder, files) {
        folderPath = currentFolder || ""
        targetFiles = files || []
        renamePattern = "{name}.{ext}"
        findText = ""
        replaceText = ""
        prefixText = ""
        suffixText = ""
        caseMode = "keep"
        isOpen = true
        updatePreview()
    }

    function close() {
        isOpen = false
    }

    function insertToken(token) {
        patternField.text = patternField.text + token
        renamePattern = patternField.text
        updatePreview()
    }

    function updatePreview() {
        if (!isOpen || !bridge || !bridge.previewBatchRename) return
        var plan = bridge.previewBatchRename(
            folderPath,
            targetFiles,
            renamePattern,
            findText,
            replaceText,
            prefixText,
            suffixText,
            caseMode
        ) || []
        previewPlan = plan

        var ready = 0
        for (var i = 0; i < plan.length; i++) {
            if (plan[i].status === "ready") ready++
        }
        readyCount = ready
    }

    function executeRename() {
        if (!bridge || !bridge.executeBatchRename || readyCount === 0) return
        isExecuting = true
        var res = bridge.executeBatchRename(previewPlan)
        isExecuting = false
        if (res && res.success) {
            root.renamed()
            root.close()
        } else {
            // refresh preview to show updated status / remaining
            updatePreview()
        }
    }

    // Backdrop
    Rectangle {
        anchors.fill: parent
        color: "#080B11"
        opacity: root.isOpen ? 0.88 : 0.0
        Behavior on opacity { NumberAnimation { duration: 180 } }
        MouseArea { anchors.fill: parent }
    }

    // Modal Card
    Rectangle {
        width: Math.min(840, parent.width - 40)
        height: Math.min(680, parent.height - 40)
        anchors.centerIn: parent
        radius: 12
        color: "#111520"
        border.color: "#273349"
        border.width: 1
        clip: true

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 18
            spacing: 12

            // Header
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Text { text: "🏷️"; font.pixelSize: 22 }

                ColumnLayout {
                    spacing: 2
                    Text {
                        text: "Smart Batch Renamer"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 16
                        font.weight: 700
                        color: "#F8FAFC"
                    }
                    Text {
                        text: "Rule-based bulk file renaming using metadata variables ({artist}, {post_id}, {title}, {date})"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        color: "#94A3B8"
                    }
                }

                Item { Layout.fillWidth: true }

                Rectangle {
                    width: 28; height: 28; radius: 5
                    color: closeBtnMouse.containsMouse ? "#EF4444" : "#1A2234"
                    border.color: closeBtnMouse.containsMouse ? "#DC2626" : "#2E3A52"
                    border.width: 1
                    Text { anchors.centerIn: parent; text: "✕"; font.pixelSize: 12; font.weight: Font.Bold; color: "#FFFFFF" }
                    MouseArea {
                        id: closeBtnMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.close()
                    }
                }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: "#1F283B" }

            // Pattern & Variable Tokens
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6

                Text {
                    text: "Renaming Pattern:"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: 600
                    color: "#E2E8F0"
                }

                TextField {
                    id: patternField
                    Layout.fillWidth: true
                    text: root.renamePattern
                    placeholderText: "e.g. {artist} - {title} ({post_id}).{ext}"
                    font.family: "Segoe UI, monospace"
                    font.pixelSize: 12
                    color: "#F8FAFC"
                    background: Rectangle {
                        color: "#0B0E16"
                        radius: 6
                        border.color: patternField.activeFocus ? "#38BDF8" : "#273349"
                        border.width: 1
                    }
                    onTextEdited: {
                        root.renamePattern = text
                        root.updatePreview()
                    }
                }

                // Quick insertion token chips
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    Text { text: "Insert Token:"; font.pixelSize: 10; color: "#64748B" }

                    Repeater {
                        model: [
                            { label: "{name}", desc: "Base filename" },
                            { label: "{ext}", desc: "Extension" },
                            { label: "{artist}", desc: "Artist name" },
                            { label: "{title}", desc: "Clean title" },
                            { label: "{post_id}", desc: "Post ID" },
                            { label: "{date}", desc: "Date (YYYY-MM-DD)" },
                            { label: "{0index}", desc: "Two-digit 01.." },
                            { label: "{index}", desc: "Sequential 1.." }
                        ]
                        delegate: Rectangle {
                            implicitHeight: 22
                            implicitWidth: chipTxt.implicitWidth + 12
                            radius: 4
                            color: chipMouse.containsMouse ? "#2A364E" : "#171F2F"
                            border.color: chipMouse.containsMouse ? "#38BDF8" : "#2B3852"
                            border.width: 1

                            Text {
                                id: chipTxt
                                anchors.centerIn: parent
                                text: modelData.label
                                font.family: "Segoe UI, monospace"
                                font.pixelSize: 10
                                font.weight: 600
                                color: "#38BDF8"
                            }
                            MouseArea {
                                id: chipMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: insertToken(modelData.label)
                            }
                        }
                    }
                }
            }

            // Find & Replace + Prefix/Suffix Row
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                // Find & Replace
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    Text { text: "Find & Replace:"; font.pixelSize: 10; font.weight: 600; color: "#94A3B8" }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6
                        TextField {
                            Layout.fillWidth: true
                            placeholderText: "Find text..."
                            font.pixelSize: 11
                            color: "#F8FAFC"
                            background: Rectangle { color: "#0B0E16"; radius: 5; border.color: "#273349"; border.width: 1 }
                            onTextEdited: { root.findText = text; root.updatePreview() }
                        }
                        TextField {
                            Layout.fillWidth: true
                            placeholderText: "Replace with..."
                            font.pixelSize: 11
                            color: "#F8FAFC"
                            background: Rectangle { color: "#0B0E16"; radius: 5; border.color: "#273349"; border.width: 1 }
                            onTextEdited: { root.replaceText = text; root.updatePreview() }
                        }
                    }
                }

                // Prefix & Suffix
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    Text { text: "Prefix & Suffix:"; font.pixelSize: 10; font.weight: 600; color: "#94A3B8" }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6
                        TextField {
                            Layout.fillWidth: true
                            placeholderText: "Prefix..."
                            font.pixelSize: 11
                            color: "#F8FAFC"
                            background: Rectangle { color: "#0B0E16"; radius: 5; border.color: "#273349"; border.width: 1 }
                            onTextEdited: { root.prefixText = text; root.updatePreview() }
                        }
                        TextField {
                            Layout.fillWidth: true
                            placeholderText: "Suffix..."
                            font.pixelSize: 11
                            color: "#F8FAFC"
                            background: Rectangle { color: "#0B0E16"; radius: 5; border.color: "#273349"; border.width: 1 }
                            onTextEdited: { root.suffixText = text; root.updatePreview() }
                        }
                    }
                }

                // Case Mode
                ColumnLayout {
                    spacing: 4
                    Text { text: "Case Mode:"; font.pixelSize: 10; font.weight: 600; color: "#94A3B8" }
                    Row {
                        spacing: 4
                        Repeater {
                            model: [
                                { mode: "keep", label: "Keep" },
                                { mode: "lower", label: "lower" },
                                { mode: "upper", label: "UPPER" },
                                { mode: "title", label: "Title" }
                            ]
                            delegate: Rectangle {
                                implicitHeight: 28
                                implicitWidth: cmText.implicitWidth + 12
                                radius: 5
                                color: root.caseMode === modelData.mode ? "#202E47" : "#0E131E"
                                border.color: root.caseMode === modelData.mode ? "#38BDF8" : "#232F45"
                                border.width: 1
                                Text {
                                    id: cmText
                                    anchors.centerIn: parent
                                    text: modelData.label
                                    font.family: "Segoe UI, sans-serif"
                                    font.pixelSize: 10
                                    font.weight: root.caseMode === modelData.mode ? 700 : Font.Normal
                                    color: root.caseMode === modelData.mode ? "#38BDF8" : "#94A3B8"
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: {
                                        root.caseMode = modelData.mode
                                        root.updatePreview()
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // Preview Table Header
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 26
                radius: 4
                color: "#161D2B"
                border.color: "#222C3E"
                border.width: 1

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 10
                    anchors.rightMargin: 10
                    spacing: 8
                    Text { text: "Original Name"; font.pixelSize: 10; font.weight: 700; color: "#94A3B8"; Layout.fillWidth: true }
                    Text { text: "➔"; font.pixelSize: 10; color: "#64748B"; Layout.preferredWidth: 20; horizontalAlignment: Text.AlignHCenter }
                    Text { text: "New Name"; font.pixelSize: 10; font.weight: 700; color: "#94A3B8"; Layout.fillWidth: true }
                    Text { text: "Status"; font.pixelSize: 10; font.weight: 700; color: "#94A3B8"; Layout.preferredWidth: 70; horizontalAlignment: Text.AlignRight }
                }
            }

            // Preview Table List
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                radius: 6
                color: "#0A0D15"
                border.color: "#1E273A"
                border.width: 1
                clip: true

                ListView {
                    id: previewListView
                    anchors.fill: parent
                    anchors.margins: 4
                    spacing: 2
                    model: root.previewPlan
                    clip: true

                    delegate: Rectangle {
                        width: previewListView.width
                        height: 28
                        radius: 4
                        color: index % 2 === 0 ? "#111623" : "#0D111C"

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 8
                            anchors.rightMargin: 8
                            spacing: 8

                            Text {
                                text: modelData.old_name
                                font.family: "Segoe UI, monospace"
                                font.pixelSize: 10
                                color: "#CBD5E1"
                                elide: Text.ElideMiddle
                                Layout.fillWidth: true
                            }

                            Text {
                                text: "➔"
                                font.pixelSize: 10
                                color: "#64748B"
                                Layout.preferredWidth: 20
                                horizontalAlignment: Text.AlignHCenter
                            }

                            Text {
                                text: modelData.new_name
                                font.family: "Segoe UI, monospace"
                                font.pixelSize: 10
                                font.weight: 600
                                color: modelData.status === "ready" ? "#38BDF8" : (modelData.status === "collision" ? "#EF4444" : "#94A3B8")
                                elide: Text.ElideMiddle
                                Layout.fillWidth: true
                            }

                            Rectangle {
                                implicitHeight: 18
                                implicitWidth: statusTxt.implicitWidth + 10
                                radius: 4
                                color: modelData.status === "ready" ? "#064E3B" : (modelData.status === "collision" ? "#450A0A" : "#1E273A")
                                border.color: modelData.status === "ready" ? "#10B981" : (modelData.status === "collision" ? "#EF4444" : "#475569")
                                border.width: 1
                                Layout.preferredWidth: implicitWidth

                                Text {
                                    id: statusTxt
                                    anchors.centerIn: parent
                                    text: modelData.status === "ready" ? "READY" : (modelData.status === "collision" ? "COLLISION" : "UNCHANGED")
                                    font.pixelSize: 8
                                    font.weight: 700
                                    color: modelData.status === "ready" ? "#34D399" : (modelData.status === "collision" ? "#F87171" : "#94A3B8")
                                }
                            }
                        }
                    }
                }
            }

            // Bottom Actions Bar
            RowLayout {
                Layout.fillWidth: true
                spacing: 12

                Text {
                    text: root.readyCount + " of " + root.previewPlan.length + " files ready to rename"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: 600
                    color: root.readyCount > 0 ? "#10B981" : "#94A3B8"
                }

                Item { Layout.fillWidth: true }

                // Cancel button
                Rectangle {
                    implicitHeight: 32
                    implicitWidth: 80
                    radius: 6
                    color: cancelMouse.containsMouse ? "#242D40" : "#161D2B"
                    border.color: "#2C374D"
                    border.width: 1

                    Text { anchors.centerIn: parent; text: "Cancel"; font.family: "Segoe UI, sans-serif"; font.pixelSize: 11; color: "#E2E8F0" }
                    MouseArea {
                        id: cancelMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.close()
                    }
                }

                // Apply Rename button
                Rectangle {
                    implicitHeight: 32
                    implicitWidth: applyText.implicitWidth + 24
                    radius: 6
                    color: root.readyCount > 0 ? (applyMouse.containsMouse ? "#4F46E5" : "#4338CA") : "#222634"
                    border.color: root.readyCount > 0 ? "#6366F1" : "#323747"
                    border.width: 1
                    opacity: root.readyCount > 0 ? 1.0 : 0.5

                    Text {
                        id: applyText
                        anchors.centerIn: parent
                        text: root.isExecuting ? "Renaming..." : ("Apply Rename (" + root.readyCount + ")")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: 700
                        color: "#FFFFFF"
                    }
                    MouseArea {
                        id: applyMouse
                        anchors.fill: parent
                        hoverEnabled: root.readyCount > 0
                        cursorShape: root.readyCount > 0 ? Qt.PointingHandCursor : Qt.ArrowCursor
                        onClicked: {
                            if (root.readyCount > 0 && !root.isExecuting) {
                                executeRename()
                            }
                        }
                    }
                }
            }
        }
    }
}
