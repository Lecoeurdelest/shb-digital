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

        <div className="login__hint">Demo: <b>user / user</b> (RM) · <b>admin / admin</b> (quản lý)</div>
      </form>
    </div>
  );
}
