import os
import smtplib
import xml.etree.ElementTree as ET
from loguru import logger
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config.config import config


def _build_html_report(test_summary, env_info, report_path):
    """从 JUnit XML 解析后拼装 HTML 报告邮件正文"""
    failures = test_summary.get("failures", [])
    total = test_summary.get("total", 0)
    passed = test_summary.get("passed", 0)
    failed = test_summary.get("failed", 0)
    skipped = test_summary.get("skipped", 0)
    duration = test_summary.get("duration", "")

    failure_rows = ""
    for i, f in enumerate(failures, 1):
        error_detail = f.get("error", "")[:300]
        failure_rows += f"""
        <tr>
            <td>{i}</td>
            <td style="font-family:monospace;font-size:12px;">{f.get('test_name', '')}</td>
            <td style="color:#e74c3c;font-family:monospace;font-size:11px;">{error_detail}</td>
        </tr>"""

    env_rows = ""
    for key, val in env_info.items():
        env_rows += f"""
        <tr>
            <td style="font-weight:bold;width:120px;">{key}</td>
            <td>{val}</td>
        </tr>"""

    html = f"""
    <div style="font-family:'Microsoft YaHei',Arial,sans-serif;max-width:800px;margin:0 auto;">
        <h2 style="color:#e74c3c;border-bottom:3px solid #e74c3c;padding-bottom:10px;">
            自动化测试告警
        </h2>
        <p style="color:#666;font-size:13px;">
            检测到 <strong style="color:#e74c3c;">{failed}</strong> 个用例失败，
            用时 <strong>{duration}</strong>，请相关开发同学关注。
        </p>

        <table style="width:100%;border-collapse:collapse;margin:15px 0;font-size:13px;">
            <tr style="background:#f5f5f5;">
                <th style="border:1px solid #ddd;padding:8px;text-align:center;">总用例</th>
                <th style="border:1px solid #ddd;padding:8px;color:#27ae60;text-align:center;">通过</th>
                <th style="border:1px solid #ddd;padding:8px;color:#e74c3c;text-align:center;">失败</th>
                <th style="border:1px solid #ddd;padding:8px;color:#f39c12;text-align:center;">跳过</th>
            </tr>
            <tr>
                <td style="border:1px solid #ddd;padding:8px;text-align:center;">{total}</td>
                <td style="border:1px solid #ddd;padding:8px;text-align:center;">{passed}</td>
                <td style="border:1px solid #ddd;padding:8px;text-align:center;">{failed}</td>
                <td style="border:1px solid #ddd;padding:8px;text-align:center;">{skipped}</td>
            </tr>
        </table>

        <h3 style="color:#2c3e50;background:#ecf0f1;padding:8px 12px;border-radius:4px;">环境信息</h3>
        <table style="width:100%;border-collapse:collapse;margin:10px 0;font-size:13px;">
            {env_rows}
        </table>

        <h3 style="color:#2c3e50;background:#ecf0f1;padding:8px 12px;border-radius:4px;">失败用例详情</h3>
        <table style="width:100%;border-collapse:collapse;margin:10px 0;font-size:12px;">
            <tr style="background:#f5f5f5;">
                <th style="border:1px solid #ddd;padding:8px;width:30px;">#</th>
                <th style="border:1px solid #ddd;padding:8px;text-align:left;">用例名称</th>
                <th style="border:1px solid #ddd;padding:8px;text-align:left;">错误信息</th>
            </tr>
            {failure_rows if failure_rows else '<tr><td colspan="3" style="border:1px solid #ddd;padding:8px;text-align:center;color:#999;">无</td></tr>'}
        </table>

        <div style="margin-top:20px;padding:12px;background:#f8f9fa;border-left:4px solid #3498db;font-size:12px;color:#555;">
            <strong>报告路径：</strong>{report_path}<br>
            <strong>提示：</strong>如报告路径无法访问，请在本地打开 Allure 报告查看完整的请求/响应详情。
        </div>
    </div>"""
    return html

def parse_test_summary(junit_xml_path):
    """解析 JUnit XML 返回 pass/fail/error/summary 字典"""
    summary = {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "failures": [], "duration": ""}
    if not os.path.exists(junit_xml_path):
        return summary

    try:
        tree = ET.parse(junit_xml_path)
        root = tree.getroot()
        time_attr = root.get("time", "0")
        try:
            seconds = float(time_attr)
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            summary["duration"] = f"{minutes}分{secs}秒"
        except (ValueError, TypeError):
            summary["duration"] = f"{time_attr}s"

        for suite in root.iter("testsuite"):
            for case in suite.iter("testcase"):
                summary["total"] += 1
                classname = case.get("classname", "")
                name = case.get("name", "")
                test_name = f"{classname}::{name}" if classname else name

                failure = case.find("failure")
                error = case.find("error")
                skipped = case.find("skipped")

                if failure is not None:
                    summary["failed"] += 1
                    error_msg = failure.get("message", "") or failure.text or ""
                    summary["failures"].append({
                        "test_name": test_name,
                        "error": error_msg.strip()
                    })
                elif error is not None:
                    summary["failed"] += 1
                    error_msg = error.get("message", "") or error.text or ""
                    summary["failures"].append({
                        "test_name": test_name,
                        "error": error_msg.strip()
                    })
                elif skipped is not None:
                    summary["skipped"] += 1
                else:
                    summary["passed"] += 1
    except Exception as e:
        logger.error(f"解析 JUnit XML 失败: {e}")

    return summary


def send_alert_email(to=None, subject=None, body=None, html_body=None):
    """发送告警邮件：支持纯文本 + HTML 格式，自动从 config 读取 SMTP 配置"""
    to = to or config.get("notify.mail_to", "")
    if not to:
        logger.warning("未配置收件邮箱，跳过邮件发送")
        return

    if isinstance(to, str):
        to_list = [addr.strip() for addr in to.split(",") if addr.strip()]
    else:
        to_list = list(to)

    subject = subject or "自动化测试告警"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config.get("notify.mail_from", "")
    msg["To"] = ", ".join(to_list)

    if body:
        msg.attach(MIMEText(body, "plain", "utf-8"))
    if html_body:
        msg.attach(MIMEText(html_body, "html", "utf-8"))

    smtp_server = config.get("notify.smtp_server", "smtp.qq.com")
    smtp_port = config.get("notify.smtp_port", 587)
    my_email = config.get("notify.mail_from", "")
    my_password = config.get("notify.mail_password", "")

    if not my_email or not my_password:
        logger.warning("邮件凭据未配置，跳过发送")
        return

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(my_email, my_password)
            server.sendmail(my_email, to_list, msg.as_string())
            logger.info(f"邮件发送成功 → {', '.join(to_list)}")
    except Exception as e:
        logger.error(f"邮件发送失败: {e}")


if __name__ == "__main__":
    send_alert_email(
        to="test@example.com",
        subject="测试邮件",
        html_body="<h3>这是一封来自自动化测试框架的测试邮件。</h3>"
    )
