// Landing.tsx — trang mặt tiền (design/Landing Page.dc.html — D-13) cho digital.tinhdev.com.
// Hero 3D = Lobby3D THẬT của app (chi nhánh BANK — "cửa sổ vào sản phẩm", người chốt 18/7 thay
// team3d capsule của mock). Auth modal = Login component thật (user/pass + Google PR #2) —
// KHÔNG form đăng ký email giả của mock (đăng ký = Google, khách mới tự tạo). Deviation ghi PR.
import { useEffect, useState } from 'react';
import { Login } from '../Login';
import { Lobby3D, type LobbyStatus } from '../Lobby3D';
import { ThemeToggle } from '../ThemeToggle';
import { conversationApi } from '../../api';
import type { AuthUser } from '../../types';
import './Landing.css';

interface AgentInfo { icon: string; name: string; color: string; desc: string; tools: string }

const AGENTS: Record<string, AgentInfo> = {
  planner: { icon: '◆', name: 'Main — Điều phối', color: '#b98cd9', desc: 'Không có domain riêng: decompose yêu cầu, giao việc, hòa giải mâu thuẫn giữa phòng ban, tổng hợp câu trả lời cuối.', tools: 'orch_dispatch · orch_merge' },
  credit: { icon: '🧮', name: 'Tín dụng', color: '#5fb2c9', desc: 'Thẩm định năng lực trả nợ: DSCR, LTV, tra CIC. Mọi chỉ số kèm ngưỡng và nguồn tool.', tools: 'calc_dscr · calc_ltv · check_cic' },
  legal: { icon: '⚖', name: 'Pháp chế & Tuân thủ', color: '#dda94a', desc: 'Soát hồ sơ pháp lý, phát hiện giấy tờ thiếu/hết hạn, gắn điều kiện trước giải ngân.', tools: 'check_documents · check_regulation' },
  products: { icon: '📦', name: 'Sản phẩm', color: '#82b878', desc: 'So sánh gói vay theo phân khúc và mục đích, đề xuất gói tối ưu kèm lãi suất từ catalog.', tools: 'get_products · match_package' },
  ops: { icon: '⚙', name: 'Vận hành', color: '#d97757', desc: 'Lập lộ trình thực thi. Hành động nhạy cảm (giải ngân) bị chặn ở tầng tool — tạo phiếu chờ người duyệt.', tools: 'ops_disburse 🔒 · get_status' },
};

// hero demo: đội đang "chạy ca" — Main + Tín dụng + Pháp chế run (icon nháy + beam), đúng cơ chế app
const HERO_AGENTS: Record<string, LobbyStatus> = { planner: 'run', credit: 'run', legal: 'run', products: 'idle', ops: 'idle' };

const STEPS = [
  { n: '1', icon: '💬', title: 'RM gõ yêu cầu tiếng Việt', desc: 'Một câu chat duy nhất. Thiếu thông tin? Main hỏi lại ngay trong hội thoại.' },
  { n: '2', icon: '🗂', title: 'Main chia việc', desc: 'Task-tree: Tín dụng chạy trước, Pháp chế chờ kết quả, Sản phẩm chạy song song.' },
  { n: '3', icon: '⚡', title: 'Đội chạy — nhìn thấy live', desc: 'Lobby 3D + canvas: từng phòng ban trả kết quả theo phong bì chuẩn, card sáng dần.' },
  { n: '4', icon: '🔒', title: 'Người duyệt bấm nút cuối', desc: 'Kết luận tổng hợp có nguồn từng con số. Giải ngân dừng ở phiếu phê duyệt — người quyết.' },
];

const CONTROLS = [
  { icon: '🗺', title: 'Live orchestration map', desc: 'Thấy realtime ai đang làm gì: node đổi màu, beam giao việc, task-tree với dependency.' },
  { icon: '🔍', title: 'Trace từng bước', desc: 'Mỗi quyết định có vết: agent nào, tool nào, input/output JSON — click là xem.' },
  { icon: '⏸', title: 'Human-approval gate', desc: 'Hành động ranh giới bị chặn ở tầng tool bằng phiếu payload-hash, single-use — không phải lời dặn trong prompt.' },
  { icon: '📋', title: 'Audit log append-only', desc: 'Mọi LLM call, tool call, quyết định người duyệt — kèm chi phí. Mọi con số click về nguồn.' },
  { icon: '🏆', title: 'Certify board', desc: 'Bảng điểm per-agent từ bộ test độc lập: chứng minh đúng bao nhiêu phần trăm trước khi lên môi trường thật.' },
  { icon: '🔔', title: 'Alert đa kênh', desc: 'Chờ-duyệt, ca xong, sự cố — bắn Discord, email, Zalo theo ma trận cấu hình. Không ai phải ngồi canh màn hình.' },
];

