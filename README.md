# Test Framework v1.0.0

一个开箱即用的 **Pytest + Allure** 自动化测试框架，支持 API / UI / 性能 三类测试，内置 Mock 能力、DB 断言、测试管理后台、Locust 压测集成，开箱即用到任何新项目。

---

## ✨ 特性

| 能力 | 说明 |
|---|---|
| 🏗️ 三层配置架构 | 默认值 `defaults.yaml` → 环境配置 `env.yaml` → `.env` 敏感注入，优先级清晰 |
| 🔌 通用 HTTP 客户端 | 自动重试、Token 缓存、统一异常捕获、Mock 切换零侵入 |
| 🖥️ UI 测试基类 | 基于 Playwright PO 模式，封装通用等待 / 截图 / 重试 |
| 🗄️ DB 断言 | MySQL / PostgreSQL 双驱动，支持查询验证业务数据 |
| 🎭 Mock 服务 | 内置 FastAPI Mock Server + `requests` 拦截器，开发测试不依赖真实后端 |
| 📊 Allure 报告 | 步骤标注、附件自动截图、历史对比、环境信息注入 |
| 📈 Locust 压测 | CLI 一键启动 headless / Web 两种模式，自动输出稳态报告 |
| 🌐 测试管理后台 | FastAPI + Vue，Web 界面触发测试任务、查看历史报告 |
| 📧 邮件告警 | 失败自动发送带报告链接的邮件通知 |
| 🔁 CI/CD 就绪 | Jenkinsfile + Gitee CI YAML，拉下来就能流水线 |

---

## 📁 目录结构

```
Test_framework_v1.0.0/
│
├── config/                  # 配置中心
│   ├── config.py            # 配置加载器（三层合并 + .env 注入）
│   ├── defaults.yaml        # 框架默认值
│   ├── env.yaml.example     # 环境配置模板（复制改名为 env.yaml）
│   ├── log_config.py        # 日志格式配置
│   └── env.yaml             # 实际环境配置（.gitignore）
│
├── core/                    # 核心能力层
│   ├── api_client.py        # 通用 HTTP 客户端（重试 / Token / Mock）
│   ├── base_page.py         # Playwright PO 基类
│   ├── db_handler.py        # 通用 DB 连接与查询（MySQL / PostgreSQL）
│   └── scheduler_task.py    # 定时任务调度器
│
├── utils/                   # 通用工具类
│   ├── assert_util.py       # 断言工具（JSON path / 模糊匹配 / 列表包含）
│   ├── data_driver.py       # 参数化数据驱动（YAML / JSON / CSV / Excel）
│   ├── data_factory.py      # 测试数据工厂（随机手机号 / 身份证 / 邮箱）
│   ├── mock_handler.py      # Mock 场景管理器
│   ├── db_util.py           # DB 业务工具 + Web 平台 service 层
│   ├── email_sender.py      # 邮件发送
│   ├── token_cache.py       # Token 缓存（自动过期刷新）
│   ├── decorators.py        # 装饰器（重试 / 步骤 / 失败截图）
│   ├── json_util.py         # JSON 工具
│   ├── yaml_util.py         # YAML 工具
│   ├── allure_attach.py     # Allure 附件快捷方法
│   └── locust_report.py     # Locust 报告解析
│
├── testcases/               # 测试用例（新项目往里填）
│   ├── conftest.py          # 通用 fixture（api_client / db / auto_mock）
│   ├── test_api/            # API 测试用例
│   ├── test_ui/             # UI 测试用例 + 子 conftest
│   └── test_performance/      # 性能压测
│       └── locustfiles/     # Locust 场景文件
│
├── mock_fastAPI/            # 可选：独立 Mock 后端服务（FastAPI）
│   ├── main.py
│   ├── api/
│   ├── schemas/
│   └── service/
│
├── web/                     # 可选：测试任务管理后台
│   ├── backend/             # FastAPI 后端（任务 CRUD + 报告查询）
│   └── frontend/            # Vue + Vite 前端
│
├── models/                  # ORM 模型 + 业务模型（新项目自行扩展）
│
├── run.py                   # 统一入口（自动分发 api / ui / performance）
├── run_api.py               # API 测试入口
├── run_ui.py                # UI 测试入口
├── run_performance.py        # 性能测试入口（pytest + pytest-benchmark）
├── run_locust.py            # Locust 压测入口
├── conftest.py              # 根级 conftest（注册 --env 命令行参数）
├── pytest.ini               # pytest 配置 + 自定义 markers
├── git_push.py              # 一键推送工具
│
├── requirements.txt         # 核心依赖
├── requirements-dev.txt     # 开发依赖
├── requirements-lock.txt    # 锁版本依赖
├── .env.example             # 敏感信息模板（复制改名为 .env）
├── .gitignore
│
├── jenkins/Jenkinsfile      # Jenkins 流水线模板
└── .gitee-ci.yml            # Gitee CI 流水线模板
```

