/** 唯讀 JD 的連續文件；資料與排序由已驗證的 API 回覆提供。 */
import { ChevronDown } from 'lucide-react';
import { useEffect, useId, useState, type ReactNode } from 'react';
import type { JobDescriptionResponse } from '../../shared/api/generated/types.gen';
import { TaskList } from './TaskList';
import { conditionLabels } from './labels';
import './job-description.css';

const sections = [
  { key: 'basic', label: '基本資料' },
  { key: 'duties', label: '職責與任務' },
  { key: 'competencies', label: '知識與技能' },
  { key: 'conditions', label: '協作與條件' },
] as const;

export function JobDescriptionDocument({
  jobDescription,
  idPrefix = 'jd',
}: {
  jobDescription: JobDescriptionResponse;
  idPrefix?: string;
}) {
  const headingId = (key: string) => `${idPrefix}-${key}`;
  useEffect(() => {
    const targetId = window.location.hash.slice(1);
    if (!sections.some((section) => `${idPrefix}-${section.key}` === targetId)) return;
    const heading = document.getElementById(targetId);
    heading?.scrollIntoView();
    heading?.focus({ preventScroll: true });
  }, [idPrefix]);
  const knowledgeNames = new Map(
    jobDescription.knowledge.map((item) => [item.id, item.name]),
  );
  const skillNames = new Map(jobDescription.skills.map((item) => [item.id, item.name]));
  const unclassifiedTasks = jobDescription.tasks.filter((task) => task.duty_id === null);
  const basicFields = [
    { label: '職務名稱', value: jobDescription.job_title },
    { label: '組織單位', value: jobDescription.organization_unit },
    { label: '直屬主管', value: jobDescription.reports_to },
    {
      label: '基準職能級別',
      value:
        jobDescription.baseline_competency_level === null
          ? null
          : `第 ${String(jobDescription.baseline_competency_level)} 級`,
    },
    { label: '職務目的', value: jobDescription.purpose, fullWidth: true },
  ];

  return (
    <div className="jd-reader">
      <nav aria-label="JD 章節" className="jd-outline">
        <div className="jd-outline-links">
          {sections.map((section) => (
            <a
              key={section.key}
              href={`#${headingId(section.key)}`}
              onClick={() => {
                document
                  .getElementById(headingId(section.key))
                  ?.focus({ preventScroll: true });
              }}
            >
              {section.label}
            </a>
          ))}
        </div>
        <span className="jd-reading-label">閱讀文件</span>
      </nav>

      <article className="jd-document" aria-labelledby={headingId('title')}>
        <header className="jd-document-heading">
          <p className="jd-eyebrow">JOB DESCRIPTION</p>
          <h1 id={headingId('title')} tabIndex={-1}>
            {jobDescription.job_title ?? '職務說明書'}
          </h1>
          <p className="jd-document-meta">
            職務說明書 <span aria-hidden="true">·</span> 版本 {jobDescription.version}
          </p>
        </header>

        <section className="jd-section" aria-labelledby={headingId('basic')}>
          <h2 id={headingId('basic')} tabIndex={-1}>
            基本資料
          </h2>
          <dl className="jd-basic-fields">
            {basicFields.map(({ label, value, fullWidth }) => (
              <div
                key={label}
                className={fullWidth ? 'jd-field jd-field-wide' : 'jd-field'}
              >
                <dt>{label}</dt>
                <dd>
                  {value !== null ? value : <span className="jd-empty">尚未填寫</span>}
                </dd>
              </div>
            ))}
          </dl>
        </section>

        <section className="jd-section" aria-labelledby={headingId('duties')}>
          <div className="jd-section-heading">
            <h2 id={headingId('duties')} tabIndex={-1}>
              職責與任務
            </h2>
            <p className="jd-section-count">
              {jobDescription.duties.length} 項職責 <span aria-hidden="true">·</span>{' '}
              {jobDescription.tasks.length} 項任務
            </p>
          </div>
          {jobDescription.duties.length === 0 && jobDescription.tasks.length === 0 && (
            <p className="jd-empty">尚未建立職責與任務。</p>
          )}
          {jobDescription.duties.map((duty) => (
            <DutySection key={duty.id} name={duty.name} scope={duty.scope}>
              <TaskList
                tasks={jobDescription.tasks.filter((task) => task.duty_id === duty.id)}
                knowledgeNames={knowledgeNames}
                skillNames={skillNames}
              />
            </DutySection>
          ))}
          {unclassifiedTasks.length > 0 && (
            <DutySection name="未分類任務">
              <TaskList
                tasks={unclassifiedTasks}
                knowledgeNames={knowledgeNames}
                skillNames={skillNames}
              />
            </DutySection>
          )}
        </section>

        <section className="jd-section" aria-labelledby={headingId('competencies')}>
          <h2 id={headingId('competencies')} tabIndex={-1}>
            知識與技能
          </h2>
          <div className="jd-catalogs">
            <CompetencyCatalog
              title="知識 K"
              items={jobDescription.knowledge}
              emptyText="尚未填寫知識。"
            />
            <CompetencyCatalog
              title="技能 S"
              items={jobDescription.skills}
              emptyText="尚未填寫技能。"
            />
          </div>
        </section>

        <section className="jd-section" aria-labelledby={headingId('conditions')}>
          <h2 id={headingId('conditions')} tabIndex={-1}>
            協作與條件
          </h2>
          <div className="jd-condition-group">
            <h3>協作對象</h3>
            {jobDescription.collaborations.length === 0 ? (
              <p className="jd-empty">尚未填寫協作對象。</p>
            ) : (
              <dl className="jd-collaborations">
                {jobDescription.collaborations.map((collaboration) => (
                  <div key={collaboration.id}>
                    <dt>{collaboration.collaborator_name}</dt>
                    <dd className={collaboration.scope !== null ? '' : 'jd-empty'}>
                      {collaboration.scope !== null
                        ? collaboration.scope
                        : '尚未填寫協作範圍。'}
                    </dd>
                  </div>
                ))}
              </dl>
            )}
          </div>
          <div className="jd-condition-group">
            <h3>共通條件</h3>
            {jobDescription.conditions.length === 0 ? (
              <p className="jd-empty">尚未填寫共通條件。</p>
            ) : (
              <ol className="jd-conditions" aria-label="共通條件">
                {jobDescription.conditions.map((condition) => (
                  <li key={condition.id}>
                    <span className="jd-condition-kind">
                      {conditionLabels[condition.kind]}
                    </span>
                    <p>{condition.text}</p>
                  </li>
                ))}
              </ol>
            )}
          </div>
        </section>
      </article>
    </div>
  );
}

