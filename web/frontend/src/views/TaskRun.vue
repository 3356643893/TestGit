<!--
  测试任务执行页面
  - 点击按钮提交任务
  - 自动轮询查询任务状态
  - 任务完成后在 iframe 展示报告
  - 底部展示历史任务列表
-->
<template>
  <div class="task-run-page">
    <h1>🚀 自动化测试任务执行</h1>

    <!-- ── 操作区 ──────────────── -->
    <div class="action-bar">
      <button @click="runTask('full')" :disabled="isRunning">
        全量测试
      </button>
      <button @click="runTask('smoke')" :disabled="isRunning" class="secondary">
        冒烟测试
      </button>
      <button @click="refreshHistory" class="ghost">
        🔄 刷新历史
      </button>
    </div>

    <!-- ── 任务状态区 ───────────── -->
    <div v-if="currentTask" class="status-panel" :class="statusClass">
      <div><strong>任务 ID：</strong>{{ currentTask.task_id }}</div>
      <div><strong>任务类型：</strong>{{ currentTask.task_type }}</div>
      <div><strong>当前状态：</strong>{{ statusText }}</div>
      <div v-if="currentTask.start_time">
        <strong>开始时间：</strong>{{ currentTask.start_time }}
      </div>
      <div v-if="currentTask.end_time">
        <strong>结束时间：</strong>{{ currentTask.end_time }}
      </div>
      <div v-if="currentTask.stdout_tail" class="log-tail">
        <strong>执行日志：</strong>
        <pre>{{ currentTask.stdout_tail }}</pre>
      </div>
    </div>

    <!-- ── 报告区 ──────────────── -->
    <div v-if="reportUrl" class="report-area">
      <h3>📊 测试报告</h3>
      <iframe :src="reportUrl" width="100%" height="800px"></iframe>
    </div>

    <!-- ── 历史任务区 ───────────── -->
    <div class="history-panel">
      <h3>📜 历史任务</h3>
      <table v-if="history.length > 0">
        <thead>
          <tr><th>报告名</th><th>创建时间</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="item in history" :key="item.report_id">
            <td>{{ item.report_id }}</td>
            <td>{{ item.mtime }}</td>
            <td><a :href="item.report_url" target="_blank">查看报告</a></td>
          </tr>
        </tbody>
      </table>
      <p v-else>暂无历史任务</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from "vue";
import axios from "axios";

// 后端基础地址（如果前后端分离部署，这里要改）
const API_BASE = "http://localhost:8000";

const isRunning = ref(false);
const currentTask = ref(null);
const reportUrl = ref("");
const history = ref([]);
const pollTimer = ref(null);

// ── 状态文字 + 样式类 ───────
const statusText = computed(() => {
  const map = {
    PENDING: "⏳ 排队中...",
    RUNNING: "⚙️ 执行中（测试可能需要几分钟）",
    SUCCESS: "✅ 全部通过",
    FAILED: "❌ 有失败用例",
    TIMEOUT: "⚠️ 任务超时"
  };
  return map[currentTask.value?.status] || currentTask.value?.status;
});

const statusClass = computed(() => ({
  "status-pending": currentTask.value?.status === "PENDING",
  "status-running": currentTask.value?.status === "RUNNING",
  "status-success": currentTask.value?.status === "SUCCESS",
  "status-failed":  currentTask.value?.status === "FAILED" ||
                    currentTask.value?.status === "TIMEOUT",
}));

// ── 提交测试任务 ─────────────
async function runTask(taskType) {
  if (isRunning.value) return;
  isRunning.value = true;
  reportUrl.value = "";

  try {
    const res = await axios.post(`${API_BASE}/api/task/submit?task_type=${taskType}`);
    currentTask.value = res.data.data;
    const taskId = currentTask.value.task_id;

    // 每 3 秒轮询一次状态
    pollTimer.value = setInterval(async () => {
      const statusRes = await axios.get(`${API_BASE}/api/task/status/${taskId}`);
      currentTask.value = statusRes.data.data;

      // 任务结束 → 显示报告
      if (["SUCCESS", "FAILED", "TIMEOUT"].includes(currentTask.value.status)) {
        clearInterval(pollTimer.value);
        reportUrl.value = `${API_BASE}/api/report/${taskId}`;
        isRunning.value = false;
        refreshHistory();  // 刷新历史列表
      }
    }, 3000);

  } catch (e) {
    alert("提交任务失败: " + e.message);
    isRunning.value = false;
  }
}

// ── 刷新历史任务 ────────────
async function refreshHistory() {
  try {
    const res = await axios.get(`${API_BASE}/api/task/history`);
    history.value = res.data.data || [];
  } catch (e) {
    console.error(e);
  }
}

// 页面加载时查一次历史
onMounted(refreshHistory);
</script>

<style scoped>
.task-run-page { max-width: 1200px; margin: 20px auto; padding: 20px; font-family: Arial, sans-serif; }
.action-bar button { padding: 10px 20px; margin-right: 10px; font-size: 16px; cursor: pointer; border: none; border-radius: 6px; }
.action-bar button:not(:disabled):hover { opacity: 0.85; }
button:disabled { opacity: 0.4; cursor: not-allowed; }
button.secondary { background: #ffa500; color: white; }
button.ghost { background: transparent; border: 1px solid #ccc; }
.status-panel { margin: 20px 0; padding: 15px; border-radius: 8px; background: #f5f5f5; }
.status-success { background: #d4edda; }
.status-failed  { background: #f8d7da; }
.status-running { background: #cce5ff; }
.log-tail pre { background: #222; color: #0f0; padding: 10px; max-height: 200px; overflow: auto; }
.report-area { margin: 30px 0; }
.history-panel { margin-top: 30px; }
.history-panel table { width: 100%; border-collapse: collapse; }
.history-panel th, .history-panel td { padding: 8px; border-bottom: 1px solid #eee; text-align: left; }
</style>