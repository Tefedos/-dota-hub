import type { MatchEnvelope, MatchPlayer, Section } from './api';
import { OverviewSection } from './OverviewSection';
import { PlayersSection } from './PlayersSection';
import { RuinerSection } from './RuinerSection';

type Data = Record<string, unknown>;
const object = (value: unknown): Data => value && typeof value === 'object' && !Array.isArray(value) ? value as Data : {};
const list = (value: unknown): Data[] => Array.isArray(value) ? value.map(object) : [];
const lines = (value: unknown): string[] => Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
const label = (value: unknown): string => value === null || value === undefined ? 'нет данных' : String(value);
const team = (value: unknown) => value === 'radiant' ? 'Radiant' : value === 'dire' ? 'Dire' : label(value);
const score = (value: unknown) => value === null || value === undefined ? 'нет данных' : `${label(value)} / 100`;
const hero = (value: unknown, names: Record<string, string>) => value === null || value === undefined ? 'герой неизвестен' : names[String(value)] ?? `Герой #${value}`;

function Notes({ values }: { values: string[] }) {
  return values.length ? <ul className="report-notes">{values.map((value, index) => <li key={`${index}-${value}`}>{value}</li>)}</ul> : <p>Подтверждённых факторов нет.</p>;
}

export function SectionContent({ section, data, heroNames, envelope, playerIdentities }: { section: Section; data: Data; heroNames: Record<string, string>; envelope?: MatchEnvelope; playerIdentities?: MatchPlayer[] }) {
  if (section === 'overview') {
    return envelope ? <OverviewSection data={data} envelope={envelope} /> : null;
  }
  if (section === 'players') return <PlayersSection data={data} />;
  if (section === 'draft') {
    const teams = object(data.teams);
    const picks = list(data.pick_events);
    const names = { ...heroNames, ...Object.fromEntries(picks.filter(pick => typeof pick.hero_id === 'number' && typeof pick.hero_name === 'string')
      .map(pick => [String(pick.hero_id), String(pick.hero_name)])) };
    return <><div className="report-grid">{(['radiant', 'dire'] as const).map(side => {
      const row = object(teams[side]), evaluation = object(row.evaluation);
      const teamReasons = list(evaluation.reasons).filter(reason => reason.scope === 'team' && reason.polarity === 'positive')
        .map(reason => label(reason.text)).filter(text => !lines(row.team_win_conditions).includes(text));
      return <article className="card report-card" key={side}><h2>{team(side)}</h2><p>Оценка: {score(evaluation.score)} · Уверенность: {label(evaluation.confidence)}</p>
        <p>Покрытие данных: {typeof evaluation.evidence_coverage === 'number' ? `${Math.round(evaluation.evidence_coverage * 100)}%` : 'нет данных'}</p>
        <h3>Условия победы</h3><Notes values={lines(row.team_win_conditions)} /><h3>Другие признаки состава</h3><Notes values={teamReasons} />
        <h3>Условные риски</h3><Notes values={lines(row.likely_vulnerabilities)} /></article>;
    })}</div><p className="report-meta">Режим оценки: {label(data.mode)} · Преимущество: {label(data.draft_advantage)}</p>
      {data.mode === 'FINAL_ONLY' && <p className="report-meta">Последовательность пиков не подтверждена: оценка на момент выбора недоступна для всего матча.</p>}
      <div className="report-grid">{picks.map((pick, index) => {
        const atPick = object(pick.at_pick), final = object(pick.final_context);
        return <article className="card report-card" key={`${label(pick.team)}-${label(pick.hero_id)}-${index}`}><h2>{hero(pick.hero_id, names)}</h2><p>{team(pick.team)}</p>
          <p>{data.mode === 'FINAL_ONLY' ? `Финальная оценка: ${score(pick.final_score)}` : `На момент выбора: ${score(pick.at_pick_score)} · Финальная: ${score(pick.final_score)}`}</p>
          <p>Уверенность: {label(final.confidence)}{data.mode === 'FINAL_ONLY' ? '' : ` · На момент выбора: ${label(atPick.confidence)}`}</p>
          <p>Контрит: {Array.isArray(pick.countered_heroes) && pick.countered_heroes.length ? pick.countered_heroes.map(id => hero(id, names)).join(', ') : 'нет данных'}</p>
          <p>Уязвим против: {Array.isArray(pick.threatened_by_heroes) && pick.threatened_by_heroes.length ? pick.threatened_by_heroes.map(id => hero(id, names)).join(', ') : 'нет данных'}</p>
          <h3>Плюсы</h3><Notes values={lines(pick.pros)} /><h3>Минусы</h3><Notes values={lines(pick.cons)} />
          <details><summary>Основания оценки</summary><Notes values={list(final.reasons).map(reason => `${label(reason.text)} (${label(reason.code)}; ${label(reason.patch_applicability)})`)} /></details></article>;
      })}</div></>;
  }
  if (section === 'ruiner') return <RuinerSection key={String(data.match_id ?? '')} data={data} heroNames={heroNames} identities={playerIdentities} envelopeLimits={envelope?.limitations} />;
  const events = list(data.events), gold = list(data.gold_adv_points), xp = list(data.xp_adv_points);
  return <><p className="report-meta">Качество: {label(data.quality)} · Событий: {events.length} · Точек золота: {gold.length} · Точек опыта: {xp.length}</p>
    {!events.length && <p>{label(data.empty_state_text)}</p>}
    <div className="card report-card"><h2>Хронология</h2><ol className="report-events">{events.map((event, index) =>
      <li key={String(event.id ?? index)}><strong>{label(event.display_clock)}</strong> · {label(event.description)} <small>({label(event.evidence_quality)})</small></li>)}</ol></div>
    {(gold.length || xp.length) ? <div className="card report-card"><h2>Преимущество по данным OpenDota</h2>
      <p>График пока не реализован. Последняя точка золота: {label(gold.at(-1)?.value)}; опыта: {label(xp.at(-1)?.value)}.</p></div> : null}</>;
}
