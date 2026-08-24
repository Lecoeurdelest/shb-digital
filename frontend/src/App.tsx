// App.tsx — auth gate + boot-check (CONTRACT §1 · D-19 · D-39 skip-auth).
// Boot: gọi GET /api/auth/me:
//   · 200 {user} (đã login HOẶC DEV_SKIP_AUTH ON) → skip Landing, vào thẳng Workspace (role từ /me).
//   · 401 → Landing (mặt tiền — Login thật trong modal). Đăng xuất / 401 mid-session → về Landing.
// Cookie JWT httponly do server giữ; /me là đường FE biết "đã có phiên" qua reload (thay vì mất
// state như trước). Mock mode: me() ném 401 → luôn hiện Landing (test luồng Login qua modal).
import { useCallback, useEffect, useState } from 'react';
import { conversationApi } from './api';
import { Landing } from './components/landing/Landing';
import { Workspace } from './Workspace';
import { ControlTower } from './components/ControlTower';
import { ErrorBoundary } from './components/ErrorBoundary';
import type { AuthUser } from './types';
import './components/Login.css';

type BootState =
  | { phase: 'checking' }
  | { phase: 'anon' }
  | { phase: 'authed'; user: AuthUser };

interface ApprovalDeepLink {
  kind: 'approval';
  approvalId: string;
  nextPath: string;
}

interface CaseDeepLink {
  kind: 'case';
  caseId: string;
  nextPath: string;
}

type AdminDeepLink = ApprovalDeepLink | CaseDeepLink;

const APPROVAL_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// SPA không thêm router chỉ cho một doorbell URL. Chỉ nhận đúng root + đúng 2 param, UUID chuẩn;
// malformed/param lặp bị coi như URL thường và tuyệt đối không kích hoạt approval fetch.
function parseApprovalDeepLink(pathname: string, search: string, hash = ''): ApprovalDeepLink | null {
  if (pathname !== '/' || hash) return null;
  const params = new URLSearchParams(search);
  const keys = Array.from(params.keys());
  if (keys.length !== 2 || new Set(keys).size !== 2 || keys.some((key) => key !== 'tab' && key !== 'approval')) {
    return null;
  }
  const approvalId = params.get('approval') ?? '';
  if (params.get('tab') !== 'approvals' || !APPROVAL_ID.test(approvalId)) return null;
  return { kind: 'approval', approvalId, nextPath: `${pathname}${search}` };
}

// D-83 exact-case URL dùng cùng kỷ luật parser với approval nhưng là contract độc lập. Hai parser
// không dùng alias chéo: tab/id sai cặp hoặc param thừa/lặp đều không tạo exact fetch.
function parseCaseDeepLink(pathname: string, search: string, hash = ''): CaseDeepLink | null {
  if (pathname !== '/' || hash) return null;
  const params = new URLSearchParams(search);
  const keys = Array.from(params.keys());
  if (keys.length !== 2 || new Set(keys).size !== 2 || keys.some((key) => key !== 'tab' && key !== 'case')) {
    return null;
  }
  const caseId = params.get('case') ?? '';
  if (params.get('tab') !== 'cases' || !APPROVAL_ID.test(caseId)) return null;
  return { kind: 'case', caseId, nextPath: `${pathname}${search}` };
}

function parseAdminDeepLink(pathname: string, search: string, hash = ''): AdminDeepLink | null {
  return parseApprovalDeepLink(pathname, search, hash) ?? parseCaseDeepLink(pathname, search, hash);
}

// App = ErrorBoundary bọc AppInner: 1 lỗi render bất kỳ nhánh nào (Login/Tower/Workspace)
// → fallback UI thay vì trắng màn. Boundary ở ngoài cùng để bắt cả lỗi trong boot/gate.
export default function App() {
  return (
    <ErrorBoundary>
      <AppInner />
    </ErrorBoundary>
  );
}

function AppInner() {
  const [deepLink] = useState(() =>
    parseAdminDeepLink(window.location.pathname, window.location.search, window.location.hash),
  );
  const [boot, setBoot] = useState<BootState>({ phase: 'checking' });
  const [view, setView] = useState<'workspace' | 'tower'>(() => (deepLink ? 'tower' : 'workspace'));
  const [initialWorkspaceConversationId, setInitialWorkspaceConversationId] = useState<string | null>(null);

  const openCaseConversation = useCallback((conversationId: string) => {
    setInitialWorkspaceConversationId(conversationId);
    setView('workspace');
  }, []);
  const clearConversationHandoff = useCallback((handledId: string) => {
    setInitialWorkspaceConversationId((current) => current === handledId ? null : current);
  }, []);
  const openTower = useCallback(() => {
    setInitialWorkspaceConversationId(null);
    setView('tower');
  }, []);
  const returnToWorkspace = useCallback(() => {
    setInitialWorkspaceConversationId(null);
    setView('workspace');
  }, []);
  const expireAuth = useCallback(() => {
    setInitialWorkspaceConversationId(null);
    setBoot({ phase: 'anon' });
  }, []);

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
    return (
      <Landing
        onSuccess={(user) => setBoot({ phase: 'authed', user })}
        initialAuthOpen={Boolean(deepLink)}
        nextPath={deepLink?.nextPath}
      />
    );
  }

  // Control Tower = màn admin (D-19). Admin toggle sang tower; user chỉ Workspace.
  const isAdmin = boot.user.role === 'admin';
  if (view === 'tower' && isAdmin) {
    return (
      <ControlTower
        onBack={returnToWorkspace}
        initialTab={deepLink?.kind === 'approval' ? 'queue' : deepLink?.kind === 'case' ? 'assessments' : undefined}
        focusedApprovalId={deepLink?.kind === 'approval' ? deepLink.approvalId : undefined}
        focusedCaseId={deepLink?.kind === 'case' ? deepLink.caseId : undefined}
        onOpenCaseConversation={openCaseConversation}
      />
    );
  }

  return (
    <Workspace
      user={boot.user}
      onAuthExpired={expireAuth}
      onOpenTower={isAdmin ? openTower : undefined}
      initialConversationId={initialWorkspaceConversationId}
      onInitialConversationHandled={clearConversationHandoff}
    />
  );
}
