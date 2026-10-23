import { useEffect, useState } from 'react';
import type { MatchPlayer, PlayerItem, PlayersReport } from './api';

type MetricKey = 'hero_damage' | 'net_worth' | 'xpm';
type SortKey = 'slot' | 'kills' | 'gpm' | 'hero_damage' | 'net_worth';
type Team = 'radiant' | 'dire';
const sides: Team[] = ['radiant', 'dire'];
const number = (value: number | null | undefined) => typeof value === 'number' && Number.isFinite(value)
  ? new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 1 }).format(value) : '—';
const positions: Record<string, string> = { safe_lane: 'Безопасная линия', mid_lane: 'Средняя линия', off_lane: 'Сложная линия', jungle: 'Лес' };

export function HeroPortrait({ url, name }: { url: string | null; name: string }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [url]);
  if (!url || failed) return <span className="player-portrait player-portrait-fallback" role="img" aria-label="Портрет героя недоступен">✦</span>;
  return <img className="player-portrait" src={url} alt={`Портрет ${name}`} width="80" height="45" loading="lazy" onError={() => setFailed(true)} />;
}

function ItemSlot({ item, label }: { item: PlayerItem | null | undefined; label: string }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [item?.image_url]);
  const status = item?.status ?? 'empty';
  const name = status === 'known' && item?.name ? item.name : status === 'empty' ? 'Пусто' : 'Неизвестный предмет';
  return <span className={`player-item player-item-${status}`} title={`${label}: ${name}`} aria-label={`${label}: ${name}`}>
    {status === 'known' && item?.image_url && !failed
      ? <img src={item.image_url} alt={name} loading="lazy" onError={() => setFailed(true)} />
      : status === 'empty' ? null : <span aria-hidden="true">?</span>}
  </span>;
}

function ItemGroup({ title, items, count }: { title: string; items: (PlayerItem | null)[] | null | undefined; count: number }) {
  return <div className="player-item-group"><h4>{title}</h4><div className="player-items">
    {Array.from({ length: count }, (_, index) => <ItemSlot key={index} item={items?.[index]} label={`${title}, слот ${index + 1}`} />)}
  </div></div>;
}

function Metric({ title, value }: { title: string; value: number | null | undefined }) {
  return <div><dt>{title}</dt><dd>{number(value)}</dd></div>;
}

function PlayerRow({ player, metric }: { player: MatchPlayer; metric: MetricKey }) {
  const heroName = player.hero_name?.trim() || 'Неизвестный герой';
  const rawName = player.display_name?.trim();
  const nickname = player.is_anonymous || !rawName || /^Игрок (Radiant|Dire) #\d+$/.test(rawName) ? 'Анонимный игрок' : rawName;
  const position = player.position?.evidence === 'confirmed' && player.position.source_field === 'lane_role'
    ? positions[player.position.position ?? ''] : undefined;
  const hasOptional = [player.obs_placed, player.sen_placed, player.stun_duration_seconds, player.buyback_count]
    .some(value => typeof value === 'number' && Number.isFinite(value));
  const metricLabel = { hero_damage: 'Урон', net_worth: 'Стоимость', xpm: 'XPM' }[metric];
  return <article className="player-row"><details className="player-more">
    <summary className="player-row-heading">
      <HeroPortrait url={player.hero_image_url ?? null} name={heroName} />
      <span className="player-identity"><strong className="player-hero-name">{heroName}</strong><span className="player-nickname" title={nickname}>{nickname}</span>
        {player.level != null && <span className="player-level">Уровень {number(player.level)}</span>}{position && <span className="player-position">{position}</span>}</span>
      <span className="player-quick-stats"><span><small>K / D / A</small><strong>{number(player.kills)} / {number(player.deaths)} / {number(player.assists)}</strong></span>
        <span><small>GPM</small><strong>{number(player.gpm)}</strong></span><span><small>{metricLabel}</small><strong>{number(player[metric])}</strong></span></span>
      <span className="player-chevron" aria-hidden="true">⌄</span>
    </summary>
    <div className="player-expanded">
      <dl className="player-metrics">
        <Metric title="Убийства" value={player.kills} /><Metric title="Смерти" value={player.deaths} /><Metric title="Помощь" value={player.assists} />
        <Metric title="GPM" value={player.gpm} /><Metric title="XPM" value={player.xpm} /><Metric title="Стоимость" value={player.net_worth} />
        <Metric title="Урон героям" value={player.hero_damage} /><Metric title="Урон строениям" value={player.tower_damage} />
        <Metric title="Лечение" value={player.hero_healing} /><Metric title="Добивания" value={player.last_hits} />
        <Metric title="Отказы" value={player.denies} /><Metric title="Уровень" value={player.level} />
      </dl>
      {hasOptional ? <dl className="player-metrics player-optional">
        {player.obs_placed != null && <Metric title="Обзорные варды" value={player.obs_placed} />}
        {player.sen_placed != null && <Metric title="Сторожевые варды" value={player.sen_placed} />}
        {player.stun_duration_seconds != null && <Metric title="Оглушение, сек." value={player.stun_duration_seconds} />}
        {player.buyback_count != null && <Metric title="Выкупы" value={player.buyback_count} />}
      </dl> : <p className="player-extra-note">Дополнительная статистика недоступна для этого матча.</p>}
      {(player.item_details || player.backpack_item_details || player.neutral_item_details) && <div className="player-inventory">
        <ItemGroup title="Инвентарь" items={player.item_details} count={6} />
        <ItemGroup title="Рюкзак" items={player.backpack_item_details} count={3} />
        <ItemGroup title="Нейтральный предмет" items={player.neutral_item_details ? [player.neutral_item_details] : []} count={1} />
      </div>}
    </div>
  </details></article>;
}

