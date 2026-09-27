let spec=null;
const $=s=>document.querySelector(s);
const toast=(m)=>{const t=$("#toast");t.textContent=m;t.classList.add("show");setTimeout(()=>t.classList.remove("show"),2800)}
function setSpec(data){
  spec=data.spec; const s=data.summary;
  $("#specStatus").textContent="READY"; $("#specStatus").style.color="var(--green)";
  $("#apiTitle").textContent=s.title; $("#apiVersion").textContent=s.version||"—"; $("#baseUrl").textContent=s.base_url||"—"; $("#specMeta").classList.remove("hidden");
  $("#opCount").textContent=s.operations.length;
  $("#opsList").innerHTML=s.operations.map(o=>`<div class="op"><span class="method">${o.method}</span><code>${o.path}</code><small>${o.operation_id}</small></div>`).join("");
  $("#runBtn").disabled=false; toast("OpenAPI contract loaded. Agent is ready.");
}
async function loadDemo(){
  try {
    const r=await fetch("/api/demo-spec");
    if(!r.ok) throw new Error("Demo API specification could not be loaded.");
    const loaded=await r.json();
    // Build the summary locally from the OpenAPI contract.
    const s=loaded; const base=s.servers?.[0]?.url||""; const ops=[];
  for(const [path,item] of Object.entries(s.paths||{})) for(const [method,o] of Object.entries(item)) if(["get","post","put","patch","delete"].includes(method)) ops.push({operation_id:o.operationId||method+path,method:method.toUpperCase(),path,summary:o.summary||"",tags:o.tags||[]});
    setSpec({spec:s,summary:{title:s.info?.title,version:s.info?.version,base_url:base,operations:ops}});
  } catch (e) {
    toast(e.message || "Could not load demo API.");
  }
}
async function loadURL(){
  const source=$("#specUrl").value.trim(); if(!source)return toast("Paste an OpenAPI URL first.");
  const r=await fetch("/api/spec",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(source)});
  const d=await r.json(); if(!r.ok)return toast(d.detail||"Could not load spec."); setSpec(d);
}
$("#demoBtn").onclick=loadDemo; $("#urlBtn").onclick=loadURL;
$("#specFile").onchange=async e=>{const f=e.target.files[0];if(!f)return;const fd=new FormData();fd.append("file",f);const r=await fetch("/api/spec/upload",{method:"POST",body:fd});const d=await r.json();if(!r.ok)return toast(d.detail||"Invalid spec");setSpec(d)};
document.querySelectorAll(".tab").forEach(b=>b.onclick=()=>{document.querySelectorAll(".tab").forEach(x=>x.classList.remove("active"));b.classList.add("active");["demo","url","file"].forEach(x=>$("#"+x+"Box").classList.toggle("hidden",x!==b.dataset.tab))});
document.querySelectorAll(".suggestions button").forEach(b=>b.onclick=()=>$("#goal").value=b.dataset.q);
$("#runBtn").onclick=run;
$("#goal").addEventListener("keydown",e=>{if((e.ctrlKey||e.metaKey)&&e.key==="Enter")run()});
async function run(){
 if(!spec)return toast("Load an OpenAPI contract first.");
 const goal=$("#goal").value.trim(); if(!goal)return toast("Give the agent a goal first.");
 $("#dashboard").classList.remove("hidden"); $("#trace").innerHTML='<div class="trace-item"><div class="trace-dot">AI</div><div class="trace-content"><small>LIVE</small><div>Agent is reading the contract and planning your workflow…</div></div></div>';
 $("#runBtn").disabled=true; $("#runBtn").innerHTML='<span class="play">◌</span> ORCHESTRATING…';
 const auth={type:$("#authType").value,token:$("#authToken").value};
 const r=await fetch("/api/agent/run?x=1",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({goal,auth,max_steps:Number($("#maxSteps").value),spec})});
 const d=await r.json(); $("#runBtn").disabled=false;$("#runBtn").innerHTML='<span class="play">▶</span> RUN AUTONOMOUS WORKFLOW <kbd>CTRL ↵</kbd>';
 if(!r.ok){toast(d.detail||"Agent failed");return}
 $("#duration").textContent=d.duration_ms+" ms";
 renderTrace(d.trace); $("#summary").textContent=d.summary; renderResults(d.results); loadAudit(); toast("Workflow completed.");
}
function renderTrace(items){
 $("#trace").innerHTML=items.map((x,i)=>{
   const label=x.type==="plan"?"PLAN":x.type==="api"?"TOOL CALL":x.type==="recovery"?"RECOVERY":"SYNTHESIS";
   return `<div class="trace-item"><div class="trace-dot">${i+1}</div><div class="trace-content"><small>${label}${x.status?` • HTTP ${x.status}`:""}</small><div>${x.message||x.url||"Response synthesized"}${x.attempts?` <span style="color:#657082">(${x.attempts} attempt${x.attempts>1?"s":""})</span>`:""}</div></div></div>`
 }).join("");
}
function renderResults(rs){
 $("#resultCards").innerHTML=rs.map(r=>`<div class="result-card"><div class="rc-head"><span>${r.method} ${r.path}</span><span>HTTP ${r.result.status}</span></div><div class="code-preview">${escapeHtml(JSON.stringify(r.result.data??r.result.error??{},null,2))}</div></div>`).join("");
}
function escapeHtml(s){return String(s).replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]))}
async function loadAudit(){const r=await fetch("/api/audit");const d=await r.json();$("#audit").innerHTML=d.items.length?d.items.map(x=>`<div class="audit-row"><b>${escapeHtml(x.goal)}</b><span>${x.timestamp} • ${x.duration_ms} ms • ${x.plan.mode.toUpperCase()}</span></div>`).join(""):'<div style="color:#656d7d;font-size:10px">No runs yet.</div>'}
$("#refreshAudit").onclick=loadAudit; loadAudit();
