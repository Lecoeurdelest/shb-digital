// test/setup.ts — vitest global setup (vite.config.ts → test.setupFiles). Nạp jest-dom
// matchers (toBeInTheDocument…) cho @testing-library/react.
import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

// afterEach(cleanup) TƯỜNG MINH — unmount DOM giữa MỌI test bất kể file. RTL auto-cleanup ngầm
// (dựa globals:true) không đảm bảo trigger đúng thời điểm khi nhiều FILE test share worker vitest
// → DOM tồn dư giữa file làm getByText match trúng phần tử của render trước (tester bắt flaky theo
// thứ tự file). Đăng ký tường minh chặn triệt để, không phụ thuộc auto-cleanup ngầm.
afterEach(cleanup);
