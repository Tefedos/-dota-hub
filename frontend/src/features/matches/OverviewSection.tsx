import type { MatchEnvelope, OverviewPlayer, OverviewReport, OverviewTeam, OverviewTeamStats } from './api';
import { HeroPortrait } from './PlayersSection';

type Data = Record<string, unknown>;
type Side = 'radiant' | 'dire';
const isObject = (value: unknown): value is Data => value !== null && typeof value === 'object' && !Array.isArray(value);
const text = (value: unknown): string | null => typeof value === 'string' && value.trim() ? value.trim() : null;
const number = (value: unknown): number | null => typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null;
const sideName = (side: Side) => side === 'radiant' ? 'Radiant' : 'Dire';
const count = (value: number | null | undefined): string => value === null || value === undefined ? '—' : String(value);

function safePortrait(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  try {
    const url = new URL(value);
    return url.protocol === 'https:' && url.hostname === 'cdn.cloudflare.steamstatic.com'
      && /^\/apps\/dota2\/images\/dota_react\/heroes\/[a-z0-9_]+\.png$/.test(url.pathname) ? url.href : null;
  } catch { return null; }
}

function readPlayers(value: unknown): OverviewPlayer[] {
  if (!Array.isArray(value)) return [];
  return value.filter(isObject).filter(player => Number.isInteger(player.player_slot) && number(player.player_slot) !== null)
    .map(player => ({
      player_slot: player.player_slot as number,
      hero_id: number(player.hero_id),
      hero_name: text(player.hero_name),
      hero_image_url: safePortrait(player.hero_image_url),
      display_name: text(player.display_name),
    })).sort((a, b) => a.player_slot - b.player_slot);
}

function readTeam(value: unknown, side: Side): OverviewTeam {
  const team = isObject(value) ? value : {};
  return {
    team: side, team_id: text(team.team_id), name: text(team.name), score: number(team.score), players: readPlayers(team.players),
  };
}

function readStats(value: unknown): OverviewTeamStats | null {
  if (!isObject(value)) return null;
  return { kills: number(value.kills), towers_destroyed: number(value.towers_destroyed), roshan_kills: number(value.roshan_kills) };
}

function readReport(data: Data): OverviewReport | null {
  if (typeof data.match_id !== 'string' || !isObject(data.radiant) || !isObject(data.dire)) return null;
  const quality = isObject(data.data_quality) ? data.data_quality : {};
  const validQuality = (value: unknown): 'complete' | 'partial' | 'unavailable' =>
    value === 'complete' || value === 'partial' ? value : 'unavailable';
  const stats = isObject(data.team_stats) ? data.team_stats : null;
  const radiantStats = readStats(stats?.radiant), direStats = readStats(stats?.dire);
  return {
    match_id: data.match_id,
    duration: number(data.duration),
    start_time: number(data.start_time),
    radiant: readTeam(data.radiant, 'radiant'),
    dire: readTeam(data.dire, 'dire'),
    winner: data.winner === 'radiant' || data.winner === 'dire' ? data.winner : null,
    game_mode: number(data.game_mode), patch: number(data.patch),
    game_mode_name: text(data.game_mode_name), patch_name: text(data.patch_name),
    team_stats: radiantStats && direStats ? { radiant: radiantStats, dire: direStats } : null,
    data_quality: {
      summary: validQuality(quality.summary), stats: validQuality(quality.stats),
      draft_order: validQuality(quality.draft_order), timeline: validQuality(quality.timeline),
      roles: validQuality(quality.roles),
    },
    source_status: text(data.source_status),
    limitations: Array.isArray(data.limitations) ? data.limitations.filter((item): item is string => typeof item === 'string' && !!item.trim()) : [],
  };
}

function duration(value: number | null): string {
  return value === null ? '—' : `${Math.floor(value / 60)}:${String(Math.floor(value % 60)).padStart(2, '0')}`;
}

function matchDate(value: number | null): string {
  if (value === null) return '—';
  const date = new Date(value * 1000);
  if (Number.isNaN(date.getTime())) return '—';
  return `${new Intl.DateTimeFormat('ru-RU', { timeZone: 'UTC', day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }).format(date)} UTC`;
}

function TeamRoster({ team, side }: { team: OverviewTeam; side: Side }) {
  return <section className={`overview-roster players-team players-team-${side}`} aria-label={`Состав ${sideName(side)}`}>
    <header className="players-team-heading"><h3>{team.name ?? sideName(side)}</h3><span>{team.players.length} / 5 игроков</span></header>
    {team.players.length ? <div className="players-list">{team.players.map(player => {
      const heroName = player.hero_name ?? 'Неизвестный герой';
      const nickname = player.display_name ?? 'Анонимный игрок';
      return <article className="overview-player player-row" key={player.player_slot}>
        <HeroPortrait url={player.hero_image_url} name={heroName} />
        <div className="player-identity"><h4 title={heroName}>{heroName}</h4><p title={nickname}>{nickname}</p></div>
      </article>;
    })}</div> : <p className="report-meta">Данные игроков этой команды недоступны.</p>}
  </section>;
}

