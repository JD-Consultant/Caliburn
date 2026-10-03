/**
 * The consultant's chat messages, formatted. Only the display is formatted; the stored text is
 * never changed, and employee and App messages are still shown verbatim (see InterviewHistory).
 *
 * Unlike SafeMarkdown, raw HTML is shown as literal text (react-markdown escapes it by default)
 * instead of being dropped, so a reply that mentions `<姓名>` loses nothing. Links and images follow
 * the shared inert rule. Headings become bold paragraphs, because a chat bubble has no document
 * outline. Soft line breaks are kept by CSS (`white-space: pre-line`).
 */
import type { ReactNode } from 'react';
import Markdown from 'react-markdown';
import type { Components } from 'react-markdown';
import { inertMarkdownComponents } from './inert-markdown';

function Heading({ children }: { children?: ReactNode }) {
  return (
    <p>
      <strong>{children}</strong>
    </p>
  );
}

const components: Components = {
  ...inertMarkdownComponents,
  h1: Heading,
  h2: Heading,
  h3: Heading,
  h4: Heading,
  h5: Heading,
  h6: Heading,
};

export function ChatMarkdown({ markdown, className }: { markdown: string; className?: string }) {
  return (
    <div className={className}>
      <Markdown components={components}>{markdown}</Markdown>
    </div>
  );
}
