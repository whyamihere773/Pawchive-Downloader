import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: tutorialRoot
    visible: opacity > 0
    anchors.fill: parent
    color: "#D90B0D12"
    z: 1150

    property bool isOpen: false
    property int currentSectionIndex: 0
    property string searchQuery: ""

    opacity: isOpen ? 1.0 : 0.0
    Behavior on opacity {
        NumberAnimation { duration: 220; easing.type: Easing.OutCubic }
    }

    MouseArea {
        anchors.fill: parent
        onClicked: {} // Prevent click-through
    }

    // Interactive Sections Data
    readonly property var sections: [
        {
            title: "Quick Start & Overview",
            icon: "🚀",
            summary: "Supported sites, interface tour, and rapid first download.",
            content: [
                {
                    heading: "Welcome to Pawchive Downloader",
                    body: "Pawchive Downloader is a high-speed, multi-threaded archival tool built specifically for artists and content platforms. It connects directly to APIs and mirror networks with built-in rate-limiting protection, character recognition, duplicate skipping, and automatic archive extraction.",
                    type: "intro"
                },
                {
                    heading: "Supported Platforms",
                    body: "• Kemono & Coomer (Patreon, Pixiv Fanbox, Fantia, Discord, Boosty, Gumroad, Afdian, DLsite, Subscribestar)\n• Bunkr albums and folders\n• nHentai galleries\n• Cloud Hosts: Mega.nz, Dropbox, Google Drive links embedded inside posts",
                    type: "info"
                },
                {
                    heading: "First Time Download Workflow",
                    body: "1. Paste a creator URL or post URL into the top search bar (e.g. https://kemono.su/patreon/user/123456).\n2. Choose page range or leave as 'All'.\n3. Click 'Scrape & Queue' or press Enter.\n4. Click 'Start Download' in the queue controls to begin.",
                    type: "tip"
                }
            ]
        },
        {
            title: "URL Input & Scraper Modes",
            icon: "📥",
            summary: "Creator scraping, single post mode, page ranges, and link harvesting.",
            content: [
                {
                    heading: "Creator URL vs Single Post URL",
                    body: "• Creator URLs (containing /user/): Scrapes entire artist archives across all posts. You can specify page ranges (e.g. 1..3) to only fetch recent content.\n• Single Post URLs (containing /post/): Immediately scrapes and queues only files and links from that specific post.\n• Direct File URLs: If you paste direct media or cloud URLs, the app detects them and queries the cloud link resolver.",
                    type: "info"
                },
                {
                    heading: "Page Range Picker",
                    body: "The page slider allows you to select which pages to scrape. Each page contains 50 posts. Page 1 is the most recent content. Setting 'All' scrapes the complete creator history.",
                    type: "tip"
                },
                {
                    heading: "Cloud Link Extractor Mode",
                    body: "Posts often have text content containing Mega.nz, Google Drive, or Bunkr links. The scraper automatically inspects post body text and embeds, extracting raw cloud links into the download queue or link export tab.",
                    type: "info"
                }
            ]
        },
        {
            title: "Filter Rules & Scopes",
            icon: "🔍",
            summary: "File types, content images, inclusion/exclusion words, and scopes.",
            content: [
                {
                    heading: "File Category Filters",
                    body: "• Images: .png, .jpg, .jpeg, .webp, .gif, .bmp, .psd, .clip\n• Videos: .mp4, .mkv, .webm, .mov, .avi, .m4v\n• Audio: .mp3, .wav, .flac, .ogg, .m4a\n• Archives: .zip, .rar, .7z, .tar, .gz\n• Text/Docs: .pdf, .txt, .epub, .doc, .docx",
                    type: "info"
                },
                {
                    heading: "Content Images Toggle",
                    body: "Content images are inline illustrations and previews embedded within the text body of posts (as opposed to attachments). Turning this ON ensures no embedded drawings are left behind.",
                    type: "tip"
                },
                {
                    heading: "Inclusion & Exclusion Keywords",
                    body: "• Keep Words: Only files matching any of these comma-separated keywords will be downloaded.\n• Skip Words: Files containing any of these keywords will be skipped.\n• Scope (Files vs Character): 'Files' matches against filenames. 'Both' matches against filenames, post titles, and character tags.",
                    type: "warning"
                }
            ]
        },
        {
            title: "Mega & Cloud Downloads",
            icon: "☁️",
            summary: "Using 'Links Only' filter, extracting Mega links, downloading vs exporting, and quota bypass.",
            content: [
                {
                    heading: "Step 1: Enable the 'Links Only' Filter",
                    body: "In the Downloader tab, under File Types, select the 'Links Only' radio filter. This instructs Pawchive Downloader to skip downloading standard image/video attachments and instead parse post descriptions, content bodies, and comments specifically for embedded cloud links.",
                    type: "tip"
                },
                {
                    heading: "Step 2: Scrape the Creator or Post",
                    body: "Paste the creator or post URL into the search bar and click 'Scrape & Queue'. The scraper automatically detects and extracts Mega URLs (both folder links like mega.nz/folder/... and single file links like mega.nz/file/...), Google Drive, Dropbox, Bunkr, and others into your Harvested Links repository.",
                    type: "info"
                },
                {
                    heading: "Step 3: Direct Download vs Link Export",
                    body: "• Option A (Download via App): Click 'Cloud Downloads' in the queue or navigation bar. The built-in cloud downloader natively queries the Mega API, resolves the folder hierarchy, and streams the decrypted AES-CTR files directly to your disk with multithreaded workers.\n• Option B (Export Links): Go to the Export/Links tab and click 'Export Harvested Links' to save a clean .txt file containing all raw Mega URLs, ready to paste directly into JDownloader, MegaSync, or aria2.",
                    type: "info"
                },
                {
                    heading: "Bypassing Mega Bandwidth Quotas (VPN & Proxy)",
                    body: "Mega limits free accounts to ~5 GB of transfer every 6 hours per IP address. When a quota limit is reached:\n• VPN Bypass: Switch your VPN server to a different city or country to obtain a new IP address, then resume your downloads.\n• Proxy Setting: Open Settings -> Network & Proxy, and input your HTTP or SOCKS5 proxy URL (e.g. socks5://127.0.0.1:1080). Pawchive will route chunk requests through the proxy, instantly bypassing the quota block.",
                    type: "warning"
                }
            ]
        },
        {
            title: "Character Learning & Folders",
            icon: "🏷️",
            summary: "Smart character folder organization, dictionary matching, and learning.",
            content: [
                {
                    heading: "Automatic Subfolder Sorting",
                    body: "When Character Organization is enabled, files are automatically sorted into folders named after the detected character (e.g., 'Creator [service] / Character Name / file.png').",
                    type: "info"
                },
                {
                    heading: "Known.txt Master Database",
                    body: "The app ships with a built-in master dictionary of over 100,000 anime, game, and comic characters. The tokenizer breaks down filenames and matches the most specific character name.",
                    type: "info"
                },
                {
                    heading: "Smart Character Learning System",
                    body: "If a character name appears repeatedly across post titles or tags, the app dynamically learns it and creates matching folders even if the character isn't yet in Known.txt.",
                    type: "tip"
                }
            ]
        },
        {
            title: "Queue, Concurrency & Rate-Limits",
            icon: "⚡",
            summary: "Worker threads, rate limit detection, and speed optimization.",
            content: [
                {
                    heading: "Worker Threads Slider",
                    body: "Adjusts parallel download concurrency (1 to 16 threads). 3–5 threads is generally the sweet spot for maximum throughput without triggering server throttles.",
                    type: "tip"
                },
                {
                    heading: "Adaptive Concurrency & 429 Protection",
                    body: "Kemono mirror servers enforce rate limits. If the server returns HTTP 429 (Too Many Requests), the app automatically throttles concurrency down to 2 threads and applies an exponential backoff before resuming smoothly.",
                    type: "warning"
                },
                {
                    heading: "Active Queue vs Completed Queue",
                    body: "Use the filter bar above the queue list to toggle between 'All', 'Downloading', 'Completed', and 'Failed' items. You can pause, cancel, or prioritize tasks on the fly.",
                    type: "info"
                }
            ]
        },
        {
            title: "Auto-Retry & Error Handling",
            icon: "🔄",
            summary: "The 5-retry limit, auto-retry toggle, and the Retry Modal.",
            content: [
                {
                    heading: "Auto-Retry Cap (Max 5 Retries)",
                    body: "To prevent infinite retry loops on broken URLs or missing files, auto-retry attempts a failed file at most 5 times. If it fails on the 5th attempt, it is marked as 'Stopped after 5 retries' and safely skipped so your queue can finish.",
                    type: "info"
                },
                {
                    heading: "Retry Modal (Manual Control)",
                    body: "All failed files are retained in the Retry Modal (accessible via the red Failed counter button). In this modal, you can inspect error codes, click 'Open Post' to see the source post, click 'Test Link', or select specific files to manually re-try.",
                    type: "tip"
                },
                {
                    heading: "Auto-Retry at End of Queue",
                    body: "When 'Auto-Retry' is toggled ON, the downloader automatically cycles through all failed files once the main queue reaches 0, retrying them up to their 5-attempt limit before concluding.",
                    type: "info"
                }
            ]
        },
        {
            title: "Watchlist & Auto-Checking",
            icon: "👁️",
            summary: "Tracking artists, startup checks, unread counters, and custom folders.",
            content: [
                {
                    heading: "Adding Creators to Watchlist",
                    body: "Click the Bookmark/Watchlist button next to any creator to add them to your watchlist. The app remembers their last download date and post offset.",
                    type: "info"
                },
                {
                    heading: "Auto-Check on Startup & Badges",
                    body: "Every artist with 'Auto-check on launch' enabled will be checked in the background when the app opens. Artists with new posts are sorted to the top with a vibrant notification highlight and an exact counter of new posts.",
                    type: "tip"
                },
                {
                    heading: "Custom Per-Creator Folders",
                    body: "You can assign each artist their own dedicated download directory using the folder icon next to their card. The decompressor and queue respect these paths automatically.",
                    type: "info"
                }
            ]
        },
        {
            title: "Bulk Decompressor",
            icon: "📦",
            summary: "7-Zip engine, recursive archive scanning, pre-flight disk checks.",
            content: [
                {
                    heading: "7-Zip High Performance Engine",
                    body: "Powered by 7za with multithreading support (-mmt). It automatically discovers 7za.exe in your project directory, system PATH, or default program installations.",
                    type: "info"
                },
                {
                    heading: "Recursive Scanning & Multi-Volume Detection",
                    body: "Scans all artist download folders recursively for .zip, .rar, .7z, .cbz, and .tar archives. Secondary parts of multi-volume archives (.part2.rar, .002) are intelligently filtered out so only part 1 is extracted.",
                    type: "tip"
                },
                {
                    heading: "Pre-Flight Disk Space Check",
                    body: "Before extracting, the engine calculates required uncompressed disk space per drive and alerts you if free disk space is insufficient, preventing frozen writes or corrupted drives.",
                    type: "warning"
                },
                {
                    heading: "Delete Archives After Extraction",
                    body: "When enabled, archives are safely deleted only if 7-Zip exits with code 0 (verified extraction). If an archive is corrupt or password-protected, the original file is preserved.",
                    type: "info"
                }
            ]
        },
        {
            title: "Post-Actions & Desktop Reports",
            icon: "🌙",
            summary: "Shutdown, Sleep, Hibernate triggers and the automatic Desktop summary report.",
            content: [
                {
                    heading: "What to Do After Completion",
                    body: "Choose an automated post-download action from the dropdown in the queue footer: 'Close App', 'Sleep', 'Hibernate', 'Shutdown', or 'Restart'.",
                    type: "info"
                },
                {
                    heading: "15-Second Safety Countdown",
                    body: "Before your computer shuts down or goes to sleep, a 15-second countdown modal appears on screen with a prominent 'Cancel' button so you can stop the action if you're still working.",
                    type: "tip"
                },
                {
                    heading: "Automatic Desktop Report (HTML & TXT)",
                    body: "Whenever a post-download action is active, the app compiles a comprehensive summary report and saves it directly to your Desktop. The report features completed creators, disk space usage, and full clickable links for any files that failed.",
                    type: "info"
                }
            ]
        },
        {
            title: "In-App Updater",
            icon: "🔄",
            summary: "Source vs compiled updates, GitHub commit tracking, and safe restarts.",
            content: [
                {
                    heading: "Smart Detection (main.py vs .exe)",
                    body: "The updater detects whether you are running from Python source or a compiled standalone .exe. For source runs, it tracks commits on the main branch so you receive updates on every push. For .exe runs, it checks GitHub Releases.",
                    type: "info"
                },
                {
                    heading: "Update Badge & Notifications",
                    body: "When a new update is found, a glowing '✨ Update' pill appears in the top navigation bar. Clicking it opens the Update dialog showing commit notes and download progress.",
                    type: "tip"
                },
                {
                    heading: "Safe Windows Hand-Off",
                    body: "Updating protects all your personal files: your watchlist, settings, and downloaded files are never overwritten. A detached helper script waits for the app to close, updates the files, and relaunches automatically.",
                    type: "info"
                }
            ]
        },
        {
            title: "Permanent Link Vault & Passwords",
            icon: "🗝️",
            summary: "Uncapped cloud link archiving, multilingual passwords, cross-post rescue, and Decompressor sync.",
            content: [
                {
                    heading: "Persistent Plain-Text Archive",
                    body: "The Link Vault permanently stores every cloud link (Mega, Google Drive, Dropbox, Pixeldrain, Bunkr, etc.) extracted across your download sessions in config/link_vault.json with automatic atomic backups. Links are grouped into an intuitive Creator > Posts > Links tree view.",
                    type: "intro"
                },
                {
                    heading: "Multilingual Password Resolver",
                    body: "Automatically identifies archive passwords across English, Japanese (パスワード), Chinese (密码), Russian (пароль), Korean (암호), French, and German using proximity-weighted distance scoring. Shows passwords right alongside each link with 1-click copy.",
                    type: "tip"
                },
                {
                    heading: "1-Hop Cross-Post & Comments Scraper",
                    body: "When artists post update announcements linking to other posts or hide passwords inside comments, the Link Vault follows cross-post links (1-hop) and parses creator comments to unearth all hidden download destinations and passwords.",
                    type: "info"
                },
                {
                    heading: "Auto-Feed to Bulk Decompressor",
                    body: "Click 'Sync Passwords to Decompressor' to automatically export all harvested passwords into the Decompressor's password list, enabling seamless zero-prompt archive extraction.",
                    type: "tip"
                },
                {
                    heading: "Live Health Prober & Dead Link Cleanup",
                    body: "Click 'Check Link Health' to non-blockingly probe links in parallel. Dead or taken-down links are flagged in red, and 'Clean Dead Links' lets you prune non-functional links with one click.",
                    type: "info"
                }
            ]
        },
        {
            title: "Multi-Drive Storage Pools",
            icon: "💽",
            summary: "Auto-spanning across backup hard drives to prevent 'No space left on device' crashes.",
            content: [
                {
                    heading: "Eliminating Disk-Full Failures",
                    body: "Large artist archives can easily overwhelm a single hard drive. Storage Pools monitor disk capacity before writing each file stream. When the primary drive drops below your safety margin (e.g. 10 GB), subsequent files automatically route to secondary drives.",
                    type: "intro"
                },
                {
                    heading: "Folder Hierarchy Preservation",
                    body: "When overflowing to a secondary drive, Pawchive replicates the identical folder hierarchy (e.g. 'E:/Kemono/Patreon/Artist/Post/file.mp4'). Your file organization remains completely consistent across all physical drives.",
                    type: "info"
                },
                {
                    heading: "Adding Secondary Storage Pools",
                    body: "Navigate to Settings -> Storage & File Processing -> Multi-Drive Overflow, enable the feature, and click 'Add Overflow Drive / Folder' to select additional hard drives or network shares.",
                    type: "tip"
                }
            ]
        },
        {
            title: "1-Click Browser Cookie Importer",
            icon: "🍪",
            summary: "Direct session extraction from Chrome, Edge, Brave, Opera, Firefox and real-time expiration monitoring.",
            content: [
                {
                    heading: "Zero DevTools Required (Firefox, Edge, Brave)",
                    body: "No need to open F12 Developer Tools or manually copy session cookies. Pawchive safely reads your installed browser's cookie database via Windows DPAPI and AES-256-GCM without locking open browser tabs.\n\nSimply go to Settings → Network & Authentication, select your browser (or leave on Auto-Detect), and click ⚡ Import from Browser. Firefox, Edge, and Opera GX are recommended for automatic import.",
                    type: "intro"
                },
                {
                    heading: "Real-Time Expiration Watchdog",
                    body: "The expiration badge tracks remaining session validity:\n🟢 Active · Session Verified — healthy, no action needed\n🟡 Expiring Soon (Xh left) — re-import soon\n🔴 Session Expired — re-import immediately\n\nThe badge updates every 60 seconds so you always know before a download fails mid-session.",
                    type: "info"
                },
                {
                    heading: "⚠️ Google Chrome 127+: Manual Cookie Extraction Required",
                    body: "Google Chrome 127 introduced App-Bound Encryption which prevents any external tool from reading Chrome's cookie database. If you use Chrome as your primary browser, you have two options:\n\n• Recommended: Log into kemono.su / coomer.su in Mozilla Firefox or Microsoft Edge and use the 1-Click importer from there.\n\n• Manual (any browser): Copy your session cookie string manually using DevTools (see next card for step-by-step instructions).",
                    type: "warning"
                },
                {
                    heading: "Manual Extraction — Chrome / Any Browser (Step by Step)",
                    body: "1. Open your browser and log into kemono.su or coomer.su.\n\n2. Press F12 to open Developer Tools (or right-click the page → Inspect).\n\n3. Click the Application tab at the top of DevTools (you may need to click ≫ to see it).\n\n4. In the left sidebar, expand Storage → Cookies → https://kemono.su (or coomer.su).\n\n5. Look for a cookie named 'session' — click it and copy the full Value from the bottom panel.\n\n6. In Pawchive, go to Settings → Network & Authentication → Session Cookie field.\n\n7. Type:  session=  and paste your value right after it. Example:\n   session=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...\n\n8. Optionally add cf_clearance the same way, separated by a semicolon:\n   session=ABC123; cf_clearance=XYZ789\n\n9. Click Save Settings. Your cookie is now active.",
                    type: "tip"
                },
                {
                    heading: "Where to Find Each Cookie",
                    body: "• kemono.su / coomer.su → Cookie name: 'session'\n• Patreon.com → Cookie name: 'session_id' (found at www.patreon.com)\n• Fanbox (fanbox.cc) → Cookie name: 'FANBOXSESSID'\n• Cloudflare bypass → Cookie name: 'cf_clearance' (same domain as the site you're accessing)\n\nYou only need the one cookie for whichever site you're downloading from. You do not need all of them.",
                    type: "info"
                }
            ]
        },
        {
            title: "Task Scheduler & Automation Hub",
            icon: "⏰",
            summary: "Automated Watchlist delta sync, scheduled creator backups, Night Owl windows, and locked thread limits.",
            content: [
                {
                    heading: "Hands-Free Archive Automation",
                    body: "Create recurring background tasks to poll your Watchlist for new posts every few hours or schedule regular creator backups at fixed daily times (e.g. 03:00 AM).",
                    type: "intro"
                },
                {
                    heading: "User-Locked Threads & Delay Mode",
                    body: "If you have carefully tuned your worker thread count and download delay for your connection, enable 'Lock Custom Threads & Delay'. This strictly prevents adaptive algorithms or background sweep tasks from altering your custom settings.",
                    type: "tip"
                },
                {
                    heading: "Night Owl Off-Peak Window",
                    body: "Configure an off-peak download window (e.g. 01:00 to 07:00). Scheduled tasks will queue and pause until the off-peak window opens, maximizing download speeds when ISP bandwidth is cheapest.",
                    type: "info"
                },
                {
                    heading: "Windows Sleep Prevention (Stay Awake)",
                    body: "Engages Windows kernel execution state flags (ES_SYSTEM_REQUIRED) while automated tasks are actively downloading, keeping your PC awake through overnight batches without changing Windows power settings.",
                    type: "tip"
                }
            ]
        },
        {
            title: "Complete Tooltip Reference",
            icon: "💡",
            summary: "Quick cheatsheet explaining every button, icon, and badge across the interface.",
            content: [
                {
                    heading: "Header Navigation Icons",
                    body: "• ❓ Tutorial: Opens this interactive guide.\n• ✨ Update: Indicates a newer version is available on GitHub.\n• ⚙️ Settings: Opens app settings (download directory, concurrency, proxy).\n• 📜 Console: Opens real-time activity and network log window.",
                    type: "info"
                },
                {
                    heading: "Queue & Filter Buttons",
                    body: "• Auto-Retry: Automatically restarts failed downloads at end of queue.\n• Manga Mode: Normalizes image filenames for clean sequential reading order.\n• Adaptive Concurrency: Automatically adjusts threads when server rate limits hit.\n• 📂 Folder Icon: Opens target download folder in Windows File Explorer.",
                    type: "tip"
                },
                {
                    heading: "Link Vault & Scheduler Controls",
                    body: "• 🗝️ Link Vault: Permanent archive of all harvested cloud links and extracted passwords.\n• ⏰ Scheduler: Automation hub for recurring Watchlist syncs and Night Owl tasks.\n• 🔒 Lock Threads: Protects custom thread count and network delays from auto-throttling.\n• 💽 Storage Pools: Replicates folder trees across secondary drives when disk space is low.\n• 🍪 Cookie Importer: 1-click browser session extractor with real-time expiration watchdog.",
                    type: "info"
                },
                {
                    heading: "Retry Modal Actions",
                    body: "• 🔗 Open Post: Opens the source post on Kemono/Coomer in your web browser.\n• 📥 Test Link: Tests or downloads the file directly in your browser.\n• 🔁 Tried Nx: Shows how many times the file has been retried.\n• 🛑 5/5 Max Retries: Indicates auto-retry has stopped trying this file.",
                    type: "info"
                }
            ]
        }
    ]

    // Main Modal Card
    Rectangle {
        id: dialogBox
        width: Math.min(tutorialRoot.width - 32, 980)
        height: Math.min(tutorialRoot.height - 32, 700)
        anchors.centerIn: parent
        radius: 12
        color: "#111622"
        border.color: "#28344E"
        border.width: 1
        clip: true

        scale: tutorialRoot.isOpen ? 1.0 : 0.92
        Behavior on scale {
            NumberAnimation { duration: 240; easing.type: Easing.OutBack }
        }

        ColumnLayout {
            anchors.fill: parent
            spacing: 0

            // ── Modal Header Bar ─────────────────────────────────────────────
            Rectangle {
                Layout.fillWidth: true
                height: 54
                color: "#161D2C"
                border.color: "#222B3D"
                border.width: 1

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 18
                    anchors.rightMargin: 18
                    spacing: 12

                    Text {
                        text: "📖"
                        font.pixelSize: 20
                    }

                    Column {
                        spacing: 1
                        Text {
                            text: "Pawchive Downloader — Complete Manual & Feature Guide"
                            font.family: "Segoe UI, Inter, sans-serif"
                            font.pixelSize: 15
                            font.weight: Font.Bold
                            color: "#F8FAFC"
                        }
                        Text {
                            text: "In-depth documentation, tooltip reference, and workflow tutorials"
                            font.pixelSize: 11
                            color: "#94A3B8"
                        }
                    }

                    Item { Layout.fillWidth: true }

                    // Close Button
                    Rectangle {
                        width: 28; height: 28; radius: 14
                        color: closeMouse.containsMouse ? "#334155" : "#1E293B"
                        Text { anchors.centerIn: parent; text: "×"; font.pixelSize: 18; color: "#94A3B8" }
                        MouseArea {
                            id: closeMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: tutorialRoot.isOpen = false
                        }
                    }
                }
            }

            // ── Main Content Area: Sidebar + Reading Pane ────────────────────
            RowLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 0

                // ── Left Sidebar Navigation ──────────────────────────────────
                Rectangle {
                    Layout.fillHeight: true
                    width: 260
                    color: "#0D111A"
                    border.color: "#1E2638"
                    border.width: 1

                    SmoothListView {
                        id: navListView
                        anchors.fill: parent
                        anchors.margins: 6
                        spacing: 4
                        clip: true
                        model: tutorialRoot.sections

                        delegate: Rectangle {
                            width: navListView.width - 4
                            height: 48
                            radius: 6
                            color: {
                                if (index === tutorialRoot.currentSectionIndex) return "#1E293B";
                                if (itemMouse.containsMouse) return "#141C2B";
                                return "transparent";
                            }
                            border.color: index === tutorialRoot.currentSectionIndex ? "#38BDF8" : "transparent"
                            border.width: 1

                            RowLayout {
                                anchors.fill: parent
                                anchors.margins: 8
                                spacing: 10

                                Text {
                                    text: modelData.icon
                                    font.pixelSize: 18
                                }

                                Column {
                                    Layout.fillWidth: true
                                    spacing: 2
                                    Text {
                                        text: modelData.title
                                        font.pixelSize: 12
                                        font.weight: index === tutorialRoot.currentSectionIndex ? Font.Bold : Font.Medium
                                        color: index === tutorialRoot.currentSectionIndex ? "#38BDF8" : "#E2E8F0"
                                        elide: Text.ElideRight
                                        width: parent.width
                                    }
                                    Text {
                                        text: modelData.summary
                                        font.pixelSize: 10
                                        color: "#64748B"
                                        elide: Text.ElideRight
                                        width: parent.width
                                    }
                                }
                            }

                            MouseArea {
                                id: itemMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: {
                                    tutorialRoot.currentSectionIndex = index;
                                    contentFlick.contentY = 0;
                                }
                            }
                        }
                    }
                }

                // ── Right Reading Pane ───────────────────────────────────────
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    color: "#111622"

                    SmoothFlickable {
                        id: contentFlick
                        anchors.fill: parent
                        anchors.margins: 20
                        contentWidth: width
                        contentHeight: contentCol.implicitHeight + 40
                        clip: true

                        ColumnLayout {
                            id: contentCol
                            width: parent.width
                            spacing: 16

                            // Section Title Banner
                            RowLayout {
                                Layout.fillWidth: true
                                spacing: 10

                                Text {
                                    text: tutorialRoot.sections[tutorialRoot.currentSectionIndex].icon
                                    font.pixelSize: 26
                                }

                                Column {
                                    Layout.fillWidth: true
                                    Text {
                                        text: tutorialRoot.sections[tutorialRoot.currentSectionIndex].title
                                        font.pixelSize: 20
                                        font.bold: true
                                        color: "#F8FAFC"
                                    }
                                    Text {
                                        text: tutorialRoot.sections[tutorialRoot.currentSectionIndex].summary
                                        font.pixelSize: 12
                                        color: "#94A3B8"
                                    }
                                }
                            }

                            Rectangle {
                                Layout.fillWidth: true
                                height: 1
                                color: "#1F293D"
                            }

                            // Content Cards Repeater
                            Repeater {
                                model: tutorialRoot.sections[tutorialRoot.currentSectionIndex].content

                                delegate: Rectangle {
                                    Layout.fillWidth: true
                                    implicitHeight: cardCol.implicitHeight + 24
                                    radius: 8
                                    color: {
                                        if (modelData.type === "tip") return "#064E3B18";
                                        if (modelData.type === "warning") return "#451A0318";
                                        return "#161D2C";
                                    }
                                    border.color: {
                                        if (modelData.type === "tip") return "#05966955";
                                        if (modelData.type === "warning") return "#D9770655";
                                        return "#222D42";
                                    }
                                    border.width: 1

                                    ColumnLayout {
                                        id: cardCol
                                        anchors.fill: parent
                                        anchors.margins: 14
                                        spacing: 8

                                        RowLayout {
                                            spacing: 8
                                            Text {
                                                text: {
                                                    if (modelData.type === "tip") return "💡 TIP";
                                                    if (modelData.type === "warning") return "⚠️ IMPORTANT";
                                                    if (modelData.type === "intro") return "📌 OVERVIEW";
                                                    return "ℹ️ DETAIL";
                                                }
                                                font.pixelSize: 10
                                                font.weight: Font.Bold
                                                color: {
                                                    if (modelData.type === "tip") return "#34D399";
                                                    if (modelData.type === "warning") return "#FBBF24";
                                                    return "#38BDF8";
                                                }
                                            }

                                            Text {
                                                text: "• " + modelData.heading
                                                font.pixelSize: 14
                                                font.weight: Font.Bold
                                                color: "#F1F5F9"
                                            }
                                        }

                                        Text {
                                            Layout.fillWidth: true
                                            text: modelData.body
                                            font.pixelSize: 12
                                            lineHeight: 1.4
                                            color: "#CBD5E1"
                                            wrapMode: Text.Wrap
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
