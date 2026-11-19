import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import "../../components"

// File/Folder dialogs and confirmation modals for ArchiveView.
Item {
    id: dialogsRoot
    required property var view
    anchors.fill: parent
    z: 200

    function openFingerprintDialog() { fingerprintFolderDialog.open() }
    function openImportDialog() { importFileDialog.open() }
    function openExportDialog() { exportFileDialog.open() }
    function openClearConfirm() { clearConfirmModal.isOpen = true }
    function openDeleteCreatorConfirm(creator) {
        dialogsRoot.view.deleteTargetCreator = creator
        deleteCreatorConfirmModal.isOpen = true
    }
    function openRemoveMissingConfirm(creator) {
        dialogsRoot.view.removeMissingTargetCreator = creator
        removeMissingConfirmModal.isOpen = true
    }
    function openDeletePostConfirm(post) {
        dialogsRoot.view.deleteTargetPost = post
        deletePostConfirmModal.isOpen = true
    }

    // ── Dialogs & Modals ───────────────────────────────────────────────
    // Fingerprint Videos Folder Dialog
    FolderDialog {
        id: fingerprintFolderDialog
        title: dialogsRoot.view.tr("dialog_fingerprint_videos", "Select Folder to Fingerprint Existing Videos")
        onAccepted: {
            var raw = selectedFolder.toString()
            var path = raw.replace(/^file:\/\/\/([A-Za-z]:)/i, "$1").replace(/^file:\/\//i, "")
            if (Qt.platform.os === "windows") path = path.replace(/^\/+/g, "")
            try { path = decodeURIComponent(path) } catch (e) {}
            if (path && dialogsRoot.view.bridge && dialogsRoot.view.bridge.fingerprintVideosAsync) {
                dialogsRoot.view.showToast(dialogsRoot.view.tr("toast_fingerprinting_videos", "Fingerprinting existing videos…"))
                dialogsRoot.view.archiveJob(function(id) { dialogsRoot.view.bridge.fingerprintVideosAsync(id, path, true) }, function(res) {
                    if (res && res.success) {
                        var msg = dialogsRoot.view.tr("toast_fingerprinted_result", "Indexed %1 new video(s) (%2 already in archive).")
                            .replace("%1", res.newly_indexed || 0)
                            .replace("%2", res.already_archived || 0)
                        dialogsRoot.view.showToast(msg)
                        dialogsRoot.view.scheduleReload()
                    } else if (res && res.errors && res.errors.length) {
                        dialogsRoot.view.showToast("Fingerprinting finished: " + res.errors[0])
                    } else {
                        dialogsRoot.view.showToast(dialogsRoot.view.archiveErrorText())
                    }
                }, { label: dialogsRoot.view.tr("job_fingerprinting_videos", "Fingerprinting videos..."), global: true })
            }
        }
    }

    // Import File Dialog
    FileDialog {
        id: importFileDialog
        title: dialogsRoot.view.tr("dialog_import_archive", "Import Download Archive File")
        nameFilters: ["Archive Backups (*.json *.db *.txt)", "Full Archive Backup (*.json)", "Archive Database (*.db)", "ID-Only List (*.txt)", "All Files (*.*)"]
        onAccepted: {
            if (dialogsRoot.view.bridge && selectedFile) {
                var path = selectedFile.toString()
                dialogsRoot.view.showToast(dialogsRoot.view.tr("toast_importing", "Importing into the archive…"))
                dialogsRoot.view.archiveJob(function(id) { dialogsRoot.view.bridge.importArchiveFileAsync(id, path) }, function(imported) {
                    if (imported < 0) dialogsRoot.view.showToast(dialogsRoot.view.archiveErrorText())
                    else dialogsRoot.view.showToast(dialogsRoot.view.tr("toast_imported_count", "Imported %1 records into archive.").replace("%1", imported || 0))
                }, { label: dialogsRoot.view.tr("job_importing_archive", "Importing archive file..."), global: true })
            }
        }
    }

    // Export File Dialog
    FileDialog {
        id: exportFileDialog
        title: dialogsRoot.view.tr("dialog_export_archive", "Export Download Archive")
        fileMode: FileDialog.SaveFile
        defaultSuffix: "json"
        nameFilters: ["Full Archive Backup (*.json)", "ID-Only List — no creator names (*.txt)"]
        onAccepted: {
            if (dialogsRoot.view.bridge && selectedFile) {
                var path = selectedFile.toString()
                var fmt = path.toLowerCase().endsWith(".txt") ? "txt" : "json"
                dialogsRoot.view._exportRequest = "archive-export-" + Date.now()
                dialogsRoot.view._startJob(dialogsRoot.view._exportRequest, dialogsRoot.view.tr("job_exporting_archive", "Exporting archive..."), "", false)
                dialogsRoot.view.bridge.exportArchiveFileAsync(dialogsRoot.view._exportRequest, path, fmt)
                dialogsRoot.view.showToast(dialogsRoot.view.tr("toast_exporting", "Exporting the archive…"))
            }
        }
    }

    // Clear All Confirmation Modal
    Rectangle {
        id: clearConfirmModal
        property bool isOpen: false
        anchors.fill: parent
        color: "#C0000000"
        visible: opacity > 0.001
        opacity: isOpen ? 1.0 : 0.0
        z: 200

        Behavior on opacity { NumberAnimation { duration: 180 } }

        MouseArea {
            anchors.fill: parent
            enabled: clearConfirmModal.isOpen
            hoverEnabled: true
            onClicked: clearConfirmModal.isOpen = false
            onWheel: function(w) { w.accepted = true }
        }

        Rectangle {
            anchors.centerIn: parent
            width: Math.min(parent.width - 40, 420)
            implicitHeight: clearCol.implicitHeight + 36
            radius: 10
            color: "#161B26"
            border.color: "#EF4444"
            border.width: 1

            MouseArea { anchors.fill: parent }

            scale: clearConfirmModal.isOpen ? 1.0 : 0.86
            Behavior on scale {
                SpringAnimation { spring: 4.2; damping: 0.38; mass: 0.85; epsilon: 0.01 }
            }

            transform: Translate {
                y: clearConfirmModal.isOpen ? 0 : 20
                Behavior on y {
                    SpringAnimation { spring: 4.2; damping: 0.38; mass: 0.85; epsilon: 0.01 }
                }
            }

            ColumnLayout {
                id: clearCol
                anchors.fill: parent
                anchors.margins: 18
                spacing: 12

                RowLayout {
                    spacing: 8
                    Text { text: "⚠️"; font.pixelSize: 20 }
                    Text {
                        text: dialogsRoot.view.tr("modal_clear_archive_title", "Clear Download Archive Database?")
                        font.family: "Segoe UI, sans-serif"
                        font.pixelSize: 14
                        font.bold: true
                        color: "#F8FAFC"
                    }
                }

                Text {
                    text: dialogsRoot.view.tr("modal_clear_archive_desc", "This will wipe all indexed records from the database. Downloaded files that were deleted from disk will become eligible for re-downloading on next scan.")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Item { Layout.fillWidth: true }

                    StyledButton {
                        text: dialogsRoot.view.tr("btn_cancel", "Cancel")
                        variant: "ghost"
                        onClicked: clearConfirmModal.isOpen = false
                    }

                    StyledButton {
                        text: dialogsRoot.view.tr("btn_confirm_clear", "Clear Everything")
                        iconText: "🗑️"
                        variant: "danger"
                        onClicked: {
                            clearConfirmModal.isOpen = false
                            if (dialogsRoot.view.bridge) {
                                dialogsRoot.view.archiveJob(function(id) { dialogsRoot.view.bridge.clearDownloadArchiveAsync(id) }, function(ok) {
                                    var cleared = (ok === true || (typeof ok === "number" && ok >= 0))
                                    dialogsRoot.view.showToast(cleared ? dialogsRoot.view.tr("toast_archive_cleared", "Download archive cleared.") : dialogsRoot.view.archiveErrorText())
                                }, { label: dialogsRoot.view.tr("job_clearing_archive", "Clearing download archive..."), global: true })
                            }
                        }
                    }
                }
            }
        }
    }

    // Delete Creator Confirmation Modal
    Rectangle {
        id: deleteCreatorConfirmModal
        property bool isOpen: false
        anchors.fill: parent
        color: "#C0000000"
        visible: opacity > 0.001
        opacity: isOpen ? 1.0 : 0.0
        z: 200

        Behavior on opacity { NumberAnimation { duration: 180 } }

        MouseArea {
            anchors.fill: parent
            enabled: deleteCreatorConfirmModal.isOpen
            hoverEnabled: true
            onClicked: deleteCreatorConfirmModal.isOpen = false
            onWheel: function(w) { w.accepted = true }
        }

        Rectangle {
            anchors.centerIn: parent
            width: Math.min(parent.width - 40, 420)
            implicitHeight: delCreatorCol.implicitHeight + 36
            radius: 10
            color: "#161B26"
            border.color: "#EF4444"
            border.width: 1

            MouseArea { anchors.fill: parent }

            scale: deleteCreatorConfirmModal.isOpen ? 1.0 : 0.86
            Behavior on scale {
                SpringAnimation { spring: 4.2; damping: 0.38; mass: 0.85; epsilon: 0.01 }
            }

            transform: Translate {
                y: deleteCreatorConfirmModal.isOpen ? 0 : 20
                Behavior on y {
                    SpringAnimation { spring: 4.2; damping: 0.38; mass: 0.85; epsilon: 0.01 }
                }
            }

            ColumnLayout {
                id: delCreatorCol
                anchors.fill: parent
                anchors.margins: 18
                spacing: 12

                Text {
                    text: dialogsRoot.view.tr("modal_delete_creator_title", "Remove Creator Records?")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 14
                    font.bold: true
                    color: "#F8FAFC"
                }

                Text {
                    text: dialogsRoot.view.deleteTargetCreator
                          ? dialogsRoot.view.tr("modal_delete_creator_desc", "Remove all %1 archived files for '%2'? Files deleted from disk will be re-downloaded next time.")
                            .replace("%1", dialogsRoot.view.deleteTargetCreator.total_files)
                            .replace("%2", dialogsRoot.view.deleteTargetCreator.creator_name)
                          : ""
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Item { Layout.fillWidth: true }

                    StyledButton {
                        text: dialogsRoot.view.tr("btn_cancel", "Cancel")
                        variant: "ghost"
                        onClicked: deleteCreatorConfirmModal.isOpen = false
                    }

                    StyledButton {
                        text: dialogsRoot.view.tr("btn_remove_creator", "Remove Creator")
                        variant: "danger"
                        onClicked: {
                            deleteCreatorConfirmModal.isOpen = false
                            if (dialogsRoot.view.bridge && dialogsRoot.view.deleteTargetCreator) {
                                var dc = dialogsRoot.view.deleteTargetCreator
                                dialogsRoot.view.archiveJob(function(id) { dialogsRoot.view.bridge.deleteArchiveCreatorAsync(id, dc.creator_id, dc.service) }, function(delCnt) {
                                    if (typeof delCnt !== "number" || delCnt < 0) dialogsRoot.view.showToast(dialogsRoot.view.archiveErrorText())
                                    else dialogsRoot.view.showToast(dialogsRoot.view.tr("toast_creator_removed", "Removed %1 files for creator.").replace("%1", delCnt))
                                }, {
                                    label: dialogsRoot.view.tr("job_removing_creator", "Removing %1 from archive...").replace("%1", dc.creator_name || dc.creator_id || "creator"),
                                    creatorKey: dialogsRoot.view._creatorBusyKey(dc.service, dc.creator_id)
                                })
                            }
                        }
                    }
                }
            }
        }
    }

    // Remove Missing Records Confirmation Modal
    Rectangle {
        id: removeMissingConfirmModal
        property bool isOpen: false
        anchors.fill: parent
        color: "#C0000000"
        visible: opacity > 0.001
        opacity: isOpen ? 1.0 : 0.0
        z: 201

        Behavior on opacity { NumberAnimation { duration: 180 } }

        MouseArea {
            anchors.fill: parent
            enabled: removeMissingConfirmModal.isOpen
            hoverEnabled: true
            onClicked: removeMissingConfirmModal.isOpen = false
            onWheel: function(w) { w.accepted = true }
        }

        Rectangle {
            anchors.centerIn: parent
            width: Math.min(parent.width - 40, 420)
            implicitHeight: removeMissingCol.implicitHeight + 36
            radius: 10
            color: "#161B26"
            border.color: "#F59E0B"
            border.width: 1

            MouseArea { anchors.fill: parent }

            scale: removeMissingConfirmModal.isOpen ? 1.0 : 0.86
            Behavior on scale {
                SpringAnimation { spring: 4.2; damping: 0.38; mass: 0.85; epsilon: 0.01 }
            }

            transform: Translate {
                y: removeMissingConfirmModal.isOpen ? 0 : 20
                Behavior on y {
                    SpringAnimation { spring: 4.2; damping: 0.38; mass: 0.85; epsilon: 0.01 }
                }
            }

            ColumnLayout {
                id: removeMissingCol
                anchors.fill: parent
                anchors.margins: 18
                spacing: 12

                Text {
                    text: dialogsRoot.view.tr("modal_remove_missing_title", "Remove Missing Records?")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 14
                    font.bold: true
                    color: "#F8FAFC"
                }

                Text {
                    text: {
                        if (!dialogsRoot.view.removeMissingTargetCreator) return ""
                        var st = dialogsRoot.view.creatorVerifyState(
                            dialogsRoot.view.removeMissingTargetCreator.service,
                            dialogsRoot.view.removeMissingTargetCreator.creator_id
                        )
                        var cnt = st ? st.missing : 0
                        return dialogsRoot.view.tr("modal_remove_missing_desc",
                            "Delete %1 archive record(s) for '%2' whose files are no longer on disk? This lets Pawchive re-download them next time."
                        ).replace("%1", cnt).replace("%2", dialogsRoot.view.removeMissingTargetCreator.creator_name)
                    }
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Item { Layout.fillWidth: true }

                    StyledButton {
                        text: dialogsRoot.view.tr("btn_cancel", "Cancel")
                        variant: "ghost"
                        onClicked: removeMissingConfirmModal.isOpen = false
                    }

                    StyledButton {
                        text: dialogsRoot.view.tr("btn_remove_missing_confirm", "Remove Records")
                        variant: "warning"
                        onClicked: {
                            removeMissingConfirmModal.isOpen = false
                            if (dialogsRoot.view.bridge && dialogsRoot.view.removeMissingTargetCreator) {
                                var rm = dialogsRoot.view.removeMissingTargetCreator
                                dialogsRoot.view.archiveJob(function(id) { dialogsRoot.view.bridge.removeMissingArchiveRecordsForCreatorAsync(id, rm.service, rm.creator_id) }, function(delCnt) {
                                    // Clear the verify state so the banner reflects fresh state
                                    var newMap = Object.assign({}, dialogsRoot.view.verificationState)
                                    delete newMap[dialogsRoot.view._verifyKey(rm.service, rm.creator_id)]
                                    dialogsRoot.view.verificationState = newMap
                                    if (typeof delCnt !== "number" || delCnt < 0) dialogsRoot.view.showToast(dialogsRoot.view.archiveErrorText())
                                    else dialogsRoot.view.showToast(dialogsRoot.view.tr("toast_missing_removed", "Removed %1 missing record(s).").replace("%1", delCnt))
                                }, {
                                    label: dialogsRoot.view.tr("job_removing_missing", "Removing missing records..."),
                                    creatorKey: dialogsRoot.view._creatorBusyKey(rm.service, rm.creator_id)
                                })
                            }
                        }
                    }
                }
            }
        }
    }

    // Delete Post Confirmation Modal
    Rectangle {
        id: deletePostConfirmModal
        property bool isOpen: false
        anchors.fill: parent
        color: "#C0000000"
        visible: opacity > 0.001
        opacity: isOpen ? 1.0 : 0.0
        z: 200

        Behavior on opacity { NumberAnimation { duration: 180 } }

        MouseArea {
            anchors.fill: parent
            enabled: deletePostConfirmModal.isOpen
            hoverEnabled: true
            onClicked: deletePostConfirmModal.isOpen = false
            onWheel: function(w) { w.accepted = true }
        }

        Rectangle {
            anchors.centerIn: parent
            width: Math.min(parent.width - 40, 420)
            implicitHeight: delPostCol.implicitHeight + 36
            radius: 10
            color: "#161B26"
            border.color: "#EF4444"
            border.width: 1

            MouseArea { anchors.fill: parent }

            scale: deletePostConfirmModal.isOpen ? 1.0 : 0.86
            Behavior on scale {
                SpringAnimation { spring: 4.2; damping: 0.38; mass: 0.85; epsilon: 0.01 }
            }

            transform: Translate {
                y: deletePostConfirmModal.isOpen ? 0 : 20
                Behavior on y {
                    SpringAnimation { spring: 4.2; damping: 0.38; mass: 0.85; epsilon: 0.01 }
                }
            }

            ColumnLayout {
                id: delPostCol
                anchors.fill: parent
                anchors.margins: 18
                spacing: 12

                Text {
                    text: dialogsRoot.view.tr("modal_delete_post_title", "Remove Post Records?")
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 14
                    font.bold: true
                    color: "#F8FAFC"
                }

                Text {
                    text: dialogsRoot.view.deleteTargetPost
                          ? dialogsRoot.view.tr("modal_delete_post_desc", "Remove all %1 files for post '%2' from archive?")
                            .replace("%1", dialogsRoot.view.deleteTargetPost.file_count)
                            .replace("%2", dialogsRoot.view.deleteTargetPost.post_title)
                          : ""
                    font.family: "Segoe UI, sans-serif"
                    font.pixelSize: 11
                    color: "#94A3B8"
                    wrapMode: Text.WordWrap
                    Layout.fillWidth: true
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Item { Layout.fillWidth: true }

                    StyledButton {
                        text: dialogsRoot.view.tr("btn_cancel", "Cancel")
                        variant: "ghost"
                        onClicked: deletePostConfirmModal.isOpen = false
                    }

                    StyledButton {
                        text: dialogsRoot.view.tr("btn_remove_post", "Remove Post")
                        variant: "danger"
                        onClicked: {
                            deletePostConfirmModal.isOpen = false
                            if (dialogsRoot.view.bridge && dialogsRoot.view.deleteTargetPost) {
                                var dp = dialogsRoot.view.deleteTargetPost
                                dialogsRoot.view.archiveJob(function(id) { dialogsRoot.view.bridge.deleteArchivePostAsync(id, dp.service, dp.post_id) }, function(delCnt) {
                                    if (typeof delCnt !== "number" || delCnt < 0) dialogsRoot.view.showToast(dialogsRoot.view.archiveErrorText())
                                    else dialogsRoot.view.showToast(dialogsRoot.view.tr("toast_post_removed", "Removed %1 files for post.").replace("%1", delCnt))
                                }, {
                                    label: dialogsRoot.view.tr("job_removing_post", "Removing post from archive..."),
                                    creatorKey: dialogsRoot.view._creatorBusyKey(dp.service, dp.service ? (dp.creator_id || "") : "")
                                })
                            }
                        }
                    }
                }
            }
        }
    }
}
