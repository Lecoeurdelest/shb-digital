// ControlTower.tsx — mặt quản trị tách bề mặt nghiệp vụ, kiểm soát và vận hành kỹ thuật. Telemetry
// chỉ được fetch khi tab TechnicalOperationsView được mount; deep-link hàng duyệt giữ nguyên.
import { lazy, Suspense, useCallback, useEffect, useState } from 'react';
import { conversationApi } from '../api';
import { useApprovalBadge } from '../hooks/useApprovalBadge';
import { ThemeToggle } from './ThemeToggle';
import { StatsOverview } from './stats/StatsOverview';
import { ShadowMatchView } from './stats/ShadowMatchView';
import { CaseWorkbench } from './stats/CaseWorkbench';
import { ApprovalQueue } from './ApprovalQueue';
import { shortId, summarize } from './controlTowerFormat';
import { AuditFact, auditActionLabel, auditActorLabel, auditBusinessDetail, auditCostSummary, auditInputSummary, auditOutputSummary } from './controlTowerAudit';
import type { AgentConfigResponse, AuditRow, CompareResult, CompareSide, Conversation } from '../types';
import './ControlTower.css';

const TechnicalOperationsView = lazy(() => import('./stats/TechnicalOperationsView').then((module) => ({
  default: module.TechnicalOperationsView,
})));

export type ControlTowerTab = 'overview' | 'shadow' | 'queue' | 'assessments' | 'audit' | 'agents' | 'technical' | 'config' | 'compare';

const TAB_LABEL: Record<ControlTowerTab, string> = {
  overview: 'Tổng quan',
  shadow: 'Đối chiếu shadow',
  queue: 'Hàng chờ duyệt',
  assessments: 'Cơ sở sơ thẩm',
  audit: 'Nhật ký kiểm soát',
  agents: 'Tiến độ xử lý',
  technical: 'Vận hành kỹ thuật',
  config: 'Cấu hình agent',
  compare: 'Phòng thử nghiệm',
};
const TAB_ORDER: ControlTowerTab[] = ['overview', 'shadow', 'queue', 'assessments', 'agents', 'audit', 'technical', 'config', 'compare'];

interface Props {
  onBack: () => void;
  initialTab?: ControlTowerTab;
  focusedApprovalId?: string;
  onOpenCaseConversation?: (conversationId: string) => void;
}

export function ControlTower({ onBack, initialTab, focusedApprovalId, onOpenCaseConversation }: Props) {
  const [tab, setTab] = useState<ControlTowerTab>(initialTab ?? (focusedApprovalId ? 'queue' : 'overview'));
  // T16-3: anomaly row-click ở Tổng quan → nhảy tab Nhật ký + seed filter mã phiên (không route mới).
  const [auditSeed, setAuditSeed] = useState('');
  const openAudit = (convId: string) => { setAuditSeed(convId); setTab('audit'); };
  // ControlTower chỉ render cho admin (App gate) → poll badge phiếu-bay luôn bật. Số nổi trên tab queue.
  const pending = useApprovalBadge(true);
  return (
    <div className="ct">
      <header className="ct__head">
        <button type="button" className="ct__back" onClick={onBack}>← Workspace</button>
        <span className="ct__title">🗼 Control Tower</span>
        <span className="ct__sub">Điều hành nghiệp vụ · phê duyệt · kiểm soát</span>
        <ThemeToggle />
        <div className="ct__tabs">
          {TAB_ORDER.map((t) => (
            <button
              key={t}
              type="button"
              className={`ct__tab${tab === t ? ' ct__tab--active' : ''}`}
              onClick={() => setTab(t)}
            >
              {TAB_LABEL[t]}
              {t === 'queue' && pending > 0 && (
                <span className="ct__tab-badge" data-testid="ct-queue-badge">{pending}</span>
              )}
            </button>
          ))}
        </div>
      </header>

      <div className="ct__body" data-scroll>
        {tab === 'overview' && <StatsOverview />}
        {tab === 'shadow' && <ShadowMatchView />}
        {tab === 'queue' && <ApprovalQueue focusedApprovalId={focusedApprovalId} />}
        {tab === 'assessments' && <CaseWorkbench onOpenCaseConversation={onOpenCaseConversation} />}
        {tab === 'audit' && <AuditView seedConvId={auditSeed} />}
        {tab === 'agents' && <ProcessingStatus />}
        {tab === 'technical' && (
          <Suspense fallback={<div className="ct__empty" role="status">Đang tải vận hành kỹ thuật…</div>}>
            <TechnicalOperationsView onOpenAudit={openAudit} />
          </Suspense>
        )}
        {tab === 'config' && <AgentConfigView />}
        {tab === 'compare' && <CompareView />}
      </div>
    </div>
  );
}

