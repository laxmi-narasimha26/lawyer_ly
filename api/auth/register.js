// Simple in-memory storage for demo (in production, use a database)
const users = {};
const sessions = {};

export default function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const { email, password, full_name } = req.body;
    
    if (users[email]) {
      return res.status(400).json({ success: false, error: 'User already exists' });
    }
    
    const user_id = `user_${Date.now()}`;
    users[email] = {
      id: user_id,
      email,
      password,
      full_name
    };
    
    const token = `token_${user_id}_${Date.now()}`;
    sessions[token] = {
      user_id,
      email,
      full_name
    };
    
    res.status(200).json({
      success: true,
      user: {
        id: user_id,
        email,
        full_name
      },
      access_token: token
    });
  } catch (error) {
    res.status(500).json({ success: false, error: 'Registration failed' });
  }
}