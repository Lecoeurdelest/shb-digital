// lobby.jsx — LobbyRoom3D: phòng làm việc 3D (three.js) — Main họp giữa, 4 sub ngồi bàn,
// beam packet khi dispatch, click nhân vật để chọn agent. Props: {agents, focus, onSelect}
window.DEG = window.DEG || {};

const STC = { idle: 0x544e45, run: 0x5fb2c9, done: 0x82b878, warn: 0xdda94a, err: 0xe0705f };
const ROLE_COL = { planner: 0xb98cd9, credit: 0x82b878, legal: 0xdda94a, products: 0x5fb2c9, ops: 0xd97757 };
const POS = { planner: [0, 0, 2.6], credit: [-3.6, 0, -1.4], legal: [-1.4, 0, -3.2], products: [1.4, 0, -3.2], ops: [3.6, 0, -1.4] };
const NAMES = { planner: 'Main', credit: 'Tín dụng', legal: 'Pháp chế', products: 'Sản phẩm', ops: 'Vận hành' };

function makeLabel(THREE, text) {
  const c = document.createElement('canvas'); c.width = 256; c.height = 64;
  const x = c.getContext('2d');
  x.font = "700 30px 'Be Vietnam Pro',sans-serif"; x.textAlign = 'center';
  x.shadowColor = 'rgba(0,0,0,.8)'; x.shadowBlur = 8;
  x.fillStyle = '#f2efe8'; x.fillText(text, 128, 42);
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(c), transparent: true, depthWrite: false }));
  s.scale.set(1.7, 0.43, 1); return s;
}

