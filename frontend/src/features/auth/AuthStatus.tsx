import { useEffect, useState } from 'react';
import { getMe, login, SessionExpired } from './api';
import type { Session } from './api';
import { telegramInitData } from './telegram';
import { localAlpha } from '../matches/api';

type AuthState = { status: 'loading' | 'not-telegram' | 'error' | 'expired' }
  | { status: 'authenticated'; session: Session; expiresAt: number };

export function AuthStatus({ onSessionChange }: { onSessionChange?: (session: Session | null) => void }) {
  if (localAlpha) return <section className="connection" aria-label="Локальный режим"><div role="status"><span className="status-dot available" aria-hidden="true" />Локальный режим Alpha<small>Без Telegram; только на этом компьютере</small></div></section>;
  return <TelegramAuthStatus onSessionChange={onSessionChange} />;
}

function TelegramAuthStatus({ onSessionChange }: { onSessionChange?: (session: Session | null) => void }) {
  // The bearer token lives only in React memory. No browser storage or URL parameters.
  const [state, setState] = useState<AuthState>({ status: 'loading' });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    onSessionChange?.(state.status === 'authenticated' ? state.session : null);
  }, [state, onSessionChange]);

  useEffect(() => {
    const controller = new AbortController();
    const authenticate = async () => {
      try {
        const raw = await telegramInitData(controller.signal);
        if (controller.signal.aborted) return;
        if (raw === null) { setState({ status: 'not-telegram' }); return; }
        const started = Date.now();
        const session = await login(raw, controller.signal);
        const user = await getMe(session.access_token, controller.signal);
        if (controller.signal.aborted) return;
        const expiresAt = started + (session.expires_in - 1) * 1000;
        if (Date.now() >= expiresAt) { setState({ status: 'expired' }); return; }
        setState({ status: 'authenticated', session: { ...session, user }, expiresAt });
      } catch (error) {
        if (!controller.signal.aborted) setState({ status: error instanceof SessionExpired ? 'expired' : 'error' });
      }
    };
    void authenticate();
    return () => controller.abort();
  }, [attempt]);

  useEffect(() => {
    if (state.status !== 'authenticated') return;
    const expire = () => setState({ status: 'expired' });
    const onVisible = () => { if (Date.now() >= state.expiresAt) expire(); };
    const timeout = window.setTimeout(expire, Math.max(0, state.expiresAt - Date.now()));
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      window.clearTimeout(timeout);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [state]);

  const label = {
    loading: 'Входим через Telegram…',
    'not-telegram': 'Откройте Dota Hub через Telegram для входа',
    error: 'Не удалось войти через Telegram',
    expired: 'Сессия истекла',
    authenticated: 'Вход через Telegram выполнен',
  }[state.status];
  const hint = state.status === 'authenticated'
    ? state.session.user.display_name ?? 'Вы вошли в Dota Hub'
    : state.status === 'error' || state.status === 'expired'
      ? 'Повторите вход. Если ошибка сохраняется, откройте приложение через бота заново.'
      : 'Анализ матчей доступен после подтверждения входа';

  return <section className="connection" aria-label="Вход через Telegram">
    <div role="status" aria-live="polite">
      <span className={`status-dot ${state.status === 'authenticated' ? 'available' : state.status === 'error' || state.status === 'expired' ? 'unavailable' : 'loading'}`} aria-hidden="true" />
      <span>{label}</span><small>{hint}</small>
    </div>
    {(state.status === 'error' || state.status === 'expired') && <button className="text-button" type="button" onClick={() => {
      setState({ status: 'loading' });
      setAttempt(value => value + 1);
    }}>Повторить вход</button>}
  </section>;
}
