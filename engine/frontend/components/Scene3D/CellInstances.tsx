"use client";

/**
 * Organic4D — 세포 InstancedMesh (Phase 4.3)
 * IMPLEMENTATION_SEQUENCE 4.3a–d: setMatrixAt, useFrame + Float32Array, count, setColorAt
 */
import { useRef, useMemo, useEffect } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";

/** 노드 간 공유 — 매 프레임 new 방지 */
const tempObject = new THREE.Object3D();
const tempColor = new THREE.Color();

export type CellInstancesProps = {
  /** 최대 인스턴스 슬롯 (버퍼 크기) */
  maxInstances?: number;
  /** 현재 그릴 세포 수 */
  count: number;
  /** 연속 xyz, length >= count * 3 */
  positions: Float32Array;
  /** 선택: 인스턴스별 RGB 0~1, length >= count * 3 (Emotion 시각화 대비) */
  colors?: Float32Array | null;
};

export function CellInstances({
  maxInstances = 4096,
  count,
  positions,
  colors = null,
}: CellInstancesProps) {
  const meshRef = useRef<THREE.InstancedMesh>(null);

  const geometry = useMemo(
    () => new THREE.SphereGeometry(0.35, 8, 6),
    []
  );

  const material = useMemo(
    () =>
      new THREE.MeshStandardMaterial({
        metalness: 0.15,
        roughness: 0.55,
        vertexColors: true,
      }),
    []
  );

  useEffect(() => {
    return () => {
      geometry.dispose();
      material.dispose();
    };
  }, [geometry, material]);

  useFrame(() => {
    const mesh = meshRef.current;
    if (!mesh) return;

    const cap = Math.min(
      count,
      maxInstances,
      Math.floor(positions.length / 3)
    );
    mesh.count = cap;

    for (let i = 0; i < cap; i++) {
      const o = i * 3;
      tempObject.position.set(
        positions[o],
        positions[o + 1],
        positions[o + 2]
      );
      tempObject.updateMatrix();
      mesh.setMatrixAt(i, tempObject.matrix);

      if (colors && colors.length >= o + 3) {
        tempColor.setRGB(
          clamp01(colors[o]),
          clamp01(colors[o + 1]),
          clamp01(colors[o + 2])
        );
      } else {
        tempColor.setRGB(0.35, 0.72, 0.92);
      }
      mesh.setColorAt(i, tempColor);
    }

    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) {
      mesh.instanceColor.needsUpdate = true;
    }
  });

  return (
    <instancedMesh
      ref={meshRef}
      args={[geometry, material, maxInstances]}
      frustumCulled={false}
    />
  );
}

function clamp01(v: number): number {
  return Math.min(1, Math.max(0, v));
}
