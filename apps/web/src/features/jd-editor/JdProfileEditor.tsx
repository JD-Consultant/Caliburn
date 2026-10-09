/** The JD's basic data: server-confirmed values, each edited in place; the command pipeline is the collections' one. */
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert, Box, Button, Paper, Stack, Typography } from '@mui/material';
import { describeReadError } from '../../shared/api/http';
import { isReviseJdProfileRequest } from '../../shared/api/validation';
import { useStoredCommand } from '../../shared/commands/use-stored-command';
import { useEditSlot } from './edit-slots-context';
import { InlineEditContext } from './inline-edit-context';
import type { InlineEdit, InlineSaveResult } from './inline-edit-context';
import { profileTextField } from './inline-fields';
import type { InlineIntent } from './inline-fields';
import { draftNoticeOf, statusOf } from './inline-session';
import { InlineText } from './InlineText';
import { jdProfileQuery } from './jd-profile-api';
import { profileCommandFor, profileFields, profileLabels } from './profile-command';
import { profileTarget, useSourceBadge } from './source-badge-context';
import { jdCommandView, profileCommand } from './jd-commands';
import { WorkStatus } from './WorkStatus';

export function JdProfileEditor({
  jobFileId,
  readOnly = false,
  refresh,
}: {
  jobFileId: string;
  refresh: () => Promise<void>;
  /** A Turn owns the JD: show it, but offer no manual edit (the App also refuses writes). */
  readOnly?: boolean;
}) {
  const profile = useQuery(jdProfileQuery(jobFileId));
  const badge = useSourceBadge();
  const [inlineKey, setInlineKey] = useState<string | null>(null);
  // Reported by the open editor itself, so a field that vanished mid-edit cannot leave the page waiting.
  const [inlineEditorOpen, setInlineEditorOpen] = useState(false);
  const definition = profileCommand(jobFileId, refresh);
  const closeEditor = () => setInlineKey(null);
  const submission = useStoredCommand(definition, closeEditor);
  const command = jdCommandView(submission, definition, closeEditor);
  const current = profile.data;
  // One edit at a time, here and in the collections: an open editor froze its revision.
  const { heldByAnother } = useEditSlot(inlineEditorOpen || command.locked);
  const disabled =
    command.locked ||
    profile.isFetching ||
    profile.isError ||
    readOnly ||
    inlineEditorOpen ||
    heldByAnother;
  const status = statusOf(command);

  function saveInline(revisionId: string, intent: InlineIntent): InlineSaveResult {
    // A basic-data field only ever asks for a basic-data change.
    if (intent.collection !== 'profile') return 'invalid';
    const next = profileCommandFor(revisionId, intent);
    if (!isReviseJdProfileRequest(next)) return 'invalid';
    void command.send(next);
    return 'submitted';
  }
  const inlineEdit: InlineEdit | null = current
    ? {
        activeKey: inlineKey,
        open: (key) => setInlineKey(key),
        close: () => setInlineKey(null),
        revisionId: current.revision_id,
        save: saveInline,
        canOpen: !disabled,
        canEdit: !command.locked && !readOnly && !profile.isError,
        status: { ...status, message: draftNoticeOf(command.message, readOnly) },
        setEditorOpen: setInlineEditorOpen,
      }
    : null;

  return (
    <Paper
      component="section"
      id="jd-profile"
      variant="outlined"
      aria-labelledby="jd-profile-heading"
      sx={{ p: { xs: 1.5, sm: 2 } }}
    >
      <Stack spacing={2}>
        <Typography variant="overline" component="h2" id="jd-profile-heading" className="jd-label">
          JD 基本資料
        </Typography>
        {profile.isPending && <p role="status">正在讀取 JD 基本資料…</p>}
        {profile.isError && (
          <Alert
            severity="error"
            action={
              <Button
                color="inherit"
                onClick={() => {
                  void profile.refetch();
                }}
              >
                重新讀取 JD
              </Button>
            }
          >
            {describeReadError(profile.error)}
          </Alert>
        )}
        {/* An open editor shows this itself, next to the draft it belongs to. */}
        {current && !inlineEditorOpen && <WorkStatus {...status} />}
        {current && (
          <InlineEditContext.Provider value={inlineEdit}>
            <Box
              component="dl"
              sx={{
                m: 0,
                display: 'grid',
                gridTemplateColumns: { xs: '1fr', sm: '8.5rem minmax(0, 1fr)' },
                columnGap: 3,
                rowGap: { xs: 0.5, sm: 1.5 },
                alignItems: 'baseline',
              }}
            >
              {profileFields.map((field) => {
                const value = current.profile[field];
                const textField = profileTextField(field, value);
                return (
                  <Box key={field} sx={{ display: 'contents' }}>
                    <Typography
                      component="dt"
                      variant="body2"
                      color="text.secondary"
                      sx={{ mt: { xs: 1, sm: 0 } }}
                    >
                      {profileLabels[field]}
                    </Typography>
                    <Typography
                      component="dd"
                      className={field === 'job_title' ? 'jd-title-value' : undefined}
                      sx={{ m: 0, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}
                    >
                      <InlineText field={textField} inline>
                        {value ?? (
                          <Typography component="span" color="text.secondary">
                            尚未提供
                          </Typography>
                        )}
                      </InlineText>{' '}
                      {inlineKey !== textField.key && badge(profileTarget(field))}
                    </Typography>
                  </Box>
                );
              })}
            </Box>
          </InlineEditContext.Provider>
        )}
      </Stack>
    </Paper>
  );
}
