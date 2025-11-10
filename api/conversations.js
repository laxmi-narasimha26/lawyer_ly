const conversations = {};

export default function handler(req, res) {
  if (req.method === 'POST') {
    // Create conversation
    try {
      const { user_id, title } = req.body;
      const conversation_id = `conv_${user_id}_${Date.now()}`;
      
      conversations[conversation_id] = {
        id: conversation_id,
        user_id,
        title: title || "New Conversation",
        created_at: new Date().toISOString(),
        messages: []
      };
      
      res.status(200).json({ conversation_id });
    } catch (error) {
      res.status(500).json({ error: 'Failed to create conversation' });
    }
  } else if (req.method === 'GET') {
    // Get user conversations
    const { user_id } = req.query;
    const userConversations = Object.values(conversations).filter(conv => conv.user_id === user_id);
    res.status(200).json({ conversations: userConversations });
  } else {
    res.status(405).json({ error: 'Method not allowed' });
  }
}