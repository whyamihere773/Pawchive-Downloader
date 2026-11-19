import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

// Only the creator cards on screen are built: building one for every creator froze the
// window for seconds on big archives (#28)
SmoothListView {
    id: creatorsListView
    required property var view
    objectName: "archiveCreatorsList"
    anchors.fill: parent
    visible: !!creatorsListView.view.creatorsModel && creatorsListView.view.creatorsModel.count > 0
    spacing: 8
    cacheBuffer: 800
    currentIndex: -1
    highlightFollowsCurrentItem: false
    model: creatorsListView.view.creatorsModel

            delegate: Rectangle {
                id: creatorCard
                width: creatorsListView.width
                radius: 8
                clip: true

        property var creatorModel: modelData
        property bool isCollapsed: !(creatorsListView.view.expandedCreators && creatorsListView.view.expandedCreators[creatorModel.creator_name])
        property int postsShown: creatorsListView.view.postsPage
        property var myPosts: creatorsListView.view.loadedPosts[creatorModel.key] || []
        property bool postsReady: !!creatorsListView.view.loadedPosts[creatorModel.key]
        Connections {
            target: creatorsListView.view
            function onPostsArrived(key) {
                if (key !== creatorCard.creatorModel.key) return
                creatorCard.myPosts = creatorsListView.view.loadedPosts[key] || []
                creatorCard.postsReady = true
            }
        }
        onIsCollapsedChanged: {
            if (!isCollapsed) creatorsListView.view.requestPosts(creatorModel)
            else postsShown = creatorsListView.view.postsPage
        }
        Component.onCompleted: if (!isCollapsed && (!postsReady || creatorsListView.view._stalePosts[creatorModel.key])) creatorsListView.view.requestPosts(creatorModel)

        property int creatorMissingCount: (creatorModel && typeof creatorModel.missing_count === "number") ? creatorModel.missing_count : 0
        property int creatorTotalCount: creatorModel.total_files || 0
        property bool isCreatorSomeMissing: creatorMissingCount > 0 && creatorMissingCount < creatorTotalCount
        property bool isCreatorAllMissing: creatorTotalCount > 0 && creatorMissingCount >= creatorTotalCount

        color: isCreatorHovered.hovered
            ? (isCreatorAllMissing ? "#1C0D11" : (isCreatorSomeMissing ? "#1C140A" : "#161D2C"))
            : (isCreatorAllMissing ? "#14080B" : (isCreatorSomeMissing ? "#140E07" : "#121722"))
        border.color: isCreatorHovered.hovered
            ? (isCreatorAllMissing ? "#EF4444" : (isCreatorSomeMissing ? "#F59E0B" : "#2DD4BF"))
            : (isCreatorAllMissing ? "#991B1B" : (isCreatorSomeMissing ? "#B45309" : "#1E2738"))
        border.width: 1

        implicitHeight: creatorCardCol.implicitHeight + 16
        Behavior on implicitHeight {
            enabled: !creatorsListView.isScrolling
            SpringAnimation {
                spring: 3.4
                damping: 0.36
                mass: 1.05
                epsilon: 1.0
            }
        }

        transform: Translate {
            y: isCreatorHovered.hovered && !creatorsListView.isScrolling ? -2.0 : 0
            Behavior on y {
                enabled: !creatorsListView.isScrolling
                SpringAnimation { spring: 4.5; damping: 0.38; mass: 0.9; epsilon: 0.1 }
            }
        }

        HoverHandler { id: isCreatorHovered }

        Behavior on border.color { ColorAnimation { duration: 160 } }
        Behavior on color { ColorAnimation { duration: 160 } }

        // Left vertical accent status bar
        Rectangle {
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: 3
            color: creatorCard.isCreatorAllMissing ? "#EF4444" : (creatorCard.isCreatorSomeMissing ? "#F59E0B" : "#2DD4BF")
            Behavior on color { ColorAnimation { duration: 180 } }
        }

        ColumnLayout {
            id: creatorCardCol
            anchors.fill: parent
            anchors.margins: 10
            spacing: 8

            // Creator Header Row — wrapped in Rectangle so the
            // collapse-toggle MouseArea is NOT a direct Layout child
            // (avoids "anchors on item managed by layout" warnings)
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: creatorHdrRow.implicitHeight + 4
                color: "transparent"

                // Collapse-toggle sits behind the RowLayout content
                // but in front of the card background (z: 0 default)
                MouseArea {
                    anchors.fill: parent
                    anchors.rightMargin: 56   // keep clear of verify + delete btns
                    cursorShape: Qt.PointingHandCursor
                    z: 0
                    onClicked: {
                        var newMap = Object.assign({}, creatorsListView.view.expandedCreators)
                        if (newMap[creatorModel.creator_name]) {
                            delete newMap[creatorModel.creator_name]
                        } else {
                            newMap[creatorModel.creator_name] = true
                        }
                        creatorsListView.view.expandedCreators = newMap
                    }
                }

                RowLayout {
                    id: creatorHdrRow
                    anchors.fill: parent
                    spacing: 8

                    // Modern circular chevron button
                    Rectangle {
                        width: 22
                        height: 22
                        radius: 11
                        color: isCreatorHovered.hovered ? "#1E293B" : "#162032"
                        border.color: isCreatorHovered.hovered
                            ? (creatorCard.isCreatorAllMissing ? "#EF4444" : (creatorCard.isCreatorSomeMissing ? "#F59E0B" : "#2DD4BF"))
                            : "#243248"
                        border.width: 1
                        scale: isCreatorHovered.hovered ? 1.08 : 1.0
                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.75 } }
                        Behavior on border.color { ColorAnimation { duration: 140 } }
                        Behavior on color { ColorAnimation { duration: 140 } }

                        Text {
                            anchors.centerIn: parent
                            text: "▶"
                            font.pixelSize: 9
                            color: creatorCard.isCreatorAllMissing ? "#EF4444" : (creatorCard.isCreatorSomeMissing ? "#F59E0B" : "#2DD4BF")
                            rotation: creatorCard.isCollapsed ? 0 : 90
                            Behavior on rotation {
                                SpringAnimation { spring: 4.5; damping: 0.35; mass: 0.8 }
                            }
                        }
                    }

                    // Service Badge
                    Rectangle {
                        implicitHeight: 18
                        implicitWidth: creatorSvcTxt.implicitWidth + 10
                        radius: 4
                        color: {
                            var s = (creatorModel.service || "").toLowerCase()
                            if (s === "patreon") return "#2A1508"
                            if (s === "fanbox") return "#2A2008"
                            if (s === "fantia") return "#0D2818"
                            if (s === "boosty") return "#1E1030"
                            if (s === "discord") return "#141530"
                            return "#161B26"
                        }
                        border.color: {
                            var s = (creatorModel.service || "").toLowerCase()
                            if (s === "patreon") return "#F97316"
                            if (s === "fanbox") return "#F59E0B"
                            if (s === "fantia") return "#10B981"
                            if (s === "boosty") return "#8B5CF6"
                            if (s === "discord") return "#6366F1"
                            return "#334155"
                        }
                        border.width: 1
                        scale: isCreatorHovered.hovered ? 1.04 : 1.0
                        Behavior on scale { SpringAnimation { spring: 4.5; damping: 0.38; mass: 0.85 } }

                        Text {
                            id: creatorSvcTxt
                            anchors.centerIn: parent
                            text: (creatorModel.service || "").toUpperCase()
                            font.pixelSize: 9
                            font.bold: true
                            color: parent.border.color
                        }
                    }

                    // Creator Name
                    Text {
                        text: creatorModel.creator_name
                        font.family: "Segoe UI, Inter, sans-serif"
                        font.pixelSize: 13
                        font.weight: 600
                        color: "#F8FAFC"
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }

                    // Missing files status badge (Amber if partial, Crimson if all)
                    Rectangle {
                        implicitHeight: 20
                        implicitWidth: creatorMissingTxt.implicitWidth + 10
                        radius: 10
                        visible: creatorCard.creatorMissingCount > 0
                        color: creatorCard.isCreatorAllMissing ? "#3F1318" : "#3D2406"
                        border.color: creatorCard.isCreatorAllMissing ? "#EF4444" : "#F59E0B"
                        border.width: 1
                        scale: isCreatorHovered.hovered ? 1.04 : 1.0
                        Behavior on scale { SpringAnimation { spring: 4.5; damping: 0.38; mass: 0.85 } }

                        Text {
                            id: creatorMissingTxt
                            anchors.centerIn: parent
                            text: creatorCard.isCreatorAllMissing
                                ? ("⚠️ " + creatorsListView.view.tr("status_all_missing", "All missing"))
                                : ("⚠️ " + creatorCard.creatorMissingCount + " " + creatorsListView.view.tr("unit_missing", "missing"))
                            font.pixelSize: 9
                            font.bold: true
                            color: creatorCard.isCreatorAllMissing ? "#FCA5A5" : "#FCD34D"
                        }
                    }

                    // Post Count Badge
                    Rectangle {
                        implicitHeight: 20
                        implicitWidth: postCntTxt.implicitWidth + 10
                        radius: 10
                        color: "#161D2B"
                        border.color: "#25334D"
                        border.width: 1
                        visible: creatorsListView.view.width >= 480
                        scale: isCreatorHovered.hovered ? 1.04 : 1.0
                        Behavior on scale { SpringAnimation { spring: 4.5; damping: 0.38; mass: 0.85 } }

                        Text {
                            id: postCntTxt
                            anchors.centerIn: parent
                            text: creatorModel.post_count + " " + creatorsListView.view.tr("unit_posts", "posts")
                            font.pixelSize: 9
                            color: "#94A3B8"
                        }
                    }

                    // File Count Badge
                    Rectangle {
                        implicitHeight: 20
                        implicitWidth: fileCntTxt.implicitWidth + 10
                        radius: 10
                        color: "#0D2924"
                        border.color: "#14B8A6"
                        border.width: 1
                        scale: isCreatorHovered.hovered ? 1.04 : 1.0
                        Behavior on scale { SpringAnimation { spring: 4.5; damping: 0.38; mass: 0.85 } }

                        Text {
                            id: fileCntTxt
                            anchors.centerIn: parent
                            text: creatorModel.total_files + " " + creatorsListView.view.tr("unit_files", "files")
                            font.pixelSize: 9
                            font.bold: true
                            color: "#2DD4BF"
                        }
                    }

                    // Verify Integrity Action Button
                    Rectangle {
                        id: verifyCreatorBtn
                        implicitHeight: 22
                        implicitWidth: 22
                        radius: 4
                        z: 1
                        property bool isVerifying: {
                            var st = creatorsListView.view.creatorVerifyState(creatorModel.service, creatorModel.creator_id)
                            return st !== null && st.running
                        }
                        readonly property bool isCreatorLocked: creatorsListView.view.isCreatorBusy(creatorModel.service, creatorModel.creator_id)
                        opacity: isCreatorLocked && !isVerifying ? 0.35 : 1.0
                        color: verifyCreatorMouse.containsMouse && !isCreatorLocked ? "#0D2033" : "transparent"
                        border.color: verifyCreatorMouse.containsMouse && !isCreatorLocked ? "#38BDF8" : (isVerifying ? "#38BDF8" : "transparent")
                        border.width: 1
                        scale: verifyCreatorMouse.pressed ? 0.85 : (verifyCreatorMouse.containsMouse ? 1.18 : 1.0)
                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.32; mass: 0.7 } }
                        Behavior on color { ColorAnimation { duration: 120 } }
                        Behavior on border.color { ColorAnimation { duration: 120 } }

                        Text {
                            anchors.centerIn: parent
                            text: verifyCreatorBtn.isVerifying ? "⏳" : "🔍"
                            font.pixelSize: 10
                            opacity: verifyCreatorMouse.containsMouse ? 1.0 : (verifyCreatorBtn.isVerifying ? 0.9 : 0.6)
                            RotationAnimator on rotation {
                                running: verifyCreatorBtn.isVerifying
                                from: 0; to: 360
                                duration: 1400
                                loops: Animation.Infinite
                            }
                        }

                        MouseArea {
                            id: verifyCreatorMouse
                            anchors.fill: parent
                            cursorShape: verifyCreatorBtn.isCreatorLocked ? Qt.BusyCursor : Qt.PointingHandCursor
                            hoverEnabled: true
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 300
                            ToolTip.text: creatorsListView.view.tr("tip_verify_creator_archive", "Verify that all archived files still exist on disk")
                            onClicked: {
                                if (!verifyCreatorBtn.isVerifying && !verifyCreatorBtn.isCreatorLocked && creatorsListView.view.bridge) {
                                    creatorsListView.view.bridge.verifyCreatorArchiveIntegrity(
                                        creatorModel.service,
                                        creatorModel.creator_id,
                                        creatorModel.creator_name
                                    )
                                }
                            }
                        }
                    }

                    // Delete Creator Action Button (z: 1 so clicks reach it over the bg MouseArea)
                    Rectangle {
                        id: delCreatorBtn
                        implicitHeight: 22
                        implicitWidth: 22
                        radius: 4
                        z: 1
                        readonly property bool isCreatorLocked: creatorsListView.view.isCreatorBusy(creatorModel.service, creatorModel.creator_id)
                        opacity: isCreatorLocked ? 0.35 : 1.0
                        color: delCreatorMouse.containsMouse && !isCreatorLocked ? "#3A1212" : "transparent"
                        border.color: delCreatorMouse.containsMouse && !isCreatorLocked ? "#EF4444" : "transparent"
                        border.width: 1
                        scale: delCreatorMouse.pressed ? 0.85 : (delCreatorMouse.containsMouse ? 1.18 : 1.0)
                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.32; mass: 0.7 } }
                        Behavior on color { ColorAnimation { duration: 120 } }
                        Behavior on border.color { ColorAnimation { duration: 120 } }

                        Text {
                            anchors.centerIn: parent
                            text: "🗑️"
                            font.pixelSize: 10
                            opacity: delCreatorMouse.containsMouse ? 1.0 : 0.6
                        }

                        MouseArea {
                            id: delCreatorMouse
                            anchors.fill: parent
                            cursorShape: delCreatorBtn.isCreatorLocked ? Qt.BusyCursor : Qt.PointingHandCursor
                            hoverEnabled: true
                            ToolTip.visible: containsMouse
                            ToolTip.delay: 300
                            ToolTip.text: creatorsListView.view.tr("tip_delete_creator_archive", "Remove all archived files for this creator (allows re-download)")
                            onClicked: {
                                if (delCreatorBtn.isCreatorLocked) return
                                creatorsListView.view.openDeleteCreatorConfirm(creatorModel)
                            }
                        }
                    }
                } // RowLayout (creatorHdrRow)
            } // Rectangle (creator header wrapper)

            // Verification Status Banner (shown when verify has run or is running)
            Rectangle {
                id: verifyBanner
                Layout.fillWidth: true
                property var vst: creatorsListView.view.creatorVerifyState(creatorModel.service, creatorModel.creator_id)
                visible: vst !== null
                implicitHeight: visible ? verifyBannerContent.implicitHeight + 14 : 0
                radius: 6
                color: {
                    if (!vst || vst.running) return "#0B1620"
                    if (vst.missing > 0) return "#1A0E00"
                    return "#071811"
                }
                border.color: {
                    if (!vst || vst.running) return "#1E3A4A"
                    if (vst.missing > 0) return "#F59E0B"
                    return "#10B981"
                }
                border.width: 1

                Behavior on color { ColorAnimation { duration: 200 } }
                Behavior on border.color { ColorAnimation { duration: 200 } }

                ColumnLayout {
                    id: verifyBannerContent
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 6

                    // Progress bar (shown while running)
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 4
                        radius: 2
                        color: "#1E2D3A"
                        visible: verifyBanner.vst !== null && verifyBanner.vst.running

                        Rectangle {
                            width: {
                                var st = verifyBanner.vst
                                if (!st || st.total <= 0) return 0
                                return Math.max(4, parent.width * (st.current / st.total))
                            }
                            height: parent.height
                            radius: 2
                            color: "#38BDF8"
                            Behavior on width { NumberAnimation { duration: 80 } }
                        }
                    }

                    // Status row
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6

                        Text {
                            text: {
                                var st = verifyBanner.vst
                                if (!st) return ""
                                if (st.running) {
                                    var pct = st.total > 0 ? Math.round(st.current * 100 / st.total) : 0
                                    return "⏳ " + creatorsListView.view.tr("verify_running", "Verifying… %1%").replace("%1", pct)
                                }
                                if (st.missing > 0)
                                    return "⚠️ " + creatorsListView.view.tr("verify_missing", "%1 missing, %2 present").replace("%1", st.missing).replace("%2", st.present)
                                return "✅ " + creatorsListView.view.tr("verify_ok", "All %1 files present").replace("%1", st.present)
                            }
                            font.pixelSize: 10
                            font.family: "Segoe UI, sans-serif"
                            color: {
                                var st = verifyBanner.vst
                                if (!st || st.running) return "#38BDF8"
                                if (st.missing > 0) return "#F59E0B"
                                return "#10B981"
                            }
                            Layout.fillWidth: true
                            Behavior on color { ColorAnimation { duration: 200 } }
                        }

                        // "Clean up" button — shown only when missing > 0 and done
                        Rectangle {
                            visible: {
                                var st = verifyBanner.vst
                                return st !== null && st.done && st.missing > 0
                            }
                            implicitHeight: 20
                            implicitWidth: cleanupTxt.implicitWidth + 14
                            radius: 4
                            color: cleanupMouse.containsMouse ? "#2D1800" : "#1A1000"
                            border.color: cleanupMouse.containsMouse ? "#F59E0B" : "#7A4A00"
                            border.width: 1
                            Behavior on color { ColorAnimation { duration: 120 } }
                            Behavior on border.color { ColorAnimation { duration: 120 } }

                            Text {
                                id: cleanupTxt
                                anchors.centerIn: parent
                                text: creatorsListView.view.tr("btn_remove_missing", "Remove missing")
                                font.pixelSize: 9
                                color: cleanupMouse.containsMouse ? "#FCD34D" : "#F59E0B"
                                Behavior on color { ColorAnimation { duration: 120 } }
                            }

                            MouseArea {
                                id: cleanupMouse
                                anchors.fill: parent
                                cursorShape: creatorsListView.view.isCreatorBusy(creatorModel.service, creatorModel.creator_id) ? Qt.BusyCursor : Qt.PointingHandCursor
                                hoverEnabled: true
                                ToolTip.visible: containsMouse
                                ToolTip.delay: 300
                                ToolTip.text: creatorsListView.view.tr("tip_remove_missing", "Delete archive records for files no longer on disk")
                                onClicked: {
                                    if (creatorsListView.view.isCreatorBusy(creatorModel.service, creatorModel.creator_id)) return
                                    creatorsListView.view.openRemoveMissingConfirm(creatorModel)
                                }
                            }
                        }

                        // Dismiss button
                        Text {
                            text: "✕"
                            font.pixelSize: 9
                            color: dismissVerifyMouse.containsMouse ? "#94A3B8" : "#475569"
                            Behavior on color { ColorAnimation { duration: 100 } }
                            MouseArea {
                                id: dismissVerifyMouse
                                anchors.fill: parent
                                anchors.margins: -4
                                cursorShape: Qt.PointingHandCursor
                                hoverEnabled: true
                                onClicked: {
                                    var key = creatorsListView.view._verifyKey(creatorModel.service, creatorModel.creator_id)
                                    var newMap = Object.assign({}, creatorsListView.view.verificationState)
                                    delete newMap[key]
                                    creatorsListView.view.verificationState = newMap
                                }
                            }
                        }
                    }
                }
            }

            // Subtle horizontal divider when dropped down
            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: "#1E2738"
                visible: !creatorCard.isCollapsed
            }


            ArchiveCreatorPostsList {
                view: creatorsListView.view
                card: creatorCard
                creatorModel: creatorCard.creatorModel
                listScrolling: creatorsListView.isScrolling
            }
        }
    } // end creatorCard Rectangle
    } // end creatorsListView
