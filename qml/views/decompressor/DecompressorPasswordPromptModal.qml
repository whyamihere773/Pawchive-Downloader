import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

// ═══════════════════════════════════════════════════════════════════════════
// ── 🔐 PASSWORD PROMPT MODAL ─────────────────────────────────────────────
// ═══════════════════════════════════════════════════════════════════════════
Item {
    id: passwordPromptOverlay
    required property var view

    function handleWrongPassword() {
        pwInput.text = "";
        pwPromptCard.inputText = "";
        pwShakeAnim.restart();
    }
    anchors.fill: parent
    // Visibility gate driven by opacity so exit animation runs before hide
    visible: opacity > 0
    opacity: passwordPromptOverlay.view.showPasswordPrompt ? 1.0 : 0.0
    z: 1000

    Behavior on opacity {
        NumberAnimation { duration: 200; easing.type: Easing.OutQuad }
    }

    // Backdrop
    Rectangle {
        anchors.fill: parent
        color: "#000000"
        opacity: 0.72
        MouseArea { anchors.fill: parent; hoverEnabled: true }
    }

    // Modal card
    Rectangle {
        id: pwPromptCard
        anchors.centerIn: parent
        width: Math.min(480, parent.width - 40)
        implicitHeight: promptCol.implicitHeight + 40
        height: implicitHeight
        radius: 14
        color: "#0F141C"
        border.color: "#F59E0B"
        border.width: 1

        // Password modal feels like a firm heavy dialog — tight spring, less bounce
        scale: passwordPromptOverlay.view.showPasswordPrompt ? 1.0 : 0.84
        opacity: passwordPromptOverlay.view.showPasswordPrompt ? 1.0 : 0.0
        transformOrigin: Item.Center

        Behavior on scale {
            SpringAnimation {
                spring: 6.5
                damping: 0.58
                mass: 1.1
                epsilon: 0.001
            }
        }
        Behavior on opacity {
            NumberAnimation { duration: 160; easing.type: Easing.OutQuad }
        }
        property string inputText: ""
        property bool showPlain: false

        function tryExtract() {
            var pw = inputText.trim();
            if (!pw || passwordPromptOverlay.view.promptTesting) return;
            if (passwordPromptOverlay.view.decompressor) {
                passwordPromptOverlay.view.promptWrongPw = false;
                passwordPromptOverlay.view.promptTesting = true;
                var ok = passwordPromptOverlay.view.decompressor.retryItemWithPassword(passwordPromptOverlay.view.promptItemId, pw, passwordPromptOverlay.view.promptRemember);
                if (!ok) {
                    passwordPromptOverlay.view.promptTesting = false;
                    passwordPromptOverlay.view.promptWrongPw = true;
                    pwInput.text = "";
                    inputText = "";
                    pwShakeAnim.restart();
                }
            }
        }
        onVisibleChanged: {
            if (visible) {
                inputText = "";
                showPlain = false;
            }
        }

        ColumnLayout {
            id: promptCol
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 20
            spacing: 14

            // Title row
            RowLayout {
                spacing: 10
                Text { text: "🔐"; font.pixelSize: 20 }
                ColumnLayout {
                    spacing: 2
                    Layout.fillWidth: true
                    Text {
                        text: passwordPromptOverlay.view.tr("modal_pw_prompt_title", "Password Required")
                        font.family: "Segoe UI, Inter, sans-serif"
                        font.pixelSize: 14
                        font.weight: 700
                        color: "#FCD34D"
                    }
                    Text {
                        text: passwordPromptOverlay.view.tr("modal_pw_prompt_desc", "This archive is encrypted. No matching password was found in your saved list.")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: "#94A3B8"
                        wrapMode: Text.WordWrap
                        Layout.fillWidth: true
                    }
                }
                // Close
                Text {
                    text: "✕"
                    font.pixelSize: 14
                    color: closePwPromptMouse.containsMouse ? "#F1F5F9" : "#64748B"
                    MouseArea {
                        id: closePwPromptMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (passwordPromptOverlay.view.decompressor) passwordPromptOverlay.view.decompressor.skipPasswordPrompt(passwordPromptOverlay.view.promptItemId);
                            passwordPromptOverlay.view.showPasswordPrompt = false;
                        }
                    }
                }
            }

            // Archive context box
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: archiveInfoCol.implicitHeight + 20
                implicitHeight: Layout.preferredHeight
                radius: 8
                color: "#131924"
                border.color: "#1E2D42"
                border.width: 1
                ColumnLayout {
                    id: archiveInfoCol
                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: 10 }
                    spacing: 3
                    Row {
                        spacing: 6
                        Text { text: "📦"; font.pixelSize: 11 }
                        Text {
                            text: passwordPromptOverlay.view.promptFilename
                            font.family: "Segoe UI, Inter, sans-serif"
                            font.pixelSize: 11
                            font.weight: Font.Bold
                            color: "#38BDF8"
                            elide: Text.ElideMiddle
                            width: pwPromptCard.width - 80
                        }
                    }
                    Row {
                        spacing: 6
                        Text { text: "🎨"; font.pixelSize: 10 }
                        Text {
                            text: passwordPromptOverlay.view.promptCreator
                            font.pixelSize: 10
                            color: "#94A3B8"
                        }
                        Text { text: "•"; font.pixelSize: 10; color: "#475569" }
                        Text {
                            text: passwordPromptOverlay.view.promptDirectory
                            font.pixelSize: 9
                            color: "#475569"
                            elide: Text.ElideLeft
                            width: pwPromptCard.width - 120
                        }
                    }
                }
            }

            // Wrong password banner
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: passwordPromptOverlay.view.promptWrongPw ? (wrongPwTxt.implicitHeight + 16) : 0
                implicitHeight: Layout.preferredHeight
                radius: 6
                color: "#3B0A0A"
                border.color: "#EF4444"
                border.width: 1
                visible: passwordPromptOverlay.view.promptWrongPw
                Text {
                    id: wrongPwTxt
                    anchors { left: parent.left; right: parent.right; top: parent.top; margins: 8 }
                    text: "⚠️  Incorrect password — 7-Zip reported 'Wrong password'. Try again."
                    font.pixelSize: 10
                    color: "#FCA5A5"
                    wrapMode: Text.WordWrap
                }
            }

            // Password input
            Text {
                text: "Archive Password"
                font.pixelSize: 11
                font.weight: Font.Medium
                color: "#94A3B8"
            }
            Rectangle {
                id: pwInputRect
                Layout.fillWidth: true
                Layout.preferredHeight: 36
                implicitHeight: 36
                radius: 7
                color: pwInput.activeFocus ? "#0B1420" : "#0B0E14"
                border.color: passwordPromptOverlay.view.promptWrongPw ? "#F87171" : (pwInput.activeFocus ? "#38BDF8" : "#334155")
                border.width: pwInput.activeFocus || passwordPromptOverlay.view.promptWrongPw ? 1.5 : 1

                SequentialAnimation {
                    id: pwShakeAnim
                    loops: 1
                    PropertyAnimation { target: pwInputRect; property: "x"; to: -6; duration: 40 }
                    PropertyAnimation { target: pwInputRect; property: "x"; to:  6; duration: 40 }
                    PropertyAnimation { target: pwInputRect; property: "x"; to: -4; duration: 40 }
                    PropertyAnimation { target: pwInputRect; property: "x"; to:  4; duration: 40 }
                    PropertyAnimation { target: pwInputRect; property: "x"; to:  0; duration: 40 }
                }

                TextBarContextArea {
                    target: pwInput
                    focusOnLeftClick: true
                }

                Item {
                    anchors { left: parent.left; right: parent.right; top: parent.top; bottom: parent.bottom; leftMargin: 10; rightMargin: 6 }

                    Text {
                        id: pwInputIcon
                        anchors { left: parent.left; verticalCenter: parent.verticalCenter }
                        text: "🔑"
                        font.pixelSize: 12
                    }

                    Text {
                        id: eyeToggle
                        anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                        text: pwPromptCard.showPlain ? "🔒" : "👁️"
                        font.pixelSize: 12
                        color: eyeMouse.containsMouse ? "#F1F5F9" : "#64748B"
                        MouseArea {
                            id: eyeMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: pwPromptCard.showPlain = !pwPromptCard.showPlain
                        }
                    }

                    TextInput {
                        id: pwInput
                        anchors {
                            left: pwInputIcon.right; leftMargin: 6
                            right: eyeToggle.left; rightMargin: 6
                            top: parent.top
                            bottom: parent.bottom
                        }
                        verticalAlignment: TextInput.AlignVCenter
                        font.pixelSize: 12
                        font.family: "Segoe UI, Inter, sans-serif"
                        color: "#E2E8F0"
                        selectionColor: "#0284C7"
                        selectedTextColor: "#FFFFFF"
                        selectByMouse: true
                        clip: true
                        echoMode: pwPromptCard.showPlain ? TextInput.Normal : TextInput.Password
                        onTextChanged: pwPromptCard.inputText = text
                        onAccepted: pwPromptCard.tryExtract()
                        Component.onCompleted: forceActiveFocus()
                        TextBarContextArea {}

                        // Placeholder overlay
                        Text {
                            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter }
                            elide: Text.ElideRight
                            text: passwordPromptOverlay.view.tr("placeholder_archive_pw", "Enter archive password...")
                            font.pixelSize: 12
                            font.family: "Segoe UI, Inter, sans-serif"
                            color: "#475569"
                            visible: pwInput.text.length === 0 && !pwInput.activeFocus
                        }
                    }
                }
            }
            Text {
                text: "Press Enter to test and extract"
                font.pixelSize: 9
                color: "#475569"
            }

            // Remember checkbox
            MouseArea {
                id: rememberMouse
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                Layout.preferredHeight: rememberRow.implicitHeight
                implicitHeight: rememberRow.implicitHeight
                Layout.fillWidth: true
                onClicked: passwordPromptOverlay.view.promptRemember = !passwordPromptOverlay.view.promptRemember
                Row {
                    id: rememberRow
                    spacing: 8
                    Rectangle {
                        width: 16; height: 16; radius: 4
                        color: passwordPromptOverlay.view.promptRemember ? "#38BDF8" : "#111827"
                        border.color: passwordPromptOverlay.view.promptRemember ? "#38BDF8" : "#334155"
                        border.width: 1
                        Text { anchors.centerIn: parent; text: "✓"; font.pixelSize: 10; font.weight: Font.Bold; color: "#0F172A"; visible: passwordPromptOverlay.view.promptRemember }
                    }
                    Text {
                        text: passwordPromptOverlay.view.tr("chk_remember_archive_pw", "Remember password in Password Bank for future archives")
                        font.pixelSize: 10
                        color: rememberMouse.containsMouse ? "#CBD5E1" : "#94A3B8"
                    }
                }
            }

            // Action buttons
            RowLayout {
                Layout.fillWidth: true
                Layout.preferredHeight: 34
                implicitHeight: 34
                spacing: 8

                // Skip All Encrypted
                Rectangle {
                    height: 32
                    implicitWidth: skipAllTxt.implicitWidth + 20
                    radius: 6
                    color: skipAllMouse.containsMouse ? "#1E293B" : "#141C2A"
                    border.color: skipAllMouse.containsMouse ? "#475569" : "#334155"
                    border.width: 1
                    Text {
                        id: skipAllTxt
                        anchors.centerIn: parent
                        text: passwordPromptOverlay.view.tr("btn_skip_all_encrypted", "Skip All Encrypted")
                        font.pixelSize: 10
                        color: "#94A3B8"
                    }
                    MouseArea {
                        id: skipAllMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (passwordPromptOverlay.view.decompressor) passwordPromptOverlay.view.decompressor.skipAllPasswordPrompts();
                            passwordPromptOverlay.view.showPasswordPrompt = false;
                        }
                    }
                }

                // Skip this one
                Rectangle {
                    height: 32
                    implicitWidth: skipOneTxt.implicitWidth + 20
                    radius: 6
                    color: skipOneMouse.containsMouse ? "#1E293B" : "#141C2A"
                    border.color: skipOneMouse.containsMouse ? "#475569" : "#334155"
                    border.width: 1
                    Text {
                        id: skipOneTxt
                        anchors.centerIn: parent
                        text: passwordPromptOverlay.view.tr("dialog_skip", "Skip")
                        font.pixelSize: 11
                        color: "#94A3B8"
                    }
                    MouseArea {
                        id: skipOneMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (passwordPromptOverlay.view.decompressor) passwordPromptOverlay.view.decompressor.skipPasswordPrompt(passwordPromptOverlay.view.promptItemId);
                            passwordPromptOverlay.view.showPasswordPrompt = false;
                        }
                    }
                }

                Item { Layout.fillWidth: true }

                // Try & Extract (primary)
                Rectangle {
                    id: tryExtractBtn
                    height: 32
                    implicitWidth: tryTxt.implicitWidth + 28
                    radius: 6
                    color: (passwordPromptOverlay.view.promptTesting || pwPromptCard.inputText.length === 0) ? "#0F2A3F"
                         : (tryMouse.containsMouse ? "#0369A1" : "#0284C7")
                    border.color: passwordPromptOverlay.view.promptTesting ? "#475569" : "#38BDF8"
                    border.width: 1
                    opacity: (passwordPromptOverlay.view.promptTesting || pwPromptCard.inputText.length === 0) ? 0.7 : 1.0

                    Row {
                        anchors.centerIn: parent
                        spacing: 6
                        Text {
                            text: passwordPromptOverlay.view.promptTesting ? "⏳" : "🔓"
                            font.pixelSize: 11
                            anchors.verticalCenter: parent.verticalCenter
                        }
                        Text {
                            id: tryTxt
                            text: passwordPromptOverlay.view.promptTesting
                                ? passwordPromptOverlay.view.tr("btn_testing_pw", "Testing...")
                                : passwordPromptOverlay.view.tr("btn_try_extract", "Try & Extract")
                            font.pixelSize: 11
                            font.weight: Font.Bold
                            color: passwordPromptOverlay.view.promptTesting ? "#94A3B8" : "#FFFFFF"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                    MouseArea {
                        id: tryMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: (passwordPromptOverlay.view.promptTesting || pwPromptCard.inputText.length === 0) ? Qt.ArrowCursor : Qt.PointingHandCursor
                        enabled: pwPromptCard.inputText.length > 0 && !passwordPromptOverlay.view.promptTesting
                        onClicked: pwPromptCard.tryExtract()
                    }
                }

            }
        }
    }
}
