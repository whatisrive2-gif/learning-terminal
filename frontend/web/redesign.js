'use strict';
let workspace={agents:[],projects:[],profiles:[],channels:[],submissions:[],messages:[],defaults:{}}, grouping='date', roundConfig={name:'本轮配置',goal:'',tone:'耐心、直接',length:'默认',depth:'正常首轮',instructions:'',suggestions:false,workflow_summary:false};
const originalRender=render, originalRow=row, originalRefresh=refresh, originalTools=renderTools;
const dayKey=x=>new Date(x).toLocaleDateString('sv-SE',{timeZone:'Asia/Shanghai'});
function groupBy(items,key){return items.reduce((a,x)=>{const k=key(x);(a[k]??=[]).push(x);return a},{})}
function subject(s){const text=s.title+' '+s.goal;if(text.includes('普天实习'))return '普天实习';if(text.includes('普天')||text.includes('普通天文学'))return '普通天文学';return ['概率论','理论力学','电磁学','天文学','数学','CS107','Git'].find(x=>text.includes(x))||'其他学习'}
function groups(items,key,card){return Object.entries(groupBy(items,key)).map(([k,rows])=>`<details class="subject-group"><summary>${esc(k)} <small>${rows.length} 项</small></summary><div class="session-grid">${rows.map(card).join('')}</div></details>`).join('')}
row=function(t){return `<div class="quick-row">${originalRow(t)}${t.executor==='manual'&&['draft','paused'].includes(t.state)?`<button class="quick-action" data-quick="complete" data-id="${t.id}" aria-label="完成 ${esc(t.title)}">✓</button>`:''}</div>`};
function renderReminder(){
 const pending=state.tasks.filter(t=>!['done','cancelled','deleted'].includes(t.state));
 const inProgress=pending.find(t=>['running','waiting_tool'].includes(t.state));
 const reminder=inProgress||pending.slice().sort((a,b)=>(a.due||'9999').localeCompare(b.due||'9999')||(a.priority==='high'?-1:0)-(b.priority==='high'?-1:0))[0];
 $('side-reminder').innerHTML=reminder?`<button class="reminder-link" data-task="${esc(reminder.id)}" title="${esc(reminder.title)}">${inProgress?'进行中':'待办'} · ${esc(reminder.title)}</button>`:'<p class="reminder-empty">暂无待办，今天从容开始。</p>';

}
render=function(){
 originalRender();document.body.dataset.view=currentView;$('new-task').hidden=currentView!=='tasks';
 renderReminder();
 if(currentView==='home'){
  $('page-title').textContent='LEARNING TERMINAL';$('page-description').textContent='学习、行动与协作，从这里开始。';
  const entries=[['tasks','01','任务待办','记录今天，推进下一步','☷'],['learning','02','近期学习','按学科继续，在 Taber 阅读','▤'],['tools','03','工具部署','监听、下载与提交','⌘'],['dispatch','04','Agent 交互中心','组织协作，交接任务与背景','⇄']];
  $('page').innerHTML=`<div class="start-layout"><section class="daily-note"><p class="figure-tag">FIELD NOTES / TODAY</p><h2>${dayKey(Date.now())}</h2><p class="intro-copy">从一个明确的目标出发。把学习材料、待办和协作放在同一个工作空间。</p><dl><dt>待推进</dt><dd>${state.tasks.filter(t=>!['done','cancelled'].includes(t.state)).length}</dd><dt>今日完成</dt><dd>${state.tasks.filter(t=>t.state==='done'&&dayKey(t.updated)===dayKey(Date.now())).length}</dd><dt>执行中</dt><dd>${state.tasks.filter(t=>['running','waiting_tool'].includes(t.state)).length}</dd><dt>学习记录</dt><dd>${learning.length}</dd></dl><p class="hint">本机工具不消耗模型额度。Agent 的外部用量以各平台为准。</p></section><div class="entry-grid">${entries.map(([view,n,title,note,icon])=>`<button class="entry" data-view="${view}"><span class="figure-tag">FIG_${n} / OPEN</span><span class="entry-art" aria-hidden="true">${icon}</span><strong>${title} <span>↗</span></strong><small>${note}</small></button>`).join('')}</div></div>`;
 }
 if(currentView==='tasks'){$('page-title').textContent='任务待办';$('page-description').textContent='按日期归档，按状态推进。';

  $('filter').insertAdjacentHTML('afterend',`<select id="grouping" aria-label="任务分组"><option value="date">按日期分组</option><option value="state">按状态分组</option></select>`);$('grouping').value=grouping;renderTasks();
 }
 if(currentView==='learning')$('page').innerHTML=`<div class="section-actions"><span>学科分组 · ${learning.length} 个会话</span><button data-publish class="primary">布置学习任务</button></div>${learning.length?learningPanels():empty('暂无学习记录','点击刷新重新读取。')}`;
 if(currentView==='dispatch')renderAgents();
 restorePanelScroll();
};
function taskTile(t){return `<article class="task-tile"><button class="tile-open" data-task="${esc(t.id)}" title="${esc(t.title)}"><strong>${esc(t.title)}</strong><span>${esc(t.category||'一般')} · ${esc(executors[t.executor])}${t.due?' · 截止 '+esc(t.due):''}</span></button><div class="task-row-actions">${badge(t)}${t.executor==='manual'&&['draft','paused'].includes(t.state)?`<button class="tile-action" data-quick="complete" data-id="${t.id}" aria-label="完成 ${esc(t.title)}">✓</button>`:''}</div></article>`}
const panelScroll={};
function restorePanelScroll(){document.querySelectorAll('[data-scroll-key]').forEach(el=>el.scrollTop=panelScroll[el.dataset.scrollKey]||0)}
document.addEventListener('scroll',e=>{if(e.target.dataset?.scrollKey)panelScroll[e.target.dataset.scrollKey]=e.target.scrollTop},true);
function learningPanels(){return `<div class="learning-panel-grid">${Object.entries(groupBy(learning,subject)).map(([name,items],i)=>`<section class="learning-folder" data-subject="${esc(name)}"><div class="panel-heading"><span class="folder-index">${String(i+1).padStart(2,'0')}</span><span class="folder-title"><strong>${esc(name)}</strong><small>${items.length} 个学习会话</small></span></div><div class="learning-panel-list" data-scroll-key="learning:${esc(name)}" tabindex="0" aria-label="${esc(name)}学习记录">${items.map(s=>`<article class="learning-item"><div><h3>${esc(s.title)}</h3><p>${date(s.updated)} · ${s.content_length?'讲解版本 '+s.revision:'尚无讲解'}</p></div><button class="secondary" data-open-session="${esc(s.id)}" ${!s.content_length?'disabled':''}>阅读 ↗</button></article>`).join('')}</div></section>`).join('')}</div>`}

