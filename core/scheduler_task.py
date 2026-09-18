"""
定时任务调度器
- 基于 APScheduler（你 requirements.txt 里已经有了）
- 支持：定时跑测试、发送结果邮件、记录历史
- 使用方式：
    1. 单独运行：python -m core.scheduler_task
    2. 或在 web 启动时顺带启动调度器
"""

import os
import sys
import subprocess
import json
import time
from datetime import datetime
from pathlib import Path
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from config.config import config
from config.log_config import logger
from utils.allure_attach import clear_allure_results

# ─────────────────────────────────────────────
# 任务 1：跑 pytest 测试用例
# ─────────────────────────────────────────────
def run_pytest_task(task_type: str = "full"):
    """
        执行 pytest 测试任务
        :param task_type: "smoke" 冒烟测试 / "full" 全量测试
    """
    logger.info(f"开始执行任务：{task_type}")

    clear_allure_results()

    pytest_args = [
        sys.executable, "-m", "pytest",
        str(BASE_DIR / "testcases"),
        "-v",
        "--alluredir=reports/allure-results",
     ]

    # 冒烟测试：只跑带 @pytest.mark.smoke 标签的用例
    if task_type == "smoke":
        pytest_args.extend(["-m", "smoke"])

    # 3. 执行测试
    result = subprocess.run(
        pytest_args,
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
        env={**os.environ.copy(), "PYTHONPATH": BASE_DIR}
    )

    # 4. 记录结果
    summary = {
        "task_type": task_type,
        "start_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "return_code": result.returncode,  # 0 = 全过，非 0 = 有失败
        "stdout_tail": result.stdout[-2000:] if result.stdout else "",
        "stderr_tail": result.stderr[-2000:] if result.stderr else "",
    }

    # 5. 保存到日志文件
    result_file = BASE_DIR / "reports" / "logs" / f"scheduler_{task_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    result_file.parent.mkdir(parents=True, exist_ok=True)
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # 6. 生成 Allure 报告
    report_dir = BASE_DIR / "reports" / "history" / f"{task_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    subprocess.run(
        ["allure", "generate", "reports/allure-results", "-o", report_dir, "--clean"],
        cwd=BASE_DIR
    )

    # 7. 如果有失败，尝试发邮件告警（你已经有 email_sender.py）
    if result.returncode != 0:
        logger.warning(f"❌ [{task_type}] 任务执行完毕：有用例失败！")
        try:
            from utils.email_sender import send_alert_email
            mail_to = config.get("notify.mail_to", "test@xxx.com")
            send_alert_email(
                to=mail_to,
                subject=f"[告警] {task_type} 自动化测试有失败用例",
                body=(
                    f"任务类型: {task_type}\n"
                    f"执行时间: {summary['start_time']}\n"
                    f"返回码: {result.returncode}\n"
                    f"输出摘要:\n{result.stdout[-1000:]}\n"
                )
            )
            logger.info(f"📧 已发送告警邮件到 {mail_to}")
        except Exception as e:
            logger.error(f"发送邮件失败: {e}")
    else:
        logger.info(f"✅ [{task_type}] 任务执行完毕：全部通过")

    return summary

# ─────────────────────────────────────────────
# 任务 2：数据清理（删除 N 天前的旧报告）
# ─────────────────────────────────────────────
def cleanup_old_reports(days: int = 7):
    """清理超过保留天数的历史报告目录"""
    history_dir = BASE_DIR / "reports" / "history"
    if not history_dir.exists():
        return

    cutoff = time.time() - days * 24 * 3600
    cleaned = 0

    for dir_path in history_dir.iterdir():
        if dir_path.is_dir() and dir_path.stat().st_mtime < cutoff:
            import shutil
            shutil.rmtree(dir_path)
            cleaned += 1

    logger.info(f"🧹 清理了 {cleaned} 个 {days} 天前的报告目录")

# ─────────────────────────────────────────────
# 调度器主入口
# ─────────────────────────────────────────────
def start_scheduler():
    """启动 APScheduler 定时任务（每日定时跑回归）"""
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")

    # ── 每天凌晨 2:00 跑全量回归 ─────────────
    scheduler.add_job(
        run_pytest_task,
        trigger=CronTrigger(hour=2, minute=0),  # Cron 表达式：每天 2 点
        args=["full"],
        id="daily_full_test",
        name="每日全量回归测试",
        replace_existing=True,
    )

    # ── 每 4 小时跑一次冒烟测试 ──────────────
    scheduler.add_job(
        run_pytest_task,
        trigger=IntervalTrigger(hours=4),       # 每 4 小时一次
        args=["smoke"],
        id="interval_smoke_test",
        name="定时冒烟测试",
        replace_existing=True,
    )

    # ── 每天凌晨 3:00 清理 7 天前的旧报告 ───
    scheduler.add_job(
        cleanup_old_reports,
        trigger=CronTrigger(hour=3, minute=0),
        args=[7],
        id="daily_cleanup",
        name="每日报告清理",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("🚀 定时任务调度器已启动")
    logger.info("已注册任务:")
    for job in scheduler.get_jobs():
        logger.info(f"  - [{job.id}] {job.name} (下次执行: {job.next_run_time})")

    return scheduler

# ─────────────────────────────────────────────
# 命令行直接运行
# ─────────────────────────────────────────────
if __name__ == "__main__":
    scheduler = start_scheduler()

    # 保持进程不退出（按 Ctrl+C 终止）
    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("👋 调度器已停止")
