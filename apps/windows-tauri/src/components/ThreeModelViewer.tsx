import { convertFileSrc } from "@tauri-apps/api/core";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OBJLoader } from "three/examples/jsm/loaders/OBJLoader.js";

type ThreeModelViewerProps = {
  modelPath: string | null;
  fallbackImage: string | null;
  modeLabel: string;
};

type ViewerStats = {
  triangles: number;
  vertices: number;
  dimensions: THREE.Vector3 | null;
};

const PLATE_SIZE_MM = 256;

export function ThreeModelViewer({ modelPath, fallbackImage, modeLabel }: ThreeModelViewerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [status, setStatus] = useState("Ready");
  const [stats, setStats] = useState<ViewerStats>({ triangles: 0, vertices: 0, dimensions: null });
  const modelUrl = useMemo(() => (modelPath ? resolveModelUrl(modelPath) : null), [modelPath]);
  const modelExtension = modelPath?.split(".").pop()?.toLowerCase() ?? "";
  const canLoadModel = modelUrl !== null && ["glb", "gltf", "obj"].includes(modelExtension);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !canLoadModel || !modelUrl) {
      setStatus(modelPath ? "3MF thumbnail mode" : "Waiting for model");
      setStats({ triangles: 0, vertices: 0, dimensions: null });
      return;
    }

    let disposed = false;
    setStatus("Loading geometry...");

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0b121c);

    const camera = new THREE.PerspectiveCamera(44, 1, 0.1, 100000);
    camera.position.set(180, 140, 220);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: "high-performance" });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    container.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.target.set(0, 40, 0);

    const hemi = new THREE.HemisphereLight(0xf5fbff, 0x172033, 1.45);
    scene.add(hemi);
    const key = new THREE.DirectionalLight(0xffffff, 2.4);
    key.position.set(150, 230, 180);
    key.castShadow = true;
    key.shadow.mapSize.set(1024, 1024);
    scene.add(key);
    const rim = new THREE.DirectionalLight(0x65d8ff, 0.95);
    rim.position.set(-220, 120, -170);
    scene.add(rim);

    const plate = createBuildPlate();
    scene.add(plate);

    const resize = () => {
      if (!container.isConnected) {
        return;
      }
      const rect = container.getBoundingClientRect();
      renderer.setSize(Math.max(1, rect.width), Math.max(1, rect.height), false);
      camera.aspect = Math.max(1, rect.width) / Math.max(1, rect.height);
      camera.updateProjectionMatrix();
    };

    const observer = new ResizeObserver(resize);
    observer.observe(container);
    resize();

    const render = () => {
      if (disposed) {
        return;
      }
      controls.update();
      renderer.render(scene, camera);
      window.requestAnimationFrame(render);
    };
    render();

    const loader = modelExtension === "obj" ? new OBJLoader() : new GLTFLoader();
    loader.load(
      modelUrl,
      (loaded) => {
        if (disposed) {
          return;
        }
        const object = "scene" in loaded ? loaded.scene : loaded;
        prepareModel(object);
        scene.add(object);
        const calculated = calculateStats(object);
        fitCamera(camera, controls, object);
        setStats(calculated);
        setStatus("Orbit viewer ready");
      },
      (event) => {
        if (event.total > 0) {
          setStatus(`Loading geometry ${Math.round((event.loaded / event.total) * 100)}%`);
        }
      },
      (error) => {
        console.error(error);
        setStatus("Could not load 3D model");
      }
    );

    return () => {
      disposed = true;
      observer.disconnect();
      controls.dispose();
      renderer.dispose();
      renderer.domElement.remove();
      scene.traverse((node) => {
        if (node instanceof THREE.Mesh) {
          node.geometry.dispose();
          disposeMaterial(node.material);
        }
      });
    };
  }, [canLoadModel, modelExtension, modelPath, modelUrl]);

  if (!canLoadModel) {
    return (
      <div className="three-viewer-fallback">
        {fallbackImage ? <img alt="3MF plate preview" src={fallbackImage} /> : <div className="preview-cube" aria-hidden="true" />}
        <div className="viewer-scale-card">
          <strong>{modeLabel}</strong>
          <span>Build plate reference: {PLATE_SIZE_MM} × {PLATE_SIZE_MM} mm</span>
          <span>{modelPath ? "Open a GLB or OBJ reference for orbit controls." : "Open a source or reference to preview scale."}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="three-viewer-wrap">
      <div className="three-canvas" ref={containerRef} />
      <div className="viewer-hud">
        <strong>{status}</strong>
        <span>{formatNumber(stats.triangles)} triangles</span>
        <span>{formatNumber(stats.vertices)} vertices</span>
        <span>{formatDimensions(stats.dimensions)}</span>
        <span>Plate {PLATE_SIZE_MM} × {PLATE_SIZE_MM} mm</span>
      </div>
    </div>
  );
}

