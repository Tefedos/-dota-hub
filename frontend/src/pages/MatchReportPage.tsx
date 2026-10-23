import { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import type { Session } from '../features/auth/api';
import { validMatchId } from '../features/auth/telegram';
import { analyzeLocalMatch, getMatchSection, localAlpha } from '../features/matches/api';
import type { MatchEnvelope, Section } from '../features/matches/api';
import { SectionContent } from '../features/matches/SectionContent';

const sections: [Section, string][] = [['overview', 'Обзор'], ['players', 'Игроки'], ['draft', 'Драфт'], ['timeline', 'Ход матча'], ['ruiner', 'Индекс ошибок / Вывод']];

export function MatchReportPage({ session }: { session: Session | null }) {
  const { matchId: parameter } = useParams();
  const matchId = validMatchId(parameter);
  const [section, setSection] = useState<Section>('overview');
  const [response, setResponse] = useState<{ matchId: string; section: Section; value: MatchEnvelope } | null>(null);
  const [failure, setFailure] = useState<{ matchId: string; section: Section; message: string } | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState(false);
  const [heroNames, setHeroNames] = useState<Record<string, string>>({});
  const tabsRef = useRef<HTMLElement>(null);
  const result = response?.matchId === matchId && response.section === section ? response.value : null;
  const error = failure?.matchId === matchId && failure.section === section ? failure.message : null;
  useEffect(() => {
    const tabs = tabsRef.current;
    const active = tabs?.querySelector<HTMLButtonElement>('[aria-pressed="true"]');
    if (!tabs || !active) return;
    const bounds = tabs.getBoundingClientRect();
    const selected = active.getBoundingClientRect();
    if (selected.left < bounds.left) tabs.scrollBy({ left: selected.left - bounds.left, behavior: 'smooth' });
    else if (selected.right > bounds.right) tabs.scrollBy({ left: selected.right - bounds.right, behavior: 'smooth' });
  }, [section]);
  useEffect(() => {
    setResponse(null); setFailure(null);
    if (!matchId || (!session && !localAlpha)) return;
    const controller = new AbortController();
    void getMatchSection(matchId, section, session?.access_token ?? null, controller.signal)
      .then(value => { if (!controller.signal.aborted) setResponse({ matchId, section, value }); })
      .catch((reason: unknown) => { if (!controller.signal.aborted) setFailure({ matchId, section, message: reason instanceof Error ? reason.message : 'Не удалось загрузить анализ' }); });
    return () => controller.abort();
  }, [matchId, session, section, attempt]);
  useEffect(() => {
    if (!matchId || (!session && !localAlpha) || section !== 'ruiner') return;
    const controller = new AbortController();
    void getMatchSection(matchId, 'players', session?.access_token ?? null, controller.signal).then(value => {
      const players = value.data?.players;
      if (!controller.signal.aborted && Array.isArray(players)) {
        setHeroNames(Object.fromEntries(players.filter(player => player && typeof player === 'object' && 'hero_id' in player && typeof player.hero_id === 'number' && 'hero_name' in player && typeof player.hero_name === 'string')
          .map(player => [String(player.hero_id), String(player.hero_name)])));
      }
    }).catch(() => {});
    return () => controller.abort();
  }, [matchId, session, section, attempt]);
  async function analyze() {
    if (!matchId || busy) return;
    setBusy(true); setFailure(null);
    try { await analyzeLocalMatch(matchId); setAttempt(value => value + 1); }
    catch (reason) { setFailure({ matchId, section, message: reason instanceof Error ? reason.message : 'Не удалось загрузить матч' }); }
    finally { setBusy(false); }
  }
  const statusMessage = busy ? 'Получаем матч от OpenDota и выполняем анализ…' : error
    ?? (!result ? section === 'players' ? 'Загружаем игроков…' : 'Загружаем анализ…'
      : result.status === 'queued' || result.status === 'running' ? 'Матч обрабатывается. Обновите статус через несколько секунд.'
        : result.status === 'failed' ? 'Анализ недоступен. Повторите запрос.'
          : result.data ? null : 'Раздел пока недоступен.');
  if (!matchId) return <section className="intro"><h1>Некорректная ссылка на матч</h1></section>;
  return <section className="intro compact match-report-page">
    <p className="eyebrow">DOTA HUB / АНАЛИЗ</p><h1>Матч {matchId}</h1>
    {!session && !localAlpha ? <p role="status">Для просмотра анализа войдите через Telegram.</p> : <>
      <nav ref={tabsRef} aria-label="Разделы анализа">{sections.map(([key, title]) => <button key={key} type="button" className="text-button" aria-pressed={section === key} onClick={() => setSection(key)}>{title}</button>)}</nav>
      {statusMessage && <div role="status">{statusMessage}</div>}
      {result?.data && <SectionContent section={section} data={result.data} heroNames={heroNames} envelope={result} />}
      {section !== 'overview' && result?.limitations.length ? <div className="card report-card"><h2>Ограничения данных</h2><ul className="report-notes">{result.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul></div> : null}
      {localAlpha && <button className="primary-button" type="button" disabled={busy} onClick={() => void analyze()}>Запросить анализ из OpenDota</button>}
      <button className="text-button" type="button" onClick={() => setAttempt(value => value + 1)}>Обновить</button>
    </>}
  </section>;
}
