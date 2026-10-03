/**
 * A fenced `diff` block drawn one line at a time, as GitHub's unified view does: a tint and a marker
 * (+ / −) per line, so a change never relies on colour alone. Any other code block stays as it is.
 * The text content is unchanged, so copying a diff still yields the diff.
 */
import { Fragment } from 'react';
import type { Components } from 'react-markdown';

type LineKind = 'add' | 'del' | 'hunk' | 'meta' | 'context';

const MARKED: readonly LineKind[] = ['add', 'del', 'context'];

/** `---` / `+++` are file headers only before the first hunk; after it they are changed text. */
function classify(lines: readonly string[]): { text: string; kind: LineKind }[] {
  const classified: { text: string; kind: LineKind }[] = [];
  let inHunk = false;
  for (const text of lines) {
    let kind: LineKind = 'context';
    if (text.startsWith('@@')) {
      inHunk = true;
      kind = 'hunk';
    } else if (text.startsWith('\\') || (!inHunk && /^(---|\+\+\+)/.test(text))) kind = 'meta';
    else if (text.startsWith('+')) kind = 'add';
    else if (text.startsWith('-')) kind = 'del';
    classified.push({ text, kind });
  }
  return classified;
}

export const diffAwareCode: NonNullable<Components['code']> = ({ className, children }) => {
  if (className !== 'language-diff' || typeof children !== 'string')
    return <code className={className}>{children}</code>;
  const lines = (children.endsWith('\n') ? children.slice(0, -1) : children).split('\n');
  return (
    <code className="diff">
      {classify(lines).map(({ text, kind }, index) => (
        // Lines never reorder; the newline between them keeps `textContent` identical to the source.
        <Fragment key={index}>
          <span className="diff__line" data-diff-line={kind}>
            {MARKED.includes(kind) ? (
              <>
                <span className="diff__mark">{text.slice(0, 1)}</span>
                {text.slice(1)}
              </>
            ) : (
              text
            )}
          </span>
          {'\n'}
        </Fragment>
      ))}
    </code>
  );
};
