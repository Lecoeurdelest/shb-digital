// App.jsx — WorkspaceApp: ráp Board (sidebar | chat | canvas). Data từ seed, không mô phỏng chạy.
function useReady() {
  const ok = () => window.DEG && window.DEG.T && window.DEG.shared && window.DEG.cards && window.DEG.chat && window.DEG.lobby && window.DEG.seed && window.THREE;
  const [ready, setReady] = React.useState(ok());
  React.useEffect(() => {
    if (ready) return;
    const t = setInterval(() => { if (ok()) { setReady(true); clearInterval(t); } }, 80);
    return () => clearInterval(t);
  }, []);
  return ready;
}

function WorkspaceApp() {
  const ready = useReady();
  if (!ready) return <div style={{ height: '100vh', display: 'grid', placeItems: 'center', background: '#1a1917', color: '#544e45', fontFamily: "'Be Vietnam Pro',sans-serif", fontSize: 13 }}>Đang nạp components…</div>;
  return <Board />;
}

function Board() {
  const T = window.DEG.T;
  const seed = window.DEG.seed;
  const { ConversationSidebar, ChatPane, SubAgentView } = window.DEG.chat;
  const { CardRenderer } = window.DEG.cards;
  const { LobbyRoom3D } = window.DEG.lobby;
  const { Btn, Toast, Pill } = window.DEG.shared;

  const [snap, setSnap] = React.useState('pending');     // trạng thái ca (xem UI, không mô phỏng)
  const [activeConv, setActiveConv] = React.useState('c1');
  const [focus, setFocus] = React.useState('planner');   // planner | sub role
  const [tab, setTab] = React.useState('lobby');         // lobby | work
  const [extraMsgs, setExtraMsgs] = React.useState([]);  // tin user gõ thêm
  const [subMsgs, setSubMsgs] = React.useState({});      // nhắn riêng sub
  const [agentOv, setAgentOv] = React.useState({});      // override (dừng sub)
  const [decision, setDecision] = React.useState(null);  // duyệt/từ chối phiếu
  const [amount, setAmount] = React.useState(5);
  const [toasts, setToasts] = React.useState([]);

  const S = seed.snapshots[snap];
  const P = seed.snapshots.pending;
  const agents = { ...S.agents, ...agentOv };

  const toast = (text, color) => {
    const id = Math.random();
    setToasts(ts => [...ts, { id, text, color }]);
    setTimeout(() => setToasts(ts => ts.filter(t => t.id !== id)), 4000);
  };
  const switchSnap = k => { setSnap(k); setAgentOv({}); setExtraMsgs([]); setDecision(null); setFocus('planner'); };

  // messages: snapshot done kế thừa pending + resolve
  let messages = S.messages || P.messages.map(m => m.kind === 'pending' ? { ...m, tone: 'pass', text: '✓ Phiếu #17 đã duyệt — ops_disburse chạy thật → biên nhận #TX-88412' } : m);
  if (decision) messages = messages.map(m => m.kind === 'pending' ? { ...m, tone: decision === 'ok' ? 'pass' : 'fail', text: decision === 'ok' ? '✓ Phiếu #17 đã duyệt — ops_disburse chạy thật → biên nhận #TX-88412' : '✗ Phiếu #17 bị từ chối — Main dừng ca, RM được notify kèm lý do' } : m);
  messages = [...messages, ...extraMsgs];

  // cards: done kế thừa pending + phiếu đã dùng + memo
  let cards = S.cards || P.cards.map(c => c.type === 'approval' ? { ...c, status: { label: '✓ ĐÃ DÙNG', tone: 'pass' }, payload: { ...c.payload, state: 'approved', note: 'Duyệt bởi admin · ops_disburse retry khớp payload-hash → biên nhận #TX-88412 · phiếu single-use' } } : c);
  if (S.extraCard) cards = [...cards, S.extraCard];
  if (decision) cards = cards.map(c => c.type === 'approval' ? { ...c, status: decision === 'ok' ? { label: '✓ ĐÃ DÙNG', tone: 'pass' } : { label: '✗ TỪ CHỐI', tone: 'fail' }, payload: { ...c.payload, state: decision === 'ok' ? 'approved' : 'rejected' } } : c);

  const deptBadges = ['credit', 'legal', 'products', 'ops'].map(k => ({
    dept: T.roleMeta[k].name.toUpperCase(),
    tone: T.agentTone[agents[k] || 'idle'],
    val: { idle: '— chờ', run: '● Đang', done: '✓ Xong', warn: '⚠ Flag', err: '✗ Hủy' }[agents[k] || 'idle']
  }));

  const stopSub = role => {
    setAgentOv(o => ({ ...o, [role]: 'err' }));
    toast(`✗ Đã hủy sub ${T.roleMeta[role].name} — event failed("user hủy") đánh thức Main (§4.2)`, T.fail);
  };
  const sendMain = txt => { setExtraMsgs(m => [...m, { kind: 'user', text: txt }]); };
  const sendSub = (role, txt) => {
    setSubMsgs(m => ({ ...m, [role]: [...(m[role] || []), { who: 'user', text: txt }] }));
    setTimeout(() => setSubMsgs(m => ({ ...m, [role]: [...(m[role] || []), { who: 'sub', text: 'Đã ghi nhận — lưu ý sẽ gộp vào kết quả bàn giao Main (§3).' }] })), 800);
  };
  const jumpCite = anchor => {
    setTab('work');
    setTimeout(() => {
      const elx = document.getElementById(`card-${anchor}`);
      if (elx) { elx.style.boxShadow = '0 0 0 2px #d97757'; const p = elx.closest('[data-scroll]'); if (p) p.scrollTop = elx.offsetTop - 80; setTimeout(() => { elx.style.boxShadow = 'none'; }, 1500); }
    }, 60);
  };
  const decide = ok => { setDecision(ok ? 'ok' : 'no'); toast(ok ? '✓ Phiếu #17 duyệt — event resume Main' : '✗ Phiếu #17 từ chối — Main dừng ca', ok ? T.pass : T.fail); };
  const whatif = () => { sendMain(`Thử lại với ${String(amount).replace('.', ',')} tỷ, kỳ hạn 60 tháng.`); toast('Câu chat what-if đã gửi tới Main — Main sẽ tự re-dispatch (mock không mô phỏng chạy)', T.acc); };

  const canvasPending = cards.some(c => c.type === 'approval' && c.payload.state === 'pending') && !decision;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', minWidth: 1360, background: T.bg, color: T.tx, fontFamily: T.font, overflow: 'hidden' }}>
      {/* topbar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '0 16px', height: 50, borderBottom: `1px solid ${T.bd}`, background: T.p1, flex: 'none' }}>
        <div style={{ width: 26, height: 26, borderRadius: 7, background: T.acc, display: 'grid', placeItems: 'center', fontWeight: 800, fontSize: 13, color: T.bg }}>G</div>
        <div style={{ fontWeight: 700, fontSize: 13.5 }}>Digital Expert Guild</div>
        <div style={{ fontSize: 10.5, color: T.mute }}>Workspace v2 · component build</div>
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 10.5, color: T.mute }}>Trạng thái ca:</span>
        <div style={{ display: 'flex', gap: 2, background: T.bg2, border: `1px solid ${T.bd}`, borderRadius: 9, padding: 3 }}>
          {Object.entries(seed.snapshots).map(([k, v]) => (
            <div key={k} onClick={() => switchSnap(k)} style={{ padding: '5px 12px', borderRadius: 7, fontSize: 11, fontWeight: 600, cursor: 'pointer', background: snap === k ? T.p3 : 'transparent', color: snap === k ? T.tx : T.mute }}>{v.label}</div>
          ))}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11.5, color: T.dim, fontWeight: 500 }}>
          <span style={{ width: 24, height: 24, borderRadius: '50%', background: T.p3, display: 'grid', placeItems: 'center', fontSize: 10, fontWeight: 700, color: T.acc }}>L</span>Lan · RM
        </div>
      </div>

      <div style={{ display: 'flex', flex: 1, minHeight: 0 }}>
        <ConversationSidebar convs={seed.convs} convStatus={S.convStatus} activeId={activeConv} onOpen={setActiveConv} onNew={() => toast('Ca mới — mock chỉ hiển thị ca Gỗ Việt Phát', T.acc)} />

        {/* khung giữa: chat Main hoặc view sub */}
        <div style={{ width: 420, flex: 'none', borderRight: `1px solid ${T.bd}`, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
          {focus === 'planner'
            ? <ChatPane messages={messages} agents={agents} showProgress={S.showProgress} onSend={sendMain} onCite={jumpCite} />
            : <SubAgentView role={focus} status={agents[focus] || 'idle'} traces={S.traces[focus]} msgs={subMsgs[focus]} onBack={() => setFocus('planner')} onStop={() => stopSub(focus)} onSend={t => sendSub(focus, t)} />}
        </div>

        {/* canvas */}
        <div style={{ flex: 1, minWidth: 0, background: T.bg2, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ flex: 'none', display: 'flex', gap: 2, padding: '10px 16px 0' }}>
            {[['lobby', '🏛 Lobby — đội làm việc'], ['work', `▦ Công việc chi tiết${cards.length ? ` (${cards.length})` : ''}`]].map(([k, label]) => (
              <div key={k} onClick={() => setTab(k)} style={{ padding: '7px 15px', borderRadius: '9px 9px 0 0', fontSize: 11.5, fontWeight: 600, cursor: 'pointer', background: tab === k ? T.bg : 'transparent', color: tab === k ? T.tx : T.mute, border: `1px solid ${tab === k ? T.bd : 'transparent'}`, borderBottom: 'none' }}>{label}</div>
            ))}
          </div>

          {tab === 'lobby' && (
            <div style={{ flex: 1, position: 'relative', margin: '0 16px 16px', background: `radial-gradient(70% 55% at 50% 78%, rgba(217,119,87,.06), transparent), ${T.bg}`, border: `1px solid ${T.bd}`, borderRadius: '0 14px 14px 14px', overflow: 'hidden' }}>
              <LobbyRoom3D agents={agents} focus={focus} onSelect={setFocus} />
              <div style={{ position: 'absolute', left: 0, right: 0, bottom: 10, textAlign: 'center', fontSize: 10, color: T.faint, pointerEvents: 'none' }}>Click Main hoặc 1 sub để mở conversation của nó ở khung giữa — xem trace · nhắn · ⏹ dừng</div>
              <div style={{ position: 'absolute', top: 12, left: 14, display: 'flex', gap: 6 }}>
                {Object.entries(T.roleMeta).map(([k, m]) => {
                  const tone = T.agentTone[agents[k] || 'idle'];
                  const [c, bg] = T.tone[tone];
                  return <div key={k} onClick={() => setFocus(k)} style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '4px 9px', borderRadius: 12, fontSize: 10, fontWeight: 600, background: bg, color: c, cursor: 'pointer', border: focus === k ? `1px solid ${T.acc}` : '1px solid transparent' }}>{m.icon} {m.name}</div>;
                })}
              </div>
            </div>
          )}

          {tab === 'work' && (
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
              {/* what-if = câu chat (§4.3) */}
              <div style={{ flex: 'none', margin: '14px 16px 0', background: 'linear-gradient(135deg, rgba(217,119,87,.14), rgba(217,119,87,.04))', border: '1.5px solid rgba(217,119,87,.4)', borderRadius: 12, padding: '12px 16px', display: 'flex', alignItems: 'center', gap: 16 }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: T.acc, letterSpacing: '.06em' }}>⭐ WHAT-IF</span>
                <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontSize: 11, fontWeight: 500, color: T.dim }}>Số tiền vay</span>
                  <input type="range" min={3} max={8} step={0.5} value={amount} onChange={e => setAmount(parseFloat(e.target.value))} style={{ flex: 1, maxWidth: 220, accentColor: T.acc }} />
                  <span style={{ font: `700 14px ${T.mono}`, color: T.acc }}>{String(amount).replace('.', ',')} tỷ</span>
                </div>
                <Btn onClick={whatif} style={{ boxShadow: '0 3px 12px rgba(217,119,87,.3)' }}>⟳ Gửi Main tính lại</Btn>
              </div>
              {canvasPending && (
                <div style={{ flex: 'none', margin: '12px 16px 0', display: 'flex', alignItems: 'center', gap: 12, background: 'rgba(221,169,74,.07)', border: '1.5px solid rgba(221,169,74,.4)', borderRadius: 12, padding: '11px 15px' }}>
                  <span style={{ fontSize: 15 }}>⏸</span>
                  <div style={{ flex: 1, fontSize: 12, fontWeight: 700, color: T.warn }}>Phiếu #17 chờ phê duyệt — ops_disburse(5 tỷ) <span style={{ fontWeight: 400, color: T.mute, fontSize: 10.5 }}>· alert 📤 Discord</span></div>
                  <Btn kind="ok" onClick={() => decide(true)} style={{ padding: '7px 14px' }}>✓ Duyệt</Btn>
                  <Btn kind="danger" onClick={() => decide(false)} style={{ padding: '7px 14px' }}>✗ Từ chối</Btn>
                </div>
              )}
              <div data-scroll style={{ flex: 1, overflowY: 'auto', padding: '14px 16px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, alignContent: 'start' }}>
                {cards.length === 0 && <div style={{ gridColumn: '1/-1', textAlign: 'center', color: T.faint, fontSize: 12, padding: '60px 0' }}>▦ Sản phẩm công việc sẽ hiện ở đây khi đội chạy (đổi "Trạng thái ca" trên topbar để xem)</div>}
                {cards.map(c => <CardRenderer key={c.id} card={c} deptBadges={deptBadges} onDecide={c.type === 'approval' && !decision && snap === 'pending' ? decide : null} />)}
              </div>
            </div>
          )}
        </div>
      </div>
      <Toast items={toasts} />
    </div>
  );
}

module.exports = { WorkspaceApp };
