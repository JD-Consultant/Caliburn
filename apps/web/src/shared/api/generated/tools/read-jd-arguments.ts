/* Generated from apps/api/contracts; do not edit. */

/**
 * 選取目前可見 JD 的一種 view；App 綁定本輪候選及來源比較基準。view 與 read_ref 必須按下列用途配對，讀取不修改 JD 或引用。
 */
export interface ReadJdArguments {
  /**
   * map：完整定位導覽；full：完整成品 Markdown；item：read_ref 所指單項及其直屬明細；profile：職稱、單位、匯報對象、目的及各自引用；responsibility_areas：全部職責自身；work_tasks：指定職責下全部任務；unassigned_work_tasks：全部未歸屬任務；required_knowledge／required_skills：全部知識／技能定義及反向任務用途；main_collaborators：全部協作對象；job_wide_conditions：全部共通條件。map 是預覽，full 不含任何定位或來源資訊；核對引用用局部 view。
   */
  view:
    | 'map'
    | 'full'
    | 'item'
    | 'profile'
    | 'responsibility_areas'
    | 'work_tasks'
    | 'unassigned_work_tasks'
    | 'required_knowledge'
    | 'required_skills'
    | 'main_collaborators'
    | 'job_wide_conditions';
  /**
   * view=item 時原樣填目前 JD 導覽、局部讀取或成功建立結果提供、改後仍有效的項目 read_ref；view=work_tasks 時填所選職責的 read_ref；所有其他 view 必須填 null。不是名稱、章節序號、citation_ref、內部 UUID、版本或寫入授權；不自行組合，也不使用人工差異中已刪項目的歷史定位。
   */
  read_ref: string | null;
}
