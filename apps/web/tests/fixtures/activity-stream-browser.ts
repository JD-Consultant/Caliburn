/** Synthetic HTTP browser fixture using the production subscription owner and query guards. */
import { createElement } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useConsultantActivityStream } from '../../src/features/interview/use-consultant-activity-stream';

function Probe() {
  const activity = useConsultantActivityStream(
    '10000000-0000-4000-8000-000000000001',
    '20000000-0000-4000-8000-000000000002',
  );
  return createElement('output', null, JSON.stringify(activity));
}

createRoot(document.getElementById('root')!).render(
  createElement(QueryClientProvider, { client: new QueryClient() }, createElement(Probe)),
);
