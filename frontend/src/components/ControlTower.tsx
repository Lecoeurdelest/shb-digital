// ControlTower.tsx — màn admin (deliverable #4 · SPEC §12/§13). 4 khối: approval queue (duyệt tại
// chỗ) · audit view (filter) · cost meter (tasks.cost per-turn) · trạng thái agent (conv/tasks).
// Data: GET /api/approvals?pending · GET /api/audit?filters · GET /api/conversations. Admin (D-19).
// Look-and-feel tham khảo design/Digital Expert Guild.dc.html Tower (D-13).
import { useCallback, useEffect, useState } from 'react';
import { conversationApi } from '../api';
import { ApiRequestError } from '../api/client';
import { useApprovalBadge } from '../hooks/useApprovalBadge';
import { roleLabel } from '../roles';
import type { ApprovalRow, AuditRow, CompareResult, CompareSide, Conversation } from '../types';
import './ControlTower.css';

type Tab = 'queue' | 'audit' | 'agents' | 'compare';

export function ControlTower({ onBack }: { onBack: () => void }) {
  const [tab, setTab] = useState<Tab>('queue');
  // ControlTower chỉ render cho admin (App gate) → poll badge phiếu-bay luôn bật. Số nổi trên tab queue.
  const pending = useApprovalBadge(true);
  return (
    <div className="ct">
      <header className="ct__head">
        <button type="button" className="ct__back" onClick={onBack}>← Workspace</button>
        <span className="ct__title">🗼 Control Tower</span>
        <span className="ct__sub">Giám sát · phê duyệt · nhật ký — quản lý</span>
        <div className="ct__tabs">
          {(['queue', 'audit', 'agents', 'compare'] as Tab[]).map((t) => (
            <button
              key={t}
              type="button"
              className={`ct__tab${tab === t ? ' ct__tab--active' : ''}`}
              onClick={() => setTab(t)}
            >
              {t === 'queue' ? 'Hàng chờ duyệt' : t === 'audit' ? 'Nhật ký tool' : t === 'agents' ? 'Trạng thái đội' : 'So sánh 1 vs đội'}
              {t === 'queue' && pending > 0 && (
                <span className="ct__tab-badge" data-testid="ct-queue-badge">{pending}</span>
              )}
            </button>
          ))}
        </div>
      </header>

      <div className="ct__body" data-scroll>
        {tab === 'queue' && <ApprovalQueue />}
        {tab === 'audit' && <AuditView />}
        {tab === 'agents' && <AgentStatus />}
        {tab === 'compare' && <CompareView />}
      </div>
    </div>
  );
}

// ── Khối 1: Approval queue — list phiếu pending + duyệt tại chỗ ──
function ApprovalQueue() {
  const [rows, setRows] = useState<ApprovalRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = useCallback(() => {
    conversationApi
      .listApprovals('pending')
      .then((r) => { setRows(r); setError(null); })
      .catch((e: unknown) => setError(e instanceof ApiRequestError ? e.body?.message ?? 'Lỗi tải hàng chờ' : 'Lỗi tải hàng chờ'));
  }, []);

  useEffect(() => { load(); }, [load]);

  const decide = (row: ApprovalRow, decision: 'approved' | 'rejected') => {
    setBusyId(row.id);
    conversationApi
      .decideApproval(row.id, decision, '')
      .then(() => { setRows((prev) => prev.filter((r) => r.id !== row.id)); }) // rời khỏi hàng chờ
      .catch((e: unknown) => {
        if (e instanceof ApiRequestError && e.status === 409) { setRows((prev) => prev.filter((r) => r.id !== row.id)); }
        else setError('Quyết phiếu thất bại');
      })
      .finally(() => setBusyId(null));
  };

  return (
    <div className="ct__section">
      <div className="ct__section-head">
        <span className="ct__section-title">Hàng chờ phê duyệt ({rows.length})</span>
        <button type="button" className="ct__refresh" onClick={load}>⟳ Tải lại</button>
      </div>
      {error && <div className="ct__error">{error}</div>}
      {rows.length === 0 ? (
        <div className="ct__empty" data-testid="queue-empty">Không có phiếu nào chờ duyệt.</div>
      ) : (
        <div className="ct__rows">
          {rows.slice(0, 50).map((row) => (
            <div key={row.id} className="ct__appr-row" data-testid={`queue-row-${row.id}`}>
              <span className="ct__appr-action">🔒 {row.action}</span>
              <span className="ct__appr-conv">{shortId(row.conv_id)}</span>
              <span className="ct__appr-payload">{summarize(row.payload)}</span>
              <div className="ct__appr-btns">
                <button type="button" className="btn btn--ok ct__appr-btn" onClick={() => decide(row, 'approved')} disabled={busyId === row.id}>✓ Duyệt</button>
                <button type="button" className="btn btn--danger ct__appr-btn" onClick={() => decide(row, 'rejected')} disabled={busyId === row.id}>✗ Từ chối</button>
              </div>
            </div>
          ))}
          {rows.length > 50 && <div className="ct__more">… và {rows.length - 50} phiếu nữa (hiển thị 50 đầu)</div>}
        </div>
      )}
    </div>
  );
}

