#!/usr/bin/env python3
"""
Fabric Data Agent External Client - Modified for Azure CLI Authentication

A standalone Python client for calling Microsoft Fabric Data Agents from outside
of the Fabric environment using Azure CLI authentication.

Differences from original:
- Uses DefaultAzureCredential instead of InteractiveBrowserCredential
- Works with Azure CLI logged-in sessions
- No browser popup needed

Requirements:
- azure-identity
- openai

Usage:
1. Ensure you're logged in with Azure CLI: `az login`
2. Set your TENANT_ID and DATA_AGENT_URL in the script or environment variables
3. Run the script - it will use your Azure CLI credentials
"""

import time
import uuid
import requests
import warnings
from azure.identity import DefaultAzureCredential
from openai import OpenAI

# Suppress OpenAI Assistants API deprecation warnings
warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    message=r".*Assistants API is deprecated.*"
)


class FabricDataAgentClient:
    """
    Client for calling Microsoft Fabric Data Agents from external applications.
    Uses Azure CLI credentials (DefaultAzureCredential).
    
    This client handles:
    - Azure CLI authentication (no browser needed)
    - Automatic token refresh
    - Bearer token management for API calls
    - Proper cleanup of resources
    """
    
    def __init__(self, tenant_id: str, data_agent_url: str):
        """
        Initialize the Fabric Data Agent client.
        
        Args:
            tenant_id (str): Your Azure tenant ID
            data_agent_url (str): The published URL of your Fabric Data Agent
        """
        self.tenant_id = tenant_id
        self.data_agent_url = data_agent_url
        self.credential = None
        self.token = None
        self._last_run_id = None
        self._last_thread_id = None
        self._last_run_details = None
        
        # Validate inputs
        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not data_agent_url:
            raise ValueError("data_agent_url is required")
        
        print(f"Initializing Fabric Data Agent Client (Azure CLI Mode)...")
        print(f"Tenant ID: {tenant_id}")
        print(f"Data Agent URL: {data_agent_url}")
        
        self._authenticate()
    
    def _authenticate(self):
        """
        Perform authentication using Azure CLI credentials.
        """
        try:
            print("\n Starting Azure CLI authentication...")
            print("Using credentials from: Azure CLI / Managed Identity")
            
            # Create credential using default Azure credential chain
            # This will try: environment variables, managed identity, Azure CLI, etc.
            self.credential = DefaultAzureCredential(
                exclude_interactive_browser_credential=True
            )
            
            # Get initial token
            self._refresh_token()
            
            print(" Authentication successful!")
            
        except Exception as e:
            print(f" Authentication failed: {e}")
            raise
    
    def _refresh_token(self):
        """
        Refresh the authentication token.
        """
        try:
            print(" Refreshing authentication token...")
            if self.credential is None:
                raise ValueError("No credential available")
            self.token = self.credential.get_token("https://api.fabric.microsoft.com/.default")
            print(f" Token obtained, expires at: {time.ctime(self.token.expires_on)}")
            
        except Exception as e:
            print(f" Token refresh failed: {e}")
            raise
    
    def _get_openai_client(self) -> OpenAI:
        """
        Create an OpenAI client configured for Fabric Data Agent calls.
        
        Returns:
            OpenAI: Configured OpenAI client
        """
        # Check if token needs refresh (refresh 5 minutes before expiry)
        if self.token and self.token.expires_on <= (time.time() + 300):
            self._refresh_token()
        
        if not self.token:
            raise ValueError("No valid authentication token available")
        
        return OpenAI(
            api_key="",  # Not used - we use Bearer token
            base_url=self.data_agent_url,
            default_query={"api-version": "2024-05-01-preview"},
            default_headers={
                "Authorization": f"Bearer {self.token.token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "ActivityId": str(uuid.uuid4())
            }
        )

    def _get_existing_or_create_new_thread(self, data_agent_url: str, thread_name = None) -> dict:
        """
        Get an existing thread or Create a new thread for the target Fabric Data Agent.

        Args:
            data_agent_url (str): The URL of the Fabric Data Agent
            thread_name (str, optional): Name for the new or existing thread. If None, a random name is generated.

        Returns:
            list: A list containing the ID and name of the created thread or existing thread
        """
        if thread_name == None:
            thread_name = f'external-client-thread-{uuid.uuid4()}'
        
        if "aiskills" in data_agent_url:
            base_url = data_agent_url.replace("aiskills", "dataagents").removesuffix("/openai").replace("/aiassistant","/__private/aiassistant")
        else:
            base_url = data_agent_url.removesuffix("/openai").replace("/aiassistant","/__private/aiassistant")
        
        get_new_thread_url = f'{base_url}/threads/fabric?tag="{thread_name}"'

        headers = {
            "Authorization": f"Bearer {self.token.token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "ActivityId": str(uuid.uuid4())
        }

        response = requests.get(get_new_thread_url, headers=headers)
        response.raise_for_status()
        thread = response.json()
        thread["name"] = thread_name

        return thread

    def ask(self, question: str, timeout: int = 120, thread_name = None) -> str:
        """
        Ask a question to the Fabric Data Agent.
        
        Args:
            question (str): The question to ask
            timeout (int): Maximum time to wait for response in seconds
            thread_name (str, optional): The name of the thread to use

        Returns:
            str: The response from the data agent
        """
        if not question.strip():
            raise ValueError("Question cannot be empty")
        
        print(f"\n Asking: {question}")
        
        try:
            client = self._get_openai_client()
            
            # Create assistant without specifying model or instructions
            assistant = client.beta.assistants.create(model="not used")
            
            # Create thread and send message
            thread = self._get_existing_or_create_new_thread(
                data_agent_url=self.data_agent_url, 
                thread_name=thread_name
                )

            client.beta.threads.messages.create(
                thread_id=thread['id'],
                role="user",
                content=question
            )
            
            # Start the run
            run = client.beta.threads.runs.create(
                thread_id=thread['id'],
                assistant_id=assistant.id
            )
            
            # Monitor the run with timeout
            start_time = time.time()
            while run.status in ["queued", "in_progress"]:
                if time.time() - start_time > timeout:
                    print(f"⏰ Request timed out after {timeout} seconds")
                    break
                
                print(f"⏳ Status: {run.status}")
                time.sleep(2)
                
                run = client.beta.threads.runs.retrieve(
                    thread_id=thread['id'],
                    run_id=run.id
                )
            
            print(f" Final status: {run.status}")
            
            # Store run details for later retrieval
            self._last_run_id = run.id
            self._last_thread_id = thread['id']
            
            # Get the response messages
            messages = client.beta.threads.messages.list(
                thread_id=thread['id'],
                order="asc"
            )

            # Extract assistant responses
            responses = []
            for msg in messages.data:
                if msg.role == "assistant":
                    try:
                        content = msg.content[0]
                        if hasattr(content, 'text'):
                            text_content = getattr(content, 'text', None)
                            if text_content is not None and hasattr(text_content, 'value'):
                                responses.append(text_content.value)
                            elif text_content is not None:
                                responses.append(str(text_content))
                            else:
                                responses.append(str(content))
                        else:
                            responses.append(str(content))
                    except (IndexError, AttributeError):
                        responses.append(str(msg.content))
            
            # Return the response
            if responses:
                return "\n".join(responses)
            else:
                return "No response received from the data agent."
        
        except Exception as e:
            print(f" Error calling data agent: {e}")
            return f"Error: {e}"
    
    def get_run_details(self, question: str = None, thread_name=None) -> dict:
        """
        Get detailed run information for the last query.
        
        Args:
            question (str, optional): Ignored - kept for API compatibility
            thread_name (str, optional): Ignored - kept for API compatibility
            
        Returns:
            dict: Detailed response including run steps, metadata from the last query
        """
        if not self._last_run_id or not self._last_thread_id:
            raise ValueError("No previous run found. Call ask() first.")
        
        try:
            client = self._get_openai_client()
            
            # Retrieve the stored run without making a new query
            run = client.beta.threads.runs.retrieve(
                thread_id=self._last_thread_id,
                run_id=self._last_run_id
            )
            
            # Get all run steps
            run_steps = client.beta.threads.runs.steps.list(
                thread_id=self._last_thread_id,
                run_id=self._last_run_id
            )

            # Get messages
            messages = client.beta.threads.messages.list(
                thread_id=self._last_thread_id,
                order="asc"
            )

            # Build detailed response
            return {
                "run_id": run.id,
                "thread_id": self._last_thread_id,
                "status": run.status,
                "created_at": run.created_at,
                "messages": {
                    "data": [
                        {
                            "id": msg.id,
                            "role": msg.role,
                            "content": [
                                {
                                    "type": getattr(content, 'type', 'unknown'),
                                    "text": getattr(getattr(content, 'text', None), 'value', str(content))
                                    if hasattr(content, 'text') else str(content)
                                }
                                for content in msg.content
                            ]
                        }
                        for msg in messages.data
                    ]
                },
                "run_steps": {
                    "data": [
                        {
                            "id": step.id,
                            "type": step.type,
                            "status": step.status,
                            "step_details": getattr(step, 'step_details', None),
                            "created_at": step.created_at,
                            "error": getattr(step, 'last_error', None)
                        }
                        for step in run_steps.data
                    ]
                }
            }
        
        except Exception as e:
            print(f" Error getting run details: {e}")
            raise
