export type Section = 'overview' | 'draft' | 'players' | 'timeline' | 'ruiner';
export const localAlpha = import.meta.env.VITE_LOCAL_ALPHA === 'true' && import.meta.env.MODE === 'development';
export type PlayerItem = {
  item_id: number; name: string | null; image_key: string | null;
  image_url: string | null; status: 'known' | 'empty' | 'unmapped' | 'unknown';
};
export type MatchPlayer = {
  player_slot: number; team: 'radiant' | 'dire'; team_player_number: number;
  display_name: string | null; name_source?: string | null; is_anonymous?: boolean | null;
  hero_id: number | null; hero_name: string | null; hero_image_url?: string | null;
  kills: number | null; deaths: number | null; assists: number | null;
  last_hits: number | null; denies: number | null; gpm: number | null; xpm: number | null;
  hero_damage: number | null; tower_damage: number | null; hero_healing: number | null; net_worth: number | null;
  level?: number | null; obs_placed?: number | null; sen_placed?: number | null;
  stun_duration_seconds?: number | null; buyback_count?: number | null;
  items?: (number | null)[]; item_details?: (PlayerItem | null)[] | null;
  neutral_item?: number | null; neutral_item_details?: PlayerItem | null;
  backpack_items?: (number | null)[] | null; backpack_item_details?: (PlayerItem | null)[] | null;
  position?: { position: string | null; evidence?: string | null; confidence?: number | null; source_field?: string | null };
  performance_position?: { position: string | number | null; evidence?: string | null; source_field?: string | null };
};
export type PlayersReport = { match_id?: string; players: MatchPlayer[]; limitations?: string[] };
export type OverviewPlayer = {
  player_slot: number;
  hero_id: number | null;
  hero_name: string | null;
  hero_image_url: string | null;
  display_name: string | null;
};
export type OverviewTeam = {
  team: 'radiant' | 'dire';
  team_id: string | null;
  name: string | null;
  score: number | null;
  players: OverviewPlayer[];
};
export type OverviewTeamStats = { kills: number | null; towers_destroyed: number | null; roshan_kills: number | null };
export type OverviewReport = {
  match_id: string;
  duration: number | null;
  radiant: OverviewTeam;
  dire: OverviewTeam;
  winner: 'radiant' | 'dire' | null;
  start_time: number | null;
  game_mode: number | null;
  patch: number | null;
  game_mode_name: string | null;
  patch_name: string | null;
  team_stats: { radiant: OverviewTeamStats; dire: OverviewTeamStats } | null;
  data_quality: { summary: 'complete' | 'partial' | 'unavailable'; stats: 'complete' | 'partial' | 'unavailable'; draft_order: 'complete' | 'partial' | 'unavailable'; timeline: 'complete' | 'partial' | 'unavailable'; roles: 'complete' | 'partial' | 'unavailable' };
  source_status: string | null;
  limitations: string[];
};
export type MatchEnvelope = {
  schema_version: 1;
  match_id: string | null;
  status: 'queued' | 'running' | 'ready' | 'failed';
  data: Record<string, unknown> | null;
  available_sections: Section[];
  error: { code: string; message: string; retryable: boolean } | null;
  limitations: string[];
  model_version?: string | null;
  config_version?: string | null;
  analyzed_at?: string | null;
  completeness?: 'full' | 'partial' | 'missing' | null;
  retry_after_seconds?: number | null;
};

export async function getMatchSection(matchId: string, section: Section, token: string | null, signal: AbortSignal): Promise<MatchEnvelope> {
  const controller = new AbortController();
  const cancel = () => controller.abort();
  signal.addEventListener('abort', cancel, { once: true });
  if (signal.aborted) cancel();
  const timeout = window.setTimeout(cancel, 8000);
  try {
    const path = localAlpha ? `/api/v1/local-alpha/matches/${matchId}/${section}` : `/api/v1/matches/${matchId}/${section}`;
    const response = await fetch(path, {
      headers: { ...(token && !localAlpha ? { Authorization: `Bearer ${token}` } : {}), Accept: 'application/json' }, signal: controller.signal,
      cache: 'no-store', credentials: 'omit', redirect: 'error',
    });
    if (response.status === 401) throw new Error('Сессия истекла. Откройте приложение через Telegram заново.');
    const data: unknown = await response.json();
    if (response.status === 404) {
      const error = data && typeof data === 'object' && 'error' in data ? data.error : null;
      if (error && typeof error === 'object' && 'code' in error && error.code === 'NOT_FOUND') throw new Error('Матч не найден в OpenDota.');
      throw new Error(localAlpha ? 'Матч ещё не загружен. Запустите анализ ниже.' : 'Матч не найден. Отправьте /match с этим номером в группе.');
    }
    if (!data || typeof data !== 'object' || !('schema_version' in data) || data.schema_version !== 1
      || !('status' in data) || !['queued', 'running', 'ready', 'failed'].includes(String(data.status))
      || !('match_id' in data) || (data.match_id !== null && data.match_id !== matchId)
      || !('available_sections' in data) || !Array.isArray(data.available_sections)
      || !('limitations' in data) || !Array.isArray(data.limitations)
      || !('data' in data) || (data.data !== null && (typeof data.data !== 'object' || Array.isArray(data.data)))
      || !('error' in data)) throw new Error('Некорректный ответ сервера. Повторите позже.');
    if (!response.ok) throw new Error(response.status === 429 ? 'Слишком частые запросы. Повторите позже.' : 'Анализ временно недоступен. Повторите позже.');
    return data as MatchEnvelope;
  } catch (error) {
    if (error instanceof TypeError || error instanceof SyntaxError || (error instanceof DOMException && error.name === 'AbortError' && !signal.aborted)) {
      throw new Error('Нет связи с сервером. Проверьте подключение и повторите попытку.');
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
    signal.removeEventListener('abort', cancel);
  }
}

export async function analyzeLocalMatch(matchId: string): Promise<void> {
  if (!localAlpha) throw new Error('Локальный анализ выключен');
  const response = await fetch(`/api/v1/local-alpha/matches/${matchId}/analyze`, {
    method: 'POST', headers: { Accept: 'application/json' }, cache: 'no-store', credentials: 'omit', redirect: 'error',
  });
  if (!response.ok) throw new Error(response.status === 429 ? 'Другой матч уже обрабатывается. Повторите позже.' : 'Не удалось запустить анализ. Проверьте backend и OpenDota.');
}
