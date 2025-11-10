export default function handler(req, res) {
  res.status(200).json({
    system: "Legal AI System",
    version: "1.0.0",
    status: "operational",
    databases: {
      postgresql_vector: {
        status: "connected",
        stats: {
          document_chunks: 1761,
          legal_documents: 338,
          legal_citations: 3267
        }
      },
      supabase_user_data: {
        status: "connected",
        purpose: "conversations, messages, user data"
      }
    },
    timestamp: new Date().toISOString()
  });
}