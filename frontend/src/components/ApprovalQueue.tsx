// ApprovalQueue.tsx — hàng chờ admin + exact-ticket deep-link (CONTRACT §6).
// Pending list và exact resource fail-soft độc lập: 404 link không làm mất hàng chờ thường.
import { useEffect, useRef, useState } from 'react';
import { conversationApi } from '../api';
import { ApiRequestError } from '../api/client';
import type { ApprovalRow } from '../types';
import { fmtApprovalVnd, laneClass, shortId, summarize } from './controlTowerFormat';

interface Props {
  focusedApprovalId?: string;
}

const STATUS_LABEL: Record<ApprovalRow['status'], string> = {
  pending: 'Chờ duyệt',
  approved: 'Đã duyệt',
  rejected: 'Đã từ chối',
  used: 'Đã thực thi',
  exec_failed: 'Thực thi lỗi',
};

export function ApprovalQueue({ focusedApprovalId }: Props) {
  const [pendingRows, setPendingRows] = useState<ApprovalRow[]>([]);
  const [focusedRow, setFocusedRow] = useState<ApprovalRow | null>(null);
  const [pendingError, setPendingError] = useState<string | null>(null);
  const [focusError, setFocusError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState('');
  const [reloadVersion, setReloadVersion] = useState(0);
  const focusedElementRef = useRef<HTMLDivElement | null>(null);

  // Hai effect cố ý tách: pending 200 vẫn render kể cả exact-ticket 404/timeout và ngược lại.
  useEffect(() => {
    let alive = true;
    conversationApi
      .listApprovals('pending')
      .then((rows) => {
        if (!alive) return;
        setPendingRows(rows);
        setPendingError(null);
      })
      .catch((error: unknown) => {
        if (!alive) return;
        const message = error instanceof ApiRequestError ? error.body?.message : null;
        setPendingError(message || 'Lỗi tải hàng chờ');
      });
    return () => {
      alive = false;
    };
  }, [reloadVersion]);

  useEffect(() => {
    let alive = true;
    setFocusedRow(null);
    setFocusError(null);
    if (!focusedApprovalId) return () => {
      alive = false;
    };

    conversationApi
      .getApproval(focusedApprovalId)
      .then((row) => {
        if (!alive) return;
        setFocusedRow(row);
      })
      .catch(() => {
        if (!alive) return;
        setFocusError('Không mở được phiếu từ liên kết. Hàng chờ thường vẫn dùng được.');
      });
    return () => {
      alive = false;
    };
  }, [focusedApprovalId, reloadVersion]);

  const rows = focusedRow
    ? [focusedRow, ...pendingRows.filter((row) => row.id !== focusedRow.id)]
    : pendingRows;
  const pendingCount = rows.filter((row) => row.status === 'pending').length;
  const focusedVisible = Boolean(focusedApprovalId && rows.some((row) => row.id === focusedApprovalId));

  useEffect(() => {
    if (!focusedVisible) return;
    const element = focusedElementRef.current;
    // jsdom/WebViews cũ có thể thiếu scrollIntoView — focus vẫn phải render, không được crash.
    if (element && typeof element.scrollIntoView === 'function') {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [focusedApprovalId, focusedVisible]);

  const refresh = () => setReloadVersion((version) => version + 1);

  const resetReject = () => {
    setRejectingId(null);
    setRejectReason('');
  };

  const submitDecision = (row: ApprovalRow, decision: 'approved' | 'rejected', reason: string) => {
    setBusyId(row.id);
    conversationApi
      .decideApproval(row.id, decision, reason)
      .then((decided) => {
        setPendingRows((previous) => previous.filter((item) => item.id !== row.id));
        if (row.id === focusedApprovalId) {
          // Decide response là approval resource nhưng có thể không enrich `display`; giữ dữ liệu
          // người-đọc của exact/list row để final ticket không tụt về UUID/JSON sau click.
          setFocusedRow({ ...decided, display: decided.display ?? row.display });
        }
        resetReject();
      })
      .catch((error: unknown) => {
        if (error instanceof ApiRequestError && error.status === 409) {
          // Row đã được quyết ở nơi khác: refetch cả hai nguồn độc lập để hiện trạng thái cuối.
          setPendingRows((previous) => previous.filter((item) => item.id !== row.id));
          resetReject();
          setReloadVersion((version) => version + 1);
          return;
        }
        setPendingError('Quyết phiếu thất bại');
      })
      .finally(() => setBusyId(null));
  };

  const openReject = (row: ApprovalRow) => {
    setRejectingId(row.id);
    setRejectReason('');
    setPendingError(null);
  };

  return (
    <div className="ct__section">
      <div className="ct__section-head">
        <span className="ct__section-title">Hàng chờ phê duyệt ({pendingCount})</span>
        <button type="button" className="ct__refresh" onClick={refresh}>⟳ Tải lại</button>
      </div>
      {pendingError && <div className="ct__error">{pendingError}</div>}
      {focusError && <div className="ct__notice" data-testid="focused-approval-error">{focusError}</div>}
      {rows.length === 0 ? (
        <div className="ct__empty" data-testid="queue-empty">Không có phiếu nào chờ duyệt.</div>
      ) : (
        <div className="ct__rows">
          {rows.slice(0, 50).map((row) => {
            const display = row.display ?? null;
            const who = display?.customer_name || display?.owner_id || shortId(row.conv_id);
            const rejecting = rejectingId === row.id;
            const isFocused = row.id === focusedApprovalId;
            const isPending = row.status === 'pending';
            return (
              <div
                key={row.id}
                ref={isFocused ? focusedElementRef : undefined}
                className={`ct__appr-wrap${isFocused ? ' ct__appr-wrap--focused' : ''}`}
                data-testid={`queue-row-${row.id}`}
                data-approval-status={row.status}
              >
                <div className="ct__appr-row">
                  <span className="ct__appr-action">🔒 {row.action}</span>
                  {display?.lane && (
                    <span className={`asmt__lane ${laneClass(display.lane)}`}>
                      {display.lane.toUpperCase()}
                    </span>
                  )}
                  <span className="ct__appr-who">{who}</span>
                  {display?.amount_vnd != null && (
                    <span className="ct__appr-amount">{fmtApprovalVnd(display.amount_vnd)}</span>
                  )}
                  {display?.loan_id && <span className="ct__appr-loan">{display.loan_id}</span>}
                  <span className="ct__appr-payload" title={summarize(row.payload)}>
                    {display ? '' : summarize(row.payload)}
                  </span>
                  <span className={`ct__appr-status ct__appr-status--${row.status}`}>
                    {STATUS_LABEL[row.status]}
                  </span>
                  {isPending ? (
                    <div className="ct__appr-btns">
                      <button
                        type="button"
                        className="btn btn--ok ct__appr-btn"
                        onClick={() => submitDecision(row, 'approved', '')}
                        disabled={busyId === row.id}
                      >
                        ✓ Duyệt
                      </button>
                      <button
                        type="button"
                        className="btn btn--danger ct__appr-btn"
                        onClick={() => openReject(row)}
                        disabled={busyId === row.id}
                        data-testid={`reject-open-${row.id}`}
                      >
                        ✗ Từ chối
                      </button>
                    </div>
                  ) : null}
                </div>
                {!isPending && row.reason ? <div className="ct__appr-reason">Lý do: {row.reason}</div> : null}
                {rejecting && isPending ? (
                  <div className="ct__reject" data-testid={`reject-panel-${row.id}`}>
                    <textarea
                      className="ct__reject-reason"
                      placeholder="Lý do từ chối (khách sẽ nhận được)…"
                      value={rejectReason}
                      onChange={(event) => setRejectReason(event.target.value)}
                      rows={2}
                      aria-label="Lý do từ chối"
                      autoFocus
                      disabled={busyId === row.id}
                    />
                    <div className="ct__reject-btns">
                      <button type="button" className="btn btn--ghost ct__appr-btn" onClick={resetReject} disabled={busyId === row.id}>
                        Huỷ
                      </button>
                      <button
                        type="button"
                        className="btn btn--danger ct__appr-btn"
                        onClick={() => submitDecision(row, 'rejected', rejectReason.trim())}
                        disabled={busyId === row.id || !rejectReason.trim()}
                        data-testid={`reject-confirm-${row.id}`}
                      >
                        {busyId === row.id ? 'Đang gửi…' : 'Xác nhận từ chối'}
                      </button>
                    </div>
                  </div>
                ) : null}
              </div>
            );
          })}
          {rows.length > 50 && <div className="ct__more">… và {rows.length - 50} phiếu nữa (hiển thị 50 đầu)</div>}
        </div>
      )}
    </div>
  );
}
