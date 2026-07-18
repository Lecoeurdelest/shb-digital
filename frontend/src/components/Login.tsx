// components/Login.tsx — màn đăng nhập (CONTRACT §1 · D-19). 2 account seed: user/admin.
// Login thành công → cookie httponly shb_token do server set (credentials:'include') → mọi call
// sau authenticated. onSuccess trả AuthUser cho App gate vào Workspace.
import { useState, type FormEvent } from 'react';
import { conversationApi, USE_MOCK_API } from '../api';
import { ApiRequestError } from '../api/client';
import type { AuthUser } from '../types';
import './Login.css';

export function Login({ onSuccess }: { onSuccess: (user: AuthUser) => void }) {
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
      setError(mode === 'register' ? 'Nhập đủ tên đăng nhập và mật khẩu.' : 'Nhập đủ tên đăng nhập và mật khẩu.');
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
            <input name="email" type="email" autoComplete="email" aria-label="Email" placeholder="name@domain.com" />
          </label>
        )}

        {error && <div className="login__error" role="alert">{error}</div>}

        <button className="btn btn--primary login__submit" type="submit" disabled={busy}>
          {busy
            ? (mode === 'register' ? 'Đang đăng ký…' : 'Đang đăng nhập…')
            : (mode === 'register' ? 'Đăng ký & vào' : 'Đăng nhập')}
        </button>

        {mode === 'login'
          ? <div className="login__hint">Demo: <b>user / user</b> (RM) · <b>admin / admin</b> (quản lý) · <b>c001 / c001</b> (khách)</div>
          : <div className="login__hint">Khách mới đăng ký → tạo hồ sơ vay ngay trong cuộc trò chuyện đầu tiên.</div>}
      </form>
    </div>
  );
}
