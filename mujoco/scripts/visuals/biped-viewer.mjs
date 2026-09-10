// Canvas rendering on demand only; no animation loop and no network access.
(function initViewer(){
  const canvas=document.querySelector('#scene'),fallback=document.querySelector('#fallback'),status=document.querySelector('#status');
  const panel=document.querySelector('#controls'),pose={...DEFAULT_POSE},camera={...DEFAULT_CAMERA};
  let context;
  try{context=canvas.getContext('2d');}catch{}
  if(!context){status.textContent='Canvas를 사용할 수 없어 정지 그림을 표시합니다.';return;}
  canvas.hidden=false;fallback.hidden=true;panel.disabled=false;
  let width=0,height=0,drag=null,labels=true;
  const announce=text=>{status.textContent=text;};
  function draw(){
    if(!width||!height)return;
    const scene=projectedScene(width,height,pose,camera);
    context.clearRect(0,0,width,height);context.fillStyle='#F5F6F0';context.fillRect(0,0,width,height);
    context.strokeStyle='#D9E3DC';context.lineWidth=1;
    for(const line of scene.grid){context.beginPath();context.moveTo(line[0].x,line[0].y);context.lineTo(line[1].x,line[1].y);context.stroke();}
    context.fillStyle='rgba(20,63,67,.065)';context.beginPath();context.ellipse(scene.origin.x,scene.origin.y,width*.125,height*.024,0,0,Math.PI*2);context.fill();
    for(const face of scene.faces){
      context.beginPath();face.points.forEach((p,i)=>i?context.lineTo(p.x,p.y):context.moveTo(p.x,p.y));context.closePath();
      context.fillStyle=face.color;context.strokeStyle=face.color;context.lineWidth=.5;context.fill();context.stroke();
    }
    if(labels){
      context.font=`600 ${width<440?13:15}px "Apple SD Gothic Neo", "Noto Sans KR", sans-serif`;
      context.textBaseline='middle';context.textAlign='right';
      for(const {point,label} of scene.anchors){
        const end=Math.max(86,point.x-70);
        context.strokeStyle='#829A90';context.lineWidth=1;context.beginPath();context.moveTo(point.x-10,point.y);context.lineTo(end,point.y);context.stroke();
        const labelWidth=context.measureText(label).width;
        context.fillStyle='rgba(245,246,240,.94)';context.fillRect(end-labelWidth-14,point.y-13,labelWidth+10,26);
        context.fillStyle='#143F43';context.fillText(label,end-8,point.y);
      }
    }
  }
  function resize(){
    const rect=canvas.getBoundingClientRect();width=rect.width;height=rect.height;
    const ratio=Math.min(window.devicePixelRatio||1,2);
    canvas.width=Math.round(width*ratio);canvas.height=Math.round(height*ratio);
    context.setTransform(ratio,0,0,ratio,0,0);draw();
  }
  function setValues(){
    for(const [id] of JOINTS){const input=document.getElementById(id);input.value=String(pose[id]);document.getElementById(`${id}-value`).value=`${pose[id]}°`;}
    document.querySelector('#pose-readout').textContent=`왼쪽 [${pose.leftHip}, ${pose.leftKnee}, ${pose.leftAnkle}]° · 오른쪽 [${pose.rightHip}, ${pose.rightKnee}, ${pose.rightAnkle}]°`;
  }
  for(const [id,label] of JOINTS){
    const input=document.getElementById(id);
    input.addEventListener('input',()=>{pose[id]=Number(input.value);setValues();draw();});
    input.addEventListener('change',()=>announce(`${label} ${pose[id]}도. 기하 자세만 변경했습니다.`));
  }
  const constrain=()=>{camera.pitch=Math.max(-.15,Math.min(1.1,camera.pitch));camera.zoom=Math.max(.7,Math.min(1.35,camera.zoom));};
  function changeView(yaw,pitch){camera.yaw=yaw;camera.pitch=pitch;camera.zoom=1;draw();}
  document.querySelector('#front').addEventListener('click',()=>{changeView(0,.12);announce('정면 시점');});
  document.querySelector('#side').addEventListener('click',()=>{changeView(Math.PI/2,.12);announce('측면 시점');});
  document.querySelector('#reset').addEventListener('click',()=>{
    Object.assign(pose,DEFAULT_POSE);Object.assign(camera,DEFAULT_CAMERA);labels=true;document.querySelector('#labels').checked=true;setValues();draw();announce('기본 자세와 시점으로 초기화했습니다.');
  });
  document.querySelector('#pose-bend').addEventListener('click',()=>{
    Object.assign(pose,{leftHip:-22,leftKnee:44,leftAnkle:-22,rightHip:-22,rightKnee:44,rightAnkle:-22});setValues();draw();announce('굽힌 기하 자세. 균형이나 지면 접촉은 계산하지 않습니다.');
  });
  document.querySelector('#labels').addEventListener('change',e=>{labels=e.target.checked;draw();});
  for(const [id,delta] of [['zoom-in',.1],['zoom-out',-.1]])document.getElementById(id).addEventListener('click',()=>{camera.zoom+=delta;constrain();draw();announce(`확대 ${Math.round(camera.zoom*100)}퍼센트`);});
  canvas.addEventListener('pointerdown',event=>{
    if(!event.isPrimary||event.button!==0)return;
    drag={id:event.pointerId,x:event.clientX,y:event.clientY};canvas.setPointerCapture(event.pointerId);canvas.focus({preventScroll:true});
  });
  canvas.addEventListener('pointermove',event=>{
    if(!drag||drag.id!==event.pointerId)return;
    camera.yaw+=(event.clientX-drag.x)*.008;camera.pitch+=(event.clientY-drag.y)*.006;
    drag.x=event.clientX;drag.y=event.clientY;constrain();draw();
  });
  function endDrag(event){if(drag?.id===event.pointerId){drag=null;announce('시점을 변경했습니다. 방향키로도 회전할 수 있습니다.');}}
  canvas.addEventListener('pointerup',endDrag);canvas.addEventListener('pointercancel',endDrag);canvas.addEventListener('lostpointercapture',()=>{drag=null;});
  canvas.addEventListener('keydown',event=>{
    let handled=true;
    switch(event.key){
      case 'ArrowLeft':camera.yaw-=.12;break;case 'ArrowRight':camera.yaw+=.12;break;
      case 'ArrowUp':camera.pitch-=.10;break;case 'ArrowDown':camera.pitch+=.10;break;
      case '+':case '=':camera.zoom+=.1;break;case '-':case '_':camera.zoom-=.1;break;
      case 'Home':Object.assign(camera,DEFAULT_CAMERA);break;default:handled=false;
    }
    if(handled){event.preventDefault();constrain();draw();announce(`시점 변경. 확대 ${Math.round(camera.zoom*100)}퍼센트`);}
  });
  if('ResizeObserver' in window)new ResizeObserver(resize).observe(canvas);else window.addEventListener('resize',resize);
  setValues();resize();announce('준비됨 · 드래그 또는 방향키로 회전하세요. 자동 재생은 없습니다.');
})();
