import { useEffect, useRef, useState } from 'react';
import { Link, NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { HomePage } from '../pages/HomePage';
import { MatchesPage } from '../pages/MatchesPage';
import { ServerStatus } from '../shared/ui/ServerStatus';
import { AuthStatus } from '../features/auth/AuthStatus';
import type { Session } from '../features/auth/api';
import { telegramStartMatchId } from '../features/auth/telegram';
import { MatchReportPage } from '../pages/MatchReportPage';

export function App() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const [session, setSession] = useState<Session | null>(null);
  const appliedStart = useRef(false);
  useEffect(() => {
    if (!session || appliedStart.current) return;
    appliedStart.current = true;
    const matchId = telegramStartMatchId();
    if (matchId) navigate(`/matches/${matchId}`, { replace: true });
  }, [session, navigate]);
  const main = useRef<HTMLElement>(null);
  useEffect(() => {
    document.title = pathname === '/matches' ? 'Анализ матча · Dota Hub' : 'Dota Hub';
    main.current?.focus();
    window.scrollTo(0, 0);
  }, [pathname]);

  return <div className="shell">
    <a className="skip-link" href="#content">Перейти к содержимому</a>
    <header className="header">
      <Link className="brand" to="/" aria-label="Dota Hub — главная"><span className="brand-mark" aria-hidden="true">D</span>DOTA<span className="brand-accent">HUB</span></Link>
      <span className="build-label">Ранняя версия</span>
    </header>
    <nav className="nav" aria-label="Основная навигация">
      <NavLink to="/" end>Главная</NavLink>
      <NavLink to="/matches">Анализ матча</NavLink>
    </nav>
    <main id="content" ref={main} tabIndex={-1}>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/matches" element={<MatchesPage />} />
        <Route path="/matches/:matchId" element={<MatchReportPage session={session} />} />
        <Route path="*" element={<section className="intro"><h1>Страница не найдена</h1><Link className="back-link" to="/">Вернуться на главную →</Link></section>} />
      </Routes>
    </main>
    <footer><AuthStatus onSessionChange={setSession} /><ServerStatus /><p className="footer-note">DOTA HUB <span>Точка отсчёта для следующей игры</span></p></footer>
  </div>;
}
