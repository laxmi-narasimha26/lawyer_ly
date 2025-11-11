import Galaxy from './Galaxy';

export default function GalaxyTest() {
  return (
    <div className="w-screen h-screen bg-black">
      <Galaxy
        mouseRepulsion={true}
        mouseInteraction={true}
        density={1.5}
        glowIntensity={0.5}
        saturation={0.6}
        hueShift={240}
        twinkleIntensity={0.4}
        rotationSpeed={0.05}
        transparent={false}
      />
      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className="bg-white/90 backdrop-blur-md rounded-lg shadow-xl p-8 border border-white/20">
          <h1 className="text-3xl font-bold text-gray-900">Galaxy Background Test</h1>
          <p className="mt-4 text-gray-600">Move your mouse to interact with the stars!</p>
        </div>
      </div>
    </div>
  );
}
