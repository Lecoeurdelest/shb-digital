// chat.jsx — sidebar hội thoại + chat Main + view giám sát sub
window.DEG = window.DEG || {};

function ConversationSidebar({ convs, convStatus, activeId, onOpen, onNew }) {
  const T = window.DEG.T;
  const META = { new: ['Mới', 'idle'], run: ['Đang chạy', 'run'], wait: ['Chờ duyệt', 'warn'], done: ['Hoàn tất', 'pass'], err: ['Lỗi', 'fail'] };
  const { StatusDot } = window.DEG.shared;
  return (
    <div style={{ width: 230, flex: 'none', borderRight: `1px solid ${T.bd}`, background: T.p1, display: 'flex', flexDirection: 'column', padding: 12, gap: 4, overflowY: 'auto' }}>
      <div onClick={onNew} style={{ padding: '9px 12px', borderRadius: 8, background: T.accBg, color: T.acc, fontWeight: 600, fontSize: 12, textAlign: 'center', marginBottom: 10, border: '1px solid rgba(217,119,87,.3)', cursor: 'pointer' }}>+ Ca mới</div>
      <div style={{ fontSize: 10, fontWeight: 600, color: T.faint, letterSpacing: '.08em', margin: '0 4px 6px' }}>HÔM NAY</div>
      {convs.map(c => {
        const [label, tone] = META[convStatus[c.id]] || META.new;
        const act = c.id === activeId;
        return (
          <div key={c.id} onClick={() => onOpen(c.id)} style={{ padding: '10px 12px', borderRadius: 8, cursor: 'pointer', background: act ? T.p2 : 'transparent', border: `1px solid ${act ? T.bd2 : 'transparent'}` }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: act ? T.tx : T.dim, marginBottom: 3 }}>{c.name}</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 10.5, color: T.mute }}>
              <StatusDot tone={tone} glow={tone === 'run'} />{label} · {c.time}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function ProgressChips({ agents }) {
  const T = window.DEG.T;
  const L = { idle: 'chờ', run: 'đang làm…', done: '✓', warn: '⚠ 1 flag', err: '✗ đã hủy' };
  return (
    <div style={{ flex: 'none', alignSelf: 'stretch', background: T.p1, border: `1px solid ${T.bd}`, borderRadius: 10, padding: '10px 13px', animation: 'deg-fadein .3s' }}>
      <div style={{ fontSize: 10, fontWeight: 600, color: T.faint, letterSpacing: '.08em', marginBottom: 8 }}>ĐỘI ĐANG LÀM VIỆC</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {Object.entries(T.roleMeta).map(([k, m]) => {
          const st = agents[k] || 'idle';
          const tone = k === 'planner' && st !== 'idle' ? 'main' : T.agentTone[st];
          const [c, bg] = T.tone[tone];
          return (
            <span key={k} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '4px 9px', borderRadius: 14, fontSize: 10.5, fontWeight: 500, background: bg, color: c }}>
              {st === 'run' && <span style={{ width: 6, height: 6, borderRadius: '50%', background: c, boxShadow: `0 0 5px ${c}`, animation: 'deg-pulse 1.2s infinite' }} />}
              {(k === 'planner' ? '◆ ' : '') + m.name} · {L[st]}
            </span>
          );
        })}
      </div>
    </div>
  );
}

function MessageBubble({ msg, onCite }) {
  const T = window.DEG.T;
  const base = { flex: 'none', animation: 'deg-fadein .3s' };
  if (msg.kind === 'user') return <div style={{ ...base, alignSelf: 'flex-end', maxWidth: '85%', background: T.p3, borderRadius: '14px 14px 4px 14px', padding: '10px 14px', fontSize: 12.5, lineHeight: 1.55, color: T.tx }}>{msg.text}</div>;
  if (msg.kind === 'ask') return (
    <div style={{ ...base, alignSelf: 'flex-start', maxWidth: '92%', background: 'rgba(185,140,217,.1)', border: '1px solid rgba(185,140,217,.3)', borderRadius: '4px 14px 14px 14px', padding: '10px 13px', fontSize: 12.5, lineHeight: 1.55, color: T.tx }}>
      <span style={{ fontSize: 10, fontWeight: 600, color: T.main }}>◆ MAIN HỎI LẠI</span><br />{msg.text}
    </div>
  );
  if (msg.kind === 'note') return <div style={{ ...base, alignSelf: 'center', fontSize: 10.5, color: T.mute, padding: '4px 12px', background: T.p1, borderRadius: 10 }}>{msg.text}</div>;
  if (msg.kind === 'pending') {
    const tone = msg.tone || 'warn';
    const [c, , bd] = T.tone[tone];
    return <div style={{ ...base, alignSelf: 'stretch', display: 'flex', alignItems: 'center', gap: 9, borderRadius: 10, padding: '10px 13px', fontSize: 11.5, fontWeight: 500, background: T.tone[tone][1], border: `1px solid ${bd}`, color: c }}>{msg.text}</div>;
  }
  if (msg.kind === 'answer') {
    const tone = msg.tone || 'pass';
    const [c, bg] = T.tone[tone];
    return (
      <div style={{ ...base, alignSelf: 'stretch', background: T.p1, border: `1px solid ${T.bd2}`, borderRadius: '4px 14px 14px 14px', overflow: 'hidden' }}>
        <div style={{ padding: '10px 14px', borderBottom: `1px solid ${T.bd}`, display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 10, fontWeight: 600, color: T.faint, letterSpacing: '.08em' }}>KẾT LUẬN</span>
          <span style={{ padding: '3px 10px', borderRadius: 12, fontSize: 11, fontWeight: 700, background: bg, color: c }}>{msg.verdict}</span>
        </div>
        <div style={{ padding: '11px 14px', fontSize: 12.5, lineHeight: 1.6, color: T.dim }}>
          {msg.body}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5, marginTop: 7 }}>
            {msg.cites.map(ct => (
              <span key={ct.label} onClick={() => onCite && onCite(ct.anchor)} style={{ color: T.tx, background: 'rgba(130,184,120,.12)', padding: '2px 8px', borderRadius: 5, fontWeight: 600, fontSize: 11.5, cursor: 'pointer' }}>{ct.label} ⓘ</span>
            ))}
          </div>
          <div style={{ marginTop: 9, paddingTop: 9, borderTop: `1px dashed ${T.bd}` }}><span style={{ fontSize: 10, fontWeight: 600, color: T.faint, letterSpacing: '.08em' }}>ĐIỀU KIỆN</span><div style={{ color: T.tx, marginTop: 3 }}>{msg.cond}</div></div>
          <div style={{ marginTop: 9, paddingTop: 9, borderTop: `1px dashed ${T.bd}` }}><span style={{ fontSize: 10, fontWeight: 600, color: T.faint, letterSpacing: '.08em' }}>BƯỚC TIẾP</span><div style={{ color: T.tx, marginTop: 3 }}>{msg.next}</div></div>
        </div>
        <div style={{ padding: '8px 14px', borderTop: `1px solid ${T.bd}`, font: `500 10px ${T.mono}`, color: T.mute }}>Nguồn: <span style={{ color: T.run }}>{msg.sources}</span></div>
      </div>
    );
  }
  return null;
}

