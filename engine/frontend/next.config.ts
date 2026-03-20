import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /** R3F + react-reconciler가 앱과 동일한 React 인스턴스를 쓰도록 (청크 분리 시 ReactCurrentOwner 오류 방지) */
  transpilePackages: ["three", "@react-three/fiber", "@react-three/drei"],
  /** Phase 8: Docker 프로덕션 이미지용 standalone 번들 */
  output: "standalone",
};

export default nextConfig;
