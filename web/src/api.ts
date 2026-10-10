export type Mode = 'auto' | 'documents' | 'search'
export type Source = { id: string; title: string; url: string }
export type ChatReply = {
  answer: string
  route: string
  verified: boolean
  sources: Source[]
  saved: boolean
  conversation_id: string
}
export type Message = { role: 'user' | 'assistant'; content: string; created_at?: string; route?: string; verified?: boolean; sources?: Source[] }
export type Document = { id: number; title: string; chunks: number }
export type Conversation = { id: string; messages: number; updated_at: string | null }

async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api${path}`, options)
  const type = response.headers.get('content-type') ?? ''
  const payload: unknown = type.includes('application/json')
    ? await response.json()
    : await response.text()
  if (!response.ok) {
    const detail = typeof payload === 'object' && payload !== null && 'detail' in payload
      ? (payload as { detail: unknown }).detail : payload
    throw new Error(typeof detail === 'string' ? detail : `Request failed: HTTP ${response.status}`)
  }
  return payload as T
}

export const service = {
  health: () => api<{ status: string }>('/health'),
  documents: () => api<Document[]>('/documents'),
  upload: (filename: string, content: string) => api<Document>('/documents', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ filename, content }),
  }),
  removeDocument: (id: number) => api<{ deleted: boolean }>(`/documents/${id}`, { method: 'DELETE' }),
  search: (query: string) => api<{ title: string; snippet: string }[]>(`/search?q=${encodeURIComponent(query)}`),
  conversations: () => api<Conversation[]>('/conversations'),
  history: (id: string) => api<Message[]>(`/conversations/${encodeURIComponent(id)}`),
  forget: (id: string) => api<{ deleted: boolean }>(`/conversations/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  chat: (args: { message: string; conversation_id: string; mode: Mode; allow_cloud: boolean; save_history: boolean }) =>
    api<ChatReply>('/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(args) }),
}