renderTasks=function(){
 const tasks=state.tasks.filter(t=>(filter==='all'||(filter==='active'?!['done','cancelled'].includes(t.state):t.state===filter))&&`${t.title} ${t.notes} ${t.category}`.toLowerCase().includes(search.toLowerCase()));
 const entries=Object.entries(groupBy(tasks,t=>grouping==='state'?labels[t.state]:(t.due||dayKey(t.created)))).sort(([a],[b])=>b.localeCompare(a));
 $('task-list').innerHTML=entries.length?`<div class="board-controls"><span>${entries.length} 个分组 · ${tasks.length} 项任务</span></div><div class="task-fold-grid">${entries.map(([k,ts],i)=>{const key=grouping+':'+k;return `<section class="task-folder"><div class="panel-heading"><span class="folder-index">${String(i+1).padStart(2,'0')}</span><span class="folder-title"><strong>${esc(k)}</strong><small>${ts.length} 项任务 · ${ts.filter(t=>t.state==='done').length} 项完成</small></span></div><div class="task-tile-grid" data-scroll-key="task:${esc(key)}" tabindex="0" aria-label="${esc(k)}任务列表">${ts.map(taskTile).join('')}</div></section>`}).join('')}</div>`:empty('没有匹配的任务','点击新建任务，只写标题即可保存。');restorePanelScroll();
};

