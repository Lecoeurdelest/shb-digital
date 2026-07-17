// components/MessageBubble.tsx — bubble chat tối giản (S1 chỉ cần user/assistant text +
// trạng thái đang stream). Card/verdict có cấu trúc (7 loại) là S3 — KHÔNG build ở đây (D-13 scope).
import type { Message } from '../types';
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
  return <div className="msg-bubble msg-bubble--assistant deg-fadein">{msg.content}</div>;
}

export function StreamingMessageBubble({ bubble }: { bubble: StreamingBubble }) {
  return (
    <div className="msg-bubble msg-bubble--assistant msg-bubble--streaming deg-fadein" data-testid="streaming-bubble">
      {bubble.text}
      <span className="msg-bubble__cursor" aria-hidden="true" />
    </div>
  );
}
