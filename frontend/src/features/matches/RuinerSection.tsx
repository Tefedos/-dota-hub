import { useState } from 'react';
import type { MatchPlayer } from './api';
import { HeroPortrait } from './PlayersSection';
import { metricNames, preliminaryReasons } from './ruiner';
import type { PerformancePlayer, PerformanceSignal, RiTeam, RuinerReport } from './ruiner';
import './RuinerSection.css';

const confidence = (value: unknown) => value === 'medium' ? 'средняя' : value === 'low' ? 'низкая' : 'не определена';
const numeric = (value: number | null | undefined) => value == null ? '—' : new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 4 }).format(value);
const indexLabel = (value: number | null | undefined) => value == null ? 'Нет оценки' : `${value}/100`;
const unique = (values: string[]) => [...new Set(values)];

function Signals({ title, signals, negative }: { title: string; signals: PerformanceSignal[]; negative?: boolean }) {
  return <section><h4>{title}</h4>{signals.length ? <ul className="ri-signals">{signals.map((signal, i) => <li key={`${signal.code}-${i}`}>
    <strong>{metricNames[signal.metric] ?? 'Игровой показатель'}</strong>
    <p>Значение: {numeric(signal.value)} · Ориентир: {numeric(signal.reference)}</p>
    <p>{signal.text}</p><small>Тип: {negative ? 'отрицательное отклонение' : signal.code.startsWith('observed_contribution:') ? 'наблюдаемый вклад без численного сравнения' : 'положительный вклад'}.
      {' '}Нормализованная сила сигнала: {numeric(signal.magnitude)}.</small>
  </li>)}</ul> : <p>Сигналы не представлены.</p>}</section>;
}

