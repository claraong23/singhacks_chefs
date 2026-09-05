import { useEffect, useRef, useState } from 'react'
import * as THREE from 'three'

/** Twenty client clusters on a ring resolving out of a scattered cloud, plus a
 *  twenty-first core — the single next action — that lands last and draws
 *  spokes back to every cluster.
 *
 *  The whole morph happens in the vertex shader off one 0–1 progress uniform,
 *  driven by an auto-loop. The canvas fills its parent, and the ring is centred
 *  in it, so wherever the parent sits on the page is where the ring sits. */

const CLUSTERS = 20
const PER_CLUSTER = 280
const CORE_POINTS = 420
const COUNT = CLUSTERS * PER_CLUSTER + CORE_POINTS

const RING_RADIUS = 3.5
const SCATTER = new THREE.Vector3(2.7, 1.5, 2.7) // half-extents: 5.4 x 3.0 x 5.4

// Auto-loop, in seconds.
const HOLD_SCATTERED = 1.1
const RESOLVE = 2.7
const HOLD_RESOLVED = 3.2
const RETURN = 1.9
const LOOP = HOLD_SCATTERED + RESOLVE + HOLD_RESOLVED + RETURN

const COLD = new THREE.Color('#59677e')
const BONE = new THREE.Color('#e7dfd2')
const BRASS = new THREE.Color('#b98a3c')

/** Roughly normal, bounded to about ±1 — enough of a bell for a cloud. */
function gauss(): number {
  return ((Math.random() + Math.random() + Math.random()) / 3 - 0.5) * 2
}

function ease(x: number): number {
  return x * x * (3 - 2 * x)
}

const VERTEX = /* glsl */ `
attribute vec3 aScatter;
attribute vec3 aTarget;
attribute float aRand;
attribute float aKind;

uniform float uProgress;
uniform float uTime;
uniform float uPixelRatio;
uniform float uSize;

varying float vD;
varying float vKind;

void main() {
  // The aRand offset staggers arrival, so the collapse ripples across the
  // field instead of every point snapping home on the same frame.
  float t = clamp((uProgress - aRand * 0.34) / 0.66, 0.0, 1.0);
  float d = smoothstep(0.0, 1.0, t);

  vec3 pos = mix(aScatter, aTarget, d);

  // Scattered points wander; resolved points hold still.
  float loose = 1.0 - d;
  pos.x += sin(uTime * 0.41 + aRand * 22.0) * 0.30 * loose;
  pos.y += cos(uTime * 0.34 + aRand * 17.0) * 0.22 * loose;
  pos.z += sin(uTime * 0.28 + aRand * 31.0) * 0.30 * loose;

  // Faint breathing once resolved, so the ring is never quite inert.
  pos *= 1.0 + sin(uTime * 0.6 + aRand * 6.2831) * 0.007 * d;

  vec4 mv = modelViewMatrix * vec4(pos, 1.0);
  gl_Position = projectionMatrix * mv;
  gl_PointSize = uSize * uPixelRatio * (58.0 / -mv.z) * (1.0 + aKind * 0.55);

  vD = d;
  vKind = aKind;
}
`

// No precision qualifier here: three.js prepends one, and declaring mediump
// while the vertex shader defaults to highp makes uProgress two different
// precisions and the program fails to link.
const FRAGMENT = /* glsl */ `
uniform float uProgress;
uniform float uDim;
uniform vec3 uCold;
uniform vec3 uBone;
uniform vec3 uBrass;

varying float vD;
varying float vKind;

void main() {
  vec2 c = gl_PointCoord - 0.5;
  float r = length(c);
  if (r > 0.5) discard;
  float falloff = smoothstep(0.5, 0.0, r);

  vec3 col = mix(uCold, uBone, uProgress);
  float alpha = falloff * (0.52 + 0.36 * vD);

  if (vKind > 0.5) {
    // The action core only exists once it has resolved.
    col = uBrass;
    alpha = falloff * vD * vD;
  }

  gl_FragColor = vec4(col, alpha * uDim);
}
`

