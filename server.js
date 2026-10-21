const express=require('express'),multer=require('multer'),{spawn}=require('child_process'),fs=require('fs'),path=require('path');
const CODE=process.env.CODE||'123123',KEY=process.env.TIKTOK_CLIENT_KEY,SEC=process.env.TIKTOK_CLIENT_SECRET;
const BASE=process.env.RENDER_EXTERNAL_URL||'http://localhost:10000',RED=BASE+'/auth/callback';
const T='/tmp/ipq';fs.mkdirSync(T,{recursive:true});
const up=multer({dest:T}),jobs={};let tt=null,state='';
const app=express();app.use(express.json());
const ok=(q,s,n)=>((q.headers['x-code']||q.query.code)===CODE)?n():s.status(401).json({error:'code'});
app.get('/',(q,s)=>s.sendFile(path.join(__dirname,'index.html')));

app.post('/api/encode',ok,up.single('file'),(q,s)=>{
 if(!q.file)return s.status(400).json({error:'no file'});
 const id=q.file.filename,fps=+q.body.fps||60,S=+q.body.res||1080,dur=+q.body.dur||0,out=path.join(T,id+'.mp4');
 const vf=`scale='if(gt(iw,ih),-2,${S})':'if(gt(iw,ih),${S},-2)':flags=lanczos,fps=${fps}`;
 const a=['-y','-i',q.file.path,'-vf',vf,'-c:v','libx264','-preset','veryfast','-crf',S>1080?'17':'15','-profile:v','high','-pix_fmt','yuv420p','-c:a','aac','-b:a','256k','-movflags','+faststart','-threads','2','-progress','pipe:1','-nostats',out];
 const j=jobs[id]={p:0,st:'run',out,t:Date.now(),msg:''};
 const f=spawn('ffmpeg',a);
 f.stdout.on('data',d=>{const m=[...String(d).matchAll(/out_time_us=(\d+)/g)].pop();if(m&&dur)j.p=Math.min(99,Math.round(m[1]/1e4/dur))});
 f.stderr.on('data',d=>{j.msg=(j.msg+d).slice(-400)});
 f.on('close',c=>{fs.unlink(q.file.path,()=>{});j.st=c===0?'done':'error';if(c===0)j.p=100});
 s.json({id});
});
app.get('/api/status/:id',ok,(q,s)=>{const j=jobs[q.params.id];j?s.json({p:j.p,st:j.st,msg:j.st==='error'?j.msg:''}):s.status(404).json({error:'none'})});
app.get('/api/download/:id',ok,(q,s)=>{const j=jobs[q.params.id];if(!j||j.st!=='done')return s.status(404).end();
 if(q.query.inline)return s.sendFile(j.out);s.download(j.out,'iPquality.mp4')});

app.get('/api/tiktok',ok,(q,s)=>s.json({linked:!!tt,configured:!!KEY}));
app.get('/auth/tiktok',ok,(q,s)=>{if(!KEY)return s.status(400).send('TIKTOK_CLIENT_KEY missing');state=Math.random().toString(36).slice(2);
 s.redirect('https://www.tiktok.com/v2/auth/authorize/?client_key='+KEY+'&scope=user.info.basic,video.publish&response_type=code&redirect_uri='+encodeURIComponent(RED)+'&state='+state)});
app.get('/auth/callback',async(q,s)=>{
 if(!q.query.code||q.query.state!==state)return s.status(400).send('error');
 try{const r=await fetch('https://open.tiktokapis.com/v2/oauth/token/',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({client_key:KEY,client_secret:SEC,code:q.query.code,grant_type:'authorization_code',redirect_uri:RED})}).then(r=>r.json());
 tt=r.access_token?r:null}catch(e){tt=null}
 s.redirect('/')});

app.post('/api/post/:id',ok,async(q,s)=>{
 try{
  const j=jobs[q.params.id];if(!j||j.st!=='done')return s.status(400).json({error:'no video'});
  if(!tt)return s.status(400).json({error:'اربط حسابك أول'});
  const size=fs.statSync(j.out).size;let chunk=size,count=1;if(size>64e6){chunk=64e6;count=Math.floor(size/chunk)}
  const r=await fetch('https://open.tiktokapis.com/v2/post/publish/video/init/',{method:'POST',headers:{Authorization:'Bearer '+tt.access_token,'Content-Type':'application/json; charset=UTF-8'},
   body:JSON.stringify({post_info:{title:String(q.body.title||'').slice(0,2000),privacy_level:q.body.privacy||'SELF_ONLY'},source_info:{source:'FILE_UPLOAD',video_size:size,chunk_size:chunk,total_chunk_count:count}})}).then(r=>r.json());
  if(!r.data||!r.data.upload_url)return s.status(400).json({error:JSON.stringify(r.error||r)});
  const fd=await fs.promises.open(j.out,'r');
  for(let i=0;i<count;i++){const st=i*chunk,en=i===count-1?size-1:st+chunk-1,b=Buffer.alloc(en-st+1);await fd.read(b,0,b.length,st);
   const u=await fetch(r.data.upload_url,{method:'PUT',headers:{'Content-Type':'video/mp4','Content-Range':`bytes ${st}-${en}/${size}`},body:b});
   if(u.status>=300)throw new Error('upload '+u.status)}
  await fd.close();s.json({ok:true})
 }catch(e){s.status(500).json({error:String(e.message||e)})}
});
setInterval(()=>{for(const id in jobs)if(Date.now()-jobs[id].t>36e5){fs.unlink(jobs[id].out,()=>{});delete jobs[id]}},6e5).unref();
app.listen(process.env.PORT||10000);
