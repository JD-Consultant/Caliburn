/**
 * The one rule every rendered Markdown shares, whoever wrote it: a link shows its target as text and
 * an image shows its alt text, so nothing can navigate away or load remote media. Each renderer adds
 * only its own policy for raw HTML and headings (SafeMarkdown, ChatMarkdown).
 */
import type { Components } from 'react-markdown';

export const inertMarkdownComponents = {
  a: ({ children, href }) => (
    <span>
      {children}
      {href ? `（${href}）` : ''}
    </span>
  ),
  img: ({ alt }) => <span>{alt}</span>,
} satisfies Components;
