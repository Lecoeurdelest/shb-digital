export class SseDataParser {
  private buffer = ''

  push(chunk: string): string[] {
    this.buffer += chunk
    const payloads: string[] = []
    let boundary = this.findBoundary()
    while (boundary) {
      const frame = this.buffer.slice(0, boundary.index)
      this.buffer = this.buffer.slice(boundary.index + boundary.length)
      const data = frame
        .split(/\r?\n/)
        .filter((line) => line.startsWith('data:'))
        .map((line) => line.slice(5).replace(/^ /, ''))
        .join('\n')
      if (data) payloads.push(data)
      boundary = this.findBoundary()
    }
    return payloads
  }

  finish(): string[] {
    if (!this.buffer.trim()) return []
    this.buffer += '\n\n'
    return this.push('')
  }

  private findBoundary(): { index: number; length: number } | null {
    const match = /\r?\n\r?\n/.exec(this.buffer)
    return match ? { index: match.index, length: match[0].length } : null
  }
}
