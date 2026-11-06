import { useRef, useState } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import { Link as RouterLink, useNavigate } from 'react-router';
import {
  Alert,
  Button,
  Container,
  Link,
  Paper,
  Skeleton,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import type { WorkspaceResponse } from '../../shared/api/generated/types.gen';
import { IconAction } from '../../shared/ui/IconAction';
import { AddIcon, CloseIcon, EditIcon, RefreshIcon } from '../../shared/ui/icons';
import { workspaceErrorMessage } from './errors';
import { workspaceListOptions } from './queries';
import { WorkspaceForm } from './WorkspaceForm';
import { DeleteWorkspaceDialog } from './DeleteWorkspaceDialog';

type WorkspaceDialog =
  { kind: 'create' } | { kind: 'rename' | 'delete'; workspace: WorkspaceResponse } | null;

export function WorkspaceListPage({
  onDeleted,
}: {
  onDeleted?: ((workspaceId: string) => Promise<void>) | undefined;
}) {
  const navigate = useNavigate();
  const workspaces = useInfiniteQuery(workspaceListOptions);
  const createButton = useRef<HTMLButtonElement>(null);
  const [filter, setFilter] = useState('');
  const [dialog, setDialog] = useState<WorkspaceDialog>(null);
  const items = workspaces.data?.pages.flatMap((page) => page.items) ?? [];
  const visible = items.filter((workspace) =>
    workspace.interviewee_name.toLocaleLowerCase().includes(filter.toLocaleLowerCase()),
  );
  function closeDialog() {
    setDialog(null);
  }
  function deleted() {
    setDialog(null);
    // MUI restores a dialog's trigger; the deleted row no longer exists.
    requestAnimationFrame(() => {
      if (document.activeElement === document.body) createButton.current?.focus();
    });
  }
  return (
    <Container maxWidth="md" className="workspace-list-page" sx={{ py: 6 }}>
      <Stack spacing={4} className="job-files-page">
        <div className="page-heading">
          <div>
            <Typography variant="h4" component="h1">
              職務檔案
            </Typography>
            <p>以訪談理解工作，逐步形成有依據的職務說明書。</p>
          </div>
          <Button
            ref={createButton}
            variant="contained"
            startIcon={<AddIcon />}
            aria-label="建立工作區"
            onClick={() => setDialog({ kind: 'create' })}
          >
            建立工作區
          </Button>
        </div>
        <Stack
          direction={{ xs: 'column', sm: 'row' }}
          spacing={2}
          sx={{ alignItems: { sm: 'center' }, justifyContent: 'space-between' }}
        >
          <TextField
            size="small"
            type="search"
            label="篩選已載入的受訪者"
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
          />
          <Stack direction="row" spacing={1} sx={{ alignItems: 'center' }}>
            <Typography variant="caption" color="text.secondary">
              已載入 {items.length} 份
            </Typography>
            <IconAction
              label="重新讀取工作區"
              disabled={workspaces.isFetching}
              onClick={() => {
                void workspaces.refetch();
              }}
            >
              <RefreshIcon />
            </IconAction>
          </Stack>
        </Stack>
        {workspaces.isPending && (
          <Stack spacing={1}>
            <p role="status" className="loading-note">
              正在讀取工作區…
            </p>
            {[0, 1, 2].map((row) => (
              <Skeleton key={row} variant="rounded" height={68} />
            ))}
          </Stack>
        )}
        {workspaces.isError && (
          <Alert
            severity="error"
            action={
              <Button
                color="inherit"
                onClick={() => {
                  void workspaces.refetch();
                }}
              >
                重新讀取
              </Button>
            }
          >
            {workspaceErrorMessage(workspaces.error)}
          </Alert>
        )}
        {workspaces.data && (
          <>
            {visible.length === 0 ? (
              <Paper variant="outlined" className="empty-state">
                <Typography variant="h6" component="h2">
                  {filter ? '沒有符合的受訪者' : '尚無職務檔案'}
                </Typography>
                <p>
                  {filter
                    ? '只篩選目前已載入的清單，也可以繼續載入更多。'
                    : '先建立一份工作區，記錄受訪者與工作。'}
                </p>
              </Paper>
            ) : (
              <TableContainer component={Paper} variant="outlined" className="file-list">
                <Table
                  aria-label="工作區清單"
                  sx={{ '& .MuiTableCell-root': { px: { xs: 1.5, sm: 2.5 } } }}
                >
                  <TableHead>
                    <TableRow>
                      <TableCell>受訪者</TableCell>
                      <TableCell align="right">操作</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {visible.map((workspace) => (
                      <TableRow key={workspace.workspace_id} hover className="file-row">
                        <TableCell>
                          <Stack
                            direction="row"
                            spacing={1.5}
                            sx={{ alignItems: 'center' }}
                          >
                            <span className="file-avatar" aria-hidden="true">
                              {Array.from(workspace.interviewee_name.trim())[0]}
                            </span>
                            <Link
                              component={RouterLink}
                              to={'/workspaces/' + workspace.workspace_id + '/jd'}
                              underline="none"
                              color="text.primary"
                              className="row-link"
                              title={workspace.workspace_id}
                            >
                              {workspace.interviewee_name}
                            </Link>
                          </Stack>
                        </TableCell>
                        <TableCell align="right" sx={{ whiteSpace: 'nowrap' }}>
                          <IconAction
                            className="row-action"
                            label={'變更 ' + workspace.interviewee_name + ' 的姓名'}
                            onClick={() => setDialog({ kind: 'rename', workspace })}
                          >
                            <EditIcon />
                          </IconAction>
                          <IconAction
                            className="row-action"
                            color="error"
                            label={'刪除 ' + workspace.interviewee_name + ' 的工作區'}
                            onClick={() => setDialog({ kind: 'delete', workspace })}
                          >
                            <CloseIcon />
                          </IconAction>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </>
        )}
        {workspaces.hasNextPage && (
          <Button
            variant="outlined"
            disabled={workspaces.isFetching}
            onClick={() => {
              void workspaces.fetchNextPage();
            }}
          >
            {workspaces.isFetchingNextPage ? '讀取中…' : '載入更多'}
          </Button>
        )}
        <Typography variant="caption" color="text.secondary">
          工作區之間的內容與歷史各自獨立。
        </Typography>
      </Stack>
      {dialog?.kind === 'create' && (
        <WorkspaceForm
          onClose={closeDialog}
          onSaved={(workspace) => {
            closeDialog();
            void navigate('/workspaces/' + workspace.workspace_id + '/jd');
          }}
        />
      )}
      {dialog?.kind === 'rename' && (
        <WorkspaceForm
          workspace={dialog.workspace}
          onClose={closeDialog}
          onSaved={closeDialog}
        />
      )}
      {dialog?.kind === 'delete' && (
        <DeleteWorkspaceDialog
          workspace={dialog.workspace}
          onClose={deleted}
          onDeleted={onDeleted}
        />
      )}
    </Container>
  );
}
