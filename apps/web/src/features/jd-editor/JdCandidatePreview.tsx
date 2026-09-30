/** Read-only candidate projection; never writes formal caches or supplies PDF content. */
import { Alert, Box, Stack, Typography } from '@mui/material';
import type {
  CandidateJdPreview,
  Condition,
  WorkTask,
} from '../../shared/api/generated/consultant-turn';

const conditionLabels: Record<Condition['kind'], string> = {
  work_environment: '工作環境',
  schedule_travel: '工時與出差',
  shared_authority: '共通權限界線',
  shared_collaboration: '共通協作界線',
  qualification: '必要資格',
};

function PreviewTasks({ tasks, work }: { tasks: WorkTask[]; work: CandidateJdPreview['work'] }) {
  return tasks.map((task) => (
    <Box key={task.task_id} sx={{ pl: 2, borderLeft: 2, borderColor: 'divider' }}>
      <Typography component="h4" variant="subtitle1">
        {task.title ?? '任務（名稱尚未提供）'}
      </Typography>
      <Typography sx={{ whiteSpace: 'pre-wrap' }}>{task.description ?? '內容尚未提供'}</Typography>
      {(
        [
          ['成果', task.outcomes],
          ['執行要求', task.requirements],
        ] as const
      ).map(
        ([label, details]) =>
          details.length > 0 && (
            <Box key={label}>
              <Typography component="h5" variant="subtitle2">
                {label}
              </Typography>
              <ul>
                {details.map((detail) => (
                  <li key={detail.detail_id} style={{ whiteSpace: 'pre-wrap' }}>
                    {detail.text}
                  </li>
                ))}
              </ul>
            </Box>
          ),
      )}
      {work.task_links
        .filter((link) => link.task_id === task.task_id)
        .map((link) => {
          const capability = work.capabilities.find(
            (item) => item.capability_id === link.capability_id,
          );
          return (
            capability && (
              <Typography key={link.capability_id} variant="body2">
                {capability.kind === 'knowledge' ? '知識' : '技能'}：
                {capability.name ?? '名稱尚未提供'}
              </Typography>
            )
          );
        })}
    </Box>
  ));
}

export function JdCandidatePreview({ candidate }: { candidate: CandidateJdPreview }) {
  const { profile, work } = candidate;
  const unassigned = work.tasks.filter((task) => task.area_id === null);
  return (
    <Stack
      component="section"
      aria-label="JD 候選預覽"
      spacing={2}
      sx={{ p: 2, border: 1, borderColor: 'divider', overflowWrap: 'anywhere' }}
    >
      <Typography component="h2" variant="h6">
        JD 候選預覽
      </Typography>
      <Alert severity="info">尚未正式保存；完成前不會取代正式 JD，PDF 仍匯出正式版本。</Alert>
      <Box component="dl" sx={{ m: 0 }}>
        {(
          [
            ['job_title', '職稱'],
            ['organization_unit', '組織單位'],
            ['reports_to', '匯報對象'],
            ['purpose', '職務目的'],
          ] as const
        ).map(([field, label]) => (
          <Box key={field} sx={{ mb: 1 }}>
            <Typography component="dt" variant="subtitle2">
              {label}
            </Typography>
            <Typography component="dd" sx={{ ml: 0, whiteSpace: 'pre-wrap' }}>
              {profile[field] ?? '尚未提供'}
            </Typography>
          </Box>
        ))}
      </Box>
      {work.areas.map((area) => (
        <Stack key={area.area_id} spacing={1}>
          <Typography component="h3" variant="subtitle1">
            {area.title ?? '職責（名稱尚未提供）'}
          </Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>
            {area.scope_text ?? '範圍尚未提供'}
          </Typography>
          <PreviewTasks
            tasks={work.tasks.filter((task) => task.area_id === area.area_id)}
            work={work}
          />
        </Stack>
      ))}
      {unassigned.length > 0 && (
        <Stack spacing={1}>
          <Typography component="h3" variant="subtitle1">
            未歸屬任務
          </Typography>
          <PreviewTasks tasks={unassigned} work={work} />
        </Stack>
      )}
      {work.capabilities.map((item) => (
        <Box key={item.capability_id}>
          <Typography component="h3" variant="subtitle1">
            {item.kind === 'knowledge' ? '知識' : '技能'}：{item.name ?? '名稱尚未提供'}
          </Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>
            {item.description ?? '說明尚未提供'}
          </Typography>
        </Box>
      ))}
      {work.collaborators.map((item) => (
        <Box key={item.collaborator_id}>
          <Typography component="h3" variant="subtitle1">
            協作對象：{item.name ?? '名稱尚未提供'}
          </Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>
            {item.scope_text ?? '合作範圍尚未提供'}
          </Typography>
        </Box>
      ))}
      {work.conditions.map((item) => (
        <Box key={item.condition_id}>
          <Typography component="h3" variant="subtitle1">
            {conditionLabels[item.kind]}
          </Typography>
          <Typography sx={{ whiteSpace: 'pre-wrap' }}>{item.text}</Typography>
        </Box>
      ))}
    </Stack>
  );
}
