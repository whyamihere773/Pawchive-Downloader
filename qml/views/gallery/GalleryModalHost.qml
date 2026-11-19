import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../components"

Item {
    id: modalHost
    required property var view
    anchors.fill: parent
    z: 9200

    property alias lightboxLoader: lightboxLoader
    property alias creatorUpdatesLoader: creatorUpdatesLoader
    property alias storageLoader: storageLoader
    property alias batchRenameLoader: batchRenameLoader
    property alias galleryCleanerLoader: galleryCleanerLoader
    property alias visualSorterLoader: visualSorterLoader
    property alias rootDiskSafetyLoader: rootDiskSafetyLoader
    property alias mediaCompressLoader: mediaCompressLoader
    property alias archiveViewerLoader: archiveViewerLoader
    property alias archiveModal: archiveModal

    readonly property bool anyModalOpen: modalHost.view.isModalOpen(lightboxLoader)
        || modalHost.view.isModalOpen(batchRenameLoader)
        || modalHost.view.isModalOpen(galleryCleanerLoader)
        || modalHost.view.isModalOpen(rootDiskSafetyLoader)
        || archiveModal.isOpen
        || modalHost.view.isModalOpen(archiveViewerLoader)
        || modalHost.view.isModalOpen(creatorUpdatesLoader)
        || modalHost.view.isModalOpen(storageLoader)
        || modalHost.view.isModalOpen(mediaCompressLoader)

    Loader {
        id: lightboxLoader
        anchors.fill: parent
        z: 9999
        active: false
        sourceComponent: Component {
            MediaLightboxModal {
                id: lightboxModal
                bridge: modalHost.view.bridge
                tools: modalHost.view.tools
                onItemDeleted: (path) => modalHost.view.refreshPreservingScroll()
            }
        }
    }

    Loader {
        id: creatorUpdatesLoader
        anchors.fill: parent
        z: 9400
        active: false
        sourceComponent: Component {
            CreatorUpdatesModal {
                id: creatorUpdatesModal
                updates: modalHost.view.updates
                onCreatorLinked: (info) => modalHost.view.creatorInfo = info
                onDownloadStarted: (folder, message) => modalHost.view.showToast(message, false)
            }
        }
    }

    Loader {
        id: storageLoader
        anchors.fill: parent
        z: 9400
        active: false
        sourceComponent: Component {
            StorageModal {
                id: storageModal
                tools: modalHost.view.tools
                onOpenFolder: (path) => modalHost.view.navigateTo(path)
                onShowFile: (path) => modalHost.view.revealInGallery(path)
            }
        }
    }

    Loader {
        id: batchRenameLoader
        anchors.fill: parent
        z: 9998
        active: false
        sourceComponent: Component {
            BatchRenameModal {
                id: batchRenameModal
                bridge: modalHost.view.bridge
                onRenamed: modalHost.view.navigateTo(modalHost.view.currentPath)
            }
        }
    }

    Loader {
        id: galleryCleanerLoader
        anchors.fill: parent
        z: 9998
        active: false
        sourceComponent: Component {
            GalleryCleanerModal {
                id: galleryCleanerModal
                bridge: modalHost.view.bridge
                onCleaned: modalHost.view.navigateTo(modalHost.view.currentPath)
                onOrganized: modalHost.view.navigateTo(modalHost.view.currentPath)
            }
        }
    }

    Loader {
        id: visualSorterLoader
        anchors.fill: parent
        z: 9998
        active: false
        sourceComponent: Component {
            VisualSorterModal {
                id: visualSorterModal
                bridge: modalHost.view.bridge
                onSortCommitted: (movedCount, msg) => {
                    modalHost.view.setVirtualBucketFilter("", [])
                    modalHost.view.showToast(msg || ("Sorted " + movedCount + " files into folders"), false, true)
                    modalHost.view.navigateTo(modalHost.view.currentPath)
                }
                onVirtualFilterRequested: (bucketName, paths) => {
                    modalHost.view.setVirtualBucketFilter(bucketName, paths)
                }
            }
        }
    }

    Loader {
        id: rootDiskSafetyLoader
        anchors.fill: parent
        z: 99999
        active: false
        sourceComponent: Component {
            RootDiskSafetyModal {
                id: rootDiskSafetyModal
            }
        }
    }

    Loader {
        id: mediaCompressLoader
        objectName: "mediaCompressLoader"
        anchors.fill: parent
        z: 9500
        active: false
        sourceComponent: Component {
            MediaCompressModal {
                bridge: modalHost.view.bridge
                onFinished: modalHost.view.refreshPreservingScroll()
                onBackgroundFinished: (headline, ok) => {
                    modalHost.view.showToast(headline, !ok)
                    // Elsewhere in the app: the global toast, which jumps back to the result when clicked
                    if (typeof appWindow !== "undefined" && appWindow.currentTab !== 7 && appWindow.showToast) {
                        appWindow.showToast((ok ? "✔ " : "⚠ ") + "Gallery: " + headline + " (click to view)", function() {
                            appWindow.currentTab = 7
                            if (mediaCompressLoader.item) mediaCompressLoader.item.reopen()
                        })
                    }
                }
            }
        }
    }

    Loader {
        id: archiveViewerLoader
        anchors.fill: parent
        z: 9200
        active: false
        // The archive viewer opens pictures and videos in the image viewer
        onLoaded: item.lightbox = modalHost.view.modal(lightboxLoader)
        sourceComponent: Component {
            ArchiveViewerModal {
                id: archiveViewer
                bridge: modalHost.view.bridge
                archiver: modalHost.view.archiver
                onExtractAllRequested: (item) => modalHost.view.extractItems([item], false)
            }
        }
    }

    GalleryArchiveModal {
        id: archiveModal
        bridge: modalHost.view.bridge
        archiver: modalHost.view.archiver
        onFinished: modalHost.view.refreshPreservingScroll()
        onBackgroundFinished: (headline, ok) => {
            modalHost.view.showToast(headline, !ok)
            // Elsewhere in the app: the global toast, which jumps back to the result when clicked
            if (typeof appWindow !== "undefined" && appWindow.currentTab !== 7 && appWindow.showToast) {
                appWindow.showToast((ok ? "✔ " : "⚠ ") + "Gallery: " + headline + " (click to view)", function() {
                    appWindow.currentTab = 7
                    archiveModal.reopen()
                })
            }
        }
    }
}
