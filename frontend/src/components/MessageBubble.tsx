// components/MessageBubble.tsx — bubble chat tối giản (S1 chỉ cần user/assistant text +
// trạng thái đang stream). Card/verdict có cấu trúc (7 loại) là S3 — KHÔNG build ở đây (D-13 scope).
import type { Message } from '../types';
import { Markdown } from './Markdown';
import { sourceLabel } from './cards/sourceLabels';
import './MessageBubble.css';

const SOURCE_ID = /\b(?:credit_assess|credit_cic_get|cust_get|products_catalog|calc_dscr|calc_ltv|check_documents?|check_regulation|match_package|legal_[a-z0-9_]+|product_[a-z0-9_]+|ops_[a-z0-9_]+|operation_[a-z0-9_]+)\b/gi;

function businessResultText(text: string): string {
  return text.replace(SOURCE_ID, (source) => sourceLabel(source));
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
    // Lỗi nội bộ vẫn nổi bật nhưng không đẩy tên runtime/telemetry ra bề mặt nghiệp vụ (D-75).
    const isError = Boolean((msg.meta as { error?: boolean } | null | undefined)?.error);
    return (
      <div className={`msg-bubble msg-bubble--note deg-fadein${isError ? ' msg-bubble--note-error' : ''}`}>
        {isError ? 'Không thể hoàn tất bước xử lý. Vui lòng thử lại hoặc liên hệ bộ phận vận hành.' : msg.content}
      </div>
    );
  }
  // Kết quả xử lý → render markdown (bold/heading/bảng/list/code). XSS-safe (react-markdown AST).
  return (
    <div className="msg-bubble msg-bubble--assistant deg-fadein">
      <Markdown text={businessResultText(msg.content)} />
    </div>
  );
}

export function StreamingMessageBubble({ bubble }: { bubble: StreamingBubble }) {
  // stream = markdown TỪNG PHẦN (có thể **chưa đóng / bảng nửa dòng) — react-markdown render best-effort,
  // không crash; con trỏ nhấp nháy cuối.
  return (
    <div className="msg-bubble msg-bubble--assistant msg-bubble--streaming deg-fadein" data-testid="streaming-bubble">
      <Markdown text={businessResultText(bubble.text)} />
      <span className="msg-bubble__cursor" aria-hidden="true" />
    </div>
  );
}
