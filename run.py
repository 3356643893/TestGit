import sys
from config.log_config import logger

SUITES = {
    "api": ("test_api", "run_api"),
    "ui": ("test_ui", "run_ui"),
    "performance": ("test_performance", "run_performance"),
}

HELP_TEXT = """
用法: python run.py [suite]

  suite:
    api          仅运行 API 测试
    ui           仅运行 UI 测试
    performance  仅运行性能/压力测试
    all          依次运行 API + UI + 性能（默认）
    help         显示本帮助

示例:
    python run.py api       # 只跑 API
    python run.py ui        # 只跑 UI
    python run.py           # 跑全部
"""


def _run_module(module_name):
    """按模块名动态 import 并执行其 run() 函数"""
    import importlib
    mod = importlib.import_module(module_name)
    mod.run()


def main():
    """主入口：解析 CLI 参数，选择 api/ui/all 测试套件并执行"""
    target = sys.argv[1] if len(sys.argv) > 1 else "all"

    if target in ("help", "-h", "--help"):
        print(HELP_TEXT)
        return

    if target == "all":
        logger.info("模式: 运行全部 (API + UI + Performance)")
        for suite_name in SUITES:
            _, runner = SUITES[suite_name]
            _run_module(runner)
        return

    if target in SUITES:
        _, runner = SUITES[target]
        logger.info(f"模式: 仅运行 {target}")
        _run_module(runner)
        return

    logger.error(f"未知 suite: {target}")
    print(HELP_TEXT)
    sys.exit(1)


if __name__ == "__main__":
    main()