refresh=async function(full=false){try{workspace=await api('workspace')}catch(e){toast(e.message)}await originalRefresh(full||currentView==='learning');renderReminder()};
function options(items,value=''){return '<option value="">请选择</option>'+items.map(a=>`<option value="${esc(a.id)}" ${a.id===value?'selected':''}>${esc(a.name)}</option>`).join('')}
function field(name,title,value='',type='text'){return `<label>${title}<input name="${name}" type="${type}" value="${esc(value)}"></label>`}
function area(name,title,value=''){return `<label>${title}<textarea name="${name}" rows="3" maxlength="12000">${esc(value)}</textarea></label>`}
function select(name,title,values,value){return `<label>${title}<select name="${name}">${values.map(v=>`<option ${v===value?'selected':''}>${esc(v)}</option>`).join('')}</select></label>`}
function pick(name,title,items,value=''){return `<label>${title}<select name="${name}">${options(items,value)}</select></label>`}
function openPanel(title,fields,save){$('compose-title').textContent=title;$('compose-form').querySelector('[type=submit]').textContent='保存';$('compose-fields').innerHTML=fields;$('compose-error').textContent='';$('compose-form').onsubmit=async e=>{e.preventDefault();const b=e.submitter;b.disabled=true;try{await save(Object.fromEntries(new FormData(e.target)));await refresh();$('compose').close();render();}catch(err){$('compose-error').textContent=err.message}finally{b.disabled=false}};$('compose').showModal()}
const learningDepthRules={
 '正常首轮':'提供可独立阅读的完整课程讲解，先说明课程问题和旧知识衔接，再展开概念、推导、典型例子、适用条件与边界。用户卡点在对应位置加深，不替代课程主线。',
 '从零补课':'从必要前置知识开始，首次出现的符号就地解释。关键例题说明模型选择、方程来源、方向、积分限、边界条件和结果检查。按可暂停的段落推进。',
 '简短回顾':'用紧凑的概念路线回顾主要联系、适用条件和易错点。只展开用户指出的卡点，明确省略的推导；不将简短回顾记为完整首轮覆盖。',
 '主动练习':'先给知识路线与短自测，等待用户作答后再针对卡点展开。作业分层提示，按用户明确要求提供完整解答；分别记录做完与掌握。'
};
const learningLengthRules={'默认':'按任务复杂度安排篇幅，不凑字数，也不省略必要的推理与条件。','较长':'充分展开关键推理、公式来源与代表性例子，分段便于暂停；避免同义重复。','较短':'减少重复铺陈与非必要例子，保留当前模式要求的主线、关键步骤与结论条件。'};
function detailedInstructions(c){return `角色与表达：${c.tone||'耐心、直接'}。使用中文，先说明要解决的问题，再给理由和步骤；避免空泛鼓励和未定义的符号。\n\n解释深度：${learningDepthRules[c.depth]||c.depth}\n\n篇幅要求：${learningLengthRules[c.length]||learningLengthRules['默认']}\n\n材料与证据：以用户指定的笔记和课件为主体，教材按需核查。回应笔记中的疑问和标注；区分明确错误、可能问题与需补条件。未核对的内容明确说明，不把阅读、工具执行或作业做完等同于掌握。\n\n交付要求：已有学习会话沿用原记录，完整讲解默认交付 Taber；用户要求仅对话时遵从。作业按实际进度分层提示。收尾建议和工作流总结分别遵从本轮开关。`}
const builtInProfiles=Object.keys(learningDepthRules).map((depth,i)=>{const c={name:['默认学习','从零补课','简短回顾','主动练习'][i],goal:'',tone:'耐心、直接',length:'默认',depth,suggestions:false,workflow_summary:false};return {...c,id:'builtin-'+i,instructions:detailedInstructions(c)}});
roundConfig={...builtInProfiles[0]};delete roundConfig.id;
function configure(){publish()}
function publish(projectId='',agentId=''){
 const c=roundConfig, templates=[...builtInProfiles,...workspace.profiles];
 openPanel('布置学习任务',field('title','任务标题')+area('notes','任务内容与材料')+`<div class="learning-config-block"><h3>本轮学习配置</h3>`+pick('template','模板',templates,'builtin-0')+area('goal','本轮学习目标（可选）',c.goal)+field('tone','语气与角色',c.tone)+`<div class="form-grid">`+select('length','回答长度',['默认','较长','较短'],c.length)+select('depth','解释深度',Object.keys(learningDepthRules),c.depth)+`</div><details class="prompt-editor"><summary>展开并编辑详细提示词</summary><p class="hint">以下要求会原样写入任务配置。你编辑的文字不会因调整上方选项而被覆盖；需要时可重新生成。</p>`+area('instructions','详细要求',c.instructions)+`<button type="button" class="secondary" data-rebuild-prompt>根据当前选项重新生成</button><p class="hint" id="prompt-status" role="status"></p></details><div class="config-switches"><label class="check"><input type="checkbox" name="suggestions" ${c.suggestions?'checked':''}>提出改进建议</label><label class="check"><input type="checkbox" name="workflow_summary" ${c.workflow_summary?'checked':''}>总结工作流</label></div><details class="learning-more"><summary>保存模板与分配选项</summary>`+field('name','模板名称',c.name)+`<label class="check"><input type="checkbox" name="save_template">将这份配置另存为模板</label>`+pick('agent_id','接收 Agent（留空：当前 GPT 对话）',workspace.agents,agentId)+pick('project_id','协作项目（可选）',workspace.projects,projectId)+`</details></div><p class="hint">前端不调用模型。保存为待安排任务，再由当前对话或已连接 Agent 执行；已发布任务保留本轮配置快照。</p>`,async d=>{
 const config=Object.fromEntries(['name','goal','tone','length','depth','instructions'].map(k=>[k,d[k]]));config.suggestions=!!d.suggestions;config.workflow_summary=!!d.workflow_summary;
 // Save a requested template first, so a template error cannot silently create a duplicate task on retry.
 if(d.save_template)await api('workspace/profiles',config);
 await api('tasks',{...Object.fromEntries(coopKeys.map(k=>[k,d[k]])),title:d.title,notes:d.notes,category:'学习',agent_id:d.agent_id,project_id:d.project_id,executor:'agent-handoff',agent:d.agent_id?'':'当前 GPT 对话',config});roundConfig={...config};toast('学习任务已记录，尚未派发');
 });
 const f=$('compose-form');f.elements.title.required=true;f.elements.instructions.rows=10;
 f.elements.template.value=templates.find(p=>p.name===c.name&&p.instructions===c.instructions)?.id||'';
 let generated=detailedInstructions(c);
 const current=()=>Object.fromEntries(['tone','length','depth'].map(k=>[k,f.elements.namedItem(k).value]));
 const regenerate=()=>{generated=detailedInstructions(current());f.elements.instructions.value=generated;$('prompt-status').textContent='已根据当前选项生成详细要求。'};
 $('compose-fields').querySelector('[data-rebuild-prompt]').onclick=()=>{if(f.elements.instructions.value!==generated&&!confirm('重新生成会替换你编辑的详细要求，继续吗？'))return;regenerate()};
 for(const key of ['tone','length','depth'])f.elements.namedItem(key).onchange=()=>{if(f.elements.instructions.value===generated)regenerate();else $('prompt-status').textContent='已保留你的详细要求；请核对它与更新后的选项是否一致。'};
 f.elements.template.onchange=e=>{const p=templates.find(x=>x.id===e.target.value);if(!p)return;for(const k of ['name','goal','tone','length','depth','instructions'])f.elements.namedItem(k).value=p[k]||'';for(const k of ['suggestions','workflow_summary'])f.elements.namedItem(k).checked=!!p[k];generated=detailedInstructions(p);$('prompt-status').textContent='已加载模板，可继续修改。'};
}
function newToolTask(){
 openPanel('新增工具任务',`<label>任务种类<select name="kind"><option value="website">监听网站</option><option value="taber">Taber 阅读</option></select></label><div id="tool-task-fields"></div>`,async d=>{
 if(d.kind==='website'){
  if(!toolCatalog?.online)throw Error('工具服务离线，请连接后重试');
  await api('tool-actions',{requestId:crypto.randomUUID(),tool_id:'homework-crawler',tool_action:'run',tool_input:{dryRun:!!d.dryRun}});toolWorkspace='monitor';monitorSelection=true;monitorTab='download';selectedTool='homework-crawler';toast('监听任务已排队，周期设置可在工作区调整');
 }else{if(!d.session)throw Error('请选择已有讲解');await api('tasks',{title:d.title,executor:'taber',session:d.session,category:'学习'});toolWorkspace='taber';toast('Taber 任务已记录，可在任务详情派发')}
 });
 const f=$('compose-form');const update=()=>{$('tool-task-fields').innerHTML=f.elements.kind.value==='website'?`<label>网站适配器<select name="adapter"><option>概率论作业网站</option></select></label><p class="hint">当前已接通概率论作业网站；其他网站需新增适配器。创建后执行一次检查，自动下载新材料；长期运行在工作区启用周期。</p><label class="check"><input type="checkbox" name="dryRun">仅试运行，不下载、不投递</label>`:field('title','任务名称','在 Taber 继续阅读')+pick('session','学习会话',learning.filter(s=>s.content_length).map(s=>({id:s.id,name:s.title})));f.querySelector('[type=submit]').textContent=f.elements.kind.value==='website'?'创建并执行':'保存任务'};f.elements.kind.onchange=update;update();
}
function renderAgents(){
 $('page').innerHTML=`<div class="section-actions"><button class="primary" data-create="agents">注册 Agent</button><button class="secondary" data-create="projects">新建协作</button><button class="secondary" data-publish>分配任务</button><button class="secondary" data-create="messages">发送站内消息</button><button class="secondary" data-loader>复制装载说明</button></div><p class="hint">装载 agent-client.py 后注册、轮询领取、回传结果。额度可登记用于分工参考；不会声称已自动查询或兑换各平台额度。</p><div class="tool-grid">${workspace.agents.map(a=>`<article class="tool-card"><span class="figure-tag">${a.parent?'CHILD / '+esc(workspace.agents.find(x=>x.id===a.parent)?.name||a.parent):'AGENT / ROOT'}</span><h3>${esc(a.name)}</h3><p>${esc(a.role||'尚未填写职责')}</p><p class="hint">${esc(a.provider)} · ${a.transport==='polling'?'轮询接口已注册':'人工交接'}<br>最近联系 ${date(a.last_seen)}<br>额度说明：${esc(a.quota||'未知')}</p><button data-assign="${a.id}">分配任务 ↗</button><button data-edit-record="agents" data-id="${a.id}">编辑资料</button></article>`).join('')||empty('注册你的第一个 Agent','可从此处记录，或通过装载接口自动注册。')}</div><h2>协作空间</h2>${workspace.projects.map(p=>`<section class="panel"><div class="panel-head"><h3>${esc(p.name)} · ${esc(p.mode)}</h3><button data-project="${p.id}">分配任务</button></div><div class="panel-body"><p>主 Agent：${esc(workspace.agents.find(a=>a.id===p.lead)?.name)}</p><p>${esc(p.goal)}</p><p class="hint">${esc(p.background)}</p>${state.tasks.filter(t=>t.project_id===p.id).map(row).join('')||'尚无分工任务'}</div></section>`).join('')}<h2>消息与讨论</h2>${workspace.messages.slice(-20).reverse().map(m=>`<article class="panel panel-body"><h3>${esc(m.name)}</h3><p class="meta">${esc(workspace.agents.find(a=>a.id===m.sender)?.name||'用户')} → ${esc(workspace.agents.find(a=>a.id===m.recipient)?.name)} · ${date(m.updated)}</p><p class="detail-text">${esc(m.body)}</p></article>`).join('')}<h2>执行与交接队列</h2>${state.tasks.filter(t=>t.executor==='agent-handoff').map(row).join('')}`;
}
function recordForm(kind,old=null){if(kind==='channels'){channelForm(old);return}const a=old||{};let fields='';
 if(kind==='agents')fields=field('name','唯一名称（例如 主 Agent / 研究-01）',a.name)+field('provider','来源 / 模型',a.provider)+field('role','明确职责',a.role)+pick('parent','父 Agent（可选）',workspace.agents.filter(x=>x.id!==a.id),a.parent)+field('quota','额度说明（手工登记）',a.quota)+area('background','背景要求',a.background);
 if(kind==='projects')fields=field('name','项目 / 主题名称')+select('mode','协作方式',['项目','讨论','自定义'],'项目')+pick('lead','主 Agent（负责整体调配）',workspace.agents)+area('goal','共同目标')+area('background','共享背景与边界');
 if(kind==='submissions')fields=field('name','作业名称')+field('path','完成文件的位置（粘贴文件完整路径）')+pick('destination','交到哪里',workspace.channels)+area('notes','提交说明');
 if(kind==='messages')fields=field('name','主题')+pick('recipient','接收 Agent',workspace.agents)+pick('project','关联协作空间',workspace.projects)+area('body','消息内容');
 openPanel(({agents:'注册 / 编辑 Agent',projects:'建立协作空间',channels:'配置可复用提交渠道',submissions:'将完成文件加入提交区域',messages:'站内消息'})[kind],fields,async d=>{await api('workspace/'+kind,{...d,...(old?{id:old.id,revision:old.revision}:{})});toast('已保存')});
}
document.addEventListener('change',e=>{if(e.target.id==='grouping'){grouping=e.target.value;renderTasks()}});