---

## 🚀 快速上手

### 1. 克隆 & 安装

```bash
git clone https://github.com/3356643893/TestGit.git
cd TestGit
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. 配置环境

```bash
# 敏感信息配置（.env 不入库）
cp .env.example .env

# 环境参数配置
cp config/env.yaml.example config/env.yaml
```

编辑 `.env`，填入 DB 账号密码（不需要 DB 测试可留空）：

```ini
TEST_DB_USER=your_user
TEST_DB_PASSWORD=your_password
STAGING_DB_USER=your_user
STAGING_DB_PASSWORD=your_password
SMTP_PASS=your_email_password
```

编辑 `config/env.yaml`，填入实际服务地址：

```yaml
environment:
  test:
    base_url: "http://127.0.0.1:8080/api"
    ui_base_url: "http://127.0.0.1:8080"
    mock:
      enabled: true        # 本地开发开 Mock，不依赖真实后端
  staging:
    base_url: "https://staging-api.xxx.com"
    ui_base_url: "https://staging.xxx.com"
    mock:
      enabled: false
  prod:
    base_url: "https://api.xxx.com"
    ui_base_url: "https://xxx.com"
    mock:
      enabled: false
```

### 3. 运行测试

```bash
# ========= API 测试 =========
python run.py api                  # 跑全部 API 用例（默认 test 环境）
python run.py api --env staging    # 指定环境
python run.py api -m "smoke"       # 只跑冒烟用例
python run_api.py -v -k "test_login"

# ========= UI 测试 =========
python run.py ui                   # Playwright 自动打开浏览器
python run_ui.py --env staging

# ========= 性能测试（pytest）=========
python run.py perf -m "pressure"
python run_performance.py --benchmark-only

# ========= Locust 压测 =========
python run_locust.py -f auth_locust.py --headless -u 100 -r 10 -t 5m
python run_locust.py -f auth_locust.py               # Web UI 交互模式
```

运行完自动生成 Allure 报告，一键打开：

```bash
allure serve allure-results
```

---

## 🔧 配置优先级

```
.env （环境变量注入，敏感信息）
        ↓ 覆盖
config/env.yaml （当前环境配置）
        ↓ 缺失时回退
config/defaults.yaml （框架默认值）
```

读取示例：

```python
from config.config import config

config.get("base_url")                  # 当前环境 base_url
config.get("db.host")                   # 当前环境 DB host
config.get("timeout", 10)               # 带默认值读取
config.get_current_env()                # 当前环境名：test / staging / prod
```

---

## 📝 写一个测试用例

### API 用例

```python
import pytest
from core.api_client import APIClient

pytestmark = pytest.mark.p0

class TestLogin:
    def test_login_success(self, api_client):
        resp = api_client.post("/login", json={
            "phone": "13800138000",
            "password": "123456"
        })
        assert resp.status_code == 200
        assert resp.json()["code"] == 0

    def test_login_wrong_password(self, api_client):
        resp = api_client.post("/login", json={
            "phone": "13800138000",
            "password": "wrong"
        })
        assert resp.status_code == 400
```

### UI 用例

```python
import pytest
from allure_commons.types import AttachmentType

pytestmark = [pytest.mark.ui, pytest.mark.p0]

