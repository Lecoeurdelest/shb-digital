// components/Login.tsx — màn đăng nhập (CONTRACT §1 · D-19). 2 account seed: user/admin.
// Login thành công → cookie httponly shb_token do server set (credentials:'include') → mọi call
// sau authenticated. onSuccess trả AuthUser cho App gate vào Workspace.
import { useEffect, useState, type FormEvent } from 'react';
import { conversationApi, USE_MOCK_API } from '../api';
import { ApiRequestError } from '../api/client';
import type { AuthUser } from '../types';
import './Login.css';

export function Login({ onSuccess }: { onSuccess: (user: AuthUser) => void }) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // Google OAuth (D-56 persona KHÁCH): nút chỉ hiện khi server bật (providers.google). Lỗi
  // fetch → coi như tắt (fail-closed hiển thị — login user/pass vẫn nguyên).
  const [googleEnabled, setGoogleEnabled] = useState(false);
  useEffect(() => {
    conversationApi.getAuthProviders()
      .then((p) => setGoogleEnabled(p.google))
      .catch(() => setGoogleEnabled(false));
  }, []);

  // UNCONTROLLED form: đọc value từ FormData lúc submit (không giữ state per-keystroke). Chuẩn
  // HTML form → hoạt động đồng nhất với người gõ, password-manager autofill, và automation tool
  // (React controlled input bỏ lỡ input event do các nguồn này set value trực tiếp).
  const submit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (busy) return;
    const form = new FormData(e.currentTarget);
    const username = String(form.get('username') ?? '').trim();
    const password = String(form.get('password') ?? '');
    if (!username || !password) {
      setError('Nhập đủ tên đăng nhập và mật khẩu.');
      return;
    }
    setBusy(true);
    setError(null);
    conversationApi
      .login(username, password)
      .then((res) => onSuccess(res.user))
      .catch((err: unknown) => {
        if (err instanceof ApiRequestError && err.body) setError(err.body.message);
        else if (err instanceof Error) setError(`Đăng nhập thất bại: ${err.message}`);
        else setError('Đăng nhập thất bại');
      })
      .finally(() => setBusy(false));
  };

  return (
    <div className="login">
      <form className="login__card" onSubmit={submit}>
        <div className="login__brand">
          <span className="login__logo">G</span>
          <div>
            <div className="login__title">Digital Expert Guild</div>
            <div className="login__sub">Đội chuyên gia số ngân hàng — SHB #132</div>
          </div>
        </div>

        {USE_MOCK_API && <div className="login__mockflag">● MOCK API — mọi credential đều vào được</div>}

        <label className="login__field">
          <span>Tên đăng nhập</span>
          <input
            name="username"
            defaultValue="user"
            autoComplete="username"
            aria-label="Tên đăng nhập"
          />
        </label>
        <label className="login__field">
          <span>Mật khẩu</span>
          <input
            name="password"
            type="password"
            autoComplete="current-password"
            aria-label="Mật khẩu"
          />
        </label>

        {error && <div className="login__error" role="alert">{error}</div>}

        <button className="btn btn--primary login__submit" type="submit" disabled={busy}>
          {busy ? 'Đang đăng nhập…' : 'Đăng nhập'}
        </button>

        {googleEnabled && (
          <>
            <div className="login__divider"><span>hoặc</span></div>
            {/* full-page redirect: /google/start → Google → callback set cookie → về FE (App boot-check /me) */}
            <a className="login__google" href="/api/auth/google/start" data-testid="login-google">
              <svg className="login__google-icon" viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.27-4.74 3.27-8.1z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84A11 11 0 0 0 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.1a6.6 6.6 0 0 1 0-4.2V7.06H2.18a11 11 0 0 0 0 9.88l3.66-2.84z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1A11 11 0 0 0 2.18 7.06l3.66 2.84C6.71 7.31 9.14 5.38 12 5.38z"/>
              </svg>
              Đăng nhập với Google
            </a>
          </>
        )}

        <div className="login__hint">Demo: <b>user / user</b> (RM) · <b>admin / admin</b> (quản lý)</div>
      </form>
    </div>
  );
}
