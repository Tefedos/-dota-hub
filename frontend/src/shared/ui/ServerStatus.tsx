import { useEffect, useState } from 'react';
import { getHealth } from '../api/client';

type Connection = 'loading' | 'available' | 'unavailable';

export function ServerStatus() {
  const [connection, setConnection] = useState<Connection>('loading');
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    void getHealth(controller.signal).then(
      () => { if (!controller.signal.aborted) setConnection('available'); },
      () => { if (!controller.signal.aborted) setConnection('unavailable'); },
    );
    return () => controller.abort();
  }, [attempt]);

  const label = {
    loading: 'Проверяем подключение…',
    available: 'Сервер доступен',
    unavailable: 'Сервер недоступен',
  }[connection];

  return (
    <section className="connection" aria-label="Подключение к серверу">
      <div role="status" aria-live="polite">
        <span className={`status-dot ${connection}`} aria-hidden="true" />
        <span>{label}</span>
        <small>{connection === 'unavailable'
          ? 'Не удалось подключиться. Повторите проверку.'
          : 'Состояние на момент последней проверки'}</small>
      </div>
      <button className="text-button" type="button" disabled={connection === 'loading'} onClick={() => {
        setConnection('loading');
        setAttempt((value) => value + 1);
      }}>Проверить</button>
    </section>
  );
}