export function RuinerSection({ data, identities = [], heroNames, envelopeLimits = [] }: {
  data: Record<string, unknown>; identities?: MatchPlayer[]; heroNames: Record<string, string>; envelopeLimits?: string[];
}) {
  const report = data as unknown as RuinerReport;
  const [side, setSide] = useState<RiTeam>('radiant');
  const players = Array.isArray(report.players) ? report.players : [];
  const members = players.filter(p => p.team === side);
  const row = report.teams?.[side];
  const preliminary = row?.preliminary_selection;
  const confirmed = row?.selection?.selection_status === 'selected';
  const selectedSlots = confirmed ? [row.selection.selected_player_slot] : preliminary?.status !== 'none' ? preliminary?.player_slots ?? [] : [];
  // Identity is joined by slot and checked against hero ID; a different match cannot lend its portrait.
  const identity = (p: PerformancePlayer) => identities.find(item => item.player_slot === p.player_slot && item.hero_id === p.hero_id);
  const name = (p: PerformancePlayer) => identity(p)?.hero_name?.trim() || (p.hero_id == null ? 'Неизвестный герой' : heroNames[String(p.hero_id)] || `Герой #${p.hero_id}`);
  const namedSlot = (slot: number | null | undefined) => {
    const p = members.find(item => item.player_slot === slot);
    return p ? name(p) : 'участник не определён';
  };
  return <section className="ri-section" aria-label="Индекс ошибок">
    <h2>Индекс ошибок</h2>
    <p className="report-meta" role="status">{report.quality === 'sufficient' ? 'Достаточно данных для расчёта.' : report.quality === 'partial' ? 'Часть данных недоступна; выводы ограничены.' : 'Недостаточно данных для расчёта.'} Индекс — относительный сигнал, а не доказательство причины поражения.</p>
    <div className="ri-team-switch" aria-label="Команда для анализа">{(['radiant', 'dire'] as const).map(team =>
      <button className="text-button" type="button" key={team} aria-pressed={side === team} onClick={() => setSide(team)}>{team === 'radiant' ? 'Radiant' : 'Dire'}</button>)}</div>
    <article className="card report-card ri-result" aria-label="Результат команды">
      {confirmed ? <><h3>Подтверждённый выбор модели — {namedSlot(row.selection.selected_player_slot)}</h3>
        <p>Индекс: {indexLabel(members.find(p => p.player_slot === row.selection.selected_player_slot)?.error_index)}. Уверенность: {confidence(members.find(p => p.player_slot === row.selection.selected_player_slot)?.confidence)}.</p>
        <p>Соблюдены строгие условия модели. Это не доказывает причину поражения.</p></>
        : <>{preliminary?.status === 'single' ? <><h3>Предварительный лидер по индексу — {namedSlot(preliminary.leader_slot)}</h3>
          <p>Индекс: {indexLabel(preliminary.highest_index)} · Отрыв от следующего: {numeric(preliminary.margin)} баллов.</p>
          <p>У игрока наиболее высокий относительный индекс негативных сигналов в своей команде. Это предварительный результат, который не доказывает причину поражения.</p></>
          : preliminary?.status === 'group' ? <><h3>Игроки с близкими индексами</h3>
            <ul>{preliminary.player_slots.map(slot => <li key={slot}>{namedSlot(slot)} — {indexLabel(members.find(p => p.player_slot === slot)?.error_index)}</li>)}</ul></>
            : <><h3>Предварительный лидер не определён</h3>{!preliminary && <p>В сохранённом отчёте нет предварительного результата. Обновите отчёт для получения доступной проекции.</p>}</>}
          <p>Подтверждённый кандидат: не определён.{preliminary && ` Уверенность: ${confidence(preliminary.confidence)}.`}</p>
          {preliminary && <ul className="report-notes">{unique(preliminary.reason_codes).map(reason => <li key={reason}>{preliminaryReasons[reason] ?? 'Дополнительное ограничение данных.'}</li>)}</ul>}
        </>}
    </article>
    <div className="ri-players">{members.length ? members.map(p => {
      const person = identity(p);
      const nickname = person?.display_name?.trim();
      const selected = selectedSlots.includes(p.player_slot);
      const positives = p.positive_signals ?? [], negatives = p.negative_signals ?? [];
      return <article key={p.player_slot} data-player-slot={p.player_slot} className={`card ri-player${selected ? ' ri-player-selected' : ''}`}>
        <details><summary className="ri-player-heading">
          <HeroPortrait url={person?.hero_image_url ?? null} name={name(p)} />
          <span className="ri-identity"><strong>{name(p)}</strong><span>{!person?.is_anonymous && nickname ? nickname : `Участник №${p.team_player_number} · слот ${p.player_slot}`}</span>
            {selected && <small>{confirmed ? 'Строгий выбор модели' : preliminary?.status === 'group' ? 'В группе близких индексов' : 'Предварительный лидер'}</small>}</span>
          <span className="ri-player-score"><strong>{indexLabel(p.error_index)}</strong><span>Уверенность: {confidence(p.confidence)}</span><small>Положительных: {positives.length} · Отрицательных: {negatives.length}</small></span>
          <span className="ri-details-label">Подробнее ⌄</span>
        </summary><div className="ri-player-details">
          <Signals title="Отрицательные сигналы" signals={negatives} negative /><Signals title="Положительные сигналы" signals={positives} />
          <h4>Ограничения</h4><p>Позиция: {p.position?.position ?? 'не определена'} · {p.position?.evidence === 'confirmed' ? 'подтверждена' : p.position?.evidence === 'estimated' ? 'предположительная' : 'нет достоверных сведений'}.</p>
          <p>Покрытие взвешенных отрицательных осей: {p.evidence_coverage == null ? '—' : `${numeric(p.evidence_coverage * 100)}%`}. Это не полнота всех игровых данных.</p>
          {!!p.missing_metrics?.length && <p>Недоступны: {unique(p.missing_metrics.map(metric => metricNames[metric] ?? 'дополнительный показатель')).join(', ')}.</p>}
          <ul className="report-notes">{unique(p.limitations ?? []).map(text => <li key={text}>{text}</li>)}</ul>
        </div></details>
      </article>;
    }) : <p role="status">Данные игроков этой команды недоступны.</p>}</div>
    <details className="card report-card ri-limitations"><summary>Ограничения анализа</summary><ul className="report-notes">{unique([
      ...(report.limitations ?? []), ...envelopeLimits, ...(preliminary?.reason_codes.filter(code => ['roles_unknown', 'roles_unconfirmed', 'leaver_context_unknown', 'confirmed_leaver'].includes(code)).map(code => preliminaryReasons[code] ?? 'Дополнительное ограничение данных.') ?? []),
    ]).map(text => <li key={text}>{text}</li>)}</ul></details>
  </section>;
}
