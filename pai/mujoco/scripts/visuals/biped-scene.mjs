// Original geometric teaching model in arbitrary display units. No robot asset,
// measured dimension, collision model, mass, dynamics, sensor, or policy data.
export const DEFAULT_POSE = Object.freeze({leftHip:-8,leftKnee:16,leftAnkle:-8,rightHip:-8,rightKnee:16,rightAnkle:-8});
export const DEFAULT_CAMERA = Object.freeze({yaw:0.52,pitch:0.22,zoom:1});
export const JOINTS = Object.freeze([
  ['leftHip','왼쪽 고관절',-40,40],['leftKnee','왼쪽 무릎',0,80],['leftAnkle','왼쪽 발목',-35,35],
  ['rightHip','오른쪽 고관절',-40,40],['rightKnee','오른쪽 무릎',0,80],['rightAnkle','오른쪽 발목',-35,35]
]);
const rad=d=>d*Math.PI/180;
const add=(a,b)=>a.map((v,i)=>v+b[i]);
const rotateX=(p,a)=>[p[0],p[1]*Math.cos(a)-p[2]*Math.sin(a),p[1]*Math.sin(a)+p[2]*Math.cos(a)];
const transform=(p,center,angle)=>add(rotateX(p,angle),center);
const COLORS={body:'#235B60',panel:'#F0D160',thigh:'#BED0C6',shin:'#789D90',joint:'#F0D160',foot:'#23494D',eye:'#173B40'};
function box(faces, center, size, color, angle=0){
  const [x,y,z]=size.map(v=>v/2);
  const vertices=[[-x,-y,-z],[x,-y,-z],[x,y,-z],[-x,y,-z],[-x,-y,z],[x,-y,z],[x,y,z],[-x,y,z]].map(p=>transform(p,center,angle));
  for(const inds of [[0,3,2,1],[4,5,6,7],[0,4,7,3],[1,2,6,5],[0,1,5,4],[3,7,6,2]])faces.push({points:inds.map(i=>vertices[i]),color});
}
function cylinder(faces,center,radius,length,color,angle=0){
  const n=18,rings=[-1,1].map(side=>Array.from({length:n},(_,i)=>transform([side*length/2,Math.cos(i*2*Math.PI/n)*radius,Math.sin(i*2*Math.PI/n)*radius],center,angle)));
  faces.push({points:[...rings[0]].reverse(),color},{points:rings[1],color});
  for(let i=0;i<n;i++)faces.push({points:[rings[0][i],rings[0][(i+1)%n],rings[1][(i+1)%n],rings[1][i]],color});
}
export function makeScene(pose=DEFAULT_POSE){
  const faces=[],anchors=[];
  box(faces,[0,1.82,0],[.91,.47,.43],COLORS.body);
  box(faces,[0,1.88,.229],[.60,.17,.045],COLORS.panel);
  box(faces,[0,2.26,.015],[.57,.30,.37],COLORS.body);
  box(faces,[0,2.27,.213],[.44,.17,.035],COLORS.panel);
  for(const x of [-.115,.115])box(faces,[x,2.28,.33],[.065,.065,.03],COLORS.eye);
  box(faces,[0,2.08,0],[.19,.09,.20],COLORS.foot);
  box(faces,[0,1.54,0],[.73,.10,.34],COLORS.foot);
  for(const [side,x] of [['left',-.30],['right',.30]]){
    const h=rad(pose[`${side}Hip`]),k=h+rad(pose[`${side}Knee`]),a=k+rad(pose[`${side}Ankle`]);
    const hip=[x,1.48,0],knee=transform([0,-.61,0],hip,h),ankle=transform([0,-.61,0],knee,k);
    box(faces,transform([0,-.305,0],hip,h),[.25,.57,.26],COLORS.thigh,h);
    box(faces,transform([0,-.305,0],knee,k),[.22,.56,.24],COLORS.shin,k);
    for(const [p,label] of [[hip,'고관절'],[knee,'무릎'],[ankle,'발목']]){
      cylinder(faces,p,.103,.32,COLORS.joint);
      if(side==='left')anchors.push({point:p,label});
    }
    box(faces,transform([0,-.12,.10],ankle,a),[.32,.15,.51],COLORS.foot,a);
  }
  return {faces,anchors};
}
export function projector(width,height,camera=DEFAULT_CAMERA){
  const scale=Math.min(width/3.5,height/3.13)*camera.zoom;
  const cy=Math.cos(camera.yaw),sy=Math.sin(camera.yaw),cp=Math.cos(camera.pitch),sp=Math.sin(camera.pitch);
  return p=>{
    const y=p[1]-1.22,x=cy*p[0]-sy*p[2],z=sy*p[0]+cy*p[2];
    return {x:width*.50+x*scale,y:height*.49-(cp*y-sp*z)*scale,depth:sp*y+cp*z};
  };
}
function shade(hex,amount){
  return '#'+[1,3,5].map(i=>Math.round(Math.min(255,Math.max(0,parseInt(hex.slice(i,i+2),16)*amount))).toString(16).padStart(2,'0')).join('');
}
export function projectedScene(width,height,pose=DEFAULT_POSE,camera=DEFAULT_CAMERA){
  const scene=makeScene(pose),project=projector(width,height,camera);
  const faces=scene.faces.map(face=>{
    const pts=face.points.map(project),p=face.points;
    const u=p[1].map((v,i)=>v-p[0][i]),v=p[2].map((v,i)=>v-p[0][i]);
    const n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]];
    const len=Math.hypot(...n)||1;
    const light=.82+.18*(n[0]*-.4+n[1]*.8+n[2]*.6)/len;
    return {points:pts,color:shade(face.color,light),depth:pts.reduce((s,p)=>s+p.depth,0)/pts.length};
  }).sort((a,b)=>a.depth-b.depth);
  const grid=[];
  for(let i=-5;i<=5;i++){const v=i*.32;grid.push([project([v,.015,-1.6]),project([v,.015,1.6])],[project([-1.6,.015,v]),project([1.6,.015,v])]);}
  return {faces,grid,anchors:scene.anchors.map(a=>({...a,point:project(a.point)})),origin:project([0,0,0])};
}
const fixed=n=>n.toFixed(2);
export function posterSVG(width=1000,height=900){
  const scene=projectedScene(width,height);
  const path=pts=>pts.map((p,i)=>`${i?'L':'M'}${fixed(p.x)} ${fixed(p.y)}`).join(' ')+'Z';
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img" aria-labelledby="biped-title biped-desc" lang="ko"><title id="biped-title">독자 제작 교육용 이족 로봇 기하 모형</title><desc id="biped-desc">상자와 원통으로 만든 두 다리 모형의 정지 이미지. 고관절, 무릎, 발목을 표시합니다. 실제 Microduck의 형상이나 검증된 치수가 아니며 동역학과 정책 재생을 포함하지 않습니다.</desc><rect width="100%" height="100%" fill="#F5F6F0"/><g stroke="#D9E3DC" stroke-width="1">${scene.grid.map(ps=>`<path d="M${fixed(ps[0].x)} ${fixed(ps[0].y)} L${fixed(ps[1].x)} ${fixed(ps[1].y)}"/>`).join('')}</g><ellipse cx="${fixed(scene.origin.x)}" cy="${fixed(scene.origin.y)}" rx="135" ry="28" fill="#143F43" opacity=".07"/><g stroke-linejoin="round">${scene.faces.map(f=>`<path d="${path(f.points)}" fill="${f.color}" stroke="${f.color}" stroke-width=".5"/>`).join('')}</g><g font-family="Pretendard,Apple SD Gothic Neo,Noto Sans KR,sans-serif" fill="#143F43"><text x="44" y="57" font-size="18" font-weight="700">ORIGINAL GEOMETRY / EDUCATIONAL ONLY</text>${scene.anchors.map(a=>`<path d="M${fixed(a.point.x-12)} ${fixed(a.point.y)} H${fixed(a.point.x-108)}" stroke="#829A90"/><text x="${fixed(a.point.x-120)}" y="${fixed(a.point.y+7)}" text-anchor="end" font-size="22">${a.label}</text>`).join('')}<text x="44" y="${height-59}" font-size="20" font-weight="700">상자 + 원통 · 임의의 비검증 치수</text><text x="44" y="${height-27}" font-size="18">실제 형상·동역학 아님 / 센서·정책 재생 없음</text></g></svg>`;
}
