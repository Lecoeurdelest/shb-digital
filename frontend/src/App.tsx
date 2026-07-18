// App.tsx — auth gate + boot-check (CONTRACT §1 · D-19 · D-39 skip-auth).
// Boot: gọi GET /api/auth/me:
//   · 200 {user} (đã login HOẶC DEV_SKIP_AUTH ON) → skip Login, vào thẳng Workspace (role từ /me).
//   · 401 → Login flow (Login.tsx). Đăng xuất / 401 mid-session → về Login.
// Cookie JWT httponly do server giữ; /me là đường FE biết "đã có phiên" qua reload (thay vì mất
// state như trước). Mock mode: me() ném 401 → luôn hiện Login (test luồng Login).
import { useEffect, useState } from 'react';
import { conversationApi } from './api';
import { Login } from './components/Login';
import { Workspace } from './Workspace';
import type { AuthUser } from './types';
import './components/Login.css';

type BootState =
  | { phase: 'checking' }
  | { phase: 'anon' }
  | { phase: 'authed'; user: AuthUser };

export default function App() {
  const [boot, setBoot] = useState<BootState>({ phase: 'checking' });

  // boot-check /me lúc mount (D-39). Lỗi/401 → anon (Login). 200 → authed (skip Login).
  useEffect(() => {
    let alive = true;
    conversationApi
      .me()
      .then((res) => {
        if (alive) setBoot({ phase: 'authed', user: res.user });
      })
      .catch(() => {
        if (alive) setBoot({ phase: 'anon' });
      });
    return () => {
      alive = false;
    };
  }, []);

  if (boot.phase === 'checking') {
    return (
      <div className="login">
        <div className="boot-check" role="status">Đang kiểm tra phiên đăng nhập…</div>
      </div>
    );
  }

  if (boot.phase === 'anon') {
    return <Login onSuccess={(user) => setBoot({ phase: 'authed', user })} />;
  }

  return <Workspace user={boot.user} onAuthExpired={() => setBoot({ phase: 'anon' })} />;
}
