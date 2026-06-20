/**
 * Split status lines (e.g. reasoning steps) into separate sections on bold headings.
 * Used by ReasoningPanel in the right pane.
 */
export function splitStatusSections(lines: string[]): string[] {
  const sections: string[] = [];
  for (const raw of lines) {
    const cleaned = raw.replace(/^Reasoning:\s*/i, '').trim();
    if (!cleaned) continue;
    // Split before bold headings (**Title**) that are followed by a newline,
    // indicating a standalone heading rather than inline bold.
    const parts = cleaned.split(/(?=\*\*[^*]+\*\*\s*\n)/);
    for (const part of parts) {
      const trimmed = part.trim();
      if (trimmed) sections.push(trimmed);
    }
  }
  return sections;
}
