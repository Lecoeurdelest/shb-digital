// components/Login.tsx — màn đăng nhập (CONTRACT §1 · D-19). 2 account seed: user/admin.
// Login thành công → cookie httponly shb_token do server set (credentials:'include') → mọi call
// sau authenticated. onSuccess trả AuthUser cho App gate vào Workspace.
import { useState, type FormEvent } from 'react';
import { conversationApi, USE_MOCK_API } from '../api';
import { ApiRequestError } from '../api/client';
import type { AuthUser } from '../types';
import './Login.css';

// googleEnabled do CALLER (Landing) prefetch + truyền — Login KHÔNG tự fetch (chống flaky
// layout-shift T11-4: nếu Login tự fetch lúc mount-trong-modal, nút Google nhảy vào SAU khi modal
// đã paint). undefined = provider đang tải (reserve chỗ, chưa hiện nút); true = hiện nút Google;
// false = ẩn (fail-closed / server tắt google). D-56 persona KHÁCH.
export function Login({ onSuccess, googleEnabled }: { onSuccess: (user: AuthUser) => void; googleEnabled?: boolean }) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<'login' | 'register'>('login'); // D-57 — khách mới đăng ký

  // UNCONTROLLED form: đọc value từ FormData lúc submit (không giữ state per-keystroke). Chuẩn
  // HTML form → hoạt động đồng nhất với người gõ, password-manager autofill, và automation tool
  // (React controlled input bỏ lỡ input event do các nguồn này set value trực tiếp).
  const submit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (busy) return;
    const form = new FormData(e.currentTarget);
    const username = String(form.get('username') ?? '').trim();
    const password = String(form.get('password') ?? '');
    const email = String(form.get('email') ?? '').trim();
    if (!username || !password) {
      setError('Nhập đủ tên đăng nhập và mật khẩu.');
      return;
    }
    // DF-A-03: validate email tự chủ (không dựa HTML5 type=email — nó chặn submit im lặng, app hiện
    // message sai case). email TUỲ CHỌN: có giá trị mà sai định dạng → message đúng nguyên nhân.
    if (mode === 'register' && email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setError('Email không hợp lệ (hoặc bỏ trống — email là tuỳ chọn).');
      return;
    }
    setBusy(true);
    setError(null);
    // register (khách mới) → auto-login cookie; login (account có sẵn). Cả 2 trả {user} → onSuccess.
    const call = mode === 'register'
      ? conversationApi.register(username, password, email || undefined)
      : conversationApi.login(username, password);
    call
      .then((res) => onSuccess(res.user))
      .catch((err: unknown) => {
        // lỗi 4-field từ body (409 username_taken, 400 bad_username/password/email) → message rõ
        if (err instanceof ApiRequestError && err.body) setError(err.body.message);
        else if (err instanceof Error) setError(`${mode === 'register' ? 'Đăng ký' : 'Đăng nhập'} thất bại: ${err.message}`);
        else setError(mode === 'register' ? 'Đăng ký thất bại' : 'Đăng nhập thất bại');
      })
      .finally(() => setBusy(false));
  };

  const switchMode = (m: 'login' | 'register') => { setMode(m); setError(null); };

  return (
    <div className="login">
      <form className="login__card" onSubmit={submit}>
        <div className="login__brand">
          <span className="login__logo">G</span>
          <div>
            <div className="login__title">Digital Expert Guild</div>
            <div className="login__sub">Đội chuyên gia số ngân hàng — BANK Digital</div>
          </div>
        </div>

        {USE_MOCK_API && <div className="login__mockflag">● MOCK API — mọi credential đều vào được</div>}

        <div className="login__tabs" role="tablist">
          <button
            type="button"
            role="tab"
            className={`login__tab${mode === 'login' ? ' login__tab--active' : ''}`}
            onClick={() => switchMode('login')}
            aria-selected={mode === 'login'}
          >
            Đăng nhập
          </button>
          <button
            type="button"
            role="tab"
            className={`login__tab${mode === 'register' ? ' login__tab--active' : ''}`}
            onClick={() => switchMode('register')}
            aria-selected={mode === 'register'}
            data-testid="tab-register"
          >
            Đăng ký khách mới
          </button>
        </div>

        <label className="login__field">
          <span>Tên đăng nhập</span>
          <input
            name="username"
            defaultValue={mode === 'login' ? 'user' : ''}
            key={mode} // reset defaultValue khi đổi mode
            autoComplete="username"
            aria-label="Tên đăng nhập"
          />
        </label>
        <label className="login__field">
          <span>Mật khẩu</span>
          <input
            name="password"
            type="password"
            autoComplete={mode === 'register' ? 'new-password' : 'current-password'}
            aria-label="Mật khẩu"
          />
        </label>
        {mode === 'register' && (
          <label className="login__field">
            <span>Email (tuỳ chọn)</span>
            {/* type="text" (KHÔNG "email") — HTML5 type=email chặn submit im lặng làm message sai case;
               tự validate regex trong submit → báo đúng nguyên nhân (DF-A-03). */}
            <input name="email" type="text" autoComplete="email" aria-label="Email" placeholder="name@domain.com" />
          </label>
        )}

        {error && <div className="login__error" role="alert">{error}</div>}

        <button className="btn btn--primary login__submit" type="submit" disabled={busy}>
          {busy
            ? (mode === 'register' ? 'Đang đăng ký…' : 'Đang đăng nhập…')
            : (mode === 'register' ? 'Đăng ký & vào' : 'Đăng nhập')}
        </button>

        {/* Khối Google: undefined (đang tải providers) → RESERVE chỗ (skeleton cùng chiều cao nút thật)
           để khi resolved không đẩy layout (chống flaky T11-4). true → nút thật. false → ẩn hẳn (null). */}
        {googleEnabled === undefined ? (
          <div className="login__google-reserve" data-testid="login-google-reserve" aria-hidden="true">
            <div className="login__divider"><span>hoặc</span></div>
            <div className="login__google login__google--skeleton" />
          </div>
        ) : googleEnabled ? (
          <>
            <div className="login__divider"><span>hoặc</span></div>
            {/* Google sign-in chuẩn: logo G 4-màu inline SVG (KHÔNG asset remote — CSP/offline-safe),
               nút trắng viền + chữ. Full-page redirect /google/start → Google → callback set cookie →
               về FE (App boot-check /me). Đăng ký = cùng flow (Google tự tạo tài khoản khách mới). */}
            <a className="login__google" href="/api/auth/google/start" data-testid="login-google">
              <svg className="login__google-icon" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.27-4.74 3.27-8.1z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.1a6.6 6.6 0 0 1 0-4.2V7.06H2.18a11 11 0 0 0 0 9.88l3.66-2.84z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1A11 11 0 0 0 2.18 7.06l3.66 2.84C6.71 7.31 9.14 5.38 12 5.38z"/>
              </svg>
              {mode === 'register' ? 'Đăng ký với Google' : 'Đăng nhập với Google'}
            </a>
          </>
        ) : null}

        {mode === 'login'
          ? <div className="login__hint">Demo: <b>c001 / c001</b> (khách)</div>
          : <div className="login__hint">Khách mới đăng ký → tạo hồ sơ vay ngay trong cuộc trò chuyện đầu tiên.</div>}
      </form>
    </div>
  );
}
