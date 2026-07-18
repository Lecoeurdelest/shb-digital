// ErrorBoundary.test.tsx — child throw → fallback render (không lộ trắng màn); child OK → render bình thường.
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { ErrorBoundary } from './ErrorBoundary';

function Boom(): never {
  throw new Error('render nổ');
}

afterEach(() => vi.restoreAllMocks());

describe('ErrorBoundary', () => {
  it('child render OK → hiển thị child, không fallback', () => {
    render(
      <ErrorBoundary>
        <div>nội dung bình thường</div>
      </ErrorBoundary>,
    );
    expect(screen.getByText('nội dung bình thường')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('child throw → fallback UI + message lỗi + nút tải lại (không crash lên trên)', () => {
    // React log lỗi ra console khi boundary bắt — nuốt để test output sạch.
    vi.spyOn(console, 'error').mockImplementation(() => {});
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText('Giao diện gặp lỗi')).toBeInTheDocument();
    expect(screen.getByText('render nổ')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Tải lại/ })).toBeInTheDocument();
  });
});
