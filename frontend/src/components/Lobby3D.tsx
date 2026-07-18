// Lobby3D.tsx — chi nhánh BANK 3D (three.js) cho tab "Đội làm việc".
// 5 quầy sáng: Main giữa (phục vụ 1 user), 4 sub hai bên (chuyên gia nội bộ). Scene TĨNH,
// render-on-demand; agent đang 'run' → icon nhấp nháy phía trên (blink loop chỉ chạy khi có run).
// Props: agents (role→trạng thái) · focus · onSelect(role). Port từ design/workspace mock (D-24).
import { useEffect, useRef } from 'react';
import * as THREE from 'three';

export type LobbyStatus = 'idle' | 'run' | 'done' | 'warn' | 'err';
interface Props {
  agents: Record<string, LobbyStatus>;
  focus?: string | null;
  onSelect?: (role: string) => void;
}

const C = {
  navy: 0x1f2a78, orange: 0xf26a21, orangeLt: 0xff8a3d,
  wall: 0xfbfcfe, wall2: 0xf2f5f9, floor: 0xf3f6fb, floorLine: 0xdce1ea,
  counter: 0xfcfdff, uniform: 0x27306f, chair: 0x9aa1ad, chairLeg: 0x6b7280,
  skin: 0xecc6a6, hair: 0x2a2622, plantPot: 0xffffff, plant: 0x46a05e,
};
const ROLE: Record<string, number> = { planner: 0x2b3a8c, credit: 0x3fae6a, legal: 0xe0a13a, products: 0x38a3c4, ops: 0xf26a21 };
const STC: Record<string, number> = { idle: 0xb9c0cc, run: 0x2f8fd6, done: 0x46a05e, warn: 0xe0a13a, err: 0xe0705f };
const NAME: Record<string, string> = { planner: 'Main', credit: 'Tín dụng', legal: 'Pháp chế', products: 'Sản phẩm', ops: 'Vận hành' };
const NUM: Record<string, number> = { planner: 0, credit: 1, legal: 2, products: 3, ops: 4 };
const POS: Record<string, [number, number, number]> = {
  planner: [0, 0, -0.2], credit: [-4.5, 0, 0.9], legal: [-2.3, 0, 0.2], products: [2.3, 0, 0.2], ops: [4.5, 0, 0.9],
};

