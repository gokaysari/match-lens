import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { execFileSync } from 'node:child_process';
import { writeFileSync } from 'node:fs';
import { createServer } from 'node:http';

const results = [];
const record = (r) => { results.push(r); writeFileSync(new URL('results.json', import.meta.url), JSON.stringify(results, null, 2)); console.log(JSON.stringify({name:r.name,status:r.status,tools:r.tools?.length,error:r.error,elapsedMs:r.elapsedMs})); };
async function probe(name, transport, call) {
  const client = new Client({name:'football-mcp-smoke',version:'1.0.0'});
  const started = Date.now();
  const row = {name, checkedAt:new Date().toISOString()};
  try {
    await client.connect(transport, {timeout:30000});
    row.server = client.getServerVersion();
    const listing = await client.listTools({}, {timeout:30000});
    row.tools = listing.tools.map(t=>({name:t.name,inputSchema:t.inputSchema}));
    row.handshake = 'PASS';
    if (call) await call(client, listing.tools, row);
  } catch(e) { row.error=String(e.message).replace(/gh[o_pus]_[A-Za-z0-9_]+/g,'[REDACTED]'); row.status='FAIL_OR_UNAUTHORIZED'; }
  finally { await client.close().catch(()=>{}); row.elapsedMs=Date.now()-started; record(row); }
}
function summarize(result) {
  return {isError:result.isError??false, content:result.content?.filter(c=>c.type==='text').map(c=>c.text.slice(0,1600))};
}
await probe('Microsoft Learn', new StreamableHTTPClientTransport(new URL('https://learn.microsoft.com/api/mcp')), async(c, tools, r)=>{
  const tool=tools.find(t=>t.name==='microsoft_docs_search');
  if(!tool) throw Error('Expected microsoft_docs_search missing');
  const result=await c.callTool({name:tool.name,arguments:{query:'Microsoft Agent Framework MCP tools'}},undefined,{timeout:30000});
  r.sample=summarize(result); r.status=result.isError?'TOOL_ERROR':'PASS';
});
const fixture=createServer((req,res)=>{res.setHeader('Content-Type','text/html; charset=utf-8');res.end(`<!doctype html><title>Football MCP test fixture</title><h1>Synthetic replay</h1><button id="persona">Analyst</button><p id="story">Casual: Blue keeps the ball</p><details><summary>Evidence</summary><p>e1, e2 — snapshot s2</p></details><script>document.getElementById('persona').addEventListener('click',()=>{document.getElementById('story').textContent='Analyst: 2 completed passes, e1 e2';});</script>`);});
await new Promise(resolve=>fixture.listen(0,'127.0.0.1',resolve));
await probe('Playwright isolated headless',new StdioClientTransport({command:process.execPath,args:['node_modules/@playwright/mcp/cli.js','--headless','--isolated','--browser','chromium'],stderr:'pipe'}),async(c,tools,r)=>{
  r.navigation=summarize(await c.callTool({name:'browser_navigate',arguments:{url:`http://127.0.0.1:${fixture.address().port}`}},undefined,{timeout:45000}));
  r.personaClick=summarize(await c.callTool({name:'browser_click',arguments:{target:'button',element:'Analyst persona button'}},undefined,{timeout:15000}));
  r.evidenceClick=summarize(await c.callTool({name:'browser_click',arguments:{target:'summary',element:'Evidence drawer'}},undefined,{timeout:15000}));
  r.interaction=summarize(await c.callTool({name:'browser_evaluate',arguments:{function:'() => { const story=document.querySelector("#story").textContent; if(!story.includes("2 completed passes")) throw Error("Persona switch failed"); if(!document.querySelector("details").open) throw Error("Evidence drawer failed"); return {story,evidenceVisible:true}; }'}},undefined,{timeout:15000}));
  r.snapshot=summarize(await c.callTool({name:'browser_snapshot',arguments:{}},undefined,{timeout:15000}));
  r.status=r.navigation.isError||r.snapshot.isError||r.interaction.isError?'TOOL_ERROR':'PASS';
});
await new Promise(resolve=>fixture.close(resolve));
let token;
try { token=execFileSync('gh',['auth','token'],{encoding:'utf8',stdio:['ignore','pipe','ignore']}).trim(); } catch {}
if(token) await probe('GitHub remote (read only probe)',new StreamableHTTPClientTransport(new URL('https://api.githubcopilot.com/mcp/'),{requestInit:{headers:{Authorization:`Bearer ${token}`,'X-MCP-Readonly':'true'}}}),async(c,tools,r)=>{
  const tool=tools.find(t=>t.name==='get_file_contents');
  if(!tool) throw Error('Expected get_file_contents missing');
  const result=await c.callTool({name:tool.name,arguments:{owner:'microsoft',repo:'insidethegamehackathon',path:'OFFICIAL RULES.md'}},undefined,{timeout:30000});
  r.sample=summarize(result); r.status=result.isError?'TOOL_ERROR':'PASS';
});
else record({name:'GitHub remote',status:'SKIPPED_NO_CREDENTIAL'});
token=undefined;
await probe('Foundry remote (unauthenticated capability probe)',new StreamableHTTPClientTransport(new URL('https://mcp.ai.azure.com')),null);
await probe('Azure MCP 3.0.0 read-only stdio',new StdioClientTransport({command:'npx',args:['--yes','@azure/mcp@3.0.0','server','start','--read-only','--disable-proxy-tools','--mode','all'],stderr:'pipe'}),async(c,tools,r)=>{
  const tool=tools.find(t=>t.name==='get_azure_bestpractices_get');
  if(!tool) {r.status=tools.length?'DISCOVERY_PASS_NO_SAMPLE':'EMPTY_TOOLS';return;}
  const result=await c.callTool({name:tool.name,arguments:{resource:'general',action:'all'}},undefined,{timeout:30000});
  r.sample=summarize(result);r.status=result.isError?'TOOL_ERROR':'PASS';
});
await probe('Context7 unauthenticated',new StreamableHTTPClientTransport(new URL('https://mcp.context7.com/mcp')),async(c,tools,r)=>{
  const tool=tools.find(t=>t.name==='resolve-library-id');
  if(!tool)throw Error('Expected library resolver missing');
  const result=await c.callTool({name:tool.name,arguments:{libraryName:'react',query:'React useState documentation'}},undefined,{timeout:30000});
  r.sample=summarize(result);r.status=result.isError?'TOOL_ERROR':'PASS';
});
