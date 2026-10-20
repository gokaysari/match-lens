import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
const client=new Client({name:'football-tests',version:'1.0.0'});
const transport=new StdioClientTransport({command:process.execPath,args:['football-server.mjs'],stderr:'pipe'});
const scope={match_id:'synthetic-01',snapshot_id:'s2'};
const call=(name,args)=>client.callTool({name,arguments:args},undefined,{timeout:2000});
const parse=r=>JSON.parse(r.content[0].text);
await client.connect(transport);
try {
  await test('exactly four read-only tools; no write or reset tool',async()=>{
    const {tools}=await client.listTools(); assert.equal(tools.length,4); assert.ok(tools.every(t=>t.annotations.readOnlyHint));
    const r=await call('reset_match',{}); assert.equal(r.isError,true);
  });
  await test('snapshot and deterministic metric preserve evidence IDs',async()=>{
    const s=parse(await call('get_match_snapshot',{match_id:'synthetic-01',as_of_event_id:'e2'}));assert.equal(s.snapshot_seq,2);assert.equal(s.snapshot_id,'s2');
    const [m]=parse(await call('get_window_metrics',{...scope,end_seq:2,window_seconds:20,metric_names:['completed_passes']})).metrics;
    assert.equal(m.metric,'completed_passes');assert.equal(m.value,2);assert.deepEqual(m.event_ids,['e1','e2']);
  });
  await test('every requested metric is computed separately',async()=>{
    const {metrics}=parse(await call('get_window_metrics',{match_id:'synthetic-01',snapshot_id:'s3',end_seq:3,window_seconds:30,metric_names:['completed_passes','shots']}));
    assert.deepEqual(metrics.map(m=>[m.metric,m.value,m.event_ids]),[['completed_passes',2,['e1','e2']],['shots',1,['e3']]]);
  });
  await test('unknown evidence is an explicit error naming the IDs',async()=>{
    const r=await call('get_evidence',{...scope,event_ids:['e1','invented']});assert.equal(r.isError,true);assert.equal(r.content[0].text,'UNKNOWN_EVIDENCE: invented');
  });
  await test('future event evidence is rejected',async()=>{const r=await call('get_evidence',{...scope,event_ids:['e3']});assert.equal(r.isError,true);assert.match(r.content[0].text,/FUTURE_EVENT_FORBIDDEN: e3/);});
  await test('the access limit follows the snapshot watermark, not a constant',async()=>{
    const later={match_id:'synthetic-01',snapshot_id:'s3'};
    assert.equal(parse(await call('get_evidence',{...later,event_ids:['e3']})).events[0].id,'e3');
    assert.equal(parse(await call('get_events',{...later,start_seq:1,end_seq:3,limit:10})).events.length,3);
    assert.match((await call('get_window_metrics',{...scope,end_seq:3,window_seconds:30,metric_names:['shots']})).content[0].text,/FUTURE/);
    assert.equal((await call('get_match_snapshot',{match_id:'synthetic-01',as_of_event_id:'e1'})).isError,true);
  });
  await test('future range and wrong match/snapshot are rejected',async()=>{
    for(const [args,code] of [[{...scope,start_seq:1,end_seq:3,limit:10},'FUTURE_EVENT_FORBIDDEN'],[{...scope,match_id:'other',start_seq:1,end_seq:2,limit:10},'UNKNOWN_MATCH'],[{...scope,snapshot_id:'s9',start_seq:1,end_seq:2,limit:10},'UNKNOWN_SNAPSHOT']]){
      const r=await call('get_events',args);assert.equal(r.isError,true);assert.equal(r.content[0].text,code);
    }
  });
  await test('truncation, range and metric allowlist are explicit',async()=>{
    assert.equal(parse(await call('get_events',{...scope,start_seq:1,end_seq:2,limit:1})).truncated,true);
    assert.equal((await call('get_events',{...scope,start_seq:2,end_seq:1,limit:10})).isError,true);
    assert.equal((await call('get_window_metrics',{...scope,end_seq:2,window_seconds:20,metric_names:['invented_xg']})).isError,true);
  });
  await test('untrusted event text stays text; snapshot does not mutate',async()=>{
    const before=await call('get_match_snapshot',{match_id:'synthetic-01',as_of_event_id:'e2'});
    const e=parse(await call('get_evidence',{...scope,event_ids:['e2']}));assert.match(e.events[0].player_name,/IGNORE PREVIOUS/);
    assert.deepEqual(await call('get_match_snapshot',{match_id:'synthetic-01',as_of_event_id:'e2'}),before);
  });
  await test('slow MCP request times out and chooses a safe fallback',async()=>{
    const slow=new Client({name:'timeout-test',version:'1'});
    await slow.connect(new StdioClientTransport({command:process.execPath,args:['football-server.mjs'],env:{...process.env,FOOTBALL_TEST_DELAY_MS:'500'},stderr:'pipe'}));
    try {
      const started=Date.now();let output;
      try {await slow.callTool({name:'get_evidence',arguments:{...scope,event_ids:['e1']}},undefined,{timeout:100});output='unreviewed';}
      catch(e) {assert.match(e.message,/timed out/i);output={kind:'fallback',text:'Analysis temporarily unavailable',claims:[]};}
      assert.equal(output.kind,'fallback');assert.deepEqual(output.claims,[]);assert.ok(Date.now()-started<1500);
    } finally {await slow.close();}
  });
  await test('crashed MCP server process is detected by the client',async()=>{
    const victim=new Client({name:'crash-test',version:'1'});
    const victimTransport=new StdioClientTransport({command:process.execPath,args:['football-server.mjs'],stderr:'pipe'});
    await victim.connect(victimTransport);
    try {
      const closed=new Promise(resolve=>{victim.onclose=resolve;});
      process.kill(victimTransport.pid,'SIGKILL');
      await closed;
      let fallback=false;try{await victim.callTool({name:'get_evidence',arguments:{...scope,event_ids:['e1']}},undefined,{timeout:1000});}catch{fallback=true;}
      assert.equal(fallback,true);
    } finally {await victim.close().catch(()=>{});}
  });
} finally {await client.close().catch(()=>{});}
