import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

// Non-intrusive banner shown in SettingsView and DownloaderView when queued/active
// downloads are running and uncommitted/newly saved setting changes affect them.
Rectangle {
    id: banner
    property var bridge: null
    property bool suppressed: false

    readonly property bool active: !suppressed && Boolean(bridge && bridge.isDownloading && bridge.hasPendingDownloadSettingsChanges)
    property real reveal: active ? 1.0 : 0.0

    Behavior on reveal {
        NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
    }

    visible: active || reveal > 0.01
    clip: true
    Layout.fillHeight: false
    implicitHeight: visible ? Math.round((bannerLayout.implicitHeight + 18) * reveal) : 0
    Layout.preferredHeight: implicitHeight
    opacity: reveal
    radius: 10
    color: "#1B1E2E"
    border.color: "#F59E0B"
    border.width: 1

    function tr(key, fallback) {
        if (typeof Lang !== "undefined" && Lang) {
            var _ = Lang.activeLanguage
            var res = Lang.t(key)
            return (res && res !== key) ? res : (fallback !== undefined ? fallback : res)
        }
        return fallback !== undefined ? fallback : key
    }

    RowLayout {
        id: bannerLayout
        anchors {
            left: parent.left
            right: parent.right
            verticalCenter: parent.verticalCenter
            leftMargin: 12
            rightMargin: 12
        }
        spacing: 10

        Text {
            text: "⚡"
            font.pixelSize: 16
            Layout.alignment: Qt.AlignTop
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2

            Text {
                Layout.fillWidth: true
                text: banner.tr("banner_pending_settings_title", "Download settings changed while queue is active")
                font.family: "Segoe UI, Inter, sans-serif"
                font.pixelSize: 12
                font.bold: true
                color: "#FCD34D"
                elide: Text.ElideRight
            }

            Text {
                Layout.fillWidth: true
                text: (banner.bridge && banner.bridge.pendingSettingsDiffSummary) ? banner.bridge.pendingSettingsDiffSummary : ""
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                color: "#CBD5E1"
                wrapMode: Text.WordWrap
                maximumLineCount: 2
                elide: Text.ElideRight
            }
        }

        StyledButton {
            text: banner.tr("btn_apply_mid_settings", "Apply Changes...")
            variant: "primary"
            implicitHeight: 30
            onClicked: {
                if (banner.bridge && banner.bridge.requestMidDownloadSettingsPrompt) {
                    banner.bridge.requestMidDownloadSettingsPrompt("global", "", "")
                }
            }
        }

        StyledButton {
            text: banner.tr("btn_dismiss", "Dismiss")
            variant: "ghost"
            implicitHeight: 30
            onClicked: {
                if (banner.bridge && banner.bridge.dismissPendingDownloadSettingsBanner) {
                    banner.bridge.dismissPendingDownloadSettingsBanner()
                }
            }
        }
    }
}
