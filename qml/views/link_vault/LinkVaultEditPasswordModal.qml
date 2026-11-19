import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

// ── Edit Password Modal ───────────────────────────────────────────────────
Popup {
    id: editPwModal
    required property var view
    x: Math.round((editPwModal.view.width - width) / 2)
    y: Math.round((editPwModal.view.height - height) / 2)
    width: Math.min(480, editPwModal.view.width - 32)
    modal: true
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    dim: true

    property string currentLinkId: ""
    property string currentLinkUrl: ""

    function openForLink(linkId, linkUrl, initialPasswords) {
        currentLinkId = linkId
        currentLinkUrl = linkUrl
        pwInputField.text = initialPasswords || ""
        open()
        pwInputField.forceActiveFocus()
    }

    background: Rectangle {
        color: "#0F1219"
        border.color: "#38BDF8"
        border.width: 1
        radius: 12
    }

    contentItem: ColumnLayout {
        spacing: 12
        anchors.margins: 6

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Text { text: "🔑"; font.pixelSize: 15 }
            Text {
                text: editPwModal.view.tr("modal_edit_pw_title", "Edit Link Password")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 14
                font.weight: Font.Bold
                color: "#F1F5F9"
                Layout.fillWidth: true
            }
        }

        Text {
            text: editPwModal.currentLinkUrl
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 11
            color: "#64748B"
            elide: Text.ElideMiddle
            Layout.fillWidth: true
        }

        Text {
            text: editPwModal.view.tr("modal_edit_pw_desc", "Enter the archive password(s) for this link. If multiple passwords apply, separate them with commas:")
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 11
            color: "#94A3B8"
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }

        Rectangle {
            Layout.fillWidth: true
            height: 36
            radius: 6
            color: pwInputField.activeFocus ? "#0B0D12" : "#181B24"
            border.color: pwInputField.activeFocus ? "#38BDF8" : (pwInputBoxMouse.containsMouse ? "#475569" : "#283042")
            border.width: pwInputField.activeFocus ? 1.5 : 1

            TextBarContextArea {
                id: pwInputBoxMouse
                target: pwInputField
                focusOnLeftClick: true
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                spacing: 8

                TextInput {
                    id: pwInputField
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    verticalAlignment: TextInput.AlignVCenter
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 12
                    color: "#F8FAFC"
                    selectionColor: "#0284C7"
                    selectedTextColor: "#FFFFFF"
                    selectByMouse: true
                    clip: true
                    TextBarContextArea {}
                    onAccepted: savePwBtn.clicked()

                    Text {
                        text: editPwModal.view.tr("placeholder_edit_pw", "e.g., lamb2024, pass123")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        color: "#475569"
                        visible: !pwInputField.text && !pwInputField.activeFocus
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.verticalCenter: parent.verticalCenter
                        elide: Text.ElideRight
                    }
                }

                Text {
                    text: "✕"
                    font.pixelSize: 12
                    color: "#64748B"
                    visible: pwInputField.text.length > 0
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: pwInputField.text = ""
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 6
            spacing: 8

            Item { Layout.fillWidth: true }

            Rectangle {
                implicitWidth: 80
                height: 32
                radius: 6
                color: cancelPwMouse.containsMouse ? "#334155" : "#1E293B"
                border.color: "#475569"
                border.width: 1

                Text {
                    anchors.centerIn: parent
                    text: editPwModal.view.tr("btn_cancel", "Cancel")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: 600
                    color: "#CBD5E1"
                }

                MouseArea {
                    id: cancelPwMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: editPwModal.close()
                }
            }

            Rectangle {
                id: savePwBtn
                implicitWidth: 90
                height: 32
                radius: 6
                color: savePwMouse.containsMouse ? "#0284C7" : "#0EA5E9"
                border.color: "#38BDF8"
                border.width: 1

                signal clicked()
                onClicked: {
                    if (editPwModal.view.bridge && editPwModal.currentLinkId) {
                        var rawInput = pwInputField.text.trim()
                        editPwModal.view.bridge.updateVaultLinkPasswords(editPwModal.currentLinkId, rawInput)
                        editPwModal.close()
                        editPwModal.view.showToast(editPwModal.view.tr("toast_pw_saved", "Password updated for link."))
                    }
                }

                Text {
                    anchors.centerIn: parent
                    text: editPwModal.view.tr("btn_save_pw", "Save")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: Font.Bold
                    color: "#FFFFFF"
                }

                MouseArea {
                    id: savePwMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: savePwBtn.clicked()
                }
            }
        }
    }
}