function AgentConfigView() {
  const [data, setData] = useState<AgentConfigResponse | null>(null);
  const [key, setKey] = useState('');
  const [content, setContent] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { conversationApi.getAgentConfig().then((next) => { setData(next); const first = next.prompts[0]; if (first) { setKey(first.key); setContent(first.active?.content ?? ''); } }).catch(() => setError('Không tải được cấu hình agent.')); }, []);
  const select = (nextKey: string) => { const prompt = data?.prompts.find((item) => item.key === nextKey); setKey(nextKey); setContent(prompt?.active?.content ?? ''); };
  const save = () => { if (!key || !content.trim() || saving) return; setSaving(true); conversationApi.saveAgentPrompt(key, content).then((next) => { setData(next); const prompt = next.prompts.find((item) => item.key === key); setContent(prompt?.active?.content ?? content); setError(null); }).catch(() => setError('Không thể kích hoạt phiên bản prompt.')).finally(() => setSaving(false)); };
  return <div className="ct__section ct__config"><div className="ct__section-head"><span className="ct__section-title">Cấu hình agent</span><span className="ct__config-env">Môi trường: {data?.environment ?? '...'}</span></div>{error && <div className="ct__error">{error}</div>}<div className="ct__config-grid"><aside><label>Agent / prompt<select aria-label="Agent / prompt" value={key} onChange={(event) => select(event.target.value)}>{data?.prompts.map((item) => <option key={item.key} value={item.key}>{item.key}</option>)}</select></label><div className="ct__config-provider">Provider được quản trị qua GitOps; không hiển thị key.</div></aside><section><div className="ct__config-version">Đang chạy: v{data?.prompts.find((item) => item.key === key)?.active?.version ?? '—'}</div><textarea aria-label="Nội dung prompt" value={content} onChange={(event) => setContent(event.target.value)} /><button type="button" className="btn btn--primary" onClick={save} disabled={saving || !content.trim()}>{saving ? 'Đang kích hoạt…' : 'Kích hoạt phiên bản mới'}</button></section></div></div>;
}

