// Landing.tsx — mặt tiền định vị máy sơ thẩm + Middle Office (D-73/D-75).
import { useEffect, useState } from 'react';
import { Login } from '../Login';
import { ThemeToggle } from '../ThemeToggle';
import { conversationApi } from '../../api';
import type { AuthUser } from '../../types';
import './Landing.css';

interface BusinessArea { icon: string; name: string; color: string; desc: string; deliverable: string }

const WORKSTREAMS: Record<string, BusinessArea> = {
  coordination: { icon: '◆', name: 'Điều phối nghiệp vụ', color: '#b98cd9', desc: 'Tiếp nhận yêu cầu, phối hợp các mảng chuyên môn và tổng hợp kết quả để RM tiếp tục xử lý.', deliverable: 'Kết luận tổng hợp' },
  credit: { icon: '🧮', name: 'Tín dụng', color: '#5fb2c9', desc: 'Kiểm tra năng lực trả nợ, DSCR, LTV và thông tin tín dụng; mỗi chỉ số có ngưỡng và nguồn.', deliverable: 'Bảng chỉ số sơ thẩm' },
  legal: { icon: '⚖', name: 'Pháp chế & Tuân thủ', color: '#dda94a', desc: 'Rà soát giấy tờ thiếu, hết hạn và điều kiện cần hoàn tất trước giải ngân.', deliverable: 'Danh mục cần bổ sung' },
  products: { icon: '📦', name: 'Sản phẩm', color: '#82b878', desc: 'Đối chiếu mục đích, phân khúc và điều kiện để đề xuất phương án phù hợp.', deliverable: 'Phương án đề xuất' },
  ops: { icon: '⚙', name: 'Vận hành', color: '#d97757', desc: 'Lập lộ trình bàn giao; hành động nhạy cảm dừng ở phiếu chờ người có thẩm quyền.', deliverable: 'Lộ trình và phiếu duyệt' },
};

const STEPS = [
  { n: '1', icon: '💬', title: 'RM nhập yêu cầu nghiệp vụ', desc: 'Nêu nhu cầu vay, thông tin khách hàng và mục tiêu cần kiểm tra trong một Phiên xử lý.' },
  { n: '2', icon: '🗂', title: 'Kiểm tra dữ liệu đầu vào', desc: 'Đối chiếu khả năng trả nợ, thông tin tín dụng và giấy tờ; chỉ rõ nội dung còn thiếu.' },
  { n: '3', icon: '📋', title: 'Chuẩn bị sản phẩm công việc', desc: 'Bảng chỉ số, điều kiện, phương án và tờ trình được cập nhật kèm nguồn nghiệp vụ.' },
  { n: '4', icon: '🔒', title: 'Bàn giao đúng thẩm quyền', desc: 'RM tiếp tục hoàn thiện; hành động nhạy cảm dừng ở phiếu để người có thẩm quyền quyết định.' },
];

const CONTROLS = [
  { icon: '🗂', title: 'Phân tách thẩm quyền', desc: 'RM chuẩn bị và bàn giao; người có thẩm quyền giữ quyết định cuối đối với hành động nhạy cảm.' },
  { icon: '🔍', title: 'Nguồn và thời điểm', desc: 'Chỉ số nghiệp vụ đi cùng nguồn dữ liệu và thời điểm để người kiểm soát có thể đối chiếu.' },
  { icon: '⏸', title: 'Phanh phê duyệt', desc: 'Giải ngân và hành động ranh giới luôn dừng ở phiếu chờ duyệt, không thực thi ngoài quy trình.' },
  { icon: '📋', title: 'Nhật ký kiểm soát', desc: 'Các bước xử lý và quyết định được lưu để kiểm tra, truy vết và phục vụ hậu kiểm.' },
  { icon: '⚠', title: 'Cảnh báo thiếu dữ liệu', desc: 'Tài liệu thiếu, thông tin mâu thuẫn và điều kiện chưa đạt được nêu rõ trước khi bàn giao.' },
  { icon: '🔔', title: 'Thông báo bàn giao', desc: 'Phiếu chờ duyệt và kết quả hoàn tất được chuyển tới đúng người, không cần ngồi canh màn hình.' },
];