document.addEventListener('click',async e=>{const b=e.target.closest('button');if(!b)return;try{
 if(b.dataset.quick){await change(b.dataset.id,{action:b.dataset.quick});return}
 if(b.hasAttribute('data-loader')){await navigator.clipboard.writeText('请在本机 learning-terminal 仓库读取 frontend/AGENT-CONNECT.md，按其中说明使用 frontend/agent-client.py 注册你的唯一名称和职责。');toast('装载说明已复制，交给需要接入的 Agent')}
 if(b.hasAttribute('data-config'))configure();
 if(b.hasAttribute('data-publish'))publish();
 if(b.dataset.assign)publish('',b.dataset.assign);
 if(b.dataset.project)publish(b.dataset.project);
 if(b.dataset.create)recordForm(b.dataset.create);
 if(b.dataset.editRecord)recordForm(b.dataset.editRecord,workspace[b.dataset.editRecord].find(x=>x.id===b.dataset.id));
 if(b.hasAttribute('data-deploy'))openPanel('部署目录监听',field('watchDir','监听目录的绝对路径')+field('intervalMinutes','检查间隔（分钟）','5','number')+`<p class="hint">稳定文件将进入手机收发队列；这不是作业提交渠道。保存保留工具原启停状态；若原本启用，新目录将按周期生效。概率论网站监听请使用下方专用抓取器。</p>`,async d=>{const task=await api('tool-actions',{requestId:crypto.randomUUID(),tool_id:'dirwatch',tool_action:'configure',tool_input:{watchDir:d.watchDir,intervalMinutes:Number(d.intervalMinutes)}});toast('配置已排队，请核对执行结果');await refresh();showDetail(task.id)});
 if(b.dataset.submitFile){const item=workspace.submissions.find(x=>x.id===b.dataset.submitFile);if(confirm('将此完成文件发送到已配置的渠道？')){b.disabled=true;await api('submit',{id:item.id,revision:item.revision});await refresh()}}
 }catch(err){toast(err.message)}});
