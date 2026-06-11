<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { Brain, Database, Download, History, RefreshCw, Search, SlidersHorizontal, Trophy } from 'lucide-vue-next'
import {
  fetchExpertSignals,
  generateTop,
  getDraws,
  getExpertConsensus,
  getLatestOpeningNumber,
  getStats,
  importExpertSignal,
  syncDraws,
} from './api'

const stats = ref({ total_draws: 0, latest_issue: null, latest_date: null })
const draws = ref([])
const candidates = ref([])
const expertConsensus = ref(null)
const latestOpening = ref(null)
const loading = ref('')
const error = ref('')
const lastSync = ref(null)
const lastExpertFetch = ref(null)
const expertText = ref('')
const numberText = reactive({
  exclude_numbers: '',
  exclude_blues: '',
  dan_numbers: '',
  kill_tails: '',
  soft_red_dan: '',
  soft_red_kill: '',
  soft_blue_dan: '',
  soft_blue_kill: '',
  soft_kill_tails: '',
})

const form = reactive({
  top_n: 50,
  candidate_pool: 50000,
  filters: {
    exclude_history: true,
    exclude_latest_opening: true,
    history_overlap: 'similar5',
    exclude_numbers: [],
    exclude_blues: [],
    dan_numbers: [],
    kill_tails: [],
    reject_three_consecutive: true,
    reject_four_consecutive: true,
    allow_two_consecutive: true,
    sum_min: 70,
    sum_max: 130,
    span_min: 14,
    span_max: 32,
    ac_min: 7,
    ac_max: 12,
    odd_even: 'any',
    max_red_repeat: 2,
    reject_blue_repeat: false,
    use_expert_signals: true,
    expert_weight: 6,
    soft_red_dan: [],
    soft_red_kill: [],
    soft_blue_dan: [],
    soft_blue_kill: [],
    soft_kill_tails: [],
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

const parseNumberList = (text, min, max) =>
  String(text || '')
    .split(/[\s,，、;；]+/)
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => Number(item))
    .filter((item) => Number.isInteger(item) && item >= min && item <= max)

const refresh = async () => {
  const [statsPayload, drawsPayload, consensusPayload, openingPayload] = await Promise.all([
    getStats(),
    getDraws(),
    getExpertConsensus(),
    getLatestOpeningNumber().catch(() => null),
  ])
  stats.value = statsPayload
  draws.value = drawsPayload
  expertConsensus.value = consensusPayload
  latestOpening.value = openingPayload
}

const handleSync = () =>
  withLoading('正在同步最新开奖', async () => {
    lastSync.value = await syncDraws({ source: 'latest' })
    await refresh()
  })

const handleGenerate = () =>
  withLoading('正在生成 Top50', async () => {
    form.filters.exclude_numbers = parseNumberList(numberText.exclude_numbers, 1, 33)
    form.filters.exclude_blues = parseNumberList(numberText.exclude_blues, 1, 16)
    form.filters.dan_numbers = parseNumberList(numberText.dan_numbers, 1, 33)
    form.filters.kill_tails = parseNumberList(numberText.kill_tails, 0, 9)
    form.filters.soft_red_dan = parseNumberList(numberText.soft_red_dan, 1, 33)
    form.filters.soft_red_kill = parseNumberList(numberText.soft_red_kill, 1, 33)
    form.filters.soft_blue_dan = parseNumberList(numberText.soft_blue_dan, 1, 16)
    form.filters.soft_blue_kill = parseNumberList(numberText.soft_blue_kill, 1, 16)
    form.filters.soft_kill_tails = parseNumberList(numberText.soft_kill_tails, 0, 9)
    candidates.value = await generateTop(form)
  })

const handleFetchExperts = () =>
  withLoading('正在抓取外部专家信号', async () => {
    lastExpertFetch.value = await fetchExpertSignals()
    expertConsensus.value = await getExpertConsensus()
  })

const handleImportExpertText = () =>
  withLoading('正在解析粘贴的专家分析', async () => {
    await importExpertSignal({ source: 'manual', text: expertText.value, weight: 1.2 })
    expertText.value = ''
    expertConsensus.value = await getExpertConsensus()
  })

const formatConsensus = (items, pad = 2) =>
  (items || [])
    .slice(0, 8)
    .map((item) => `${String(item.number).padStart(pad, '0')}(${item.weight})`)
    .join('、') || '无'

const formatOpening = (opening) => {
  if (!opening) return '暂未获取'
  const reds = opening.reds.map((item) => String(item).padStart(2, '0')).join(' ')
  return `${opening.issue}期 ${reds} + ${String(opening.blue).padStart(2, '0')}`
}

onMounted(() => {
  withLoading('正在读取系统状态', refresh)
})
</script>

<template>
  <main class="shell">
    <section class="topbar">
      <div>
        <p class="eyebrow">SSQ V7.0</p>
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
      <button :disabled="!!loading" @click="handleFetchExperts">
        <Search :size="18" />
        <span>抓取外部信号</span>
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
    <p v-if="lastExpertFetch" class="message success">
      外部信号 {{ lastExpertFetch.length }} 条，红胆共识：
      {{ formatConsensus(expertConsensus?.red_dan) }}
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
        <div class="field-row">
          <label>历史排除</label>
          <select v-model="form.filters.history_overlap">
            <option value="similar5">排除历史5+重合</option>
            <option value="exact">排除历史6红相同</option>
            <option value="none">不限制</option>
          </select>
        </div>
        <div class="text-field">
          <label>排除红球</label>
          <input v-model="numberText.exclude_numbers" placeholder="如：02 11 25" />
        </div>
        <div class="text-field">
          <label>胆码</label>
          <input v-model="numberText.dan_numbers" placeholder="如：05 12" />
        </div>
        <div class="text-field">
          <label>杀尾号</label>
          <input v-model="numberText.kill_tails" placeholder="如：0 4 9" />
        </div>
        <div class="text-field">
          <label>排除蓝球</label>
          <input v-model="numberText.exclude_blues" placeholder="如：02 13" />
        </div>
        <div class="range-row">
          <label>和值</label>
          <input v-model.number="form.filters.sum_min" type="number" />
          <span>至</span>
          <input v-model.number="form.filters.sum_max" type="number" />
        </div>
        <div class="range-row">
          <label>跨度</label>
          <input v-model.number="form.filters.span_min" type="number" />
          <span>至</span>
          <input v-model.number="form.filters.span_max" type="number" />
        </div>
        <div class="range-row">
          <label>AC值</label>
          <input v-model.number="form.filters.ac_min" type="number" />
          <span>至</span>
          <input v-model.number="form.filters.ac_max" type="number" />
        </div>
        <div class="field-row">
          <label>奇偶结构</label>
          <select v-model="form.filters.odd_even">
            <option value="any">不限</option>
            <option value="3:3">3:3</option>
            <option value="4:2">4:2</option>
            <option value="2:4">2:4</option>
            <option value="5:1">5:1</option>
            <option value="1:5">1:5</option>
          </select>
        </div>
        <div class="field-row">
          <label>最大重红</label>
          <input v-model.number="form.filters.max_red_repeat" type="number" min="0" max="6" />
        </div>
        <label class="check"><input v-model="form.filters.exclude_history" type="checkbox" />排除历史号码</label>
        <label class="check"><input v-model="form.filters.exclude_latest_opening" type="checkbox" />排除最新北京开机号</label>
        <p class="hint">当前开机号：{{ formatOpening(latestOpening) }}</p>
        <label class="check"><input v-model="form.filters.allow_two_consecutive" type="checkbox" />允许2连号</label>
        <label class="check"><input v-model="form.filters.reject_three_consecutive" type="checkbox" />排除3连号</label>
        <label class="check"><input v-model="form.filters.reject_four_consecutive" type="checkbox" />排除4连号</label>
        <label class="check"><input v-model="form.filters.reject_blue_repeat" type="checkbox" />排除重蓝</label>

        <div class="panel-title compact-title">
          <Search :size="18" />
          <h2>外部信号融合</h2>
        </div>
        <label class="check"><input v-model="form.filters.use_expert_signals" type="checkbox" />启用抓取信号</label>
        <div class="field-row">
          <label>信号权重</label>
          <input v-model.number="form.filters.expert_weight" type="number" min="0" max="20" step="0.5" />
        </div>
        <div class="text-field">
          <label>软红胆</label>
          <input v-model="numberText.soft_red_dan" placeholder="加分，不硬定胆" />
        </div>
        <div class="text-field">
          <label>软杀红</label>
          <input v-model="numberText.soft_red_kill" placeholder="降分，不硬排除" />
        </div>
        <div class="text-field">
          <label>软蓝胆</label>
          <input v-model="numberText.soft_blue_dan" placeholder="如：03 09" />
        </div>
        <div class="text-field">
          <label>软杀蓝</label>
          <input v-model="numberText.soft_blue_kill" placeholder="如：01 16" />
        </div>
        <div class="text-field">
          <label>软杀尾</label>
          <input v-model="numberText.soft_kill_tails" placeholder="如：0 4 9" />
        </div>
        <div class="text-field">
          <label>粘贴专家分析</label>
          <textarea v-model="expertText" placeholder="粘贴包含胆码、杀号、蓝球、杀尾等文字"></textarea>
          <button class="inline-action" :disabled="!!loading || expertText.trim().length < 2" @click="handleImportExpertText">
            解析入库
          </button>
        </div>
        <div class="signal-box" v-if="expertConsensus">
          <p><strong>红胆</strong>{{ formatConsensus(expertConsensus.red_dan) }}</p>
          <p><strong>杀红</strong>{{ formatConsensus(expertConsensus.red_kill) }}</p>
          <p><strong>蓝胆</strong>{{ formatConsensus(expertConsensus.blue_dan) }}</p>
          <p><strong>杀蓝</strong>{{ formatConsensus(expertConsensus.blue_kill) }}</p>
          <p><strong>杀尾</strong>{{ formatConsensus(expertConsensus.kill_tails, 1) }}</p>
        </div>
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
                <th>外部</th>
                <th>和值</th>
                <th>跨度</th>
                <th>奇偶</th>
                <th>三区</th>
                <th>AC</th>
                <th>重红</th>
                <th>连号</th>
                <th>同尾</th>
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
                <td :class="['expert-score', item.expert_score > 0 ? 'positive' : item.expert_score < 0 ? 'negative' : '']">
                  {{ item.expert_score }}
                </td>
                <td>{{ item.sum_value }}</td>
                <td>{{ item.span }}</td>
                <td>{{ item.odd_even }}</td>
                <td>{{ item.zone_ratio }}</td>
                <td>{{ item.ac_value }}</td>
                <td>{{ item.red_repeat }}</td>
                <td>{{ item.consecutive }}</td>
                <td>{{ item.same_tail }}</td>
                <td class="reasons">{{ item.reasons.join(' / ') }}</td>
              </tr>
              <tr v-if="!candidates.length">
                <td colspan="14" class="empty">点击 AI评分 Top50 生成号码</td>
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
