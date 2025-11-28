# Migration Guide: Azure OpenAI to Microsoft Foundry

## Overview
This guide covers the migration from Azure OpenAI Service to Microsoft Foundry for the DAIOL Chatbot.

## Key Changes

### 1. Endpoint Format
- **Old**: `https://<resource>.openai.azure.com/`
- **New**: `https://<resource>.services.ai.azure.com/`

### 2. API Version
- **Old**: `2024-08-01-preview`
- **New**: `2024-12-01-preview` (or `2024-10-21`)

### 3. Authentication (Recommended)
**Best Practice**: Use Managed Identity instead of API keys in production.

#### For Development (API Key):
```python
client = AzureOpenAI(
    api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
    api_version="2024-12-01-preview",
    azure_endpoint="https://open-ai-service-class.services.ai.azure.com/",
)
```

#### For Production (Managed Identity):
```python
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

token_provider = get_bearer_token_provider(
    DefaultAzureCredential(),
    "https://cognitiveservices.azure.com/.default"
)

client = AzureOpenAI(
    azure_ad_token_provider=token_provider,
    api_version="2024-12-01-preview",
    azure_endpoint="https://open-ai-service-class.services.ai.azure.com/",
)
```

## Updated Files

### 1. `app.py`
- Updated `get_azure_client()` to support both authentication methods
- Added Managed Identity support for production deployments
- Maintains backward compatibility with API key authentication

### 2. `chatbot-plan-and-testing.ipynb`
- Updated endpoint to Foundry format
- Updated API version to `2024-12-01-preview`
- Fixed code to use `completion.choices[0].message.content` instead of `.text.strip()`

### 3. `requirements.txt`
- Added `azure-identity==1.19.0` for Managed Identity support

## Deployment Steps

### Step 1: Install Dependencies
```powershell
pip install -r requirements.txt
```

### Step 2: Update Environment Variables
Create a `.env` file based on `.env.example`:

```bash
AZURE_OPENAI_ENDPOINT=https://open-ai-service-class.services.ai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key-here
AZURE_OPENAI_API_VERSION=2024-12-01-preview
AZURE_OPENAI_DEPLOYMENT=gpt-4o-mini
```

### Step 3: Test Locally
```powershell
python app.py
```

### Step 4: Deploy to Azure App Service

#### Option A: Using API Key (Development)
Set the environment variables in Azure App Service configuration.

#### Option B: Using Managed Identity (Production - Recommended)
1. Enable Managed Identity on your App Service
2. Grant the Managed Identity access to your Foundry resource:
   - Role: `Cognitive Services OpenAI User`
3. Remove `AZURE_OPENAI_API_KEY` from App Service configuration
4. The app will automatically use Managed Identity

### Step 5: Configure Managed Identity (Production)

1. **Enable System-Assigned Managed Identity**:
   ```bash
   az webapp identity assign --name <app-name> --resource-group <resource-group>
   ```

2. **Grant Access to Foundry Resource**:
   ```bash
   az role assignment create \
     --assignee <managed-identity-principal-id> \
     --role "Cognitive Services OpenAI User" \
     --scope /subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.CognitiveServices/accounts/<foundry-resource-name>
   ```

## Testing

### Test the Migration
1. Run the notebook cells to verify Foundry connectivity
2. Test the `/api/health` endpoint
3. Test the `/api/start` endpoint to create a session
4. Test the `/api/chat` endpoint with a message

### Example Test (PowerShell):
```powershell
# Health check
Invoke-RestMethod -Uri "http://localhost:8000/api/health"

# Start session
$response = Invoke-RestMethod -Uri "http://localhost:8000/api/start" -Method POST -ContentType "application/json" -Body '{"userName":"Test User"}'
$token = $response.token

# Send chat message
Invoke-RestMethod -Uri "http://localhost:8000/api/chat" -Method POST -Headers @{"Authorization"=$token} -ContentType "application/json" -Body '{"message":"Hello!"}'
```

## Troubleshooting

### Error: "Authentication failed"
- Verify your endpoint URL is correct (`.services.ai.azure.com`)
- Check API key is valid
- For Managed Identity: Ensure role assignment is correct

### Error: "Model not found"
- Verify deployment name matches your Foundry deployment
- Check the model is deployed in your Foundry resource

### Error: "API version not supported"
- Use `2024-12-01-preview` or `2024-10-21`
- Older versions may not work with Foundry endpoints

## Benefits of Migration

1. **Access to More Models**: Foundry provides access to OpenAI and third-party models
2. **Better Performance**: Improved infrastructure and capabilities
3. **Enhanced Security**: Better support for Managed Identity
4. **Future-Proof**: Microsoft's strategic platform for AI services

## Resources

- [Microsoft Foundry Documentation](https://learn.microsoft.com/en-us/azure/ai-foundry/)
- [Azure OpenAI Migration Guide](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/migration)
- [Managed Identity Best Practices](https://learn.microsoft.com/en-us/entra/identity/managed-identities-azure-resources/overview)