refresh(true);

function channelForm(old=null){
 const a=old||{}, draft={folder:{},email:{},webhook:{}};let previous=a.type||'folder';draft[previous]={...a};
 openPanel('设置提交方式',`<label>交到哪里<select name="type"><option value="folder">保存到文件夹</option><option value="email">发送邮件</option><option value="webhook">提交网站</option></select></label>`+field('name','给这个方式起个名字（可选）',a.name)+`<div id="destination-fields"></div>`,async d=>{await api('workspace/channels',{...d,name:d.name.trim()||channelNames[d.type]+' · '+d.target,...(old?{id:old.id,revision:old.revision}:{})});toast('提交方式已保存，下次直接选择即可')});
 const f=$('compose-form');f.elements.type.value=previous;
 const update=()=>{const type=f.elements.type.value,v=draft[type];$('destination-fields').innerHTML=type==='folder'?field('target','文件夹位置',v.target)+`<p class="hint">完成文件会复制到这个文件夹，原文件保留。</p>`:type==='email'?field('target','收件邮箱',v.target,'email')+`<details class="sender-settings" ${!v.sender?'open':''}><summary>发件账号 · 首次设置后可复用</summary>`+field('sender','发件邮箱',v.sender,'email')+field('host','邮箱服务器（SMTP SSL，端口 465）',v.host)+field('credential_env','已配置的授权码变量名',v.credential_env)+`<p class="hint">使用本机已配置的凭证，不在此输入密码。</p></details>`:field('target','网站接收接口（HTTPS）',v.target,'url')+`<p class="hint">这里需要网站提供的提交接口。若只有普通作业页面，请通过左侧“＋”交给 Agent 接入该网站。</p><details><summary>接口认证（可选）</summary>`+field('credential_env','本机凭证变量名',v.credential_env)+`<p class="hint">接收格式：submissionId、filename、sha256、contentBase64。</p></details>`;f.elements.target.required=true};
 f.elements.type.onchange=()=>{draft[previous]=Object.fromEntries(new FormData(f));previous=f.elements.type.value;update()};update();
}

