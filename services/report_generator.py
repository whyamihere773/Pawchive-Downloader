"""
Post-Download Completion Report Generator.
Generates beautiful HTML and plaintext summary reports on the user's Desktop
detailing completed creators, downloaded file counts, disk size usage,
and comprehensive links for any failed downloads.
"""

import os
import sys
import html
from datetime import datetime
from typing import List, Dict, Any, Optional

try:
    from core.downloader import DownloadTask
except ImportError:
    DownloadTask = Any

try:
    from services.update_service import get_local_version_info
except Exception:
    def get_local_version_info():
        return {"version": "unknown", "short_commit": ""}


def get_desktop_path() -> str:
    """Find the user's Desktop directory reliably across Windows, Linux (XDG), and macOS."""
    # 1. Try Windows Registry Shell Folders
    if sys.platform == "win32":
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
            )
            val, _ = winreg.QueryValueEx(key, "Desktop")
            winreg.CloseKey(key)
            expanded = os.path.expandvars(val)
            if os.path.exists(expanded):
                return expanded
        except Exception:
            pass

        # Check OneDrive Desktop
        userprofile = os.environ.get("USERPROFILE", os.path.expanduser("~"))
        onedrive_desktop = os.path.join(userprofile, "OneDrive", "Desktop")
        if os.path.exists(onedrive_desktop):
            return onedrive_desktop
    else:
        # Linux: try xdg-user-dir DESKTOP (handles localized Desktop names e.g. Schreibtisch, Bureau)
        try:
            import subprocess
            out = subprocess.check_output(["xdg-user-dir", "DESKTOP"], stderr=subprocess.DEVNULL, timeout=2).decode().strip()
            if out and os.path.isdir(out):
                return out
        except Exception:
            pass

    # Standard Desktop fallback
    home = os.path.expanduser("~")
    std_desktop = os.path.join(home, "Desktop")
    if os.path.isdir(std_desktop):
        return std_desktop

    # Fallback to home dir
    return home


def _format_size(num_bytes: int) -> str:
    """Format bytes into human-readable string."""
    if num_bytes <= 0:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:3.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"


