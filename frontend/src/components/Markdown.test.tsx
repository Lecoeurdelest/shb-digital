// Markdown.test.tsx — render markdown assistant (bold/heading/bảng gfm/code/list) + XSS-safe.
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { Markdown } from './Markdown';
import { MessageBubble } from './MessageBubble';
import type { Message } from '../types';

describe('Markdown', () => {
  it('**bold** → <strong>, ### → <h3>', () => {
    const { container } = render(<Markdown text={'### Kết luận\nphần **quan trọng**'} />);
    expect(container.querySelector('h3')).toHaveTextContent('Kết luận');
    expect(container.querySelector('strong')).toHaveTextContent('quan trọng');
  });

  it('pipe-table (gfm) → <table> với th/td (KHÔNG render raw | )', () => {
    const md = '| Thông tin | Chi tiết |\n|---|---|\n| Số tiền | 5 tỷ |';
    const { container } = render(<Markdown text={md} />);
    expect(container.querySelector('table')).toBeInTheDocument();
    expect(container.querySelectorAll('th')).toHaveLength(2);
    expect(screen.getByText('Số tiền')).toBeInTheDocument();
    expect(screen.getByText('5 tỷ')).toBeInTheDocument();
  });

  it('`code` inline + list', () => {
    const { container } = render(<Markdown text={'gọi `credit_assess`\n\n- một\n- hai'} />);
    expect(container.querySelector('code')).toHaveTextContent('credit_assess');
    expect(container.querySelectorAll('li')).toHaveLength(2);
  });

  it('XSS-safe: HTML/script trong text = LITERAL (không thành thẻ, không rehype-raw)', () => {
    const { container } = render(<Markdown text={'<script>alert(1)</script> và <b>x</b>'} />);
    // KHÔNG có <script> thật injected
    expect(container.querySelector('script')).toBeNull();
    // text hiện như literal (react-markdown escape)
    expect(container.textContent).toContain('alert(1)');
  });

  it('MessageBubble assistant → render markdown; user → plain (không parse)', () => {
    const asst: Message = { id: 'm1', conv_id: 'c1', ts: '', sender: 'assistant', content: '**đậm**', meta: null };
    const user: Message = { id: 'm2', conv_id: 'c1', ts: '', sender: 'user', content: '**không đậm**', meta: null };
    const { container: a } = render(<MessageBubble msg={asst} />);
    expect(a.querySelector('strong')).toHaveTextContent('đậm');
    const { container: u } = render(<MessageBubble msg={user} />);
    expect(u.querySelector('strong')).toBeNull(); // user text literal
    expect(u.textContent).toContain('**không đậm**');
  });
});
