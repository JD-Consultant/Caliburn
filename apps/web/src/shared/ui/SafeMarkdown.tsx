/** Read-only Markdown has no active HTML, navigable links or remote media. */
import { Box } from '@mui/material';
import Markdown from 'react-markdown';
import type { Components } from 'react-markdown';
import { diffAwareCode } from './diff-code';
import { inertMarkdownComponents } from './inert-markdown';

const components = { ...inertMarkdownComponents, code: diffAwareCode } satisfies Components;

export function SafeMarkdown({ markdown }: { markdown: string }) {
  return (
    <Box
      sx={{
        overflowWrap: 'anywhere',
        '& pre': { overflowX: 'auto', p: 2, bgcolor: 'action.hover' },
      }}
    >
      <Markdown skipHtml components={components}>
        {markdown}
      </Markdown>
    </Box>
  );
}
