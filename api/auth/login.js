// Demo users
const users = {
  "admin@legalai.com": {
    id: "admin_001",
    email: "admin@legalai.com",
    password: "admin123",
    full_name: "Legal AI Admin"
  },
  "lawyer@legalai.com": {
    id: "lawyer_001", 
    email: "lawyer@legalai.com",
    password: "lawyer123",
    full_name: "Legal Professional"
  },
  "demo@legalai.com": {
    id: "demo_001",
    email: "demo@legalai.com",
    password: "demo123",
    full_name: "Demo User"
  }
};

const sessions = {};

export default function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const { email, password } = req.body;
    
    if (!users[email] || users[email].password !== password) {
      return res.status(401).json({ success: false, error: 'Invalid credentials' });
    }
    
    const user = users[email];
    const token = `token_${user.id}_${Date.now()}`;
    sessions[token] = {
      user_id: user.id,
      email: user.email,
      full_name: user.full_name
    };
    
    res.status(200).json({
      success: true,
      user: {
        id: user.id,
        email: user.email,
        full_name: user.full_name
      },
      access_token: token
    });
  } catch (error) {
    res.status(500).json({ success: false, error: 'Login failed' });
  }
}