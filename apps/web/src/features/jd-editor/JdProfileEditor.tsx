/** Show only server-confirmed profile data; opening the form captures its edit baseline. */
import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Alert, Box, Button, Stack, Typography } from '@mui/material';
import type { JdProfileView } from '../../shared/api/generated/jd-profile-view';
import { describeReadError } from '../../shared/api/http';
import { EditJdProfileDialog } from './EditJdProfileDialog';
import { jdProfileQuery } from './jd-profile-api';
import { jdWorkQuery } from './jd-work-api';
import { profileFields, profileLabels } from './profile-command';

export function JdProfileEditor({ jobFileId }: { jobFileId: string }) {
  const queryClient = useQueryClient();
  const profile = useQuery(jdProfileQuery(jobFileId));
  const [editing, setEditing] = useState<JdProfileView | null>(null);
  function refresh(): void {
    setEditing(null);
    void queryClient.invalidateQueries({ queryKey: jdProfileQuery(jobFileId).queryKey });
    void queryClient.invalidateQueries({ queryKey: jdWorkQuery(jobFileId).queryKey });
  }
  return (
    <section aria-labelledby="jd-profile-heading">
      <Stack spacing={2}>
        <Typography variant="h6" component="h2" id="jd-profile-heading">
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
        {profile.data && !profile.isError && (
          <>
            <Box
              component="dl"
              sx={{
                m: 0,
                display: 'grid',
                gridTemplateColumns: { xs: '1fr', sm: '11rem 1fr' },
                gap: 1,
              }}
            >
              {profileFields.map((field) => (
                <Box key={field} sx={{ display: 'contents' }}>
                  <Typography component="dt" sx={{ fontWeight: 600 }}>
                    {profileLabels[field]}
                  </Typography>
                  <Typography
                    component="dd"
                    sx={{ m: 0, mb: 1, whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}
                  >
                    {profile.data.profile[field] ?? '尚未提供'}
                  </Typography>
                </Box>
              ))}
            </Box>
            <div>
              <Button
                variant="outlined"
                disabled={profile.isFetching}
                onClick={() => {
                  if (profile.data) setEditing(profile.data);
                }}
              >
                編輯基本資料
              </Button>
            </div>
          </>
        )}
      </Stack>
      {editing && (
        <EditJdProfileDialog
          jobFileId={jobFileId}
          baseline={editing}
          onClose={() => setEditing(null)}
          onRefresh={refresh}
        />
      )}
    </section>
  );
}
