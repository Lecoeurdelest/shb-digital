// team3d.jsx — đội agent 3D cho landing hero. Props: {focus, onSelect}
// Basic render: camera cố định, không shadow, pixelRatio 1.
window.DEGL = window.DEGL || {};

const ROLE = {
  planner: { col: 0xb98cd9, pos: [0, 0.5, 1.6], name: 'Main' },
  credit: { col: 0x5fb2c9, pos: [-3.1, 0, -0.9], name: 'Tín dụng' },
  legal: { col: 0xdda94a, pos: [-1.2, 0, -2.5], name: 'Pháp chế' },
  products: { col: 0x82b878, pos: [1.2, 0, -2.5], name: 'Sản phẩm' },
  ops: { col: 0xd97757, pos: [3.1, 0, -0.9], name: 'Vận hành' }
};

function label(THREE, text, color) {
  const c = document.createElement('canvas'); c.width = 256; c.height = 64;
  const x = c.getContext('2d');
  x.font = "700 28px 'Be Vietnam Pro',sans-serif"; x.textAlign = 'center';
  x.shadowColor = 'rgba(0,0,0,.9)'; x.shadowBlur = 10;
  x.fillStyle = color; x.fillText(text, 128, 42);
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(c), transparent: true, depthWrite: false }));
  s.scale.set(1.6, 0.4, 1); return s;
}

