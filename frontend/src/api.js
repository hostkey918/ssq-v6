const api = async (path, options = {}) => {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  if (!response.ok) {
    let message = response.statusText
    try {
      const payload = await response.json()
      message = payload.detail || message
    } catch {
      // Keep the HTTP status text.
    }
    throw new Error(message)
  }
  return response.json()
}

export const getStats = () => api('/api/stats')
export const getDraws = () => api('/api/draws?limit=30')
export const syncDraws = (params = {}) => {
  const query = new URLSearchParams(params).toString()
  return api(`/api/sync${query ? `?${query}` : ''}`, { method: 'POST' })
}
export const generateTop = (payload) =>
  api('/api/generate', { method: 'POST', body: JSON.stringify(payload) })
export const fetchExpertSignals = (payload = {}) =>
  api('/api/expert-signals/fetch', { method: 'POST', body: JSON.stringify(payload) })
export const importExpertSignal = (payload) =>
  api('/api/expert-signals/import', { method: 'POST', body: JSON.stringify(payload) })
export const getExpertConsensus = () => api('/api/expert-signals/consensus')