export function Lobby3D({ agents, focus, onSelect }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const live = useRef({ agents, focus, onSelect });
  live.current = { agents, focus, onSelect };
  const applyRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    // Guard: môi trường không hỗ trợ WebGL/canvas (vd jsdom khi chạy test) → bỏ qua, render div rỗng.
    try {

    const std = (color: number, o: Partial<THREE.MeshStandardMaterialParameters> = {}) =>
      new THREE.MeshStandardMaterial({ color, roughness: 0.7, metalness: 0.05, ...o });
    const roundRect = (x: CanvasRenderingContext2D, rx: number, ry: number, w: number, h: number, r: number) => {
      x.beginPath(); x.moveTo(rx + r, ry); x.arcTo(rx + w, ry, rx + w, ry + h, r); x.arcTo(rx + w, ry + h, rx, ry + h, r); x.arcTo(rx, ry + h, rx, ry, r); x.arcTo(rx, ry, rx + w, ry, r); x.closePath();
    };
    const canvasTex = (draw: (x: CanvasRenderingContext2D, w: number, h: number) => void, w = 256, h = 128) => {
      const c = document.createElement('canvas'); c.width = w; c.height = h;
      draw(c.getContext('2d')!, w, h);
      const tx = new THREE.CanvasTexture(c); tx.anisotropy = 8; return tx;
    };

    const makeBankWordmark = () => canvasTex((x, w, h) => {
      x.clearRect(0, 0, w, h);
      x.fillStyle = '#f26a21'; roundRect(x, 26, h / 2 - 30, 60, 60, 10); x.fill();
      x.strokeStyle = '#c0410f'; x.lineWidth = 7; x.lineCap = 'round';
      x.beginPath(); x.moveTo(40, h / 2 + 16); x.quadraticCurveTo(56, h / 2 - 4, 72, h / 2 + 16); x.stroke();
      x.beginPath(); x.moveTo(40, h / 2 + 2); x.quadraticCurveTo(56, h / 2 - 18, 72, h / 2 + 2); x.stroke();
      x.fillStyle = '#1f2a78'; x.font = "800 62px 'Be Vietnam Pro',sans-serif"; x.textBaseline = 'middle';
      x.fillText('BANK', 104, h / 2 - 4);
      x.fillStyle = '#6b7180'; x.font = "500 15px 'Be Vietnam Pro',sans-serif";
      x.fillText('Đối tác tin cậy, giải pháp phù hợp', 106, h / 2 + 34);
    }, 512, 180);

    const numDisc = (n: number) => canvasTex((x, w, h) => {
      x.clearRect(0, 0, w, h);
      x.fillStyle = '#1f2a78'; x.beginPath(); x.arc(w / 2, h / 2, 54, 0, 7); x.fill();
      x.fillStyle = '#fff'; x.font = "800 60px 'Be Vietnam Pro',sans-serif";
      x.textAlign = 'center'; x.textBaseline = 'middle'; x.fillText(String(n), w / 2, h / 2 + 3);
    }, 128, 128);

    const nameLabel = (text: string) => {
      const tx = canvasTex((x, w, h) => {
        x.clearRect(0, 0, w, h);
        x.font = "700 34px 'Be Vietnam Pro',sans-serif"; x.textAlign = 'center'; x.textBaseline = 'middle';
        x.fillStyle = 'rgba(31,42,120,.14)'; roundRect(x, 18, h / 2 - 30, w - 36, 60, 30); x.fill();
        x.fillStyle = '#1f2a78'; x.fillText(text, w / 2, h / 2);
      }, 256, 80);
      const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tx, transparent: true, depthWrite: false }));
      s.scale.set(1.7, 0.53, 1); return s;
    };

    const person = (role: string) => {
      const g = new THREE.Group(); const accent = ROLE[role];
      const seat = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.28, 0.1, 20), std(0x2b3040)); seat.position.y = 0.5; seat.castShadow = true;
      const back = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.5, 0.08), std(0x2b3040)); back.position.set(0, 0.78, -0.26);
      const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.26, 0.5, 6, 16), std(C.uniform, { roughness: 0.6 })); body.position.y = 1.02; body.castShadow = true;
      const scarf = new THREE.Mesh(new THREE.TorusGeometry(0.2, 0.055, 10, 24), std(accent, { roughness: 0.5, metalness: 0.15 })); scarf.rotation.x = Math.PI / 2; scarf.position.y = 1.24;
      const head = new THREE.Mesh(new THREE.SphereGeometry(0.2, 24, 24), std(C.skin, { roughness: 0.55 })); head.position.y = 1.55; head.castShadow = true;
      const cap = new THREE.Mesh(new THREE.SphereGeometry(0.212, 22, 22, 0, 6.3, 0, Math.PI * 0.5), std(C.hair, { roughness: 0.85 })); cap.position.y = 1.585;
      const bun = new THREE.Mesh(new THREE.SphereGeometry(0.1, 14, 14), std(C.hair, { roughness: 0.85 })); bun.position.set(0, 1.52, -0.19);
      const eyeG = new THREE.SphereGeometry(0.022, 8, 8); const eyeM = std(0x2a2622, { roughness: 0.4 });
      const eL = new THREE.Mesh(eyeG, eyeM); const eR = new THREE.Mesh(eyeG, eyeM); eL.position.set(-0.07, 1.56, 0.185); eR.position.set(0.07, 1.56, 0.185);
      const ring = new THREE.Mesh(new THREE.TorusGeometry(0.5, 0.04, 10, 40), new THREE.MeshBasicMaterial({ color: STC.idle, transparent: true, opacity: 0.9 })); ring.rotation.x = Math.PI / 2; ring.position.y = 0.06;
      body.userData.role = head.userData.role = role;
      g.add(seat, back, body, scarf, head, cap, bun, eL, eR, ring);
      g.userData = { role, body, head, ring };
      return g;
    };

    const customer = (i: number) => {
      const g = new THREE.Group();
      const shirts = [0xffffff, 0xf3ece0, 0xcf8f9c, 0xdbe0e8, 0xe8d9c0]; const col = shirts[i % shirts.length];
      const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.25, 0.44, 6, 14), std(col, { roughness: 0.78 })); body.position.y = 0.96; body.castShadow = true;
      const head = new THREE.Mesh(new THREE.SphereGeometry(0.19, 20, 20), std(C.skin, { roughness: 0.55 })); head.position.y = 1.44;
      const hair = new THREE.Mesh(new THREE.SphereGeometry(0.205, 20, 20, 0, 6.3, 0, Math.PI * 0.72), std(C.hair, { roughness: 0.85 })); hair.position.set(0, 1.47, 0.03); hair.rotation.x = 0.35;
      const pony = new THREE.Mesh(new THREE.SphereGeometry(0.09, 12, 12), std(C.hair)); pony.position.set(0, 1.34, 0.16); pony.scale.set(1, 1.5, 1);
      g.add(body, head, hair, pony); return g;
    };

    const tubChair = () => {
      const g = new THREE.Group();
      const seat = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.26, 0.16, 20), std(C.chair, { roughness: 0.85 })); seat.position.y = 0.5; seat.castShadow = true;
      const back = new THREE.Mesh(new THREE.CylinderGeometry(0.32, 0.32, 0.42, 20, 1, true, Math.PI * 0.15, Math.PI * 1.05), std(C.chair, { roughness: 0.85, side: THREE.DoubleSide })); back.position.y = 0.72;
      const legG = new THREE.Group();
      for (let i = 0; i < 4; i++) { const l = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 0.44, 8), std(C.chairLeg)); const a = i * Math.PI / 2 + Math.PI / 4; l.position.set(Math.cos(a) * 0.2, 0.22, Math.sin(a) * 0.2); legG.add(l); }
      g.add(seat, back, legG); return g;
    };

    const plant = () => {
      const g = new THREE.Group();
      const pot = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.12, 0.28, 16), std(C.plantPot, { roughness: 0.4 })); pot.position.y = 0.14; pot.castShadow = true;
      for (let i = 0; i < 5; i++) { const leaf = new THREE.Mesh(new THREE.SphereGeometry(0.16, 10, 10), std(C.plant, { roughness: 0.8 })); leaf.position.set((i - 2) * 0.06, 0.42 + (i % 3) * 0.08, (i % 2 - 0.5) * 0.14); leaf.scale.y = 1.5; g.add(leaf); }
      g.add(pot); return g;
    };

    const dotMap = canvasTex((x, w, h) => { const gr = x.createRadialGradient(w / 2, h / 2, 1, w / 2, h / 2, w / 2); gr.addColorStop(0, '#fff'); gr.addColorStop(0.45, 'rgba(255,255,255,0.95)'); gr.addColorStop(1, 'rgba(255,255,255,0)'); x.fillStyle = gr; x.fillRect(0, 0, w, h); }, 64, 64);

    const station = (role: string) => {
      const g = new THREE.Group(); const accent = ROLE[role]; const isMain = role === 'planner'; const deskW = isMain ? 2.0 : 1.7;
      const desk = new THREE.Mesh(new THREE.BoxGeometry(deskW, 0.9, 0.85), std(C.counter, { roughness: 0.35, metalness: 0.1 })); desk.position.y = 0.45; desk.castShadow = desk.receiveShadow = true;
      const top = new THREE.Mesh(new THREE.BoxGeometry(deskW + 0.14, 0.07, 1.0), std(0xffffff, { roughness: 0.25 })); top.position.y = 0.93; top.castShadow = true;
      const stripe = new THREE.Mesh(new THREE.BoxGeometry(deskW, 0.09, 0.86), std(C.orange, { roughness: 0.5 })); stripe.position.y = 0.12;
      g.add(desk, top, stripe);
      const scr = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.32, 0.03), new THREE.MeshStandardMaterial({ color: 0x0f1220, emissive: accent, emissiveIntensity: 0.25, roughness: 0.3 })); scr.position.set(isMain ? 0 : -0.35, 1.22, -0.18);
      const foot = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.11, 0.06, 12), std(0x9aa1ad)); foot.position.set(isMain ? 0 : -0.35, 1.02, -0.18);
      g.userData.screen = scr; g.add(scr, foot);
      if (!isMain) {
        const glass = new THREE.Mesh(new THREE.BoxGeometry(deskW + 0.1, 0.5, 0.03), new THREE.MeshStandardMaterial({ color: C.orange, transparent: true, opacity: 0.22, roughness: 0.1, metalness: 0.2 })); glass.position.set(0, 1.2, 0.44); g.add(glass);
        const frame = new THREE.Mesh(new THREE.BoxGeometry(deskW + 0.14, 0.04, 0.05), std(C.orange)); frame.position.set(0, 1.46, 0.44); g.add(frame);
        const disc = new THREE.Sprite(new THREE.SpriteMaterial({ map: numDisc(NUM[role]), transparent: true, depthWrite: false })); disc.scale.set(0.42, 0.42, 1); disc.position.set(deskW / 2 - 0.1, 1.28, 0.46); g.add(disc);
        const tray = new THREE.Mesh(new THREE.BoxGeometry(0.34, 0.05, 0.24), std(0xdfe3ec)); tray.position.set(0.5, 0.98, 0.1); g.add(tray);
      }
      const p = person(role); p.position.set(0, 0, -0.55); g.add(p);
      g.userData.person = p; g.userData.ring = p.userData.ring; g.userData.body = p.userData.body; g.userData.head = p.userData.head;
      const lbl = nameLabel(NAME[role]); lbl.position.set(0, 2.15, 0); g.add(lbl);
      if (isMain) { const chair = tubChair(); chair.position.set(0, 0, 1.85); g.add(chair); const cust = customer(0); cust.position.set(0, 0, 1.7); g.add(cust); }
      const icon = new THREE.Sprite(new THREE.SpriteMaterial({ map: dotMap, transparent: true, depthWrite: false, opacity: 0 }));
      icon.scale.set(0.36, 0.36, 1); icon.position.set(0, 2.55, 0); icon.visible = false; g.add(icon); g.userData.statusIcon = icon;
      return g;
    };

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(el.clientWidth, el.clientHeight);
    renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.LinearToneMapping; renderer.toneMappingExposure = 1.18;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    el.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf4f7fc);
    scene.fog = new THREE.Fog(0xf4f7fc, 28, 55);
    const cam = new THREE.PerspectiveCamera(43, el.clientWidth / el.clientHeight, 0.1, 100);

    scene.add(new THREE.AmbientLight(0xffffff, 0.78));
    scene.add(new THREE.HemisphereLight(0xffffff, 0xe4e8f0, 1.0));
    const key = new THREE.DirectionalLight(0xfff6ec, 1.15); key.position.set(7, 12, 8);
    key.castShadow = true; key.shadow.mapSize.set(2048, 2048);
    key.shadow.camera.near = 1; key.shadow.camera.far = 45;
    key.shadow.camera.left = -16; key.shadow.camera.right = 16; key.shadow.camera.top = 16; key.shadow.camera.bottom = -16;
    key.shadow.bias = -0.0004; scene.add(key);
    const fill = new THREE.DirectionalLight(0xdfe6ff, 0.35); fill.position.set(-8, 6, 4); scene.add(fill);

    const floor = new THREE.Mesh(new THREE.PlaneGeometry(60, 60), std(C.floor, { roughness: 0.38, metalness: 0.14 })); floor.rotation.x = -Math.PI / 2; floor.receiveShadow = true; scene.add(floor);
    const grid = new THREE.GridHelper(60, 30, C.floorLine, C.floorLine); (grid.material as THREE.Material).opacity = 0.35; (grid.material as THREE.Material).transparent = true; grid.position.y = 0.002; scene.add(grid);

    const wall = new THREE.Mesh(new THREE.PlaneGeometry(40, 12), std(C.wall, { roughness: 0.9 })); wall.position.set(0, 6, -7); wall.receiveShadow = true; scene.add(wall);
    const wallL = new THREE.Mesh(new THREE.PlaneGeometry(20, 12), std(C.wall2, { roughness: 0.9 })); wallL.position.set(-20, 6, 3); wallL.rotation.y = Math.PI / 2; scene.add(wallL);
    const wallR = wallL.clone(); wallR.position.x = 20; wallR.rotation.y = -Math.PI / 2; scene.add(wallR);
    [-11.5, 11.5].forEach((px) => {
      const fr = new THREE.Mesh(new THREE.BoxGeometry(4.1, 7.2, 0.1), std(0xeaedf2)); fr.position.set(px, 4.6, -6.97); scene.add(fr);
      const win = new THREE.Mesh(new THREE.PlaneGeometry(3.6, 6.6), new THREE.MeshStandardMaterial({ color: 0xdcefff, emissive: 0xd2e8ff, emissiveIntensity: 0.4, roughness: 0.15, metalness: 0.1 })); win.position.set(px, 4.6, -6.9); scene.add(win);
      const mull = new THREE.Mesh(new THREE.BoxGeometry(0.06, 6.6, 0.02), std(0xeaedf2)); mull.position.set(px, 4.6, -6.88); scene.add(mull);
    });
    const wm = new THREE.Mesh(new THREE.PlaneGeometry(6.8, 2.4), new THREE.MeshBasicMaterial({ map: makeBankWordmark(), transparent: true })); wm.position.set(0, 4.75, -6.94); scene.add(wm);
    const bar = new THREE.Mesh(new THREE.BoxGeometry(34, 0.34, 0.12), new THREE.MeshStandardMaterial({ map: canvasTex((x, w, h) => { const g = x.createLinearGradient(0, 0, w, 0); g.addColorStop(0, '#f26a21'); g.addColorStop(0.55, '#f26a21'); g.addColorStop(1, '#1f2a78'); x.fillStyle = g; x.fillRect(0, 0, w, h); }, 512, 32), roughness: 0.5 })); bar.position.set(0, 3.35, -6.9); scene.add(bar);
    [-7.5, -6.4, 6.4, 7.5].forEach((px) => { const f = new THREE.Mesh(new THREE.BoxGeometry(0.66, 0.86, 0.05), std(0xf3d38a, { metalness: 0.3, roughness: 0.4 })); f.position.set(px, 4.7, -6.88); scene.add(f); const mat = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.66, 0.02), std(0xffffff)); mat.position.set(px, 4.7, -6.85); scene.add(mat); });
    for (let i = -2; i <= 2; i++) { const p = new THREE.Mesh(new THREE.BoxGeometry(3.4, 0.1, 1.2), new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0xffffff, emissiveIntensity: 0.5 })); p.position.set(i * 4.2, 7.4, -1); scene.add(p); }

    const pickables: THREE.Object3D[] = [];
    const chars: Record<string, THREE.Group> = {};
    Object.keys(POS).forEach((role) => {
      const g = station(role); g.position.set(...POS[role]);
      if (role !== 'planner') g.rotation.y = POS[role][0] < 0 ? 0.28 : -0.28;
      scene.add(g); chars[role] = g;
      pickables.push(g.userData.body, g.userData.head);
    });
    const p1 = plant(); p1.position.set(-6.5, 0, -2); scene.add(p1);
    const p2 = plant(); p2.position.set(6.5, 0, -2); scene.add(p2);
    const wc = tubChair(); wc.position.set(-6.8, 0, 4); scene.add(wc);
    const wc2 = tubChair(); wc2.position.set(6.8, 0, 4); scene.add(wc2);

    const beams: Record<string, { curve: THREE.QuadraticBezierCurve3; tube: THREE.Mesh; packet: THREE.Mesh }> = {};
    ['credit', 'legal', 'products', 'ops'].forEach((r) => {
      const a = new THREE.Vector3(...POS.planner); a.y = 1.5;
      const b = new THREE.Vector3(...POS[r]); b.y = 1.3;
      const mid = a.clone().lerp(b, 0.5); mid.y = 2.6;
      const curve = new THREE.QuadraticBezierCurve3(a, mid, b);
      const tube = new THREE.Mesh(new THREE.TubeGeometry(curve, 24, 0.012, 6), new THREE.MeshBasicMaterial({ color: C.orange, transparent: true, opacity: 0.4 }));
      const packet = new THREE.Mesh(new THREE.SphereGeometry(0.06, 10, 10), new THREE.MeshBasicMaterial({ color: C.orangeLt }));
      scene.add(tube, packet); beams[r] = { curve, tube, packet };
    });

    const ray = new THREE.Raycaster(); const mv = new THREE.Vector2();
    const pick = (e: MouseEvent): string | null => {
      const r = el.getBoundingClientRect();
      mv.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
      ray.setFromCamera(mv, cam);
      const hit = ray.intersectObjects(pickables)[0];
      return hit ? hit.object.userData.role : null;
    };
    const onClick = (e: MouseEvent) => { const r = pick(e); if (r && live.current.onSelect) live.current.onSelect(r); };
    const onMove = (e: MouseEvent) => { el.style.cursor = pick(e) ? 'pointer' : 'default'; };
    el.addEventListener('click', onClick); el.addEventListener('mousemove', onMove);

    cam.position.set(0, 3.2, 10.0); cam.lookAt(0, 1.9, -1.8);

    let blinkRaf: number | null = null;
    const applyState = () => {
      const { agents: ag, focus: foc } = live.current;
      let anyRun = false;
      Object.entries(chars).forEach(([role, g]) => {
        const st: LobbyStatus = (ag && ag[role]) || 'idle'; const isFoc = foc === role;
        g.userData.ring.material.color.setHex(isFoc ? C.orange : STC[st]);
        g.userData.ring.scale.setScalar(isFoc ? 1.15 : 1);
        if (g.userData.screen) g.userData.screen.material.emissiveIntensity = st === 'run' ? 0.5 : st === 'idle' ? 0.12 : 0.3;
        const ic = g.userData.statusIcon;
        if (st === 'idle') { ic.visible = false; ic.userData.blink = false; }
        else { ic.visible = true; ic.material.color.setHex(STC[st]); ic.userData.blink = st === 'run'; if (st === 'run') anyRun = true; else ic.material.opacity = 0.95; }
      });
      Object.entries(beams).forEach(([r, b]) => { const on = ((ag && ag[r]) || 'idle') === 'run'; b.tube.visible = on; b.packet.visible = on; if (on) b.packet.position.copy(b.curve.getPoint(0.5)); });
      renderer.render(scene, cam);
      if (anyRun && blinkRaf === null) blink();
      else if (!anyRun && blinkRaf !== null) { cancelAnimationFrame(blinkRaf); blinkRaf = null; }
    };
    const blink = () => {
      const o = 0.28 + Math.abs(Math.sin(performance.now() * 0.005)) * 0.72;
      Object.values(chars).forEach((g) => { const ic = g.userData.statusIcon; if (ic.userData.blink) ic.material.opacity = o; });
      renderer.render(scene, cam);
      blinkRaf = requestAnimationFrame(blink);
    };
    applyRef.current = applyState;

    const ro = new ResizeObserver(() => {
      if (!el.clientWidth || !el.clientHeight) return;
      renderer.setSize(el.clientWidth, el.clientHeight); cam.aspect = el.clientWidth / el.clientHeight; cam.updateProjectionMatrix(); applyState();
    });
    ro.observe(el);
    applyState();

    return () => {
      if (blinkRaf !== null) cancelAnimationFrame(blinkRaf);
      ro.disconnect(); applyRef.current = null;
      el.removeEventListener('click', onClick); el.removeEventListener('mousemove', onMove);
      renderer.dispose(); if (renderer.domElement.parentNode === el) el.removeChild(renderer.domElement);
    };
    } catch { return undefined; } // WebGL/canvas không khả dụng → không dựng scene
  }, []);

  useEffect(() => { if (applyRef.current) applyRef.current(); }, [agents, focus]);

  return <div ref={ref} className="lobby3d" style={{ position: 'relative', width: '100%', height: 'clamp(280px, 42vh, 460px)' }} />;
}
