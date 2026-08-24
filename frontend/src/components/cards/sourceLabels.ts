// Raw source chỉ dùng làm khóa nội bộ; nhãn này là contract trình bày D-75.
const SOURCE_LABELS: Array<[prefix: string, label: string]> = [
  ['credit_cic', 'Thông tin tín dụng'],
  ['cic', 'Thông tin tín dụng'],
  ['credit', 'Tín dụng'],
  ['calc_dscr', 'Tín dụng'],
  ['calc_ltv', 'Tín dụng'],
  ['legal', 'Pháp lý'],
  ['check_document', 'Pháp lý'],
  ['check_regulation', 'Pháp lý'],
  ['product', 'Sản phẩm'],
  ['match_package', 'Sản phẩm'],
  ['operation', 'Vận hành'],
  ['ops', 'Vận hành'],
  ['cust', 'Dữ liệu khách hàng'],
  ['customer', 'Dữ liệu khách hàng'],
  ['core', 'Hệ thống lõi'],
];

export function sourceLabel(source: string): string {
  const normalized = source.trim().toLowerCase();
  return SOURCE_LABELS.find(([prefix]) => normalized.startsWith(prefix))?.[1] ?? 'Nguồn nghiệp vụ';
}
