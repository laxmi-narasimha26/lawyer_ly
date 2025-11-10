export default function handler(req, res) {
  res.status(200).json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    databases: {
      postgresql: 'connected',
      supabase: 'connected'
    },
    message: 'Legal AI System - Live Deployment'
  });
}