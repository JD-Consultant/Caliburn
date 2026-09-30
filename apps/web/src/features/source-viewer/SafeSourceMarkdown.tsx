/** Source Markdown has no active content. */
import { Box } from '@mui/material';
import Markdown from 'react-markdown';

export function SafeSourceMarkdown({ markdown }: { markdown: string }) {
  return (
    <Box
      sx={{
        overflowWrap: 'anywhere',
        '& pre': { overflowX: 'auto', p: 2, bgcolor: 'action.hover' },
      }}
    >
      <Markdown
        skipHtml
        components={{
          a: ({ children, href }) => (
            <span>
              {children}
              {href ? `（${href}）` : ''}
            </span>
          ),
          img: ({ alt }) => <span>{alt}</span>,
        }}
      >
        {markdown}
      </Markdown>
    </Box>
  );
}
