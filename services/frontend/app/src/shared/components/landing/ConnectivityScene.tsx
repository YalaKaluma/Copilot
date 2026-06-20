import { useRef, useMemo, useState, useEffect } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Points, PointMaterial } from '@react-three/drei';
import * as THREE from 'three';
import { useTheme } from '../../providers/ThemeProvider';

// Animated data packet that travels along connections
function DataPacket({
  startPoint,
  endPoint,
  color,
  delay
}: {
  startPoint: THREE.Vector3;
  endPoint: THREE.Vector3;
  color: string;
  delay: number;
}) {
  const ref = useRef<THREE.Mesh>(null!);
  const [progress, setProgress] = useState(0);

  useFrame((state) => {
    const t = ((state.clock.getElapsedTime() + delay) % 3) / 3;
    setProgress(t);

    if (ref.current) {
      ref.current.position.lerpVectors(startPoint, endPoint, t);
      // Pulse effect
      const scale = 0.8 + Math.sin(t * Math.PI) * 0.4;
      ref.current.scale.setScalar(scale);
    }
  });

  // Only show when in transit
  const opacity = progress > 0.05 && progress < 0.95 ? 1 : 0;

  return (
    <mesh ref={ref}>
      <sphereGeometry args={[0.08, 8, 8]} />
      <meshBasicMaterial color={color} transparent opacity={opacity} />
    </mesh>
  );
}

function NetworkNodes({ theme }: { theme: string }) {
  const nodeCount = 80;
  const connectionDistance = 4;

  // Generate node positions in a more structured pattern
  const nodes = useMemo(() => {
    const positions: THREE.Vector3[] = [];

    // Create nodes in a spherical distribution with clustering
    for (let i = 0; i < nodeCount; i++) {
      const phi = Math.acos(-1 + (2 * i) / nodeCount);
      const theta = Math.sqrt(nodeCount * Math.PI) * phi;

      const radius = 6 + Math.random() * 2;
      const x = radius * Math.cos(theta) * Math.sin(phi);
      const y = radius * Math.sin(theta) * Math.sin(phi);
      const z = radius * Math.cos(phi);

      positions.push(new THREE.Vector3(x, y, z));
    }
    return positions;
  }, []);

  // Create connections between nearby nodes
  const connections = useMemo(() => {
    const lines: { start: THREE.Vector3; end: THREE.Vector3 }[] = [];

    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const dist = nodes[i].distanceTo(nodes[j]);
        if (dist < connectionDistance) {
          lines.push({ start: nodes[i], end: nodes[j] });
        }
      }
    }
    return lines;
  }, [nodes]);

  // Points buffer
  const pointsArray = useMemo(() => {
    const arr = new Float32Array(nodes.length * 3);
    nodes.forEach((node, i) => {
      arr[i * 3] = node.x;
      arr[i * 3 + 1] = node.y;
      arr[i * 3 + 2] = node.z;
    });
    return arr;
  }, [nodes]);

  // Lines buffer
  const linesArray = useMemo(() => {
    const arr: number[] = [];
    connections.forEach(({ start, end }) => {
      arr.push(start.x, start.y, start.z, end.x, end.y, end.z);
    });
    return new Float32Array(arr);
  }, [connections]);

  const groupRef = useRef<THREE.Group>(null!);
  const pointsRef = useRef<THREE.Points>(null!);

  useFrame((state) => {
    const t = state.clock.getElapsedTime();
    groupRef.current.rotation.y = t * 0.03;
    groupRef.current.rotation.x = Math.sin(t * 0.02) * 0.1;
  });

  // Theme-based colors
  const isDark = theme === 'dark';
  const nodeColor = isDark ? '#818cf8' : '#6366f1';
  const lineColor = isDark ? '#4f46e5' : '#a5b4fc';
  const packetColor = isDark ? '#22d3ee' : '#06b6d4';

  // Select some connections for data packets
  const packetConnections = useMemo(() => {
    return connections.slice(0, Math.min(15, connections.length));
  }, [connections]);

  return (
    <group ref={groupRef}>
      {/* Main nodes */}
      <Points ref={pointsRef} positions={pointsArray} stride={3} frustumCulled={false}>
        <PointMaterial
          transparent
          color={nodeColor}
          size={0.12}
          sizeAttenuation={true}
          depthWrite={false}
          opacity={isDark ? 0.9 : 0.7}
        />
      </Points>

      {/* Connection lines */}
      <lineSegments>
        <bufferGeometry>
          <bufferAttribute
            attach="attributes-position"
            count={linesArray.length / 3}
            array={linesArray}
            itemSize={3}
          />
        </bufferGeometry>
        <lineBasicMaterial
          color={lineColor}
          transparent
          opacity={isDark ? 0.15 : 0.1}
        />
      </lineSegments>

      {/* Animated data packets */}
      {packetConnections.map((conn, i) => (
        <DataPacket
          key={i}
          startPoint={conn.start}
          endPoint={conn.end}
          color={packetColor}
          delay={i * 0.4}
        />
      ))}

      {/* Central hub glow */}
      <mesh position={[0, 0, 0]}>
        <sphereGeometry args={[0.5, 32, 32]} />
        <meshBasicMaterial
          color={isDark ? '#6366f1' : '#4f46e5'}
          transparent
          opacity={0.1}
        />
      </mesh>
      <mesh position={[0, 0, 0]}>
        <sphereGeometry args={[1, 32, 32]} />
        <meshBasicMaterial
          color={isDark ? '#6366f1' : '#4f46e5'}
          transparent
          opacity={0.05}
        />
      </mesh>
    </group>
  );
}

// Floating particles for atmosphere
function FloatingParticles({ theme }: { theme: string }) {
  const count = 200;
  const ref = useRef<THREE.Points>(null!);

  const positions = useMemo(() => {
    const arr = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      arr[i * 3] = (Math.random() - 0.5) * 30;
      arr[i * 3 + 1] = (Math.random() - 0.5) * 30;
      arr[i * 3 + 2] = (Math.random() - 0.5) * 30;
    }
    return arr;
  }, []);

  useFrame((state) => {
    const t = state.clock.getElapsedTime();
    ref.current.rotation.y = t * 0.01;
    ref.current.rotation.x = t * 0.005;
  });

  const isDark = theme === 'dark';

  return (
    <Points ref={ref} positions={positions} stride={3} frustumCulled={false}>
      <PointMaterial
        transparent
        color={isDark ? '#475569' : '#cbd5e1'}
        size={0.03}
        sizeAttenuation={true}
        depthWrite={false}
        opacity={isDark ? 0.5 : 0.3}
      />
    </Points>
  );
}

export function ConnectivityScene() {
  const { theme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) return null;

  return (
    <div className="absolute inset-0 z-0 pointer-events-none">
      <Canvas
        camera={{ position: [0, 0, 15], fov: 55 }}
        gl={{ antialias: true, alpha: true }}
      >
        <ambientLight intensity={0.4} />
        <pointLight position={[10, 10, 10]} intensity={0.3} />
        <FloatingParticles theme={theme} />
        <NetworkNodes theme={theme} />
      </Canvas>
    </div>
  );
}
