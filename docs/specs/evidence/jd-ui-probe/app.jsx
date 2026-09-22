import React, { useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { nativeDiff, nativeOperations, printable, ReadOnlyDocument, updateText } from './render.jsx';

const prettyNative = value => JSON.stringify(value, (_key, item) => item === undefined ? '⟪原生 JavaScript undefined⟫' : item, 2);
function Comparison({ entry }) {
  const diff = useMemo(() => nativeDiff(entry.before, entry.after), [entry]);
  const updates = nativeOperations(diff);
  return <section id={entry.id} className="comparison">
    <h2>{entry.title}</h2><p>{entry.note}</p>
    {entry.id !== 'full-r2' && <p className="warning">已知原生缺口：以下比較未修補。前後快照與當時捕捉的操作才是這個反例的完整觀測材料。</p>}
    <div className="three-columns">
      <article><h3>前版 <small>保存的乾淨快照</small></h3><ReadOnlyDocument value={entry.before} name={`${entry.id}-before`} /></article>
      <article><h3>後版 <small>保存的乾淨快照</small></h3><ReadOnlyDocument value={entry.after} name={`${entry.id}-after`} /></article>
      <article><h3>原生比較 <small>每次重開重新計算</small></h3><ReadOnlyDocument value={diff} name={`${entry.id}-diff`} /></article>
    </div>
    <section className="metadata"><h3>原生比較確實輸出的屬性變更</h3>
      <p>這裡只讀取 computeDiff 的 diffOperation。0、false、物件與 undefined 如實呈現；不從快照補算缺少的差異。</p>
      {updates.filter(x => x.operation.type === 'update').length ? updates.filter(x => x.operation.type === 'update').map((row, i) => <div key={i} className="property-row"><strong>{row.id ?? row.type} · 路徑 [{row.path.join(', ')}]</strong><pre>{updateText(row.operation)}</pre></div>) : <p>本例沒有原生 update operation。</p>}
    </section>
    <details open={entry.id !== 'full-r2'}><summary>實際保存的前後與操作材料（研究資訊）</summary>
      <p>原生操作是本次修改時同步捕捉並保存的批次。它們沒有被重播或轉換成高亮，也不是跨任意歷史快照的通用比較。</p>
      <div className="raw-grid"><div><h4>前版 JSON</h4><pre>{printable(entry.before)}</pre></div><div><h4>後版 JSON</h4><pre>{printable(entry.after)}</pre></div></div>
      <h4>確實捕捉的 editor.operations</h4><pre>{printable(entry.batches.map(b => b.operations))}</pre>
    </details>
    <details><summary>原樣原生比較值（undefined 以明示文字顯示，沒有重新寫入文件）</summary><pre>{prettyNative(diff)}</pre></details>
  </section>;
}
function App({ materials }) {
  const [tab, setTab] = useState('full');
  return <main>
    <header><p className="eyebrow">有限呈現驗證 · 2026-09-09 · 免費 OSS 固定版本</p><h1>同一份 JD，前後改了什麼</h1>
      <p>真正 React Plate 唯讀文件。這是完整 r2 與固定研究改動；不是正式產品、審閱流程或全面 diff 通過證明。</p>
      <div className="legend"><span className="diff-insert">新增</span><span className="diff-delete">移除</span><span className="diff-update">原生屬性更新</span><span>比較中的同 ID 刪＋增保留兩份內容</span></div>
      <nav><button aria-pressed={tab === 'full'} onClick={() => setTab('full')}>完整 r2 比較</button><button aria-pressed={tab === 'limits'} onClick={() => setTab('limits')}>兩個已知反例</button><button onClick={() => window.location.reload()}>清除頁面並從保存材料重開</button></nav>
      <p className="status" data-load-status="saved-materials-loaded">已從檔案重新載入乾淨快照與操作材料。Plate {materials.versions.platejs} · diff {materials.versions.diff} · React {materials.versions.react}。本頁沒有 localStorage／編輯／保存 diff。</p>
    </header>
    {materials.cases.filter(entry => tab === 'full' ? entry.id === 'full-r2' : entry.id !== 'full-r2').map(entry => <Comparison key={entry.id} entry={entry} />)}
    <footer>本次文件來源 SHA-256：<code>{materials.source.sha256}</code><br />Node／SSR 結果與瀏覽器驗收分開記錄。正文完整性不代表原生差異能表示任意屬性；兩個已知反例仍存在。</footer>
  </main>;
}
fetch('/materials.json', { cache: 'no-store' }).then(response => { if (!response.ok) throw new Error(`材料讀取失敗 ${response.status}`); return response.json(); }).then(materials => createRoot(document.getElementById('root')).render(<App materials={materials} />)).catch(error => { document.getElementById('root').textContent = error.stack; });