export function HeroField() {
  const hostRef = useRef<HTMLDivElement | null>(null)
  const [lost, setLost] = useState(false)

  useEffect(() => {
    const host = hostRef.current
    if (!host) return

    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches

    let renderer: THREE.WebGLRenderer
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    } catch {
      setLost(true)
      return
    }

    const dpr = Math.min(window.devicePixelRatio || 1, 1.5)
    renderer.setPixelRatio(dpr)
    renderer.setSize(host.clientWidth, host.clientHeight)
    renderer.setClearColor(0x000000, 0)
    host.appendChild(renderer.domElement)

    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(50, host.clientWidth / host.clientHeight, 0.1, 100)
    camera.position.set(0, 0, 10)

    const group = new THREE.Group()
    // The copy block is wider than it is tall, so the ring is squashed very
    // slightly to match its proportions — near enough a circle, but it clears
    // the nav above and the stats strip below.
    const FLATTEN = 0.82
    group.scale.set(1, FLATTEN, 1)
    scene.add(group)

    // ── Geometry ───────────────────────────────────────────────────────────
    const scatter = new Float32Array(COUNT * 3)
    const target = new Float32Array(COUNT * 3)
    const rand = new Float32Array(COUNT)
    const kind = new Float32Array(COUNT)
    const centres: THREE.Vector3[] = []

    let n = 0
    for (let c = 0; c < CLUSTERS; c += 1) {
      const angle = (c / CLUSTERS) * Math.PI * 2
      // Radius wobble and depth jitter so it reads as an uneven book, not a dial.
      const radius = RING_RADIUS * (0.85 + Math.random() * 0.3)
      const z = (Math.random() - 0.5) * 0.72
      // Spread stands in for position size.
      const spread = 0.16 + Math.random() * 0.24
      // The ring sits in the XY plane, facing the camera, so it always reads as
      // a circle the way it does in the reference clip.
      const centre = new THREE.Vector3(Math.cos(angle) * radius, Math.sin(angle) * radius, z)
      centres.push(centre)

      for (let p = 0; p < PER_CLUSTER; p += 1, n += 1) {
        scatter[n * 3] = gauss() * SCATTER.x
        scatter[n * 3 + 1] = gauss() * SCATTER.y
        scatter[n * 3 + 2] = gauss() * SCATTER.z
        target[n * 3] = centre.x + gauss() * spread
        target[n * 3 + 1] = centre.y + gauss() * spread
        target[n * 3 + 2] = centre.z + gauss() * spread
        rand[n] = Math.random() * 0.72
        kind[n] = 0
      }
    }

    for (let p = 0; p < CORE_POINTS; p += 1, n += 1) {
      scatter[n * 3] = gauss() * SCATTER.x
      scatter[n * 3 + 1] = gauss() * SCATTER.y
      scatter[n * 3 + 2] = gauss() * SCATTER.z
      target[n * 3] = gauss() * 0.13
      target[n * 3 + 1] = gauss() * 0.13
      target[n * 3 + 2] = gauss() * 0.13
      // High aRand: the action lands last, after the book has settled.
      rand[n] = 0.72 + Math.random() * 0.28
      kind[n] = 1
    }

    const geometry = new THREE.BufferGeometry()
    geometry.setAttribute('position', new THREE.BufferAttribute(scatter.slice(), 3))
    geometry.setAttribute('aScatter', new THREE.BufferAttribute(scatter, 3))
    geometry.setAttribute('aTarget', new THREE.BufferAttribute(target, 3))
    geometry.setAttribute('aRand', new THREE.BufferAttribute(rand, 1))
    geometry.setAttribute('aKind', new THREE.BufferAttribute(kind, 1))
    geometry.boundingSphere = new THREE.Sphere(new THREE.Vector3(), 8)

    const uniforms = {
      uProgress: { value: reduced ? 1 : 0 },
      uTime: { value: 0 },
      uPixelRatio: { value: dpr },
      // Small and bright: the reference reads as fine silver speckle, not blobs.
      uSize: { value: 0.82 },
      uDim: { value: 1.0 },
      uCold: { value: COLD },
      uBone: { value: BONE },
      uBrass: { value: BRASS },
    }

    const material = new THREE.ShaderMaterial({
      uniforms,
      vertexShader: VERTEX,
      fragmentShader: FRAGMENT,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    })

    group.add(new THREE.Points(geometry, material))

    // ── The warm bloom around the action core ──────────────────────────────
    // In the reference this haze is what makes the centre read as the one warm
    // thing on screen; the 420 core points alone are far too small for it.
    const bloomCanvas = document.createElement('canvas')
    bloomCanvas.width = 256
    bloomCanvas.height = 256
    const ctx = bloomCanvas.getContext('2d')
    if (ctx) {
      // A hot white-gold centre falling away fast into a wide amber haze —
      // the shape of the core in 05-gold-core-collapse.
      const g = ctx.createRadialGradient(128, 128, 0, 128, 128, 128)
      g.addColorStop(0, 'rgba(255, 246, 226, 1)')
      g.addColorStop(0.035, 'rgba(255, 219, 156, 0.92)')
      g.addColorStop(0.1, 'rgba(226, 160, 78, 0.45)')
      g.addColorStop(0.28, 'rgba(176, 112, 46, 0.15)')
      g.addColorStop(0.6, 'rgba(120, 74, 30, 0.04)')
      g.addColorStop(1, 'rgba(0, 0, 0, 0)')
      ctx.fillStyle = g
      ctx.fillRect(0, 0, 256, 256)
    }
    const bloomTexture = new THREE.CanvasTexture(bloomCanvas)
    const bloomMaterial = new THREE.SpriteMaterial({
      map: bloomTexture,
      transparent: true,
      depthWrite: false,
      opacity: 0,
      blending: THREE.AdditiveBlending,
    })
    const bloom = new THREE.Sprite(bloomMaterial)
    // Counter the group's vertical squash so the core stays round.
    bloom.scale.set(4.6, 4.6 / FLATTEN, 1)
    group.add(bloom)

    // ── Spokes: each cluster centre back to the action at the origin ───────
    const spokes = new Float32Array(CLUSTERS * 6)
    centres.forEach((centre, i) => {
      spokes[i * 6] = centre.x
      spokes[i * 6 + 1] = centre.y
      spokes[i * 6 + 2] = centre.z
      spokes[i * 6 + 3] = 0
      spokes[i * 6 + 4] = 0
      spokes[i * 6 + 5] = 0
    })
    const spokeGeometry = new THREE.BufferGeometry()
    spokeGeometry.setAttribute('position', new THREE.BufferAttribute(spokes, 3))
    const spokeMaterial = new THREE.LineBasicMaterial({
      color: BRASS,
      transparent: true,
      opacity: 0,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    })
    group.add(new THREE.LineSegments(spokeGeometry, spokeMaterial))

    // ── Drag ───────────────────────────────────────────────────────────────
    let velocity = 0
    let dragging = false
    let lastX = 0
    let lastY = 0

    const canvas = renderer.domElement
    const onDown = (event: PointerEvent) => {
      dragging = true
      lastX = event.clientX
      lastY = event.clientY
      canvas.setPointerCapture(event.pointerId)
    }
    const onMove = (event: PointerEvent) => {
      if (!dragging) return
      // Horizontal drag spins the ring in its own plane, so it stays circular.
      velocity += (event.clientX - lastX) * 0.0009
      group.rotation.x = THREE.MathUtils.clamp(
        group.rotation.x + (event.clientY - lastY) * 0.0016,
        -0.35,
        0.85,
      )
      lastX = event.clientX
      lastY = event.clientY
    }
    const onUp = (event: PointerEvent) => {
      dragging = false
      if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId)
    }
    canvas.addEventListener('pointerdown', onDown)
    canvas.addEventListener('pointermove', onMove)
    canvas.addEventListener('pointerup', onUp)
    canvas.addEventListener('pointercancel', onUp)

    const onContextLost = (event: Event) => {
      event.preventDefault()
      setLost(true)
    }
    canvas.addEventListener('webglcontextlost', onContextLost)

    // ── Resize ─────────────────────────────────────────────────────────────
    const resize = () => {
      const w = host.clientWidth
      const h = host.clientHeight
      if (!w || !h) return
      renderer.setSize(w, h)
      camera.aspect = w / h
      camera.updateProjectionMatrix()
    }
    const observer = new ResizeObserver(resize)
    observer.observe(host)
    window.addEventListener('resize', resize)

    // ── Loop ───────────────────────────────────────────────────────────────
    const clock = new THREE.Clock()
    let frame = 0

    const tick = () => {
      frame = requestAnimationFrame(tick)
      const elapsed = clock.getElapsedTime()

      let progress: number
      if (reduced) {
        progress = 1
      } else {
        const t = elapsed % LOOP
        if (t < HOLD_SCATTERED) progress = 0
        else if (t < HOLD_SCATTERED + RESOLVE) progress = ease((t - HOLD_SCATTERED) / RESOLVE)
        else if (t < HOLD_SCATTERED + RESOLVE + HOLD_RESOLVED) progress = 1
        else progress = 1 - ease((t - HOLD_SCATTERED - RESOLVE - HOLD_RESOLVED) / RETURN)
      }

      uniforms.uProgress.value = progress
      uniforms.uTime.value = reduced ? 0 : elapsed
      // Kept to a whisper: 05 has no visible spokes, and they would otherwise
      // cut straight through the headline.
      spokeMaterial.opacity = Math.pow(progress, 4) * 0.2
      // The bloom arrives with the core, and breathes very slightly once lit.
      bloomMaterial.opacity =
        Math.pow(progress, 3) * 0.95 * (reduced ? 1 : 1 + Math.sin(elapsed * 0.7) * 0.06)

      if (!reduced) {
        group.rotation.z += 0.0006 + velocity
        velocity *= 0.94
      }

      renderer.render(scene, camera)
    }
    tick()

    return () => {
      cancelAnimationFrame(frame)
      observer.disconnect()
      window.removeEventListener('resize', resize)
      canvas.removeEventListener('pointerdown', onDown)
      canvas.removeEventListener('pointermove', onMove)
      canvas.removeEventListener('pointerup', onUp)
      canvas.removeEventListener('pointercancel', onUp)
      canvas.removeEventListener('webglcontextlost', onContextLost)
      geometry.dispose()
      spokeGeometry.dispose()
      material.dispose()
      spokeMaterial.dispose()
      bloomTexture.dispose()
      bloomMaterial.dispose()
      renderer.dispose()
      if (canvas.parentNode === host) host.removeChild(canvas)
    }
  }, [])

  return (
    <div className="hero-field" ref={hostRef} aria-hidden="true">
      {lost && (
        <p className="hero-field-fallback" aria-hidden="false">
          The animation could not start on this device. Everything on this page works without it.
        </p>
      )}
    </div>
  )
}
