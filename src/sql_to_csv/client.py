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
import logging
from azure.identity import DefaultAzureCredential
from openai import OpenAI

# Set up logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

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
        
        logger.info(f"Initializing Fabric Data Agent Client: tenant_id={tenant_id}")
        
        self._authenticate()
    
    def _authenticate(self):
        """
        Perform authentication using Azure CLI credentials.
        """
        try:
            logger.info("Starting Azure CLI authentication")
            logger.debug("Using credentials from: Azure CLI / Managed Identity")
            
            # Create credential using default Azure credential chain
            # This will try: environment variables, managed identity, Azure CLI, etc.
            self.credential = DefaultAzureCredential(
                exclude_interactive_browser_credential=True
            )
            
            # Get initial token
            self._refresh_token()
            
            logger.info("Authentication successful")
            
        except Exception as e:
            logger.error(f"Authentication failed: {e}", exc_info=True)
            raise
    
    def _refresh_token(self):
        """
        Refresh the authentication token.
        """
        try:
            logger.debug("Refreshing authentication token")
            if self.credential is None:
                raise ValueError("No credential available")
            self.token = self.credential.get_token("https://api.fabric.microsoft.com/.default")
            logger.debug(f"Token obtained, expires at: {time.ctime(self.token.expires_on)}")
            
        except Exception as e:
            logger.error(f"Token refresh failed: {e}", exc_info=True)
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
        
        logger.info(f"[ask] Starting query: {question}")
        
        try:
            logger.debug("[ask] Creating OpenAI client")
            client = self._get_openai_client()
            
            # Create assistant without specifying model or instructions
            logger.debug("[ask] Creating assistant")
            assistant = client.beta.assistants.create(model="not used")
            logger.debug(f"[ask] Assistant created: {assistant.id}")
            
            # Create thread and send message
            logger.debug("[ask] Creating/getting thread")
            thread = self._get_existing_or_create_new_thread(
                data_agent_url=self.data_agent_url, 
                thread_name=thread_name
                )
            logger.debug(f"[ask] Thread: {thread['id']}")

            logger.debug("[ask] Sending user message")
            client.beta.threads.messages.create(
                thread_id=thread['id'],
                role="user",
                content=question
            )
            
            # Start the run
            logger.debug("[ask] Creating run")
            run = client.beta.threads.runs.create(
                thread_id=thread['id'],
                assistant_id=assistant.id
            )
            logger.debug(f"[ask] Run created: {run.id}, status: {run.status}")
            
            # Monitor the run with timeout
            start_time = time.time()
            iteration = 0
            while run.status in ["queued", "in_progress"]:
                if time.time() - start_time > timeout:
                    logger.warning(f"[ask] Request timed out after {timeout} seconds")
                    break
                
                iteration += 1
                elapsed = time.time() - start_time
                logger.debug(f"[ask] Iteration {iteration}, elapsed: {elapsed:.1f}s, status: {run.status}")
                time.sleep(2)
                
                run = client.beta.threads.runs.retrieve(
                    thread_id=thread['id'],
                    run_id=run.id
                )
            
            logger.info(f"[ask] Run completed with status: {run.status}")
            
            # Store run details for later retrieval
            self._last_run_id = run.id
            self._last_thread_id = thread['id']
            
            # Get the response messages
            logger.debug("[ask] Retrieving messages")
            messages = client.beta.threads.messages.list(
                thread_id=thread['id'],
                order="asc"
            )
            logger.debug(f"[ask] Got {len(messages.data)} messages")

            # Extract assistant responses
            responses = []
            for idx, msg in enumerate(messages.data):
                logger.debug(f"[ask] Message {idx}: role={msg.role}")
                if msg.role == "assistant":
                    try:
                        if msg.content and len(msg.content) > 0:
                            content = msg.content[0]
                            logger.debug(f"[ask] Content type: {type(content)}, has text attr: {hasattr(content, 'text')}")
                            
                            # Handle text content
                            if hasattr(content, 'text'):
                                text_content = getattr(content, 'text', None)
                                logger.debug(f"[ask] text_content type: {type(text_content)}")
                                if text_content is not None:
                                    if hasattr(text_content, 'value'):
                                        # Extract the actual text value
                                        text_value = text_content.value
                                        logger.debug(f"[ask] Got text value, length: {len(text_value)}")
                                        # Ensure it's properly encoded as UTF-8
                                        if isinstance(text_value, bytes):
                                            logger.debug("[ask] Converting bytes to string")
                                            text_value = text_value.decode('utf-8', errors='replace')
                                        responses.append(str(text_value))
                                    else:
                                        # Direct string or object
                                        logger.debug("[ask] text_content is direct string/object")
                                        responses.append(str(text_content))
                            else:
                                # Fallback: convert content to string
                                logger.debug("[ask] No text attribute, converting content to string")
                                responses.append(str(content))
                        else:
                            logger.warning("[ask] Empty content in message")
                            responses.append("Empty response from assistant")
                    except (IndexError, AttributeError, UnicodeDecodeError) as e:
                        logger.error(f"[ask] Error extracting message content: {e}", exc_info=True)
                        # Last resort: convert entire message to string
                        try:
                            responses.append(str(msg.content))
                        except Exception as fallback_error:
                            logger.error(f"[ask] Fallback conversion failed: {fallback_error}", exc_info=True)
                            responses.append("Unable to extract response text")
            
            logger.info(f"[ask] Extracted {len(responses)} responses")
            
            # Return the response
            if responses:
                final_response = "\n".join(responses)
                logger.debug(f"[ask] Final response length: {len(final_response)}")
                # Final encoding check
                try:
                    final_response.encode('utf-8')
                except UnicodeEncodeError as e:
                    logger.warning(f"[ask] Response contains invalid characters: {e}")
                    final_response = final_response.encode('utf-8', errors='replace').decode('utf-8')
                logger.info(f"[ask] Query completed successfully, response length: {len(final_response)}")
                return final_response
            else:
                logger.warning("[ask] No responses extracted")
                return "No response received from the data agent."
        
        except Exception as e:
            logger.error(f"[ask] Error calling data agent: {e}", exc_info=True)
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
            logger.error(f"Error getting run details: {e}", exc_info=True)
            raise
