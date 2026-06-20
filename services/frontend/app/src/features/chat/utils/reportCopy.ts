function parseTableRow(line: string): string[] {
  const trimmed = line.trim().replace(/^\|/, '').replace(/\|$/, '');
  return trimmed.split('|').map((cell) => cell.trim());
}

function isTableSeparator(line: string): boolean {
  return /^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-{3,}:?\s*\|?\s*$/.test(line);
}

function convertMarkdownTablesToText(markdown: string): string {
  const lines = markdown.split('\n');
  const output: string[] = [];

  for (let i = 0; i < lines.length; i += 1) {
    const current = lines[i];
    const next = lines[i + 1];

    if (!current.includes('|') || !next || !isTableSeparator(next)) {
      output.push(current);
      continue;
    }

    const headers = parseTableRow(current);
    const rowLines: string[] = [];
    let j = i + 2;

    while (j < lines.length && lines[j].trim() !== '' && lines[j].includes('|')) {
      rowLines.push(lines[j]);
      j += 1;
    }

    if (headers.length === 0 || rowLines.length === 0) {
      output.push(current);
      continue;
    }

    for (const rowLine of rowLines) {
      const cells = parseTableRow(rowLine);
      const pairs = headers
        .map((header, idx) => {
          const value = cells[idx]?.trim();
          if (!header || !value) return null;
          return `${header}: ${value}`;
        })
        .filter((pair): pair is string => Boolean(pair));

      if (pairs.length > 0) {
        output.push(`- ${pairs.join('; ')}`);
      }
    }

    i = j - 1;
  }

  return output.join('\n');
}

export function reportMarkdownToPlainText(markdown: string): string {
  const normalized = markdown.replace(/\r\n/g, '\n');
  const tablesNormalized = convertMarkdownTablesToText(normalized);

  const withoutCodeFences = tablesNormalized.replace(
    /```[^\n]*\n([\s\S]*?)```/g,
    (_, code: string) => `\n${code.trimEnd()}\n`
  );

  const linkNormalized = withoutCodeFences
    .replace(
      /\[([^\]]+)\]\(([^)\s]+)(?:\s+"[^"]*")?\)/g,
      (_match, label: string, url: string) => `${label} (${url})`
    )
    .replace(/<((?:https?:\/\/|mailto:)[^>]+)>/g, '$1');

  const inlineMarkdownCleaned = linkNormalized
    .replace(/`([^`]+)`/g, '$1')
    .replace(/(\*\*|__)(.*?)\1/g, '$2')
    .replace(/~~(.*?)~~/g, '$1')
    .replace(/(^|[\s(])([*_])([^*_]+)\2(?=[\s).,;:!?]|$)/g, '$1$3');

  const normalizedLines = inlineMarkdownCleaned
    .split('\n')
    .map((line) =>
      line
        .replace(/^\s{0,3}#{1,6}\s+/, '')
        .replace(/^\s{0,3}>\s?/, '')
        .replace(/^\s{0,3}[-*+]\s+/, '- ')
        .replace(/^\s{0,3}\d+[.)]\s+/, '1. ')
        .replace(/^\s{0,3}---+\s*$/, '')
        .replace(/[ \t]+$/g, '')
    )
    .join('\n');

  return normalizedLines.replace(/\n{3,}/g, '\n\n').trim();
}
