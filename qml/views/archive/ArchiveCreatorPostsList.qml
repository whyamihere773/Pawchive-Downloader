import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

// Dropped-down Posts Container with Left Connector Rail
Item {
    id: postsContainer
    required property var view
    required property var card
    required property var creatorModel
    required property bool listScrolling
    Layout.fillWidth: true
    visible: !postsContainer.card.isCollapsed
    implicitHeight: postsInnerCol.implicitHeight

    // Left vertical connector rail line
    Rectangle {
        anchors.left: parent.left
        anchors.leftMargin: 8
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 6
        width: 2
        radius: 1
        color: postsContainer.card.isCreatorAllMissing ? "#7F1D1D" : (postsContainer.card.isCreatorSomeMissing ? "#78350F" : "#1E293B")
    }

    ColumnLayout {
        id: postsInnerCol
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.leftMargin: 18
        spacing: 6

        Text {
            visible: !postsContainer.card.isCollapsed && !postsContainer.card.postsReady
            text: postsContainer.view.tr("archive_loading_posts", "Loading posts…")
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 11
            color: "#64748B"
            Layout.topMargin: 2
            Layout.bottomMargin: 2
        }

        Repeater {
            model: postsContainer.card.isCollapsed ? null : postsContainer.card.myPosts.slice(0, postsContainer.card.postsShown)

            delegate: Rectangle {
                id: postCard
                Layout.fillWidth: true
                property var postModel: modelData
                property string postKey: creatorModel.creator_name + "_" + postModel.post_id
                property bool isPostCollapsed: postsContainer.view.searchFilter.length === 0 && !(postsContainer.view.expandedPosts && postsContainer.view.expandedPosts[postKey])
                property int filesShown: postsContainer.view.filesPage

                property int missingCount: (postModel && typeof postModel.missing_count === "number") ? postModel.missing_count : 0
                property int totalFiles: (postModel && postModel.files) ? postModel.files.length : (postModel.file_count || 0)
                property bool isSomeMissing: missingCount > 0 && missingCount < totalFiles
                property bool isAllMissing: totalFiles > 0 && missingCount >= totalFiles
                property bool hasMissingFiles: missingCount > 0

                implicitHeight: postCol.implicitHeight + 12
                Behavior on implicitHeight {
                    enabled: !postsContainer.listScrolling
                    SpringAnimation {
                        spring: 3.8
                        damping: 0.36
                        mass: 0.95
                        epsilon: 1.0
                    }
                }

                clip: true
                radius: 6
                color: isPostHovered.hovered
                    ? (isAllMissing ? "#2B0E14" : (isSomeMissing ? "#261B09" : "#0F1420"))
                    : (isAllMissing ? "#1A070A" : (isSomeMissing ? "#1B1306" : "#0B0E16"))
                border.color: isPostHovered.hovered
                    ? (isAllMissing ? "#EF4444" : (isSomeMissing ? "#F59E0B" : "#38BDF8"))
                    : (isAllMissing ? "#DC2626" : (isSomeMissing ? "#D97706" : "#182030"))
                border.width: 1

                transform: Translate {
                    y: isPostHovered.hovered && !postsContainer.listScrolling ? -1.5 : 0
                    Behavior on y {
                        enabled: !postsContainer.listScrolling
                        SpringAnimation { spring: 4.8; damping: 0.38; mass: 0.85; epsilon: 0.1 }
                    }
                }

                HoverHandler { id: isPostHovered }

                Behavior on border.color { ColorAnimation { duration: 140 } }
                Behavior on color { ColorAnimation { duration: 140 } }

                ColumnLayout {
                    id: postCol
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 6

                    // Post Header — wrapped in Rectangle so the
                    // collapse-toggle MouseArea is NOT a Layout child
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: postHdrRow.implicitHeight + 4
                        color: "transparent"

                        // Collapse-toggle background MouseArea
                        MouseArea {
                            anchors.fill: parent
                            anchors.rightMargin: 24   // keep clear of delete btn
                            cursorShape: Qt.PointingHandCursor
                            z: 0
                            onClicked: {
                                var newMap = Object.assign({}, postsContainer.view.expandedPosts)
                                if (newMap[postKey]) {
                                    delete newMap[postKey]
                                } else {
                                    newMap[postKey] = true
                                }
                                postsContainer.view.expandedPosts = newMap
                            }
                        }

                        RowLayout {
                            id: postHdrRow
                            anchors.fill: parent
                            spacing: 6

                            // Sub-chevron
                            Text {
                                text: "▾"
                                font.pixelSize: 10
                                color: postCard.isAllMissing ? "#EF4444" : (postCard.isSomeMissing ? "#F59E0B" : "#38BDF8")
                                rotation: postCard.isPostCollapsed ? -90 : 0
                                scale: isPostHovered.hovered ? 1.15 : 1.0
                                Behavior on rotation {
                                    SpringAnimation { spring: 4.5; damping: 0.35; mass: 0.8 }
                                }
                                Behavior on scale {
                                    SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.75 }
                                }
                            }

                            // Post Title
                            Text {
                                text: postModel.post_title
                                font.family: "Segoe UI, sans-serif"
                                font.pixelSize: 11
                                font.weight: 600
                                color: postCard.isAllMissing ? "#FCA5A5" : (postCard.isSomeMissing ? "#FCD34D" : "#E2E8F0")
                                elide: Text.ElideRight
                                Layout.fillWidth: true
                            }

                            // Missing Files Warning Badge (Amber if partial, Crimson if all)
                            Rectangle {
                                implicitHeight: 16
                                implicitWidth: postMissingTxt.implicitWidth + 8
                                radius: 3
                                visible: postCard.hasMissingFiles
                                color: postCard.isAllMissing ? "#3F1318" : "#3D2406"
                                border.color: postCard.isAllMissing ? "#EF4444" : "#F59E0B"
                                border.width: 1
                                scale: isPostHovered.hovered ? 1.05 : 1.0
                                Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }

                                Text {
                                    id: postMissingTxt
                                    anchors.centerIn: parent
                                    text: postCard.isAllMissing
                                        ? ("⚠️ " + postsContainer.view.tr("status_all_x_missing", "All %1 missing").replace("%1", postCard.missingCount))
                                        : ("⚠️ " + postCard.missingCount + " / " + postCard.totalFiles + " " + postsContainer.view.tr("unit_missing", "missing"))
                                    font.pixelSize: 8
                                    font.weight: 600
                                    color: postCard.isAllMissing ? "#FCA5A5" : "#FCD34D"
                                }
                            }

                            // Post ID Badge
                            Rectangle {
                                implicitHeight: 16
                                implicitWidth: pidTxt.implicitWidth + 8
                                radius: 3
                                color: "#161D2B"
                                border.color: "#28354A"
                                border.width: 1
                                visible: postsContainer.view.width >= 520
                                scale: isPostHovered.hovered ? 1.05 : 1.0
                                Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.38; mass: 0.8 } }

                                Text {
                                    id: pidTxt
                                    anchors.centerIn: parent
                                    text: "#" + postModel.post_id
                                    font.pixelSize: 8
                                    color: "#64748B"
                                }
                            }

                            // Post File Count
                            Text {
                                text: postModel.file_count + " " + postsContainer.view.tr("unit_files", "files")
                                font.pixelSize: 9
                                color: "#94A3B8"
                            }

                            // Delete Post Action Button (z: 1 so it receives clicks over bg MouseArea)
                            Rectangle {
                                implicitHeight: 18
                                implicitWidth: 18
                                radius: 3
                                z: 1
                                color: delPostMouse.containsMouse ? "#3A1212" : "transparent"
                                border.color: delPostMouse.containsMouse ? "#EF4444" : "transparent"
                                border.width: 1
                                scale: delPostMouse.pressed ? 0.85 : (delPostMouse.containsMouse ? 1.18 : 1.0)
                                Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.32; mass: 0.7 } }
                                Behavior on color { ColorAnimation { duration: 120 } }
                                Behavior on border.color { ColorAnimation { duration: 120 } }

                                Text {
                                    anchors.centerIn: parent
                                    text: "🗑️"
                                    font.pixelSize: 9
                                    opacity: delPostMouse.containsMouse ? 1.0 : 0.5
                                }

                                MouseArea {
                                    id: delPostMouse
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    hoverEnabled: true
                                    ToolTip.visible: containsMouse
                                    ToolTip.delay: 300
                                    ToolTip.text: postsContainer.view.tr("tip_delete_post_archive", "Remove all files of this post from archive")
                                    onClicked: {
                                        postsContainer.view.openDeletePostConfirm(postModel)
                                    }
                                }
                            }
                        } // RowLayout (postHdrRow)
                    } // Rectangle (post header wrapper)

                    // Files Under This Post
                    ColumnLayout {
                        Layout.fillWidth: true
                        visible: !postCard.isPostCollapsed
                        spacing: 4
                        Layout.leftMargin: 14

                        Repeater {
                            model: (postsContainer.card.isCollapsed || postCard.isPostCollapsed) ? null : postModel.files.slice(0, postCard.filesShown)

                            delegate: Rectangle {
                                Layout.fillWidth: true
                                implicitHeight: 28
                                radius: 4
                                property var fileData: modelData
                                property bool isMissing: fileData.is_missing === 1
                                color: fileRowMouse.hovered
                                    ? (isMissing ? (postCard.isAllMissing ? "#2B1117" : "#261A09") : "#162030")
                                    : (isMissing ? (postCard.isAllMissing ? "#1A090D" : "#1B1306") : "#0E121A")
                                border.color: fileRowMouse.hovered
                                    ? (isMissing ? (postCard.isAllMissing ? "#EF4444" : "#F59E0B") : "#2B3C57")
                                    : (isMissing ? (postCard.isAllMissing ? "#7F1D1D" : "#B45309") : "#161B26")
                                border.width: 1

                                transform: Translate {
                                    x: fileRowMouse.hovered && !postsContainer.listScrolling ? 4.0 : 0
                                    Behavior on x {
                                        enabled: !postsContainer.listScrolling
                                        SpringAnimation { spring: 4.8; damping: 0.38; mass: 0.85; epsilon: 0.1 }
                                    }
                                }

                                Behavior on border.color { ColorAnimation { duration: 120 } }
                                Behavior on color { ColorAnimation { duration: 120 } }

                                HoverHandler { id: fileRowMouse }

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 8
                                    anchors.rightMargin: 8
                                    spacing: 8

                                    // File Extension Badge
                                    Rectangle {
                                        implicitHeight: 18
                                        implicitWidth: extTxt.implicitWidth + 8
                                        radius: 3
                                        color: {
                                            var e = (fileData.file_ext || "").toLowerCase()
                                            if (e === "link" || e === "url") return "#083344"
                                            if (e === "zip" || e === "rar" || e === "7z") return "#2A1F0D"
                                            if (e === "psd" || e === "clip") return "#0E2838"
                                            if (e === "png" || e === "jpg" || e === "webp") return "#0C2418"
                                            if (e === "mp4" || e === "mkv") return "#2E0E20"
                                            if (e === "mp3" || e === "wav") return "#220E2E"
                                            return "#1E2430"
                                        }
                                        border.color: {
                                            var e = (fileData.file_ext || "").toLowerCase()
                                            if (e === "link" || e === "url") return "#06B6D4"
                                            if (e === "zip" || e === "rar" || e === "7z") return "#F59E0B"
                                            if (e === "psd" || e === "clip") return "#38BDF8"
                                            if (e === "png" || e === "jpg" || e === "webp") return "#10B981"
                                            if (e === "mp4" || e === "mkv") return "#EC4899"
                                            if (e === "mp3" || e === "wav") return "#A855F7"
                                            return "#64748B"
                                        }
                                        border.width: 1
                                        scale: fileRowMouse.hovered ? 1.08 : 1.0
                                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.75 } }

                                        Text {
                                            id: extTxt
                                            anchors.centerIn: parent
                                            text: (fileData.file_ext || "").toUpperCase() === "LINK" ? "🔗 LINK" : (fileData.file_ext || "FILE")
                                            font.pixelSize: 8
                                            font.bold: true
                                            color: parent.border.color
                                        }
                                    }

                                    // Filename or Link URL
                                    Text {
                                        text: fileData.filename
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 11
                                        color: isMissing ? (postCard.isAllMissing ? "#FCA5A5" : "#FCD34D") : ((fileData.file_ext || "").toLowerCase() === "link" ? "#38BDF8" : "#E2E8F0")
                                        font.underline: (fileData.file_ext || "").toLowerCase() === "link" && fileRowMouse.hovered
                                        elide: Text.ElideRight
                                        Layout.fillWidth: true
                                    }

                                    // Quick Open button for external links
                                    Rectangle {
                                        visible: (fileData.file_ext || "").toLowerCase() === "link"
                                        implicitHeight: 18
                                        implicitWidth: openLinkRow.implicitWidth + 8
                                        radius: 3
                                        color: linkBtnMouse.containsMouse ? "#083344" : "#0A1926"
                                        border.color: linkBtnMouse.containsMouse ? "#22D3EE" : "#0E7490"
                                        border.width: 1
                                        scale: linkBtnMouse.pressed ? 0.92 : (linkBtnMouse.containsMouse ? 1.08 : 1.0)
                                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.75 } }
                                        Behavior on color { ColorAnimation { duration: 120 } }

                                        RowLayout {
                                            id: openLinkRow
                                            anchors.centerIn: parent
                                            spacing: 3

                                            Text {
                                                text: "↗"
                                                font.pixelSize: 9
                                                color: "#22D3EE"
                                            }
                                            Text {
                                                text: postsContainer.view.tr("btn_open", "Open")
                                                font.pixelSize: 8
                                                font.bold: true
                                                color: "#22D3EE"
                                            }
                                        }

                                        MouseArea {
                                            id: linkBtnMouse
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            hoverEnabled: true
                                            ToolTip.visible: containsMouse
                                            ToolTip.delay: 200
                                            ToolTip.text: postsContainer.view.tr("tip_open_external_link", "Open external link in browser")
                                            onClicked: {
                                                var raw = fileData.filename || ""
                                                var u = raw
                                                var m = raw.match(/https?:\/\/[^\s]+/)
                                                if (m) u = m[0]
                                                if (u.indexOf("http") === 0) {
                                                    Qt.openUrlExternally(u)
                                                }
                                            }
                                        }
                                    }

                                    // File Size (or "Link" for link records)
                                    Text {
                                        text: (fileData.file_ext || "").toLowerCase() === "link" ? "Link" : fileData.file_size_str
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 10
                                        color: (fileData.file_ext || "").toLowerCase() === "link" ? "#06B6D4" : "#64748B"
                                        visible: ((fileData.file_ext || "").toLowerCase() === "link" || fileData.file_size_str.length > 0) && postsContainer.view.width >= 420
                                    }

                                    // Hash preview with copy button — hidden when narrow
                                    Rectangle {
                                        visible: fileData.file_hash.length > 0 && postsContainer.view.width >= 560
                                        implicitHeight: 18
                                        implicitWidth: hashRow.implicitWidth + 8
                                        radius: 3
                                        color: hashHover.containsMouse ? "#1E293B" : "#121722"
                                        border.color: "#242E42"
                                        border.width: 1
                                        scale: hashHover.pressed ? 0.92 : (hashHover.containsMouse ? 1.06 : 1.0)
                                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.35; mass: 0.75 } }
                                        Behavior on color { ColorAnimation { duration: 120 } }

                                        RowLayout {
                                            id: hashRow
                                            anchors.centerIn: parent
                                            spacing: 4

                                            Text {
                                                text: "#" + fileData.file_hash.substring(0, 8) + "…"
                                                font.family: "Consolas, monospace"
                                                font.pixelSize: 9
                                                color: "#94A3B8"
                                            }

                                            Text {
                                                text: "📋"
                                                font.pixelSize: 8
                                                opacity: hashHover.containsMouse ? 1.0 : 0.5
                                            }
                                        }

                                        MouseArea {
                                            id: hashHover
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            hoverEnabled: true
                                            ToolTip.visible: containsMouse
                                            ToolTip.delay: 200
                                            ToolTip.text: postsContainer.view.tr("tip_copy_sha256", "SHA256: %1 (Click to copy)").replace("%1", fileData.file_hash)
                                            onClicked: {
                                                if (typeof appBridge !== "undefined" && appBridge) {
                                                    appBridge.copyToClipboard(fileData.file_hash)
                                                    postsContainer.view.showToast(postsContainer.view.tr("toast_hash_copied", "Hash copied to clipboard!"))
                                                }
                                            }
                                        }
                                    }

                                    // Download Date — hidden at narrow widths
                                    Text {
                                        text: fileData.downloaded_at_str
                                        font.family: "Segoe UI, sans-serif"
                                        font.pixelSize: 9
                                        color: "#475569"
                                        visible: postsContainer.view.width >= 500
                                    }

                                    // Missing Status Tag (Amber if partial, Crimson if all)
                                    Rectangle {
                                        visible: isMissing
                                        implicitHeight: 18
                                        implicitWidth: missingFileTxt.implicitWidth + 8
                                        radius: 3
                                        color: postCard.isAllMissing ? "#3F1318" : "#3D2406"
                                        border.color: postCard.isAllMissing ? "#EF4444" : "#F59E0B"
                                        border.width: 1

                                        Text {
                                            id: missingFileTxt
                                            anchors.centerIn: parent
                                            text: "⚠️ " + postsContainer.view.tr("status_missing", "Missing")
                                            font.pixelSize: 8
                                            font.bold: true
                                            color: postCard.isAllMissing ? "#FCA5A5" : "#FCD34D"
                                        }
                                    }

                                    // Delete single file button
                                    Rectangle {
                                        implicitHeight: 20
                                        implicitWidth: 20
                                        radius: 3
                                        color: delFileMouse.containsMouse ? "#3A1212" : "transparent"
                                        border.color: delFileMouse.containsMouse ? "#EF4444" : "transparent"
                                        border.width: 1
                                        scale: delFileMouse.pressed ? 0.85 : (delFileMouse.containsMouse ? 1.18 : 1.0)
                                        Behavior on scale { SpringAnimation { spring: 5.0; damping: 0.32; mass: 0.7 } }
                                        Behavior on color { ColorAnimation { duration: 120 } }
                                        Behavior on border.color { ColorAnimation { duration: 120 } }

                                        Text {
                                            anchors.centerIn: parent
                                            text: "🗑️"
                                            font.pixelSize: 9
                                            opacity: delFileMouse.containsMouse ? 1.0 : 0.4
                                        }

                                        MouseArea {
                                            id: delFileMouse
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            hoverEnabled: true
                                            ToolTip.visible: containsMouse
                                            ToolTip.delay: 300
                                            ToolTip.text: postsContainer.view.tr("tip_delete_file_archive", "Remove this file from archive (allows re-downloading)")
                                            onClicked: {
                                                if (postsContainer.view.bridge && !postsContainer.view.isCreatorBusy(creatorModel.service, creatorModel.creator_id)) {
                                                    var recId = fileData.id
                                                    postsContainer.view.archiveJob(function(id) { postsContainer.view.bridge.deleteArchiveRecordAsync(id, recId) }, function(ok) {
                                                        if (ok === true || (typeof ok === "number" && ok >= 0)) postsContainer.view.showToast(postsContainer.view.tr("toast_file_removed", "File removed from archive."))
                                                        else if (postsContainer.view.bridge.archiveLastError()) postsContainer.view.showToast(postsContainer.view.archiveErrorText())
                                                    }, {
                                                        label: postsContainer.view.tr("job_removing_record", "Removing record from archive..."),
                                                        creatorKey: postsContainer.view._creatorBusyKey(creatorModel.service, creatorModel.creator_id)
                                                    })
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                        // Long lists open a page at a time: building hundreds of cards at once froze the window (#28)
                        Text {
                            visible: postCard.totalFiles > postCard.filesShown
                            text: postsContainer.view.tr("archive_show_more_files", "Show %1 more files (%2 left)").replace("%1", Math.min(postsContainer.view.pageSize * 2, postCard.totalFiles - postCard.filesShown)).replace("%2", postCard.totalFiles - postCard.filesShown)
                            font.family: "Segoe UI, sans-serif"
                            font.pixelSize: 11
                            color: moreMouse_archive_show_more_files.containsMouse ? "#5EEAD4" : "#2DD4BF"
                            Layout.topMargin: 2
                            Layout.bottomMargin: 4
                            MouseArea {
                                id: moreMouse_archive_show_more_files
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: postCard.filesShown += postsContainer.view.pageSize * 2
                            }
                        }
                    }
                }
            }
        }
        // Long lists open a page at a time: building hundreds of cards at once froze the window (#28)
        Text {
            visible: postsContainer.card.myPosts.length > postsContainer.card.postsShown
            text: postsContainer.view.tr("archive_show_more_posts", "Show %1 more posts (%2 left)").replace("%1", Math.min(postsContainer.view.pageSize, postsContainer.card.myPosts.length - postsContainer.card.postsShown)).replace("%2", postsContainer.card.myPosts.length - postsContainer.card.postsShown)
            font.family: "Segoe UI, sans-serif"
            font.pixelSize: 11
            color: moreMouse_archive_show_more_posts.containsMouse ? "#5EEAD4" : "#2DD4BF"
            Layout.topMargin: 2
            Layout.bottomMargin: 4
            MouseArea {
                id: moreMouse_archive_show_more_posts
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: postsContainer.card.postsShown += postsContainer.view.pageSize
            }
        }
    }
}
