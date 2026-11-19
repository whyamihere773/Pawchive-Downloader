import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

// Right Panel: Live Console Log View & Active Downloads Panel
Rectangle {
    id: consoleContainer
    required property var window
    required property var splitView

    readonly property real maxAllowedConsoleWidth: Math.max(320, consoleContainer.splitView.width - 380)
    readonly property real baseConsoleWidth: {
        var raw = appBridge ? appBridge.consoleWidth : 680
        return Math.min(raw, maxAllowedConsoleWidth)
    }
    // Open / close motion. Opening: width 320 ms, fade 260 ms, content slide 380 ms, all
    // starting together. Closing is the same motion played backwards over 380 ms: the slide
    // starts first, the width follows 60 ms later and the fade 120 ms later, so all three end
    // together. Two fixed animations (rather than Behaviors whose timing depends on
    // showConsole) so the close can never pick up the opening timing.
    property real widthProgress: 0          // 0 = closed, 1 = open
    property real slideX: 35                // content offset while closed
    opacity: 0
    readonly property real animConsoleWidth: baseConsoleWidth * widthProgress
    readonly property bool isOpeningOrClosing: consoleOpenAnim.running || consoleCloseAnim.running

    ParallelAnimation {
        id: consoleOpenAnim
        NumberAnimation { target: consoleContainer; property: "widthProgress"; to: 1; duration: 320; easing.type: Easing.OutCubic }
        NumberAnimation { target: consoleContainer; property: "opacity"; to: 1; duration: 260; easing.type: Easing.OutCubic }
        NumberAnimation { target: consoleContainer; property: "slideX"; to: 0; duration: 380; easing.type: Easing.OutBack; easing.overshoot: 1.25 }
    }
    ParallelAnimation {
        id: consoleCloseAnim
        SequentialAnimation {
            PauseAnimation { duration: 60 }
            NumberAnimation { target: consoleContainer; property: "widthProgress"; to: 0; duration: 320; easing.type: Easing.InCubic }
        }
        SequentialAnimation {
            PauseAnimation { duration: 120 }
            NumberAnimation { target: consoleContainer; property: "opacity"; to: 0; duration: 260; easing.type: Easing.InCubic }
        }
        // InBack is OutBack played backwards: a small pull the other way, then out
        NumberAnimation { target: consoleContainer; property: "slideX"; to: 35; duration: 380; easing.type: Easing.InBack; easing.overshoot: 1.25 }
    }
    Connections {
        target: consoleContainer.window
        function onShowConsoleChanged() {
            if (consoleContainer.window.showConsole) { consoleCloseAnim.stop(); consoleOpenAnim.restart() }
            else { consoleOpenAnim.stop(); consoleCloseAnim.restart() }
        }
    }
    Component.onCompleted: {
        var on = consoleContainer.window.showConsole
        widthProgress = on ? 1 : 0
        opacity = on ? 1 : 0
        slideX = on ? 0 : 35
    }

    SplitView.preferredWidth: consoleContainer.splitView.isHandleDragging ? width : animConsoleWidth
    SplitView.minimumWidth: (consoleContainer.window.showConsole && !isOpeningOrClosing) ? 320 : 0
    SplitView.maximumWidth: (consoleContainer.window.showConsole || isOpeningOrClosing) ? maxAllowedConsoleWidth : 0
    visible: animConsoleWidth > 2
    clip: true
    color: "#0B0D12"

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 8

        transform: Translate { x: consoleContainer.slideX }

        ActiveDownloadsPanel {
            id: activeDownloadsPanel
            Layout.fillWidth: true
            bridge: appBridge
            visible: implicitHeight > 0.5 || (appBridge && appBridge.activeQueueModel && appBridge.activeQueueModel.count > 0)
        }

        ConsoleLogView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            logModel: appBridge ? appBridge.logModel : null
            onExportLogsRequested: if (appBridge) appBridge.exportLogs()
            onClearLogsRequested: if (appBridge) appBridge.clearLogs()
            onExportLinksRequested: if (appBridge) appBridge.exportAllLinks()
            onDownloadLinksRequested: consoleContainer.window.openCloudModal()
        }
    } // ColumnLayout inside consoleContainer
} // consoleContainer