// ── Audit view — filter tool_calls. T16-3: seedConvId (từ anomaly row-click Tổng quan) →
//    khởi tạo filter mã phiên đúng ngay khi vào tab. Đổi seed (row khác) → cập nhật filter.
function AuditView({ seedConvId = '' }: { seedConvId?: string }) {
  const [rows, setRows] = useState<AuditRow[]>([]);
  const [convId, setConvId] = useState(seedConvId);
  const [tool, setTool] = useState('');
  const [error, setError] = useState<string | null>(null);

  // seed đổi (mở tab qua anomaly row-click với mã phiên mới) → nạp vào ô lọc conv_id.
  useEffect(() => { if (seedConvId) setConvId(seedConvId); }, [seedConvId]);

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
        <span className="ct__section-title">Nhật ký kiểm soát ({rows.length})</span>
        <input className="ct__filter" placeholder="Lọc theo mã phiên…" value={convId} onChange={(e) => setConvId(e.target.value)} aria-label="Lọc theo mã phiên" />
        <input className="ct__filter" placeholder="Lọc loại hoạt động…" value={tool} onChange={(e) => setTool(e.target.value)} aria-label="Lọc theo loại hoạt động" />
      </div>
      {error && <div className="ct__error">{error}</div>}
      {rows.length === 0 ? (
        <div className="ct__empty">Chưa có hoạt động kiểm soát phù hợp với bộ lọc.</div>
      ) : (
        <div className="ct__audit-list">
          {rows.slice(0, 100).map((r) => (
            <article key={r.id} className="ct__audit-card">
              <div className="ct__audit-main">
                <div className="ct__audit-title">{auditActionLabel(r)}</div>
                <div className="ct__audit-detail">{auditBusinessDetail(r)}</div>
                <div className="ct__audit-facts">
                  <AuditFact label="Đầu vào" value={auditInputSummary(r)} />
                  <AuditFact label="Kết quả" value={auditOutputSummary(r)} />
                  {auditCostSummary(r) && <AuditFact label="Chi phí" value={auditCostSummary(r)!} />}
                </div>
              </div>
              <div className="ct__audit-meta">
                <span>{fmtTs(r.ts)}</span>
                <span>{auditActorLabel(r.actor)}</span>
                <span>Phiên {shortId(r.conv_id)}</span>
                {r.task_id && <span>Bước {shortId(r.task_id)}</span>}
                <span>Mã ghi {shortId(r.id)}</span>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

// Trạng thái hồ sơ là bề mặt nghiệp vụ; cost/token đã tách sang Vận hành kỹ thuật.
function ProcessingStatus() {
  const [convs, setConvs] = useState<Conversation[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    conversationApi
      .listConversations()
      .then((c) => { setConvs(c); setError(null); })
      .catch(() => setError('Lỗi tải danh sách phiên xử lý'));
  }, []);

  const byStatus = convs.reduce<Record<string, number>>((acc, c) => {
    acc[c.status] = (acc[c.status] ?? 0) + 1;
    return acc;
  }, {});
  // DF-B-03: "1 Lỗi" đếm phiên xử lý status='failed' → drill-down = list chính các phiên đó
  // (tiêu đề + mã phiên) ngay dưới số đếm. Dùng convs đã load, KHÔNG
  // thêm API. (Role thuộc TASK — không có list-tasks API; xem note báo cáo. Không xây route mới.)
  const failedConvs = convs.filter((c) => c.status === 'failed');

  return (
    <div className="ct__section">
      <div className="ct__section-title">Tiến độ xử lý — {convs.length} phiên xử lý</div>
      {error && <div className="ct__error">{error}</div>}
      <div className="ct__stat-grid">
        {(['running', 'waiting_approval', 'done', 'failed', 'idle'] as const).map((s) => (
          <div key={s} className={`ct__stat ct__stat--${s}`}>
            <div className="ct__stat-num">{byStatus[s] ?? 0}</div>
            <div className="ct__stat-label">{STATUS_LABEL[s]}</div>
          </div>
        ))}
      </div>
      {failedConvs.length > 0 && (
        <div className="ct__failed" data-testid="failed-list">
          <div className="ct__failed-title">⚠ Phiên xử lý đang lỗi ({failedConvs.length})</div>
          <ul className="ct__failed-rows">
            {failedConvs.slice(0, 20).map((c) => (
              <li key={c.id} className="ct__failed-row" data-testid={`failed-row-${c.id}`}>
                <span className="ct__failed-name">{c.title || '(phiên xử lý chưa đặt tên)'}</span>
                <code className="ct__failed-id">{shortId(c.id)}</code>
              </li>
            ))}
          </ul>
          {failedConvs.length > 20 && <div className="ct__more">… và {failedConvs.length - 20} phiên xử lý lỗi nữa</div>}
        </div>
      )}
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
      <div className="ct__section-title">Phòng thử nghiệm — so sánh cấu hình xử lý</div>
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
      {running && <div className="ct__cmp-loading">⏳ Đang chạy hai cách xử lý song song — thường mất khoảng 90 giây…</div>}
      {error && <div className="ct__error">{error}</div>}
      {result && (
        <div className="ct__cmp-cols">
          <CompareColumn title="Xử lý đơn giản" side={result.single} accent="single" />
          <CompareColumn title="Đội chuyên gia phối hợp" side={result.multi} accent="multi" />
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
        {side.tool_calls != null && <span className="ct__cmp-metric">🔧 {side.tool_calls} bước xử lý</span>}
        {side.cards != null && <span className="ct__cmp-metric">▦ {side.cards} card</span>}
        {side.cost != null && <span className="ct__cmp-metric">💰 {summarize(side.cost)}</span>}
      </div>
      <div className="ct__cmp-text">{side.text ?? '(không có nội dung)'}</div>
      {side.conv_id && <div className="ct__cmp-link">Phiên xử lý: <code>{shortId(side.conv_id)}</code> (mở ở Workspace để xem kết quả chi tiết)</div>}
    </div>
  );
}

function fmtTs(ts: string): string {
  return ts ? ts.slice(0, 19).replace('T', ' ') : '';
}
