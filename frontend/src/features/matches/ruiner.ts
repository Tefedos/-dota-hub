export type RiTeam = 'radiant' | 'dire';
export type RiConfidence = 'low' | 'medium';
export type PreliminarySelection = {
  projection_version: 'ri_preliminary_v1'; minimum_margin: 15;
  status: 'single' | 'group' | 'none'; player_slots: number[]; leader_slot: number | null;
  highest_index: number | null; margin: number | null; confidence: RiConfidence; reason_codes: string[];
};
export type PerformanceSignal = {
  code: string; metric: string; text: string; value: number; reference: number | null; magnitude: number;
};
export type PerformancePlayer = {
  player_slot: number; team_player_number: number; hero_id: number | null; team: RiTeam;
  error_index: number | null; confidence: RiConfidence; evidence_coverage: number;
  position: { position: number | null; evidence: 'confirmed' | 'estimated' | 'unknown' };
  positive_signals: PerformanceSignal[]; negative_signals: PerformanceSignal[];
  missing_metrics: string[]; limitations: string[];
};
export type PerformanceTeam = {
  selection: { selection_status: 'selected' | 'no_confident_selection'; selected_player_slot: number | null };
  preliminary_selection?: PreliminarySelection | null;
};
export type RuinerReport = {
  match_id: string; quality: 'sufficient' | 'partial' | 'insufficient'; players: PerformancePlayer[];
  teams: Partial<Record<RiTeam, PerformanceTeam>>; limitations: string[];
};

export const preliminaryReasons: Record<string, string> = {
  highest_relative_index: 'Наибольший относительный индекс в команде.',
  close_scores: 'Индексы отличаются менее чем на 15 баллов. Данных недостаточно для обоснованного выделения одного игрока.',
  incomplete_team: 'Для сравнения требуется полный состав из пяти игроков.',
  invalid_roster: 'Не удалось подтвердить корректность состава команды.',
  incomplete_player_scores: 'Индекс рассчитан не для всех пяти игроков.',
  invalid_player_scores: 'Некоторые оценки не прошли проверку допустимых значений.',
  all_indices_zero: 'Все рассчитанные индексы равны нулю.',
  leader_signals_missing: 'Максимальный индекс не подтверждается доступными отрицательными сигналами.',
  confirmed_leaver: 'Есть подтверждённый выход из матча; специальное правило анализа ещё не согласовано.',
  invalid_leaver_context: 'Сведения о выходе игроков из матча противоречивы.',
  blocking_player_context: 'В данных игроков есть ограничения, препятствующие предварительному сравнению.',
  roles_unknown: 'Роли игроков не определены; сравнение имеет ограничения.',
  roles_unconfirmed: 'Роли игроков оценены, но не подтверждены.',
  leaver_context_unknown: 'Нет достоверных сведений о том, покидали ли игроки матч.',
  stored_projection_inconsistent: 'Сохранённый предварительный вывод противоречит данным игроков. Надёжный выбор сейчас недоступен.',
};
export const metricNames: Record<string, string> = {
  deaths_per_min: 'Смертность в минуту', kill_participation: 'Участие в командных убийствах', kda: 'Соотношение убийств и помощи к смертям',
  gpm: 'Золото в минуту', xpm: 'Опыт в минуту', hero_damage_per_min: 'Урон героям в минуту',
  tower_damage_per_min: 'Урон строениям в минуту', healing_per_min: 'Лечение в минуту',
  obs_placed: 'Установленные обзорные варды', sen_placed: 'Установленные сторожевые варды',
  observer_kills: 'Уничтоженные обзорные варды', sentry_kills: 'Уничтоженные сторожевые варды',
};
