type TelegramWebApp = { initData: string; ready: () => void; startParam?: string };

declare global {
  interface Window { Telegram?: { WebApp?: TelegramWebApp } }
}

// The SDK is loaded asynchronously so an unavailable external script cannot block the app.
export async function telegramInitData(signal: AbortSignal): Promise<string | null> {
  if (signal.aborted) throw new Error('Вход отменён');
  if (!window.Telegram?.WebApp) {
    const existing = document.getElementById('telegram-web-app');
    const script = existing ?? document.createElement('script');
    if (!existing) {
      script.id = 'telegram-web-app';
      (script as HTMLScriptElement).async = true;
      (script as HTMLScriptElement).src = 'https://telegram.org/js/telegram-web-app.js?64';
    }
    await new Promise<void>((resolve, reject) => {
      const finish = (ok: boolean) => {
        window.clearTimeout(timeout);
        script.removeEventListener('load', loaded);
        script.removeEventListener('error', failed);
        signal.removeEventListener('abort', failed);
        if (ok) resolve(); else reject(new Error('Telegram недоступен'));
      };
      const loaded = () => finish(Boolean(window.Telegram?.WebApp));
      const failed = () => finish(false);
      const timeout = window.setTimeout(failed, 8000);
      script.addEventListener('load', loaded, { once: true });
      script.addEventListener('error', failed, { once: true });
      signal.addEventListener('abort', failed, { once: true });
      if (!existing) document.head.appendChild(script);
    });
  }
  const app = window.Telegram?.WebApp;
  if (!app || typeof app.initData !== 'string') throw new Error('Telegram недоступен');
  if (!app.initData) return null;
  app.ready();
  return app.initData;
}

export function validMatchId(value: string | undefined): string | null {
  return value && /^[1-9][0-9]{0,18}$/.test(value) && BigInt(value) <= 9223372036854775807n ? value : null;
}

// Routing hint only. Authentication always uses the complete raw initData and backend signature checks.
export function telegramStartMatchId(): string | null {
  const app = window.Telegram?.WebApp;
  const rawStart = app?.initData ? new URLSearchParams(app.initData).get('start_param') : null;
  const candidate = rawStart ?? app?.startParam ?? new URLSearchParams(window.location.search).get('tgWebAppStartParam');
  if (!candidate?.startsWith('match_')) return null;
  return validMatchId(candidate.slice(6));
}
