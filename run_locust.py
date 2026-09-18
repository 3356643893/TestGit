import os
import sys
import shutil
import subprocess
import argparse
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from config.log_config import logger
from utils.email_sender import send_alert_email, _build_html_report, parse_test_summary
from utils.locust_report import (
    parse_locust_csv,
    filter_warmup,
    should_send_alert,
    FAILURE_RATE_THRESHOLD,
)

LOCUSTFILE_DIR_NAME = "locustfiles"
LOCUSTFILES: dict[str, str] = {}

DEFAULT_USERS = 50
DEFAULT_SPAWN_RATE = 5
DEFAULT_RUN_TIME = "1m"
DEFAULT_LOCUSTFILE = ""
WEB_HOST = "127.0.0.1"
WEB_PORT = 8089
DEFAULT_WARMUP_SECONDS = 0


def _resolve_locustfile(base_dir: Path, name: str) -> Path:
    """根据 locustfile 名或路径定位绝对路径"""
    if name in LOCUSTFILES:
        return base_dir / "testcases" / "test_performance" / LOCUSTFILE_DIR_NAME / LOCUSTFILES[name]
    candidate = Path(name)
    if not candidate.is_absolute():
        candidate = base_dir / "testcases" / "test_performance" / LOCUSTFILE_DIR_NAME / name
    if candidate.exists():
        return candidate
    logger.error(f"找不到 locustfile: {name}")
    logger.error(f"请确认文件存在于 testcases/test_performance/{LOCUSTFILE_DIR_NAME}/ 目录下")
    sys.exit(1)


def _find_locust_bin() -> str:
    locust_bin = shutil.which("locust")
    if locust_bin:
        return locust_bin
    if sys.executable:
        return sys.executable
    logger.error("找不到 locust 可执行文件，且找不到 python，请先 pip install locust")
    sys.exit(1)


def _build_cmd(locust_bin: str, locustfile_abs: str, locust_args: list) -> list:
    """拼接 locust 命令行参数列表（bin, -f locustfile, 其他 args）"""
    return [locust_bin, "-f", locustfile_abs, *locust_args]


def _run_web(locustfile_abs: str, locustfile_dir: str, auto_open: bool):
    """启动 Locust Web UI 模式（交互式，自动打开浏览器）"""
    cmd = _build_cmd(_find_locust_bin(), locustfile_abs,
                     ["--web-host", WEB_HOST, "--web-port", str(WEB_PORT)])

    logger.info("=" * 50)
    logger.info("Locust Web UI 模式")
    logger.info("=" * 50)
    logger.info(f"Locust 文件: {locustfile_abs}")
    logger.info(f"Web 地址:    http://{WEB_HOST}:{WEB_PORT}")
    logger.info("在浏览器中填写并发用户数 / 产卵率 / 运行时长后，点击 Start")
    logger.info("按 Ctrl+C 停止 Locust 进程")
    logger.info("-" * 50)

    if auto_open:
        time.sleep(2)
        webbrowser.open(f"http://{WEB_HOST}:{WEB_PORT}")

    env = os.environ.copy()
    try:
        subprocess.run(cmd, cwd=locustfile_dir, env=env)
    except KeyboardInterrupt:
        logger.info("收到 Ctrl+C，Locust 已停止")
    logger.info("Locust Web UI 模式结束")


def _run_headless(locustfile_abs: str, locustfile_dir: str, users: int, spawn_rate: int,

                 run_time: str, burst: bool, warmup_seconds: int):
    """启动 Locust 无头模式：支持渐进加压(burst)、预热(warmup)、生成 HTML 报告"""
    locust_bin = _find_locust_bin()
    base_dir = Path(__file__).resolve().parent
    report_dir = base_dir / "reports" / "locust"
    report_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    locustfile_stem = Path(locustfile_abs).stem
    html_report = str(report_dir / f"locust_{locustfile_stem}_{timestamp}.html")
    csv_prefix = str(report_dir / f"locust_{locustfile_stem}_{timestamp}")
    junit_xml = str(report_dir / f"locust_{locustfile_stem}_{timestamp}.xml")
    log_file = str(report_dir / f"locust_{locustfile_stem}_{timestamp}.log")

    effective_spawn_rate = users if burst else spawn_rate

    args = [
        "--headless",
        "-u", str(users),
        "-r", str(effective_spawn_rate),
        "-t", run_time,
        "--html", html_report,
        "--csv", csv_prefix,
    ]

    try:
        import locust
        if tuple(int(x) for x in locust.__version__.split(".")[:2]) >= (2, 12):
            args.extend(["--junit-xml", junit_xml])
    except ImportError:
        logger.error("未安装 locust，请先执行: pip install locust")
        sys.exit(1)

    cmd = _build_cmd(locust_bin, locustfile_abs, args)

    logger.info("=" * 50)
    logger.info("Locust Headless 模式")
    logger.info("=" * 50)
    logger.info(f"Locust 文件: {locustfile_abs}")
    logger.info(f"并发用户: {users} | 产卵率: {effective_spawn_rate}/s | 运行时间: {run_time}")
    if burst:
        logger.info("Burst 模式: 瞬间起满用户")
    if warmup_seconds > 0:
        logger.info(f"预热剔除: 前 {warmup_seconds} 秒数据将从稳态报告中剔除")
    logger.info(f"HTML 报告: {html_report}")
    logger.info(f"CSV 前缀:  {csv_prefix}_*.csv")
    logger.info(f"日志:      {log_file}")
    logger.info("-" * 50)

    with open(log_file, "w", encoding="utf-8") as lf:
        result = subprocess.run(
            cmd,
            cwd=locustfile_dir,
            env=os.environ.copy(),
            stdout=lf,
            stderr=subprocess.STDOUT,
        )

    logger.info("-" * 50)
    locust_exit = result.returncode

    if Path(html_report).exists():
        logger.info(f"Locust HTML 报告已生成: {html_report}")
    else:
        logger.warning(f"Locust HTML 报告未生成: {html_report}")

    if warmup_seconds > 0:
        filter_warmup(csv_prefix, warmup_seconds, report_dir)

    if locust_exit == 0:
        logger.info("Locust 压测完成：全部请求成功")
    else:
        logger.warning(f"Locust 压测完成：存在失败请求 (返回码={locust_exit})")

    summary = _collect_summary(junit_xml, csv_prefix, run_time)

    if should_send_alert(summary):
        _send_failure_email(
            summary=summary,
            locustfile_stem=locustfile_stem,
            users=users,
            spawn_rate=effective_spawn_rate,
            run_time=run_time,
            burst=burst,
            warmup_seconds=warmup_seconds,
            html_report=html_report,
        )
    else:
        total = summary.get("total", 0)
        failed = summary.get("failed", 0)
        rate = (failed / max(total, 1) * 100)
        logger.info(f"失败率 {rate:.2f}% 低于阈值 {FAILURE_RATE_THRESHOLD*100:.1f}%，跳过告警邮件")

    logger.info("Locust Headless 压测结束")
    sys.exit(locust_exit)


