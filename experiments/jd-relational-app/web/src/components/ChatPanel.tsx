'use client';
import { Alert, Box, Button, Chip, Divider, Paper, Stack, TextField, Typography } from '@mui/material';
import type { SessionSnapshot } from '../lib/session';
import type { ChatController, ChatSnapshot } from '../lib/chat-session';
import type { ChatRunState } from '../../../src/jd_relational/generated/jd-chat-http';

function runLabel(run: ChatRunState): string {
  switch (run.run_status) {
    case 'running': return run.stop_requested ? '已請求停止，等待安全結束' : 'AI 正在整理你的工作';
    case 'closing': return '正在確認保存並收尾';
    case 'recovery_required': return '原回合需要完成收尾';
    case 'completed': return '本輪回覆已完成';
    case 'cancelled': return '本輪已停止';
    case 'failed': return run.input_state === 'saved' ? '原話已保存，回覆未完成' : '這次原話尚未保存';
    case 'not_found': return '尚未查到原回合，結果仍待確認';
  }
}

export default function ChatPanel({ snapshot, chat, controller, archived, holding, onText, onComposition, onChange }: {
  snapshot: SessionSnapshot; chat: ChatSnapshot; controller: ChatController | null; archived: boolean;
  holding?: boolean;
  onText: (text: string) => void; onComposition: (active: boolean) => void; onChange: (ref: string) => void;
}) {
  const original = snapshot.row?.chatSubmission;
  const run = chat.run?.run_id === chat.runId
    && (!original || original.request.run_id === chat.runId) ? chat.run : null;
  const committed = run?.jd_effects.results.filter(result => result.status === 'committed') ?? [];
  const pendingNotInHistory = original && !chat.messages.some(message => message.role === 'user' && message.run_id === original.request.run_id);
  return <Paper component="section" aria-label="工作訪談" sx={{ p: 2.5, alignSelf: 'start', minWidth: 0 }}>
    <Chip label="你的工作顧問" size="small" variant="outlined" />
    <Typography variant="h6" sx={{ mt: 2 }}>從實際工作，逐步整理。</Typography>
    <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>說說你負責的工作、實際例子與需要更正的地方。資料足夠時，AI 會整理到右側 JD。</Typography>
    <Divider sx={{ my: 2 }} />
    <Box sx={{ maxHeight: '55vh', overflowY: 'auto', overflowWrap: 'anywhere' }}>
      {chat.page?.next_cursor && <Button disabled={chat.busy} onClick={() => void controller?.more()}>載入較早對話</Button>}
      {chat.loading && <Typography role="status">讀取已保存的對話…</Typography>}
      {!chat.loading && !chat.messages.length && <Typography color="text.secondary" sx={{ mb: 2 }}>可以先從「我平常負責……」開始。不用一次說完。</Typography>}
      {chat.messages.map(message => <Box key={message.message_id} sx={{ mb: 2, p: 1.5,
        bgcolor: message.role === 'user' ? 'action.hover' : 'transparent', borderRadius: 1 }}>
        <Typography variant="caption" color="text.secondary">{message.role === 'user' ? '你' : 'AI 顧問'}</Typography>
        <Typography className="jd-text">{message.text}</Typography>
      </Box>)}
      {pendingNotInHistory && <Paper variant="outlined" sx={{ p: 1.5, mb: 2 }}>
        <Typography variant="caption">{run?.input_state === 'saved'
          ? '原話已保存；目前對話頁未顯示這段原文'
          : run?.input_state === 'not_saved' ? '原話尚未保存，原輸入仍保留在此瀏覽器'
            : '原輸入保留在此瀏覽器，正在確認接收結果'}</Typography>
        <Typography className="jd-text">{original.request.text}</Typography>
      </Paper>}
    </Box>
    {run && <Box sx={{ my: 2 }}>
      <Typography role="status" variant="body2">{runLabel(run)}</Typography>
      {run.input_state === 'unconfirmed' && <Typography variant="caption">原話是否保存仍待查明。</Typography>}
      {run.jd_effects.state === 'unconfirmed' && <Typography variant="body2" color="text.secondary">本輪修改結果尚未全部確認；已保存的修改可先查看。</Typography>}
      {run.jd_effects.state === 'settled' && !committed.length && <Typography variant="body2" color="text.secondary">本輪沒有修改 JD。</Typography>}
      {committed.length > 0 && <Box sx={{ mt: 1 }}>
        <Typography variant="body2">已保存 {committed.length} 次 JD 修改</Typography>
        <Stack>{committed.map((result, index) => <Button key={result.operation_ref} sx={{ justifyContent: 'flex-start' }}
          disabled={!result.change_ref} onClick={() => { if (result.change_ref) onChange(result.change_ref); }}>查看第 {index + 1} 次實際改動</Button>)}</Stack>
      </Box>}
    </Box>}
    {chat.error && <Alert severity="warning" sx={{ my: 2 }}>{chat.error.message}</Alert>}
    <Stack direction="row" sx={{ gap: 0.5, flexWrap: 'wrap', mb: 1 }}>
      <Button disabled={chat.busy || chat.loading} onClick={() => void controller?.refresh()}>重新查看</Button>
      {chat.canRetry && <Button disabled={chat.busy} onClick={() => void controller?.retry()}>繼續原送出</Button>}
      {run?.run_status === 'running' && !run.stop_requested && <Button disabled={chat.busy} onClick={() => void controller?.cancel()}>停止本輪</Button>}
      {run?.run_status === 'recovery_required' && <Button disabled={chat.busy} onClick={() => void controller?.recover()}>完成原回合收尾</Button>}
      {run?.input_state === 'not_saved' && original && <Button disabled={chat.busy || snapshot.chatText.length > 0}
        onClick={() => void controller?.restore()}>取回原話編輯</Button>}
    </Stack>
    <TextField label="告訴顧問你的工作" value={snapshot.chatText} onChange={event => onText(event.target.value)}
      multiline minRows={3} maxRows={10} fullWidth disabled={snapshot.loading || !snapshot.row || snapshot.chatSending || archived}
      slotProps={{ htmlInput: { onCompositionStart: () => onComposition(true), onCompositionEnd: () => onComposition(false) } }} />
    <Stack direction="row" sx={{ mt: 1, gap: 1, alignItems: 'center', justifyContent: 'space-between' }}>
      <Typography variant="caption" color="text.secondary">{snapshot.chatSaving ? '保留輸入中…' : snapshot.chatText ? '輸入已暫存於此瀏覽器' : 'Enter 換行，按送出開始訪談'}</Typography>
      <Button variant="contained" disabled={!snapshot.chatReady || chat.busy || chat.loading || !snapshot.chatText.trim() || archived || !!holding}
        onClick={() => void controller?.send()}>送出</Button>
    </Stack>
    {holding && <Typography variant="caption" color="text.secondary">正在確認一次還原，暫停送出。你的輸入會保留。</Typography>}
    {run?.run_status === 'running' && <Typography variant="caption" color="text.secondary">JD 暫停手改。可以先輸入下一段，完成本輪後再送出。</Typography>}
  </Paper>;
}
