const sessions = {};

export default function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const guest_id = `guest_${Date.now()}`;
    const token = `token_${guest_id}`;
    
    sessions[token] = {
      user_id: guest_id,
      email: `${guest_id}@guest.local`,
      full_name: "Guest User"
    };
    
    res.status(200).json({
      success: true,
      user: {
        id: guest_id,
        email: `${guest_id}@guest.local`,
        full_name: "Guest User"
      },
      access_token: token
    });
  } catch (error) {
    res.status(500).json({ success: false, error: 'Guest login failed' });
  }
}