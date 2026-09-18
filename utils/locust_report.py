import csv
import os
from pathlib import Path
from config.log_config import logger

FAILURE_RATE_THRESHOLD = 0.05


def parse_locust_csv(csv_prefix: str) -> dict:
    summary = {
        "total": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "failures": [],
        "duration": "",
    }

    failure_csv = f"{csv_prefix}_failures.csv"
    stats_csv = f"{csv_prefix}_stats.csv"

    if os.path.exists(failure_csv):
        with open(failure_csv, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                summary["failures"].append({
                    "test_name": row.get("Name", "unknown"),
                    "error": (
                        f"方法={row.get('Method','?')} 响应码={row.get('Response Code','?')} "
                        f"次数={row.get('Occurrences','?')} "
                        f"均值={row.get('Average Response Time','?')}ms"
                    ),
                })
                summary["failed"] += int(row.get("Occurrences", 1))

    if os.path.exists(stats_csv):
        with open(stats_csv, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                num_fail = int(row.get("Failure Count", 0) or 0)
                num_req = int(row.get("Request Count", 0) or 0)
                summary["total"] += num_req
                summary["failed"] += num_fail
                summary["passed"] += (num_req - num_fail)

    return summary


def should_send_alert(summary: dict, threshold: float = FAILURE_RATE_THRESHOLD) -> bool:
    total = summary.get("total", 0)
    failed = summary.get("failed", 0)
    if total == 0:
        return False
    return (failed / total) > threshold


def filter_warmup(csv_prefix: str, warmup_seconds: int, report_dir: Path) -> Path | None:
    history_csv = f"{csv_prefix}_stats_history.csv"
    if not os.path.exists(history_csv):
        logger.warning(f"未找到 {history_csv}，无法进行预热剔除")
        return None

    filtered_path = report_dir / f"{Path(history_csv).stem}_steady.csv"

    steady_rows = []
    peak_qps = 0.0
    steady_qps_sum = 0.0
    steady_qps_count = 0
    steady_p95_sum = 0.0
    steady_p95_count = 0
    steady_total_req = 0
    steady_total_fail = 0

    with open(history_csv, newline="", encoding="utf-8") as src:
        reader = csv.DictReader(src)
        fieldnames = reader.fieldnames
        for row in reader:
            try:
                elapsed = float(row.get("Elapsed Time", 0))
            except (ValueError, TypeError):
                continue

            if elapsed < warmup_seconds:
                continue

            steady_rows.append(row)

            try:
                qps = float(row.get("Requests/s", 0) or 0)
            except (ValueError, TypeError):
                qps = 0.0
            peak_qps = max(peak_qps, qps)
            steady_qps_sum += qps
            steady_qps_count += 1

            try:
                p95 = float(row.get("95%", 0) or 0)
            except (ValueError, TypeError):
                p95 = 0.0
            if p95 > 0:
                steady_p95_sum += p95
                steady_p95_count += 1

            try:
                steady_total_req += int(row.get("Request Count", 0) or 0)
                steady_total_fail += int(row.get("Failure Count", 0) or 0)
            except (ValueError, TypeError):
                pass

    if not steady_rows:
        logger.warning("稳态期无数据，跳过预热剔除报告")
        return None

    with open(filtered_path, "w", newline="", encoding="utf-8") as dst:
        writer = csv.DictWriter(dst, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(steady_rows)

    avg_qps = steady_qps_sum / steady_qps_count if steady_qps_count else 0.0
    avg_p95 = steady_p95_sum / steady_p95_count if steady_p95_count else 0.0
    fail_rate = (steady_total_fail / steady_total_req * 100) if steady_total_req else 0.0

    summary_text = (
        f"稳态期指标（剔除前 {warmup_seconds} 秒预热数据）\n"
        f"{'=' * 40}\n"
        f"稳态样本点数:   {len(steady_rows)}\n"
        f"稳态总请求数:   {steady_total_req}\n"
        f"稳态失败率:     {fail_rate:.2f}%\n"
        f"稳态平均 QPS:   {avg_qps:.1f}\n"
        f"稳态峰值 QPS:   {peak_qps:.1f}\n"
        f"稳态平均 P95:   {avg_p95:.0f} ms\n"
        f"\n过滤后历史数据: {filtered_path}\n"
    )
    logger.info(summary_text)
    return filtered_path