// ── Khối 2: Audit view — filter tool_calls ──
function AuditView() {
  const [rows, setRows] = useState<AuditRow[]>([]);
  const [convId, setConvId] = useState('');
  const [tool, setTool] = useState('');
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    const filters: Record<string, string> = {};
    if (convId.trim()) filters.conv_id = convId.trim();
    if (tool.trim()) filters.tool = tool.trim();
    conversationApi
      .auditFiltered(filters)
      .then((r) => { setRows(r); setError(null); })
      .catch(() => setError('Lỗi tải nhật ký'));
  }, [convId, tool]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="ct__section">
      <div className="ct__section-head">
        <span className="ct__section-title">Nhật ký tool-call ({rows.length})</span>
        <input className="ct__filter" placeholder="Lọc conv_id…" value={convId} onChange={(e) => setConvId(e.target.value)} aria-label="Lọc conv_id" />
        <input className="ct__filter" placeholder="Lọc tool…" value={tool} onChange={(e) => setTool(e.target.value)} aria-label="Lọc tool" />
      </div>
      {error && <div className="ct__error">{error}</div>}
      {rows.length === 0 ? (
        <div className="ct__empty">Không có tool-call (thử lọc conv_id của 1 ca có hoạt động).</div>
      ) : (
        <table className="ct__audit">
          <thead><tr><th>Thời điểm</th><th>Actor</th><th>Tool</th><th>Input</th></tr></thead>
          <tbody>
            {rows.slice(0, 100).map((r) => (
              <tr key={r.id}>
                <td className="ct__audit-ts">{fmtTs(r.ts)}</td>
                <td className="ct__audit-actor">{r.actor === 'main' ? 'Main' : roleLabel(r.actor)}</td>
                <td><code className="ct__audit-tool">{r.tool}</code></td>
                <td className="ct__audit-in">{summarize(r.input)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ── Khối 3+4: Trạng thái đội + cost meter (từ conversations + tasks) ──
function AgentStatus() {
  const [convs, setConvs] = useState<Conversation[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    conversationApi
      .listConversations()
      .then((c) => { setConvs(c); setError(null); })
      .catch(() => setError('Lỗi tải danh sách ca'));
  }, []);

  const byStatus = convs.reduce<Record<string, number>>((acc, c) => {
    acc[c.status] = (acc[c.status] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="ct__section">
      <div className="ct__section-title">Trạng thái đội — {convs.length} ca</div>
      {error && <div className="ct__error">{error}</div>}
      <div className="ct__stat-grid">
        {(['running', 'waiting_approval', 'done', 'failed', 'idle'] as const).map((s) => (
          <div key={s} className={`ct__stat ct__stat--${s}`}>
            <div className="ct__stat-num">{byStatus[s] ?? 0}</div>
            <div className="ct__stat-label">{STATUS_LABEL[s]}</div>
          </div>
        ))}
      </div>
      <div className="ct__note">
        💰 Cost meter: chi phí tính theo LƯỢT (tasks.cost per-turn) — cost per-tool chưa có (SDK không tách, D-48).
        Mở 1 ca ở Workspace để xem cost per-turn của lượt đó.
      </div>
    </div>
  );
}

const STATUS_LABEL: Record<string, string> = {
  running: 'Đang chạy', waiting_approval: 'Chờ duyệt', done: 'Hoàn tất', failed: 'Lỗi', idle: 'Sẵn sàng',
};

// ── Deliverable #5: compare single-agent vs multi-agent (2 cột) ──
function CompareView() {
  const [question, setQuestion] = useState('Khách C001 vay 500 triệu được không?');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<CompareResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = () => {
    if (running || !question.trim()) return;
    setRunning(true);
    setError(null);
    setResult(null);
    conversationApi
      .runCompare(question.trim())
      .then((r) => setResult(r))
      .catch(() => setError('So sánh thất bại — thử lại (chạy 2 chế độ mất ~90s).'))
      .finally(() => setRunning(false));
  };

  return (
    <div className="ct__section">
      <div className="ct__section-title">So sánh: 1 LLM trần vs cả ĐỘI (deliverable #5)</div>
      <div className="ct__cmp-input">
        <input
          className="ct__cmp-q"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Câu hỏi thẩm định…"
          aria-label="Câu hỏi so sánh"
          disabled={running}
        />
        <button type="button" className="btn btn--primary ct__cmp-run" onClick={run} disabled={running} data-testid="compare-run">
          {running ? 'Đang chạy 2 chế độ…' : '▶ Chạy so sánh'}
        </button>
      </div>
      {running && <div className="ct__cmp-loading">⏳ Đang chạy SINGLE + MULTI song song — mất ~90s (model chạy thật, kiên nhẫn)…</div>}
      {error && <div className="ct__error">{error}</div>}
      {result && (
        <div className="ct__cmp-cols">
          <CompareColumn title="1 LLM TRẦN (single)" side={result.single} accent="single" />
          <CompareColumn title="CẢ ĐỘI (multi-agent)" side={result.multi} accent="multi" />
        </div>
      )}
    </div>
  );
}

function CompareColumn({ title, side, accent }: { title: string; side: CompareSide | null | undefined; accent: 'single' | 'multi' }) {
  if (!side) {
    return (
      <div className={`ct__cmp-col ct__cmp-col--${accent}`}>
        <div className="ct__cmp-col-title">{title}</div>
        <div className="ct__cmp-partial">Không có kết quả (chế độ này timeout / lỗi — partial).</div>
      </div>
    );
  }
  return (
    <div className={`ct__cmp-col ct__cmp-col--${accent}`}>
      <div className="ct__cmp-col-title">{title}</div>
      <div className="ct__cmp-metrics">
        {side.duration_s != null && <span className="ct__cmp-metric">⏱ {side.duration_s}s</span>}
        {side.tool_calls != null && <span className="ct__cmp-metric">🔧 {side.tool_calls} tool</span>}
        {side.cards != null && <span className="ct__cmp-metric">▦ {side.cards} card</span>}
        {side.cost != null && <span className="ct__cmp-metric">💰 {summarize(side.cost)}</span>}
      </div>
      <div className="ct__cmp-text">{side.text ?? '(không có nội dung)'}</div>
      {side.conv_id && <div className="ct__cmp-link">Ca thật: <code>{shortId(side.conv_id)}</code> (mở ở Workspace để xem trace đầy đủ)</div>}
    </div>
  );
}

function shortId(id: string): string {
  return id.length > 14 ? `${id.slice(0, 10)}…` : id;
}
function summarize(obj: unknown): string {
  if (obj == null) return '';
  try { return JSON.stringify(obj).slice(0, 90); } catch { return ''; }
}
function fmtTs(ts: string): string {
  return ts ? ts.slice(0, 19).replace('T', ' ') : '';
}
