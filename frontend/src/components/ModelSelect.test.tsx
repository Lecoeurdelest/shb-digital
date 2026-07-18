// ModelSelect.test.tsx — S15 T15-2/4. Migrate coverage ModelPicker cũ (default chọn sẵn, provider
// disabled thiếu key, đổi provider→onChange, getModels lỗi→fallback) + MỚI: text-button 1 dòng,
// dropdown portal group, per-turn (open-conv value từ prop), tolerant default (T15-4 phantom guard).
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ModelSelect } from './ModelSelect';
import { conversationApi } from '../api';
import type { ModelsResponse } from '../types';

const MODELS: ModelsResponse = {
  providers: [
    { name: 'claude-cli', kind: 'subscription', base_url: null, models: ['haiku', 'sonnet', 'opus'], default: true, has_key: true },
    { name: 'zai', kind: 'api', base_url: 'https://api.z.ai', models: ['glm-4.6', 'glm-4.5'], default: false, has_key: true },
    { name: 'openai', kind: 'api', base_url: null, models: ['gpt-4o'], default: false, has_key: false },
  ],
  default: 'claude-cli',
};

beforeEach(() => vi.restoreAllMocks());

describe('ModelSelect (T15-2/4)', () => {
  it('autoDefault + chưa chọn → default response (claude-cli/haiku) qua onChange', async () => {
    vi.spyOn(conversationApi, 'getModels').mockResolvedValue(MODELS);
    const onChange = vi.fn();
    render(<ModelSelect provider="" model="" onChange={onChange} autoDefault />);
    await waitFor(() => expect(onChange).toHaveBeenCalledWith('claude-cli', 'haiku'));
  });

  it('label 1 dòng "model · provider" khi đã chọn', async () => {
    vi.spyOn(conversationApi, 'getModels').mockResolvedValue(MODELS);
    render(<ModelSelect provider="zai" model="glm-4.6" onChange={vi.fn()} />);
    await waitFor(() => expect(screen.getByTestId('model-select-btn')).toHaveTextContent('glm-4.6 · zai'));
  });

  it('click button → dropdown portal group theo provider (ra body)', async () => {
    vi.spyOn(conversationApi, 'getModels').mockResolvedValue(MODELS);
    render(<ModelSelect provider="claude-cli" model="haiku" onChange={vi.fn()} />);
    await waitFor(() => screen.getByTestId('model-select-btn'));
    fireEvent.click(screen.getByTestId('model-select-btn'));
    const menu = screen.getByTestId('model-select-menu');
    expect(menu.closest('.msel')).toBeNull(); // portal ra body
    expect(screen.getByTestId('model-opt-zai-glm-4.6')).toBeInTheDocument();
  });

  it('chọn model provider khác → onChange(provider, model)', async () => {
    vi.spyOn(conversationApi, 'getModels').mockResolvedValue(MODELS);
    const onChange = vi.fn();
    render(<ModelSelect provider="claude-cli" model="haiku" onChange={onChange} />);
    await waitFor(() => screen.getByTestId('model-select-btn'));
    fireEvent.click(screen.getByTestId('model-select-btn'));
    fireEvent.click(screen.getByTestId('model-opt-zai-glm-4.5'));
    expect(onChange).toHaveBeenCalledWith('zai', 'glm-4.5');
  });

  it('provider has_key=false (openai) → item disabled', async () => {
    vi.spyOn(conversationApi, 'getModels').mockResolvedValue(MODELS);
    render(<ModelSelect provider="claude-cli" model="haiku" onChange={vi.fn()} />);
    await waitFor(() => screen.getByTestId('model-select-btn'));
    fireEvent.click(screen.getByTestId('model-select-btn'));
    expect(screen.getByTestId('model-opt-openai-gpt-4o')).toBeDisabled();
  });

  it('disabled (running) → button disabled, click không mở menu', async () => {
    vi.spyOn(conversationApi, 'getModels').mockResolvedValue(MODELS);
    render(<ModelSelect provider="zai" model="glm-4.6" onChange={vi.fn()} disabled />);
    await waitFor(() => screen.getByTestId('model-select-btn'));
    expect(screen.getByTestId('model-select-btn')).toBeDisabled();
    fireEvent.click(screen.getByTestId('model-select-btn'));
    expect(screen.queryByTestId('model-select-menu')).not.toBeInTheDocument();
  });

  it('getModels lỗi → fallback "mặc định máy chủ", không crash', async () => {
    vi.spyOn(conversationApi, 'getModels').mockRejectedValue(new Error('net'));
    render(<ModelSelect provider="" model="" onChange={vi.fn()} autoDefault />);
    await waitFor(() => expect(screen.getByText(/mặc định máy chủ/)).toBeInTheDocument());
  });

  // T15-4: provider/model MA (không có trong list) → KHÔNG render phantom; kẹp về default:true/đầu list.
  it('T15-4: provider ma (đã biến mất khỏi list) → hiện default provider, không phantom', async () => {
    vi.spyOn(conversationApi, 'getModels').mockResolvedValue(MODELS);
    // ca lưu provider 'ghost' đã gỡ → label phải kẹp về default (claude-cli), KHÔNG hiện 'ghost'
    render(<ModelSelect provider="ghost" model="ghost-model" onChange={vi.fn()} />);
    await waitFor(() => screen.getByTestId('model-select-btn'));
    const label = screen.getByTestId('model-select-btn').textContent ?? '';
    expect(label).toContain('claude-cli'); // kẹp về default provider
    expect(label).not.toContain('ghost');
  });

  it('T15-4: default response KHÔNG có trong list → fallback default:true (autoDefault)', async () => {
    vi.spyOn(conversationApi, 'getModels').mockResolvedValue({ ...MODELS, default: 'khong-ton-tai' });
    const onChange = vi.fn();
    render(<ModelSelect provider="" model="" onChange={onChange} autoDefault />);
    // default 'khong-ton-tai' không có → resolveSelection → provider default:true = claude-cli
    await waitFor(() => expect(onChange).toHaveBeenCalledWith('claude-cli', 'haiku'));
  });
});
