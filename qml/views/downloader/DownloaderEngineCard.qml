import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

CardSection {
    id: engineCard
    required property var view
    Layout.fillWidth: true
    title: engineCard.view.tr("card_concurrency_engine", "Concurrency & Threading Engine")
    iconText: "⚡"
    entranceOffsetY: engineCard.view.tabEntranceOffsetY * 1.25
    entranceOpacity: engineCard.view.tabEntranceOpacity

    ColumnLayout {
        width: parent.width
        spacing: 12

        // Worker threads row
        Flow {
            width: parent.width
            Layout.fillWidth: true
            spacing: 8

            Text {
                text: engineCard.view.tr("label_concurrent_workers", "Concurrent Workers:")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 12
                color: "#94A3B8"
                height: 32
                verticalAlignment: Text.AlignVCenter
            }

            RowLayout {
                height: 32
                spacing: 8
                opacity: (engineCard.view.bridge && engineCard.view.bridge.isTelegramUrl) ? 0.45 : ((engineCard.view.bridge && engineCard.view.bridge.adaptiveThreading) ? 0.38 : 1.0)
                Behavior on opacity { NumberAnimation { duration: 180 } }

                Slider {
                    id: threadSlider
                    from: 1
                    to: engineCard.view.bridge ? engineCard.view.bridge.maxCpuThreads : 24
                    stepSize: 1
                    value: (engineCard.view.bridge && engineCard.view.bridge.isTelegramUrl) ? 2 : (engineCard.view.bridge ? engineCard.view.bridge.threadsCount : 4)
                    implicitWidth: engineCard.view.width > 540 ? 160 : 110
                    implicitHeight: 32
                    enabled: (engineCard.view.bridge && engineCard.view.bridge.isTelegramUrl) ? false : (engineCard.view.bridge ? !engineCard.view.bridge.adaptiveThreading : true)
                    onMoved: if (engineCard.view.bridge && enabled) engineCard.view.bridge.threadsCount = Math.round(value)

                    background: Item {
                        x: threadSlider.leftPadding
                        y: threadSlider.topPadding + threadSlider.availableHeight / 2 - height / 2
                        width: threadSlider.availableWidth
                        implicitHeight: 6
                        height: 6

                        Rectangle {
                            width: parent.width; height: parent.height
                            radius: 3
                            color: "#101827"
                            border.color: "#1E2D42"
                            border.width: 1
                        }
                        Rectangle {
                            width: Math.max(6, threadSlider.visualPosition * parent.width)
                            height: parent.height
                            radius: 3
                            color: "#38BDF8"
                            opacity: threadSlider.enabled ? 1.0 : 0.35
                        }
                    }

                    handle: Item {
                        x: threadSlider.leftPadding + threadSlider.visualPosition * (threadSlider.availableWidth - width)
                        y: threadSlider.topPadding + threadSlider.availableHeight / 2 - height / 2
                        width: 28; height: 28

                        scale: threadSlider.pressed ? 1.25 : (threadSlider.hovered ? 1.12 : 1.0)
                        Behavior on scale { SpringAnimation { spring: 5.2; damping: 0.30; mass: 0.6; epsilon: 0.005 } }

                        Rectangle {
                            anchors.centerIn: parent
                            width: 28; height: 28; radius: 14
                            color: "transparent"
                            border.color: "#38BDF8"
                            border.width: 1
                            opacity: (threadSlider.pressed || threadSlider.hovered) ? 0.5 : 0.0
                            Behavior on opacity { NumberAnimation { duration: 160 } }
                        }
                        Rectangle {
                            anchors.centerIn: parent
                            width: 16; height: 16; radius: 8
                            color: "#38BDF8"
                            opacity: threadSlider.enabled ? 1.0 : 0.3
                        }
                    }
                }

                // Value chip with spring hover
                Rectangle {
                    implicitWidth: workerVal.implicitWidth + 18
                    height: 24; radius: 12
                    color: "#0C1828"
                    border.color: (engineCard.view.bridge && engineCard.view.bridge.isTelegramUrl) ? "#92400E"
                                  : ((engineCard.view.bridge && engineCard.view.bridge.threadsLocked) ? "#7F1D1D" : "#164E63")
                    border.width: 1

                    scale: workerChipMouse.containsMouse ? 1.08 : 1.0
                    Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.32; mass: 0.65; epsilon: 0.005 } }

                    Text {
                        id: workerVal
                        anchors.centerIn: parent
                        text: (engineCard.view.bridge && engineCard.view.bridge.isTelegramUrl) ? "2"
                              : (engineCard.view.bridge && engineCard.view.bridge.adaptiveThreading
                                 ? engineCard.view.bridge.threadsCount.toString()
                                 : Math.round(threadSlider.value).toString())
                        font.family: "Segoe UI, sans-serif"
                        font.bold: true
                        font.pixelSize: 11
                        color: (engineCard.view.bridge && engineCard.view.bridge.isTelegramUrl) ? "#FCD34D"
                               : ((engineCard.view.bridge && engineCard.view.bridge.threadsLocked) ? "#FCA5A5" : "#7DD3FA")
                    }

                    MouseArea {
                        id: workerChipMouse
                        anchors.fill: parent
                        hoverEnabled: true
                    }
                }
            }

            RowLayout {
                height: 32
                spacing: 8

                // Thread Lock Button with Newtonian Fluid squash-stretch and buoyant hover
                Rectangle {
                    id: lockBtn
                    height: 24
                    radius: 5
                    opacity: (engineCard.view.bridge && engineCard.view.bridge.isTelegramUrl) ? 0.35 : 1.0
                    Behavior on opacity { NumberAnimation { duration: 180 } }
                    implicitWidth: lockRow.implicitWidth + 16
                    color: (engineCard.view.bridge && engineCard.view.bridge.threadsLocked)
                           ? (lockMouse.containsMouse ? "#3A1A1C" : "#2D1517")
                           : (lockMouse.containsMouse ? "#1E293B" : "#161E2E")
                    border.color: (engineCard.view.bridge && engineCard.view.bridge.threadsLocked)
                                  ? (lockMouse.containsMouse ? "#F87171" : "#EF4444")
                                  : (lockMouse.containsMouse ? "#475569" : "#242A38")
                    border.width: 1

                    scale: lockMouse.pressed ? 0.94 : (lockMouse.containsMouse ? 1.04 : 1.0)
                    Behavior on scale { SpringAnimation { spring: 4.8; damping: 0.32; mass: 0.8; epsilon: 0.005 } }

                    transform: Translate {
                        y: lockMouse.containsMouse ? -1.5 : 0
                        Behavior on y { SpringAnimation { spring: 4.5; damping: 0.35; mass: 0.8; epsilon: 0.1 } }
                    }

                    RowLayout {
                        id: lockRow
                        anchors.centerIn: parent
                        spacing: 4

                        Text {
                            text: (engineCard.view.bridge && engineCard.view.bridge.threadsLocked) ? "🔒" : "🔓"
                            font.pixelSize: 11
                        }

                        Text {
                            text: (engineCard.view.bridge && engineCard.view.bridge.threadsLocked)
                                  ? engineCard.view.tr("btn_thread_locked", "Locked")
                                  : engineCard.view.tr("btn_thread_lock", "Lock")
                            font.family: "Segoe UI, sans-serif"
                            font.bold: true
                            font.pixelSize: 11
                            color: (engineCard.view.bridge && engineCard.view.bridge.threadsLocked) ? "#F87171" : "#94A3B8"
                        }
                    }

                    MouseArea {
                        id: lockMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: (engineCard.view.bridge && engineCard.view.bridge.isTelegramUrl) ? Qt.ArrowCursor : Qt.PointingHandCursor
                        onClicked: {
                            if (engineCard.view.bridge && !(engineCard.view.bridge.isTelegramUrl)) {
                                engineCard.view.bridge.threadsLocked = !engineCard.view.bridge.threadsLocked
                            }
                        }
                    }

                    ToolTip {
                        id: lockToolTip
                        visible: lockMouse.containsMouse
                        delay: 400
                        timeout: 5000
                        text: (engineCard.view.bridge && engineCard.view.bridge.isTelegramUrl)
                              ? engineCard.view.tr("tip_thread_tg_locked", "Telegram Lock: Concurrency is locked to 2 threads to prevent FloodWait bans and connection drops.")
                              : ((engineCard.view.bridge && engineCard.view.bridge.threadsLocked)
                                 ? (engineCard.view.tr("tip_thread_locked_active", "Thread Lock Active: Worker concurrency is locked. Adaptive scaling is disabled and HTTP 429 cooldown is 30s."))
                                 : (engineCard.view.tr("tip_thread_lock", "Lock Thread Sweetspot: Lock current concurrency. Disables adaptive scaling and prevents rate limits from altering your thread count.")))
                        contentItem: Text {
                            text: lockToolTip.text
                            font.family: "Segoe UI, Inter, sans-serif"
                            font.pixelSize: 11
                            color: "#F1F5F9"
                            wrapMode: Text.WordWrap
                        }
                        background: Rectangle {
                            color: "#141924"
                            border.color: (engineCard.view.bridge && engineCard.view.bridge.threadsLocked) ? "#EF4444" : "#38BDF8"
                            border.width: 1
                            radius: 6
                        }
                    }
                }

                // Adaptive Threading Toggle Button with Newtonian Fluid squash-stretch and buoyant hover
                Rectangle {
                    id: adaptiveBtn
                    height: 24
                    radius: 5
                    readonly property bool isTg: engineCard.view.bridge && engineCard.view.bridge.isTelegramUrl
                    readonly property bool isLocked: engineCard.view.bridge && engineCard.view.bridge.threadsLocked
                    readonly property bool isAdaptive: !isTg && !isLocked && (engineCard.view.bridge && engineCard.view.bridge.adaptiveThreading)
                    readonly property bool canToggle: !isTg && !isLocked

                    opacity: canToggle ? 1.0 : 0.38
                    Behavior on opacity { NumberAnimation { duration: 180 } }

                    implicitWidth: adaptiveRow.implicitWidth + 16
                    color: isAdaptive
                           ? (adaptiveMouse.containsMouse ? "#3A2908" : "#2A1D05")
                           : (adaptiveMouse.containsMouse ? "#1E293B" : "#161E2E")
                    border.color: isAdaptive
                                  ? (adaptiveMouse.containsMouse ? "#FCD34D" : "#F59E0B")
                                  : (adaptiveMouse.containsMouse ? "#475569" : "#242A38")
                    border.width: 1

                    scale: (canToggle && adaptiveMouse.pressed) ? 0.94 : ((canToggle && adaptiveMouse.containsMouse) ? 1.04 : 1.0)
                    Behavior on scale { SpringAnimation { spring: 4.8; damping: 0.32; mass: 0.8; epsilon: 0.005 } }

                    transform: Translate {
                        y: (adaptiveBtn.canToggle && adaptiveMouse.containsMouse) ? -1.5 : 0
                        Behavior on y { SpringAnimation { spring: 4.5; damping: 0.35; mass: 0.8; epsilon: 0.1 } }
                    }

                    RowLayout {
                        id: adaptiveRow
                        anchors.centerIn: parent
                        spacing: 5

                        Text {
                            text: "⚡"
                            font.pixelSize: 11
                            scale: adaptiveBtn.isAdaptive ? 1.15 : 1.0
                            Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.7; epsilon: 0.01 } }
                        }

                        Text {
                            text: engineCard.view.tr("opt_adaptive_threading", "Adaptive Threading")
                            font.family: "Segoe UI, sans-serif"
                            font.bold: true
                            font.pixelSize: 11
                            color: adaptiveBtn.isAdaptive ? "#FCD34D" : "#94A3B8"
                        }
                    }

                    MouseArea {
                        id: adaptiveMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: adaptiveBtn.canToggle ? Qt.PointingHandCursor : Qt.ArrowCursor
                        onClicked: {
                            if (engineCard.view.bridge && adaptiveBtn.canToggle) {
                                engineCard.view.bridge.adaptiveThreading = !engineCard.view.bridge.adaptiveThreading
                            }
                        }
                    }

                    ToolTip {
                        id: adaptiveToolTip
                        visible: adaptiveMouse.containsMouse
                        delay: 400
                        timeout: 5000
                        text: adaptiveBtn.isTg
                              ? engineCard.view.tr("opt_adaptive_telegram_tip", "Adaptive Threading is disabled for Telegram downloads (locked strictly to 2 threads to prevent account bans)")
                              : (adaptiveBtn.isLocked
                                 ? engineCard.view.tr("opt_adaptive_disabled_tip", "Adaptive Threading is disabled because Thread Lock is active")
                                 : engineCard.view.tr("opt_adaptive_threading_tip", "Automatically scale worker thread count based on network conditions and 429 rate limits"))
                        contentItem: Text {
                            text: adaptiveToolTip.text
                            font.family: "Segoe UI, Inter, sans-serif"
                            font.pixelSize: 11
                            color: "#F1F5F9"
                            wrapMode: Text.WordWrap
                        }
                        background: Rectangle {
                            color: "#141924"
                            border.color: adaptiveBtn.isAdaptive ? "#F59E0B" : "#38BDF8"
                            border.width: 1
                            radius: 6
                        }
                    }
                }

                // Telegram thread lock reason badge
                Rectangle {
                    id: tgLockBadge
                    visible: engineCard.view.bridge && engineCard.view.bridge.isTelegramUrl
                    height: 24; radius: 5
                    implicitWidth: tgLockRow.implicitWidth + 14
                    color: "#2E1A11"; border.color: "#F59E0B"; border.width: 1

                    scale: tgLockMouse.pressed ? 0.95 : (tgLockMouse.containsMouse ? 1.03 : 1.0)
                    transformOrigin: Item.Center
                    Behavior on scale { SpringAnimation { spring: 3.8; damping: 0.32; mass: 1.8 } }

                    transform: Translate {
                        y: tgLockMouse.containsMouse ? -2 : 0
                        Behavior on y { SpringAnimation { spring: 3.5; damping: 0.35; mass: 1.8 } }
                    }

                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: -3
                        radius: 8
                        color: "transparent"
                        border.color: "#F59E0B"
                        border.width: 1
                        opacity: 0.25

                        SequentialAnimation on opacity {
                            loops: Animation.Infinite
                            running: tgLockBadge.visible
                            NumberAnimation { to: 0.75; duration: 1500; easing.type: Easing.InOutSine }
                            NumberAnimation { to: 0.15; duration: 1500; easing.type: Easing.InOutSine }
                        }
                    }

                    RowLayout {
                        id: tgLockRow
                        anchors.centerIn: parent; spacing: 5
                        Text { text: "🔒"; font.pixelSize: 10 }
                        Text {
                            text: engineCard.view.tr("tg_threads_locked_reason", "Telegram: Locked to 2 threads (anti-ban)")
                            font.family: "Segoe UI, sans-serif"; font.pixelSize: 11; font.bold: true; color: "#FCD34D"
                        }
                    }

                    MouseArea {
                        id: tgLockMouse
                        anchors.fill: parent
                        hoverEnabled: true
                    }

                    ToolTip {
                        id: tgLockTooltip
                        visible: tgLockMouse.containsMouse
                        delay: 200
                        timeout: 8000
                        text: engineCard.view.tr("tg_threads_locked_tooltip", "Telegram limits simultaneous connections per account. Concurrency is locked to 2 worker threads to prevent FloodWait temporary bans and connection drops.")
                        contentItem: Text {
                            text: tgLockTooltip.text
                            font.family: "Segoe UI, Inter, sans-serif"
                            font.pixelSize: 11
                            color: "#F1F5F9"
                            wrapMode: Text.WordWrap
                        }
                        background: Rectangle {
                            color: "#141924"
                            border.color: "#F59E0B"
                            border.width: 1
                            radius: 6
                        }
                    }
                }

                // CPU detection chip
                Rectangle {
                    height: 22
                    radius: 4
                    color: "#161E2E"
                    border.color: "#1E293B"
                    border.width: 1
                    implicitWidth: cpuBadgeText.implicitWidth + 12

                    Text {
                        id: cpuBadgeText
                        anchors.centerIn: parent
                        text: (engineCard.view.bridge && engineCard.view.bridge.threadsLocked)
                              ? ("🔒 " + engineCard.view.tr("badge_locked", "Locked:") + " " + engineCard.view.bridge.threadsCount + "T")
                              : (engineCard.view.bridge && engineCard.view.bridge.adaptiveThreading
                                 ? engineCard.view.tr("badge_adaptive", "⚡ Adaptive")
                                 : (engineCard.view.bridge ? (engineCard.view.tr("badge_cpu_cores", "⚡ CPU Cores:") + " " + engineCard.view.bridge.maxCpuThreads) : engineCard.view.tr("badge_cpu_auto", "⚡ CPU Auto")))
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 10
                        color: (engineCard.view.bridge && engineCard.view.bridge.threadsLocked)
                               ? "#F87171"
                               : (engineCard.view.bridge && engineCard.view.bridge.adaptiveThreading ? "#FBBF24" : "#38BDF8")
                    }
                }
            }
        }

        // Thread Delay After Download
        Flow {
            width: parent.width
            Layout.fillWidth: true
            spacing: 8

            Text {
                text: engineCard.view.tr("label_thread_delay", "⏱️ Thread Delay After Download:")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 12
                color: "#94A3B8"
                height: 32
                verticalAlignment: Text.AlignVCenter
            }

            RowLayout {
                height: 32
                spacing: 8

                Slider {
                    id: delaySlider
                    from: 0.0
                    to: 10.0
                    stepSize: 0.5
                    value: engineCard.view.bridge ? engineCard.view.bridge.downloadDelay : 2.0
                    implicitWidth: engineCard.view.width > 540 ? 160 : 110
                    implicitHeight: 32
                    onMoved: if (engineCard.view.bridge) engineCard.view.bridge.downloadDelay = value

                    background: Item {
                        x: delaySlider.leftPadding
                        y: delaySlider.topPadding + delaySlider.availableHeight / 2 - height / 2
                        width: delaySlider.availableWidth
                        implicitHeight: 6
                        height: 6

                        Rectangle {
                            width: parent.width; height: parent.height
                            radius: 3
                            color: "#100D1E"
                            border.color: "#231A40"
                            border.width: 1
                        }
                        Rectangle {
                            width: Math.max(6, delaySlider.visualPosition * parent.width)
                            height: parent.height
                            radius: 3
                            color: "#A78BFA"
                        }
                    }

                    handle: Item {
                        x: delaySlider.leftPadding + delaySlider.visualPosition * (delaySlider.availableWidth - width)
                        y: delaySlider.topPadding + delaySlider.availableHeight / 2 - height / 2
                        width: 28; height: 28

                        scale: delaySlider.pressed ? 1.25 : (delaySlider.hovered ? 1.12 : 1.0)
                        Behavior on scale { SpringAnimation { spring: 5.2; damping: 0.30; mass: 0.6; epsilon: 0.005 } }

                        Rectangle {
                            anchors.centerIn: parent
                            width: 28; height: 28; radius: 14
                            color: "transparent"
                            border.color: "#A78BFA"
                            border.width: 1
                            opacity: (delaySlider.pressed || delaySlider.hovered) ? 0.5 : 0.0
                            Behavior on opacity { NumberAnimation { duration: 160 } }
                        }
                        Rectangle {
                            anchors.centerIn: parent
                            width: 16; height: 16; radius: 8
                            color: "#A78BFA"
                        }
                    }
                }

                // Value chip
                Rectangle {
                    implicitWidth: delayVal.implicitWidth + 18
                    height: 24; radius: 12
                    color: "#0D0A1E"
                    border.color: "#3B2A6B"
                    border.width: 1

                    scale: delayChipMouse.containsMouse ? 1.08 : 1.0
                    Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.32; mass: 0.65; epsilon: 0.005 } }

                    Text {
                        id: delayVal
                        anchors.centerIn: parent
                        text: (engineCard.view.bridge ? engineCard.view.bridge.downloadDelay.toFixed(1) : "2.0") + "s"
                        font.family: "Segoe UI, sans-serif"
                        font.bold: true
                        font.pixelSize: 11
                        color: "#C4B5FD"
                    }

                    MouseArea {
                        id: delayChipMouse
                        anchors.fill: parent
                        hoverEnabled: true
                    }
                }
            }

            Text {
                text: engineCard.view.tr("label_anti_429", "(anti-429 cooldown)")
                font.family: "Segoe UI, sans-serif"
                font.pixelSize: 11
                color: "#64748B"
                height: 32
                verticalAlignment: Text.AlignVCenter
            }
        }
    }
}
