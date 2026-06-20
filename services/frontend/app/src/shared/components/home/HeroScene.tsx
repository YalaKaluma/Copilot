import { useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Float, Environment, Stars } from '@react-three/drei';
import { EffectComposer, Bloom, Vignette } from '@react-three/postprocessing';
import * as THREE from 'three';

function FloatingShape({ position, color, speed = 1 }: { position: [number, number, number], color: string, speed?: number }) {
    const meshRef = useRef<THREE.Mesh>(null);
    const rotationAxis = useMemo(() => new THREE.Vector3(
        Math.random() - 0.5,
        Math.random() - 0.5,
        Math.random() - 0.5
    ).normalize(), []);

    useFrame((state) => {
        if (!meshRef.current) return;
        const t = state.clock.getElapsedTime();
        meshRef.current.rotation.x = Math.sin(t * 0.3 * speed) * 0.2;
        meshRef.current.rotation.y = Math.cos(t * 0.2 * speed) * 0.2;
        meshRef.current.rotateOnAxis(rotationAxis, 0.01 * speed);
    });

    return (
        <Float speed={2} rotationIntensity={0.5} floatIntensity={0.5}>
            <mesh ref={meshRef} position={position}>
                <dodecahedronGeometry args={[1, 0]} />
                <meshPhysicalMaterial
                    color={color}
                    roughness={0}
                    transmission={0.6}
                    thickness={0.5}
                    envMapIntensity={2}
                />
            </mesh>
        </Float>
    );
}

function Scene() {
    return (
        <>
            <Environment preset="city" />
            <Stars radius={100} depth={50} count={5000} factor={4} saturation={0} fade speed={1} />

            <ambientLight intensity={0.5} />
            <pointLight position={[10, 10, 10]} intensity={1.5} color="#4f46e5" />
            <pointLight position={[-10, -10, -10]} intensity={1} color="#ec4899" />

            <FloatingShape position={[2, 0, 0]} color="#4f46e5" speed={1.2} />
            <FloatingShape position={[-2, 1, -1]} color="#8b5cf6" speed={0.8} />
            <FloatingShape position={[0, -2, 1]} color="#ec4899" speed={1} />

            {/* Background Particles */}
            <group position={[0, 0, -5]}>
                {Array.from({ length: 20 }).map((_, i) => (
                    <FloatingShape
                        key={i}
                        position={[
                            (Math.random() - 0.5) * 20,
                            (Math.random() - 0.5) * 20,
                            (Math.random() - 0.5) * 10
                        ]}
                        color={['#4f46e5', '#8b5cf6', '#ec4899'][Math.floor(Math.random() * 3)]}
                        speed={0.5}
                    />
                ))}
            </group>

            <EffectComposer>
                <Bloom luminanceThreshold={1} mipmapBlur intensity={1.5} />
                <Vignette eskil={false} offset={0.1} darkness={0.5} />
            </EffectComposer>
        </>
    );
}

export function HeroScene() {
    return (
        <div className="absolute inset-0 z-0">
            <Canvas camera={{ position: [0, 0, 8], fov: 45 }}>
                <Scene />
            </Canvas>
        </div>
    );
}
