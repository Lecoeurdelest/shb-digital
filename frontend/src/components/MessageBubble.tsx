// components/MessageBubble.tsx — bubble chat tối giản (S1 chỉ cần user/assistant text +
// trạng thái đang stream). Card/verdict có cấu trúc (7 loại) là S3 — KHÔNG build ở đây (D-13 scope).
import type { Message } from '../types';
import { Markdown } from './Markdown';
import './MessageBubble.css';

export interface StreamingBubble {
  turnId: string;
  text: string;
}

export function MessageBubble({ msg }: { msg: Message }) {
  if (msg.sender === 'user') {
    return <div className="msg-bubble msg-bubble--user deg-fadein">{msg.content}</div>;
  }
  if (msg.sender === 'system') {
    // system message lỗi (CONTRACT §4b Gap2 B — main fail) nổi bật hơn note thường.
    const isError = Boolean((msg.meta as { error?: boolean } | null | undefined)?.error);
    return (
      <div className={`msg-bubble msg-bubble--note deg-fadein${isError ? ' msg-bubble--note-error' : ''}`}>
        {msg.content}
      </div>
    );
  }
  // assistant (Main) → render markdown (bold/heading/bảng/list/code). XSS-safe (react-markdown AST).
  return (
    <div className="msg-bubble msg-bubble--assistant deg-fadein">
      <Markdown text={msg.content} />
    </div>
  );
}

export function StreamingMessageBubble({ bubble }: { bubble: StreamingBubble }) {
  // stream = markdown TỪNG PHẦN (có thể **chưa đóng / bảng nửa dòng) — react-markdown render best-effort,
  // không crash; con trỏ nhấp nháy cuối.
  return (
    <div className="msg-bubble msg-bubble--assistant msg-bubble--streaming deg-fadein" data-testid="streaming-bubble">
      <Markdown text={bubble.text} />
      <span className="msg-bubble__cursor" aria-hidden="true" />
    </div>
  );
}
