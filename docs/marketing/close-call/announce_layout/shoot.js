// Re-shoot stills: node shoot.js  (writes frame_1..6.png at 1080x1920 from frames.html?s=s1..s6)
const {chromium}=require('playwright');
(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:540,height:960},deviceScaleFactor:2});
for(let i=1;i<=6;i++){await p.goto('file://'+__dirname+'/frames.html?s=s'+i);await p.waitForTimeout(300);await p.screenshot({path:__dirname+`/frame_${i}.png`});}
await b.close();})();