function DutySection({
  name,
  scope,
  children,
}: {
  name: string;
  scope?: string | null;
  children: ReactNode;
}) {
  const [expanded, setExpanded] = useState(true);
  const id = useId();
  const titleId = `${id}-title`;
  const tasksId = `${id}-tasks`;

  return (
    <div className="jd-duty">
      <h3>
        <button
          id={titleId}
          type="button"
          className="jd-duty-toggle"
          aria-expanded={expanded}
          aria-controls={tasksId}
          onClick={() => setExpanded(!expanded)}
        >
          <ChevronDown aria-hidden="true" size={18} />
          <span>{name}</span>
        </button>
      </h3>
      {scope !== undefined && (
        <p className={scope !== null ? 'jd-duty-scope' : 'jd-duty-scope jd-empty'}>
          {scope !== null ? scope : '尚未填寫職責範圍。'}
        </p>
      )}
      <div id={tasksId} role="region" aria-labelledby={titleId} hidden={!expanded}>
        {children}
      </div>
    </div>
  );
}

function CompetencyCatalog({
  title,
  items,
  emptyText,
}: {
  title: string;
  items: JobDescriptionResponse['knowledge'];
  emptyText: string;
}) {
  return (
    <div className="jd-catalog">
      <h3>{title}</h3>
      {items.length === 0 ? (
        <p className="jd-empty">{emptyText}</p>
      ) : (
        <ol className="jd-catalog-list">
          {items.map((item) => (
            <li key={item.id}>
              <h4>{item.name}</h4>
              <p className={item.description !== null ? '' : 'jd-empty'}>
                {item.description !== null ? item.description : '尚未填寫說明。'}
              </p>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
