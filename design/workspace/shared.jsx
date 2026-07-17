// shared.jsx — theme token + primitive dùng chung
window.DEG = window.DEG || {};

const T = {
  bg: '#1a1917', bg2: '#161514', p1: '#211f1d', p2: '#2a2825', p3: '#332f2b',
  bd: '#37332f', bd2: '#48423b',
  tx: '#f2efe8', dim: '#b0a99d', mute: '#7d766a', faint: '#544e45',
  acc: '#d97757', accBg: 'rgba(217,119,87,.16)',
  run: '#5fb2c9', pass: '#82b878', fail: '#e0705f', warn: '#dda94a', main: '#b98cd9',
  font: "'Be Vietnam Pro',system-ui,sans-serif", mono: 'ui-monospace,Menlo,monospace'
};
// tone → [màu chữ, nền dim, viền]
T.tone = {
  idle: [T.faint, T.p1, T.bd],
  run: [T.run, 'rgba(95,178,201,.12)', 'rgba(95,178,201,.5)'],
  pass: [T.pass, 'rgba(130,184,120,.1)', 'rgba(130,184,120,.4)'],
  warn: [T.warn, 'rgba(221,169,74,.1)', 'rgba(221,169,74,.4)'],
  fail: [T.fail, 'rgba(224,112,95,.1)', 'rgba(224,112,95,.4)'],
  main: [T.main, 'rgba(185,140,217,.15)', 'rgba(185,140,217,.4)']
};
T.agentTone = { idle: 'idle', run: 'run', done: 'pass', warn: 'warn', err: 'fail' };
T.roleMeta = {
  planner: { name: 'Main', icon: '◆', desc: 'điều phối · hòa giải · tổng hợp' },
  credit: { name: 'Tín dụng', icon: '🧮', desc: 'DSCR · LTV · CIC' },
  legal: { name: 'Pháp chế', icon: '⚖', desc: 'giấy tờ · quy định' },
  products: { name: 'Sản phẩm', icon: '📦', desc: 'catalog gói vay' },
  ops: { name: 'Vận hành', icon: '⚙', desc: 'quy trình · disburse' }
};

function StatusDot({ tone, glow }) {
  const c = T.tone[tone][0];
  return <span style={{ width: 7, height: 7, borderRadius: '50%', background: c, boxShadow: glow ? `0 0 6px ${c}` : 'none', display: 'inline-block', flex: 'none' }} />;
}

function Pill({ tone = 'idle', children, style }) {
  const [c, bg] = T.tone[tone];
  return <span style={{ padding: '3px 10px', borderRadius: 12, fontSize: 10.5, fontWeight: 700, background: bg, color: c, whiteSpace: 'nowrap', ...style }}>{children}</span>;
}

function Btn({ kind = 'primary', onClick, children, style }) {
  const S = {
    primary: { background: T.acc, color: T.bg, border: 'none' },
    ghost: { background: 'none', color: T.dim, border: `1px solid ${T.bd2}` },
    danger: { background: 'none', color: T.fail, border: `1px solid rgba(224,112,95,.4)` },
    ok: { background: T.pass, color: T.bg, border: 'none' }
  }[kind];
  return <div onClick={onClick} style={{ padding: '8px 16px', borderRadius: 9, fontSize: 12, fontWeight: 700, cursor: 'pointer', textAlign: 'center', userSelect: 'none', ...S, ...style }}>{children}</div>;
}

function Toast({ items }) {
  return (
    <div style={{ position: 'fixed', top: 60, right: 16, display: 'flex', flexDirection: 'column', gap: 8, zIndex: 99 }}>
      {items.map(t => (
        <div key={t.id} style={{ background: T.p2, border: `1px solid ${T.bd2}`, borderLeft: `3px solid ${t.color || T.acc}`, borderRadius: 10, padding: '11px 15px', fontSize: 11.5, fontWeight: 500, color: T.tx, boxShadow: '0 8px 24px rgba(0,0,0,.5)', maxWidth: 320, animation: 'deg-fadein .3s' }}>{t.text}</div>
      ))}
    </div>
  );
}

window.DEG.T = T;
window.DEG.shared = { StatusDot, Pill, Btn, Toast };
const Register = () => null;
module.exports = { Register };
