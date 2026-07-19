// components/MessageBubble.tsx — bubble chat tối giản (S1 chỉ cần user/assistant text +
// trạng thái đang stream). Card/verdict có cấu trúc (7 loại) là S3 — KHÔNG build ở đây (D-13 scope).
import type { Message } from '../types';
import { Markdown } from './Markdown';
import { turnMetrics, fmtDuration } from './stats/traceMetrics';
import { fmtUsd, fmtTokens } from './stats/costTransforms';
import './MessageBubble.css';

// T16-4: dòng mờ metrics MAIN dưới bubble assistant (meta.metrics — role='main'). null → không hiện.
function MainMetricsLine({ msg }: { msg: Message }) {
  const m = turnMetrics(msg);
  if (!m) return null;
  const tokens = (Number(m.input_tokens) || 0) + (Number(m.output_tokens) || 0)
    + (Number(m.cache_read_tokens) || 0) + (Number(m.cache_create_tokens) || 0);
  const bits: string[] = [];
  if (m.model) bits.push(`⚙ ${m.model}`);
  if (m.duration_ms != null) bits.push(`⏱ ${fmtDuration(m.duration_ms)}`);
  if (m.cost_usd != null) bits.push(`💰 ${fmtUsd(Number(m.cost_usd))} ước tính`);
  if (tokens > 0) bits.push(`🔢 ${fmtTokens(tokens)} token`);
  if (bits.length === 0) return null;
  return <div className="msg-bubble__metrics" data-testid="main-metrics">{bits.join('  ·  ')}</div>;
}

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
      <MainMetricsLine msg={msg} />
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
