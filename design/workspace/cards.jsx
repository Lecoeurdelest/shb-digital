// cards.jsx — 7 card-type generic: render theo LOẠI phong bì, không theo ca (N5)
window.DEG = window.DEG || {};

function CardFrame({ card, children, onAnchor }) {
  const T = window.DEG.T;
  const st = card.status || { label: '', tone: 'idle' };
  const [c] = T.tone[st.tone] || T.tone.idle;
  const warnBd = st.tone === 'warn' ? 'rgba(221,169,74,.3)' : T.bd;
  return (
    <div id={`card-${card.id}`} ref={onAnchor} style={{ background: T.p1, border: `1px solid ${warnBd}`, borderRadius: 12, overflow: 'hidden', animation: 'deg-fadein .4s', gridColumn: ['case_file', 'approval', 'document'].includes(card.type) ? '1/-1' : 'auto' }}>
      <div style={{ padding: '10px 14px', borderBottom: `1px solid ${T.bd}`, display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 11.5, fontWeight: 700, color: T.tx }}>{card.title}</span>
        <span style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 10, fontWeight: 600, color: c }}>
          {st.live && <span style={{ width: 6, height: 6, borderRadius: '50%', background: c, boxShadow: `0 0 5px ${c}`, animation: 'deg-pulse 1.2s infinite' }} />}
          {st.label}
        </span>
      </div>
      {children}
    </div>
  );
}

const Shimmer = ({ w }) => <div style={{ height: 11, borderRadius: 6, width: w, background: 'linear-gradient(90deg,#2a2825 25%,#332f2b 50%,#2a2825 75%)', backgroundSize: '200px 100%', animation: 'deg-shimmer 1.4s infinite linear' }} />;
function SkeletonCard() { return <div style={{ padding: 14, display: 'flex', flexDirection: 'column', gap: 9 }}><Shimmer w="80%" /><Shimmer w="55%" /><Shimmer w="70%" /></div>; }

function CaseFileCard({ payload, deptBadges }) {
  const T = window.DEG.T;
  return (
    <div style={{ padding: '12px 14px', display: 'flex', alignItems: 'center', gap: 14 }}>
      <div style={{ width: 38, height: 38, borderRadius: 10, background: T.p3, display: 'grid', placeItems: 'center', fontSize: 15, fontWeight: 700, color: T.acc }}>{payload.name.split(' ').slice(-2).map(w => w[0]).join('')}</div>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 13.5, fontWeight: 700, color: T.tx }}>{payload.name}</div>
        <div style={{ fontSize: 10.5, color: T.mute }}>{payload.sub}</div>
      </div>
      <div style={{ display: 'flex', gap: 7 }}>
        {(deptBadges || []).map(b => {
          const [c, bg, bd] = window.DEG.T.tone[b.tone];
          return <div key={b.dept} style={{ textAlign: 'center', padding: '5px 11px', borderRadius: 9, background: bg, border: `1px solid ${bd}` }}>
            <div style={{ fontSize: 9, fontWeight: 600, color: T.mute }}>{b.dept}</div>
            <div style={{ fontSize: 11, fontWeight: 700, color: c }}>{b.val}</div>
          </div>;
        })}
      </div>
    </div>
  );
}

function MetricCard({ payload }) {
  const T = window.DEG.T;
  return (
    <div style={{ padding: '8px 14px 12px', display: 'grid', gridTemplateColumns: '1fr auto auto', gap: '5px 14px', alignItems: 'center' }}>
      {payload.rows.map(r => (
        <React.Fragment key={r.name}>
          <span style={{ fontSize: 11.5, color: T.dim, paddingTop: 5 }}>{r.name} <span style={{ color: T.faint }}>{r.hint}</span></span>
          <span style={{ font: `700 13px ${T.mono}`, color: T.tx, paddingTop: 5 }}>{r.val}{r.delta && <span style={{ color: T.pass, fontSize: 10 }}> {r.delta}</span>}</span>
          <span style={{ fontSize: 11.5, color: r.ok ? T.pass : T.fail, paddingTop: 5 }}>{r.ok ? '✓ Đạt' : '✗'} <span style={{ font: `500 9px ${T.mono}`, color: T.run }}>{r.src}</span></span>
        </React.Fragment>
      ))}
    </div>
  );
}

function ChecklistCard({ payload }) {
  const T = window.DEG.T;
  const M = { pass: ['✓', T.pass], warn: ['⚠', T.warn], fail: ['✗', T.fail] };
  return (
    <div style={{ padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 7 }}>
      {payload.items.map((it, i) => {
        const [mark, c] = M[it.state];
        const flag = it.state !== 'pass';
        return (
          <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', fontSize: 11.5, color: T.dim, borderRadius: 8, padding: flag ? '7px 9px' : 0, margin: flag ? '2px -2px 0' : 0, background: flag ? 'rgba(221,169,74,.08)' : 'transparent', border: flag ? '1px solid rgba(221,169,74,.25)' : '1px solid transparent' }}>
            <span style={{ color: c }}>{mark}</span>
            <span style={{ color: flag ? T.tx : T.dim }}>{it.text}{it.note && <><br /><span style={{ fontSize: 10, color: T.mute }}>{it.note}</span></>}</span>
          </div>
        );
      })}
    </div>
  );
}

