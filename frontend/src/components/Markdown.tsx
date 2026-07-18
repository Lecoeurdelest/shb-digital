// components/Markdown.tsx — render markdown cho tin nhắn assistant/stream (Main trả lời có **bold**,
// ### heading, | bảng |, list, `code`). react-markdown parse → React elements (KHÔNG dangerouslySetInnerHTML,
// KHÔNG rehype-raw) → HTML/script trong text agent = literal, XSS-safe không cần sanitizer. remark-gfm
// bắt buộc cho pipe-tables + strikethrough + autolink. Style bubble-scoped ở MessageBubble.css.
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export function Markdown({ text }: { text: string }) {
  return (
    <div className="md">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
    </div>
  );
}