const MARQUEE = ['🧮 DSCR · LTV · CIC có nguồn tool', '⚖ Pháp chế soát từng giấy tờ', '🔒 Giải ngân chờ người duyệt', '📋 Audit log append-only', '⚡ 3–5 ngày → 4 phút', '📤 Alert Discord · Email · Zalo'];

export function Landing({ onSuccess }: { onSuccess: (user: AuthUser) => void }) {
  const [authOpen, setAuthOpen] = useState(false);
  const [heroFocus, setHeroFocus] = useState('planner');
  const pick = AGENTS[heroFocus] ?? AGENTS.planner;

  // PREFETCH providers NGAY khi Landing mount (không đợi mở modal) — chống flaky layout-shift T11-4:
  // fetch bắt đầu lúc page-load, user đọc hero vài giây trước khi bấm Đăng nhập → thường resolved
  // TRƯỚC khi modal mở → Login nhận googleEnabled đã biết → nút Google KHÔNG "nhảy vào" sau. undefined
  // = đang chờ (Login reserve chỗ), bool = resolved. Fail → false (fail-closed, nút ẩn).
  const [googleEnabled, setGoogleEnabled] = useState<boolean | undefined>(undefined);
  useEffect(() => {
    let alive = true;
    conversationApi.getAuthProviders()
      .then((p) => { if (alive) setGoogleEnabled(p.google); })
      .catch(() => { if (alive) setGoogleEnabled(false); });
    return () => { alive = false; };
  }, []);

  return (
    <div className="landing">
      {/* NAV */}
      <nav className="lp-nav">
        <span className="lp-logo">G</span>
        <span className="lp-nav__title">Digital Expert Guild</span>
        <span className="lp-nav__sub">Hội đồng Chuyên gia Số</span>
        <span className="lp-nav__spacer" />
        <a className="lp-nav__link" href="#agents">Đội chuyên gia</a>
        <a className="lp-nav__link" href="#how">Cách vận hành</a>
        <a className="lp-nav__link" href="#control">Kiểm soát</a>
        <ThemeToggle />
        <button type="button" className="lp-btn lp-btn--ghost" data-testid="landing-login" onClick={() => setAuthOpen(true)}>Đăng nhập</button>
        <button type="button" className="lp-btn lp-btn--primary" data-testid="landing-signup" onClick={() => setAuthOpen(true)}>Dùng thử</button>
      </nav>

      {/* HERO */}
      <header className="lp-hero">
        <div className="lp-hero__grid">
          <div>
            <div className="lp-badge"><span className="lp-badge__dot" />Multi-agent banking · có giám sát · có phanh · có bằng chứng</div>
            <h1 className="lp-hero__title">Một đội chuyên gia số.<br />Nghiệp vụ ngân hàng<br /><span>xong trong 4 phút.</span></h1>
            <p className="lp-hero__sub">RM gõ một yêu cầu tiếng Việt — Main chia việc cho Tín dụng, Pháp chế, Sản phẩm, Vận hành. Mọi con số có nguồn, hành động nhạy cảm chờ người duyệt.</p>
            <div className="lp-hero__cta">
              <button type="button" className="lp-btn lp-btn--primary lp-btn--lg" onClick={() => setAuthOpen(true)}>Bắt đầu miễn phí →</button>
              <a className="lp-btn lp-btn--ghost lp-btn--lg" href="#how">Xem cách vận hành</a>
            </div>
            <div className="lp-hero__stats">
              <div><b>4 phòng ban</b><span>chuyên sâu + 1 Main điều phối</span></div>
              <i />
              <div><b>100% có vết</b><span>trace · audit · nguồn từng số</span></div>
              <i />
              <div><b className="lp-acc">0 tự tiện</b><span>giải ngân chờ người duyệt</span></div>
            </div>
          </div>
          {/* 3D THẬT của app — cửa sổ vào sản phẩm */}
          <div className="lp-hero__stage">
            <Lobby3D agents={HERO_AGENTS} focus={heroFocus} onSelect={setHeroFocus} />
            <div className="lp-hero__chip" style={{ borderColor: pick.color }}>
              <span className="lp-hero__chip-icon">{pick.icon}</span>
              <div>
                <div className="lp-hero__chip-name" style={{ color: pick.color }}>{pick.name}</div>
                <div className="lp-hero__chip-desc">{pick.desc}</div>
              </div>
            </div>
            <div className="lp-hero__hint">click một nhân vật để xem vai trò</div>
          </div>
        </div>
      </header>

      {/* MARQUEE */}
      <div className="lp-marquee"><div className="lp-marquee__track">{[...MARQUEE, ...MARQUEE].map((m, i) => <span key={i}>{m}</span>)}</div></div>

      {/* AGENTS */}
      <section id="agents" className="lp-section">
        <div className="lp-section__head">
          <div className="lp-kicker">ĐỘI CHUYÊN GIA</div>
          <h2>Một Main điều phối — bốn phòng ban chuyên sâu</h2>
          <p>Hub-and-spoke: mọi bàn giao qua Main, không side-channel. Thêm nghiệp vụ mới = thêm tool + prompt — đội không đổi.</p>
        </div>
        <div className="lp-agents">
          {Object.values(AGENTS).map((a, i) => (
            <div className="lp-agent" key={a.name}>
              <span className="lp-agent__n">0{i + 1}</span>
              <span className="lp-agent__icon" style={{ color: a.color }}>{a.icon}</span>
              <span className="lp-agent__body">
                <span className="lp-agent__name" style={{ color: a.color }}>{a.name}</span>
                <span className="lp-agent__desc">{a.desc}</span>
              </span>
              <span className="lp-agent__tools">{a.tools}</span>
            </div>
          ))}
        </div>
      </section>

      {/* HOW */}
      <section id="how" className="lp-section lp-section--alt">
        <div className="lp-section__inner">
          <div className="lp-section__head">
            <div className="lp-kicker">CÁCH VẬN HÀNH</div>
            <h2>Từ một câu chat đến quyết định có bằng chứng</h2>
          </div>
          <div className="lp-steps">
            {STEPS.map((st) => (
              <div className="lp-step" key={st.n}>
                <span className="lp-step__n">{st.n}</span>
                <span className="lp-step__icon">{st.icon}</span>
                <div className="lp-step__title">{st.title}</div>
                <div className="lp-step__desc">{st.desc}</div>
              </div>
            ))}
          </div>
          <div className="lp-example">
            <div className="lp-example__body">
              <div className="lp-kicker lp-kicker--dim">VÍ DỤ THẬT — CA VAY 5 TỶ</div>
              <div className="lp-example__text">
                "Gỗ Việt Phát vay 5 tỷ mở rộng xưởng…" → <em className="ok">DSCR 1,40 ✓</em> · <em className="ok">LTV 62,5% ✓</em> · <em className="warn">⚠ thiếu PCCC 2026</em> → <b>DUYỆT CÓ ĐIỀU KIỆN</b> · giải ngân <em className="warn">🔒 chờ người duyệt</em>
              </div>
            </div>
            <div className="lp-example__nums">
              <div><s>3–5 ngày</s><span>quy trình cũ · 4 phòng ban</span></div>
              <div><b>4 phút</b><span>đội agent + 1 lần duyệt</span></div>
            </div>
          </div>
        </div>
      </section>

      {/* CONTROL */}
      <section id="control" className="lp-section">
        <div className="lp-section__head">
          <div className="lp-kicker">NGÂN HÀNG KIỂM SOÁT ĐƯỢC</div>
          <h2>Không phải hộp đen — mọi bước có vết</h2>
        </div>
        <div className="lp-controls">
          {CONTROLS.map((c) => (
            <div className="lp-control" key={c.title}>
              <span className="lp-control__icon">{c.icon}</span>
              <div className="lp-control__title">{c.title}</div>
              <div className="lp-control__desc">{c.desc}</div>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="lp-cta">
        <h2>Sẵn sàng gặp đội chuyên gia số?</h2>
        <p>Tài khoản RM để chạy ca — tài khoản Admin để thấy toàn bộ Control Tower.</p>
        <div className="lp-cta__row">
          <button type="button" className="lp-btn lp-btn--primary lp-btn--lg" onClick={() => setAuthOpen(true)}>Tạo tài khoản →</button>
          <button type="button" className="lp-btn lp-btn--ghost lp-btn--lg" onClick={() => setAuthOpen(true)}>Đăng nhập</button>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="lp-footer">
        <span className="lp-logo lp-logo--sm">G</span>
        <span className="lp-footer__name">Digital Expert Guild</span>
        <span className="lp-footer__note">· Hackathon #132</span>
        <span className="lp-nav__spacer" />
        <span className="lp-footer__note">Workspace · Control Tower</span>
      </footer>

      {/* AUTH MODAL — Login THẬT (user/pass + tab Đăng ký khách mới + nút Google khi server bật). */}
      {authOpen && (
        <div className="lp-modal" data-testid="landing-authmodal">
          <div className="lp-modal__overlay" onClick={() => setAuthOpen(false)} />
          <div className="lp-modal__card">
            <button type="button" className="lp-modal__close" aria-label="Đóng" onClick={() => setAuthOpen(false)}>✕</button>
            {/* Login tự lo mọi đường vào: user/pass · tab Đăng ký khách mới (T9-3) · nút Google (ẩn khi
               server tắt — gỡ signup-hint google cứng ở đây để khối Google ẩn TRỌN khi providers.google=false). */}
            <Login onSuccess={onSuccess} googleEnabled={googleEnabled} />
          </div>
        </div>
      )}
    </div>
  );
}
