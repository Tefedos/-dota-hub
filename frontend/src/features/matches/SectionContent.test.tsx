// @vitest-environment jsdom
import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { SectionContent } from './SectionContent';

afterEach(cleanup);

it('keeps team evidence on the team card, names heroes and leaves null scores empty', () => {
  render(<SectionContent section="draft" heroNames={{}} data={{
    mode: 'FINAL_ONLY', draft_advantage: 'insufficient_data',
    teams: {
      radiant: { evaluation: { score: null, confidence: 'low', evidence_coverage: 0,
        reasons: [{ scope: 'team', polarity: 'positive', text: 'В составе есть контроль.' }] },
        team_win_conditions: [], likely_vulnerabilities: [] },
      dire: { evaluation: { score: null, confidence: 'low', evidence_coverage: 0, reasons: [] },
        team_win_conditions: [], likely_vulnerabilities: [] },
    },
    pick_events: [{ hero_id: 35, hero_name: 'Sniper', team: 'dire', at_pick_score: null,
      final_score: null, at_pick: { confidence: 'low' }, final_context: { confidence: 'low', reasons: [] },
      pros: [], cons: [], countered_heroes: [], threatened_by_heroes: [] }],
  }} />);
  expect(screen.getByText(/Режим оценки: FINAL_ONLY/)).toBeTruthy();
  const card = screen.getByRole('heading', { name: 'Sniper' }).closest('.report-card');
  expect(card).not.toBeNull();
  expect(within(card as HTMLElement).getByText(/Финальная оценка: нет данных/)).toBeTruthy();
  expect(within(card as HTMLElement).queryByText(/На момент выбора/)).toBeNull();
  expect(screen.getByText(/оценка на момент выбора недоступна для всего матча/)).toBeTruthy();
  expect(within(card as HTMLElement).queryByText('В составе есть контроль.')).toBeNull();
  expect(screen.getByText('В составе есть контроль.')).toBeTruthy();
  expect(screen.queryByText('Герой #35')).toBeNull();
});