function OptionsCard({ payload }) {
  const T = window.DEG.T;
  return (
    <div style={{ padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 6 }}>
      {payload.opts.map((o, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 10px', borderRadius: 8, fontSize: 11, background: o.rec ? T.accBg : 'transparent', border: `1px solid ${o.rec ? 'rgba(217,119,87,.35)' : 'transparent'}` }}>
          <span style={{ color: o.rec ? T.acc : T.faint }}>{o.rec ? '★' : '○'}</span>
          <span style={{ flex: 1, fontWeight: o.rec ? 600 : 400, color: o.rec ? T.tx : T.dim }}>{o.name}</span>
          <span style={{ font: `700 12px ${T.mono}`, color: o.rec ? T.acc : T.dim }}>{o.rate}</span>
          <span style={{ color: T.mute }}>{o.term}</span>
        </div>
      ))}
    </div>
  );
}

function TimelineCard({ payload }) {
  const T = window.DEG.T;
  return (
    <div style={{ padding: '12px 14px' }}>
      {payload.steps.map((s, i) => (
        <div key={i} style={{ display: 'flex', gap: 11 }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <div style={{ width: 22, height: 22, borderRadius: '50%', display: 'grid', placeItems: 'center', fontSize: 10, fontWeight: 700, flex: 'none', background: s.gate ? 'rgba(221,169,74,.18)' : T.p2, color: s.gate ? T.warn : T.dim, border: `1px solid ${s.gate ? 'rgba(221,169,74,.4)' : T.bd}` }}>{i + 1}</div>
            {i < payload.steps.length - 1 && <div style={{ width: 2, flex: 1, minHeight: 14, background: T.p2 }} />}
          </div>
          <div style={{ paddingBottom: 12 }}>
            <div style={{ fontSize: 11.5, fontWeight: 600, color: T.tx }}>{s.text}</div>
            <div style={{ fontSize: 10, color: T.mute, marginTop: 1 }}>{s.note}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

function ApprovalCard({ payload, onDecide }) {
  const T = window.DEG.T;
  const { Btn, Pill } = window.DEG.shared;
  const st = payload.state; // pending | approved | rejected
  return (
    <div style={{ padding: '12px 14px', display: 'flex', alignItems: 'center', gap: 12 }}>
      <span style={{ fontSize: 17 }}>{payload.icon}</span>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: T.tx }}>{payload.text}</div>
        <div style={{ fontSize: 10.5, color: T.mute, marginTop: 2 }}>{payload.note}</div>
      </div>
      {st === 'pending' && onDecide && <>
        <Btn kind="ok" onClick={() => onDecide(true)} style={{ padding: '7px 14px' }}>✓ Duyệt</Btn>
        <Btn kind="danger" onClick={() => onDecide(false)} style={{ padding: '7px 14px' }}>✗ Từ chối</Btn>
      </>}
      {st === 'pending' && !onDecide && <Pill tone="warn">CHỜ DUYỆT</Pill>}
      {st === 'approved' && <Pill tone="pass">ĐÃ DUYỆT · PHIẾU ĐÃ DÙNG</Pill>}
      {st === 'rejected' && <Pill tone="fail">TỪ CHỐI</Pill>}
    </div>
  );
}

function DocumentCard({ payload }) {
  const T = window.DEG.T;
  const { Btn } = window.DEG.shared;
  return (
    <div style={{ padding: '14px 18px' }}>
      <div style={{ background: T.tx, color: T.p2, borderRadius: 8, padding: '18px 20px', fontFamily: 'Georgia,serif' }}>
        <div style={{ textAlign: 'center', fontSize: 10, letterSpacing: '.1em', color: T.mute }}>{payload.org}</div>
        <div style={{ textAlign: 'center', fontSize: 14, fontWeight: 700, margin: '8px 0 12px' }}>{payload.docTitle}</div>
        <div style={{ fontSize: 11, lineHeight: 1.7 }}>
          {payload.fields.map(([k, v]) => <div key={k}><b>{k}:</b> {v}</div>)}
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 16, fontSize: 10, color: T.mute }}>
          <span>Lập bởi: {payload.by}</span>
          <span style={{ textAlign: 'center' }}>CÁN BỘ THẨM ĐỊNH<br /><br />(đã ký số)</span>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
        <Btn style={{ padding: '7px 15px', fontSize: 11 }}>↓ Export PDF</Btn>
        <Btn kind="ghost" style={{ padding: '7px 15px', fontSize: 11 }}>Gửi cấp phê duyệt</Btn>
      </div>
    </div>
  );
}

// CardRenderer — canvas cố định, phong bì là input
function CardRenderer({ card, deptBadges, onDecide }) {
  const body = {
    skeleton: <SkeletonCard />,
    case_file: <CaseFileCard payload={card.payload} deptBadges={deptBadges} />,
    metric: <MetricCard payload={card.payload} />,
    checklist: <ChecklistCard payload={card.payload} />,
    options: <OptionsCard payload={card.payload} />,
    timeline: <TimelineCard payload={card.payload} />,
    approval: <ApprovalCard payload={card.payload} onDecide={onDecide} />,
    document: <DocumentCard payload={card.payload} />
  }[card.type] || <div style={{ padding: 14, color: '#7d766a', fontSize: 11 }}>Loại card chưa hỗ trợ: {card.type}</div>;
  return <CardFrame card={card}>{body}</CardFrame>;
}

window.DEG.cards = { CardRenderer, CardFrame };
const Register = () => null;
module.exports = { Register };
