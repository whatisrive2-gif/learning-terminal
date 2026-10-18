import test from 'node:test';
import assert from 'node:assert/strict';
import {parseLesson,buildReader} from './reader.mjs';
const input={session:'l_ab12',workspace:'C:/学习/状态',revision:2,goal:'理解数学推导'};
test('declination inequality renders with its symbols intact',()=>{
  const r=parseLesson(String.raw`条件为 \(\delta<-(90^\circ-\varphi)\)。`);
  assert.equal(r.formulas,1);assert.deepEqual(r.errors,[]);
  const html=r.sections[0].blocks[0].html;
  assert.match(html,/<mi>δ<\/mi>/);assert.match(html,/<mo>&lt;<\/mo>/);
});
test('display formulas work within sentences, lists and tables',()=>{
  for(const text of [String.raw`前文 \[x<0\] 后文`,String.raw`前文 $$x<0$$ 后文`,
      String.raw`- 条件 \[x<0\]。`,String.raw`| 条件 |`+'\n|---|\n| '+String.raw`\[x<0\]`+' |']){
    const r=parseLesson(text);assert.equal(r.formulas,1,text);assert.deepEqual(r.errors,[]);
  }
});
test('broken source cannot masquerade as zero formula errors',()=>{
  for(const text of [String.raw`(delta<-(90^\circ-\varphi)`,String.raw`(delta)`, '(\u000barphi)']) {
    const r=parseLesson(text);assert.ok(r.errors.length>0,text);assert.equal(r.formulas,0);
  }
});
test('code, prose and valid Greek commands do not trigger naked-math warnings',()=>{
  for(const text of ['普通括号（解释），delta 是一个名称。', '`\\varphi`', '```text\n(delta) \\varphi\n```', String.raw`\(\varphi\)`]){
    assert.deepEqual(parseLesson(text).errors,[],text);
  }
});
test('citations hide technical IDs while preserving raw provenance',()=>{
  for(const reference of ['[S:s_074c2dc7d603] p.7–8','[S:s\\_074c2dc7d603] p.7–8']){
    const result=parseLesson('## 学习\n\n解释。'+reference);
    const block=result.sections[0].blocks[0];
    assert.ok(block.raw.includes(reference));
    assert.match(block.html,/data-citation="s_074c2dc7d603"/);
    assert.match(block.html,/>第 7–8 页<\/button>/);
    assert.ok(!block.html.replace(/<[^>]*>/g,'').includes('s_074c2dc7d603'));
  }
});
test('citation syntax inside code is not transformed',()=>{
  const result=parseLesson('`[S:s_ab12] p.3`\n\n```text\n[S:s_ab12] p.3\n```');
  assert.ok(!result.sections.flatMap(s=>s.blocks).some(b=>b.html.includes('data-citation=')));
});

test('all four math delimiter types become MathML',()=>{
  const result=parseLesson('# 数学\n\n## 公式\n\n行内 \\(x^2\\) 和 $y_1$。\n\n\\[\n\\frac{a}{b}\n\\]\n\n$$\nz=2\n$$\n');
  assert.equal(result.formulas,4);assert.equal(result.errors.length,0);
  assert.ok(result.sections[0].blocks.some(b=>b.html.includes('<mfrac>')));
});
test('matrix and aligned expressions render',()=>{
  const result=parseLesson('\\[\\begin{pmatrix}a\\\\b\\end{pmatrix}\\]\n\n\\[\\begin{aligned}x&=a+b\\\\y&=c\\end{aligned}\\]\n');
  assert.equal(result.formulas,2);assert.deepEqual(result.errors,[]);
});
test('code fences are not treated as formulas or section headings',()=>{
  const result=parseLesson('## 正文\n\n```text\n## not a section\n$x$\n```\n');
  assert.equal(result.sections.length,1);assert.equal(result.formulas,0);
});
test('invalid formula remains visibly flagged',()=>{
  const result=parseLesson('\\[\\notARealCommand{x}\\]\n');
  assert.equal(result.errors.length,1);assert.match(result.sections[0].blocks[0].html,/公式待核对/);
});
test('raw HTML, scripts and javascript links cannot execute',()=>{
  const result=parseLesson('<script>alert(1)</script>\n\n<img src=x onerror=alert(1)>\n\n[bad](javascript:alert(1))');
  const html=result.sections.flatMap(s=>s.blocks).map(b=>b.html).join('');
  assert.ok(!html.includes('<script>'));assert.ok(!html.includes('<img '));assert.ok(!html.includes('href="javascript:'));
});
test('script-closing text in metadata is escaped',()=>{
  const result=buildReader({...input,goal:'</script><script>alert(1)</script>',markdown:'## 学习\n\n内容'});
  assert.equal((result.fragment.match(/<script>/g)||[]).length,1);
  assert.ok(result.fragment.includes('\\u003c/script'));
});
test('changed block is marked, unchanged content is retained',()=>{
  const result=parseLesson('## 一\n\n保留。\n\n增加。','## 一\n\n保留。');
  assert.equal(result.sections[0].blocks[0].changed,false);
  assert.equal(result.sections[0].blocks[1].changed,true);
});
test('context carries session and revision without an API call',()=>{
  const result=buildReader({...input,markdown:'## 学习\n\n内容'});
  assert.match(result.fragment,/sendFollowUpMessage/);assert.match(result.fragment,/l_ab12/);
  assert.ok(!result.fragment.includes('fetch('));assert.ok(!result.fragment.includes('<link'));
});
