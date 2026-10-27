const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8001').replace(/\/$/, '')

async function responseError(response: Response) {
  const body = await response.text()
  if (!body) return `Request failed (${response.status})`
  try {
    const parsed = JSON.parse(body)
    return parsed.detail || parsed.message || body
  } catch {
    return body
  }
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
      ...options,
    })
    if (!response.ok) {
      throw new Error(await responseError(response))
    }
    if (response.status === 204) return undefined as T
    return response.json() as Promise<T>
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error('Unable to reach the GenPlan backend. Confirm the FastAPI server is running on http://127.0.0.1:8001 and that the app is using the correct API URL.')
    }
    throw error
  }
}

export async function uploadDocument(projectId: number, file: File) {
  const formData = new FormData()
  formData.append('file', file)

  try {
    const response = await fetch(`${API_BASE}/api/projects/${projectId}/documents`, {
      method: 'POST',
      body: formData,
    })

    if (!response.ok) {
      throw new Error(await responseError(response))
    }

    return response.json()
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error('The document upload could not reach the GenPlan backend. Check the FastAPI server and the API base URL before trying again.')
    }
    throw error
  }
}

export async function previewDocument(file: File) {
  const formData = new FormData()
  formData.append('file', file)

  try {
    const response = await fetch(`${API_BASE}/api/documents/preview`, {
      method: 'POST',
      body: formData,
    })
    if (!response.ok) throw new Error(await responseError(response))
    return response.json() as Promise<{ filename: string; stories: import('../types').Story[]; preview: string }>
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error('The document preview could not reach the GenPlan backend. Check the FastAPI server and API base URL.')
    }
    throw error
  }
}
