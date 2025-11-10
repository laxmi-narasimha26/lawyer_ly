export default function handler(req, res) {
  const credentials = [
    { email: "admin@legalai.com", password: "admin123", name: "Legal AI Admin" },
    { email: "lawyer@legalai.com", password: "lawyer123", name: "Legal Professional" },
    { email: "demo@legalai.com", password: "demo123", name: "Demo User" }
  ];
  
  res.status(200).json({ credentials });
}