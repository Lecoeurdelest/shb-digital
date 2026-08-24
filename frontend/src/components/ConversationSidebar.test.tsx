// ConversationSidebar.test.tsx — S15 T15-3: rename inline + delete 2-bước + trap #3 (Enter trong
// rename KHÔNG mở ca; click nút CRUD KHÔNG mở ca). showActions gate.
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ConversationSidebar } from './ConversationSidebar';
import type { Conversation } from '../types';

const convs: Conversation[] = [
  { id: 'c1', title: 'Phiên C001', status: 'idle', created_at: '' },
  { id: 'c2', title: 'Phiên C029', status: 'done', created_at: '' },
];

function setup(over: Partial<Parameters<typeof ConversationSidebar>[0]> = {}) {
  const onOpen = vi.fn(), onNew = vi.fn(), onRename = vi.fn(), onDelete = vi.fn();
  render(
    <ConversationSidebar
      conversations={convs} activeId="c1" onOpen={onOpen} onNew={onNew} creating={false}
      onRename={onRename} onDelete={onDelete} showActions
      {...over}
    />,
  );
  return { onOpen, onNew, onRename, onDelete };
}

describe('ConversationSidebar CRUD (T15-3)', () => {
  it('showActions=false → không render nút CRUD', () => {
    setup({ showActions: false });
    expect(screen.queryByTestId('conv-edit-c1')).not.toBeInTheDocument();
    expect(screen.queryByTestId('conv-del-c1')).not.toBeInTheDocument();
  });

  it('showActions → mỗi ca có nút ✎ + 🗑', () => {
    setup();
    expect(screen.getByTestId('conv-edit-c1')).toBeInTheDocument();
    expect(screen.getByTestId('conv-del-c1')).toBeInTheDocument();
    expect(screen.getByTestId('conv-edit-c2')).toBeInTheDocument();
  });

  it('click ✎ → input rename (KHÔNG mở ca — stopPropagation)', () => {
    const { onOpen } = setup();
    fireEvent.click(screen.getByTestId('conv-edit-c1'));
    expect(screen.getByTestId('conv-rename-c1')).toBeInTheDocument();
    expect(onOpen).not.toHaveBeenCalled(); // trap #3
  });

  it('rename Enter → onRename(id, title mới) + KHÔNG mở ca', () => {
    const { onOpen, onRename } = setup();
    fireEvent.click(screen.getByTestId('conv-edit-c1'));
    const input = screen.getByTestId('conv-rename-c1');
    fireEvent.change(input, { target: { value: 'Tên phiên mới' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onRename).toHaveBeenCalledWith('c1', 'Tên phiên mới');
    expect(onOpen).not.toHaveBeenCalled(); // Enter trong input không bubble ra div (trap #3)
  });

  it('rename Escape → huỷ, KHÔNG onRename', () => {
    const { onRename } = setup();
    fireEvent.click(screen.getByTestId('conv-edit-c1'));
    const input = screen.getByTestId('conv-rename-c1');
    fireEvent.change(input, { target: { value: 'abc' } });
    fireEvent.keyDown(input, { key: 'Escape' });
    expect(screen.queryByTestId('conv-rename-c1')).not.toBeInTheDocument();
    expect(onRename).not.toHaveBeenCalled();
  });

  it('rename giữ nguyên tên (không đổi) → KHÔNG onRename', () => {
    const { onRename } = setup();
    fireEvent.click(screen.getByTestId('conv-edit-c1'));
    const input = screen.getByTestId('conv-rename-c1');
    fireEvent.keyDown(input, { key: 'Enter' }); // giá trị = title cũ
    expect(onRename).not.toHaveBeenCalled();
  });

  it('delete 2-bước: 🗑 → confirm (chưa gọi onDelete); Xoá → onDelete', () => {
    const { onDelete, onOpen } = setup();
    fireEvent.click(screen.getByTestId('conv-del-c1'));
    expect(screen.getByTestId('conv-confirm-c1')).toBeInTheDocument();
    expect(onDelete).not.toHaveBeenCalled(); // chưa xoá, chỉ hỏi
    expect(onOpen).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId('conv-del-yes-c1'));
    expect(onDelete).toHaveBeenCalledWith('c1');
  });

  it('delete Huỷ → đóng confirm, KHÔNG onDelete', () => {
    const { onDelete } = setup();
    fireEvent.click(screen.getByTestId('conv-del-c1'));
    fireEvent.click(screen.getByText('Huỷ'));
    expect(screen.queryByTestId('conv-confirm-c1')).not.toBeInTheDocument();
    expect(onDelete).not.toHaveBeenCalled();
  });

  it('click thân ca (không phải nút) → mở ca như cũ', () => {
    const { onOpen } = setup();
    fireEvent.click(screen.getByText('Phiên C029'));
    expect(onOpen).toHaveBeenCalledWith('c2');
  });

  it('copy sidebar dùng Phiên xử lý, không gọi conversation là ca/hồ sơ', () => {
    const { onNew } = setup();
    fireEvent.click(screen.getByRole('button', { name: /^\+ Phiên xử lý$/i }));
    expect(onNew).toHaveBeenCalledOnce();
    expect(screen.getByText('PHIÊN XỬ LÝ CỦA BẠN')).toBeInTheDocument();
    expect(screen.queryByText(/CA CỦA BẠN|HỒ SƠ CỦA BẠN/i)).not.toBeInTheDocument();
  });
});

describe('ConversationSidebar groups (D-79)', () => {
  const groups = [
    { id: 'g1', name: 'Doanh nghiệp', created_by: 'user', created_at: '', updated_at: '' },
    { id: 'g2', name: 'Cá nhân', created_by: 'user', created_at: '', updated_at: '' },
  ];

  it('nhóm phiên theo group_id và giữ khu vực chưa phân nhóm', () => {
    setup({ groups, conversations: [{ ...convs[0], group_id: 'g1' }, convs[1]] });
    expect(screen.getByRole('region', { name: 'Nhóm Doanh nghiệp' })).toHaveTextContent('Phiên C001');
    expect(screen.getByRole('region', { name: 'Chưa phân nhóm' })).toHaveTextContent('Phiên C029');
  });

  it('tạo nhóm inline bằng Enter', async () => {
    const onCreateGroup = vi.fn().mockResolvedValue(undefined);
    setup({ onCreateGroup });
    fireEvent.click(screen.getByRole('button', { name: '+ Nhóm' }));
    const input = screen.getByRole('textbox', { name: 'Tên nhóm phiên xử lý' });
    fireEvent.change(input, { target: { value: '  Hồ sơ ưu tiên  ' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    await waitFor(() => expect(onCreateGroup).toHaveBeenCalledWith('Hồ sơ ưu tiên'));
  });

  it('chuyển nhóm không kích hoạt mở phiên', () => {
    const onMoveConversation = vi.fn();
    const { onOpen } = setup({ groups, onMoveConversation });
    fireEvent.change(screen.getByRole('combobox', { name: 'Nhóm của Phiên C001' }), {
      target: { value: 'g2' },
    });
    expect(onMoveConversation).toHaveBeenCalledWith('c1', 'g2');
    expect(onOpen).not.toHaveBeenCalled();
  });
});
