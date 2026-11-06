/** Published map → fixed-version item → original sources, without background-job guesses. */
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
import type { MemoryMapEntryResponse } from '../../shared/api/generated/types.gen';
import { SafeMarkdown } from '../../shared/ui/SafeMarkdown';
import { describeMemoryError } from './errors';
import { memoryItemOptions, memoryMapOptions } from './queries';
import { MemorySourceMessage } from './MemorySourceMessage';

interface MemoryViewerProps {
  workspaceId: string;
  open: boolean;
  onClose: () => void;
}

export function MemoryViewer({ workspaceId, open, onClose }: MemoryViewerProps) {
  const titleId = useId();
  return (
    <Dialog
      open={open}
      onClose={onClose}
      aria-labelledby={titleId}
      fullWidth
      maxWidth="md"
    >
      <DialogTitle id={titleId}>目前已發布的 Memory</DialogTitle>
      <DialogContent>
        {open && <MemoryBrowser key={workspaceId} workspaceId={workspaceId} />}
      </DialogContent>
      <DialogActions>
        <Button variant="outlined" onClick={onClose}>
          關閉
        </Button>
      </DialogActions>
    </Dialog>
  );
}

interface ItemSelection {
  publishedVersion: number;
  itemId: string;
}

function MemoryBrowser({ workspaceId }: { workspaceId: string }) {
  const [path, setPath] = useState<ItemSelection[]>([]);
  const [returnFocusId, setReturnFocusId] = useState<string | null>(null);
  const query = useQuery(memoryMapOptions(workspaceId));
  const selected = path.at(-1);
  if (selected)
    return (
      <>
        <Button
          key={`back:${selected.publishedVersion}:${selected.itemId}`}
          autoFocus
          size="small"
          onClick={() => setPath(path.slice(0, -1))}
        >
          {path.length > 1 ? '← 回到工作理解' : '← 回到 Memory 導覽'}
        </Button>
        <MemoryItem
          key={`${selected.publishedVersion}:${selected.itemId}`}
          workspaceId={workspaceId}
          {...selected}
          onOpenSituation={(itemId) =>
            setPath([...path, { publishedVersion: selected.publishedVersion, itemId }])
          }
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
        <Typography variant="body2">
          已發布的整理內容。閱讀不會改變顧問這輪使用的版本。
        </Typography>
        <Button
          autoFocus={!memory?.items.some((item) => item.item_id === returnFocusId)}
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
          {describeMemoryError(query.error)}
          {memory && ' 以下保留上次讀取的版本。'}
        </Alert>
      )}
      {memory &&
        (memory.published_version === null ? (
          <p>尚無已發布的 Memory。</p>
        ) : (
          <>
            <Version value={memory.published_version} />
            {(['situation', 'understanding'] as const).map((kind) => (
              <MemorySection
                key={kind}
                title={kind === 'situation' ? '工作情境' : '工作理解'}
                items={memory.items.filter((item) => item.kind === kind)}
                returnFocusId={returnFocusId}
                onSelect={(itemId) => {
                  if (memory.published_version !== null) {
                    setReturnFocusId(itemId);
                    setPath([{ publishedVersion: memory.published_version, itemId }]);
                  }
                }}
              />
            ))}
          </>
        ))}
    </>
  );
}

function MemorySection({
  title,
  items,
  returnFocusId,
  onSelect,
}: {
  title: string;
  items: MemoryMapEntryResponse[];
  returnFocusId: string | null;
  onSelect: (itemId: string) => void;
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
            <Box component="li" key={item.item_id} sx={{ mb: 1.5 }}>
              <Button
                autoFocus={returnFocusId === item.item_id}
                size="small"
                onClick={() => onSelect(item.item_id)}
                sx={{ textAlign: 'left', overflowWrap: 'anywhere' }}
              >
                {item.title}
              </Button>
              <Typography
                variant="body2"
                sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}
              >
                {item.description}
              </Typography>
            </Box>
          ))}
        </Box>
      )}
    </Box>
  );
}

function MemoryItem({
  workspaceId,
  publishedVersion,
  itemId,
  onOpenSituation,
}: ItemSelection & {
  workspaceId: string;
  onOpenSituation: (itemId: string) => void;
}) {
  const query = useQuery(memoryItemOptions(workspaceId, publishedVersion, itemId));
  const [sourceId, setSourceId] = useState<string | null>(null);
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
        <Alert severity="error">{describeMemoryError(query.error)}</Alert>
      ) : (
        <Box component="article" sx={{ mt: 2 }}>
          <Version value={publishedVersion} />
          <Typography variant="body2">
            {query.data.kind === 'situation' ? '工作情境' : '工作理解'}
          </Typography>
          <Typography
            component="h3"
            variant="h6"
            sx={{ overflowWrap: 'anywhere', mt: 1 }}
          >
            {query.data.title}
          </Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere', my: 1 }}>
            {query.data.description}
          </Typography>
          <SafeMarkdown markdown={query.data.body} />
          <Box component="section" aria-label="Memory 來源" sx={{ mt: 3 }}>
            <Typography component="h4" variant="subtitle2">
              {query.data.kind === 'situation' ? '訪談來源' : '同一發布版的工作情境來源'}
            </Typography>
            {query.data.source_ids.length === 0 ? (
              <p>此項目沒有列出的來源。</p>
            ) : (
              <Stack direction="row" sx={{ flexWrap: 'wrap', gap: 1, my: 1 }}>
                {query.data.source_ids.map((id, index) => (
                  <Button
                    key={id}
                    size="small"
                    variant="outlined"
                    aria-pressed={
                      query.data.kind === 'situation' ? sourceId === id : undefined
                    }
                    onClick={() => {
                      if (query.data.kind === 'situation') setSourceId(id);
                      else onOpenSituation(id);
                    }}
                  >
                    {query.data.kind === 'situation' ? '訪談來源' : '工作情境來源'}{' '}
                    {index + 1}
                  </Button>
                ))}
              </Stack>
            )}
            {query.data.kind === 'situation' && sourceId && (
              <MemorySourceMessage
                key={sourceId}
                workspaceId={workspaceId}
                messageId={sourceId}
              />
            )}
          </Box>
        </Box>
      )}
    </>
  );
}

function Version({ value }: { value: number }) {
  return (
    <Typography
      variant="caption"
      component="p"
      sx={{ color: 'text.secondary', overflowWrap: 'anywhere', my: 1 }}
    >
      發布版本：{value}
    </Typography>
  );
}
