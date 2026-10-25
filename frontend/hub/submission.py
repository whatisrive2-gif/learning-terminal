"""Explicit file submissions through reusable channels, with no automatic retries."""
import base64
import hashlib
import json
import os
from pathlib import Path
import smtplib
import ssl
from email.message import EmailMessage
import urllib.request
from .workspace import get
from .core import now

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): raise ValueError('提交接口重定向被拒绝，请核对渠道地址')

def send(store, data):
    def update(item,**fields):
        item.update(**fields,updated=now(),revision=item['revision']+1)
        store.db.execute('UPDATE records SET data=? WHERE kind=? AND id=?',(json.dumps(item,ensure_ascii=False),'submissions',item['id']))
        return item
    with store.lock,store.db:
        item=get(store,'submissions',data.get('id'))
        if not item or item['revision']!=data.get('revision') or item['status']!='ready': raise ValueError('条目已变化或已提交；不会重复发送')
        channel=item['channel_snapshot']
        path=Path(item['path'])
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=item['sha256']: raise ValueError('文件已修改，请重新加入提交区域以确认新版本')
        secret=os.environ.get(channel['credential_env'],'') if channel['credential_env'] else ''
        if channel['credential_env'] and not secret: raise ValueError('服务进程缺少渠道凭证环境变量')
        if channel['type']=='email' and not secret: raise ValueError('邮件渠道需要 SMTP 密码环境变量')
        update(item,status='sending')
    try:
        if channel['type']=='folder':
            dest=Path(channel['target'])
            if not dest.is_dir(): raise ValueError('提交目录不存在')
            target=dest/(item['id'][:8]+'-'+path.name)
            with target.open('xb') as stream: stream.write(raw)
            receipt='文件已写入指定目录：'+str(target)
        elif channel['type']=='webhook':
            payload=json.dumps(dict(submissionId=item['id'],filename=path.name,sha256=item['sha256'],contentBase64=base64.b64encode(raw).decode())).encode()
            headers={'Content-Type':'application/json','Idempotency-Key':item['id']}
            if secret: headers['Authorization']='Bearer '+secret
            req=urllib.request.Request(channel['target'],data=payload,headers=headers,method='POST')
            with urllib.request.build_opener(NoRedirect).open(req,timeout=25) as response:
                receipt='提交接口 HTTP '+str(response.status)+'；接收方保存/作业验收须另行确认'
        else:
            msg=EmailMessage();msg['From']=channel['sender'];msg['To']=channel['target'];msg['Subject']=item['name'];msg.set_content(item['notes'] or '作业提交')
            msg.add_attachment(raw,maintype='application',subtype='octet-stream',filename=path.name)
            with smtplib.SMTP_SSL(channel['host'],465,timeout=25,context=ssl.create_default_context()) as smtp:
                smtp.login(channel['sender'],secret)
                refused=smtp.send_message(msg)
                if refused: raise ValueError('收件人被拒绝')
            receipt='SMTP 已接受邮件；不代表收件人已阅读或作业通过'
        with store.lock,store.db: return update(item,status='submitted',receipt=receipt)
    except Exception as exc:
        # Network failures can happen after the other side accepted the file.
        with store.lock,store.db: return update(item,status='unknown',receipt='结果需核对；不会自动重发。'+type(exc).__name__)
