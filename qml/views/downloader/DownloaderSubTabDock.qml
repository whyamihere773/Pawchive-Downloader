import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

Rectangle {
    id: subTabDock
    required property var view
    Layout.fillWidth: true
    implicitHeight: 46
    radius: 10
    color: "#0F131C"
    border.color: "#1E2536"
    border.width: 1

    readonly property bool isCompact: width < 660

    readonly property var activeBtn: {
        if (subTabDock.view.currentSubTab === 0) return tabBtn0
        if (subTabDock.view.currentSubTab === 1) return tabBtn1
        if (subTabDock.view.currentSubTab === 2) return tabBtn2
        return tabBtn3
    }

    // Liquid Gliding Active Indicator Pill
    Rectangle {
        id: tabGlider
        y: 5
        height: 36
        radius: 8
        color: "#1B2232"
        border.color: "#38BDF8"
        border.width: 1
        x: subTabDock.activeBtn ? (subTabDock.activeBtn.x + 4) : 4
        width: subTabDock.activeBtn ? subTabDock.activeBtn.width : 100

        // Liquid soft cyan aura
        Rectangle {
            anchors.fill: parent
            radius: 7
            color: Qt.rgba(56/255, 189/255, 248/255, 0.08)
        }

        // Newtonian Fluid Spring Physics for gliding between tabs
        Behavior on x {
            SpringAnimation {
                spring: 4.8
                damping: 0.35
                mass: 0.85
                epsilon: 0.2
            }
        }
        Behavior on width {
            SpringAnimation {
                spring: 5.0
                damping: 0.36
                mass: 0.85
                epsilon: 0.2
            }
        }
    }

    RowLayout {
        id: tabRow
        anchors.fill: parent
        anchors.margins: 4
        spacing: 4

        // Tab 0: Quick Download
        Item {
            id: tabBtn0
            Layout.fillWidth: true
            Layout.fillHeight: true

            scale: tabMouse0.pressed ? 0.93 : (tabMouse0.containsMouse ? 1.025 : 1.0)
            transformOrigin: Item.Center
            Behavior on scale {
                SpringAnimation { spring: 5.2; damping: 0.32; mass: 0.70; epsilon: 0.005 }
            }

            transform: Translate {
                y: tabMouse0.containsMouse ? -1.0 : 0.0
                Behavior on y {
                    SpringAnimation { spring: 4.8; damping: 0.35; mass: 0.75; epsilon: 0.1 }
                }
            }

            Row {
                anchors.centerIn: parent
                spacing: subTabDock.isCompact ? 4 : 6

                Text {
                    text: "⚡"
                    font.pixelSize: subTabDock.isCompact ? 12 : 13
                    anchors.verticalCenter: parent.verticalCenter
                    scale: (subTabDock.view.currentSubTab === 0 || tabMouse0.containsMouse) ? 1.15 : 1.0
                    Behavior on scale {
                        SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.7; epsilon: 0.01 }
                    }
                }

                Text {
                    text: subTabDock.isCompact ? subTabDock.view.tr("tab_quick_short", "Quick") : subTabDock.view.tr("tab_quick_download", "Quick Download")
                    font.family: "Segoe UI, Inter, sans-serif"
                    font.pixelSize: subTabDock.isCompact ? 11 : 12
                    font.weight: subTabDock.view.currentSubTab === 0 ? 600 : Font.Medium
                    color: subTabDock.view.currentSubTab === 0 ? "#F8FAFC" : (tabMouse0.containsMouse ? "#CBD5E1" : "#94A3B8")
                    elide: Text.ElideRight
                    width: Math.min(implicitWidth, tabBtn0.width - (subTabDock.isCompact ? 24 : 32))
                    anchors.verticalCenter: parent.verticalCenter
                    Behavior on color { ColorAnimation { duration: 150 } }
                }
            }

            MouseArea {
                id: tabMouse0
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: subTabDock.view.currentSubTab = 0
            }
        }

        // Tab 1: Filters & Dates
        Item {
            id: tabBtn1
            Layout.fillWidth: true
            Layout.fillHeight: true

            scale: tabMouse1.pressed ? 0.93 : (tabMouse1.containsMouse ? 1.025 : 1.0)
            transformOrigin: Item.Center
            Behavior on scale {
                SpringAnimation { spring: 5.2; damping: 0.32; mass: 0.70; epsilon: 0.005 }
            }

            transform: Translate {
                y: tabMouse1.containsMouse ? -1.0 : 0.0
                Behavior on y {
                    SpringAnimation { spring: 4.8; damping: 0.35; mass: 0.75; epsilon: 0.1 }
                }
            }

            Row {
                anchors.centerIn: parent
                spacing: subTabDock.isCompact ? 4 : 5

                Text {
                    text: "🎯"
                    font.pixelSize: subTabDock.isCompact ? 12 : 13
                    anchors.verticalCenter: parent.verticalCenter
                    scale: (subTabDock.view.currentSubTab === 1 || tabMouse1.containsMouse) ? 1.15 : 1.0
                    Behavior on scale {
                        SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.7; epsilon: 0.01 }
                    }
                }

                Text {
                    text: subTabDock.isCompact ? subTabDock.view.tr("tab_filters_short", "Filters") : subTabDock.view.tr("tab_filters_dates", "Filters & Dates")
                    font.family: "Segoe UI, Inter, sans-serif"
                    font.pixelSize: subTabDock.isCompact ? 11 : 12
                    font.weight: subTabDock.view.currentSubTab === 1 ? 600 : Font.Medium
                    color: subTabDock.view.currentSubTab === 1 ? "#F8FAFC" : (tabMouse1.containsMouse ? "#CBD5E1" : "#94A3B8")
                    elide: Text.ElideRight
                    width: Math.min(implicitWidth, tabBtn1.width - (subTabDock.view.activeFilterCount > 0 ? 42 : 28))
                    anchors.verticalCenter: parent.verticalCenter
                    Behavior on color { ColorAnimation { duration: 150 } }
                }

                // Active filter count mini-pill
                Rectangle {
                    id: filterBadge
                    visible: subTabDock.view.activeFilterCount > 0
                    width: visible ? 16 : 0
                    height: 16
                    radius: 8
                    color: "#0369A1"
                    border.color: "#38BDF8"
                    border.width: 1
                    anchors.verticalCenter: parent.verticalCenter

                    scale: visible ? 1.0 : 0.0
                    Behavior on scale {
                        SpringAnimation { spring: 5.5; damping: 0.32; mass: 0.75; epsilon: 0.01 }
                    }

                    Text {
                        anchors.centerIn: parent
                        text: subTabDock.view.activeFilterCount.toString()
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 9
                        font.bold: true
                        color: "#F0F9FF"
                    }
                }
            }

            MouseArea {
                id: tabMouse1
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: subTabDock.view.currentSubTab = 1
            }
        }

        // Tab 2: Structure & Engine
        Item {
            id: tabBtn2
            Layout.fillWidth: true
            Layout.fillHeight: true

            scale: tabMouse2.pressed ? 0.93 : (tabMouse2.containsMouse ? 1.025 : 1.0)
            transformOrigin: Item.Center
            Behavior on scale {
                SpringAnimation { spring: 5.2; damping: 0.32; mass: 0.70; epsilon: 0.005 }
            }

            transform: Translate {
                y: tabMouse2.containsMouse ? -1.0 : 0.0
                Behavior on y {
                    SpringAnimation { spring: 4.8; damping: 0.35; mass: 0.75; epsilon: 0.1 }
                }
            }

            Row {
                anchors.centerIn: parent
                spacing: subTabDock.isCompact ? 4 : 6

                Text {
                    text: "⚙️"
                    font.pixelSize: subTabDock.isCompact ? 12 : 13
                    anchors.verticalCenter: parent.verticalCenter
                    scale: (subTabDock.view.currentSubTab === 2 || tabMouse2.containsMouse) ? 1.15 : 1.0
                    Behavior on scale {
                        SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.7; epsilon: 0.01 }
                    }
                }

                Text {
                    text: subTabDock.isCompact ? subTabDock.view.tr("tab_structure_short", "Engine") : subTabDock.view.tr("tab_structure_engine", "Structure & Engine")
                    font.family: "Segoe UI, Inter, sans-serif"
                    font.pixelSize: subTabDock.isCompact ? 11 : 12
                    font.weight: subTabDock.view.currentSubTab === 2 ? 600 : Font.Medium
                    color: subTabDock.view.currentSubTab === 2 ? "#F8FAFC" : (tabMouse2.containsMouse ? "#CBD5E1" : "#94A3B8")
                    elide: Text.ElideRight
                    width: Math.min(implicitWidth, tabBtn2.width - (subTabDock.isCompact ? 36 : 50))
                    anchors.verticalCenter: parent.verticalCenter
                    Behavior on color { ColorAnimation { duration: 150 } }
                }

                // Concurrency & Adaptive thread chip mini-pill
                Rectangle {
                    id: threadBadge
                    implicitWidth: threadBadgeText.implicitWidth + 10
                    height: 16
                    radius: 8
                    color: (subTabDock.view.bridge && subTabDock.view.bridge.threadsLocked) ? "#3A1A1C"
                           : ((subTabDock.view.bridge && subTabDock.view.bridge.adaptiveThreading) ? "#291E0A" : "#0C1828")
                    border.color: (subTabDock.view.bridge && subTabDock.view.bridge.threadsLocked) ? "#EF4444"
                                  : ((subTabDock.view.bridge && subTabDock.view.bridge.adaptiveThreading) ? "#F59E0B" : "#164E63")
                    border.width: 1
                    anchors.verticalCenter: parent.verticalCenter

                    Text {
                        id: threadBadgeText
                        anchors.centerIn: parent
                        text: subTabDock.view.threadChipText
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 9
                        font.bold: true
                        color: (subTabDock.view.bridge && subTabDock.view.bridge.threadsLocked) ? "#FCA5A5"
                               : ((subTabDock.view.bridge && subTabDock.view.bridge.adaptiveThreading) ? "#FCD34D" : "#7DD3FA")
                    }
                }
            }

            MouseArea {
                id: tabMouse2
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: subTabDock.view.currentSubTab = 2
            }
        }

        // Tab 3: Batch Importer
        Item {
            id: tabBtn3
            visible: !subTabDock.view.embeddedInModal
            Layout.fillWidth: !subTabDock.view.embeddedInModal
            Layout.fillHeight: true

            scale: tabMouse3.pressed ? 0.93 : (tabMouse3.containsMouse ? 1.025 : 1.0)
            transformOrigin: Item.Center
            Behavior on scale {
                SpringAnimation { spring: 5.2; damping: 0.32; mass: 0.70; epsilon: 0.005 }
            }

            transform: Translate {
                y: tabMouse3.containsMouse ? -1.0 : 0.0
                Behavior on y {
                    SpringAnimation { spring: 4.8; damping: 0.35; mass: 0.75; epsilon: 0.1 }
                }
            }

            Row {
                anchors.centerIn: parent
                spacing: subTabDock.isCompact ? 4 : 5

                Text {
                    text: "📋"
                    font.pixelSize: subTabDock.isCompact ? 12 : 13
                    anchors.verticalCenter: parent.verticalCenter
                    scale: (subTabDock.view.currentSubTab === 3 || tabMouse3.containsMouse) ? 1.15 : 1.0
                    Behavior on scale {
                        SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.7; epsilon: 0.01 }
                    }
                }

                Text {
                    text: subTabDock.isCompact ? subTabDock.view.tr("tab_batch_short", "Batch") : subTabDock.view.tr("tab_batch_import", "Batch Importer")
                    font.family: "Segoe UI, Inter, sans-serif"
                    font.pixelSize: subTabDock.isCompact ? 11 : 12
                    font.weight: subTabDock.view.currentSubTab === 3 ? 600 : Font.Medium
                    color: subTabDock.view.currentSubTab === 3 ? "#F8FAFC" : (tabMouse3.containsMouse ? "#CBD5E1" : "#94A3B8")
                    elide: Text.ElideRight
                    width: Math.min(implicitWidth, tabBtn3.width - (subTabDock.view.detectedBatchUrlCount > 0 ? 42 : 28))
                    anchors.verticalCenter: parent.verticalCenter
                    Behavior on color { ColorAnimation { duration: 150 } }
                }

                // Batch URL count mini-pill
                Rectangle {
                    id: batchUrlBadge
                    visible: subTabDock.view.detectedBatchUrlCount > 0
                    width: visible ? 16 : 0
                    height: 16
                    radius: 8
                    color: "#065F46"
                    border.color: "#10B981"
                    border.width: 1
                    anchors.verticalCenter: parent.verticalCenter

                    scale: visible ? 1.0 : 0.0
                    Behavior on scale {
                        SpringAnimation { spring: 5.5; damping: 0.32; mass: 0.75; epsilon: 0.01 }
                    }

                    Text {
                        anchors.centerIn: parent
                        text: subTabDock.view.detectedBatchUrlCount.toString()
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 9
                        font.bold: true
                        color: "#ECFDF5"
                    }
                }
            }

            MouseArea {
                id: tabMouse3
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: subTabDock.view.currentSubTab = 3
            }
        }
    }
}
