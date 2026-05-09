"use client";

import { Canvas } from "@react-three/fiber";
import { OrbitControls, Grid, Bounds } from "@react-three/drei";
import { CellInstances, type CellInstancesProps } from "./CellInstances";

type Scene3DCanvasProps = CellInstancesProps;

/**
 * God View 3D 캔버스 (Phase 4.2)
 * 카메라·조명·그리드 + CellInstances
 */
export default function Scene3DCanvas(props: Scene3DCanvasProps) {
  return (
    <div className="h-[min(72vh,680px)] w-full overflow-hidden rounded-[24px] border border-slate-200 bg-white">
      <Canvas
        camera={{ position: [14, 10, 14], fov: 50 }}
        gl={{ antialias: true, alpha: false }}
        dpr={[1, 2]}
      >
        <color attach="background" args={["#f8fafc"]} />
        <ambientLight intensity={0.7} />
        <directionalLight position={[12, 18, 8]} intensity={1.2} />
        <Grid
          infiniteGrid
          fadeDistance={40}
          cellSize={1}
          cellColor="#dbeafe"
          sectionColor="#93c5fd"
        />
        <Bounds fit clip observe margin={1.25}>
          <CellInstances {...props} />
        </Bounds>
        <OrbitControls makeDefault enableDamping dampingFactor={0.08} />
      </Canvas>
    </div>
  );
}