function createBuildPlate() {
  const group = new THREE.Group();
  const plateGeometry = new THREE.BoxGeometry(PLATE_SIZE_MM, 1.2, PLATE_SIZE_MM);
  const plateMaterial = new THREE.MeshStandardMaterial({
    color: 0x162231,
    roughness: 0.65,
    metalness: 0.08,
    transparent: true,
    opacity: 0.86
  });
  const plate = new THREE.Mesh(plateGeometry, plateMaterial);
  plate.position.y = -0.7;
  plate.receiveShadow = true;
  group.add(plate);

  const grid = new THREE.GridHelper(PLATE_SIZE_MM, 16, 0x58d7ff, 0x2a4058);
  grid.position.y = 0.03;
  group.add(grid);

  const outline = new THREE.LineSegments(
    new THREE.EdgesGeometry(new THREE.BoxGeometry(PLATE_SIZE_MM, 1.4, PLATE_SIZE_MM)),
    new THREE.LineBasicMaterial({ color: 0x77e3ff, transparent: true, opacity: 0.55 })
  );
  outline.position.y = -0.6;
  group.add(outline);
  return group;
}

function resolveModelUrl(path: string) {
  if (path.startsWith("http://") || path.startsWith("https://") || path.startsWith("/") || path.startsWith("blob:")) {
    return path;
  }
  return convertFileSrc(path);
}

function prepareModel(object: THREE.Object3D) {
  const box = new THREE.Box3().setFromObject(object);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  const maxSize = Math.max(size.x, size.y, size.z);
  const scale = maxSize > 0 ? Math.min(1, 170 / maxSize) : 1;
  object.scale.multiplyScalar(scale);

  const scaledBox = new THREE.Box3().setFromObject(object);
  const scaledCenter = scaledBox.getCenter(new THREE.Vector3());
  object.position.sub(scaledCenter);
  const groundBox = new THREE.Box3().setFromObject(object);
  object.position.y -= groundBox.min.y;
  object.traverse((node) => {
    if (node instanceof THREE.Mesh) {
      node.castShadow = true;
      node.receiveShadow = true;
      if (!node.material) {
        node.material = new THREE.MeshStandardMaterial({ color: 0xd5d8dd, roughness: 0.72 });
      }
    }
  });
  center.set(0, 0, 0);
}

function fitCamera(camera: THREE.PerspectiveCamera, controls: OrbitControls, object: THREE.Object3D) {
  const box = new THREE.Box3().setFromObject(object);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  const maxSize = Math.max(size.x, size.y, size.z, PLATE_SIZE_MM);
  const distance = maxSize * 1.65;
  camera.position.set(center.x + distance, center.y + distance * 0.72, center.z + distance);
  camera.near = Math.max(0.1, distance / 1000);
  camera.far = distance * 12;
  camera.updateProjectionMatrix();
  controls.target.copy(center);
  controls.update();
}

function calculateStats(object: THREE.Object3D): ViewerStats {
  let triangles = 0;
  let vertices = 0;
  object.traverse((node) => {
    if (!(node instanceof THREE.Mesh)) {
      return;
    }
    const geometry = node.geometry;
    vertices += geometry.attributes.position?.count ?? 0;
    triangles += geometry.index ? geometry.index.count / 3 : (geometry.attributes.position?.count ?? 0) / 3;
  });
  const dimensions = new THREE.Box3().setFromObject(object).getSize(new THREE.Vector3());
  return { triangles: Math.round(triangles), vertices, dimensions };
}

function disposeMaterial(material: THREE.Material | THREE.Material[]) {
  const materials = Array.isArray(material) ? material : [material];
  for (const entry of materials) {
    entry.dispose();
  }
}

function formatNumber(value: number) {
  return new Intl.NumberFormat().format(value);
}

function formatDimensions(dimensions: THREE.Vector3 | null) {
  if (!dimensions) {
    return "Scale pending";
  }
  return `${dimensions.x.toFixed(0)} × ${dimensions.y.toFixed(0)} × ${dimensions.z.toFixed(0)} mm`;
}
