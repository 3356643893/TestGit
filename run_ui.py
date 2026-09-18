import os
import sys
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from config.log_config import logger
from utils.allure_attach import clear_allure_results
from utils.email_sender import send_alert_email, _build_html_report, parse_test_summary

PYTEST_INFRA_ERRORS = {2, 4, 5}

SUITE = "ui"
TEST_DIR_NAME = "test_ui"


def run():
    """UI 测试套件入口：pytest 执行 test_ui 目录"""
    base_dir = Path(__file__).resolve().parent
    current_python = sys.executable
    allure_bin = shutil.which("allure")
    report_dir = base_dir / "reports" / SUITE
    report_dir.mkdir(parents=True, exist_ok=True)

    test_path = str(base_dir / "testcases" / TEST_DIR_NAME)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    allure_results = str(report_dir / "allure-results")
    allure_report = str(report_dir / "allure-report")
    junit_xml = str(report_dir / f"junit_{timestamp}.xml")
    log_file = str(report_dir / f"pytest_{timestamp}.log")

    clear_allure_results(SUITE)

    if not allure_bin:
        logger.error("未找到 allure 命令，请确认已安装 allure 并添加到 PATH")
        sys.exit(1)

    env = os.environ.copy()
    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    result = subprocess.run(
        [current_python, "-m", "pytest", test_path, "-v",
         f"--alluredir={allure_results}",
         f"--junitxml={junit_xml}",
         f"--log-file={log_file}"],
        shell=False,
        env=env
    )

    pytest_exit = result.returncode

    if pytest_exit in PYTEST_INFRA_ERRORS:
        logger.error(f"pytest 执行异常，返回码: {pytest_exit}")
        if pytest_exit == 4:
            logger.error("可能原因：导入错误、conftest 配置问题、命令行参数错误")
        elif pytest_exit == 5:
            logger.error("可能原因：没有收集到测试用例")
        sys.exit(pytest_exit)

    if pytest_exit == 0:
        logger.info("UI pytest 执行完毕：全部通过")
    else:
        logger.warning(f"UI pytest 执行完毕：存在失败用例 (返回码={pytest_exit})")

    result = subprocess.run(
        [allure_bin, "generate", allure_results, "-o", allure_report, "--clean"],
        shell=False,
        env=env
    )

    if result.returncode != 0:
        logger.error(f"allure generate 执行失败，返回码: {result.returncode}")
        sys.exit(result.returncode)

    report_index = str(Path(allure_report) / "index.html")
    logger.info(f"UI 测试报告已生成: {report_index}")

    if pytest_exit != 0:
        logger.info("发送告警邮件...")
        try:
            from config.config import config
            test_summary = parse_test_summary(junit_xml)

            current_env = config.get("env", "unknown")
            env_section = config.get("environment", {}).get(current_env, {})
            env_info = {
                "执行时间": start_time,
                "环境": current_env,
                "类型": "UI 测试",
                "API 地址": env_section.get("base_url", "N/A"),
                "UI 地址": env_section.get("ui_base_url", "N/A"),
                "数据库": env_section.get("db", {}).get("database", "N/A"),
                "报告路径": report_index,
            }

            html_body = _build_html_report(test_summary, env_info, report_index)

            failed_count = test_summary.get("failed", 0)
            total_count = test_summary.get("total", 0)
            send_alert_email(
                subject=f"[告警] UI 自动化测试 {failed_count}/{total_count} 用例失败",
                html_body=html_body
            )
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")

    logger.info("UI 测试结束")


if __name__ == "__main__":
    run()