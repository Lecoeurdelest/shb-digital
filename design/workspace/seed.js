// Seed data — "phong bì là input": đổi ca = đổi JSON, không sửa component.
// 4 snapshot trạng thái để xem UI (không mô phỏng chạy).
window.DEG = window.DEG || {};
window.DEG.seed = {
  convs: [
    { id: 'c1', name: 'Gỗ Việt Phát — vay 5 tỷ', time: '10:24' },
    { id: 'c2', name: 'Minh Long — LC 2 tỷ', time: '09:51' },
    { id: 'c3', name: 'Hộ KD Tân Phú — 800tr', time: '08:30' }
  ],
  snapshots: {
    new: {
      label: 'Mới', convStatus: { c1: 'new', c2: 'wait', c3: 'done' },
      agents: { planner: 'idle', credit: 'idle', legal: 'idle', products: 'idle', ops: 'idle' },
      messages: [
        { kind: 'user', text: 'Công ty TNHH Gỗ Việt Phát muốn vay 5 tỷ mở rộng xưởng, thế chấp nhà xưởng định giá 8 tỷ. Kiểm tra khả năng vay giúp tôi.' },
        { kind: 'ask', text: 'Mục đích vay là mở rộng nhà xưởng hiện tại hay xây mới? Điều này ảnh hưởng gói sản phẩm và điều kiện pháp lý.' }
      ],
      cards: [], traces: {}, showProgress: false
    },
    running: {
      label: 'Đang chạy', convStatus: { c1: 'run', c2: 'wait', c3: 'done' },
      agents: { planner: 'run', credit: 'run', legal: 'idle', products: 'run', ops: 'idle' },
      messages: [
        { kind: 'user', text: 'Công ty TNHH Gỗ Việt Phát muốn vay 5 tỷ mở rộng xưởng, thế chấp nhà xưởng định giá 8 tỷ. Kiểm tra khả năng vay giúp tôi.' },
        { kind: 'ask', text: 'Mục đích vay là mở rộng nhà xưởng hiện tại hay xây mới?' },
        { kind: 'user', text: 'Mở rộng xưởng hiện tại.' }
      ],
      cards: [
        { id: 'info', type: 'case_file', title: 'Hồ sơ ca — Case File', status: { label: 'CẬP NHẬT LIVE', tone: 'run', live: true }, payload: { name: 'Công ty TNHH Gỗ Việt Phát', sub: 'SME · Sản xuất gỗ · KH-2214 · Đề nghị: 5 tỷ / 60 tháng · TSBĐ: nhà xưởng 8 tỷ' } },
        { id: 'credit', type: 'skeleton', title: 'Thẩm định Tín dụng', status: { label: 'ĐANG XỬ LÝ', tone: 'run', live: true } },
        { id: 'products', type: 'skeleton', title: 'So sánh gói vay', status: { label: 'ĐANG XỬ LÝ', tone: 'run', live: true } }
      ],
      traces: {
        credit: [
          { kind: 'tool', label: 'calc_dscr(kh=KH-2214, vay=5 tỷ) → 1.40', time: '10:24:41' },
          { kind: 'tool', label: 'calc_ltv(collateral=8 tỷ) → 62.5%', time: '10:24:43' },
          { kind: 'think', label: 'Đang tra CIC…', time: '10:24:45' }
        ],
        products: [{ kind: 'tool', label: 'get_products(segment=SME) → 3 gói', time: '10:24:42' }]
      },
      showProgress: true
    },
    pending: {
      label: 'Chờ duyệt', convStatus: { c1: 'wait', c2: 'wait', c3: 'done' },
      agents: { planner: 'done', credit: 'done', legal: 'warn', products: 'done', ops: 'done' },
      messages: [
        { kind: 'user', text: 'Công ty TNHH Gỗ Việt Phát muốn vay 5 tỷ mở rộng xưởng, thế chấp nhà xưởng định giá 8 tỷ. Kiểm tra khả năng vay giúp tôi.' },
        { kind: 'ask', text: 'Mục đích vay là mở rộng nhà xưởng hiện tại hay xây mới?' },
        { kind: 'user', text: 'Mở rộng xưởng hiện tại.' },
        {
          kind: 'answer', verdict: 'DUYỆT CÓ ĐIỀU KIỆN', tone: 'warn',
          body: 'Hồ sơ đạt cả 3 chỉ tiêu tín dụng. Gói đề xuất: SME Mở rộng SX 8,2%/năm.',
          cites: [{ label: 'DSCR 1,40', anchor: 'credit' }, { label: 'LTV 62,5%', anchor: 'credit' }, { label: 'CIC nhóm 1', anchor: 'credit' }, { label: 'PCCC thiếu', anchor: 'legal' }],
          cond: 'Bổ sung giấy phép PCCC bản cập nhật 2026 trước giải ngân.',
          next: '1. Gửi KH bổ sung PCCC · 2. Trình phê duyệt hạn mức · 3. Giải ngân (chờ duyệt 🔒)',
          sources: 'calc_dscr · calc_ltv · check_cic · check_documents · get_products'
        },
        { kind: 'pending', tone: 'warn', text: '⏸ Yêu cầu trình phê duyệt đã gửi — chờ cấp có thẩm quyền duyệt · alert 📤 Discord' }
      ],
      cards: [
        { id: 'info', type: 'case_file', title: 'Hồ sơ ca — Case File', status: { label: '✓ ĐỦ 4 PHÒNG BAN', tone: 'pass' }, payload: { name: 'Công ty TNHH Gỗ Việt Phát', sub: 'SME · Sản xuất gỗ · KH-2214 · Đề nghị: 5 tỷ / 60 tháng · TSBĐ: nhà xưởng 8 tỷ' } },
        {
          id: 'credit', type: 'metric', title: 'Thẩm định Tín dụng', status: { label: '✓ ĐẠT 3/3', tone: 'pass' }, payload: {
            rows: [
              { name: 'DSCR', hint: '(ngưỡng ≥1,2)', val: '1,40', ok: true, src: 'calc_dscr' },
              { name: 'LTV', hint: '(trần 70%)', val: '62,5%', ok: true, src: 'calc_ltv' },
              { name: 'CIC', hint: '', val: 'Nhóm 1', ok: true, src: 'check_cic' }
            ]
          }
        },
        {
          id: 'legal', type: 'checklist', title: 'Pháp chế & Tuân thủ', status: { label: '⚠ 1 ĐIỀU KIỆN', tone: 'warn' }, payload: {
            items: [
              { state: 'pass', text: 'ĐKKD còn hiệu lực' },
              { state: 'pass', text: 'Hồ sơ thế chấp nhà xưởng hợp lệ' },
              { state: 'warn', text: 'Giấy phép PCCC — thiếu bản cập nhật 2026', note: 'Điều kiện trước giải ngân · nguồn: check_documents' }
            ]
          }
        },
        {
          id: 'products', type: 'options', title: 'So sánh gói vay', status: { label: '3 GÓI · ĐỀ XUẤT 1', tone: 'pass' }, payload: {
            opts: [
              { rec: true, name: 'SME Mở rộng SX', rate: '8,2%', term: '60 th' },
              { rec: false, name: 'Thế chấp chuẩn', rate: '9,1%', term: '48 th' },
              { rec: false, name: 'Tín chấp DN', rate: '11,5%', term: '36 th' }
            ]
          }
        },
        {
          id: 'ops', type: 'timeline', title: 'Vận hành — bước tiếp', status: { label: '✓ 3 BƯỚC', tone: 'pass' }, payload: {
            steps: [
              { text: 'Bổ sung giấy phép PCCC 2026', note: 'KH thực hiện · điều kiện tiên quyết', gate: false },
              { text: 'Phê duyệt hạn mức 5 tỷ', note: 'chờ người duyệt 🔒 gated', gate: true },
              { text: 'Giải ngân về TK doanh nghiệp', note: 'sau phê duyệt · ops_disburse()', gate: false }
            ]
          }
        },
        {
          id: 'approval', type: 'approval', title: 'Phiếu phê duyệt #17 — Approval', status: { label: '⏸ GATED', tone: 'warn' }, payload: {
            icon: '💸', text: 'ops_disburse(5 tỷ → TK Gỗ Việt Phát)',
            note: 'Phiếu khoá theo payload-hash · single-use · gate cưỡng chế TẦNG TOOL (§4.4)', state: 'pending'
          }
        }
      ],
      traces: {
        credit: [
          { kind: 'tool', label: 'calc_dscr → {"dscr":1.40,"pass":true}', time: '10:24:41' },
          { kind: 'tool', label: 'calc_ltv → {"ltv":62.5,"pass":true}', time: '10:24:43' },
          { kind: 'tool', label: 'check_cic → {"group":1}', time: '10:24:46' },
          { kind: 'decision', label: 'ĐẠT 3/3 chỉ tiêu — bàn giao kết quả cho Main', time: '10:24:52' }
        ],
        legal: [
          { kind: 'tool', label: 'check_documents → {"pccc":"outdated_2026"}', time: '10:25:04' },
          { kind: 'decision', label: 'Flag: thiếu PCCC 2026 → điều kiện trước giải ngân', time: '10:25:11' }
        ],
        products: [
          { kind: 'tool', label: 'get_products(SME) → 3 gói', time: '10:24:42' },
          { kind: 'decision', label: 'Đề xuất SME Mở rộng SX 8,2%', time: '10:24:50' }
        ],
        ops: [
          { kind: 'tool', label: 'ops_disburse → {"code":"approval_required","hint":"Đã tạo phiếu #17"}', time: '10:25:20' },
          { kind: 'decision', label: 'Timeline 3 bước · giải ngân gated chờ duyệt', time: '10:25:24' }
        ]
      },
      showProgress: false
    },
    done: {
      label: 'Hoàn tất', convStatus: { c1: 'done', c2: 'wait', c3: 'done' },
      agents: { planner: 'done', credit: 'done', legal: 'warn', products: 'done', ops: 'done' },
      messages: null, // App sẽ lấy từ pending + đổi pending→resolved
      cards: null,    // App sẽ lấy từ pending + phiếu ĐÃ DÙNG + thêm document
      extraCard: {
        id: 'memo', type: 'document', title: 'Tờ trình tổng hợp — Document', status: { label: '✓ SẴN SÀNG EXPORT', tone: 'pass' }, payload: {
          org: 'NGÂN HÀNG SHB — CHI NHÁNH ĐÔNG ĐÔ', docTitle: 'TỜ TRÌNH THẨM ĐỊNH CẤP TÍN DỤNG',
          fields: [
            ['Khách hàng', 'Công ty TNHH Gỗ Việt Phát (KH-2214)'],
            ['Đề nghị', '5 tỷ đồng · 60 tháng · TSBĐ nhà xưởng 8 tỷ'],
            ['Thẩm định', 'DSCR 1,40 (≥1,2) · LTV 62,5% (trần 70%) · CIC nhóm 1'],
            ['Kết luận', 'DUYỆT CÓ ĐIỀU KIỆN'],
            ['Điều kiện', 'Bổ sung giấy phép PCCC bản cập nhật 2026 trước giải ngân']
          ], by: 'Digital Expert Guild'
        }
      },
      traces: {}, showProgress: false
    }
  }
};
