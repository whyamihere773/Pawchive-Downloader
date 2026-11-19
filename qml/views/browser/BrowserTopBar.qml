import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

Rectangle {
    id: topBar
    required property var view
    objectName: "browserTopBar"
    Layout.fillWidth: true
    Layout.preferredHeight: topBarFlow.implicitHeight + 12
    radius: 10
    color: "#0F131C"
    border.color: "#1E2536"
    border.width: 1
    clip: true

    Flow {
        id: topBarFlow
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 6
        spacing: 8

        // ── Dual-Mode Switcher (Online Mode <-> Local Disk Mode) ────
        Rectangle {
            id: modeDock
            height: 34
            width: Math.min(276, Math.max(120, topBarFlow.width))
            radius: 8
            color: "#090C12"
            border.color: "#1E293B"
            border.width: 1
            clip: true

            // Newtonian Liquid Glider Pill
            Rectangle {
                id: modeGlider
                readonly property real slotW: Math.max(40, (modeDock.width - 10) / 2)
                y: 3
                height: 28
                width: slotW
                radius: 6
                x: topBar.view.isLocalMode ? (modeDock.width - 4 - slotW) : 4
                color: topBar.view.isLocalMode ? "#064E3B" : "#172554"
                border.color: topBar.view.isLocalMode ? "#10B981" : "#38BDF8"
                border.width: 1

                Behavior on x {
                    NumberAnimation { duration: 130; easing.type: Easing.OutCubic }
                }
                Behavior on color { ColorAnimation { duration: 120 } }
                Behavior on border.color { ColorAnimation { duration: 180 } }
            }

            RowLayout {
                anchors.fill: parent
                anchors.margins: 3
                spacing: 4

                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Springy { hover: onlineModeMouse.containsMouse; pressed: onlineModeMouse.pressed }

                    Row {
                        anchors.centerIn: parent
                        spacing: 5
                        Text { text: "🌐"; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: "Online Browser"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: !topBar.view.isLocalMode ? Font.Bold : Font.Medium
                            color: !topBar.view.isLocalMode ? "#F8FAFC" : "#94A3B8"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                    MouseArea {
                        id: onlineModeMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: "Browse live creators & posts online and mark them into your Download Cart"
                        onClicked: if (topBar.view.bBridge) topBar.view.bBridge.setBrowserMode("online")
                    }
                }

                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Springy { hover: localModeMouse.containsMouse; pressed: localModeMouse.pressed }

                    Row {
                        anchors.centerIn: parent
                        spacing: 5
                        Text { text: "💾"; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                        Text {
                            text: "Local On-Disk"
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            font.weight: topBar.view.isLocalMode ? Font.Bold : Font.Medium
                            color: topBar.view.isLocalMode ? "#ECFDF5" : "#94A3B8"
                            anchors.verticalCenter: parent.verticalCenter
                        }
                    }
                    MouseArea {
                        id: localModeMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 300
                        ToolTip.text: "Browse ONLY creators and posts present on your local drives — with multi-drive support"
                        onClicked: if (topBar.view.bBridge) topBar.view.bBridge.setBrowserMode("local")
                    }
                }
            }
        }

        // ── ONLINE MODE: Capability-Driven Modular Provider Switcher ─
        Repeater {
            model: topBar.view.providersManifest

            delegate: Rectangle {
                readonly property var pData: modelData || ({})
                readonly property bool isCurrent: topBar.view.activeProvider === pData.id
                readonly property string accent: pData.accentColor || "#38BDF8"

                visible: !topBar.view.isLocalMode
                height: 34
                width: Math.min(topBarFlow.width, provPillRow.implicitWidth + 20)
                radius: 7
                color: isCurrent ? "#182235" : (provMouse.containsMouse ? "#141A28" : "#0B0E16")
                border.color: isCurrent ? accent : "#1E293B"
                border.width: isCurrent ? 1.5 : 1

                Springy { hover: provMouse.containsMouse; pressed: provMouse.pressed }
                Behavior on color { ColorAnimation { duration: 150 } }
                Behavior on border.color { ColorAnimation { duration: 150 } }

                Row {
                    id: provPillRow
                    anchors.centerIn: parent
                    spacing: 6
                    Text {
                        text: pData.icon || "🌐"
                        font.pixelSize: 12
                        anchors.verticalCenter: parent.verticalCenter
                    }
                    Text {
                        text: pData.name || pData.id || ""
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 12
                        font.weight: isCurrent ? Font.Bold : Font.Medium
                        color: isCurrent ? "#F8FAFC" : "#94A3B8"
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }

                MouseArea {
                    id: provMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 300
                    ToolTip.text: "Switch provider to " + (pData.domain || pData.name || "")
                    onClicked: if (topBar.view.bBridge) topBar.view.bBridge.setActiveProvider(pData.id)
                }
            }
        }

        // ── LOCAL MODE: Multi-Drive Filter Pills & Folder Manager ───
        Rectangle {
            id: allDrvChip
            readonly property bool isAll: !topBar.view.bBridge || topBar.view.bBridge.activeDriveFilter === "all"
            visible: topBar.view.isLocalMode
            height: 34
            width: Math.min(topBarFlow.width, allDrvRow.implicitWidth + 16)
            radius: 6
            color: isAll ? "#064E3B" : "#121824"
            border.color: isAll ? "#10B981" : "#1E293B"
            border.width: 1
            Springy { hover: allDrvMouse.containsMouse; pressed: allDrvMouse.pressed }

            Row {
                id: allDrvRow
                anchors.centerIn: parent
                spacing: 5
                Text { text: "💽"; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                Text {
                    text: "All Drives"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: allDrvChip.isAll ? Font.Bold : Font.Medium
                    color: allDrvChip.isAll ? "#ECFDF5" : "#94A3B8"
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
            MouseArea {
                id: allDrvMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: if (topBar.view.bBridge) topBar.view.bBridge.setDriveFilter("all")
            }
        }

        Repeater {
            model: topBar.view.bBridge ? topBar.view.bBridge.localDrives : []

            delegate: Rectangle {
                readonly property var dInfo: modelData || ({})
                readonly property bool isSel: topBar.view.bBridge && topBar.view.bBridge.activeDriveFilter === dInfo.drive

                visible: topBar.view.isLocalMode
                height: 34
                width: Math.min(topBarFlow.width, drvChipRow.implicitWidth + rmDrvBtn.width + 20)
                radius: 6
                color: isSel ? "#064E3B" : "#121824"
                border.color: isSel ? "#10B981" : "#1E293B"
                border.width: 1
                clip: true
                Springy { hover: drvChipMouse.containsMouse; pressed: drvChipMouse.pressed }

                Row {
                    id: drvChipRow
                    anchors.left: parent.left
                    anchors.leftMargin: 8
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 5
                    Text { text: "💽"; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                    Text {
                        width: Math.min(implicitWidth, Math.max(60, topBarFlow.width - rmDrvBtn.width - 48))
                        text: (dInfo.drive || "") + " (" + Number(dInfo.free_gb || 0).toFixed(0) + " GB free)"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: isSel ? Font.Bold : Font.Medium
                        color: isSel ? "#ECFDF5" : "#CBD5E1"
                        elide: Text.ElideRight
                        anchors.verticalCenter: parent.verticalCenter
                    }
                }
                MouseArea {
                    id: drvChipMouse
                    z: 1
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    anchors.right: rmDrvBtn.left
                    anchors.rightMargin: 2
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    ToolTip.visible: containsMouse
                    ToolTip.delay: 300
                    ToolTip.text: "Filter creators stored on drive " + (dInfo.drive || "") + " (" + (dInfo.root_path || "") + ")"
                    onClicked: if (topBar.view.bBridge) topBar.view.bBridge.setDriveFilter(dInfo.drive)
                }
                Rectangle {
                    id: rmDrvBtn
                    z: 2
                    width: 18
                    height: 18
                    radius: 4
                    anchors.right: parent.right
                    anchors.rightMargin: 5
                    anchors.verticalCenter: parent.verticalCenter
                    color: rmDrvMouse.containsMouse ? "#991B1B" : "#1E293B"
                    border.color: rmDrvMouse.containsMouse ? "#F87171" : "#334155"
                    border.width: 1
                    Text {
                        anchors.centerIn: parent
                        text: "✕"
                        font.pixelSize: 9
                        font.weight: Font.Bold
                        color: rmDrvMouse.containsMouse ? "#FEE2E2" : "#94A3B8"
                    }
                    MouseArea {
                        id: rmDrvMouse
                        objectName: "removeLocalDriveMouse"
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 250
                        ToolTip.text: "Hide drive " + (dInfo.drive || "") + " from Local Browser"
                        onClicked: if (topBar.view.bBridge) topBar.view.bBridge.removeLocalDrive(dInfo.drive || "", dInfo.root_path || "")
                    }
                }
            }
        }

        // Add Another Drive / Folder Root Button
        Rectangle {
            visible: topBar.view.isLocalMode
            height: 34
            width: Math.min(topBarFlow.width, addRootRow.implicitWidth + 16)
            radius: 6
            color: addRootMouse.containsMouse ? "#1E293B" : "#131926"
            border.color: "#38BDF8"
            border.width: 1
            Springy { hover: addRootMouse.containsMouse; pressed: addRootMouse.pressed }

            Row {
                id: addRootRow
                anchors.centerIn: parent
                spacing: 5
                Text { text: "📁+"; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
                Text {
                    text: "Add Drive Folder…"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: 600
                    color: "#38BDF8"
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
            MouseArea {
                id: addRootMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                ToolTip.visible: containsMouse
                ToolTip.delay: 300
                ToolTip.text: "Add another disk folder where you moved or stored downloaded artists"
                onClicked: topBar.view.openAddLibraryRootDialog()
            }
        }

        // Restore Hidden / Excluded Drives Button
        Rectangle {
            id: restoreDrivesBtn
            visible: topBar.view.isLocalMode && !!(topBar.view.bBridge && topBar.view.bBridge.excludedLocalDrives && topBar.view.bBridge.excludedLocalDrives.length > 0)
            height: 34
            width: Math.min(topBarFlow.width, restoreDrvRow.implicitWidth + 16)
            radius: 6
            color: restoreDrvMouse.containsMouse ? "#1E293B" : "#131926"
            border.color: "#F59E0B"
            border.width: 1
            Springy { hover: restoreDrvMouse.containsMouse; pressed: restoreDrvMouse.pressed }

            Row {
                id: restoreDrvRow
                anchors.centerIn: parent
                spacing: 5
                Text { text: "↺"; font.pixelSize: 12; color: "#FBBF24"; anchors.verticalCenter: parent.verticalCenter }
                Text {
                    text: "Restore (" + ((topBar.view.bBridge && topBar.view.bBridge.excludedLocalDrives) ? topBar.view.bBridge.excludedLocalDrives.length : 0) + ")"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: 600
                    color: "#FDE68A"
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
            MouseArea {
                id: restoreDrvMouse
                objectName: "restoreDrivesBtnMouse"
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                ToolTip.visible: containsMouse
                ToolTip.delay: 300
                ToolTip.text: "Restore previously removed default or system drives"
                onClicked: if (topBar.view.bBridge) topBar.view.bBridge.restoreDefaultLocalDrives()
            }
        }

        // ── Online Target Toggle: Creators vs Global Posts ──────────
        Rectangle {
            visible: !topBar.view.isLocalMode && !topBar.view.hasSelectedCreator && !!topBar.view.activeCaps.supportsGlobalPostSearch
            height: 34
            width: Math.min(topBarFlow.width, targetRow.implicitWidth + 16)
            radius: 7
            color: "#121722"
            border.color: "#263248"
            border.width: 1

            Row {
                id: targetRow
                anchors.centerIn: parent
                spacing: 4

                Rectangle {
                    id: cTgtChip
                    readonly property bool isC: !topBar.view.bBridge || topBar.view.bBridge.searchTarget === "creators"
                    height: 26
                    width: cTgtTxt.implicitWidth + 14
                    radius: 5
                    color: isC ? "#1E293B" : "transparent"
                    Text {
                        id: cTgtTxt
                        anchors.centerIn: parent
                        text: "👤 Creators"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: cTgtChip.isC ? Font.Bold : Font.Normal
                        color: cTgtChip.isC ? "#38BDF8" : "#94A3B8"
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: if (topBar.view.bBridge) topBar.view.bBridge.setSearchTarget("creators")
                    }
                }

                Rectangle {
                    id: pTgtChip
                    readonly property bool isP: topBar.view.bBridge && topBar.view.bBridge.searchTarget === "posts"
                    height: 26
                    width: pTgtTxt.implicitWidth + 14
                    radius: 5
                    color: isP ? "#1E293B" : "transparent"
                    Text {
                        id: pTgtTxt
                        anchors.centerIn: parent
                        text: "🖼️ Posts"
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 11
                        font.weight: pTgtChip.isP ? Font.Bold : Font.Normal
                        color: pTgtChip.isP ? "#38BDF8" : "#94A3B8"
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: if (topBar.view.bBridge) topBar.view.bBridge.setSearchTarget("posts")
                    }
                }
            }
        }

        // ── Live Downloader Status Pill (1-Click Jump to Downloader) ──
        Rectangle {
            id: activeDlChip
            visible: !!(topBar.view.bridge && topBar.view.bridge.isDownloading)
            height: 34
            width: Math.min(topBarFlow.width, activeDlRow.implicitWidth + 16)
            radius: 7
            color: activeDlMouse.containsMouse ? "#065F46" : "#064E3B"
            border.color: "#34D399"
            border.width: 1
            Springy { hover: activeDlMouse.containsMouse; pressed: activeDlMouse.pressed }

            Row {
                id: activeDlRow
                anchors.centerIn: parent
                spacing: 6
                Text { text: "⬇"; font.pixelSize: 11; color: "#6EE7B7"; anchors.verticalCenter: parent.verticalCenter }
                Text {
                    text: "Downloading… · View"
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    font.weight: Font.Bold
                    color: "#ECFDF5"
                    anchors.verticalCenter: parent.verticalCenter
                }
            }
            MouseArea {
                id: activeDlMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                ToolTip.visible: containsMouse
                ToolTip.delay: 250
                ToolTip.text: "A download is running — click to switch to the Downloader tab"
                onClicked: if (topBar.view.bBridge) topBar.view.bBridge.openDownloaderTab()
            }
        }

        // ── Refresh Button ──────────────────────────────────────────
        Rectangle {
            height: 34
            width: 36
            radius: 7
            color: refMouse.containsMouse ? "#1E293B" : "#141926"
            border.color: "#2E3A52"
            border.width: 1
            Springy { hover: refMouse.containsMouse; pressed: refMouse.pressed }

            Text {
                anchors.centerIn: parent
                text: "🔄"
                font.pixelSize: 13
            }
            MouseArea {
                id: refMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                ToolTip.visible: containsMouse
                ToolTip.delay: 300
                ToolTip.text: topBar.view.isLocalMode ? "Rescan all local drives & heal moved artist paths" : "Refresh current page"
                onClicked: {
                    if (!topBar.view.bBridge) return
                    if (topBar.view.hasSelectedCreator) {
                        topBar.view.bBridge.loadCreatorPosts(topBar.view.bBridge.creatorPostsOffset, topBar.view.creatorPostSearchText)
                    } else {
                        topBar.view.bBridge.refresh(topBar.view.isLocalMode)
                    }
                }
            }
        }
    }
}
