import { Canvas } from '@react-three/fiber';
import { OrbitControls, PerspectiveCamera } from '@react-three/drei';
import { ReactNode, Suspense } from 'react';

interface Scene3DProps {
  children: ReactNode;
  className?: string;
  cameraPosition?: [number, number, number];
  enableControls?: boolean;
  enableZoom?: boolean;
  background?: string;
}

function Fallback() {
  return (
    <mesh>
      <boxGeometry args={[1, 1, 1]} />
      <meshStandardMaterial color="#666" wireframe />
    </mesh>
  );
}

export function Scene3D({
  children,
  className,
  cameraPosition = [0, 0, 5],
  enableControls = true,
  enableZoom = false,
  background = 'transparent',
}: Scene3DProps) {
  return (
    <div className={className}>
      <Canvas
        style={{ background }}
        gl={{ antialias: true, alpha: true }}
      >
        <PerspectiveCamera makeDefault position={cameraPosition} fov={50} />
        <ambientLight intensity={0.5} />
        <directionalLight position={[10, 10, 5]} intensity={1} />
        <Suspense fallback={<Fallback />}>
          {children}
        </Suspense>
        {enableControls && (
          <OrbitControls
            enableZoom={enableZoom}
            enablePan={false}
            autoRotate
            autoRotateSpeed={2}
          />
        )}
      </Canvas>
    </div>
  );
}
