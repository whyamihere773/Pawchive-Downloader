import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

Popup {
    id: providerLoginModal
    required property var view

    function resetInputs() {
        loginPassField.text = ""
        loginCookieField.text = ""
    }
    objectName: "providerLoginModal"
    anchors.centerIn: Overlay.overlay
    width: Math.min(480, Math.max(360, providerLoginModal.view.width * 0.46))
    padding: 18
    modal: true
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    readonly property string targetPid: providerLoginModal.view.loginModalProviderId || (providerLoginModal.view.bBridge ? providerLoginModal.view.bBridge.activeProvider : "pawchive")
    readonly property string targetDisplayName: {
        if (targetPid === "pawchive") return "Pawchive"
        if (targetPid === "cumst") return "Cum.st"
        if (targetPid === "coomerfans") return "CoomerFans"
        return providerLoginModal.view.activeProviderDisplayName
    }

    background: Rectangle {
        radius: 12
        color: "#0F1420"
        border.color: "#F59E0B"
        border.width: 1.5
    }

    contentItem: ColumnLayout {
        spacing: 12

        RowLayout {
            Layout.fillWidth: true
            Text {
                Layout.fillWidth: true
                text: "🔐 Sign In to " + providerLoginModal.targetDisplayName
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 16
                font.weight: Font.Bold
                color: "#F8FAFC"
            }
            Text {
                text: "✕"
                font.pixelSize: 14
                color: "#94A3B8"
                MouseArea {
                    anchors.fill: parent
                    anchors.margins: -6
                    cursorShape: Qt.PointingHandCursor
                    onClicked: providerLoginModal.close()
                }
            }
        }

        Text {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 12
            color: "#94A3B8"
            text: {
                if (providerLoginModal.view.loginModalReason === "favorites") {
                    return "Log in to your " + providerLoginModal.targetDisplayName + " account to browse your favorited creators."
                }
                if (providerLoginModal.view.loginModalReason === "favorite_creator") {
                    return "Log in to save or remove favorited creators directly on your " + providerLoginModal.targetDisplayName + " account."
                }
                return "Log in with your account credentials, import cookies from your browser, or paste your session cookie."
            }
        }

        Rectangle {
            visible: providerLoginModal.view.loginModalError.length > 0
            Layout.fillWidth: true
            implicitHeight: loginErrLbl.implicitHeight + 14
            radius: 7
            color: "#2A1215"
            border.color: "#F43F5E"
            border.width: 1
            Text {
                id: loginErrLbl
                anchors.fill: parent
                anchors.margins: 7
                wrapMode: Text.WordWrap
                text: providerLoginModal.view.loginModalError
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                color: "#FDA4AF"
            }
        }

        // Username & Password Login
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: credCol.implicitHeight + 20
            radius: 8
            color: "#0B0F19"
            border.color: "#1E293B"
            border.width: 1

            ColumnLayout {
                id: credCol
                anchors.fill: parent
                anchors.margins: 10
                spacing: 8

                Text {
                    text: "Account Credentials"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: Font.Bold
                    color: "#CBD5E1"
                }

                TextField {
                    id: loginUserField
                    objectName: "loginUsernameField"
                    Layout.fillWidth: true
                    placeholderText: "Username or email"
                    color: "#F8FAFC"
                    placeholderTextColor: "#64748B"
                    selectionColor: "#0284C7"
                    selectedTextColor: "#FFFFFF"
                    selectByMouse: true
                    clip: true
                    verticalAlignment: TextInput.AlignVCenter
                    background: Rectangle {
                        radius: 6
                        color: loginUserField.activeFocus ? "#0B0D12" : "#121722"
                        border.color: loginUserField.activeFocus ? "#38BDF8" : (loginUserField.hovered ? "#475569" : "#1E293B")
                        border.width: loginUserField.activeFocus ? 1.5 : 1
                    }
                    TextBarContextArea {}
                }

                TextField {
                    id: loginPassField
                    objectName: "loginPasswordField"
                    Layout.fillWidth: true
                    echoMode: TextInput.Password
                    placeholderText: "Password"
                    color: "#F8FAFC"
                    placeholderTextColor: "#64748B"
                    selectionColor: "#0284C7"
                    selectedTextColor: "#FFFFFF"
                    selectByMouse: true
                    clip: true
                    verticalAlignment: TextInput.AlignVCenter
                    background: Rectangle {
                        radius: 6
                        color: loginPassField.activeFocus ? "#0B0D12" : "#121722"
                        border.color: loginPassField.activeFocus ? "#38BDF8" : (loginPassField.hovered ? "#475569" : "#1E293B")
                        border.width: loginPassField.activeFocus ? 1.5 : 1
                    }
                    onAccepted: {
                        if (providerLoginModal.view.bBridge && !(providerLoginModal.view.bBridge.isLoggingInProvider)) {
                            providerLoginModal.view.loginModalError = ""
                            providerLoginModal.view.bBridge.loginProvider(providerLoginModal.targetPid, loginUserField.text, loginPassField.text)
                        }
                    }
                    TextBarContextArea {}
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 34
                    radius: 7
                    opacity: (providerLoginModal.view.bBridge && providerLoginModal.view.bBridge.isLoggingInProvider) ? 0.6 : 1.0
                    color: loginSubMouse.containsMouse ? "#D97706" : "#F59E0B"
                    Springy { hover: loginSubMouse.containsMouse; pressed: loginSubMouse.pressed }

                    Text {
                        anchors.centerIn: parent
                        text: (providerLoginModal.view.bBridge && providerLoginModal.view.bBridge.isLoggingInProvider) ? "Signing in…" : "Log In to " + providerLoginModal.targetDisplayName
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        font.weight: Font.Bold
                        color: "#0F172A"
                    }
                    MouseArea {
                        id: loginSubMouse
                        objectName: "loginSubmitBtn"
                        anchors.fill: parent
                        enabled: !(providerLoginModal.view.bBridge && providerLoginModal.view.bBridge.isLoggingInProvider)
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (providerLoginModal.view.bBridge) {
                                providerLoginModal.view.loginModalError = ""
                                providerLoginModal.view.bBridge.loginProvider(providerLoginModal.targetPid, loginUserField.text, loginPassField.text)
                            }
                        }
                    }
                }
            }
        }

        // Browser Cookie Import / Paste Cookie
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: cookieCol.implicitHeight + 20
            radius: 8
            color: "#0B0F19"
            border.color: "#1E293B"
            border.width: 1

            ColumnLayout {
                id: cookieCol
                anchors.fill: parent
                anchors.margins: 10
                spacing: 8

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 32
                    radius: 7
                    opacity: (providerLoginModal.view.bBridge && providerLoginModal.view.bBridge.isLoggingInProvider) ? 0.6 : 1.0
                    color: importCookieMouse.containsMouse ? "#1E293B" : "#121722"
                    border.color: "#38BDF8"
                    border.width: 1
                    Springy { hover: importCookieMouse.containsMouse; pressed: importCookieMouse.pressed }

                    Text {
                        anchors.centerIn: parent
                        text: "🌐 1-Click Import Session Cookies from Browser"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: Font.Bold
                        color: "#38BDF8"
                    }
                    MouseArea {
                        id: importCookieMouse
                        objectName: "loginImportCookiesBtn"
                        anchors.fill: parent
                        enabled: !(providerLoginModal.view.bBridge && providerLoginModal.view.bBridge.isLoggingInProvider)
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (providerLoginModal.view.bBridge) {
                                providerLoginModal.view.loginModalError = ""
                                providerLoginModal.view.bBridge.importProviderCookies(providerLoginModal.targetPid, "")
                            }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    TextField {
                        id: loginCookieField
                        objectName: "loginCookieField"
                        Layout.fillWidth: true
                        placeholderText: "Or paste Cookie header (e.g. session=...)"
                        color: "#F8FAFC"
                        placeholderTextColor: "#64748B"
                        selectionColor: "#0284C7"
                        selectedTextColor: "#FFFFFF"
                        selectByMouse: true
                        clip: true
                        verticalAlignment: TextInput.AlignVCenter
                        font.pixelSize: 11
                        background: Rectangle {
                            radius: 6
                            color: loginCookieField.activeFocus ? "#0B0D12" : "#121722"
                            border.color: loginCookieField.activeFocus ? "#38BDF8" : (loginCookieField.hovered ? "#475569" : "#1E293B")
                            border.width: loginCookieField.activeFocus ? 1.5 : 1
                        }
                        TextBarContextArea {}
                    }
                    Rectangle {
                        Layout.preferredHeight: 32
                        implicitWidth: verifyCBtnTxt.implicitWidth + 18
                        radius: 6
                        color: verifyCookieMouse.containsMouse ? "#0EA5E9" : "#0284C7"
                        Springy { hover: verifyCookieMouse.containsMouse; pressed: verifyCookieMouse.pressed }
                        Text {
                            id: verifyCBtnTxt
                            anchors.centerIn: parent
                            text: "Verify"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: Font.Bold
                            color: "#FFFFFF"
                        }
                        MouseArea {
                            id: verifyCookieMouse
                            objectName: "loginVerifyCookieBtn"
                            anchors.fill: parent
                            enabled: !(providerLoginModal.view.bBridge && providerLoginModal.view.bBridge.isLoggingInProvider)
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (providerLoginModal.view.bBridge) {
                                    providerLoginModal.view.loginModalError = ""
                                    providerLoginModal.view.bBridge.saveProviderCookie(providerLoginModal.targetPid, loginCookieField.text)
                                }
                            }
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Rectangle {
                Layout.preferredHeight: 28
                implicitWidth: openSettingsAuthTxt.implicitWidth + 14
                radius: 6
                color: openSettingsAuthMouse.containsMouse ? "#1E293B" : "transparent"
                border.color: "#334155"
                border.width: 1
                Text {
                    id: openSettingsAuthTxt
                    anchors.centerIn: parent
                    text: "⚙️ Accounts in Settings"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                }
                MouseArea {
                    id: openSettingsAuthMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: {
                        providerLoginModal.close()
                        if (providerLoginModal.view.bBridge) providerLoginModal.view.bBridge.navigateToTabRequested(11)
                    }
                }
            }
            Item { Layout.fillWidth: true }
            Rectangle {
                Layout.preferredHeight: 28
                implicitWidth: 74
                radius: 6
                color: cancelAuthMouse.containsMouse ? "#1E293B" : "#121722"
                border.color: "#334155"
                border.width: 1
                Text {
                    anchors.centerIn: parent
                    text: "Cancel"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#CBD5E1"
                }
                MouseArea {
                    id: cancelAuthMouse
                    objectName: "loginCancelBtn"
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: providerLoginModal.close()
                }
            }
        }
    }
}
