/* Generated from apps/api/contracts; do not edit. */

export interface ReadJdChangesArguments {
  query: ManualQuery | SourceQuery;
}
export interface ManualQuery {
  kind: 'manual';
  scope: AllScope | AreaScope | ItemScope | ProfileFieldScope;
}
export interface AllScope {
  kind: 'all';
}
export interface AreaScope {
  kind: 'area';
  view:
    | 'profile'
    | 'responsibility_areas'
    | 'unassigned_work_tasks'
    | 'required_knowledge'
    | 'required_skills'
    | 'main_collaborators'
    | 'job_wide_conditions';
}
export interface ItemScope {
  kind: 'item';
  read_ref: string;
}
export interface ProfileFieldScope {
  kind: 'profile_field';
  field: 'job_title' | 'organization_unit' | 'reports_to' | 'purpose';
}
export interface SourceQuery {
  kind: 'source';
  citation_ref: string;
}