function sortedPlayers(players: MatchPlayer[], side: Team, sort: SortKey): MatchPlayer[] {
  const source = players.map((player, index) => ({ player, index })).filter(({ player }) => player.team === side);
  source.sort((a, b) => {
    if (sort === 'slot') return a.player.player_slot - b.player.player_slot || a.index - b.index;
    const left = a.player[sort]; const right = b.player[sort];
    if (left == null && right == null) return a.index - b.index;
    if (left == null) return 1;
    if (right == null) return -1;
    return right - left || a.index - b.index;
  });
  return source.map(({ player }) => player);
}

export function PlayersSection({ data }: { data: Record<string, unknown> }) {
  const report = data as PlayersReport;
  const players = Array.isArray(report.players) ? report.players.filter((player): player is MatchPlayer => !!player && typeof player === 'object') : [];
  const [metric, setMetric] = useState<MetricKey>('hero_damage');
  const [sort, setSort] = useState<SortKey>('slot');
  const [activeTeam, setActiveTeam] = useState<Team>('radiant');
  const incomplete = players.length < 10 || players.some(player => [player.kills, player.deaths, player.assists, player.gpm, player.xpm, player.hero_damage, player.tower_damage, player.net_worth].some(value => value == null));
  return <section className="players-section" aria-label="Игроки матча">
    {players.length === 0 ? <p className="report-meta" role="status">Данные игроков пока недоступны.</p> : <>
      {incomplete && <p className="report-meta" role="status">Часть сведений об игроках недоступна; отсутствующие показатели отмечены знаком «—».</p>}
      <div className="players-toolbar">
        <label>Показатель <select value={metric} onChange={event => setMetric(event.target.value as MetricKey)}>
          <option value="hero_damage">Урон героям</option><option value="net_worth">Net Worth</option><option value="xpm">XPM</option>
        </select></label>
        <label>Сортировка <select value={sort} onChange={event => setSort(event.target.value as SortKey)}>
          <option value="slot">Исходный порядок</option><option value="kills">Убийства</option><option value="gpm">GPM</option>
          <option value="hero_damage">Урон героям</option><option value="net_worth">Net Worth</option>
        </select></label>
      </div>
      <div className="players-team-switch" aria-label="Выбор команды">{sides.map(side => <button type="button" key={side}
        aria-pressed={activeTeam === side} onClick={() => setActiveTeam(side)}>{side === 'radiant' ? 'Radiant' : 'Dire'}</button>)}</div>
      <div className="players-teams">{sides.map(side => {
        const teamPlayers = sortedPlayers(players, side, sort);
        return <section className={`players-team players-team-${side}${activeTeam === side ? ' players-team-active' : ''}`}
          aria-label={side === 'radiant' ? 'Radiant' : 'Dire'} key={side}>
          <header className="players-team-heading"><h2>{side === 'radiant' ? 'Radiant' : 'Dire'}</h2><span>{teamPlayers.length} / 5 игроков</span></header>
          <div className="players-list">{teamPlayers.length ? teamPlayers.map((player, index) =>
            <PlayerRow player={player} metric={metric} key={`${player.player_slot}-${index}`} />)
            : <p className="report-meta">Данные игроков этой команды недоступны.</p>}</div>
        </section>;
      })}</div>
    </>}
  </section>;
}
