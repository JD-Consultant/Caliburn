/* Generated from apps/api/contracts; do not edit. */

export type Areas = Area[];
export type Tasks = WorkTask[];
export type Capabilities = Capability[];
export type TaskLinks = TaskLink[];
export type Collaborators = Collaborator[];
export type Conditions = Condition[];

/**
 * Read-only discovery for an existing job file. Turn is the admitted active or paused consultant (including pending pause), or explicit null when none exists. Excludes terminal history and Memory work. A missing job file is HTTP 404.
 */
export interface CurrentConsultantTurn {
  turn: ConsultantTurn | null;
}
export interface ConsultantTurn {
  job_file_id: string;
  execution_id: string;
  status: 'active' | 'paused' | 'completed' | 'cancelled' | 'failed';
  /**
   * Persisted pause intent, not a safe-Step acknowledgement. Active plus true means waiting for a safe Step; paused remains true until resume or cancellation clears it. False does not imply supervisor availability.
   */
  pause_requested: boolean;
  input_text: string;
  /**
   * Complete saved assistant commentary in original order; not formal interview sources. Null means the reader is not configured, not an empty history.
   */
  commentary: PublicCommentary[] | null;
  /**
   * A read-only candidate from one fixed revision, only while active or paused. Null also covers the interval before candidate initialization. Never the formal JD or PDF source.
   */
  candidate: CandidateJdPreview | null;
  /**
   * Currently available App controls; each request rechecks the scoped execution. Pause records intent until a safe Step acknowledges it. Empty when terminal or controls are not configured.
   *
   * @maxItems 3
   */
  allowed_controls:
    | []
    | ['pause' | 'cancel' | 'resume']
    | ['pause' | 'cancel' | 'resume', 'pause' | 'cancel' | 'resume']
    | ['pause' | 'cancel' | 'resume', 'pause' | 'cancel' | 'resume', 'pause' | 'cancel' | 'resume'];
}
export interface PublicCommentary {
  response_id: string;
  message_id: string;
  text: string;
}
export interface CandidateJdPreview {
  profile: Profile;
  work: {
    revision_id: string;
    areas: Areas;
    tasks: Tasks;
    capabilities: Capabilities;
    task_links: TaskLinks;
    collaborators: Collaborators;
    conditions: Conditions;
  };
}
export interface Profile {
  job_title: string | null;
  organization_unit: string | null;
  reports_to: string | null;
  purpose: string | null;
}
export interface Area {
  area_id: string;
  title: string | null;
  scope_text: string | null;
}
export interface WorkTask {
  task_id: string;
  area_id: string | null;
  title: string | null;
  description: string | null;
  outcomes: Detail[];
  requirements: Detail[];
}
export interface Detail {
  detail_id: string;
  text: string;
}
export interface Capability {
  capability_id: string;
  kind: 'knowledge' | 'skill';
  name: string | null;
  description: string | null;
}
export interface TaskLink {
  task_id: string;
  capability_id: string;
}
export interface Collaborator {
  collaborator_id: string;
  name: string | null;
  scope_text: string | null;
}
export interface Condition {
  condition_id: string;
  kind:
    | 'work_environment'
    | 'schedule_travel'
    | 'shared_authority'
    | 'shared_collaboration'
    | 'qualification';
  text: string;
}
