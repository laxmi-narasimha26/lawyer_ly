# Vercel Deployment Guide for Lawyer.ly

This guide will help you deploy your Legal AI application to Vercel.

## Project Structure

- **Frontend**: React + Vite + TypeScript (will be deployed to Vercel)
- **Backend**: Python FastAPI (needs separate deployment or serverless setup)

## Deployment Options

### Option 1: Deploy via Vercel Dashboard (Recommended - Easiest)

This is the simplest method and requires no command-line authentication:

1. **Go to [Vercel Dashboard](https://vercel.com/)**
   - Sign in or create a free account

2. **Import Your Repository**
   - Click "Add New..." → "Project"
   - Import your GitHub repository: `laxmi-narasimha26/lawyer_ly`
   - Select the branch: `claude/deploy-to-vercel-01LCYWaW8rZzUCaC9msKXRDF`

3. **Configure the Project**
   - Vercel will auto-detect the `vercel.json` configuration
   - Build Command: `cd frontend && npm install && npm run build`
   - Output Directory: `frontend/dist`
   - Install Command: `npm install` (in frontend directory)

4. **Environment Variables** (if needed)
   - Add any required environment variables in the Vercel dashboard
   - For the frontend, you might need:
     - `VITE_API_URL` - Your backend API URL

5. **Deploy**
   - Click "Deploy"
   - Vercel will build and deploy your frontend
   - You'll get a live URL like: `https://lawyer-ly.vercel.app`

### Option 2: Deploy via Vercel CLI

If you prefer using the command line:

1. **Authenticate with Vercel**
   ```bash
   vercel login
   ```
   This will open a browser for authentication.

2. **Deploy**
   ```bash
   # For production deployment
   vercel --prod

   # Or for preview deployment
   vercel
   ```

3. **Follow the prompts**
   - Set up and deploy: Yes
   - Which scope: Your account
   - Link to existing project: No (first time)
   - Project name: lawyer-ly
   - Directory: ./
   - Override settings: No (uses vercel.json)

### Option 3: Deploy via GitHub Integration (Recommended - Automatic)

This enables automatic deployments on every push:

1. **Connect GitHub to Vercel**
   - Go to [Vercel Dashboard](https://vercel.com/)
   - Click "Add New..." → "Project"
   - Authorize Vercel to access your GitHub repository

2. **Select Repository**
   - Choose `laxmi-narasimha26/lawyer_ly`
   - Vercel will automatically deploy on every push to your branch

3. **Benefits**
   - Automatic deployments on every git push
   - Preview deployments for pull requests
   - Automatic HTTPS
   - Global CDN
   - Built-in analytics

## Backend Deployment

The backend (Python FastAPI) is complex and has several dependencies:
- Database (PostgreSQL)
- Vector store
- RAG pipeline
- Azure Storage
- Monitoring services

### Recommended Backend Deployment Options:

#### Option 1: Deploy Backend to Render (Recommended)

Render is great for Python backends:

1. Go to [Render Dashboard](https://render.com/)
2. Create a new "Web Service"
3. Connect your GitHub repository
4. Configure:
   - **Build Command**: `cd backend && pip install -r requirements.txt`
   - **Start Command**: `cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Environment**: Python 3
5. Add environment variables (DATABASE_URL, OPENAI_API_KEY, etc.)
6. Deploy!

After deployment, update `vercel.json` with your backend URL:
```json
{
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://your-render-backend.onrender.com/api/:path*"
    }
  ]
}
```

#### Option 2: Deploy Backend to Railway

1. Go to [Railway](https://railway.app/)
2. Create a new project from your GitHub repo
3. Select the backend directory
4. Railway will auto-detect FastAPI
5. Add environment variables
6. Deploy!

#### Option 3: Deploy Backend to Fly.io

```bash
cd backend
flyctl launch
flyctl deploy
```

## Post-Deployment Configuration

### 1. Update Frontend API URL

If you deployed the backend separately, update the API URL in the frontend:

Create/update `frontend/.env.production`:
```env
VITE_API_URL=https://your-backend-url.com
```

### 2. Configure CORS in Backend

Update `backend/main.py` to allow requests from your Vercel frontend:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://lawyer-ly.vercel.app",  # Your Vercel URL
        "http://localhost:3000"  # For local development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 3. Set Up Environment Variables

In Vercel Dashboard, add any required environment variables:
- `VITE_API_URL` - Your backend API URL
- Any other frontend environment variables

### 4. Custom Domain (Optional)

1. Go to your Vercel project settings
2. Navigate to "Domains"
3. Add your custom domain
4. Update DNS records as instructed

## Vercel Configuration Details

The `vercel.json` file includes:

```json
{
  "version": 2,
  "buildCommand": "cd frontend && npm install && npm run build",
  "outputDirectory": "frontend/dist",
  "framework": null,
  "rewrites": [
    {
      "source": "/api/:path*",
      "destination": "https://your-backend-url.com/api/:path*"
    }
  ]
}
```

## Troubleshooting

### Build Fails

- Check that all dependencies are in `frontend/package.json`
- Verify Node.js version compatibility
- Check build logs in Vercel dashboard

### API Calls Fail

- Verify backend URL in `vercel.json` rewrites
- Check CORS configuration in backend
- Verify environment variables are set

### Environment Variables Not Working

- Ensure they start with `VITE_` prefix for Vite apps
- Redeploy after adding new variables

## Monitoring

- **Vercel Analytics**: Available in the Vercel dashboard
- **Logs**: Real-time logs in Vercel dashboard
- **Performance**: Built-in performance monitoring

## Costs

- **Vercel Free Tier**:
  - 100GB bandwidth
  - Unlimited deployments
  - Automatic HTTPS
  - Perfect for frontend hosting

- **Backend Hosting**:
  - Render: Free tier available (with limitations)
  - Railway: $5/month credit for free
  - Fly.io: Free tier available

## Next Steps

1. ✅ Vercel configuration created
2. ✅ Code pushed to GitHub
3. 🔲 Deploy via Vercel Dashboard (recommended)
4. 🔲 Deploy backend to Render/Railway
5. 🔲 Update API URL in vercel.json
6. 🔲 Configure CORS in backend
7. 🔲 Test the deployment

## Quick Deploy Command

If you have Vercel CLI authenticated:

```bash
# Production deployment
vercel --prod

# Preview deployment
vercel
```

## Support

- [Vercel Documentation](https://vercel.com/docs)
- [Vercel Support](https://vercel.com/support)
- [Render Documentation](https://render.com/docs)

---

**Current Status**: ✅ Configuration ready for deployment

The frontend is configured and ready to deploy to Vercel. You can now:
1. Use the Vercel Dashboard to import and deploy (easiest)
2. Use GitHub integration for automatic deployments
3. Use CLI after running `vercel login`
