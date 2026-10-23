import { Link } from 'react-router-dom';

export function HomePage() {
  return <>
    <section className="intro">
      <p className="eyebrow">ТВОЯ ИГРА. ТВОЙ ПРОГРЕСС.</p>
      <h1>Больше понимания.<br /><span>Больше возможностей.</span></h1>
      <p className="lead">Отправь /match с номером игры в Telegram-группе и открой подробный разбор по кнопке бота.</p>
    </section>
    <div className="hub-grid">
      <section className="card feature-card">
        <div className="card-top"><span className="feature-icon" aria-hidden="true">↗</span><span className="badge">В разработке</span></div>
        <p className="eyebrow">МАТЧИ</p>
        <h2>Каждая игра —<br />повод разобраться</h2>
        <p>Обзор, драфт, показатели игроков, ход матча и индекс ошибок — с учётом доступных данных.</p>
        <Link className="primary-button" to="/matches">Анализ матча <span aria-hidden="true">→</span></Link>
      </section>
      <div className="upcoming-grid">
        <section className="card upcoming"><span className="badge">Драфт</span><h2>Составы команд</h2><p>Оценки и взаимодействия героев при достаточном покрытии данных.</p></section>
        <section className="card upcoming"><span className="badge">Ход матча</span><h2>События игры</h2><p>Подтверждённые события и возможные изменения преимущества.</p></section>
      </div>
    </div>
  </>;
}