// Per-task leadership is independent of the host that happens to display this page.
const coopKeys=['collaboration_mode','lead_host_id','execution_host_id','integrator_agent_id','responsibilities'];
const hostName=id=>workspace.hosts?.find(h=>h.id===id)?.name||id||'未指定';
function coopFields(c={}){
 const local=workspace.local_host_id;
 return `<fieldset class="cooperation-fields"><legend>主机分工</legend><label>协作方式<select name="collaboration_mode"><option value="led" ${c.collaboration_mode!=='joint'?'selected':''}>指定主机主导</option><option value="joint" ${c.collaboration_mode==='joint'?'selected':''}>双方共同协作</option></select></label>`+pick('lead_host_id','主导主机（共同协作时忽略）',workspace.hosts||[],c.lead_host_id??local)+pick('execution_host_id','执行主机',workspace.hosts||[],c.execution_host_id??local)+pick('integrator_agent_id','成果汇总 Agent（可选）',workspace.agents,c.integrator_agent_id)+area('responsibilities','双方分工与汇总约定（共同协作必填）',c.responsibilities)+`<p class="hint">两端地位平等，主导权只属于当前任务。离线不会自动改变分工。</p></fieldset>`;
}
function coopLabel(t){const c=t.collaboration;return !c?'尚未设置主机分工':c.collaboration_mode==='joint'?'双方共同协作':hostName(c.lead_host_id)+'主导'}
const beforeCoopPanel=openPanel;
openPanel=function(title,fields,save){
 if(title==='布置学习任务'){
  fields+=coopFields();
 }
 return beforeCoopPanel(title,fields,save);
};
const beforeCoopEditor=openEditor;
openEditor=function(task=null,defaults={}){beforeCoopEditor(task,defaults);$('task-form').querySelector('.cooperation-fields')?.remove();$('task-form').querySelector('[type=submit]').insertAdjacentHTML('beforebegin',coopFields(task?.collaboration))};
const beforeCoopTile=taskTile;
taskTile=function(t){return beforeCoopTile(t).replace('</strong>',`</strong><small>${esc(coopLabel(t))}</small>`)};
const beforeCoopAgents=renderAgents;
renderAgents=function(){
 beforeCoopAgents();
 $('page').insertAdjacentHTML('afterbegin',`<section class="panel panel-body"><h2>协作主机</h2><p>主机地位平等；每项任务分别指定主导方式、执行位置和汇总责任。</p><button data-host-new>登记另一台主机</button> <button data-import-packet>导入交接包</button><div class="tool-grid">${(workspace.hosts||[]).map(h=>`<article class="tool-card"><h3>${esc(h.name)}${h.id===workspace.local_host_id?' · 本机':''}</h3><p>${esc(h.platform)} · ${h.connection_status==='online'?'在线（本机服务）':'远端状态未知'}</p><small>主机 ID：${esc(h.id)}</small><p>${esc(h.endpoint||'')}</p></article>`).join('')}</div><p class="hint">远端资料登记不代表连接成功。交接包由你通过“远程传输”传送，再在目标电脑导入；收到的任务不会自动执行。</p></section>`);
 for(const card of $('page').querySelectorAll('.tool-card')){
  const button=card.querySelector('[data-edit-record="agents"]');if(!button)continue;
  const a=workspace.agents.find(x=>x.id===button.dataset.id);
  card.insertAdjacentHTML('beforeend',`<p>${esc(hostName(a.host_id))} · ${{online:'在线',offline:'离线',unknown:'连接未知'}[a.connection_status]||'连接未知'} · ${{idle:'空闲',busy:'忙碌',paused:'暂停',offline:'已退出'}[a.work_status]||'未报告'}</p>`);
 }
};
const beforeCoopRecord=recordForm;
recordForm=function(kind,old=null){beforeCoopRecord(kind,old);if(kind==='agents')$('compose-fields').insertAdjacentHTML('beforeend',pick('host_id','所在主机',workspace.hosts||[],old?.host_id||workspace.local_host_id))};
const beforeCoopDetail=showDetail;
showDetail=function(id,open=true){
 beforeCoopDetail(id,open);const t=state.tasks.find(x=>x.id===id);if(!t)return;
 const c=t.collaboration||{};
 $('detail-content').insertAdjacentHTML('beforeend',`<section class="detail-section"><h3>${esc(coopLabel(t))}</h3><p>执行主机：${esc(hostName(c.execution_host_id))} · 汇总：${esc(workspace.agents.find(a=>a.id===c.integrator_agent_id)?.name||'按分工约定')}</p><p class="detail-text">${esc(c.responsibilities||'未填写分工')}</p>${t.origin?`<p>来自 ${esc(hostName(t.origin.host_id))} 的任务；原任务版本 ${esc(t.origin.revision)}</p>`:''}${!['done','deleted','cancelled'].includes(t.state)?`<button data-coop-edit="${esc(id)}">调整主导与分工</button>`:''} ${t.executor==='agent-handoff'&&t.state==='waiting_external'&&!t.origin?`<button data-packet-export="${esc(id)}" data-kind="handoff">导出任务交接包</button>`:''}${t.origin&&['review','done'].includes(t.state)?`<button data-packet-export="${esc(id)}" data-kind="result">导出结果回传包</button>`:''}<p class="hint">分工变更使用版本校验并留存历史，不会重新运行任务。结果回传后仍需验收。</p></section>`);
};
function downloadPacket(packet){const url=URL.createObjectURL(new Blob([JSON.stringify(packet,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download=`LT-${packet.kind}-${packet.packet_id}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}
document.addEventListener('click',async e=>{
 const b=e.target.closest('button');if(!b)return;
 try{
  if(b.hasAttribute('data-host-new'))openPanel('登记协作主机',field('id','对方终端显示的主机 ID')+field('name','主机名称（例如 Windows）')+field('platform','系统','Windows')+field('endpoint','远程连接说明（可选）'),d=>{if(!d.id.trim())throw Error('请填写对方终端显示的主机 ID');return api('workspace/hosts',d)});
  if(b.dataset.coopEdit){const t=state.tasks.find(x=>x.id===b.dataset.coopEdit);$('detail').close();openPanel('调整主导与分工',coopFields(t.collaboration),d=>api('tasks/'+t.id,{...d,action:'collaboration',revision:t.revision}))}
  if(b.dataset.packetExport){const t=state.tasks.find(x=>x.id===b.dataset.packetExport);downloadPacket(await api('agent',{action:'export-packet',task_id:t.id,packet_kind:b.dataset.kind,target_host_id:t.collaboration?.execution_host_id}));toast('交接包已下载，请通过远程传输递交')}
  if(b.hasAttribute('data-import-packet')){
   const input=document.createElement('input');input.type='file';input.accept='.json,application/json';
   input.onchange=async()=>{try{const f=input.files[0];if(!f)return;if(f.size>90000)throw Error('交接包超过 90 KB');const packet=JSON.parse(await f.text());openPanel('核对并导入交接包',`<p>来源：${esc(packet.sender?.name||'未知')}<br>类型：${esc(packet.kind)}<br>任务：${esc(packet.payload?.title||packet.payload?.id||'未知')}</p><p class="detail-text">${esc(packet.payload?.notes||packet.payload?.result||'')}</p>`,async()=>{const r=await api('agent',{action:'import-packet',packet});toast(r.duplicate?'此交接包已接收，未重复创建':'已接收，任务仍需安排或验收')})}catch(err){toast(err.message)}};input.click();
  }
 }catch(err){toast(err.message)}
});