def test_homepage(playwright, ui_base_url):
    page = playwright.new_page()
    page.goto(ui_base_url)
    assert page.title() == "Your App"
    allure.attach(page.screenshot(), name="homepage", attachment_type=AttachmentType.PNG)
    page.close()
```

### 带 DB 断言的用例

```python
def test_order_created(api_client, db):
    resp = api_client.post("/orders", json={"sku": "ABC"})
    order_id = resp.json()["data"]["id"]
    row = db.query_one("SELECT status FROM orders WHERE id = ?", (order_id,))
    assert row["status"] == "paid"
```

### 参数化数据驱动

```python
import pytest
from utils.data_driver import load_yaml

test_data = load_yaml("testcases/data/login_cases.yaml")

@pytest.mark.parametrize("case", test_data)
def test_login_param(api_client, case):
    resp = api_client.post("/login", json=case["input"])
    assert resp.status_code == case["expect"]["status"]
```

---

## 🎭 使用 Mock

### 启用 Mock

在 `config/env.yaml` 中设置 `mock.enabled: true`，`requests` 会自动被拦截。

### 定义 Mock 场景

```python
from utils.mock_handler import activate_mock, register_mock_data

# 注册场景数据
register_mock_data("payment", "success", {
    "code": 0, "msg": "ok", "data": {"order_id": "MOCK_123"}
})

# 激活场景
activate_mock(payment="success")
```

### 启动独立 Mock 后端（可选）

```bash
cd mock_fastAPI
python main.py
# 默认 http://127.0.0.1:9000
```

---

## 🌐 测试管理后台（可选）

```bash
# 后端
cd web/backend
python main.py                # http://127.0.0.1:8001

# 前端（开发模式）
cd web/frontend
npm install
npm run dev                   # http://127.0.0.1:5173

# 前端（生产构建）
npm run build
```

---

## 📊 Pytest Markers

| Marker | 说明 |
|---|---|
| `smoke` | 冒烟测试 |
| `regression` | 全量回归 |
| `p0` / `p1` | 优先级 |
| `ui` / `api` | 测试类型 |
| `pressure` | 性能压力测试 |
| `slow` | 耗时较长用例 |
| `env` | 多环境测试 |

筛选示例：

```bash
pytest -m "smoke"
pytest -m "p0 and api"
pytest -m "not slow"
```

---

## 🔁 CI/CD

### Jenkins

仓库根目录的 `jenkins/Jenkinsfile` 可直接用：

```groovy
// 在 Jenkins 里新建 Pipeline 任务，指向仓库根目录的 Jenkinsfile
// 或使用 Jenkins Shared Library
```

### Gitee CI

仓库根目录的 `.gitee-ci.yml` 可直接用，触发 push / MR 自动构建。

---

## 🗑️ 项目清理说明

本框架已做过以下清理，确保可直接复用：

- ❌ 已移除：`.venv` / `.git` 历史 / `.idea` / 所有 `__pycache__` / 真实 `.env` 凭据
- ❌ 已移除：`api_client.py` 中的业务 Mock 路径硬编码
- ❌ 已移除：`testcases/conftest.py` 中的业务 Mock fixture（payment / auth / sms）
- ❌ 已移除：`pytest.ini` 中的业务 markers（register / profile）
- ❌ 已移除：`run_locust.py` 中的业务 Locust 场景硬编码
- ✅ 保留：`web/` 测试管理后台 / `mock_fastAPI/` Mock 服务 / 所有通用工具

---

## 📌 新项目 Checklist

- [ ] `pip install -r requirements.txt`
- [ ] 复制 `.env.example` → `.env`，填敏感信息
- [ ] 复制 `config/env.yaml.example` → `config/env.yaml`，改服务地址
- [ ] 往 `testcases/` 里填业务测试用例
- [ ] 往 `core/apis/` 里封装业务 API 类（可选）
- [ ] 往 `testcases/locustfiles/` 里写 Locust 场景（可选）
- [ ] `python run.py api` 跑通冒烟
- [ ] `git remote add origin <new_repo>` 推到自己的仓库

---

## 📄 License

MIT