function Team3D({ focus, onSelect }) {
  const ref = React.useRef(null);
  const live = React.useRef({ focus, onSelect }); live.current = { focus, onSelect };

  React.useEffect(() => {
    const el = ref.current, THREE = window.THREE;
    if (!el || !THREE) return;
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(1);
    renderer.setSize(el.clientWidth, el.clientHeight);
    el.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    const cam = new THREE.PerspectiveCamera(38, el.clientWidth / el.clientHeight, 0.1, 60);
    cam.position.set(0, 4.6, 9.6); cam.lookAt(0, 0.7, -0.4);

    scene.add(new THREE.AmbientLight(0xfff4ea, 0.6));
    const key = new THREE.DirectionalLight(0xfff0e0, 1.05); key.position.set(5, 8, 6); scene.add(key);
    const warm = new THREE.PointLight(0xd97757, 16, 11); warm.position.set(0, 3, 0.5); scene.add(warm);

    const mkStd = (color, extra) => new THREE.MeshStandardMaterial({ color, roughness: 0.5, ...extra });
    // sàn đĩa + vòng sáng
    const disc = new THREE.Mesh(new THREE.CylinderGeometry(5.4, 5.7, 0.22, 52), mkStd(0x211f1d, { roughness: 0.95 }));
    disc.position.y = -0.12; scene.add(disc);
    const rim = new THREE.Mesh(new THREE.TorusGeometry(5.4, 0.03, 8, 72), new THREE.MeshBasicMaterial({ color: 0xd97757, transparent: true, opacity: 0.4 }));
    rim.rotation.x = Math.PI / 2; rim.position.y = 0.01; scene.add(rim);
    const grid = new THREE.GridHelper(11, 12, 0x3a3530, 0x272420); grid.position.y = 0.005; scene.add(grid);

    // podium Main
    const podium = new THREE.Mesh(new THREE.CylinderGeometry(0.85, 0.95, 0.5, 28), mkStd(0x322d28));
    podium.position.set(0, 0.25, 1.6); scene.add(podium);
    // hologram trên Main
    const holo = new THREE.Mesh(new THREE.TorusGeometry(0.4, 0.02, 8, 44), new THREE.MeshBasicMaterial({ color: 0xd97757, transparent: true, opacity: 0.7 }));
    holo.rotation.x = Math.PI / 2; holo.position.set(0, 3.05, 1.6); scene.add(holo);

    const pickables = [], chars = {};
    Object.entries(ROLE).forEach(([role, R]) => {
      const g = new THREE.Group();
      const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.3, 0.6, 4, 16), mkStd(R.col, { roughness: 0.4, emissive: R.col, emissiveIntensity: 0.08 }));
      body.position.y = 0.82;
      const head = new THREE.Mesh(new THREE.SphereGeometry(0.23, 20, 20), mkStd(0xe8e2d6, { roughness: 0.35 }));
      head.position.y = 1.5;
      const visor = new THREE.Mesh(new THREE.SphereGeometry(0.235, 20, 12, Math.PI * 1.25, Math.PI * 0.5, Math.PI * 0.32, Math.PI * 0.22), new THREE.MeshBasicMaterial({ color: R.col }));
      visor.position.y = 1.5;
      const ring = new THREE.Mesh(new THREE.TorusGeometry(0.55, 0.04, 8, 44), new THREE.MeshBasicMaterial({ color: R.col, transparent: true, opacity: 0.75 }));
      ring.rotation.x = Math.PI / 2; ring.position.y = 0.04;
      const lb = label(THREE, R.name, '#f2efe8'); lb.position.y = 2.15;
      g.add(body, head, visor, ring, lb);
      g.position.set(...R.pos);
      g.lookAt(0, R.pos[1], 5);
      body.userData.role = head.userData.role = role;
      pickables.push(body, head);
      chars[role] = { g, body, head, ring, baseY: R.pos[1] };
      scene.add(g);
    });

    // beam Main → subs
    const beams = [];
    ['credit', 'legal', 'products', 'ops'].forEach((r, i) => {
      const a = new THREE.Vector3(0, 1.7, 1.6);
      const b = new THREE.Vector3(ROLE[r].pos[0], ROLE[r].pos[1] + 1.2, ROLE[r].pos[2]);
      const mid = a.clone().lerp(b, 0.5); mid.y += 0.9;
      const curve = new THREE.QuadraticBezierCurve3(a, mid, b);
      const tube = new THREE.Mesh(new THREE.TubeGeometry(curve, 20, 0.008, 6), new THREE.MeshBasicMaterial({ color: ROLE[r].col, transparent: true, opacity: 0.22 }));
      const packet = new THREE.Mesh(new THREE.SphereGeometry(0.05, 8, 8), new THREE.MeshBasicMaterial({ color: 0xffffff }));
      scene.add(tube, packet);
      beams.push({ curve, packet, phase: i * 0.25 });
    });

    const ray = new THREE.Raycaster(), mv = new THREE.Vector2();
    const pick = e => {
      const r = el.getBoundingClientRect();
      mv.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
      ray.setFromCamera(mv, cam);
      const hit = ray.intersectObjects(pickables)[0];
      return hit ? hit.object.userData.role : null;
    };
    const onClick = e => { const r = pick(e); if (r) live.current.onSelect && live.current.onSelect(r); };
    const onMove = e => { el.style.cursor = pick(e) ? 'pointer' : 'default'; };
    el.addEventListener('click', onClick); el.addEventListener('mousemove', onMove);
    const ro = new ResizeObserver(() => { renderer.setSize(el.clientWidth, el.clientHeight); cam.aspect = el.clientWidth / el.clientHeight; cam.updateProjectionMatrix(); });
    ro.observe(el);

    let t = 0, raf;
    const tick = () => {
      raf = requestAnimationFrame(tick);
      t += 0.016;
      holo.rotation.z = t * 0.8;
      const f = live.current.focus;
      Object.entries(chars).forEach(([role, c], i) => {
        c.g.position.y = c.baseY + Math.sin(t * 1.6 + i) * 0.045;
        const focused = f === role;
        c.ring.scale.setScalar(focused ? 1.35 + Math.sin(t * 4) * 0.06 : 1);
        c.ring.material.opacity = focused ? 1 : 0.55;
        c.body.material.emissiveIntensity = focused ? 0.35 : 0.08;
      });
      beams.forEach(b => b.packet.position.copy(b.curve.getPoint((t * 0.3 + b.phase) % 1)));
      renderer.render(scene, cam);
    };
    tick();
    return () => { cancelAnimationFrame(raf); ro.disconnect(); el.removeEventListener('click', onClick); el.removeEventListener('mousemove', onMove); renderer.dispose(); el.removeChild(renderer.domElement); };
  }, []);

  return <div ref={ref} style={{ position: 'absolute', inset: 0 }} />;
}

window.DEGL.Team3D = Team3D;
module.exports = { Team3D };
