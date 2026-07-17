// roles.ts — nhãn Việt-hoá role (dùng chung TaskBadge + App reason). Role ĐỘNG (CONTRACT §3):
// role lạ → trả raw, KHÔNG hardcode enum cứng. S1 chỉ thấy `credit`.
const ROLE_LABEL: Record<string, string> = {
  credit: 'Tín dụng',
  legal: 'Pháp chế',
  products: 'Sản phẩm',
  ops: 'Vận hành',
};

export function roleLabel(role: string): string {
  return ROLE_LABEL[role] ?? role;
}
