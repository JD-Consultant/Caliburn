/** Navigate only links supplied by the selected formal citation's fixed chain. */
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert, Button } from '@mui/material';
import type { InterviewContent } from '../../shared/api/generated/jd-source-content-view';
import { SafeMarkdown } from '../../shared/ui/SafeMarkdown';
import { ArrowBackIcon, ChevronRightIcon } from '../../shared/ui/icons';
import { describeSourceError, jdSourceContentQuery } from './source-api';
import type { SourceScope } from './source-api';
import { SourceKindIcon } from './SourceKindIcon';

const speakerLabels: Record<InterviewContent['speaker'], string> = {
  app: '系統',
  employee: '員工',
  consultant: '顧問',
};

export function SourceDetails({ scope }: { scope: SourceScope }) {
  const [sourceRef, setSourceRef] = useState<string | null>(null);
  const source = useQuery(jdSourceContentQuery(scope, sourceRef));
  const content = source.data?.content;
  return (
    <div className="source-body">
      <p className="source-note">以下正文為原引用當時的固定版本。</p>
      {sourceRef !== null && (
        <Button
          size="small"
          startIcon={<ArrowBackIcon />}
          onClick={() => setSourceRef(null)}
          sx={{ alignSelf: 'flex-start' }}
        >
          回到直接來源
        </Button>
      )}
      {source.isFetching ? (
        <p role="status">正在讀取來源正文…</p>
      ) : source.isError ? (
        <Alert severity="error">{describeSourceError(source.error)}</Alert>
      ) : (
        content &&
        (content.kind === 'interview' ? (
          // The employee's own words, set apart as a quotation (Hypothes.is, Kindle highlights).
          <figure className="source-quote">
            <figcaption>
              訪談 #{content.interview_sequence} · {speakerLabels[content.speaker]}
            </figcaption>
            <blockquote>{content.interview_text}</blockquote>
          </figure>
        ) : (
          <>
            <h4 className="source-body__title">{content.title}</h4>
            {content.description !== '' && (
              <p className="source-body__description">{content.description}</p>
            )}
            <div className="source-prose">
              <SafeMarkdown markdown={content.body} />
            </div>
            {content.references.length > 0 && (
              <div>
                <p className="source-note">此來源的依據</p>
                <ul className="source-group__rows">
                  {content.references.map((link) => (
                    <li key={link.source_ref} className="source-row">
                      <button
                        type="button"
                        className="source-row__main"
                        onClick={() => setSourceRef(link.source_ref)}
                      >
                        <SourceKindIcon kind={link.kind} />
                        <span className="source-row__label">{link.label}</span>
                      </button>
                      <ChevronRightIcon className="source-row__chevron" aria-hidden="true" />
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        ))
      )}
    </div>
  );
}
