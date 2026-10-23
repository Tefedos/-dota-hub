import { Link } from 'react-router-dom';
import { MatchIdForm } from '../features/matches/MatchIdForm';
import { localAlpha } from '../features/matches/api';

export function MatchesPage() {
  return <>
    <Link className="back-link" to="/">← На главную</Link>
    <section className="intro compact">
      <p className="eyebrow">DOTA HUB / МАТЧИ</p>
      <h1>Анализ матча</h1>
      <p className="lead">Разбирай игру. Замечай детали. Становись сильнее.</p>
    </section>
    <section className="card match-card" aria-label="Поиск матча">
      <div className="card-top"><span className="feature-icon" aria-hidden="true">⌕</span><span className="badge">В разработке</span></div>
      <h2>Начнём с твоего матча</h2>
      <p>{localAlpha ? 'Введите Match ID, чтобы открыть сохранённый отчёт или запросить анализ через OpenDota.' : 'Отправь /match с номером матча в разрешённой Telegram-группе. Бот подготовит анализ и даст ссылку на него.'}</p>
      <MatchIdForm />
    </section>
    <aside className="info-note"><span aria-hidden="true">i</span><p>{localAlpha ? 'Локальный режим включён явно. Данные анализа поступают из backend и OpenDota.' : 'На этой странице можно проверить формат номера. Загрузка нового матча запускается командой в группе.'}</p></aside>
  </>;
}
