import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { randomUUID, createHash } from 'node:crypto';
import { Marked } from 'marked';
import katex from 'katex';

const here = path.dirname(fileURLToPath(import.meta.url));
const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safeJSON = value => JSON.stringify(value).replace(/[<>&\u2028\u2029]/g, c => `\\u${c.charCodeAt(0).toString(16).padStart(4,'0')}`);

export function parseLesson(markdown, previous = '') {
  let formulas = 0;
  const errors = [];
  // Audit the source too: unrecognised math never reaches KaTeX's error handler.
  for(const hit of markdown.matchAll(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g)) {
    errors.push({kind:'control-character',tex:`U+${hit[0].charCodeAt(0).toString(16).padStart(4,'0')}`,
      message:`第 ${markdown.slice(0,hit.index).split('\n').length} 行存在控制字符，可能由公式反斜杠被字符串转义造成。请修复源码。`});
  }
  const math = (tex, display) => {
    try {
      const rendered = katex.renderToString(tex.trim(), {displayMode: display, output: 'mathml',
        throwOnError: true, trust: false, strict: 'warn', maxExpand: 1000, maxSize: 20});
      formulas++;
      return `<span class="lt-math${display ? ' lt-display' : ''}" data-tex="${escape(tex)}">${rendered}</span>`;
    } catch (error) {
      errors.push({tex, message: error.message});
      return `<span class="lt-math-error" role="note">公式待核对：<code>${escape(tex)}</code></span>`;
    }
  };
  const md = new Marked({gfm:true, breaks:false});
  md.use({extensions:[
    {name:'ltCitation', level:'inline',
      start(src) { const i=src.indexOf('[S:'); return i<0?undefined:i; },
      tokenizer(src) {
        const hit=/^\[S:(s\\?_[a-f0-9]+)\](?:[ \t]*p{1,2}\.[ \t]*([0-9]+(?:[ \t]*[–—-][ \t]*[0-9]+)?))?/.exec(src);
        if(hit) return {type:'ltCitation',raw:hit[0],source:hit[1].replaceAll('\\',''),pages:hit[2]||''};
      }, renderer(token) {
        const label=token.pages?`第 ${token.pages} 页`:'来源';
        return `<button type="button" class="lt-citation" data-citation="${escape(token.source)}" data-pages="${escape(token.pages)}" aria-label="查看出处：${escape(label)}">${escape(label)}</button>`;
      }},
    {name:'ltDisplay', level:'block',
      start(src) { const i = src.search(/^ {0,3}(?:\\\[|\$\$)/m); return i < 0 ? undefined : i; },
      tokenizer(src) {
        const hit = /^(?: {0,3})\\\[([\s\S]*?)\\\](?:[ \t]*\n|$)/.exec(src)
          || /^(?: {0,3})\$\$([\s\S]*?)\$\$(?:[ \t]*\n|$)/.exec(src);
        if(hit) return {type:'ltDisplay',raw:hit[0],tex:hit[1]};
      }, renderer(token) { return math(token.tex,true); }},
    {name:'ltInline',level:'inline',
      start(src) { const i=src.search(/\\[([]|\$/); return i<0?undefined:i; },
      tokenizer(src) {
        const display=/^\\\[([\s\S]*?)\\\]/.exec(src) || /^\$\$([\s\S]*?)\$\$/.exec(src);
        if(display) return {type:'ltInline',raw:display[0],tex:display[1],display:true};
        const hit=/^\\\(([\s\S]*?)\\\)/.exec(src) || /^\$(?!\$)([^\n$]+?)\$(?!\$)/.exec(src);
        if(hit) return {type:'ltInline',raw:hit[0],tex:hit[1]};
      }, renderer(token) { return math(token.tex,!!token.display); }}
  ], renderer:{
    html(token) { return escape(token.text); },
    link(token) {
      const text=this.parser.parseInline(token.tokens);
      if(!/^(https?:\/\/|#[a-zA-Z0-9_-])/i.test(token.href)) return text;
      return `<a href="${escape(token.href)}" target="_blank" rel="noopener noreferrer">${text}</a>`;
    },
    image(token) { return `<span class="lt-image-note">图像：${escape(token.text)}（请在原材料中核对）</span>`; }
  }});
  const tokens=md.lexer(markdown.replace(/\r\n/g,'\n'));
  md.walkTokens(tokens, token=>{
    if(token.type!=='text' || token.tokens) return;
    const raw=token.raw || token.text || '';
    const tex=/\\(?:alpha|beta|gamma|delta|varphi|phi|theta|sigma|omega|circ|frac|sqrt|mathrm|text|left|right|begin|end|sin|cos|tan|cdot|times|pm|sum|int|leq|geq)\b/.test(raw);
    const bareGreek=/\((?:alpha|beta|gamma|delta|varphi|theta|sigma)(?=[,=<>\s)])/i.test(raw);
    if(tex || bareGreek) errors.push({kind:'unwrapped-math',tex:raw.slice(0,240),
      message:'疑似公式未被数学分隔符包围，或希腊字母命令丢失反斜杠。保留原文，需检查源码；不能自动猜测符号含义。'});
  });
  const oldTokens=md.lexer(previous.replace(/\r\n/g,'\n'));
  const previousBlocks=new Set(oldTokens.filter(t=>t.type!=='space').map(t=>t.raw.trim()));
  let title='学习讲解';
  const sections=[];
  let current={title:'导读',blocks:[]};
  for(const token of tokens) {
    if(token.type==='space') continue;
    if(token.type==='heading' && token.depth===1 && sections.length===0 && current.blocks.length===0) {
      title=token.text; continue;
    }
    if(token.type==='heading' && token.depth===2) {
      if(current.blocks.length) sections.push(current);
      current={title:token.text,blocks:[]};
    } else {
      const raw=token.raw.trim();
      const html=md.parser([token]);
      current.blocks.push({id:createHash('sha256').update(raw).digest('hex').slice(0,12),raw,html,
        changed:!!previous && !previousBlocks.has(raw)});
    }
  }
  if(current.blocks.length) sections.push(current);
  if(!sections.length) throw new Error('讲解没有可展示内容。');
  return {title,sections,formulas,errors};
}

export function buildReader(input) {
  if(typeof input.markdown!=='string' || !input.markdown.trim()) throw new Error('缺少讲解正文。');
  if(!/^l_[a-f0-9]+$/.test(input.session) || typeof input.workspace!=='string' || !input.workspace.trim()
    || !Number.isInteger(input.revision) || input.revision<1) throw new Error('缺少有效的持久学习会话、目录或版本。');
  const lesson=parseLesson(input.markdown,input.previous || '');
  const rootId='lt-'+randomUUID().replaceAll('-','');
  const css=fs.readFileSync(path.join(here,'reader.css'),'utf8').replaceAll('__ROOT__',rootId);
  const client=fs.readFileSync(path.join(here,'reader-client.js'),'utf8');
  const context={session:input.session,workspace:input.workspace,revision:input.revision,
    goal:input.goal || '',title:lesson.title,sections:lesson.sections.map(s=>({title:s.title,blocks:s.blocks.map(({html,...b})=>b)})),
    sources:input.sources || [],branches:input.branches || [],initialSection:Math.max(0,Math.min(input.initialSection || 0,lesson.sections.length-1)),
    viewPath:input.viewPath || '',previousRevision:input.previousRevision || null};
  const options=lesson.sections.map((s,i)=>`<option value="${i}">${escape(s.title)}</option>`).join('');
  const sections=lesson.sections.map((s,i)=>`<section class="lt-section" data-section="${i}" ${i!==context.initialSection?'hidden':''}>
    <h2>${escape(s.title)}</h2>${s.blocks.map((b,j)=>`<div class="lt-block${b.changed?' lt-changed':''}" data-block="${j}">
    <div class="lt-content">${b.html}</div><button type="button" class="lt-select" data-select="${j}" aria-label="选定第 ${j+1} 段">选定这段</button>
    ${b.changed?'<span class="lt-change-label">本版新增或调整</span>':''}</div>`).join('\n')}</section>`).join('\n');
  const fragment=`<div id="${rootId}" class="lt-reader">
<style>${css}</style>
<header class="lt-header"><span class="lt-eyebrow">学习终端 / 阅读与追问</span><span>讲解版本 ${input.revision}</span></header>
<h1 class="lt-title">${escape(lesson.title)}</h1>
<p class="lt-goal">${escape(input.goal || '按你的问题逐步展开。')}</p>
<div class="lt-nav"><label>当前章节<select data-role="chapters" aria-label="当前章节">${options}</select></label><div class="lt-paging"><button type="button" data-role="prev">上一节</button><button type="button" data-role="next">下一节</button></div></div>
<p class="lt-hint">点击一段正文或划选文字即可追问；也可用 Tab 定位段落、Enter 选择。</p>
${lesson.errors.length?`<p class="lt-warning" role="alert">发现 ${lesson.errors.length} 项公式或源码问题；部分内容可能未正确排版，请先核对。</p>`:''}
<main>${sections}</main>
<details data-role="sources" class="lt-sources"><summary>来源与核对</summary><p data-role="source-detail">点击正文中的页码查看材料名称。来源标记不代表内容已经核实。</p></details>
<div class="lt-question">
<div class="lt-question-head"><span>围绕这里继续</span><button type="button" data-role="clear">改用整节</button></div>
<p class="lt-selection" data-role="selection">当前章节</p>
<div class="lt-actions" role="group" aria-label="学习操作">
<button type="button" data-action="deepen">沿这里深入</button><button type="button" data-action="steps">补中间步骤</button><button type="button" data-action="example">换个例子</button><button type="button" data-action="check">检查我的理解</button>
<button type="button" data-action="merge" ${context.branches.some(b=>b.status==='open')?'':'disabled'}>合回主线</button></div>
<label class="lt-note-label">你的问题或理解（可选）<textarea data-role="note" rows="2" placeholder="例如：我知道这个公式，但为什么这里可以用？"></textarea></label>
<div class="lt-send-row"><button type="button" data-role="send" class="lt-primary" disabled>先选择一个学习操作</button><span data-role="transport">检测对话连接…</span></div>
<p data-role="status" class="lt-status" role="status" aria-live="polite"></p>
<details data-role="prompt-details"><summary>查看将发送的上下文</summary><textarea data-role="prompt" rows="5" readonly aria-label="提问上下文"></textarea></details>
</div>
<footer class="lt-footer"><span>点击正文或划选文字，再选择学习操作。</span><button type="button" data-action="refresh">载入最新讲解</button><button type="button" data-action="reorganize">重组整体</button></footer>
</div>
<script>(()=>{const rootId=${safeJSON(rootId)};const context=${safeJSON(context)};${client}\n})();</script>`;
  if(Buffer.byteLength(fragment,'utf8')>=1000000) throw new Error('阅读视图超过 1 MB，请按章节生成，未静默截断。');
  return {fragment,report:{title:lesson.title,sections:lesson.sections.length,formulas:lesson.formulas,
    formulaErrors:lesson.errors,bytes:Buffer.byteLength(fragment),revision:input.revision}};
}

if(process.argv[1] && path.resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  try {
    const input=JSON.parse(fs.readFileSync(0,'utf8'));
    const {fragment,report}=buildReader(input);
    const output=path.resolve(input.out);
    fs.mkdirSync(path.dirname(output),{recursive:true});
    fs.writeFileSync(output,fragment,{encoding:'utf8',flag:'wx'});
    console.log(JSON.stringify({path:output,...report}));
  } catch(error) { console.error(JSON.stringify({error:error.message})); process.exitCode=1; }
}
