import { useEffect } from 'react';
import { updateJobDescription } from '../content-api';
import { EditableText } from '../editing/EditableText';
import { useJobDescriptionEditor } from '../editing/useJobDescriptionEditor';
import { CatalogEditor } from './CatalogEditor';
import { ConditionsEditor } from './ConditionsEditor';
import { DutiesEditor } from './DutiesEditor';
import { CompetencyLevelPicker } from './CompetencyLevelPicker';
import { FoldableSection } from './FoldableSection';
import { JdOutline } from './JdOutline';
import { revealJdTarget } from './jd-navigation';
import { SourceBadge } from '../sources/SourceBadge';
import '../job-description.css';
import './editor.css';

export function JobDescriptionEditor() {
  const { jobDescription: jd, blocked, editingKey, execute } = useJobDescriptionEditor();
  useEffect(() => {
    const id = window.location.hash.slice(1);
    if (id) requestAnimationFrame(() => revealJdTarget(id));
  }, []);
  return (
    <div className="jd-reader jd-editor">
      <JdOutline />
      <article className="jd-document" aria-labelledby="jd-title">
        <header className="jd-document-heading">
          <h1 id="jd-title" tabIndex={-1}>
            職務說明書
          </h1>
          <p className="jd-document-meta">
            職務說明書 <span aria-hidden="true">·</span> 版本 {jd.version}
          </p>
        </header>
        <FoldableSection
          id="jd-basic"
          title="基本資料"
          actions={
            <SourceBadge targetKind="job_description" targetId={jd.job_description_id} />
          }
        >
          <div className="jd-basic-fields">
            {(
              [
                { key: 'job_title', label: '職務名稱' },
                { key: 'organization_unit', label: '組織單位' },
                { key: 'reports_to', label: '直屬主管' },
                { key: 'purpose', label: '職務目的' },
              ] as const
            ).map(({ key, label }) => (
              <div
                className={key === 'purpose' ? 'jd-field jd-field-wide' : 'jd-field'}
                key={key}
              >
                <EditableText
                  draftKey={`basic.${key}`}
                  label={label}
                  value={jd[key]}
                  multiline={key === 'purpose'}
                  onSave={(value, current) =>
                    updateJobDescription(
                      current.workspace_id,
                      current.job_description_id,
                      {
                        expected_version: current.version,
                        [key]: value === '' ? null : value,
                      },
                    )
                  }
                />
              </div>
            ))}
            <CompetencyLevelPicker
              label="基準職能級別"
              value={jd.baseline_competency_level}
              disabled={blocked || editingKey !== null}
              onChange={(value) => {
                return execute((current) =>
                  updateJobDescription(current.workspace_id, current.job_description_id, {
                    expected_version: current.version,
                    baseline_competency_level: value,
                  }),
                );
              }}
            />
          </div>
        </FoldableSection>
        <DutiesEditor />
        <FoldableSection
          id="jd-competencies"
          title="知識與技能"
          count={jd.knowledge.length + jd.skills.length}
        >
          <div className="jd-catalogs">
            <CatalogEditor kind="knowledge" />
            <CatalogEditor kind="skills" />
          </div>
        </FoldableSection>
        <ConditionsEditor />
      </article>
    </div>
  );
}
