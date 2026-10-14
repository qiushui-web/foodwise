import { test, expect } from '@playwright/test';
import { createPinia, setActivePinia } from 'pinia';
import { createWriteIntent } from '../src/api/write-intent';

test('write intent reuses retries and changes keys for a new intent',()=>{
  const intent=createWriteIntent();
  const first=intent.key({dishId:1,qty:10});
  expect(intent.key({dishId:1,qty:10})).toBe(first);
  expect(intent.key({dishId:1,qty:11})).not.toBe(first);
  const second=intent.key({dishId:1,qty:11});intent.complete();
  expect(intent.key({dishId:1,qty:11})).not.toBe(second);
});

test('client preserves pagination and clears timeout after abort or errors',async ()=>{
  const originalFetch=globalThis.fetch;
  const originalDocument=globalThis.document;
  const originalWindow=globalThis.window;
  const timers=new Set<ReturnType<typeof setTimeout>>();
  Object.assign(globalThis,{
    document:{querySelector:()=>({content:'/foodwise/'})},
    window:{setTimeout:(fn:()=>void,ms:number)=>{const id=setTimeout(fn,ms);timers.add(id);return id;},clearTimeout:(id:ReturnType<typeof setTimeout>)=>{timers.delete(id);clearTimeout(id);},location:{assign:()=>{}}},
  });
  setActivePinia(createPinia());
  try {
    const {getPage,getApi}=await import('../src/utils/vue-api');
    globalThis.fetch=async ()=>new Response(JSON.stringify({success:true,data:{items:[{id:1}],page:2,size:1,total:3,totalPages:3}}),{headers:{'content-type':'application/json'}});
    const page=await getPage<{id:number}>('/dishes');expect(page.page).toBe(2);expect(page.total).toBe(3);expect(timers.size).toBe(0);
    globalThis.fetch=async (_input,init)=>new Promise((_resolve,reject)=>{
      init?.signal?.addEventListener('abort',()=>reject(new DOMException('aborted','AbortError')),{once:true});
    });
    await expect(getApi('/slow',{timeoutMs:20})).rejects.toThrow('请求超时');expect(timers.size).toBe(0);
    globalThis.fetch=async ()=>{throw new Error('offline');};
    await expect(getApi('/offline')).rejects.toThrow('网络连接失败');expect(timers.size).toBe(0);
  } finally {
    globalThis.fetch=originalFetch;
    Object.assign(globalThis,{document:originalDocument,window:originalWindow});
    for(const timer of timers)clearTimeout(timer);
  }
});
