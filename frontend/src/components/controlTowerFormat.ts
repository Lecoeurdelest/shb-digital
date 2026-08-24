export function shortId(id: string): string {
  return id.length > 14 ? `${id.slice(0, 10)}…` : id;
}

export function summarize(value: unknown): string {
  if (value == null) return '';
  try {
    return JSON.stringify(value).slice(0, 90);
  } catch {
    return '';
  }
}

export function laneClass(lane: string): string {
  const classes: Record<string, string> = {
    green: 'lane--green',
    yellow: 'lane--yellow',
    red: 'lane--red',
  };
  return classes[lane.toLowerCase()] ?? 'lane--idle';
}

export function fmtApprovalVnd(amount: number): string {
  return `${amount.toLocaleString('vi-VN')} ₫`;
}
