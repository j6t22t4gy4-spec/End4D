"use client";

import { Canvas } from "@react-three/fiber";
import { OrbitControls, Grid } from "@react-three/drei";
import { CellInstances, type CellInstancesProps } from "./CellInstances";

type Scene3DCanvasProps = CellInstancesProps;

/**
 * God View 3D 캔버스 (Phase 4.2)
 * 카메라·조명·그리드 + CellInstances
 */
export default function Scene3DCanvas(props: Scene3DCanvasProps) {
  return (
    <div className="h-[min(70vh,560px)] w-full rounded-lg overflow-hidden border border-slate-700">
      <Canvas
        camera={{ position: [14, 10, 14], fov: 50 }}
        gl={{ antialias: true, alpha: false }}
        dpr={[1, 2]}
      >
        <color attach="background" args={["#0a0e14"]} />
        <ambientLight intensity={0.45} />
        <directionalLight position={[12, 18, 8]} intensity={1.1} />
        <Grid
          infiniteGrid
          fadeDistance={40}
          cellSize={1}
          cellColor="#1e3a4a"
          sectionColor="#2d5a6e"
        />
        <CellInstances {...props} />
        <OrbitControls makeDefault enableDamping dampingFactor={0.08} />
      </Canvas>
    </div>
  );
}