function LobbyRoom3D({ agents, focus, onSelect }) {
  const ref = React.useRef(null);
  const live = React.useRef({ agents, focus, onSelect });
  live.current = { agents, focus, onSelect };

  React.useEffect(() => {
    const el = ref.current, THREE = window.THREE;
    if (!el || !THREE) return;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(1); // basic mode: nhẹ render
    renderer.setSize(el.clientWidth, el.clientHeight);
    renderer.shadowMap.enabled = false; // basic mode: tắt shadow — làm đẹp sau
    el.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0x1a1917, 15, 32);
    const cam = new THREE.PerspectiveCamera(40, el.clientWidth / el.clientHeight, 0.1, 100);

    scene.add(new THREE.AmbientLight(0xfff4ea, 0.55));
    const key = new THREE.DirectionalLight(0xfff0e0, 1.1); key.position.set(6, 9, 5); scene.add(key);
    const warm = new THREE.PointLight(0xd97757, 22, 12); warm.position.set(0, 3.4, 0); scene.add(warm);

    // sàn tròn + lưới
    const floor = new THREE.Mesh(new THREE.CylinderGeometry(9.5, 9.8, 0.25, 56), new THREE.MeshStandardMaterial({ color: 0x211f1d, roughness: 0.92 }));
    floor.position.y = -0.13; floor.receiveShadow = true; scene.add(floor);
    const grid = new THREE.GridHelper(17, 17, 0x3d3833, 0x2a2825); grid.position.y = 0.005; scene.add(grid);
    // thảm họp giữa
    const rug = new THREE.Mesh(new THREE.CylinderGeometry(2.6, 2.6, 0.02, 40), new THREE.MeshStandardMaterial({ color: 0x2a2420, roughness: 1 }));
    rug.position.y = 0.02; rug.receiveShadow = true; scene.add(rug);

    // bàn họp trung tâm + hologram
    const mkStd = (color, extra) => new THREE.MeshStandardMaterial({ color, roughness: 0.55, ...extra });
    const table = new THREE.Group();
    const top = new THREE.Mesh(new THREE.CylinderGeometry(1.45, 1.45, 0.12, 36), mkStd(0x3a352f));
    top.position.y = 0.92; top.castShadow = true;
    const leg = new THREE.Mesh(new THREE.CylinderGeometry(0.14, 0.3, 0.92, 14), mkStd(0x2a2825));
    leg.position.y = 0.46;
    table.add(top, leg); scene.add(table);
    const holo = new THREE.Group();
    const ring1 = new THREE.Mesh(new THREE.TorusGeometry(0.52, 0.025, 8, 48), new THREE.MeshBasicMaterial({ color: 0xd97757, transparent: true, opacity: 0.75 }));
    const ring2 = new THREE.Mesh(new THREE.TorusGeometry(0.36, 0.018, 8, 40), new THREE.MeshBasicMaterial({ color: 0xe8906f, transparent: true, opacity: 0.5 }));
    ring1.rotation.x = ring2.rotation.x = Math.PI / 2; ring2.position.y = 0.16;
    holo.add(ring1, ring2); holo.position.y = 1.55; scene.add(holo);

    // nhân vật + bàn làm việc
    const pickables = [], chars = {};
    Object.keys(POS).forEach(role => {
      const g = new THREE.Group();
      const col = ROLE_COL[role];
      if (role !== 'planner') {
        const desk = new THREE.Group();
        const dTop = new THREE.Mesh(new THREE.BoxGeometry(1.5, 0.09, 0.75), mkStd(0x38332d));
        dTop.position.y = 0.78; dTop.castShadow = true;
        const dL1 = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.78, 0.68), mkStd(0x2a2825)); dL1.position.set(-0.68, 0.39, 0);
        const dL2 = dL1.clone(); dL2.position.x = 0.68;
        const screen = new THREE.Mesh(new THREE.BoxGeometry(0.62, 0.4, 0.045), new THREE.MeshStandardMaterial({ color: 0x121110, emissive: col, emissiveIntensity: 0.35, roughness: 0.3 }));
        screen.position.set(0, 1.12, -0.16); screen.rotation.x = -0.12;
        desk.add(dTop, dL1, dL2, screen);
        desk.lookAt(0, 0, 0); // quay bàn về trung tâm
        g.add(desk);
        g.userData.screen = screen;
      }
      const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.27, 0.52, 4, 14), mkStd(col, { roughness: 0.45 }));
      body.position.y = role === 'planner' ? 0.82 : 0.72; body.castShadow = true;
      const head = new THREE.Mesh(new THREE.SphereGeometry(0.21, 18, 18), mkStd(0xe8e2d6, { roughness: 0.4 }));
      head.position.y = body.position.y + 0.62;
      const ring = new THREE.Mesh(new THREE.TorusGeometry(0.55, 0.045, 8, 44), new THREE.MeshBasicMaterial({ color: STC.idle, transparent: true, opacity: 0.85 }));
      ring.rotation.x = Math.PI / 2; ring.position.y = 0.05;
      const label = makeLabel(THREE, NAMES[role]); label.position.y = 2.15;
      const person = new THREE.Group(); person.add(body, head);
      // sub ngồi hơi lùi sau bàn, nhìn về trung tâm
      if (role !== 'planner') { person.position.z = 0.42; person.scale.setScalar(0.92); }
      g.add(person, ring, label);
      g.position.set(...POS[role]);
      if (role !== 'planner') g.lookAt(0, 0, 0);
      body.userData.role = head.userData.role = role;
      pickables.push(body, head);
      g.userData = { ...g.userData, role, body, head, ring, person };
      scene.add(g); chars[role] = g;
    });

    // beam + packet (Main → sub khi run)
    const beams = {};
    ['credit', 'legal', 'products', 'ops'].forEach(r => {
      const a = new THREE.Vector3(...POS.planner); a.y = 1.25;
      const b = new THREE.Vector3(...POS[r]); b.y = 1.05;
      const mid = a.clone().lerp(b, 0.5); mid.y = 2.1;
      const curve = new THREE.QuadraticBezierCurve3(a, mid, b);
      const tube = new THREE.Mesh(new THREE.TubeGeometry(curve, 24, 0.012, 6), new THREE.MeshBasicMaterial({ color: STC.run, transparent: true, opacity: 0.35 }));
      const packet = new THREE.Mesh(new THREE.SphereGeometry(0.06, 10, 10), new THREE.MeshBasicMaterial({ color: 0x9fdcee }));
      scene.add(tube, packet);
      beams[r] = { curve, tube, packet, phase: Math.random() };
    });

    // raycast chọn agent
    const ray = new THREE.Raycaster(), mv = new THREE.Vector2();
    const pick = e => {
      const r = el.getBoundingClientRect();
      mv.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
      ray.setFromCamera(mv, cam);
      const hit = ray.intersectObjects(pickables)[0];
      return hit ? hit.object.userData.role : null;
    };
    const onClick = e => { const r = pick(e); if (r) live.current.onSelect(r); };
    const onMove = e => { el.style.cursor = pick(e) ? 'pointer' : 'default'; };
    el.addEventListener('click', onClick);
    el.addEventListener('mousemove', onMove);

    const ro = new ResizeObserver(() => {
      renderer.setSize(el.clientWidth, el.clientHeight);
      cam.aspect = el.clientWidth / el.clientHeight; cam.updateProjectionMatrix();
    });
    ro.observe(el);

    // basic mode: camera CỐ ĐỊNH, không xoay (làm đẹp/orbit xử lý sau)
    cam.position.set(0, 6.4, 11);
    cam.lookAt(0, 0.7, 0);
    let t = 0, raf;
    const tick = () => {
      raf = requestAnimationFrame(tick);
      t += 0.016;
      const { agents, focus } = live.current;
      holo.rotation.y = t * 0.4;
      Object.entries(chars).forEach(([role, g]) => {
        const st = agents[role] || 'idle';
        const focused = focus === role;
        g.userData.ring.material.color.setHex(focused ? 0xd97757 : STC[st]);
        g.userData.ring.scale.setScalar(focused ? 1.22 : st === 'run' ? 1 + Math.sin(t * 5) * 0.08 : 1);
        g.userData.person.position.y = st === 'run' ? Math.abs(Math.sin(t * 4.2)) * 0.055 : 0;
        if (g.userData.screen) g.userData.screen.material.emissiveIntensity = st === 'run' ? 0.55 + Math.sin(t * 7) * 0.25 : st === 'idle' ? 0.08 : 0.3;
        g.userData.body.material.emissive = new THREE.Color(st === 'err' ? 0x3a1410 : 0x000000);
      });
      Object.entries(beams).forEach(([r, b]) => {
        const on = (agents[r] || 'idle') === 'run';
        b.tube.visible = b.packet.visible = on;
        if (on) b.packet.position.copy(b.curve.getPoint((t * 0.45 + b.phase) % 1));
      });
      renderer.render(scene, cam);
    };
    tick();

    return () => {
      cancelAnimationFrame(raf); ro.disconnect();
      el.removeEventListener('click', onClick); el.removeEventListener('mousemove', onMove);
      renderer.dispose(); el.removeChild(renderer.domElement);
    };
  }, []);

  return <div ref={ref} style={{ position: 'absolute', inset: 0 }} />;
}

window.DEG.lobby = { LobbyRoom3D };
const Register = () => null;
module.exports = { Register };
