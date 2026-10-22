import * as THREE from './vendor/three.module.min.js';

const INTRO_DURATION_MS=5000;
const overlay=document.getElementById('hex-loader');
const canvas=document.getElementById('loader-canvas');
const reduced=window.matchMedia('(prefers-reduced-motion: reduce)');
let renderer,frame,finished=false,timeout;

function startIntro(){
  if(!overlay||reduced.matches)return;
  try{if(sessionStorage.getItem('hex-intro-v7'))return;}catch{}
  try{
    renderer=new THREE.WebGLRenderer({canvas,alpha:true,antialias:true,powerPreference:'low-power'});
    renderer.setPixelRatio(Math.min(devicePixelRatio,1.7));
    renderer.shadowMap.enabled=true;
    renderer.shadowMap.type=THREE.PCFSoftShadowMap;
    renderer.toneMapping=THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure=1.1;
    const scene=new THREE.Scene();
    const camera=new THREE.PerspectiveCamera(37,1,.1,40);
    scene.add(new THREE.HemisphereLight(0xb0c5e2,0x0d1421,1.7));
    const key=new THREE.DirectionalLight(0xe6f5ff,3.8);
    key.position.set(-3,6,4);key.castShadow=true;
    key.shadow.mapSize.set(1024,1024);
    key.shadow.camera.left=-4;key.shadow.camera.right=4;
    key.shadow.camera.top=5;key.shadow.camera.bottom=-3;
    key.shadow.normalBias=.03;key.shadow.bias=-.0003;scene.add(key);
    const rim=new THREE.PointLight(0x5484bc,9,12);rim.position.set(3,2,-3);scene.add(rim);
    const fill=new THREE.PointLight(0x8daecb,5,10);fill.position.set(-3,1,2);scene.add(fill);

    // Thick, beveled cross with different front and side materials.
    const outline=[[-.26,1],[.26,1],[.26,.26],[1,.26],[1,-.26],[.26,-.26],[.26,-1],[-.26,-1],[-.26,-.26],[-1,-.26],[-1,.26],[-.26,.26]];
    const shape=new THREE.Shape();outline.forEach(([x,y],i)=>i?shape.lineTo(x,y):shape.moveTo(x,y));shape.closePath();
    const geometry=new THREE.ExtrudeGeometry(shape,{depth:.58,bevelEnabled:true,bevelThickness:.09,bevelSize:.085,bevelSegments:4,steps:1});
    geometry.translate(0,0,-.29);geometry.computeVertexNormals();
    const cross=new THREE.Mesh(geometry,[
      new THREE.MeshPhysicalMaterial({color:0x86a3cc,roughness:.48,metalness:.25,clearcoat:.15}),
      new THREE.MeshPhysicalMaterial({color:0x24456e,roughness:.4,metalness:.4,clearcoat:.15})
    ]);
    cross.castShadow=true;cross.receiveShadow=true;cross.position.y=1.55;scene.add(cross);

    const pedestal=new THREE.Mesh(new THREE.CylinderGeometry(2.5,2.6,.16,80),new THREE.MeshStandardMaterial({color:0x131d2b,metalness:.15,roughness:.8}));
    pedestal.position.y=-.23;pedestal.receiveShadow=true;scene.add(pedestal);
    const floor=new THREE.Mesh(new THREE.PlaneGeometry(70,70),new THREE.ShadowMaterial({color:0x030a15,opacity:.38}));
    floor.rotation.x=-Math.PI/2;floor.position.y=-.33;floor.receiveShadow=true;scene.add(floor);
    const edge=new THREE.Mesh(new THREE.TorusGeometry(2.51,.012,5,90),new THREE.MeshBasicMaterial({color:0x31435c}));
    edge.rotation.x=Math.PI/2;edge.position.y=-.14;scene.add(edge);

    const orbit=new THREE.Group();orbit.position.y=1.3;scene.add(orbit);
    const hoop=new THREE.Mesh(new THREE.TorusGeometry(1.84,.024,10,80),new THREE.MeshStandardMaterial({color:0x385c8a,metalness:.4,roughness:.5}));
    hoop.rotation.x=Math.PI/2;orbit.add(hoop);
    const nodes=[];
    for(let i=0;i<3;i++){
      const node=new THREE.Mesh(new THREE.BoxGeometry(.2,.2,.2),new THREE.MeshPhysicalMaterial({color:0x54769e,roughness:.5,metalness:.15,clearcoat:.1}));
      node.castShadow=true;orbit.add(node);nodes.push(node);
    }
    const resize=()=>{
      const {width,height}=canvas.getBoundingClientRect();
      renderer.setSize(width,height,false);camera.aspect=width/height;camera.updateProjectionMatrix();
    };
    overlay.hidden=false;document.body.setAttribute('aria-busy','true');resize();
    const observer=new ResizeObserver(resize);observer.observe(canvas);
    try{sessionStorage.setItem('hex-intro-v7','1');}catch{}
    let started;
    const finish=()=>{
      if(finished)return;finished=true;cancelAnimationFrame(frame);clearTimeout(timeout);observer.disconnect();
      overlay.classList.add('leaving');document.body.removeAttribute('aria-busy');
      window.removeEventListener('keydown',escape);
      setTimeout(()=>{overlay.hidden=true;scene.traverse(object=>{object.geometry?.dispose();const materials=Array.isArray(object.material)?object.material:[object.material];materials.filter(Boolean).forEach(material=>material.dispose());});renderer.dispose();},270);
    };
    const escape=event=>{if(event.key==='Escape')finish();};
    document.getElementById('skip-loader').onclick=finish;window.addEventListener('keydown',escape);
    const draw=seconds=>{
      const angle=.58+seconds*.12;
      camera.position.set(Math.sin(angle)*7.1,3.4,Math.cos(angle)*7.1);camera.lookAt(0,1,0);
      cross.rotation.set(.08+Math.sin(seconds)*.08,-.45+seconds*.3,.08);
      cross.position.y=1.55+Math.sin(seconds*1.8)*.11;
      orbit.rotation.set(.18,seconds*.2,-.24);
      nodes.forEach((node,i)=>{
        const phase=i*Math.PI*2/3;
        node.position.set(Math.cos(phase)*1.84,Math.sin(seconds*2+i)*.18,Math.sin(phase)*1.84);
        node.rotation.set(seconds*.2+i,seconds*.25,i*.3);
      });
      renderer.render(scene,camera);
    };
    const animate=now=>{
      if(finished)return;draw((now-started)/1000);
      if(now-started>=INTRO_DURATION_MS){finish();return;}
      frame=requestAnimationFrame(animate);
    };
    draw(0);started=performance.now();timeout=setTimeout(finish,INTRO_DURATION_MS);frame=requestAnimationFrame(animate);
    window.addEventListener('pagehide',finish,{once:true});
  }catch{overlay.hidden=true;document.body.removeAttribute('aria-busy');renderer?.dispose();}
}
startIntro();
