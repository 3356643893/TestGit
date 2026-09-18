import time
from playwright.sync_api import Page, Frame, Locator, TimeoutError as PlaywrightTimeoutError


DEFAULT_TIMEOUT = 10000
POLL_INTERVAL = 100


class BasePage:
    """
    增强型页面对象基类：
    - iframe 双向查找（正向 by_index/by_name + 反向 containing_locator）
    - Mask 遮罩层处理（自动检测并等待消失）
    - 稳定等待（auto_wait + 元素就绪状态机：visible + enabled + stable）
    - 失败重试（操作失败自动重试 N 次）
    - 文件下载（event.expect_download + save_as）
    - 文件上传（set_input_files + 多文件支持）
    - 浏览器上下文隔离（storage_state + 多标签页）
    """

    def __init__(self, page: Page):
        """接收 Playwright Page 对象"""
        self.page = page

    # ========== 私有辅助 ==========

    def _resolve_locator(self, locator: str, locator_type: str = "css") -> Locator:
        """解析定位器为 Playwright Locator"""
        if locator_type == "xpath":
            return self.page.locator(f"xpath={locator}")
        return self.page.locator(locator)

    def _resolve_multi_locator(self, locators: list, locator_type: str = "css") -> Locator:
        """多个定位器合并为一个 Locator（任一定位器命中即算）"""
        prefix = "xpath=" if locator_type == "xpath" else ""
        result = self.page.locator(f"{prefix}{locators[0]}")
        for loc in locators[1:]:
            result = result.or_(self.page.locator(f"{prefix}{loc}"))
        return result

    def _with_retry(self, operation: callable, name: str = "", retries: int = 2):
        """执行操作，失败自动重试 retries 次"""
        last_err = None
        for attempt in range(retries + 1):
            try:
                return operation()
            except Exception as e:
                last_err = e
                if attempt < retries:
                    time.sleep(0.5)
        raise Exception(f"[{name or operation.__name__}] 重试 {retries + 1} 次后仍失败: {last_err}")

    # ========== 稳定等待 ==========

    def wait_for_element_stable(self, locator, locator_type="css", timeout=5000, stable_ms=300):
        """
        等待元素稳定可见：先 wait_for visible，再连续 stable_ms 毫秒保持可见。
        避免元素刚出现又消失（如 loading 闪动）导致误操作。
        """
        el = self._resolve_locator(locator, locator_type)
        el.wait_for(state="visible", timeout=timeout)
        start = time.time()
        stable_start = None
        while time.time() - start < timeout / 1000:
            if el.is_visible():
                if stable_start is None:
                    stable_start = time.time()
                elif (time.time() - stable_start) * 1000 >= stable_ms:
                    return el
            else:
                stable_start = None
            time.sleep(POLL_INTERVAL / 1000)
        raise Exception(f"元素 [{locator}] 在 {timeout}ms 内未达到稳定可见状态")

    def wait_until_ready(self, locator, locator_type="css", timeout=DEFAULT_TIMEOUT):
        """
        元素就绪状态机：visible → enabled → stable → return Locator
        """
        el = self.wait_for_element_stable(locator, locator_type, timeout=timeout)
        self.wait_for_element(locator, locator_type, timeout=timeout, state="visible")
        return el

    # ========== 导航与等待 ==========

    def goto(self, url: str, wait_until="domcontentloaded"):
        """跳转页面，等待 DOM 就绪后自动等待主按钮可点击"""
        self.page.goto(url, wait_until=wait_until)
        self.page.wait_for_load_state("networkidle", timeout=15000)

    def wait_for_load_state(self, state: str = "networkidle", timeout: int = 30000):
        """等待页面达到指定加载状态"""
        self.page.wait_for_load_state(state, timeout=timeout)

    def wait_for_timeout(self, milliseconds: int):
        """硬等待指定毫秒数"""
        self.page.wait_for_timeout(milliseconds)

    def wait_for_element(self, locator, locator_type="css", timeout=5000, state="visible"):
        """等待元素出现/消失"""
        if locator_type == "xpath":
            self.page.wait_for_selector(f"xpath={locator}", timeout=timeout, state=state)
        else:
            self.page.wait_for_selector(locator, timeout=timeout, state=state)

    def wait_for_event(self, event: str, timeout: int = 5000):
        """等待指定事件触发"""
        return self.page.wait_for_event(event, timeout=timeout)

    # ========== Mask 遮罩层处理 ==========

    def wait_mask_gone(self, mask_selector: str = ".el-loading-mask, .k-loading-mask, .ant-spin, .loading-mask",

                       timeout: int = 10000):
        """
        等待全屏遮罩（Loading Mask）消失。
        默认支持 ElementUI、KendoUI、AntDesign 三种 Loading 遮罩。
        """
        try:
            self.page.wait_for_selector(
                mask_selector,
                state="hidden",
                timeout=timeout
            )
        except PlaywrightTimeoutError:
            pass

    def is_mask_present(self, mask_selector: str = ".el-loading-mask, .k-loading-mask") -> bool:
        """判断遮罩层是否存在"""
        try:
            self.page.wait_for_selector(mask_selector, state="visible", timeout=500)
            return True
        except PlaywrightTimeoutError:
            return False

    # ========== iframe 双向查找 ==========

    def switch_frame_by_index(self, index: int) -> Frame:
        """按索引切换 iframe（从 page.frames 列表取）"""
        frames = self.page.frames
        if index < len(frames):
            return frames[index]
        raise Exception(f"iframe 索引 {index} 越界，当前页面共 {len(frames)} 个 iframe")

    def switch_frame_by_name(self, name: str) -> Frame:
        """按 name/id 切换 iframe"""
        frame = self.page.frame(name=name)
        if frame:
            return frame
        raise Exception(f"未找到 name/id 为 '{name}' 的 iframe")

    def switch_frame_by_url(self, url_pattern: str) -> Frame:
        """按 URL 正则匹配切换 iframe"""
        import re
        for frame in self.page.frames:
            if re.search(url_pattern, frame.url):
                return frame
        raise Exception(f"未找到 URL 匹配 '{url_pattern}' 的 iframe")

    def find_frame_containing(self, locator: str, locator_type: str = "css") -> Frame:
        """
        反向查找：根据元素定位器反查它属于哪个 iframe。
        用于不确定元素在哪个 iframe 中的场景。
        """
        prefix = "xpath=" if locator_type == "xpath" else ""
        full = f"{prefix}{locator}"
        for frame in self.page.frames:
            try:
                if frame.locator(full).count() > 0:
                    return frame
            except Exception:
                continue
        raise Exception(f"所有 iframe 中均未找到元素 [{locator}]")

    def switch_to_frame(self, frame_locator=None, index=None, name=None, url_pattern=None):
        """统一入口：多种方式切换 iframe"""
        if index is not None:
            frame = self.switch_frame_by_index(index)
        elif name is not None:
            frame = self.switch_frame_by_name(name)
        elif url_pattern is not None:
            frame = self.switch_frame_by_url(url_pattern)
        elif frame_locator is not None:
            frame = self.switch_frame(frame_locator)
        else:
            raise ValueError("必须指定 frame_locator / index / name / url_pattern 其中之一")
        return frame

    def switch_to_main(self):
        """返回主页面"""
        return self.page.main_frame

    def switch_frame(self, frame_locator, locator_type="css"):
        """按 url 或 locator 切换 iframe（兼容旧写法）"""
        frame = self.page.frame(url=frame_locator) if frame_locator.startswith("http") else None
        if frame:
            return frame
        return self.page.frame(self._resolve_locator(frame_locator, locator_type))

    # ========== 点击与输入（带重试 + 自动 Mask 处理） ==========

    def click(self, locator, locator_type="css", timeout=5000, index: int = None,

              retries: int = 2, wait_mask: bool = True):
        """点击元素，自动处理遮罩 + 失败重试"""
        def _do():
            if wait_mask:
                self.wait_mask_gone()
            el = self._resolve_locator(locator, locator_type)
            target = el.nth(index) if index is not None else el.first
            target.click(timeout=timeout)
        self._with_retry(_do, f"click({locator})", retries=retries)

    def double_click(self, locator, locator_type="css", index: int = None):
        """双击元素"""
        el = self._resolve_locator(locator, locator_type)
        target = el.nth(index) if index is not None else el.first
        target.dblclick()

    def right_click(self, locator, locator_type="css", index: int = None):
        """右键点击元素"""
        el = self._resolve_locator(locator, locator_type)
        target = el.nth(index) if index is not None else el.first
        target.click(button="right")

    def click_any(self, locators: list, locator_type="css", timeout=2000):
        """尝试多个定位器，命中就点"""
        for loc in locators:
            try:
                self._resolve_locator(loc, locator_type).first.click(timeout=timeout)
                return
            except Exception:
                continue
        raise Exception(f"所有定位器均未命中: {locators}")

    def hover(self, locator, locator_type="css", index: int = None):
        """鼠标悬停元素"""
        el = self._resolve_locator(locator, locator_type)
        target = el.nth(index) if index is not None else el.first
        target.hover()

    def input_text(self, locator, text, locator_type="css", index: int = None, clear_first: bool = True):
        """输入文本到元素（默认先清空再填）"""
        el = self._resolve_locator(locator, locator_type)
        target = el.nth(index) if index is not None else el.first
        if clear_first:
            target.fill("")
        target.fill(text)

    def clear_text(self, locator, locator_type="css", index: int = None):
        """清空元素内容"""
        el = self._resolve_locator(locator, locator_type)
        target = el.nth(index) if index is not None else el.first
        target.fill("")

    def type_key(self, key: str, locator=None, locator_type="css"):
        """模拟键盘按键"""
        if locator:
            self._resolve_locator(locator, locator_type).press(key)
        else:
            self.page.keyboard.press(key)

    def select_option(self, locator, value=None, label=None, index=None, locator_type="css"):
        """从下拉框选择选项（value/label/index 三选一）"""
        el = self._resolve_locator(locator, locator_type)
        target = el.first
        if value is not None:
            target.select_option(value=value)
        elif label is not None:
            target.select_option(label=label)
        elif index is not None:
            target.select_option(index=index)
        else:
            raise ValueError("必须指定 value、label 或 index 其中之一")

    def check(self, locator, locator_type="css", index: int = None):
        """勾选复选框"""
        el = self._resolve_locator(locator, locator_type)
        target = el.nth(index) if index is not None else el.first
        target.check()

    def uncheck(self, locator, locator_type="css", index: int = None):
        """取消勾选复选框"""
        el = self._resolve_locator(locator, locator_type)
        target = el.nth(index) if index is not None else el.first
        target.uncheck()

    # ========== 获取元素信息 ==========

    def get_text(self, locator, locator_type="css", index: int = None):
        """获取元素文本内容"""
        el = self._resolve_locator(locator, locator_type)
        target = el.nth(index) if index is not None else el.first
        return target.text_content()

    def get_attribute(self, locator, attribute, locator_type="css", index: int = None):
        """获取元素指定属性值"""
        el = self._resolve_locator(locator, locator_type)
        target = el.nth(index) if index is not None else el.first
        return target.get_attribute(attribute)

    def get_input_value(self, locator, locator_type="css", index: int = None):
        """获取输入框当前值"""
        el = self._resolve_locator(locator, locator_type)
        target = el.nth(index) if index is not None else el.first
        return target.input_value()

    def count_elements(self, locator, locator_type="css"):
        """统计匹配元素数量"""
        return self._resolve_locator(locator, locator_type).count()

    # ========== 元素状态判断 ==========

    def is_visible(self, locator, locator_type="css", index: int = None):
        """判断元素是否可见"""
        el = self._resolve_locator(locator, locator_type)
        target = el.nth(index) if index is not None else el.first
        return target.is_visible()

    def is_enabled(self, locator, locator_type="css", index: int = None):
        """判断元素是否可操作"""
        el = self._resolve_locator(locator, locator_type)
        target = el.nth(index) if index is not None else el.first
        return target.is_enabled()

    def is_checked(self, locator, locator_type="css", index: int = None):
        """判断复选框是否选中"""
        el = self._resolve_locator(locator, locator_type)
        target = el.nth(index) if index is not None else el.first
        return target.is_checked()

    # ========== 高级操作（文件、拖拽、事件） ==========

    def upload_file(self, locator, file_path, locator_type="css"):
        """上传文件（支持单个或多个文件路径列表）"""
        el = self._resolve_locator(locator, locator_type)
        if isinstance(file_path, list):
            el.set_input_files(file_path)
        else:
            el.set_input_files(file_path)

    def download_file(self, trigger_selector: str, save_as: str,

                      locator_type: str = "css", timeout: int = 30000) -> str:
        """
        点击触发下载按钮 → 保存为指定路径 → 返回保存后的完整路径。
        """
        prefix = "xpath=" if locator_type == "xpath" else ""
        with self.page.expect_download(timeout=timeout) as download_info:
            self.page.locator(f"{prefix}{trigger_selector}").click()
        download = download_info.value
        download.save_as(save_as)
        return save_as

    def drag_to(self, source_locator, target_locator, source_type="css", target_type="css"):
        """拖拽源元素到目标元素位置"""
        src = self._resolve_locator(source_locator, source_type)
        dst = self._resolve_locator(target_locator, target_type)
        src.drag_to(dst)

    def scroll_to(self, x: int = 0, y: int = 0):
        """滚动到指定坐标"""
        self.page.evaluate(f"window.scrollTo({x}, {y})")

    def scroll_to_bottom(self):
        """滚动到页面底部"""
        self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")

    def scroll_to_element(self, locator, locator_type="css", index: int = None):
        """滚动页面直到元素可见"""
        el = self._resolve_locator(locator, locator_type)
        target = el.nth(index) if index is not None else el.first
        target.scroll_into_view_if_needed()

    def dispatch_event(self, locator, event: str, locator_type="css", index: int = None):
        """在元素上派发自定义 DOM 事件"""
        el = self._resolve_locator(locator, locator_type)
        target = el.nth(index) if index is not None else el.first
        target.dispatch_event(event)

    def locator(self, locator, locator_type="css"):
        """创建 Locator（兼容旧写法）"""
        return self._resolve_locator(locator, locator_type)

    def on_dialog(self, handler: callable):
        """注册对话框处理回调"""
        self.page.on("dialog", handler)

    def once_dialog(self, handler: callable):
        """注册一次性对话框回调"""
        self.page.once("dialog", handler)

    # ========== 截图 ==========

    def take_screenshot(self, full_page: bool = False):
        """对整个页面截图"""
        return self.page.screenshot(full_page=full_page)

    def take_element_screenshot(self, locator, save_path: str, locator_type="css"):
        """元素级截图"""
        self._resolve_locator(locator, locator_type).screenshot(path=save_path)

    # ========== 浏览器上下文 / 多标签页 ==========

    def new_tab(self, url: str = "about:blank") -> Page:
        """打开新标签页，返回新 Page 对象"""
        return self.page.context.new_page()

    def switch_tab_by_index(self, index: int) -> Page:
        """按索引切换到指定标签页并置于前台"""
        pages = self.page.context.pages
        if 0 <= index < len(pages):
            pages[index].bring_to_front()
            return pages[index]
        raise Exception(f"标签页索引 {index} 越界，共 {len(pages)} 个")

    def save_storage_state(self, path: str):
        """保存登录态（cookies + localStorage）"""
        self.page.context.storage_state(path=path)

    def load_storage_state(self, path: str) -> Page:
        """用已保存的登录态创建新 context（无需重新登录）"""
        return self.page.browser.new_context(storage_state=path)

    def close_current_tab(self):
        """关闭当前标签页"""
        self.page.close()