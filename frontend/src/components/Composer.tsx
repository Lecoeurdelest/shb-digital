// components/Composer.tsx — input chat (mirror shared look-and-feel design/workspace/chat.jsx Composer).
import { useState, type KeyboardEvent } from 'react';
import './Composer.css';

interface Props {
  placeholder: string;
  disabled?: boolean;
  onSend: (text: string) => void;
}

export function Composer({ placeholder, disabled, onSend }: Props) {
  const [value, setValue] = useState('');

  const fire = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue('');
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') fire();
  };

  return (
    <div className="composer">
      <div className="composer__box">
        <input
          className="composer__input"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          aria-label="Ô nhập câu hỏi"
        />
        <button
          className="composer__send"
          onClick={fire}
          disabled={disabled || !value.trim()}
          type="button"
          aria-label="Gửi"
        >
          ↑
        </button>
      </div>
    </div>
  );
}
