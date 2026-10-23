export type HealthResponse = {
  status: 'ok';
  service: 'dota-hub-api';
};

function isHealthResponse(value: unknown): value is HealthResponse {
  return typeof value === 'object' && value !== null
    && 'status' in value && value.status === 'ok'
    && 'service' in value && value.service === 'dota-hub-api';
}

export async function getHealth(signal: AbortSignal): Promise<HealthResponse> {
  const controller = new AbortController();
  const cancel = () => controller.abort();
  signal.addEventListener('abort', cancel, { once: true });
  if (signal.aborted) cancel();
  const timeout = window.setTimeout(cancel, 5000);
  try {
    const response = await fetch('/api/v1/health', {
      signal: controller.signal,
      cache: 'no-store',
      headers: { Accept: 'application/json' },
    });
    if (!response.ok) throw new Error('Сервер недоступен');
    const data: unknown = await response.json();
    if (!isHealthResponse(data)) throw new Error('Некорректный ответ сервера');
    return data;
  } finally {
    window.clearTimeout(timeout);
    signal.removeEventListener('abort', cancel);
  }
}
