import { describe, expect, it } from 'vitest';
import { ApiRequestError } from './api/client';
import { describeError, userFacingErrorMessage } from './workspaceUtil';

describe('workspace error presentation', () => {
  it('hides raw runtime and server errors from the user surface', () => {
    expect(describeError(new Error('provider model token stacktrace'), 'Không tải được dữ liệu')).toBe('Không tải được dữ liệu');
    expect(userFacingErrorMessage(
      new ApiRequestError(500, {
        code: 'provider_down',
        message: 'provider model token stacktrace',
        hint: 'Kiểm tra server log.',
        retryable: true,
      }, 'provider_down'),
      'Không tải được dữ liệu',
    )).toBe('Không tải được dữ liệu');
  });

  it('keeps actionable validation and business messages visible', () => {
    expect(userFacingErrorMessage(
      new ApiRequestError(400, {
        code: 'bad_email',
        message: 'Email không hợp lệ.',
        hint: 'Kiểm định dạng name@domain.',
        retryable: false,
      }, 'bad_email'),
      'Đăng ký thất bại',
    )).toBe('Email không hợp lệ.');

    expect(userFacingErrorMessage(
      new ApiRequestError(409, {
        code: 'conversation_busy',
        message: 'Phiên xử lý đang chạy.',
        hint: 'Chờ lượt hiện tại kết thúc.',
        retryable: true,
      }, 'conversation_busy'),
      'Đổi tên thất bại',
    )).toBe('Phiên xử lý đang chạy.');
  });
});
