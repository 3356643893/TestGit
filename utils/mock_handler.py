import json
from pathlib import Path
from config.config import config

MOCK_DATA_FILE = Path(__file__).parent.parent / "mock_fastAPI" / "mock_data" / "mock_scenes.json"

_MOCK_SCENES = None
_mock_active = False
_mock_scenes = {}


def _load_mock_scenes() -> dict:
    global _MOCK_SCENES
    if _MOCK_SCENES is None:
        if not MOCK_DATA_FILE.exists():
            _MOCK_SCENES = {}
        else:
            with open(MOCK_DATA_FILE, "r", encoding="utf-8") as f:
                _MOCK_SCENES = json.load(f)
    return _MOCK_SCENES


def get_scene_data(scene_key: str, scene_val: str) -> dict | None:
    scenes = _load_mock_scenes()
    return scenes.get(scene_key, {}).get(scene_val)


def get_all_scenes() -> dict:
    scenes = _load_mock_scenes()
    return {k: list(v.keys()) for k, v in scenes.items()}


def activate_mock(scene: str = None, **kwargs):
    """激活 Mock，支持指定场景或按 env.yaml 配置自动读取

    用法:
        activate_mock("payment:success")
        activate_mock()
        activate_mock(payment="success", sms="rate_limit")
    """
    global _mock_active, _mock_scenes

    if scene:
        if ":" in scene:
            key, val = scene.split(":", 1)
            kwargs[key] = val
        else:
            raise ValueError(f"场景格式错误: '{scene}'。请使用 '业务:场景' 格式，例如 'payment:success'")

    if not kwargs:
        scenes = _load_mock_scenes()
        mock_cfg = config.get("mock", {})
        if mock_cfg.get("enabled"):
            for key in scenes:
                cfg_val = mock_cfg.get(key)
                if cfg_val and cfg_val in scenes[key]:
                    kwargs[key] = cfg_val

    _mock_scenes = kwargs
    _mock_active = True


def deactivate_mock():
    """Mock"""
    global _mock_active, _mock_scenes
    _mock_active = False
    _mock_scenes = {}


def is_mock_active() -> bool:
    """判断 Mock 是否已启用"""
    return _mock_active


def get_current_scenes() -> dict:
    """获取当前激活的 Mock 场景"""
    return _mock_scenes.copy()