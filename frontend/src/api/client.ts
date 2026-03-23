const BASE = '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

// ── Types ──────────────────────────────────────────────────────

export interface HealthData {
  status: string
  timestamp: string
  mongodb: string
  collections: { raw: number; clean: number; ner: number; quarantine: number }
}

export interface StatsData {
  raw: number
  clean: number
  ner: number
  quarantine: number
  raw_by_rank: Record<string, number>
  jobs_tracked: number
}

export interface Article {
  url: string
  title: string
  feed: string
  pub?: string
  lang?: string
  entity_count?: number
  doc_stats?: { char_count: number; token_count: number; sentence_count: number }
  cleaning_flags?: Record<string, boolean>
  signal_counts?: Record<string, number>
}

export interface NEREntity {
  text: string
  label: 'PER' | 'ORG' | 'LOC' | 'MISC'
  start: number
  end: number
}

export interface NERArticleDetail {
  clean: Article & {
    body: string
    clean_text: string
    preprocessed_text: string
    money_tags: string[]
    percent_tags: string[]
    datetime_tags: string[]
  }
  ner: (Article & { entities: NEREntity[]; body: string }) | null
}

export interface TFIDFTerm {
  term: string
  score: number
  is_ner: boolean
}

export interface TFIDFComparison {
  sample_size: number
  clean_top_terms: TFIDFTerm[]
  ner_top_terms: TFIDFTerm[]
  entity_distribution: Record<string, number>
  clean_vocab_size: number
  ner_vocab_size: number
  ner_token_ratio: number
}

export interface Job {
  job_id: string
  job_name: string
  status: 'queued' | 'running' | 'success' | 'failed'
  started_at: string
  finished_at?: string
  result?: Record<string, unknown>
}

// ── API calls ──────────────────────────────────────────────────

export const api = {
  health:  () => get<HealthData>('/health'),
  stats:   () => get<StatsData>('/stats'),

  articles: (params: { skip?: number; limit?: number; collection?: 'clean' | 'ner'; search?: string }) => {
    const q = new URLSearchParams()
    if (params.skip   !== undefined) q.set('skip',   String(params.skip))
    if (params.limit  !== undefined) q.set('limit',  String(params.limit))
    if (params.collection)           q.set('collection', params.collection)
    if (params.search)               q.set('search', params.search)
    return get<{ items: Article[]; total: number; skip: number; limit: number }>(`/articles?${q}`)
  },

  nerArticle: (url: string) => {
    const b64 = btoa(url).replace(/=/g, '')
    return get<NERArticleDetail>(`/articles/ner/${b64}`)
  },

  tfidf: (sampleSize = 200) =>
    get<TFIDFComparison>(`/compare/tfidf?sample_size=${sampleSize}`),

  triggerJob: (job_name: string, dry_run = false) =>
    post<{ job_id: string; status: string }>('/jobs/trigger', { job_name, dry_run }),

  jobs:    () => get<{ jobs: Job[] }>('/jobs'),
  jobById: (id: string) => get<Job>(`/jobs/${id}`),
}
