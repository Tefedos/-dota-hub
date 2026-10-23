import { useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { localAlpha } from './api';

function validateMatchId(value: string): string | null {
  if (!value) return 'Введите Match ID.';
  if (!/^[1-9][0-9]*$/.test(value)) return 'Match ID должен быть положительным целым числом без пробелов и знаков.';
  if (value.length > 19 || BigInt(value) > 9223372036854775807n) {
    return 'Match ID не должен превышать 9223372036854775807.';
  }
  return null;
}

export function MatchIdForm() {
  const navigate = useNavigate();
  const [matchId, setMatchId] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const problem = validateMatchId(matchId.trim());
    setError(problem);
    setSubmitted(!problem);
    if (problem) input.current?.focus();
    else if (localAlpha) navigate(`/matches/${matchId.trim()}`);
  }

  return (
    <form onSubmit={submit} noValidate>
      <label htmlFor="match-id">Match ID</label>
      <div className="input-row">
        <input ref={input} id="match-id" name="matchId" type="text" inputMode="numeric"
          autoComplete="off" spellCheck={false} maxLength={64} placeholder="Введите номер матча"
          value={matchId} aria-invalid={Boolean(error)}
          aria-describedby={error ? 'match-help match-error' : 'match-help'}
          onChange={(event) => { setMatchId(event.target.value); setError(null); setSubmitted(false); }} />
        <button className="primary-button" type="submit">{localAlpha ? 'Открыть матч' : 'Проверить ID'} <span aria-hidden="true">↗</span></button>
      </div>
      <p className="field-help" id="match-help">Номер можно найти в Dota 2: история игр → нужный матч.</p>
      {error && <p className="field-error" id="match-error" role="alert">{error}</p>}
      {submitted && <div className="notice" role="status"><strong>Формат Match ID корректен</strong>
        <p>Отправьте в Telegram-группе: /match {matchId.trim()}</p></div>}
    </form>
  );
}