const MARQUEE = ['🧮 DSCR · LTV · CIC có nguồn', '⚖ Rà soát từng giấy tờ', '🔒 Giải ngân chờ người duyệt', '📋 Nhật ký kiểm soát', '⚡ Chuẩn bị tờ trình nhanh hơn', '🔔 Thông báo đúng người xử lý'];

interface Props {
  onSuccess: (user: AuthUser) => void;
  initialAuthOpen?: boolean;
  nextPath?: string;
}

export function Landing({ onSuccess, initialAuthOpen = false, nextPath }: Props) {
  const [authOpen, setAuthOpen] = useState(initialAuthOpen);

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
        <span className="lp-nav__brandblock">
          <span className="lp-nav__brand">BANK Digital</span>
          <span className="lp-nav__tagline">Sơ thẩm &amp; Middle Office</span>
        </span>
        <span className="lp-nav__spacer" />
        <a className="lp-nav__link" href="#agents">Năng lực nghiệp vụ</a>
        <a className="lp-nav__link" href="#how">Quy trình</a>
        <a className="lp-nav__link" href="#control">Kiểm soát</a>
        <ThemeToggle />
        <button type="button" className="lp-btn lp-btn--ghost" data-testid="landing-login" onClick={() => setAuthOpen(true)}>Đăng nhập</button>
        <button type="button" className="lp-btn lp-btn--primary" data-testid="landing-signup" onClick={() => setAuthOpen(true)}>Dùng thử</button>
      </nav>

      {/* HERO */}
      <header className="lp-hero">
        <div className="lp-hero__grid">
          <div>
            <div className="lp-badge"><span className="lp-badge__dot" />Sơ thẩm khoản vay phức tạp · có nguồn · có phanh · người duyệt</div>
            <h1 className="lp-hero__title">Từ yêu cầu của RM<br />đến tờ trình sơ thẩm<br /><span>có căn cứ.</span></h1>
            <p className="lp-hero__sub">Một Phiên xử lý phối hợp Tín dụng, Pháp chế, Sản phẩm và Vận hành để kiểm tra dữ liệu, chỉ ra nội dung thiếu và chuẩn bị bàn giao. Mọi con số có nguồn; quyết định cuối vẫn thuộc về con người.</p>
            <div className="lp-hero__cta">
              <button type="button" className="lp-btn lp-btn--primary lp-btn--lg" onClick={() => setAuthOpen(true)}>Bắt đầu xử lý →</button>
              <a className="lp-btn lp-btn--ghost lp-btn--lg" href="#how">Khám phá quy trình</a>
            </div>
            <div className="lp-hero__stats">
              <div><b>4 mảng</b><span>phối hợp xuyên suốt</span></div>
              <i />
              <div><b>Nguồn từng số</b><span>sẵn sàng đối chiếu</span></div>
              <i />
              <div><b className="lp-acc">0 tự tiện</b><span>giải ngân chờ người duyệt</span></div>
            </div>
          </div>
          <div className="lp-hero__stage">
            <div style={{ height: '100%', display: 'grid', placeItems: 'center', padding: 36 }}>
              <div className="lp-example" style={{ marginTop: 0 }}>
                <div className="lp-example__body">
                  <div className="lp-kicker lp-kicker--dim">SẢN PHẨM CÔNG VIỆC</div>
                  <div className="lp-example__text">
                    <b>Tờ trình sơ thẩm</b><br />DSCR 1,40 · LTV 62,5% · CIC nhóm 1<br />
                    <em className="warn">Thiếu xác nhận PCCC còn hiệu lực</em><br />
                    Khuyến nghị: <em className="ok">duyệt có điều kiện</em>
                  </div>
                </div>
              </div>
            </div>
            <div className="lp-hero__hint">Kết quả minh họa · quyết định thuộc người có thẩm quyền</div>
          </div>
        </div>
      </header>

      {/* MARQUEE */}
      <div className="lp-marquee"><div className="lp-marquee__track">{[...MARQUEE, ...MARQUEE].map((m, i) => <span key={i}>{m}</span>)}</div></div>

      {/* NĂNG LỰC NGHIỆP VỤ */}
      <section id="agents" className="lp-section">
        <div className="lp-section__head">
          <div className="lp-kicker">NĂNG LỰC NGHIỆP VỤ</div>
          <h2>Một quy trình xuyên suốt bốn mảng chuyên môn</h2>
          <p>RM nhận kết quả theo từng sản phẩm công việc, biết rõ nội dung đã kiểm tra, phần còn thiếu và bước bàn giao tiếp theo.</p>
        </div>
        <div className="lp-agents">
          {Object.values(WORKSTREAMS).map((a, i) => (
            <div className="lp-agent" key={a.name}>
              <span className="lp-agent__n">0{i + 1}</span>
              <span className="lp-agent__icon" style={{ color: a.color }}>{a.icon}</span>
              <span className="lp-agent__body">
                <span className="lp-agent__name" style={{ color: a.color }}>{a.name}</span>
                <span className="lp-agent__desc">{a.desc}</span>
              </span>
              <span className="lp-agent__tools">{a.deliverable}</span>
            </div>
          ))}
        </div>
      </section>

      {/* HOW */}
      <section id="how" className="lp-section lp-section--alt">
        <div className="lp-section__inner">
          <div className="lp-section__head">
            <div className="lp-kicker">CÁCH VẬN HÀNH</div>
            <h2>Từ yêu cầu nghiệp vụ đến bàn giao có căn cứ</h2>
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
              <div className="lp-kicker lp-kicker--dim">VÍ DỤ — KHOẢN VAY 5 TỶ</div>
              <div className="lp-example__text">
                "Gỗ Việt Phát vay 5 tỷ mở rộng xưởng…" → <em className="ok">DSCR 1,40 ✓</em> · <em className="ok">LTV 62,5% ✓</em> · <em className="warn">⚠ thiếu PCCC 2026</em> → <b>DUYỆT CÓ ĐIỀU KIỆN</b> · giải ngân <em className="warn">🔒 chờ người duyệt</em>
              </div>
            </div>
            <div className="lp-example__nums">
              <div><s>3–5 ngày</s><span>quy trình cũ · 4 phòng ban</span></div>
              <div><b>1 luồng</b><span>phối hợp + 1 lần duyệt</span></div>
            </div>
          </div>
        </div>
      </section>

      {/* CONTROL */}
      <section id="control" className="lp-section">
        <div className="lp-section__head">
          <div className="lp-kicker">NGÂN HÀNG KIỂM SOÁT ĐƯỢC</div>
          <h2>Mọi bước rõ trách nhiệm và có thể đối chiếu</h2>
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
        <h2>Sẵn sàng mở Phiên xử lý sơ thẩm?</h2>
        <p>Tài khoản RM để chuẩn bị và bàn giao; tài khoản quản lý để theo dõi phê duyệt.</p>
        <div className="lp-cta__row">
          <button type="button" className="lp-btn lp-btn--primary lp-btn--lg" onClick={() => setAuthOpen(true)}>Tạo tài khoản →</button>
          <button type="button" className="lp-btn lp-btn--ghost lp-btn--lg" onClick={() => setAuthOpen(true)}>Đăng nhập</button>
        </div>
      </section>

      {/* FOOTER */}
      <footer className="lp-footer">
        <span className="lp-logo lp-logo--sm">G</span>
        <span className="lp-footer__name">BANK Digital</span>
        <span className="lp-footer__note">· Hackathon #132</span>
        <span className="lp-nav__spacer" />
        <span className="lp-footer__note">Sơ thẩm · Middle Office · Phê duyệt</span>
      </footer>

      {/* AUTH MODAL — Login THẬT (user/pass + tab Đăng ký khách mới + nút Google khi server bật). */}
      {authOpen && (
        <div className="lp-modal" data-testid="landing-authmodal">
          <div className="lp-modal__overlay" onClick={() => setAuthOpen(false)} />
          <div className="lp-modal__card">
            <button type="button" className="lp-modal__close" aria-label="Đóng" onClick={() => setAuthOpen(false)}>✕</button>
            {/* Login tự lo mọi đường vào: user/pass · tab Đăng ký khách mới (T9-3) · nút Google (ẩn khi
               server tắt — gỡ signup-hint google cứng ở đây để khối Google ẩn TRỌN khi providers.google=false). */}
            <Login onSuccess={onSuccess} googleEnabled={googleEnabled} nextPath={nextPath} />
          </div>
        </div>
      )}
    </div>
  );
}
