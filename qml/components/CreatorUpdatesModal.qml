import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// ── "Check for new posts" (Gallery) ─────────────────────────────────────────
// Compares the creator's posts online with what is already saved in the folder you're
// looking at, and downloads what's missing straight into that folder.
Item {
    id: root

    property var updates: null            // galleryUpdates
    property bool isOpen: false
    property string folder: ""
    property var creator: ({})            // creatorForFolder() answer
    property string stage: "idle"         // "link" | "checking" | "result" | "queued" | "error"
    property int token: -1
    property var result: ({})
    property var progress: ({})
    property string message: ""
    property string linkError: ""

    signal creatorLinked(var info)
    signal downloadStarted(string folder, string message)

    anchors.fill: parent
    z: 9400
    opacity: isOpen ? 1 : 0
    visible: opacity > 0.005
    enabled: isOpen
    Behavior on opacity { NumberAnimation { duration: 190; easing.type: Easing.OutCubic } }

    function open(path, info) {
        folder = path
        creator = info || ({})
        result = ({})
        progress = ({})
        message = ""
        linkError = ""
        isOpen = true
        root.forceActiveFocus()
        if (creator.found) startCheck()
        else {
            stage = "link"
            linkInput.text = ""
            linkInput.forceActiveFocus()
        }
    }
    function close() {
        if (stage === "checking" && updates) updates.cancel()
        isOpen = false
    }
    function startCheck() {
        if (!updates) return
        stage = "checking"
        progress = ({ stage: "local" })
        token = updates.checkFolder(folder)
    }
    function saveLink() {
        if (!updates) return
        var info = updates.rememberCreatorLink(folder, linkInput.text)
        if (!info.found) {
            linkError = info.error || "That link didn't work."
            return
        }
        creator = info
        creatorLinked(info)
        startCheck()
    }
    function download(includeOlder) {
        if (!updates || !updates.downloadMissing(token, includeOlder)) return
        stage = "queued"
        message = "Preparing the download…"
    }
    function plural(n, word) { return n + " " + word + (n === 1 ? "" : "s") }

    Connections {
        target: root.updates
        function onCheckProgress(t, p) { if (t === root.token) root.progress = p }
        function onCheckFinished(t, r) {
            if (t !== root.token) return
            root.result = r
            if (r.ok) root.stage = "result"
            else { root.message = r.error || "Something went wrong."; root.stage = "error" }
        }
        function onDownloadQueued(t, r) {
            if (t !== root.token) return
            root.message = r.message
            if (r.ok) root.downloadStarted(r.folder, r.message)
            else root.stage = "error"
        }
    }

    // Dialog button
    component Btn: Rectangle {
        id: b
        property string label: ""
        property bool primary: false
        signal clicked()
        implicitWidth: bl.implicitWidth + 26
        implicitHeight: 32
        radius: 7
        color: primary ? (bm.containsMouse ? "#0EA5E9" : "#0284C7") : (bm.containsMouse ? "#1E293B" : "#151B29")
        border.color: primary ? "#38BDF8" : "#2E384D"
        Text { id: bl; anchors.centerIn: parent; text: b.label; font.family: "Segoe UI"; font.pixelSize: 12; font.weight: 600; color: "#F8FAFC" }
        Springy { hover: bm.containsMouse; pressed: bm.pressed }
        MouseArea { id: bm; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: b.clicked() }
    }

    // Backdrop: swallow clicks, hover and the wheel
    Rectangle {
        anchors.fill: parent
        color: "#060910"
        opacity: 0.88
        MouseArea { anchors.fill: parent; hoverEnabled: true; onClicked: root.close(); onWheel: (wheel) => wheel.accepted = true }
    }

    Keys.onEscapePressed: root.close()

    Rectangle {
        id: card
        // Heavy panel: settles in on a soft spring
        scale: root.isOpen ? 1.0 : 0.9
        Behavior on scale { SpringAnimation { spring: 3.4; damping: 0.36; mass: 1.6; epsilon: 0.0008 } }
        anchors.centerIn: parent
        width: Math.min(520, parent.width - 32)
        height: body.implicitHeight + 40
        radius: 14
        color: "#101420"
        border.color: "#2A364E"
        border.width: 1
        MouseArea { anchors.fill: parent }   // clicks inside don't close it

        ColumnLayout {
            id: body
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 20
            spacing: 14

            // Header
            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                Rectangle {
                    width: 42; height: 42; radius: 21
                    color: "#0F2A3A"
                    border.color: "#38BDF8"
                    Text {
                        anchors.centerIn: parent
                        text: "🔄"
                        font.pixelSize: 19
                        RotationAnimator on rotation { from: 0; to: 360; duration: 1400; loops: Animation.Infinite; running: root.stage === "checking" }
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    Text {
                        text: root.stage === "link" ? "Which creator is this?" : ("Check for new posts" + ((root.result.name || root.progress.name) ? ": " + (root.result.name || root.progress.name) : ""))
                        font.family: "Segoe UI"; font.pixelSize: 15; font.weight: 700; color: "#F1F5F9"
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                    Text {
                        text: root.folder
                        font.family: "Segoe UI"; font.pixelSize: 10; color: "#64748B"
                        elide: Text.ElideMiddle
                        Layout.fillWidth: true
                    }
                }
                Rectangle {
                    width: 26; height: 26; radius: 6
                    color: closeX.containsMouse ? "#3A1620" : "transparent"
                    Text { anchors.centerIn: parent; text: "✕"; color: "#94A3B8"; font.pixelSize: 12 }
                    MouseArea { id: closeX; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: root.close() }
                }
            }

            // ── Not recognised: paste the creator's link once ──
            ColumnLayout {
                visible: root.stage === "link"
                Layout.fillWidth: true
                spacing: 8
                Text {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: "The gallery couldn't tell which creator these files came from. Paste the creator's page link once, and it will remember it for this folder."
                    font.family: "Segoe UI"; font.pixelSize: 12; color: "#CBD5E1"
                }
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: 32
                    radius: 6
                    color: "#0B0F18"
                    border.color: linkInput.activeFocus ? "#38BDF8" : "#2A364E"
                    TextInput {
                        id: linkInput
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        verticalAlignment: TextInput.AlignVCenter
                        color: "#F8FAFC"
                        font.family: "Segoe UI"; font.pixelSize: 12
                        selectByMouse: true
                        clip: true
                        onAccepted: root.saveLink()
                        onTextChanged: root.linkError = ""
                        Text {
                            visible: !linkInput.text
                            anchors.verticalCenter: parent.verticalCenter
                            text: "https://kemono.cr/patreon/user/12345"
                            color: "#475569"; font.family: "Segoe UI"; font.pixelSize: 12
                        }
                    }
                }
                Text {
                    visible: root.linkError.length > 0
                    text: root.linkError
                    color: "#F87171"; font.family: "Segoe UI"; font.pixelSize: 11
                    Layout.fillWidth: true; wrapMode: Text.WordWrap
                }
            }

            // ── Checking ──
            ColumnLayout {
                visible: root.stage === "checking"
                Layout.fillWidth: true
                spacing: 8
                Text {
                    text: root.progress.stage === "online"
                          ? ("Reading the creator's posts…  page " + Math.max(1, root.progress.page || 1) + ((root.progress.scanned || 0) > 0 ? ("  ·  " + root.progress.scanned + " posts so far") : ""))
                          : "Looking at what's already in this folder…"
                    font.family: "Segoe UI"; font.pixelSize: 12; color: "#CBD5E1"
                }
                // Indeterminate shimmer so it never looks stuck
                Rectangle {
                    Layout.fillWidth: true
                    height: 4; radius: 2
                    color: "#1E2536"
                    clip: true
                    Rectangle {
                        width: parent.width * 0.3; height: parent.height; radius: 2
                        color: "#38BDF8"
                        NumberAnimation on x { from: -parent.width * 0.3; to: parent.width; duration: 1100; loops: Animation.Infinite; running: root.stage === "checking" }
                    }
                }
            }

            // ── Result ──
            ColumnLayout {
                visible: root.stage === "result"
                Layout.fillWidth: true
                spacing: 10

                // Big, plain answer
                Rectangle {
                    Layout.fillWidth: true
                    implicitHeight: answerCol.implicitHeight + 20
                    radius: 10
                    color: (root.result.newCount || 0) > 0 ? "#0F2A22" : "#141A28"
                    border.color: (root.result.newCount || 0) > 0 ? "#34D399" : "#2A364E"
                    ColumnLayout {
                        id: answerCol
                        anchors.left: parent.left; anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.margins: 12
                        spacing: 4
                        Text {
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                            text: {
                                var r = root.result
                                if (!r.matched) return "None of the files here match this creator's posts yet."
                                if (r.newCount > 0) return "✨ " + root.plural(r.newCount, "new post") + " since your latest download"
                                return "✔ You're up to date"
                            }
                            font.family: "Segoe UI"; font.pixelSize: 15; font.weight: 700
                            color: (root.result.newCount || 0) > 0 ? "#6EE7B7" : "#E2E8F0"
                        }
                        Text {
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                            text: {
                                var r = root.result
                                var t = "You have " + (r.have || 0) + " of " + root.plural(r.total || 0, "post") + " with files"
                                if (r.latestHave) t += "  ·  latest one from " + r.latestHave
                                if (r.olderCount > 0) t += "\n" + root.plural(r.olderCount, "older post") + (r.matched ? " you don't have" : " available")
                                return t
                            }
                            font.family: "Segoe UI"; font.pixelSize: 11; color: "#94A3B8"
                        }
                    }
                }

                // A peek at what would be downloaded
                Repeater {
                    model: root.result.newest || []
                    delegate: RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Text { text: modelData.date || ""; font.family: "Segoe UI"; font.pixelSize: 10; color: "#64748B"; Layout.preferredWidth: 70 }
                        Text { text: modelData.title; font.family: "Segoe UI"; font.pixelSize: 11; color: "#CBD5E1"; elide: Text.ElideRight; Layout.fillWidth: true }
                    }
                }
            }

            // ── Queued / error ──
            Text {
                visible: root.stage === "queued" || root.stage === "error"
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: (root.stage === "error" ? "⚠ " : "⬇ ") + root.message
                font.family: "Segoe UI"; font.pixelSize: 12
                color: root.stage === "error" ? "#FCA5A5" : "#6EE7B7"
            }

            // ── Buttons ──
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Item { Layout.fillWidth: true }
                Btn {
                    label: root.stage === "result" || root.stage === "queued" ? "Close" : "Cancel"
                    onClicked: root.close()
                }
                Btn {
                    visible: root.stage === "link"
                    primary: true
                    label: "Save & check"
                    onClicked: root.saveLink()
                }
                Btn {
                    visible: root.stage === "error"
                    primary: true
                    label: "Try again"
                    onClicked: root.creator.found ? root.startCheck() : root.open(root.folder, root.creator)
                }
                Btn {
                    visible: root.stage === "result" && (root.result.olderCount || 0) > 0
                    primary: (root.result.newCount || 0) === 0
                    label: "Download all " + ((root.result.newCount || 0) + (root.result.olderCount || 0)) + " missing"
                    onClicked: root.download(true)
                }
                Btn {
                    visible: root.stage === "result" && (root.result.newCount || 0) > 0
                    primary: true
                    label: "Download " + root.plural(root.result.newCount || 0, "new post")
                    onClicked: root.download(false)
                }
            }
        }
    }
}
