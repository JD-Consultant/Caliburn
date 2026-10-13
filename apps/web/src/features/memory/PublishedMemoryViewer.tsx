/** Read the current publication map, then keep every body read pinned to that snapshot. */
import { useId, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Stack,
  Typography,
} from '@mui/material';
import type { PublishedMemory } from '../../shared/api/generated/http/types.gen';
import { describeReadError } from '../../shared/api/http';
import { SafeMarkdown } from '../../shared/ui/SafeMarkdown';
import { memoryObjectQuery, publishedMemoryQuery } from './memory-api';

export function PublishedMemoryViewer({ jobFileId }: { jobFileId: string }) {
  return <MemoryDisclosure key={jobFileId} jobFileId={jobFileId} />;
}

function MemoryDisclosure({ jobFileId }: { jobFileId: string }) {
  const [open, setOpen] = useState(false);
  const titleId = useId();
  return (
    <>
      <Button size="small" variant="outlined" onClick={() => setOpen(true)} sx={{ flexShrink: 0 }}>
        Memory
      </Button>
      <Dialog
        open={open}
        onClose={() => setOpen(false)}
        aria-labelledby={titleId}
        fullWidth
        maxWidth="md"
      >
        <DialogTitle id={titleId}>目前已發布的 Memory</DialogTitle>
        <DialogContent>{open && <MemoryBrowser jobFileId={jobFileId} />}</DialogContent>
        <DialogActions>
          <Button variant="outlined" onClick={() => setOpen(false)}>
            關閉
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}

function MemoryBrowser({ jobFileId }: { jobFileId: string }) {
  const [selected, setSelected] = useState<{ snapshotId: string; objectId: string } | null>(null);
  const query = useQuery(publishedMemoryQuery(jobFileId));
  if (selected !== null)
    return (
      <>
        <Button autoFocus size="small" onClick={() => setSelected(null)}>
          ← 回到 Memory 導覽
        </Button>
        <MemoryObject
          key={`${selected.snapshotId}:${selected.objectId}`}
          jobFileId={jobFileId}
          {...selected}
        />
      </>
    );
  const memory = query.data;
  return (
    <>
      <Stack
        direction="row"
        spacing={1}
        sx={{ alignItems: 'center', justifyContent: 'space-between', mb: 2 }}
      >
        <Typography variant="body2">已發布的整理內容。閱讀不會改變顧問這輪使用的版本。</Typography>
        <Button
          autoFocus
          size="small"
          aria-disabled={query.isFetching}
          onClick={() => {
            if (!query.isFetching) void query.refetch();
          }}
          sx={{ flexShrink: 0 }}
        >
          重新讀取 Memory
        </Button>
      </Stack>
      {query.isFetching && <p role="status">正在確認最新發布版本…</p>}
      {query.isError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {describeReadError(query.error)}
          {memory && ' 以下保留上次讀取的版本。'}
        </Alert>
      )}
      {memory &&
        (memory.snapshot_id === null ? (
          <p>尚無已發布的 Memory。</p>
        ) : (
          <>
            <Version id={memory.snapshot_id} />
            <Typography variant="body2" sx={{ mb: 2 }}>
              涵蓋至第 {memory.covered_through_sequence} 則訪談。
            </Typography>
            <MemorySection
              title="工作情境"
              items={memory.work_situations}
              onSelect={(objectId) => {
                if (memory.snapshot_id !== null)
                  setSelected({ snapshotId: memory.snapshot_id, objectId });
              }}
            />
            <MemorySection
              title="工作理解"
              items={memory.work_understandings}
              onSelect={(objectId) => {
                if (memory.snapshot_id !== null)
                  setSelected({ snapshotId: memory.snapshot_id, objectId });
              }}
            />
          </>
        ))}
    </>
  );
}

function MemorySection({
  title,
  items,
  onSelect,
}: {
  title: string;
  items: PublishedMemory['work_situations'];
  onSelect: (objectId: string) => void;
}) {
  return (
    <Box component="section" sx={{ mb: 3 }}>
      <Typography component="h3" variant="h6">
        {title}（{items.length}）
      </Typography>
      {items.length === 0 ? (
        <p>此版本尚無{title}。</p>
      ) : (
        <Box component="ul" sx={{ pl: 2.5 }}>
          {items.map((item) => (
            <Box component="li" key={item.object_id} sx={{ mb: 1.5 }}>
              <Button
                size="small"
                onClick={() => onSelect(item.object_id)}
                sx={{ textAlign: 'left', overflowWrap: 'anywhere' }}
              >
                {item.title}
              </Button>
              <Typography variant="body2" sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>
                {item.description}
              </Typography>
            </Box>
          ))}
        </Box>
      )}
    </Box>
  );
}

function MemoryObject({
  jobFileId,
  snapshotId,
  objectId,
}: {
  jobFileId: string;
  snapshotId: string;
  objectId: string;
}) {
  const query = useQuery(memoryObjectQuery(jobFileId, snapshotId, objectId));
  return (
    <>
      <Button
        size="small"
        aria-disabled={query.isFetching}
        onClick={() => {
          if (!query.isFetching) void query.refetch();
        }}
      >
        重新讀取正文
      </Button>
      {query.isPending ? (
        <p role="status">正在讀取 Memory 正文…</p>
      ) : query.isError ? (
        <Alert severity="error">{describeReadError(query.error)}</Alert>
      ) : (
        <Box component="article" sx={{ mt: 2 }}>
          <Version id={snapshotId} />
          <Typography variant="body2">
            {query.data.layer === 'work_situation' ? '工作情境' : '工作理解'}
          </Typography>
          <Typography component="h3" variant="h6" sx={{ overflowWrap: 'anywhere', mt: 1 }}>
            {query.data.title}
          </Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', my: 1 }}>
            {query.data.description}
          </Typography>
          <SafeMarkdown markdown={query.data.body} />
        </Box>
      )}
    </>
  );
}

function Version({ id }: { id: string }) {
  return (
    <Typography
      variant="caption"
      component="p"
      sx={{ color: 'text.secondary', overflowWrap: 'anywhere', my: 1 }}
    >
      版本：{id}
    </Typography>
  );
}