def generate_completion_report(
    tasks: List[Any],
    action_name: str = "Completion",
    elapsed_seconds: float = 0.0,
    dest_dir: Optional[str] = None
) -> Dict[str, str]:
    """
    Build and save both HTML and TXT reports to the Desktop.
    Returns a dict with paths: {'html': path, 'txt': path}.
    """
    desktop = dest_dir or get_desktop_path()
    os.makedirs(desktop, exist_ok=True)

    # App version stamp
    ver_info = get_local_version_info()
    app_version = ver_info.get("version", "unknown")
    short_commit = ver_info.get("short_commit", "")
    version_display = app_version
    if short_commit and short_commit not in ("current", app_version):
        version_display = f"{app_version} ({short_commit})"

    timestamp_str = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    now_display = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Metrics calculation
    total_tasks = len(tasks)
    completed_tasks = [t for t in tasks if getattr(t, "status", "") == "completed"]
    failed_tasks = [t for t in tasks if getattr(t, "status", "") == "failed"]
    skipped_tasks = [t for t in tasks if getattr(t, "status", "") not in ("completed", "failed")]

    total_bytes = sum(getattr(t, "downloaded_bytes", 0) or getattr(t, "file_size", 0) for t in completed_tasks)

    # Group completed by creator
    creators_dict: Dict[str, Dict[str, Any]] = {}
    for t in completed_tasks:
        c_name = getattr(t, "creator_name", "") or "Unknown"
        service = getattr(t, "service", "") or "kemono"
        key = f"{c_name} [{service}]"
        if key not in creators_dict:
            creators_dict[key] = {
                "name": c_name,
                "service": service,
                "count": 0,
                "bytes": 0
            }
        creators_dict[key]["count"] += 1
        creators_dict[key]["bytes"] += (getattr(t, "downloaded_bytes", 0) or getattr(t, "file_size", 0))

    creators_list = sorted(creators_dict.values(), key=lambda x: x["bytes"], reverse=True)

    # Build TXT Report
    txt_filename = f"Kemono_Download_Report_{timestamp_str}.txt"
    txt_path = os.path.join(desktop, txt_filename)

    lines = []
    lines.append("=" * 70)
    lines.append("  PAWCHIVE / KEMONO DOWNLOAD COMPLETION REPORT")
    lines.append("=" * 70)
    lines.append(f"  Date & Time:    {now_display}")
    lines.append(f"  Pawchive Ver:   {version_display}")
    lines.append(f"  Post Action:    {action_name.upper()}")
    if elapsed_seconds > 0:
        mins, secs = divmod(int(elapsed_seconds), 60)
        hrs, mins = divmod(mins, 60)
        lines.append(f"  Duration:       {hrs:02d}h {mins:02d}m {secs:02d}s")
    lines.append(f"  Total Files:    {total_tasks}")
    lines.append(f"  Completed:      {len(completed_tasks)}")
    lines.append(f"  Failed:         {len(failed_tasks)}")
    lines.append(f"  Total Size:     {_format_size(total_bytes)}")
    lines.append("-" * 70)

    lines.append("\n[COMPLETED CREATORS]")
    if creators_list:
        for c in creators_list:
            lines.append(f"  * {c['name']} [{c['service']}]: {c['count']} file(s) ({_format_size(c['bytes'])})")
    else:
        lines.append("  (None)")

    if failed_tasks:
        lines.append("\n" + "!" * 70)
        lines.append(f"  [FAILED DOWNLOADS - {len(failed_tasks)} ITEM(S)]")
        lines.append("!" * 70)
        for idx, f in enumerate(failed_tasks, 1):
            fn = getattr(f, "filename", "unknown")
            creator = getattr(f, "creator_name", "")
            post_title = getattr(f, "post_title", "")
            post_id = getattr(f, "post_id", "")
            service = getattr(f, "service", "")
            post_url = getattr(f, "post_url", "")
            if not post_url and service and post_id:
                post_url = f"https://pawchive.pw/{service}/user/{creator}/post/{post_id}"
            file_url = getattr(f, "url", "")
            err = getattr(f, "error_msg", "") or "Download failed"
            retries = getattr(f, "retry_count", 0)

            lines.append(f"\n#{idx}: {fn}")
            lines.append(f"   Creator / Post: {creator} - {post_title}")
            if post_url:
                lines.append(f"   Post Link:      {post_url}")
            if file_url:
                lines.append(f"   File Link:      {file_url}")
            lines.append(f"   Error:          {err} (Retries: {retries})")
    else:
        lines.append("\n[STATUS: 100% SUCCESS - All downloads completed without errors]")

    lines.append("\n" + "=" * 70)
    lines.append("  End of Report")
    lines.append("=" * 70)

    try:
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    except Exception as e:
        txt_path = ""

    # Build Beautiful Dark-Theme HTML Report
    html_filename = f"Kemono_Download_Report_{timestamp_str}.html"
    html_path = os.path.join(desktop, html_filename)

    creators_rows_html = ""
    for c in creators_list:
        creators_rows_html += f"""
        <tr>
            <td style="font-weight: 600; color: #F8FAFC;">{html.escape(c['name'])}</td>
            <td><span class="badge badge-service">{html.escape(c['service'])}</span></td>
            <td style="text-align: right; color: #34D399; font-weight: bold;">{c['count']}</td>
            <td style="text-align: right; font-family: monospace; color: #94A3B8;">{_format_size(c['bytes'])}</td>
        </tr>
        """
    if not creators_rows_html:
        creators_rows_html = '<tr><td colspan="4" style="text-align:center; color: #64748B;">No completed creators</td></tr>'

    failed_cards_html = ""
    for idx, f in enumerate(failed_tasks, 1):
        fn = html.escape(getattr(f, "filename", "unknown"))
        creator = html.escape(getattr(f, "creator_name", "") or "Unknown")
        post_title = html.escape(getattr(f, "post_title", "") or "Untitled Post")
        post_id = getattr(f, "post_id", "")
        service = getattr(f, "service", "")
        post_url = getattr(f, "post_url", "")
        if not post_url and service and post_id:
            post_url = f"https://pawchive.pw/{service}/user/{getattr(f, 'creator_name', '')}/post/{post_id}"
        file_url = getattr(f, "url", "")
        err = html.escape(getattr(f, "error_msg", "") or "Download failed")
        retries = getattr(f, "retry_count", 0)

        post_link_tag = f'<a href="{html.escape(post_url)}" target="_blank" class="btn btn-primary">🔗 Open Post</a>' if post_url else ""
        file_link_tag = f'<a href="{html.escape(file_url)}" target="_blank" class="btn btn-secondary">📥 Direct Download Link</a>' if file_url else ""

        failed_cards_html += f"""
        <div class="fail-card">
            <div class="fail-header">
                <span class="fail-index">#{idx}</span>
                <span class="fail-filename">{fn}</span>
                <span class="badge badge-danger">{retries}/5 Retries</span>
            </div>
            <div class="fail-meta">
                <div class="meta-item"><strong>Creator:</strong> {creator}</div>
                <div class="meta-item"><strong>Post:</strong> {post_title}</div>
            </div>
            <div class="fail-error">⚠️ {err}</div>
            <div class="fail-links">
                {post_link_tag}
                {file_link_tag}
            </div>
        </div>
        """

    failed_section_html = ""
    if failed_tasks:
        failed_section_html = f"""
        <div class="section">
            <h2 class="section-title text-danger">⚠️ Failed Downloads ({len(failed_tasks)})</h2>
            <p class="subtitle">The following files failed to download after all retry attempts. Click the buttons below to open the post or download them directly.</p>
            <div class="fail-grid">
                {failed_cards_html}
            </div>
        </div>
        """
    else:
        failed_section_html = """
        <div class="section success-banner">
            <h2>✨ 100% Success!</h2>
            <p>All queue files finished without errors. No failures detected.</p>
        </div>
        """

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Download Completion Report - {timestamp_str}</title>
    <style>
        :root {{
            --bg: #0B0D12;
            --card-bg: #131722;
            --card-border: #232D42;
            --text-primary: #F8FAFC;
            --text-secondary: #94A3B8;
            --accent: #38BDF8;
            --success: #34D399;
            --danger: #EF4444;
            --warning: #F59E0B;
        }}
        body {{
            background-color: var(--bg);
            color: var(--text-primary);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            margin: 0;
            padding: 30px 20px;
            line-height: 1.5;
        }}
        .container {{
            max-width: 960px;
            margin: 0 auto;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--card-border);
            padding-bottom: 16px;
            margin-bottom: 24px;
        }}
        .title h1 {{
            margin: 0;
            font-size: 24px;
            color: var(--text-primary);
        }}
        .title p {{
            margin: 4px 0 0 0;
            color: var(--text-secondary);
            font-size: 13px;
        }}
        .action-tag {{
            background: #1E293B;
            border: 1px solid #334155;
            color: var(--accent);
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            margin-bottom: 28px;
        }}
        .stat-card {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 10px;
            padding: 16px;
            text-align: center;
        }}
        .stat-value {{
            font-size: 26px;
            font-weight: 800;
            color: var(--text-primary);
            margin-top: 4px;
        }}
        .stat-label {{
            font-size: 11px;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .section {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 24px;
        }}
        .section-title {{
            font-size: 18px;
            margin-top: 0;
            margin-bottom: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .text-danger {{ color: var(--danger); }}
        .subtitle {{
            color: var(--text-secondary);
            font-size: 13px;
            margin-top: -8px;
            margin-bottom: 16px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }}
        th {{
            text-align: left;
            padding: 10px;
            color: var(--text-secondary);
            border-bottom: 1px solid var(--card-border);
            font-weight: 600;
            font-size: 12px;
            text-transform: uppercase;
        }}
        td {{
            padding: 12px 10px;
            border-bottom: 1px solid #1A2234;
        }}
        .badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
        }}
        .badge-service {{
            background: #1E293B;
            color: #38BDF8;
            border: 1px solid #0284C7;
        }}
        .badge-danger {{
            background: #450A0A;
            color: #F87171;
            border: 1px solid #991B1B;
        }}
        .fail-grid {{
            display: flex;
            flex-direction: column;
            gap: 12px;
        }}
        .fail-card {{
            background: #181A24;
            border: 1px solid #3B181E;
            border-left: 4px solid var(--danger);
            border-radius: 6px;
            padding: 14px;
        }}
        .fail-header {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 6px;
        }}
        .fail-index {{
            color: var(--danger);
            font-weight: bold;
            font-size: 12px;
        }}
        .fail-filename {{
            font-weight: 600;
            font-size: 14px;
            color: #F1F5F9;
            flex: 1;
            word-break: break-all;
        }}
        .fail-meta {{
            font-size: 12px;
            color: var(--text-secondary);
            display: flex;
            gap: 18px;
            margin-bottom: 8px;
        }}
        .fail-error {{
            background: #2D1418;
            border: 1px solid #5A1E26;
            color: #FCA5A5;
            padding: 6px 10px;
            border-radius: 4px;
            font-size: 12px;
            font-family: monospace;
            margin-bottom: 10px;
        }}
        .fail-links {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }}
        .btn {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 12px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
            text-decoration: none;
            transition: all 0.15s;
        }}
        .btn-primary {{
            background: #0284C7;
            color: #FFFFFF;
        }}
        .btn-primary:hover {{ background: #0369A1; }}
        .btn-secondary {{
            background: #334155;
            color: #F8FAFC;
        }}
        .btn-secondary:hover {{ background: #475569; }}
        .success-banner {{
            text-align: center;
            border-color: #065F46;
            background: #064E3B22;
            padding: 30px;
        }}
        .success-banner h2 {{ color: var(--success); margin: 0 0 6px 0; }}
        .success-banner p {{ color: var(--text-secondary); margin: 0; }}
        .footer {{
            text-align: center;
            font-size: 12px;
            color: #64748B;
            margin-top: 30px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="title">
                <h1>Pawchive / Kemono Download Report</h1>
                <p>Generated on {now_display} &nbsp;·&nbsp; <span style="color:#38BDF8; font-family: monospace;">v{html.escape(version_display)}</span></p>
            </div>
            <div class="action-tag">Post Action: {html.escape(action_name)}</div>
        </div>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Total Files</div>
                <div class="stat-value">{total_tasks}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Completed</div>
                <div class="stat-value" style="color: var(--success);">{len(completed_tasks)}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Failed</div>
                <div class="stat-value" style="color: {'var(--danger)' if failed_tasks else 'var(--text-secondary)'};">{len(failed_tasks)}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Total Written</div>
                <div class="stat-value" style="color: var(--accent);">{_format_size(total_bytes)}</div>
            </div>
        </div>

        <div class="section">
            <h2 class="section-title">📂 Completed Creators ({len(creators_list)})</h2>
            <table>
                <thead>
                    <tr>
                        <th>Creator</th>
                        <th>Platform</th>
                        <th style="text-align: right;">Files</th>
                        <th style="text-align: right;">Total Size</th>
                    </tr>
                </thead>
                <tbody>
                    {creators_rows_html}
                </tbody>
            </table>
        </div>

        {failed_section_html}

        <div class="footer">
            Pawchive Downloader • Report saved to Desktop
        </div>
    </div>
</body>
</html>"""

    try:
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
    except Exception as e:
        html_path = ""

    return {
        "html": html_path,
        "txt": txt_path
    }