function qualityLabel(value: 'complete' | 'partial' | 'unavailable'): string {
  return value === 'complete' ? 'доступны' : value === 'partial' ? 'частично доступны' : 'недоступны';
}

export function OverviewSection({ data, envelope }: { data: Data; envelope: MatchEnvelope }) {
  const report = readReport(data);
  const useful = report && (report.radiant.score !== null || report.dire.score !== null || report.duration !== null
    || report.radiant.players.length > 0 || report.dire.players.length > 0);
  if (!report || !useful || report.match_id !== envelope.match_id) return <section className="card report-card" aria-label="Обзор матча"><h2>Обзор матча</h2><p>Нет данных о матче.</p></section>;

  const { radiant, dire } = report;
  const limitations = [...new Set([...report.limitations, ...envelope.limitations].map(item => item.trim()).filter(Boolean))];
  const partial = envelope.completeness !== 'full' || report.source_status === 'FOUND_PARTIAL'
    || Object.values(report.data_quality).some(value => value !== 'complete') || limitations.length > 0;
  const metricRows: [string, keyof OverviewTeamStats][] = [
    ['Убийства', 'kills'], ['Разрушенные башни', 'towers_destroyed'], ['Убийства Roshan', 'roshan_kills'],
  ];
  return <section className="overview" aria-label="Обзор матча">
    <header className="overview-heading"><h2>Обзор матча</h2>
      <span className="overview-state" role="status">{partial ? 'Готов · Есть ограничения' : 'Анализ готов'}</span></header>

    <section className="card overview-result" aria-label="Результат матча">
      <div className={`overview-side overview-side-radiant${report.winner === 'radiant' ? ' overview-winner' : ''}`}>
        <strong title={radiant.name ?? sideName('radiant')}>{radiant.name ?? sideName('radiant')}</strong>
        {report.winner === 'radiant' && <small>Победитель</small>}
      </div>
      <div className="overview-score" aria-label={`Счёт ${count(radiant.score)} : ${count(dire.score)}`}><strong>{count(radiant.score)} <span>:</span> {count(dire.score)}</strong></div>
      <div className={`overview-side overview-side-dire${report.winner === 'dire' ? ' overview-winner' : ''}`}>
        <strong title={dire.name ?? sideName('dire')}>{dire.name ?? sideName('dire')}</strong>
        {report.winner === 'dire' && <small>Победитель</small>}
      </div>
    </section>

    <div className="overview-meta" aria-label="Сведения о матче">
      <div className="card"><span>Длительность</span><strong>{duration(report.duration)}</strong></div>
      <div className="card"><span>Дата матча</span><strong>{matchDate(report.start_time)}</strong></div>
      <div className="card"><span>Режим</span><strong>{report.game_mode_name ?? 'Не определён'}</strong></div>
      <div className="card"><span>Патч</span><strong>{report.patch_name ?? 'Не определён'}</strong></div>
    </div>

    <section aria-label="Составы команд" className="overview-block"><h3>Составы команд</h3>
      <div className="players-teams"><TeamRoster team={radiant} side="radiant" /><TeamRoster team={dire} side="dire" /></div>
    </section>

    <section aria-label="Командная статистика" className="overview-block"><h3>Командная статистика</h3>
      <div className="card overview-stats"><div className="overview-stats-header"><span>Показатель</span><span>Radiant</span><span>Dire</span></div>
        {metricRows.map(([name, key]) => {
          const a = report.team_stats?.radiant[key] ?? null, b = report.team_stats?.dire[key] ?? null;
          return <div className="overview-stats-row" key={key}><span>{name}</span><strong>{count(a)}</strong><strong>{count(b)}</strong></div>;
        })}
        {metricRows.some(([, key]) => report.team_stats?.radiant[key] == null || report.team_stats?.dire[key] == null)
          && <p className="overview-stats-note">«—» означает: показатель не подтверждён данными матча.</p>}
      </div>
    </section>

    <details className="card overview-quality"><summary>Качество данных и ограничения</summary>
      <div className="overview-quality-content">
        <p>Базовый обзор: {envelope.completeness === 'full' ? 'полный' : envelope.completeness === 'partial' ? 'частичный' : 'неполный'}.</p>
        {report.source_status === 'FOUND_PARTIAL' && <p>Исходные данные матча частично доступны.</p>}
        <p>Сведения об игроках: {qualityLabel(report.data_quality.stats)}. Данные хронологии: {qualityLabel(report.data_quality.timeline)}. Данные о ролях: {qualityLabel(report.data_quality.roles)}.</p>
        {limitations.length > 0 && <ul className="report-notes">{limitations.map(item => <li key={item}>{item}</li>)}</ul>}
      </div>
    </details>
  </section>;
}
