// App.tsx — auth gate mỏng (CONTRACT §1 · D-19). Chưa login → Login; đã login → Workspace.
// Auth state = có AuthUser hay không. Cookie JWT httponly do server giữ (FE không đọc được) —
// FE chỉ nhớ "đã login + role gì" trong memory; F5 mất state → về Login (S1 chấp nhận, ghi
// deviation: chưa persist session qua reload; mở rộng sau = gọi /me lúc mount nếu backend có).
import { useState } from 'react';
import { Login } from './components/Login';
import { Workspace } from './Workspace';
import type { AuthUser } from './types';

export default function App() {
  const [user, setUser] = useState<AuthUser | null>(null);

  if (!user) return <Login onSuccess={setUser} />;
  return <Workspace user={user} onAuthExpired={() => setUser(null)} />;
}
