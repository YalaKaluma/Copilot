import { describe, expect, it } from 'vitest';
import { reportMarkdownToPlainText } from './reportCopy';

describe('reportMarkdownToPlainText', () => {
  it('converts headings, emphasis, and paragraphs to readable plain text', () => {
    const markdown = `# Executive Summary
This is **important** and _actionable_.

## Outcome
Revenue increased.`;

    expect(reportMarkdownToPlainText(markdown)).toBe(
      'Executive Summary\nThis is important and actionable.\n\nOutcome\nRevenue increased.'
    );
  });

  it('preserves list structure and normalizes mixed list markers', () => {
    const markdown = `- First
* Second
1) Third
4. Fourth`;

    expect(reportMarkdownToPlainText(markdown)).toBe(
      '- First\n- Second\n1. Third\n1. Fourth'
    );
  });

  it('formats markdown links as label and url', () => {
    const markdown = 'See [Q4 report](https://example.com/q4 "Q4").';

    expect(reportMarkdownToPlainText(markdown)).toBe(
      'See Q4 report (https://example.com/q4).'
    );
  });

  it('removes markdown fences while keeping code block body', () => {
    const markdown = '```sql\nSELECT * FROM table;\n```';

    expect(reportMarkdownToPlainText(markdown)).toBe('SELECT * FROM table;');
  });

  it('collapses excessive blank lines and trims output', () => {
    const markdown = 'Line 1\n\n\n\nLine 2  \n';

    expect(reportMarkdownToPlainText(markdown)).toBe('Line 1\n\nLine 2');
  });

  it('converts markdown tables into readable plain-text rows', () => {
    const markdown = `Promo Investment Totals by Retailer
| Retailer | Total Promo Investment | Number of Brands Included |
|----------|------------------------|---------------------------|
| B&M | £2,112,065 | 2 |
| WICKES | £1,967,509.07 | 4 |`;

    expect(reportMarkdownToPlainText(markdown)).toBe(
      'Promo Investment Totals by Retailer\n- Retailer: B&M; Total Promo Investment: £2,112,065; Number of Brands Included: 2\n- Retailer: WICKES; Total Promo Investment: £1,967,509.07; Number of Brands Included: 4'
    );
  });
});