function Composer({ placeholder, onSend }) {
  const T = window.DEG.T;
  const [v, setV] = React.useState('');
  const fire = () => { if (v.trim()) { onSend(v.trim()); setV(''); } };
  return (
    <div style={{ flex: 'none', padding: '12px 14px', borderTop: `1px solid ${T.bd}` }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, background: T.p1, border: `1px solid ${T.bd2}`, borderRadius: 12, padding: '10px 14px' }}>
        <input value={v} onChange={e => setV(e.target.value)} onKeyDown={e => e.key === 'Enter' && fire()} placeholder={placeholder}
          style={{ flex: 1, background: 'none', border: 'none', outline: 'none', color: T.tx, font: `400 12.5px ${T.font}` }} />
        <div onClick={fire} style={{ width: 28, height: 28, borderRadius: 8, background: T.acc, display: 'grid', placeItems: 'center', color: T.bg, fontWeight: 700, cursor: 'pointer' }}>↑</div>
      </div>
    </div>
  );
}

function ChatPane({ messages, agents, showProgress, onSend, onCite }) {
  const T = window.DEG.T;
  const scRef = React.useRef(null);
  React.useEffect(() => { if (scRef.current) scRef.current.scrollTop = scRef.current.scrollHeight; }, [messages, showProgress]);
  return (
    <>
      <div ref={scRef} style={{ flex: 1, overflowY: 'auto', padding: '16px 14px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {messages.map((m, i) => <MessageBubble key={i} msg={m} onCite={onCite} />)}
        {showProgress && <ProgressChips agents={agents} />}
      </div>
      <Composer placeholder="Hỏi tiếp về ca này…" onSend={onSend} />
    </>
  );
}

// View giám sát 1 sub: trace sống + nhắn + dừng (bàn giao chính thức vẫn qua Main — §3)
function SubAgentView({ role, status, traces, msgs, onBack, onStop, onSend }) {
  const T = window.DEG.T;
  const meta = T.roleMeta[role];
  const tone = T.agentTone[status];
  const [c, bg, bd] = T.tone[tone];
  const STL = { idle: 'Chờ việc — chưa được dispatch', run: '● Đang làm việc…', done: '✓ Hoàn tất — kết quả đã bàn giao Main', warn: '⚠ Hoàn tất — có flag', err: '✗ Đã hủy bởi user' }[status];
  const { Btn } = window.DEG.shared;
  const items = [...(traces || []).map(t => ({ ...t, isTrace: true })), ...(msgs || [])];
  return (
    <>
      <div style={{ flex: 'none', padding: '11px 14px', borderBottom: `1px solid ${T.bd}`, display: 'flex', alignItems: 'center', gap: 10, background: '#1d1c1a' }}>
        <div onClick={onBack} style={{ width: 26, height: 26, borderRadius: 8, border: `1px solid ${T.bd2}`, display: 'grid', placeItems: 'center', color: T.dim, cursor: 'pointer', fontSize: 13 }}>←</div>
        <div style={{ width: 32, height: 32, borderRadius: 9, display: 'grid', placeItems: 'center', fontSize: 15, background: bg, border: `1px solid ${bd}` }}>{meta.icon}</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 12.5, fontWeight: 700, color: T.tx }}>SUB {meta.name}</div>
          <div style={{ fontSize: 10, fontWeight: 600, color: c }}>{STL}</div>
        </div>
        {status === 'run' && <Btn kind="danger" onClick={onStop} style={{ padding: '7px 13px', fontSize: 11 }}>⏹ Dừng sub</Btn>}
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: 14, display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ flex: 'none', alignSelf: 'center', fontSize: 9.5, color: T.faint, padding: '3px 10px', border: `1px dashed ${T.bd}`, borderRadius: 9 }}>kênh giám sát — bàn giao chính thức vẫn qua Main (§3)</div>
        {items.length === 0 && <div style={{ flex: 'none', alignSelf: 'center', color: T.faint, fontSize: 11.5, padding: '26px 0' }}>Sub chưa có hoạt động trong ca này</div>}
        {items.map((si, i) => si.isTrace ? (
          <div key={i} style={{ flex: 'none', display: 'flex', alignItems: 'flex-start', gap: 8, background: T.p1, border: `1px solid ${T.p2}`, borderRadius: 9, padding: '8px 11px', animation: 'deg-fadein .3s' }}>
            <span style={{ padding: '2px 7px', borderRadius: 6, fontSize: 9, fontWeight: 700, border: `1px solid ${T.bd}`, color: T.mute, flex: 'none' }}>{si.kind}</span>
            <span style={{ flex: 1, fontSize: 11, lineHeight: 1.5, color: T.dim }}>{si.label}</span>
            <span style={{ font: `500 9px ${T.mono}`, color: T.faint, flex: 'none' }}>{si.time}</span>
          </div>
        ) : (
          <div key={i} style={{ flex: 'none', alignSelf: si.who === 'user' ? 'flex-end' : 'flex-start', maxWidth: '85%', background: si.who === 'user' ? T.p3 : T.p1, border: si.who === 'user' ? 'none' : `1px solid ${T.bd}`, borderRadius: si.who === 'user' ? '12px 12px 4px 12px' : '4px 12px 12px 12px', padding: '8px 12px', fontSize: 11.5, color: si.who === 'user' ? T.tx : T.dim, animation: 'deg-fadein .3s' }}>{si.text}</div>
        ))}
      </div>
      <Composer placeholder={`Nhắn riêng cho sub ${meta.name}…`} onSend={onSend} />
    </>
  );
}

window.DEG.chat = { ConversationSidebar, ChatPane, SubAgentView, ProgressChips, MessageBubble, Composer };
const Register = () => null;
module.exports = { Register };
