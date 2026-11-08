"""Create/reuse GitHub incidents; daily reminders and recovery are deduplicated."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from update_health import request_json


def incident_action(existing, healthy, now):
    if healthy:
        return "resolve" if existing and existing["state"] == "open" else "none"
    if not existing or existing["state"] != "open":
        return "create"
    last = datetime.fromisoformat(existing["updated_at"].replace("Z", "+00:00"))
    return "remind" if now - last >= timedelta(hours=23) else "none"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=("deployment", "freshness"), required=True)
    parser.add_argument("--report", type=Path, default=Path(".cache-update-health.local/report.json"))
    args = parser.parse_args()
    token = os.environ["GH_TOKEN"]
    repo = os.environ["GITHUB_REPOSITORY"]
    api = f"https://api.github.com/repos/{repo}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}

    def get(path):
        return request_json(api + path, headers=headers)

    def write(path, body, method="POST"):
        request = urllib.request.Request(api + path, data=json.dumps(body).encode(),
                                         headers={**headers, "Content-Type": "application/json"}, method=method)
        # No automatic retries of non-idempotent writes.
        with urllib.request.urlopen(request, timeout=25) as response:
            return json.load(response)

    if args.kind == "deployment":
        healthy = os.environ.get("DEPLOY_CONCLUSION") == "success"
        run_id = os.environ["DEPLOY_RUN_ID"]
        url = f"https://github.com/{repo}/actions/runs/{run_id}"
        details = []
        for page in range(1, 11):
            jobs = get(f"/actions/runs/{run_id}/jobs?per_page=100&page={page}").get("jobs", [])
            for job in jobs:
                failed = [step["name"] for step in job.get("steps", []) if step.get("conclusion") in ("failure", "cancelled", "timed_out")]
                if failed or job.get("conclusion") in ("failure", "cancelled", "timed_out"):
                    details.append(f"- {job['name']}: {', '.join(failed) or job.get('conclusion')} ([日志]({job['html_url']}))")
            if len(jobs) < 100:
                break
        detail = "\n".join(details) or f"Workflow conclusion: {os.environ.get('DEPLOY_CONCLUSION', 'unknown')}"
    else:
        report = json.loads(args.report.read_text(encoding="utf-8")) if args.report.exists() else {"ok": False, "detail": "监控未生成检查报告，请查看运行日志。"}
        healthy, detail = report["ok"], report["detail"]
        url = f"https://github.com/{repo}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    marker = f"<!-- feng-update-incident:{args.kind} -->"
    # Scan open issues, including later pages; never touch user-authored issues.
    existing = None
    for page in range(1, 101):
        issues = get(f"/issues?state=open&per_page=100&page={page}")
        existing = next((issue for issue in issues if marker in (issue.get("body") or "")
                         and issue.get("user", {}).get("login") == "github-actions[bot]" and "pull_request" not in issue), None)
        if existing or len(issues) < 100:
            break
    action = incident_action(existing, healthy, datetime.now(timezone.utc))
    fingerprint = f"<!-- feng-update-detail:{hashlib.sha256(detail.encode()).hexdigest()} -->"
    if existing and not healthy and fingerprint not in (existing.get("body") or ""):
        action = "update"
    category = "自动更新/发布失败" if args.kind == "deployment" else "线上数据过期或不可验证"
    body = f"{marker}\n{fingerprint}\n\n{detail}\n\n[检查日志]({url})\n\n请订阅本 Issue 接收故障、每日提醒及恢复通知。通知邮件取决于个人 GitHub 设置。"
    if action == "create":
        issue = write("/issues", {"title": f"[更新告警] {category}", "body": body, "assignees": [repo.split('/')[0]]})
        print(f"Incident created: {issue['html_url']}")
    elif action in ("remind", "resolve", "update"):
        status = '已恢复，线上验证通过。' if healthy else '故障情况有变化，请核查。' if action == 'update' else '故障仍未恢复，请检查。'
        message = f"{status}\n\n{detail}\n\n[检查日志]({url})"
        write(f"/issues/{existing['number']}/comments", {"body": message})
        if action == "resolve":
            write(f"/issues/{existing['number']}", {"state": "closed", "state_reason": "completed"}, "PATCH")
        elif action == "update":
            previous = existing.get("body") or ""
            updated = re.sub(r'<!-- feng-update-detail:[a-f0-9]+ -->', fingerprint, previous)
            if updated == previous and fingerprint not in previous:
                updated += "\n" + fingerprint
            write(f"/issues/{existing['number']}", {"body": updated}, "PATCH")
        print(f"Incident {action}: {existing['html_url']}")
    else:
        print("No incident change needed")


if __name__ == "__main__":
    main()
