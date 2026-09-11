import React from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen, fireEvent } from '@testing-library/react';
const state=vi.hoisted(()=>({session:null as unknown}));
vi.mock('./useJdSession',()=>({useJdSession:()=>state.session}));
vi.mock('./JdEditor',()=>({JdEditor:()=> <div>保留的工作稿</div>,applySavedHead:vi.fn()}));
vi.mock('./JdChanges',()=>({JdChanges:()=>null}));
vi.mock('./JdNode',()=>({ReadOnlyValue:()=>null}));
import { JdWorkspace } from './JdWorkspace';
afterEach(cleanup);
it('R03 no-run owner failure shows restart steps and keeps draft on state refresh',()=>{
  const revalidate=vi.fn();
  state.session={document:'A',head:{revision_ref:'r1'},value:[],metadata:{title:'我的工作'},
    dirty:true,text:'還沒送出的補充',run:null,messages:[],candidate:null,
    recovery:{status:'no_pending',request_key:null,write_blocked:true,can_recover:false,restart_required:true},
    restartRequired:true,locked:true,bindHead:vi.fn(),revalidate};
  render(<JdWorkspace document="A"/>);
  expect(screen.getByRole('status').textContent).toContain('需要重新啟動');
  expect(screen.getByText(/先保留此頁/)).toBeTruthy();
  expect(screen.getByText(/停止.*重新啟動/)).toBeTruthy();
  expect(screen.getByText('保留的工作稿')).toBeTruthy();
  fireEvent.click(screen.getByRole('button',{name:'重新讀取狀態'}));
  expect(revalidate).toHaveBeenCalledOnce();
  expect(screen.queryByText('停止顧問')).toBeNull();
});