def _collect_summary(junit_xml: str, csv_prefix: str, run_time: str) -> dict:
    """从 Locust 报告 CSV 汇总成功/失败/平均响应时间"""
    if os.path.exists(junit_xml):
        return parse_test_summary(junit_xml)
    summary = parse_locust_csv(csv_prefix)
    summary["duration"] = run_time
    return summary


def _send_failure_email(summary: dict, locustfile_stem: str, users: int, spawn_rate: int,

                        run_time: str, burst: bool, warmup_seconds: int,
                        html_report: str):
    """发送 Locust 失败告警邮件：包含压测参数、成功率、平均响应时间等"""
    logger.info("发送告警邮件...")
    try:
        from config.config import config
        current_env = config.get("env", "unknown")
        env_section = config.get("environment", {}).get(current_env, {})

        spawn_desc = f"{spawn_rate}/s" + (" (burst)" if burst else "")

        env_info = {
            "环境": current_env,
            "类型": "Locust 压测",
            "压测场景": locustfile_stem,
            "并发用户": str(users),
            "产卵率": spawn_desc,
            "运行时长": run_time,
            "预热剔除": f"前 {warmup_seconds} 秒" if warmup_seconds > 0 else "不剔除",
            "API 地址": env_section.get("base_url", "N/A"),
            "报告路径": html_report,
        }

        html_body = _build_html_report(summary, env_info, html_report)

        total = summary.get("total", 0)
        failed = summary.get("failed", 0)
        fail_pct = (failed / total * 100) if total else 0
        send_alert_email(
            subject=f"[告警] Locust 压测 {failed}/{total} 请求失败 (失败率 {fail_pct:.1f}%)",
            html_body=html_body,
        )
    except Exception as e:
        logger.error(f"邮件发送失败: {e}")


def run(locustfile_key: str, users: int, spawn_rate: int, run_time: str,
        headless: bool, no_open: bool, burst: bool, warmup_seconds: int):
    """Locust CLI 入口：解析参数后调用无头/Web 模式"""
    base_dir = Path(__file__).resolve().parent
    locustfile_abs = _resolve_locustfile(base_dir, locustfile_key)
    locustfile_dir = str(locustfile_abs.parent)

    if headless:
        _run_headless(locustfile_abs, locustfile_dir, users, spawn_rate, run_time, burst, warmup_seconds)
    else:
        _run_web(locustfile_abs, locustfile_dir, auto_open=not no_open)


def _parse_args():
    """解析 Locust 命令行参数"""
    parser = argparse.ArgumentParser(description="Locust 压测运行器")
    parser.add_argument("-f", "--locustfile", required=True,
                        help="Locust 场景文件名（放在 testcases/test_performance/locustfiles/ 下）或绝对路径")
    parser.add_argument("--headless", action="store_true",
                        help="无界面自动运行模式（默认是 Web UI 交互模式）")
    parser.add_argument("--no-open", action="store_true",
                        help="Web UI 模式下不自动打开浏览器")
    parser.add_argument("-u", "--users", type=int, default=DEFAULT_USERS,
                        help=f"(headless) 并发用户数 (默认: {DEFAULT_USERS})")
    parser.add_argument("-r", "--spawn-rate", type=int, default=DEFAULT_SPAWN_RATE,
                        help=f"(headless) 每秒产卵率 (默认: {DEFAULT_SPAWN_RATE})")
    parser.add_argument("-t", "--run-time", default=DEFAULT_RUN_TIME,
                        help=f"(headless) 运行时长，如 30s, 5m, 1h (默认: {DEFAULT_RUN_TIME})")
    parser.add_argument("--burst", action="store_true",
                        help="(headless) 瞬间启动所有用户（spawn_rate 强制 = users）")
    parser.add_argument("--warmup", type=int, default=DEFAULT_WARMUP_SECONDS,
                        help="(headless) 预热期秒数，稳态报告中将剔除前 N 秒 (默认: 0 = 不剔除)")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run(
        locustfile_key=args.locustfile,
        users=args.users,
        spawn_rate=args.spawn_rate,
        run_time=args.run_time,
        headless=args.headless,
        no_open=args.no_open,
        burst=args.burst,
        warmup_seconds=args.warmup,
    )