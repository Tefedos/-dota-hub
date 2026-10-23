export type User = {
  telegram_user_id: string;
  username: string | null;
  display_name: string | null;
  created_at: string;
  updated_at: string;
};

export type Session = { access_token: string; token_type: 'bearer'; expires_in: number; user: User };

export class SessionExpired extends Error {}

function isUser(value: unknown): value is User {
  return typeof value === 'object' && value !== null
    && 'telegram_user_id' in value && typeof value.telegram_user_id === 'string' && /^[1-9][0-9]{0,18}$/.test(value.telegram_user_id)
    && 'username' in value && (value.username === null || typeof value.username === 'string')
    && 'display_name' in value && (value.display_name === null || typeof value.display_name === 'string')
    && 'created_at' in value && typeof value.created_at === 'string'
    && 'updated_at' in value && typeof value.updated_at === 'string';
}

async function request(path: string, init: RequestInit, signal: AbortSignal): Promise<unknown> {
  const controller = new AbortController();
  const cancel = () => controller.abort();
  signal.addEventListener('abort', cancel, { once: true });
  if (signal.aborted) cancel();
  const timeout = window.setTimeout(cancel, 5000);
  try {
    const response = await fetch(`/api/v1/auth/${path}`, {
      ...init, signal: controller.signal, cache: 'no-store', credentials: 'omit', redirect: 'error',
    });
    if (response.status === 401 && path === 'me') throw new SessionExpired();
    if (!response.ok) throw new Error('Не удалось выполнить вход');
    return await response.json() as unknown;
  } finally {
    window.clearTimeout(timeout);
    signal.removeEventListener('abort', cancel);
  }
}

export async function login(initData: string, signal: AbortSignal): Promise<Session> {
  const data = await request('telegram', {
    method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ init_data: initData }),
  }, signal);
  if (typeof data !== 'object' || data === null
    || !('access_token' in data) || typeof data.access_token !== 'string' || !data.access_token || data.access_token.length > 4096
    || !('token_type' in data) || data.token_type !== 'bearer'
    || !('expires_in' in data) || typeof data.expires_in !== 'number' || !Number.isInteger(data.expires_in) || data.expires_in < 1 || data.expires_in > 3600
    || !('user' in data) || !isUser(data.user)) throw new Error('Некорректный ответ сервера');
  return { access_token: data.access_token, token_type: 'bearer', expires_in: data.expires_in, user: data.user };
}

export async function getMe(token: string, signal: AbortSignal): Promise<User> {
  const data = await request('me', { headers: { Authorization: `Bearer ${token}`, Accept: 'application/json' } }, signal);
  if (!isUser(data)) throw new Error('Некорректный ответ сервера');
  return data;
}
