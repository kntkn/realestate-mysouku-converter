# Claude API Setup for Vercel Deployment

## Step 1: Get Claude API Key
1. Visit https://console.anthropic.com/
2. Create an account or log in
3. Navigate to API Keys section
4. Create a new API key
5. Copy the key (it starts with 'sk-ant-')

## Step 2: Set Environment Variable in Vercel
1. Go to https://vercel.com/dashboard
2. Select your project: realestate-mysouku-converter
3. Go to Settings > Environment Variables
4. Add new variable:
   - Name: CLAUDE_API_KEY
   - Value: [your API key from step 1]
   - Environment: Production, Preview, Development

## Step 3: Redeploy
After setting the environment variable, redeploy:
```bash
vercel --prod
```

## Current Status
- ✅ Application deployed successfully
- ✅ Fallback mode working (default 25mm footer height)
- ⏳ Claude API integration ready (needs API key)

Without Claude API key, the system will use default footer region detection.
With Claude API key, AI will intelligently detect footer regions for better results.
