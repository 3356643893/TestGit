"""
一键提交推送脚本

用法：
    python git_push.py                           # 默认 commit message（时间戳）+ 推送当前分支
    python git_push.py "fix: 修复登录Bug"         # 自定义 commit message
    python git_push.py "msg" -b master           # 强制推送到指定分支（不推荐日常用）
    python git_push.py --force                   # 跳过 add 前的确认（默认会展示状态让你瞄一眼）

设计原则：
    - 推送的是【当前分支】，不会乱切分支
    - 默认禁止直接推 master/main（怕手滑）
    - pull 冲突时脚本停住，等你手动解决后再重跑
    - 不绕过 .gitignore，git add . 就是让 git 决定哪些该加
"""
import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_DIR = str(Path(__file__).resolve().parent)

PROTECTED_BRANCHES = {"master", "main", "develop"}


def run_git(cmd: str, check: bool = True) -> tuple[int, str, str]:
    """执行 git 命令，返回 (退出码, stdout, stderr)"""
    result = subprocess.run(
        cmd, shell=True, cwd=PROJECT_DIR,
        capture_output=True, text=True,
        encoding="utf-8", errors="replace"
    )
    if result.stdout and not check:
        print(result.stdout.strip())
    if result.stderr and not check:
        print(result.stderr.strip())
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def check_git_repo() -> bool:
    """校验：是否在 git 仓库内"""
    rc, out, _ = run_git("git rev-parse --is-inside-work-tree")
    if rc != 0 or out != "true":
        print("❌ 当前目录不是 git 仓库")
        return False
    return True


def is_rebasing() -> bool:
    """检查：是否处于 rebase 中断状态"""
    rc, _, _ = run_git("git rev-parse --git-path rebase-merge")
    if rc != 0:
        rc, _, _ = run_git("git rev-parse --git-path rebase-apply")
    return rc == 0


def get_current_branch() -> str:
    """获取当前分支名（detached HEAD 时返回空）"""
    rc, out, _ = run_git("git rev-parse --abbrev-ref HEAD")
    if rc != 0 or out == "HEAD":
        return ""
    return out


def check_branch_protection(target_branch: str, force_override: bool) -> bool:
    """校验：目标分支是否在保护名单内，保护分支禁止直接推送"""
    if target_branch in PROTECTED_BRANCHES:
        if force_override:
            print(f"⚠️  目标分支 '{target_branch}' 受保护，已通过 --force 强制覆盖")
            return True
        print(f"❌ 分支 '{target_branch}' 受保护（PROTECTED_BRANCHES={PROTECTED_BRANCHES}）")
        print("   直接推主分支容易污染历史。建议：")
        print(f"     1. 创建 feature 分支:  git checkout -b feature/my-change")
        print(f"     2. 推送后发 Pull Request")
        print(f"     3. 或确认要直接推时加 --force 参数")
        return False
    return True


def show_status():
    """展示当前 git 状态（让你确认要提交什么）"""
    print("📋 当前 git 状态：")
    rc, out, err = run_git("git status --short")
    if out:
        for line in out.splitlines():
            print(f"   {line}")
    if rc != 0 and err:
        print(f"   {err}")
    if not out and rc == 0:
        print("   （工作区干净，没有变更）")
    return out or err


def confirm_add() -> bool:
    """让用户确认是否要 git add 全部"""
    try:
        ans = input("\n⚠️  确认 'git add .' 暂存所有变更？[y/N]: ").strip().lower()
        return ans in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        return False


def do_pull_rebase() -> bool:
    """执行 git pull --rebase，冲突时停住并提示"""
    print("\n📥 拉取远程更新（rebase）...")
    rc, out, err = run_git("git pull --rebase", check=False)
    if rc == 0:
        return True

    if is_rebasing():
        print("\n❌ pull --rebase 发生冲突！脚本已停住，等你手动解决：")
        print("   1. git status                    看哪些文件冲突了")
        print("   2. 手动编辑冲突文件（解决 <<< === >>>）")
        print("   3. git add <冲突文件>")
        print("   4. git rebase --continue         继续 rebase")
        print("      或 git rebase --abort         放弃 rebase")
        print("   5. 解决完后重新运行本脚本")
        return False

    print(f"❌ pull 失败 (exit={rc})")
    return False


def do_push(target_branch: str) -> bool:
    """推送到目标分支（git push origin HEAD:<branch>，显式指定远程分支）"""
    print(f"\n🚀 推送到 origin/{target_branch} ...")
    rc, out, err = run_git(f'git push origin HEAD:{target_branch}', check=False)
    if rc != 0:
        if "rejected" in err.lower() or "non-fast-forward" in err.lower():
            print("\n❌ 推送被拒绝：远程有你本地没有的提交")
            print("   请先运行 python git_push.py 重新 pull --rebase")
        else:
            print(f"❌ push 失败 (exit={rc})")
            print("   请检查网络、远程仓库权限，或手动执行 git push 看完整错误")
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description="一键 git add + commit + pull --rebase + push")
    parser.add_argument("message", nargs="?", default=None, help="commit message（默认用时间戳）")
    parser.add_argument("-b", "--branch", default=None, help="指定推送的远程分支（默认推当前分支）")
    parser.add_argument("-f", "--force", action="store_true", help="跳过 add 前的确认 + 允许推保护分支")
    args = parser.parse_args()

    print("=" * 55)

    # ----- 前置检查 -----
    if not check_git_repo():
        return 1

    current = get_current_branch()
    if not current:
        print("❌ 当前处于 detached HEAD，不建议推送")
        print("   请先 git checkout <branch> 切回分支")
        return 1

    target_branch = args.branch or current
    print(f"📍 当前分支: {current}")
    print(f"🎯 推送目标: origin/{target_branch}")

    # ----- 分支保护校验 -----
    if not check_branch_protection(target_branch, args.force):
        return 1

    # ----- 检测 rebase 中断残留 -----
    if is_rebasing():
        print("\n⚠️  检测到上次 rebase 未完成，请先手动处理：")
        print("   git rebase --continue   或   git rebase --abort")
        return 1

    # ----- commit message -----
    commit_msg = args.message or f"update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    print(f"📝 Commit: {commit_msg}")
    print("=" * 55)

    # ----- 展示状态 + 确认 -----
    has_changes = show_status()
    if not has_changes:
        print("\n✅ 没有变更，无需提交推送")
        return 0

    # ----- git add -----
    if args.force:
        print("\n📦 --force 模式，跳过确认直接暂存全部变更...")
    elif not confirm_add():
        print("\n❌ 已取消。手动处理后重新运行。")
        return 1

    rc, _, err = run_git("git add .", check=False)
    if rc != 0:
        print(f"❌ git add 失败: {err}")
        return 1

    # ----- git commit -----
    rc, _, _ = run_git(f'git commit -m "{commit_msg}"', check=False)
    if rc != 0:
        print("⚠️  可能没有变更需要提交，或提交失败")

    # ----- git pull --rebase -----
    if not do_pull_rebase():
        return 1

    # ----- git push -----
    if not do_push(target_branch):
        return 1

    print("\n✅ 完成！")
    return 0


if __name__ == "__main__":
    sys.exit(main())