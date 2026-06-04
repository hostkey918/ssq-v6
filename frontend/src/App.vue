<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Brain, Database, Download, History, RefreshCw, SlidersHorizontal, Trophy } from 'lucide-vue-next'
import { generateTop, getDraws, getStats, syncDraws } from './api'

const stats = ref({ total_draws: 0, latest_issue: null, latest_date: null })
const draws = ref([])
const candidates = ref([])
const loading = ref('')
const error = ref('')
const lastSync = ref(null)

const form = reactive({
  top_n: 50,
  candidate_pool: 20000,
  filters: {
    exclude_history: true,
    reject_three_consecutive: true,
    reject_four_consecutive: true,
    sum_min: 70,
    sum_max: 130,
    ac_min: 7,
    ac_max: 12,
    max_red_repeat: 2,
    reject_blue_repeat: false,
  },
})

const statusText = computed(() => {
  if (loading.value) return loading.value
  if (stats.value.latest_issue) return `最新 ${stats.value.latest_issue}，共 ${stats.value.total_draws} 期`
  return '等待同步历史开奖'
})

const withLoading = async (text, fn) => {
  loading.value = text
  error.value = ''
  try {
    await fn()
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = ''
  }
}

const refresh = async () => {
  const [statsPayload, drawsPayload] = await Promise.all([getStats(), getDraws()])
  stats.value = statsPayload
  draws.value = drawsPayload
}

const handleSync = () =>
  withLoading('正在同步开奖数据', async () => {
    lastSync.value = await syncDraws()
    await refresh()
  })

const handleGenerate = () =>
  withLoading('正在生成 Top50', async () => {
    candidates.value = await generateTop(form)
  })

onMounted(() => {
  withLoading('正在读取系统状态', refresh)
})
</script>

<template>
  <main class="shell">
    <section class="topbar">
      <div>
        <p class="eyebrow">SSQ V6.0</p>
        <h1>双色球智能筛选后台</h1>
      </div>
      <div class="status-pill">
        <Database :size="18" />
        <span>{{ statusText }}</span>
      </div>
    </section>

    <section class="actions">
      <button class="primary" :disabled="!!loading" @click="handleSync">
        <RefreshCw :size="18" />
        <span>同步历史开奖</span>
      </button>
      <button :disabled="!!loading" @click="handleGenerate">
        <Brain :size="18" />
        <span>AI评分 Top50</span>
      </button>
      <button :disabled="!!loading" @click="refresh">
        <Download :size="18" />
        <span>刷新数据</span>
      </button>
    </section>

    <p v-if="error" class="message error">{{ error }}</p>
    <p v-if="lastSync" class="message success">
      抓取 {{ lastSync.fetched }} 条，新增 {{ lastSync.inserted }} 条，更新 {{ lastSync.updated }} 条
    </p>

    <section class="grid">
      <aside class="panel controls">
        <div class="panel-title">
          <SlidersHorizontal :size="18" />
          <h2>过滤参数</h2>
        </div>

        <div class="field-row">
          <label>输出数量</label>
          <input v-model.number="form.top_n" type="number" min="1" max="200" />
        </div>
        <div class="field-row">
          <label>候选池</label>
          <input v-model.number="form.candidate_pool" type="number" min="100" max="200000" />
        </div>
        <div class="range-row">
          <label>和值</label>
          <input v-model.number="form.filters.sum_min" type="number" />
          <span>至</span>
          <input v-model.number="form.filters.sum_max" type="number" />
        </div>
        <div class="range-row">
          <label>AC值</label>
          <input v-model.number="form.filters.ac_min" type="number" />
          <span>至</span>
          <input v-model.number="form.filters.ac_max" type="number" />
        </div>
        <div class="field-row">
          <label>最大重红</label>
          <input v-model.number="form.filters.max_red_repeat" type="number" min="0" max="6" />
        </div>
        <label class="check"><input v-model="form.filters.exclude_history" type="checkbox" />排除历史号码</label>
        <label class="check"><input v-model="form.filters.reject_three_consecutive" type="checkbox" />排除3连号</label>
        <label class="check"><input v-model="form.filters.reject_four_consecutive" type="checkbox" />排除4连号</label>
        <label class="check"><input v-model="form.filters.reject_blue_repeat" type="checkbox" />排除重蓝</label>
      </aside>

      <section class="panel results">
        <div class="panel-title">
          <Trophy :size="18" />
          <h2>Top50号码</h2>
        </div>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>红球</th>
                <th>蓝球</th>
                <th>评分</th>
                <th>和值</th>
                <th>AC</th>
                <th>重红</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in candidates" :key="`${item.rank}-${item.reds.join('-')}-${item.blue}`">
                <td>{{ item.rank }}</td>
                <td>
                  <span v-for="n in item.reds" :key="n" class="ball red">{{ String(n).padStart(2, '0') }}</span>
                </td>
                <td><span class="ball blue">{{ String(item.blue).padStart(2, '0') }}</span></td>
                <td class="score">{{ item.score }}</td>
                <td>{{ item.sum_value }}</td>
                <td>{{ item.ac_value }}</td>
                <td>{{ item.red_repeat }}</td>
                <td class="reasons">{{ item.reasons.join(' / ') }}</td>
              </tr>
              <tr v-if="!candidates.length">
                <td colspan="8" class="empty">点击 AI评分 Top50 生成号码</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </section>

    <section class="panel history">
      <div class="panel-title">
        <History :size="18" />
        <h2>最近开奖</h2>
      </div>
      <div class="draw-list">
        <div v-for="draw in draws" :key="draw.issue" class="draw-item">
          <strong>{{ draw.issue }}</strong>
          <span class="date">{{ draw.draw_date || '-' }}</span>
          <span class="numbers">
            <span v-for="n in draw.reds" :key="n" class="ball red small">{{ String(n).padStart(2, '0') }}</span>
            <span class="ball blue small">{{ String(draw.blue).padStart(2, '0') }}</span>
          </span>
        </div>
      </div>
    </section>
  </main>
</template>
