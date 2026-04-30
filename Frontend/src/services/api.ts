type JsonValue = Record<string, unknown>;

function getStoredToken() {
  try {
    const serializedState = localStorage.getItem('authState');
    if (!serializedState) {
      return null;
    }

    const parsed = JSON.parse(serializedState);
    return parsed?.token ?? null;
  } catch {
    return null;
  }
}

export function getAuthHeaders(extraHeaders: HeadersInit = {}) {
  const token = getStoredToken();
  const headers = new Headers(extraHeaders);

  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  return headers;
}

export async function apiJsonFetch(url: string, init: RequestInit = {}) {
  const response = await fetch(url, {
    ...init,
    headers: getAuthHeaders(init.headers),
  });

  const contentType = response.headers.get('content-type') ?? '';
  const isJson = contentType.includes('application/json');
  const payload = isJson ? await response.json() : await response.text();

  if (!response.ok) {
    if (isJson && payload && typeof payload === 'object' && 'error' in (payload as JsonValue)) {
      throw new Error(String((payload as JsonValue).error));
    }

    if (typeof payload === 'string' && payload.trim()) {
      throw new Error(payload);
    }

    throw new Error('Request failed');
  }

  return payload;
}
